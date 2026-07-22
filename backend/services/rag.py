"""Service de récupération documentaire (RAG) pour le pipeline de chat.

Isole l'appel à la recherche hybride pgvector et l'enrichit avec les titres de
documents pour construire des citations. Conçu pour être *robuste par défaut* :

- Le modèle d'embeddings (torch) est importé **paresseusement** : l'application
  démarre et les autres routes fonctionnent même si le poids/torch est absent.
- La récupération se fait dans une **session de lecture séparée**, afin qu'un
  échec (pgvector indisponible, base vide, torch absent) ne pollue jamais la
  transaction d'écriture du chat. En cas d'erreur, on renvoie `[]` (dégradation
  gracieuse : le LLM répondra sans contexte plutôt que de faire échouer la requête).
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.core.database import SessionLocal
from backend.models.document_models import Document

logger = logging.getLogger(__name__)


async def retrieve_context(question: str, top_k: int, rrf_k: int) -> list[dict[str, Any]]:
    """Renvoie les meilleurs chunks pour `question`, enrichis du titre/méta document.

    Ne lève jamais : toute défaillance est journalisée et donne une liste vide.
    """
    try:
        # Imports paresseux : ne chargent torch/HF que si la récupération est réellement tentée.
        from backend.AI.RAG.semantic_search import retrieve_hybrid_chunks

        async with SessionLocal() as db:
            chunks = await retrieve_hybrid_chunks(
                db_session=db,
                query_text=question,
                embedding_model=None,
                top_k=top_k,
                rrf_k=rrf_k,
            )
            if not chunks:
                return []

            # Enrichissement : titre + méta du document parent (une seule requête).
            document_ids = {c["document_id"] for c in chunks}
            rows = await db.execute(
                select(Document).options(selectinload(Document.source_file)).where(
                    Document.id.in_(document_ids)
                )
            )
            docs = {document.id: document for document in rows.scalars().all()}

        enriched: list[dict[str, Any]] = []
        for chunk in chunks:
            doc = docs.get(chunk["document_id"])
            enriched.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "document_id": chunk["document_id"],
                    "content": chunk["content"],
                    "page_number": chunk["page_number"],
                    "score": chunk["score"],  # RRF (classement)
                    "similarity": chunk.get("similarity"),  # cosinus [0,1] (gate/affichage)
                    "title": doc.title if doc else "Document",
                    "meta": _build_meta(doc, chunk["page_number"]),
                }
            )
        return enriched

    except Exception:
        logger.warning("Récupération RAG indisponible, réponse générée sans contexte", exc_info=True)
        return []


def _build_meta(doc: Any, page_number: int | None) -> str:
    parts: list[str] = []
    if doc is not None and doc.file_path:
        parts.append(str(doc.file_path))
    if doc is not None and doc.file_type:
        parts.append(str(doc.file_type))
    if page_number:
        parts.append(f"p. {page_number}")
    return " · ".join(parts)
