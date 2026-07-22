"""Tests pour backend/routers/feedbacks.py (réel, branché sur la base de
données — tout utilisateur authentifié peut lire/écrire)."""

from backend.tests.conftest import auth_header


async def _create_feedback(client, token, **overrides):
    payload = {"rating": 4, "comment": "Plutôt utile", **overrides}
    return await client.post("/api/feedbacks", json=payload, headers=auth_header(token))


async def test_list_feedbacks_requires_auth(client):
    response = await client.get("/api/feedbacks")

    assert response.status_code == 401


async def test_create_feedback(client, user_token, regular_user):
    response = await _create_feedback(client, user_token)

    assert response.status_code == 201
    body = response.json()
    assert body["rating"] == 4
    assert body["comment"] == "Plutôt utile"
    assert body["user_id"] == str(regular_user.id)


async def test_list_feedbacks_includes_created_entry(client, user_token):
    create_response = await _create_feedback(client, user_token)
    feedback_id = create_response.json()["id"]

    response = await client.get("/api/feedbacks", headers=auth_header(user_token))

    assert response.status_code == 200
    assert feedback_id in [f["id"] for f in response.json()]


async def test_get_feedback_by_id(client, user_token):
    create_response = await _create_feedback(client, user_token)
    feedback_id = create_response.json()["id"]

    response = await client.get(f"/api/feedbacks/{feedback_id}", headers=auth_header(user_token))

    assert response.status_code == 200
    assert response.json()["rating"] == 4


async def test_get_unknown_feedback_is_not_found(client, user_token):
    response = await client.get(
        "/api/feedbacks/00000000-0000-0000-0000-000000000000",
        headers=auth_header(user_token),
    )

    assert response.status_code == 404


async def test_update_feedback(client, user_token):
    create_response = await _create_feedback(client, user_token, rating=2, comment="Bof")
    feedback_id = create_response.json()["id"]

    response = await client.patch(
        f"/api/feedbacks/{feedback_id}",
        json={"rating": 5, "comment": "Finalement très bien"},
        headers=auth_header(user_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rating"] == 5
    assert body["comment"] == "Finalement très bien"


async def test_update_unknown_feedback_is_not_found(client, user_token):
    response = await client.patch(
        "/api/feedbacks/00000000-0000-0000-0000-000000000000",
        json={"rating": 3},
        headers=auth_header(user_token),
    )

    assert response.status_code == 404


async def test_delete_feedback(client, user_token):
    create_response = await _create_feedback(client, user_token, rating=1, comment="à supprimer")
    feedback_id = create_response.json()["id"]

    response = await client.delete(f"/api/feedbacks/{feedback_id}", headers=auth_header(user_token))
    assert response.status_code == 200

    get_response = await client.get(f"/api/feedbacks/{feedback_id}", headers=auth_header(user_token))
    assert get_response.status_code == 404


async def test_delete_unknown_feedback_is_not_found(client, user_token):
    response = await client.delete(
        "/api/feedbacks/00000000-0000-0000-0000-000000000000",
        headers=auth_header(user_token),
    )

    assert response.status_code == 404
