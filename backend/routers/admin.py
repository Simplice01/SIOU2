from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, extract
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.deps import require_role
from backend.models.schemas import (
    DocumentCreate,
    DocumentRead,
    DocumentUpdate,
    FeedbackRead,
    UserCreate,
    UserRead,
    UserUpdate,
)
from backend.models.user_model import User
from backend.models.document_models import Document
from backend.models.feedback_model import Feedback
from backend.models.conversation_models import Conversation
from backend.core.security import hash_password , verify_password

router = APIRouter(prefix="/api/admin", tags=["Admin"])

@router.get("/statistics")
async def get_statistics(_: User = Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    """
    Get dashboard statistics including:
    - Total users count
    - Conversations count (current month and previous month)
    - Documents count (total and by status)
    - Feedbacks count
    - Category distribution for conversations
    """
    # Calculate date ranges
    today = datetime.now(timezone.utc)
    current_month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous_month_start = (current_month_start - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Get total users count
    users_result = await db.execute(select(func.count(User.id)))
    total_users = users_result.scalar_one()

    # Get conversations count for current month
    current_month_conversations_result = await db.execute(
        select(func.count(Conversation.id))
        .where(Conversation.created_at >= current_month_start)
    )
    current_month_conversations = current_month_conversations_result.scalar_one()

    # Get conversations count for previous month
    previous_month_conversations_result = await db.execute(
        select(func.count(Conversation.id))
        .where(Conversation.created_at >= previous_month_start)
        .where(Conversation.created_at < current_month_start)
    )
    previous_month_conversations = previous_month_conversations_result.scalar_one()

    # Get total documents count and by status
    total_documents_result = await db.execute(select(func.count(Document.id)))
    total_documents = total_documents_result.scalar_one()

    active_documents_result = await db.execute(
        select(func.count(Document.id))
        .where(Document._status == Document.STATUS_ACTIVE)
    )
    active_documents = active_documents_result.scalar_one()

    processing_documents_result = await db.execute(
        select(func.count(Document.id))
        .where(Document._status == Document.STATUS_PROCESSING)
    )
    processing_documents = processing_documents_result.scalar_one()

    failed_documents_result = await db.execute(
        select(func.count(Document.id))
        .where(Document._status == Document.STATUS_FAILED)
    )
    failed_documents = failed_documents_result.scalar_one()

    # Get total feedbacks count
    feedbacks_result = await db.execute(select(func.count(Feedback.id)))
    total_feedbacks = feedbacks_result.scalar_one()

    # Calculate percentage change for conversations
    if previous_month_conversations > 0:
        conversation_change_percent = ((current_month_conversations - previous_month_conversations) / previous_month_conversations) * 100
    else:
        conversation_change_percent = 100.0 if current_month_conversations > 0 else 0.0

    # Get recent documents (last 7 days)
    seven_days_ago = today - timedelta(days=7)
    recent_documents_result = await db.execute(
        select(func.count(Document.id))
        .where(Document.created_at >= seven_days_ago)
    )
    recent_documents = recent_documents_result.scalar_one()

    # Mock category distribution (would need actual category field in conversations)
    # For now, using hardcoded distribution similar to the frontend
    category_distribution = [
        {"category": "État civil", "percentage": 38},
        {"category": "Identité & titres de voyage", "percentage": 27},
        {"category": "Entreprises & fiscalité", "percentage": 21},
        {"category": "Autres démarches", "percentage": 14}
    ]

    return {
        "users": {
            "total": total_users
        },
        "conversations": {
            "current_month": current_month_conversations,
            "previous_month": previous_month_conversations,
            "change_percent": round(conversation_change_percent, 1),
            "category_distribution": category_distribution
        },
        "documents": {
            "total": total_documents,
            "active": active_documents,
            "processing": processing_documents,
            "failed": failed_documents,
            "recent": recent_documents
        },
        "feedbacks": {
            "total": total_feedbacks
        }
    }


def _not_found(entity: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{entity} introuvable")


# A mettre à jour : Besoin d'une fonction qui retourne les utilisateurs de la BDD
@router.get("/users", response_model=list[UserRead])
async def list_users(_: User = Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()



@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(*, payload: UserCreate, _: User = Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
        
    existing = await db.execute(select(User).where(User.email == payload.username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nom d'utilisateur déjà utilisé")

    user = User(
            username=payload.username,
            password_hash=hash_password(payload.password),
            first_name=payload.first_name,
            last_name=payload.last_name,
            role=payload.role,
            is_active=payload.is_active,
        )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
    
    
    
  
@router.get("/users/{user_id}", response_model=UserRead)
async def get_user_by_id(user_id: UUID, _: User = Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    
    user = await db.get(User, user_id)
    if user is None:
        raise _not_found("Utilisateur")
    return user



# Vraiment besoin d'un modèle de recupération automatique des utilisateurs en Base 
@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(user_id: UUID, payload: UserUpdate, _: User = Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    
    user = await db.get(User, user_id)
    if user is None:
        raise _not_found("Utilisateur")

    for field_name in ("first_name", "last_name", "role", "is_active"):
        value = getattr(payload, field_name)
        if value is not None:
            setattr(user, field_name, value)

    await db.commit()
    await db.refresh(user)
    return user

   

@router.delete("/users/{user_id}")
async def delete_user(user_id: UUID, _: User = Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    
    user = await db.get(User, user_id)
    if user is None:
        raise _not_found("Utilisateur")
    await db.delete(user)
    await db.commit()
    return {"detail": f"Utilisateur {user_id} supprimé"}

  


# Gestion des documents par l'admin

@router.get("/documents", response_model=list[DocumentRead])
async def list_documents(_: User = Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    
    result = await db.execute(select(Document).options(selectinload(Document.source_file)).order_by(Document.created_at.desc()))
    return result.scalars().all()



@router.post("/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def create_document(
        *,
        payload: DocumentCreate,
        current_admin: User = Depends(require_role("admin")),
        db: AsyncSession = Depends(get_db),
    ):
        document = Document(
            title=payload.title,
            file_path=payload.file_path,
            file_type=payload.file_type,
            status=payload.status,
            uploaded_by=payload.uploaded_by or current_admin.id,
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document
  
  
  
@router.get("/documents/{document_id}", response_model=DocumentRead)
async def get_document_by_id(document_id: UUID, _: User = Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    
        document = await db.get(Document, document_id)
        if document is None:
            raise _not_found("Document")
        return document
    


@router.patch("/documents/{document_id}", response_model=DocumentRead)
async def update_document(document_id: UUID, payload: DocumentUpdate, _: User = Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    
    document = await db.get(Document, document_id)
    if document is None:
        raise _not_found("Document")

    for field_name in ("title", "file_path", "file_type", "status", "uploaded_by"):
        value = getattr(payload, field_name)
        if value is not None:
            setattr(document, field_name, value)

    await db.commit()
    await db.refresh(document)
    return document


@router.delete("/documents/{document_id}")

async def delete_document(document_id: UUID, _: User = Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    
        document = await db.get(Document, document_id)
        if document is None:
            raise _not_found("Document")
        await db.delete(document)
        await db.commit()
        return {"detail": f"Document {document_id} supprimé"}
    
   
        
# FeedBacks

@router.get("/feedbacks", response_model=list[FeedbackRead])
async def list_feedbacks(_: User = Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    
    result = await db.execute(select(Feedback).order_by(Feedback.created_at.desc()))
    return result.scalars().all()

    
    
    
@router.get("/feedbacks/{feedback_id}", response_model=FeedbackRead)
async def get_feedback_by_id(feedback_id: UUID, _: User = Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
        feedback = await db.get(Feedback, feedback_id)
        if feedback is None:
            raise _not_found("Feedback")
        return feedback



@router.delete("/feedbacks/{feedback_id}")
async def delete_feedback(feedback_id: UUID, _: User = Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
        feedback = await db.get(Feedback, feedback_id)
        if feedback is None:
            raise _not_found("Feedback")
        await db.delete(feedback)
        await db.commit()
        return {"detail": f"Feedback {feedback_id} supprimé"}
    
