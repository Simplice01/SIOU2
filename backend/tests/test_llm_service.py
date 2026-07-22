"""Tests unitaires du client LLM (backend/services/llm.py).

Le transport HTTP est simulé (monkeypatch de httpx.AsyncClient) : on vérifie le
mapping de la réponse (format OpenAI / Groq) et la conversion des erreurs en
LLMError, sans dépendre d'un service LLM réel.
"""

import httpx
import pytest

from backend.services import llm


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class _FakeClient:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json, headers=None):
        if self._exc is not None:
            raise self._exc
        return self._response


def _patch_client(monkeypatch, **kwargs):
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda *a, **k: _FakeClient(**kwargs))


async def test_generate_answer_maps_openai_response(monkeypatch):
    payload = {
        "model": "llama-3.3-70b-versatile",
        "choices": [
            {"message": {"role": "assistant", "content": "Bonjour, voici la réponse."}}
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 34},
    }
    _patch_client(monkeypatch, response=_FakeResponse(payload))

    out = await llm.generate_answer("Salut", ["contexte"])

    assert out["text"] == "Bonjour, voici la réponse."
    assert out["model"] == "llama-3.3-70b-versatile"
    assert out["prompt_tokens"] == 12
    assert out["completion_tokens"] == 34
    assert isinstance(out["latency_ms"], int) and out["latency_ms"] >= 0


async def test_generate_answer_raises_on_transport_error(monkeypatch):
    _patch_client(monkeypatch, exc=httpx.ConnectError("connection refused"))

    with pytest.raises(llm.LLMError):
        await llm.generate_answer("Salut", None)


async def test_generate_answer_raises_on_empty_content(monkeypatch):
    _patch_client(
        monkeypatch,
        response=_FakeResponse({"choices": [{"message": {"content": "   "}}]}),
    )

    with pytest.raises(llm.LLMError):
        await llm.generate_answer("Salut", None)


def test_build_chat_messages_includes_context():
    messages = llm.build_chat_messages("Ma question", ["chunk A", "chunk B"])

    assert messages[0]["role"] == "system"
    assert any("chunk A" in m["content"] for m in messages)
    assert messages[-1] == {"role": "user", "content": "Ma question"}
