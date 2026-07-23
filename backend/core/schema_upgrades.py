"""Micro-migrations idempotentes appliquées au démarrage (PostgreSQL uniquement).

Le schéma est créé via `Base.metadata.create_all`, qui crée les tables
manquantes mais **n'altère jamais** une table déjà existante et n'émet pas les
index d'expression full-text (GIN) ni vectoriels (pgvector). Ces DDL, propres à
Postgres et non portables via `create_all`, sont appliquées ici de façon
idempotente (`IF NOT EXISTS`).

Solution volontairement légère adaptée au stade actuel du projet. À remplacer
par Alembic dès que le schéma se stabilise et doit être versionné/rollbackable.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

# Ordre important : extension d'abord, puis colonne, puis index.
_POSTGRES_UPGRADES: tuple[str, ...] = (
    "CREATE EXTENSION IF NOT EXISTS vector",
    "CREATE EXTENSION IF NOT EXISTS unaccent",
    # Colonne ajoutée aux bases déjà déployées (create_all ignore les tables existantes).
    "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS chunk_metadata JSONB",
    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS model_used TEXT",
    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS prompt_tokens INTEGER",
    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS completion_tokens INTEGER",
    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS latency_ms INTEGER",
    "ALTER TABLE feedback_reports ADD COLUMN IF NOT EXISTS metadata JSONB",
    # Recherche dense (ANN) : opérateur cosine, cohérent avec le `<=>` de la requête hybride.
    "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw "
    "ON document_chunks USING hnsw (embedding vector_cosine_ops)",
    # Recherche sparse (full-text FR) : index d'expression aligné sur `to_tsvector('french', content)`.
    "CREATE INDEX IF NOT EXISTS ix_document_chunks_content_fts "
    "ON document_chunks USING gin (to_tsvector('french', content))",
)


async def run_startup_upgrades(conn: AsyncConnection) -> None:
    """Applique les micro-migrations Postgres.

    No-op sur tout autre dialecte (ex. le SQLite en mémoire des tests), afin que
    la suite de tests reste portable et n'exécute pas de DDL Postgres-spécifique.
    """
    if conn.dialect.name != "postgresql":
        return
    for statement in _POSTGRES_UPGRADES:
        await conn.execute(text(statement))
