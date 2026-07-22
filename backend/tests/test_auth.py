"""Tests pour backend/routers/auth.py (login, refresh, logout, me)."""

from backend.tests.conftest import auth_header


async def test_login_with_valid_credentials_returns_tokens_and_user(client, regular_user):
    response = await client.post(
        "/api/auth/login",
        json={"username": "user_test", "password": "UserPass123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["username"] == "user_test"
    assert body["user"]["role"] == "user"


async def test_login_with_wrong_password_is_rejected(client, regular_user):
    response = await client.post(
        "/api/auth/login",
        json={"username": "user_test", "password": "wrong-password"},
    )

    assert response.status_code == 401


async def test_login_with_unknown_username_is_rejected(client):
    response = await client.post(
        "/api/auth/login",
        json={"username": "does-not-exist", "password": "whatever"},
    )

    assert response.status_code == 401


async def test_login_with_inactive_account_is_rejected(client, make_user):
    await make_user("inactive_user", "Password123", is_active=False)

    response = await client.post(
        "/api/auth/login",
        json={"username": "inactive_user", "password": "Password123"},
    )

    assert response.status_code == 401


async def test_me_with_valid_token_returns_current_user(client, user_token):
    response = await client.get("/api/auth/me", headers=auth_header(user_token))

    assert response.status_code == 200
    assert response.json()["username"] == "user_test"


async def test_me_without_token_is_rejected(client):
    response = await client.get("/api/auth/me")

    assert response.status_code == 401


async def test_me_with_garbage_token_is_rejected(client):
    response = await client.get("/api/auth/me", headers=auth_header("not-a-real-token"))

    assert response.status_code == 401


async def test_refresh_with_valid_refresh_token_issues_new_access_token(client, regular_user):
    login_response = await client.post(
        "/api/auth/login",
        json={"username": "user_test", "password": "UserPass123"},
    )
    refresh_token = login_response.json()["refresh_token"]

    response = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]

    # Le nouveau jeton d'accès doit lui-même être utilisable sur une route protégée.
    me_response = await client.get("/api/auth/me", headers=auth_header(body["access_token"]))
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "user_test"


async def test_refresh_rejects_an_access_token_used_as_refresh_token(client, user_token):
    """Un jeton d'accès ne doit jamais être utilisable à la place d'un jeton de rafraîchissement."""
    response = await client.post("/api/auth/refresh", json={"refresh_token": user_token})

    assert response.status_code == 401


async def test_refresh_with_garbage_token_is_rejected(client):
    response = await client.post("/api/auth/refresh", json={"refresh_token": "not-a-real-token"})

    assert response.status_code == 401


async def test_logout_always_succeeds(client):
    """Logout est un no-op sans état (pas de table de session/révocation côté serveur)."""
    response = await client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"detail": "Déconnexion effectuée"}
