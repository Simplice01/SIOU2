"""Tests pour backend/routers/chat.py (POST /api/chat).

Le pipeline RAG + LLM est mocké (`retrieve_context`, `generate_answer`) pour
rester déterministe et sans I/O. Ces tests couvrent : l'authentification, la
création/rattachement de conversation, la persistance des messages, et le
**confidence gate** (refus sans source ou sous le seuil `rag_min_score`).
"""

import json
import uuid

import pytest

from backend.routers.chat import REFUSAL_TEXT
from backend.tests.conftest import auth_header


@pytest.fixture(autouse=True)
def mock_rag(monkeypatch):
    """Rend le pipeline RAG déterministe et rapide pour les tests.

    - `generate_answer` : réponse simulée (pas d'appel Ollama), avec compteur.
    - `retrieve_context` : renvoie [] par défaut (pas de chargement torch ni de
      SQL pgvector). Les tests qui veulent du contexte le surchargent.
    """
    calls = {"generate": 0}

    async def fake_generate_answer(question, context_chunks=None):
        calls["generate"] += 1
        return {
            "text": f"Réponse simulée à : {question}",
            "model": "mistral-test",
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "latency_ms": 5,
        }

    async def fake_retrieve_context(question, top_k, rrf_k):
        return []

    monkeypatch.setattr("backend.routers.chat.generate_answer", fake_generate_answer)
    monkeypatch.setattr("backend.routers.chat.retrieve_context", fake_retrieve_context)
    return calls


