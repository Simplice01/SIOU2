import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

import backend.models  # noqa: F401
from backend.core.config import settings
from backend.core.database import Base, engine
from backend.core.schema_upgrades import run_startup_upgrades
from backend.routers.admin import router as admin_router
from backend.routers.auth import router as auth_router
from backend.routers.chat import router as chat_router
from backend.routers.conversation import router as conversation_router
from backend.routers.documents import router as documents_router
from backend.routers.feedbacks import router as feedbacks_router
from backend.routers.notifications import router as notifications_router
from backend.routers.stats import router as stats_router


logger = logging.getLogger(__name__)


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


async def _warm_up_embeddings() -> None:
    # SIOU2 now reads the existing PostgreSQL knowledge base with full-text
    # retrieval. No heavy local embedding model is loaded at startup.
    logger.info("Embedding warmup skipped: PostgreSQL retrieval is active.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await run_startup_upgrades(conn)
    asyncio.create_task(_warm_up_embeddings())
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
try:
    from backend.routers.audio import router as audio_router

    app.include_router(audio_router)
except ModuleNotFoundError as exc:
    if exc.name != "faster_whisper":
        raise
    logger.warning("Audio router disabled: faster-whisper is not installed.")

app.include_router(admin_router)
app.include_router(documents_router)
app.include_router(conversation_router)
app.include_router(feedbacks_router)
app.include_router(notifications_router)
app.include_router(chat_router)
app.include_router(stats_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.app_name}


_frontend_dir = Path(__file__).parent / "frontend"
if _frontend_dir.is_dir():
    app.mount("/", NoCacheStaticFiles(directory=_frontend_dir, html=True), name="frontend")


def main():
    print(f"{settings.app_name} is configured. Launch it with uvicorn main:app --reload")


if __name__ == "__main__":
    main()
