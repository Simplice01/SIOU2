"""Fixtures pytest partagées par la suite de tests backend.

Les tests tournent contre la vraie application FastAPI (`main.app`), pas
une réimplémentation — un test qui passe signifie donc que la véritable
API se comporte comme attendu. La dépendance de base de données
(`get_db`) est remplacée à chaque test par une base SQLite isolée en
mémoire, pour que les tests ne touchent jamais la vraie base Postgres et
ne se pollue pas entre eux.
"""

import os

# config.py exige ces variables dès l'import, avant tout module `backend.*`
# — on fixe des valeurs de test sûres si l'environnement ne les fournit pas
# déjà (ex. un vrai fichier .env).
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-only")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.core.database import Base, get_db
from backend.core.security import hash_password
from backend.models.user_model import User
from main import app


@pytest_asyncio.fixture
async def db_session():
    """Une base SQLite en mémoire toute neuve, isolée pour chaque test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    """Client HTTP branché sur la vraie application, avec get_db pointé vers la base de test."""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def make_user(db_session):
    """Fixture-usine : insère un utilisateur directement dans la base de test."""

    async def _make_user(username: str, password: str, role: str = "user", is_active: bool = True) -> User:
        user = User(
            username=username,
            password_hash=hash_password(password),
            role=role,
            is_active=is_active,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    return _make_user


@pytest_asyncio.fixture
async def admin_user(make_user):
    return await make_user("admin_test", "AdminPass123", role="admin")


@pytest_asyncio.fixture
async def regular_user(make_user):
    return await make_user("user_test", "UserPass123", role="user")


async def _login(client, username, password) -> str:
    response = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def admin_token(client, admin_user):
    return await _login(client, "admin_test", "AdminPass123")


@pytest_asyncio.fixture
async def user_token(client, regular_user):
    return await _login(client, "user_test", "UserPass123")


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
