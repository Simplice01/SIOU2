"""Tests pour backend/routers/stats.py — statistiques agrégées du tableau
de bord. L'endpoint est accessible à tout utilisateur authentifié (données
agrégées, non nominatives) mais refuse les requêtes sans jeton.

Chaque test part d'une base SQLite en mémoire vierge (fixture `db_session`),
les compteurs sont donc isolés d'un test à l'autre.
"""

from backend.tests.conftest import auth_header


async def test_statistics_without_token_is_unauthorized(client):
    response = await client.get("/api/stats")
    assert response.status_code == 401


async def test_statistics_shape_and_zeros_on_empty_db(client, user_token):
    response = await client.get("/api/stats", headers=auth_header(user_token))

    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"conversations", "documents"}
    assert data["conversations"]["current_month"] == 0
    assert data["conversations"]["previous_month"] == 0
    assert data["conversations"]["change_percent"] == 0.0
    assert data["documents"] == {"total": 0, "recent": 0, "by_status": []}


async def test_statistics_counts_documents_by_status(client, admin_token):
    headers = auth_header(admin_token)
    for index, status in enumerate(("active", "active", "processing")):
        response = await client.post(
            "/api/documents",
            json={"title": f"D{index}", "file_path": f"d{index}.pdf", "file_type": "pdf", "status": status},
            headers=headers,
        )
        assert response.status_code == 201

    data = (await client.get("/api/stats", headers=headers)).json()

    assert data["documents"]["total"] == 3
    assert data["documents"]["recent"] == 3
    by_status = {row["status"]: row for row in data["documents"]["by_status"]}
    assert by_status["active"]["count"] == 2
    assert by_status["active"]["label"] == "Actifs"
    assert by_status["active"]["percentage"] == 67  # round(2 / 3 * 100)
    assert by_status["processing"]["count"] == 1


async def test_statistics_counts_conversations_this_month(client, admin_token):
    headers = auth_header(admin_token)
    response = await client.post("/api/conversations", json={"title": "C1"}, headers=headers)
    assert response.status_code == 201

    data = (await client.get("/api/stats", headers=headers)).json()

    assert data["conversations"]["current_month"] >= 1
    assert data["conversations"]["previous_month"] == 0
    assert data["conversations"]["change_percent"] == 100.0
