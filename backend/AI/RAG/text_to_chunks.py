"""Pipeline d'ingestion documentaire : texte -> chunks -> embeddings -> base.

Ce module est prévu pour être exécuté comme *tâche de fond* (BackgroundTask
ou worker), et non dans le cycle requête/réponse : le calcul d'embeddings est
lourd (CPU/torch). Il reste néanmoins entièrement `async`-safe — les appels
bloquants (embeddings, découpage, lecture disque) sont déportés dans un thread
via `asyncio.to_thread` pour ne jamais figer la boucle asyncio.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_huggingface import HuggingFaceEmbeddings
from sqlalchemy import delete, select

from backend.AI.RAG.semantic_search import split_administrative_document
from backend.core.database import SessionLocal
from backend.models.document_models import Document, DocumentChunk

logger = logging.getLogger(__name__)

# Modèle local (~440 Mo) résolu relativement à ce fichier — indépendant du
# répertoire de lancement (uvicorn, vercel, tests). Fallback sur le hub HF si
# le poids local n'est pas présent. Le modèle produit des vecteurs de dim 384,
# ce qui correspond à `DocumentChunk.embedding = Vector(384)`.
_PRETRAINED_DIR = Path(__file__).resolve().parents[2] / "pretrained" / "paraphrase-local"
_FALLBACK_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_embeddings_model: HuggingFaceEmbeddings | None = None
_embeddings_lock = threading.Lock()


def get_embeddings() -> HuggingFaceEmbeddings:
    """Charge (paresseusement, une seule fois) le modèle d'embeddings.

    Chargé au premier usage plutôt qu'à l'import : les ~440 Mo ne pèsent sur la
    mémoire que si l'ingestion est réellement sollicitée, jamais à l'import.
    Thread-safe (double-checked locking) : `get_embeddings` est appelé depuis
    `asyncio.to_thread`, donc potentiellement en concurrence — sans verrou, deux
    appels simultanés chargeraient le modèle deux fois.
    """
    global _embeddings_model
    if _embeddings_model is None:
        with _embeddings_lock:
            if _embeddings_model is None:
                model_name = str(_PRETRAINED_DIR) if _PRETRAINED_DIR.exists() else _FALLBACK_MODEL
                logger.info("Chargement du modèle d'embeddings: %s", model_name)
                _embeddings_model = HuggingFaceEmbeddings(
                    model_name=model_name,
                    model_kwargs={"device": "cpu"},  # 'cuda' si un GPU est disponible
                    encode_kwargs={"normalize_embeddings": True},
                )
    return _embeddings_model


def _format_chunk_content(chunk: Any) -> str:
    """Préfixe le contenu par le fil d'Ariane des en-têtes Markdown.

    Le découpage hybride (`split_administrative_document`) place la hiérarchie
    structurelle (Titre / Chapitre / Article) dans `chunk.metadata`. On la
    conserve dans le texte indexé *et* embarqué — ce qui améliore le rappel et
    la lisibilité des citations — en attendant une colonne dédiée (JSONB, étape 3).
    """
    metadata = getattr(chunk, "metadata", None) or {}
    breadcrumb = " > ".join(str(value) for value in metadata.values() if value)
    if breadcrumb:
        return f"[{breadcrumb}]\n{chunk.page_content}"
    return chunk.page_content


async def process_document_to_chunks(
    document_text: str,
    document_title: str,
    file_type: str = "md",
    uploaded_by: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    headers_to_split_on: list[tuple[str, str]] | None = None,
    chunk_size: int = 400,
    chunk_overlap: int = 40,
    page_number: int = 1,
) -> dict[str, Any]:
    """Découpe, embarque et stocke un document dans la base.

    Si `document_id` est fourni, les chunks sont rattachés à un document déjà
    enregistré (cas nominal : la route d'upload crée la ligne, la tâche de fond
    l'indexe). Sinon un nouveau document est créé.

    Le statut du document est persisté à `processing` *avant* le travail lourd
    (donc observable en base), puis passé à `active` en une seule transaction
    incluant tous les chunks (tout-ou-rien), ou à `failed` en cas d'erreur.
    """
    async with SessionLocal() as db:
        # 1. Résoudre / créer le document, et le marquer `processing` (commit
        #    immédiat pour que le statut soit visible pendant l'indexation).
        if document_id is not None:
            document = await db.get(Document, document_id)
            if document is None:
                return {
                    "success": False,
                    "error": f"Document {document_id} introuvable",
                    "document_id": str(document_id),
                }
            document.status = Document.STATUS_PROCESSING
        else:
            document = Document(
                title=document_title,
                file_path=f"processed/{document_title}.{file_type}",
                file_type=file_type,
                status=Document.STATUS_PROCESSING,
                uploaded_by=uploaded_by,
            )
            db.add(document)

        await db.commit()
        await db.refresh(document)
        document_id = document.id

        try:
            # 2. Découpage hybride (Markdown structurel puis récursif). Pur
            #    Python mais potentiellement coûteux -> hors boucle asyncio.
            chunks = await asyncio.to_thread(
                split_administrative_document,
                document_text,
                headers_to_split_on,
                chunk_size,
                chunk_overlap,
            )
            logger.info("Document %s : %d chunks générés", document_id, len(chunks))

            if not chunks:
                document.status = Document.STATUS_FAILED
                await db.commit()
                return {
                    "success": False,
                    "error": "Aucun chunk généré (document vide ?)",
                    "document_id": str(document_id),
                    "status": Document.STATUS_FAILED,
                }

            # 3. Embeddings en *batch* (un seul passage modèle, bien plus
            #    rapide que chunk par chunk), déportés dans un thread.
            contents = [_format_chunk_content(chunk) for chunk in chunks]
            metadatas = [dict(getattr(chunk, "metadata", None) or {}) for chunk in chunks]
            model = get_embeddings()
            vectors = await asyncio.to_thread(model.embed_documents, contents)

            # 4. Ré-indexation idempotente : purger les anciens chunks de ce
            #    document avant d'insérer les nouveaux (sinon ré-ingérer duplique).
            #    Même transaction que l'insertion -> atomique. Les éventuelles
            #    citations (message_sources) pointant vers ces chunks passent à
            #    NULL (FK ON DELETE SET NULL).
            await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))

            # 5. Insertion des chunks + passage à `active` dans une seule
            #    transaction (tout-ou-rien). Les métadonnées structurelles brutes
            #    sont conservées dans la colonne dédiée (en plus du fil d'Ariane
            #    embarqué dans le contenu, utile au rappel).
            db.add_all(
                DocumentChunk(
                    document_id=document_id,
                    content=content,
                    page_number=page_number,
                    embedding=vector,
                    chunk_metadata=metadata or None,
                )
                for content, metadata, vector in zip(contents, metadatas, vectors)
            )
            document.status = Document.STATUS_ACTIVE
            document.updated_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info("Document %s indexé : %d chunks stockés", document_id, len(contents))
            return {
                "success": True,
                "document_id": str(document_id),
                "document_title": document.title,
                "chunk_count": len(contents),
                "status": Document.STATUS_ACTIVE,
                "embedding_dimensions": len(vectors[0]) if vectors else 0,
            }

        except Exception as exc:
            logger.exception("Échec de l'indexation du document %s", document_id)
            await db.rollback()
            # Le document existe déjà (commit `processing`) : on le repasse à
            # `failed` pour tracer l'échec de façon fiable.
            document = await db.get(Document, document_id)
            if document is not None:
                document.status = Document.STATUS_FAILED
                await db.commit()
            return {
                "success": False,
                "error": str(exc),
                "document_id": str(document_id),
                "status": Document.STATUS_FAILED,
            }


def _read_text_file(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as handle:
        return handle.read()


async def process_document_from_file(
    file_path: str,
    document_title: str,
    file_type: str = "txt",
    **kwargs: Any,
) -> dict[str, Any]:
    """Variante lisant le texte depuis un fichier (lecture disque hors boucle).

    Note : le fichier est entièrement chargé en mémoire (les splitters LangChain
    exigent le texte complet). Le streaming de très gros fichiers reste une
    évolution ultérieure.
    """
    try:
        document_text = await asyncio.to_thread(_read_text_file, file_path)
    except Exception as exc:
        logger.error("Lecture du fichier %s échouée : %s", file_path, exc)
        return {
            "success": False,
            "error": f"Lecture du fichier échouée : {exc}",
            "file_path": file_path,
        }

    return await process_document_to_chunks(
        document_text=document_text,
        document_title=document_title,
        file_type=file_type,
        **kwargs,
    )


async def get_document_chunks(document_id: uuid.UUID) -> list[dict[str, Any]]:
    """Récupère tous les chunks d'un document, triés par date de création."""
    async with SessionLocal() as db:
        result = await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.created_at)
        )
        return [
            {
                "chunk_id": str(chunk.id),
                "content": chunk.content,
                "page_number": chunk.page_number,
                "metadata": chunk.chunk_metadata,
                "created_at": chunk.created_at.isoformat() if chunk.created_at else None,
            }
            for chunk in result.scalars().all()
        ]
