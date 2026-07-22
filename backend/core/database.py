from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from backend.core.config import sqlalchemy_database_url


Base = declarative_base()

# pool_pre_ping : valide (et reconnecte au besoin) une connexion avant chaque
# usage — indispensable avec Neon (Postgres serverless) qui ferme les connexions
# inactives, ce qui provoquait sinon des 500 « connection is closed » après une
# période d'inactivité. pool_recycle recycle proactivement les connexions âgées.
engine = create_async_engine(
    sqlalchemy_database_url(),
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
