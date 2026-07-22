"""Service LLM : construction des messages et génération via une API compatible OpenAI.

Le client parle le format OpenAI (`POST /chat/completions`), donc interchangeable
entre **Groq, Mistral, Gemini, OpenAI** et **Ollama** (endpoint `/v1`), au choix
via `.env` (base_url, api_key, model). Le module expose des *builders* purs
(testables sans I/O) et `generate_answer`. Toute erreur de transport/protocole
est convertie en `LLMError`, que le routeur traduit en réponse HTTP (503).
"""

import json
import time
from collections.abc import AsyncIterator

import httpx

from backend.core.config import settings


class LLMError(Exception):
    """Le service de génération est indisponible ou a renvoyé une réponse invalide."""


def build_system_prompt(extra_context: str | None = None) -> str:
    if not extra_context:
        return settings.system_prompt
    return f"{settings.system_prompt}\n\nContexte additionnel:\n{extra_context}"


def build_chat_messages(question: str, context_chunks: list[str] | None = None) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": build_system_prompt()}]
    if context_chunks:
        messages.append(
            {
                "role": "system",
                "content": "Contexte documentaire:\n" + "\n\n".join(context_chunks),
            }
        )
    messages.append({"role": "user", "content": question})
    return messages


async def generate_answer(question: str, context_chunks: list[str] | None = None) -> dict:
    """Génère une réponse via une API compatible OpenAI (`POST /chat/completions`).

    Retourne le texte et les métriques LLMOps (tokens, latence) pour persistance.
    Lève `LLMError` si le service est injoignable ou répond de façon invalide.
    """
    messages = build_chat_messages(question, context_chunks=context_chunks)
    body = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
        "stream": False,
    }
    headers = {}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
            response = await client.post(
                f"{settings.llm_base_url}/chat/completions", json=body, headers=headers
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise LLMError(f"Service LLM injoignable : {exc}") from exc

    choices = data.get("choices") or []
    content = (choices[0].get("message", {}).get("content") or "" if choices else "").strip()
    if not content:
        raise LLMError("Réponse du service LLM vide ou malformée.")

    usage = data.get("usage") or {}
    return {
        "text": content,
        "model": data.get("model") or settings.llm_model,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }


async def stream_answer(question: str, context_chunks: list[str] | None = None) -> AsyncIterator[str]:
    """Génère la réponse **en flux** via une API compatible OpenAI (`stream: true`).

    Générateur asynchrone : *yield* chaque fragment de texte (delta) dès qu'il
    arrive, pour un affichage au fil de l'eau côté client (SSE). Lève `LLMError`
    si le service est injoignable ou renvoie un flux invalide — l'appelant décide
    alors comment le signaler dans le flux SSE.
    """
    messages = build_chat_messages(question, context_chunks=context_chunks)
    body = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
        "stream": True,
    }
    headers = {}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
            async with client.stream(
                "POST", f"{settings.llm_base_url}/chat/completions", json=body, headers=headers
            ) as response:
                if response.status_code >= 400:
                    # Sur une réponse streamée, le corps d'erreur doit être lu explicitement.
                    await response.aread()
                    raise LLMError(f"Service LLM erreur {response.status_code} : {response.text}")

                async for line in response.aiter_lines():
                    # Protocole SSE OpenAI : lignes « data: {json} », terminées par « data: [DONE] ».
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[len("data:") :].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        payload = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
                    choices = payload.get("choices") or []
                    if not choices:
                        continue
                    delta = (choices[0].get("delta") or {}).get("content")
                    if delta:
                        yield delta
    except httpx.HTTPError as exc:
        raise LLMError(f"Service LLM injoignable : {exc}") from exc