async def test_ask_question_without_context_refuses(client, user_token, mock_rag):
    """Sans source documentaire : SIOU refuse, sans appeler le LLM."""
    response = await client.post(
        "/api/chat",
        json={"question": "Une question hors corpus documentaire"},
        headers=auth_header(user_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == REFUSAL_TEXT
    assert body["sources"] == []
    assert mock_rag["generate"] == 0  # confidence gate : pas d'appel LLM


async def test_ask_question_with_context_generates(client, user_token, monkeypatch, mock_rag):
    """Avec du contexte : SIOU appelle le LLM et renvoie les sources citées."""

    async def fake_retrieve_context(question, top_k, rrf_k):
        return [
            {
                "chunk_id": uuid.uuid4(),
                "document_id": uuid.uuid4(),
                "content": "Extrait pertinent du décret.",
                "page_number": 1,
                "score": 0.031,  # RRF (classement)
                "similarity": 0.82,  # cosinus > rag_min_score : passe le gate
                "title": "Décret A",
                "meta": "guide.pdf · pdf · p. 1",
            }
        ]

    monkeypatch.setattr("backend.routers.chat.retrieve_context", fake_retrieve_context)

    response = await client.post(
        "/api/chat",
        json={"question": "Une question documentée"},
        headers=auth_header(user_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text"].startswith("Réponse simulée")
    assert len(body["sources"]) == 1
    assert body["sources"][0]["title"] == "Décret A"
    assert body["sources"][0]["score"] == 0.82  # cosinus affiché, pas le RRF
    assert body["confidence"] == 0.82
    assert mock_rag["generate"] == 1


async def test_ask_question_below_similarity_threshold_refuses(client, user_token, monkeypatch, mock_rag):
    """Contexte trouvé mais faiblement pertinent (< rag_min_score) : SIOU refuse,
    sans appeler le LLM ni citer de source."""

    async def fake_retrieve_context(question, top_k, rrf_k):
        return [
            {
                "chunk_id": uuid.uuid4(),
                "document_id": uuid.uuid4(),
                "content": "Extrait faiblement lié.",
                "page_number": 1,
                "score": 0.010,
                "similarity": 0.12,  # cosinus < rag_min_score (0.35) : sous le seuil
                "title": "Décret B",
                "meta": "autre.pdf · pdf · p. 1",
            }
        ]

    monkeypatch.setattr("backend.routers.chat.retrieve_context", fake_retrieve_context)

    response = await client.post(
        "/api/chat",
        json={"question": "Une question hors sujet"},
        headers=auth_header(user_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == REFUSAL_TEXT
    assert body["sources"] == []  # pas de citation sous le seuil
    assert mock_rag["generate"] == 0  # confidence gate : pas d'appel LLM


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    """Découpe un corps SSE en liste (event, data-json)."""
    events = []
    for block in body.strip().split("\n\n"):
        if not block.strip():
            continue
        event, data = None, None
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data = json.loads(line[len("data:") :].strip())
        events.append((event, data))
    return events


async def test_ask_question_stream_streams_tokens_and_persists(client, user_token, monkeypatch, mock_rag):
    """Flux SSE : meta → tokens → done ; le message IA est bien persisté à la fin."""

    async def fake_retrieve_context(question, top_k, rrf_k):
        return [
            {
                "chunk_id": uuid.uuid4(),
                "document_id": uuid.uuid4(),
                "content": "Extrait pertinent du décret.",
                "page_number": 1,
                "score": 0.031,
                "similarity": 0.82,  # passe le gate
                "title": "Décret A",
                "meta": "guide.pdf · pdf · p. 1",
            }
        ]

    async def fake_stream_answer(question, context_chunks=None):
        for piece in ["Bonjour", " ", "le monde"]:
            yield piece

    monkeypatch.setattr("backend.routers.chat.retrieve_context", fake_retrieve_context)
    monkeypatch.setattr("backend.routers.chat.stream_answer", fake_stream_answer)

    response = await client.post(
        "/api/chat/stream",
        json={"question": "Une question documentée"},
        headers=auth_header(user_token),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(response.text)
    kinds = [event for event, _ in events]
    assert kinds[0] == "meta"
    assert "token" in kinds
    assert kinds[-1] == "done"

    # Reconstitution du texte streamé.
    text = "".join(data["delta"] for event, data in events if event == "token")
    assert text == "Bonjour le monde"

    # done : sources citées + confiance = similarité cosinus.
    done = next(data for event, data in events if event == "done")
    assert len(done["sources"]) == 1
    assert done["sources"][0]["title"] == "Décret A"
    assert done["confidence"] == 0.82

    # Persistance : la conversation contient bien la question + la réponse IA.
    meta = next(data for event, data in events if event == "meta")
    conversation_id = meta["conversation_id"]
    messages = (await client.get(
        f"/api/conversations/{conversation_id}/messages", headers=auth_header(user_token)
    )).json()
    assert [m["sender_type"] for m in messages] == ["human", "ia"]
    assert messages[1]["content"] == "Bonjour le monde"


async def test_ask_question_stream_refuses_below_threshold(client, user_token, monkeypatch, mock_rag):
    """Flux SSE : sous le seuil, le refus est streamé et aucun token LLM n'est produit."""

    async def fake_retrieve_context(question, top_k, rrf_k):
        return [
            {
                "chunk_id": uuid.uuid4(),
                "document_id": uuid.uuid4(),
                "content": "Extrait faiblement lié.",
                "page_number": 1,
                "score": 0.010,
                "similarity": 0.12,  # sous rag_min_score
                "title": "Décret B",
                "meta": "autre.pdf · pdf · p. 1",
            }
        ]

    stream_calls = {"n": 0}

    async def fake_stream_answer(question, context_chunks=None):
        stream_calls["n"] += 1
        yield "ne devrait pas être appelé"

    monkeypatch.setattr("backend.routers.chat.retrieve_context", fake_retrieve_context)
    monkeypatch.setattr("backend.routers.chat.stream_answer", fake_stream_answer)

    response = await client.post(
        "/api/chat/stream",
        json={"question": "Une question hors sujet"},
        headers=auth_header(user_token),
    )

    assert response.status_code == 200
    events = _parse_sse(response.text)
    text = "".join(data["delta"] for event, data in events if event == "token")
    assert text == REFUSAL_TEXT
    assert stream_calls["n"] == 0  # pas d'appel LLM sous le seuil
    done = next(data for event, data in events if event == "done")
    assert done["sources"] == []


async def test_ask_question_requires_auth(client):
    response = await client.post("/api/chat", json={"question": "Où se trouve l'ASIN ?"})

    assert response.status_code == 401


async def test_ask_question_creates_a_new_conversation(client, user_token):
    response = await client.post(
        "/api/chat",
        json={"question": "Où se trouve l'ASIN ?"},
        headers=auth_header(user_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text"]
    assert body["conversation_id"]

    # La conversation créée doit être visible et rattachée à l'utilisateur.
    list_response = await client.get("/api/conversations", headers=auth_header(user_token))
    conversation_ids = [c["id"] for c in list_response.json()]
    assert body["conversation_id"] in conversation_ids


async def test_ask_question_reuses_existing_conversation(client, user_token):
    create_response = await client.post(
        "/api/conversations", json={"title": "Discussion existante"}, headers=auth_header(user_token)
    )
    conversation_id = create_response.json()["id"]

    response = await client.post(
        "/api/chat",
        json={"question": "Et pour les pièces à fournir ?", "conversation_id": conversation_id},
        headers=auth_header(user_token),
    )

    assert response.status_code == 200
    assert response.json()["conversation_id"] == conversation_id


async def test_ask_question_with_unknown_conversation_id_is_not_found(client, user_token):
    response = await client.post(
        "/api/chat",
        json={
            "question": "Où se trouve l'ASIN ?",
            "conversation_id": "00000000-0000-0000-0000-000000000000",
        },
        headers=auth_header(user_token),
    )

    assert response.status_code == 404


async def test_ask_question_with_someone_elses_conversation_is_not_found(client, user_token, admin_token):
    create_response = await client.post(
        "/api/conversations", json={"title": "Conversation admin"}, headers=auth_header(admin_token)
    )
    conversation_id = create_response.json()["id"]

    response = await client.post(
        "/api/chat",
        json={"question": "Où se trouve l'ASIN ?", "conversation_id": conversation_id},
        headers=auth_header(user_token),
    )

    assert response.status_code == 404
