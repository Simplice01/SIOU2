"""Tests pour backend/routers/admin.py — gestion des utilisateurs,
documents et feedbacks, tous protégés par require_role("admin").

Ce routeur a remplacé l'ancien backend/routers/users.py : la gestion des
utilisateurs vit maintenant sous /api/admin/users au lieu de /api/users,
et la modération des documents/feedbacks a été ajoutée à côté. Il n'y a
plus d'endpoint pratique deactivate/activate ni de garde-fou anti-auto-
suppression ici (contrairement à l'ancien users.py) — un admin désactive
via PATCH {"is_active": false} et peut supprimer son propre compte.
"""

from backend.models.document_models import Document
from backend.models.feedback_model import Feedback
from backend.tests.conftest import auth_header


# --- Utilisateurs --------------------------------------------------------


async def test_list_users_as_admin(client, admin_token, admin_user, regular_user):
    response = await client.get("/api/admin/users", headers=auth_header(admin_token))

    assert response.status_code == 200
    usernames = {user["username"] for user in response.json()}
    assert {"admin_test", "user_test"} <= usernames


async def test_list_users_as_non_admin_is_forbidden(client, user_token):
    response = await client.get("/api/admin/users", headers=auth_header(user_token))

    assert response.status_code == 403


async def test_list_users_without_token_is_unauthorized(client):
    response = await client.get("/api/admin/users")

    assert response.status_code == 401


async def test_create_user_as_admin(client, admin_token):
    response = await client.post(
        "/api/admin/users",
        json={"username": "new_person", "password": "SomePass123"},
        headers=auth_header(admin_token),
    )

    assert response.status_code == 201
    assert response.json()["username"] == "new_person"


async def test_create_user_with_duplicate_username_is_conflict(client, admin_token, regular_user):
    response = await client.post(
        "/api/admin/users",
        json={"username": "user_test", "password": "SomePass123"},
        headers=auth_header(admin_token),
    )

    assert response.status_code == 409


async def test_create_user_as_non_admin_is_forbidden(client, user_token):
    response = await client.post(
        "/api/admin/users",
        json={"username": "someone", "password": "SomePass123"},
        headers=auth_header(user_token),
    )

    assert response.status_code == 403


async def test_get_user_by_id_as_admin(client, admin_token, regular_user):
    response = await client.get(f"/api/admin/users/{regular_user.id}", headers=auth_header(admin_token))

    assert response.status_code == 200
    assert response.json()["username"] == "user_test"


async def test_get_unknown_user_is_not_found(client, admin_token):
    response = await client.get(
        "/api/admin/users/00000000-0000-0000-0000-000000000000",
        headers=auth_header(admin_token),
    )

    assert response.status_code == 404


