"""Wrapper d'ingestion documentaire pour l'exécution en tâche de fond.

Le pipeline lourd (`text_to_chunks`, qui charge torch/HF) est importé
**paresseusement** ici : le routeur `documents` peut donc importer ce module
sans tirer torch au démarrage de l'API. La fonction est conçue pour être
planifiée via `BackgroundTasks` — elle ne renvoie rien et ne lève jamais : tout
échec est journalisé et le document est basculé en statut `failed`.
"""

import logging
import uuid

from backend.core.database import SessionLocal
from backend.models.document_models import Document

logger = logging.getLogger(__name__)


async def _mark_document_failed(document_id: uuid.UUID) -> None:
    """Bascule le document en `failed` (best-effort, dans sa propre session)."""
    try:
        async with SessionLocal() as db:
            document = await db.get(Document, document_id)
            if document is not None:
                document.status = Document.STATUS_FAILED
                await db.commit()
    except Exception:
        logger.exception("Impossible de marquer le document %s en échec", document_id)


async def run_document_ingestion(
    document_id: uuid.UUID,
    document_text: str,
    document_title: str,
    file_type: str = "md",
    uploaded_by: uuid.UUID | None = None,
    chunk_size: int = 400,
    chunk_overlap: int = 40,
) -> None:
    """Découpe, embarque et indexe le document (déjà créé) en arrière-plan."""
    try:
        # Import paresseux : ne charge torch/HF que lors d'une ingestion réelle.
        from backend.AI.RAG.text_to_chunks import process_document_to_chunks
    except Exception:
        logger.exception(
            "Ingestion indisponible (dépendances embeddings absentes) — document %s", document_id
        )
        await _mark_document_failed(document_id)
        return

    result = await process_document_to_chunks(
        document_text=document_text,
        document_title=document_title,
        file_type=file_type,
        uploaded_by=uploaded_by,
        document_id=document_id,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    if result.get("success"):
        logger.info("Ingestion réussie — document %s : %s chunks", document_id, result.get("chunk_count"))
    else:
        logger.warning("Ingestion échouée — document %s : %s", document_id, result.get("error"))
