from backend.tests.conftest import auth_header


async def test_admin_can_create_and_list_notifications(client, admin_token):
    response = await client.post(
        "/api/admin/notifications",
        json={
            "title": "Information importante",
            "message": "Une nouvelle consigne est disponible.",
            "target_role": "user",
            "notification_type": "info",
            "priority": "normal",
        },
        headers=auth_header(admin_token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Information importante"
    assert body["target_role"] == "user"
    assert body["is_read"] is False

    list_response = await client.get("/api/admin/notifications", headers=auth_header(admin_token))
    assert list_response.status_code == 200
    assert [item["title"] for item in list_response.json()] == ["Information importante"]


async def test_regular_user_cannot_manage_notifications(client, user_token):
    response = await client.post(
        "/api/admin/notifications",
        json={"title": "X", "message": "Y"},
        headers=auth_header(user_token),
    )

    assert response.status_code == 403


async def test_user_only_receives_notifications_for_own_role(client, admin_token, user_token):
    await client.post(
        "/api/admin/notifications",
        json={"title": "Pour tous", "message": "Visible par tous.", "target_role": "all"},
        headers=auth_header(admin_token),
    )
    await client.post(
        "/api/admin/notifications",
        json={"title": "Pour usagers", "message": "Visible par les usagers.", "target_role": "user"},
        headers=auth_header(admin_token),
    )
    await client.post(
        "/api/admin/notifications",
        json={"title": "Pour admins", "message": "Visible par les admins.", "target_role": "admin"},
        headers=auth_header(admin_token),
    )

    response = await client.get("/api/notifications", headers=auth_header(user_token))

    assert response.status_code == 200
    titles = {item["title"] for item in response.json()}
    assert titles == {"Pour tous", "Pour usagers"}


async def test_user_can_mark_notifications_as_read(client, admin_token, user_token):
    create_response = await client.post(
        "/api/admin/notifications",
        json={"title": "A lire", "message": "Contenu.", "target_role": "user"},
        headers=auth_header(admin_token),
    )
    notification_id = create_response.json()["id"]

    count_response = await client.get("/api/notifications/unread-count", headers=auth_header(user_token))
    assert count_response.status_code == 200
    assert count_response.json()["unread_count"] == 1

    read_response = await client.post(f"/api/notifications/{notification_id}/read", headers=auth_header(user_token))
    assert read_response.status_code == 200
    assert read_response.json()["is_read"] is True

    count_response = await client.get("/api/notifications/unread-count", headers=auth_header(user_token))
    assert count_response.json()["unread_count"] == 0


async def test_mark_all_notifications_as_read(client, admin_token, user_token):
    for index in range(2):
        await client.post(
            "/api/admin/notifications",
            json={"title": f"Notification {index}", "message": "Contenu.", "target_role": "user"},
            headers=auth_header(admin_token),
        )

    response = await client.post("/api/notifications/read-all", headers=auth_header(user_token))

    assert response.status_code == 200
    assert response.json()["unread_count"] == 0