async def test_update_user_as_admin(client, admin_token, regular_user):
    response = await client.patch(
        f"/api/admin/users/{regular_user.id}",
        json={"last_name": "Doe", "is_active": False},
        headers=auth_header(admin_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["last_name"] == "Doe"
    assert body["is_active"] is False


async def test_update_user_as_non_admin_is_forbidden(client, user_token, admin_user):
    response = await client.patch(
        f"/api/admin/users/{admin_user.id}",
        json={"last_name": "Hacked"},
        headers=auth_header(user_token),
    )

    assert response.status_code == 403


async def test_delete_user_as_admin(client, admin_token, regular_user):
    response = await client.delete(f"/api/admin/users/{regular_user.id}", headers=auth_header(admin_token))

    assert response.status_code == 200

    get_response = await client.get(f"/api/admin/users/{regular_user.id}", headers=auth_header(admin_token))
    assert get_response.status_code == 404


async def test_delete_user_as_non_admin_is_forbidden(client, user_token, admin_user):
    response = await client.delete(f"/api/admin/users/{admin_user.id}", headers=auth_header(user_token))

    assert response.status_code == 403


# --- Documents -----------------------------------------------------------


async def test_list_documents_as_admin(client, admin_token, db_session):
    db_session.add(Document(title="Doc admin", file_path="/x.pdf", file_type="pdf"))
    await db_session.commit()

    response = await client.get("/api/admin/documents", headers=auth_header(admin_token))

    assert response.status_code == 200
    assert any(doc["title"] == "Doc admin" for doc in response.json())


async def test_list_documents_as_non_admin_is_forbidden(client, user_token):
    response = await client.get("/api/admin/documents", headers=auth_header(user_token))

    assert response.status_code == 403


async def test_create_document_as_admin(client, admin_token, admin_user):
    response = await client.post(
        "/api/admin/documents",
        json={"title": "Nouveau document", "file_path": "/data/doc.pdf", "file_type": "pdf"},
        headers=auth_header(admin_token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Nouveau document"
    # uploaded_by prend par défaut l'admin qui crée le document, si non fourni.
    assert body["uploaded_by"] == str(admin_user.id)


async def test_get_document_by_id_as_admin(client, admin_token, db_session):
    document = Document(title="Doc a lire", file_path="/x.pdf", file_type="pdf")
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    response = await client.get(f"/api/admin/documents/{document.id}", headers=auth_header(admin_token))

    assert response.status_code == 200
    assert response.json()["title"] == "Doc a lire"


async def test_get_unknown_document_is_not_found(client, admin_token):
    response = await client.get(
        "/api/admin/documents/00000000-0000-0000-0000-000000000000",
        headers=auth_header(admin_token),
    )

    assert response.status_code == 404


async def test_update_document_as_admin(client, admin_token, db_session):
    document = Document(title="Ancien titre", file_path="/x.pdf", file_type="pdf")
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    response = await client.patch(
        f"/api/admin/documents/{document.id}",
        json={"title": "Nouveau titre", "status": "active"},
        headers=auth_header(admin_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Nouveau titre"
    assert body["status"] == "active"


async def test_delete_document_as_admin(client, admin_token, db_session):
    document = Document(title="A supprimer", file_path="/x.pdf", file_type="pdf")
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    response = await client.delete(f"/api/admin/documents/{document.id}", headers=auth_header(admin_token))

    assert response.status_code == 200

    get_response = await client.get(
        f"/api/admin/documents/{document.id}", headers=auth_header(admin_token)
    )
    assert get_response.status_code == 404


# --- Feedbacks -------------------------------------------------------------


async def test_list_feedbacks_as_admin(client, admin_token, db_session):
    db_session.add(Feedback(rating=4, comment="Pas mal"))
    await db_session.commit()

    response = await client.get("/api/admin/feedbacks", headers=auth_header(admin_token))

    assert response.status_code == 200
    assert any(f["comment"] == "Pas mal" for f in response.json())


async def test_list_feedbacks_as_non_admin_is_forbidden(client, user_token):
    response = await client.get("/api/admin/feedbacks", headers=auth_header(user_token))

    assert response.status_code == 403


async def test_get_feedback_by_id_as_admin(client, admin_token, db_session):
    feedback = Feedback(rating=5, comment="Top")
    db_session.add(feedback)
    await db_session.commit()
    await db_session.refresh(feedback)

    response = await client.get(f"/api/admin/feedbacks/{feedback.id}", headers=auth_header(admin_token))

    assert response.status_code == 200
    assert response.json()["comment"] == "Top"


async def test_get_unknown_feedback_is_not_found(client, admin_token):
    response = await client.get(
        "/api/admin/feedbacks/00000000-0000-0000-0000-000000000000",
        headers=auth_header(admin_token),
    )

    assert response.status_code == 404


async def test_delete_feedback_as_admin(client, admin_token, db_session):
    feedback = Feedback(rating=1, comment="A supprimer")
    db_session.add(feedback)
    await db_session.commit()
    await db_session.refresh(feedback)

    response = await client.delete(f"/api/admin/feedbacks/{feedback.id}", headers=auth_header(admin_token))

    assert response.status_code == 200

    get_response = await client.get(
        f"/api/admin/feedbacks/{feedback.id}", headers=auth_header(admin_token)
    )
    assert get_response.status_code == 404
