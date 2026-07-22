"""Tests pour backend/routers/documents.py (réel, branché sur la base de
données). Lecture : tout utilisateur authentifié. Écriture (upload/update/
delete/validate/reject) : réservée aux rôles admin/responsable_ministere/
point_focal (WRITE_ROLES)."""

from backend.tests.conftest import auth_header

DOCUMENT_PAYLOAD = {
    "title": "Guide des démarches numériques",
    "file_path": "/data/docs/guide.pdf",
    "file_type": "pdf",
}


async def _upload(client, token, **overrides):
    payload = {**DOCUMENT_PAYLOAD, **overrides}
    return await client.post("/api/documents", json=payload, headers=auth_header(token))


async def test_list_documents_requires_auth(client):
    response = await client.get("/api/documents")

    assert response.status_code == 401


async def test_list_documents_authenticated(client, user_token):
    response = await client.get("/api/documents", headers=auth_header(user_token))

    assert response.status_code == 200
    assert response.json() == []


async def test_upload_document_as_admin(client, admin_token):
    response = await _upload(client, admin_token)

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == DOCUMENT_PAYLOAD["title"]
    assert body["status"] == "processing"


async def test_upload_document_as_regular_user_is_forbidden(client, user_token):
    response = await _upload(client, user_token)

    assert response.status_code == 403


async def test_get_document_by_id(client, admin_token, user_token):
    create_response = await _upload(client, admin_token)
    document_id = create_response.json()["id"]

    response = await client.get(f"/api/documents/{document_id}", headers=auth_header(user_token))

    assert response.status_code == 200
    assert response.json()["id"] == document_id


async def test_get_unknown_document_is_not_found(client, user_token):
    response = await client.get(
        "/api/documents/00000000-0000-0000-0000-000000000000",
        headers=auth_header(user_token),
    )

    assert response.status_code == 404


async def test_update_document_as_admin(client, admin_token):
    create_response = await _upload(client, admin_token)
    document_id = create_response.json()["id"]

    response = await client.put(
        f"/api/documents/{document_id}",
        json={"status": "active"},
        headers=auth_header(admin_token),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "active"


async def test_update_document_as_regular_user_is_forbidden(client, admin_token, user_token):
    create_response = await _upload(client, admin_token)
    document_id = create_response.json()["id"]

    response = await client.put(
        f"/api/documents/{document_id}",
        json={"status": "active"},
        headers=auth_header(user_token),
    )

    assert response.status_code == 403


async def test_delete_document_as_admin(client, admin_token):
    create_response = await _upload(client, admin_token)
    document_id = create_response.json()["id"]

    response = await client.delete(f"/api/documents/{document_id}", headers=auth_header(admin_token))
    assert response.status_code == 200

    get_response = await client.get(f"/api/documents/{document_id}", headers=auth_header(admin_token))
    assert get_response.status_code == 404


async def test_ingest_document_schedules_background_task(client, admin_token, monkeypatch):
    """POST /ingest crée le document en `processing` et planifie l'indexation.

    Le vrai pipeline (torch/embeddings) est mocké : on vérifie le contrat de la
    route (202, statut, tâche de fond planifiée avec les bons arguments)."""
    calls = []

    async def fake_ingest(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("backend.routers.documents.run_document_ingestion", fake_ingest)

    response = await client.post(
        "/api/documents/ingest",
        json={"title": "Décret 2024", "content": "# Titre\nArticle 1 : contenu.", "file_type": "md"},
        headers=auth_header(admin_token),
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "processing"
    assert body["title"] == "Décret 2024"

    # La tâche de fond s'exécute après l'envoi de la réponse (ASGITransport).
    assert len(calls) == 1
    assert str(calls[0]["document_id"]) == body["id"]
    assert calls[0]["document_text"].startswith("# Titre")


async def test_ingest_document_as_regular_user_is_forbidden(client, user_token, monkeypatch):
    async def fake_ingest(**kwargs):
        return None

    monkeypatch.setattr("backend.routers.documents.run_document_ingestion", fake_ingest)

    response = await client.post(
        "/api/documents/ingest",
        json={"title": "X", "content": "y"},
        headers=auth_header(user_token),
    )

    assert response.status_code == 403


async def test_validate_document(client, admin_token):
    create_response = await _upload(client, admin_token)
    document_id = create_response.json()["id"]

    response = await client.post(f"/api/documents/{document_id}/validate", headers=auth_header(admin_token))

    assert response.status_code == 200
    assert response.json()["status"] == "active"


async def test_reject_document(client, admin_token):
    create_response = await _upload(client, admin_token)
    document_id = create_response.json()["id"]

    response = await client.post(f"/api/documents/{document_id}/reject", headers=auth_header(admin_token))

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
