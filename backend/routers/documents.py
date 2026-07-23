from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.deps import get_current_user, require_role
from backend.models.document_models import Document
from backend.models.schemas import DocumentCreate, DocumentIngestRequest, DocumentRead, DocumentUpdate
from backend.models.user_model import User
from backend.services.ingestion import run_document_ingestion

router = APIRouter(prefix="/api/documents", tags=["Documents"])

# Roles autorises a consulter et administrer la base documentaire (back-office).
WRITE_ROLES = ("admin", "administrateur", "ministry_manager", "responsable_ministere", "validator", "point_focal")


@router.get("", response_model=list[DocumentRead])
async def list_documents_endpoint(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(*WRITE_ROLES)),
):
    """Liste les documents indexes pour les roles back-office."""
    result = await db.execute(select(Document).options(selectinload(Document.source_file)).order_by(Document.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    payload: DocumentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(*WRITE_ROLES)),
):
    """Enregistre un nouveau document (métadonnées)."""
    document = Document(
        title=payload.title,
        file_path=payload.file_path,
        file_type=payload.file_type,
        status=payload.status or Document.STATUS_PROCESSING,
        uploaded_by=payload.uploaded_by or current_user.id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


@router.post("/ingest", response_model=DocumentRead, status_code=status.HTTP_202_ACCEPTED)
async def ingest_document(
    payload: DocumentIngestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(*WRITE_ROLES)),
):
    """Crée un document et lance son découpage/indexation en tâche de fond.

    Répond immédiatement (202) avec le document en statut `processing` ; le
    découpage, le calcul des embeddings et le stockage des chunks se déroulent
    en arrière-plan (le statut passera à `active` ou `failed`). Suivre l'état
    via GET /api/documents/{id}.
    """
    document = Document(
        title=payload.title,
        file_path=f"processed/{payload.title}.{payload.file_type}",
        file_type=payload.file_type,
        status=Document.STATUS_PROCESSING,
        uploaded_by=current_user.id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    background_tasks.add_task(
        run_document_ingestion,
        document_id=document.id,
        document_text=payload.content,
        document_title=payload.title,
        file_type=payload.file_type,
        uploaded_by=current_user.id,
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
    )
    return document


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document_endpoint(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")
    return document


@router.put("/{document_id}", response_model=DocumentRead)
async def update_document(
    document_id: UUID,
    payload: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(*WRITE_ROLES)),
):
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(document, field_name, value)
    await db.commit()
    await db.refresh(document)
    return document


@router.delete("/{document_id}")
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(*WRITE_ROLES)),
):
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")
    await db.delete(document)
    await db.commit()
    return {"detail": f"Document {document_id} supprimé"}


@router.post("/{document_id}/validate", response_model=DocumentRead)
async def validate_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(*WRITE_ROLES)),
):
    """Valide un document (statut -> actif/publié)."""
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")
    document.status = Document.STATUS_ACTIVE
    await db.commit()
    await db.refresh(document)
    return document


@router.post("/{document_id}/reject", response_model=DocumentRead)
async def reject_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(*WRITE_ROLES)),
):
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")
    document.status = Document.STATUS_FAILED
    await db.commit()
    await db.refresh(document)
    return document
