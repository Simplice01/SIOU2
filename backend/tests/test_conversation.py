"""Tests pour backend/routers/conversation.py (réel, branché sur la base
de données — chaque utilisateur ne voit/modifie que ses propres
conversations, sauf l'admin qui a accès à tout)."""

from backend.tests.conftest import auth_header


async def test_get_conversations_requires_auth(client):
    response = await client.get("/api/conversations")

    assert response.status_code == 401


async def test_get_conversations_returns_only_own(client, user_token, regular_user, admin_user, db_session):
    from backend.models.conversation_models import Conversation

    db_session.add(Conversation(user_id=regular_user.id, title="Ma conversation"))
    db_session.add(Conversation(user_id=admin_user.id, title="Conversation admin"))
    await db_session.commit()

    response = await client.get("/api/conversations", headers=auth_header(user_token))

    assert response.status_code == 200
    titles = [c["title"] for c in response.json()]
    assert titles == ["Ma conversation"]


async def test_create_conversation(client, user_token, regular_user):
    response = await client.post(
        "/api/conversations",
        json={"title": "Nouvelle recherche"},
        headers=auth_header(user_token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Nouvelle recherche"
    assert body["user_id"] == str(regular_user.id)


async def test_get_conversation_by_id_owned(client, user_token):
    create_response = await client.post(
        "/api/conversations", json={"title": "Test"}, headers=auth_header(user_token)
    )
    conversation_id = create_response.json()["id"]

    response = await client.get(f"/api/conversations/{conversation_id}", headers=auth_header(user_token))

    assert response.status_code == 200
    assert response.json()["id"] == conversation_id


async def test_get_conversation_not_owned_is_not_found(client, user_token, admin_token):
    create_response = await client.post(
        "/api/conversations", json={"title": "Conversation admin"}, headers=auth_header(admin_token)
    )
    conversation_id = create_response.json()["id"]

    response = await client.get(f"/api/conversations/{conversation_id}", headers=auth_header(user_token))

    assert response.status_code == 404


async def test_get_conversation_not_owned_but_admin_can_access(client, user_token, admin_token):
    create_response = await client.post(
        "/api/conversations", json={"title": "Conversation utilisateur"}, headers=auth_header(user_token)
    )
    conversation_id = create_response.json()["id"]

    response = await client.get(f"/api/conversations/{conversation_id}", headers=auth_header(admin_token))

    assert response.status_code == 200


async def test_get_unknown_conversation_is_not_found(client, user_token):
    response = await client.get(
        "/api/conversations/00000000-0000-0000-0000-000000000000",
        headers=auth_header(user_token),
    )

    assert response.status_code == 404


async def test_get_conversation_messages(client, user_token, regular_user, db_session):
    from backend.models.conversation_models import Conversation, Message

    conversation = Conversation(user_id=regular_user.id, title="Fil")
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)
    db_session.add(Message(conversation_id=conversation.id, sender_type="human", content="Bonjour"))
    db_session.add(
        Message(conversation_id=conversation.id, sender_type="ia", content="Réponse", model_used="test")
    )
    await db_session.commit()

    response = await client.get(
        f"/api/conversations/{conversation.id}/messages", headers=auth_header(user_token)
    )

    assert response.status_code == 200
    body = response.json()
    assert [m["sender_type"] for m in body] == ["human", "ia"]
    assert body[0]["content"] == "Bonjour"
    assert body[1]["model_used"] == "test"


async def test_get_conversation_messages_not_owned_is_not_found(client, user_token, admin_token):
    create_response = await client.post(
        "/api/conversations", json={"title": "Conversation admin"}, headers=auth_header(admin_token)
    )
    conversation_id = create_response.json()["id"]

    response = await client.get(
        f"/api/conversations/{conversation_id}/messages", headers=auth_header(user_token)
    )

    assert response.status_code == 404


async def test_update_conversation_title(client, user_token):
    create_response = await client.post(
        "/api/conversations", json={"title": "Avant"}, headers=auth_header(user_token)
    )
    conversation_id = create_response.json()["id"]

    response = await client.patch(
        f"/api/conversations/{conversation_id}",
        json={"title": "Après"},
        headers=auth_header(user_token),
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Après"


async def test_update_conversation_not_owned_is_not_found(client, user_token, admin_token):
    create_response = await client.post(
        "/api/conversations", json={"title": "Conversation admin"}, headers=auth_header(admin_token)
    )
    conversation_id = create_response.json()["id"]

    response = await client.patch(
        f"/api/conversations/{conversation_id}",
        json={"title": "Piratage"},
        headers=auth_header(user_token),
    )

    assert response.status_code == 404


async def test_delete_conversation(client, user_token):
    create_response = await client.post(
        "/api/conversations", json={"title": "À supprimer"}, headers=auth_header(user_token)
    )
    conversation_id = create_response.json()["id"]

    response = await client.delete(f"/api/conversations/{conversation_id}", headers=auth_header(user_token))
    assert response.status_code == 200

    get_response = await client.get(f"/api/conversations/{conversation_id}", headers=auth_header(user_token))
    assert get_response.status_code == 404


async def test_delete_conversation_not_owned_is_not_found(client, user_token, admin_token):
    create_response = await client.post(
        "/api/conversations", json={"title": "Conversation admin"}, headers=auth_header(admin_token)
    )
    conversation_id = create_response.json()["id"]

    response = await client.delete(f"/api/conversations/{conversation_id}", headers=auth_header(user_token))

    assert response.status_code == 404
