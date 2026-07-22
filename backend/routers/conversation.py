from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.deps import get_current_user
from backend.models.conversation_models import Conversation, Message
from backend.models.schemas import ConversationCreate, ConversationRead, ConversationUpdate, MessageRead
from backend.models.user_model import User

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation introuvable")


async def _get_owned(conversation_id: UUID, db: AsyncSession, user: User) -> Conversation:
    """Récupère une conversation en vérifiant l'appartenance (admin : accès total)."""
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise NOT_FOUND
    if conversation.user_id != user.id and user.role != "admin":
        raise NOT_FOUND
    return conversation


@router.get("", response_model=list[ConversationRead])
async def get_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne les conversations de l'utilisateur connecté."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{conversation_id}", response_model=ConversationRead)
async def get_conversation_by_id(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _get_owned(conversation_id, db, current_user)


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
async def get_conversation_messages(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne les messages d'une conversation (ordre chronologique), pour rejouer le fil."""
    await _get_owned(conversation_id, db, current_user)  # 404 si absente / non possédée
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return result.scalars().all()


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = Conversation(
        user_id=payload.user_id or current_user.id,
        title=payload.title,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


@router.patch("/{conversation_id}", response_model=ConversationRead)
async def update_conversation(
    conversation_id: UUID,
    payload: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = await _get_owned(conversation_id, db, current_user)
    if payload.title is not None:
        conversation.title = payload.title
    await db.commit()
    await db.refresh(conversation)
    return conversation


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = await _get_owned(conversation_id, db, current_user)
    await db.delete(conversation)
    await db.commit()
    return {"detail": f"Conversation {conversation_id} supprimée"}
