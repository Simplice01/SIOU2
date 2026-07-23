from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.deps import get_current_user
from backend.models.feedback_model import Feedback
from backend.models.schemas import FeedbackCreate, FeedbackRead, FeedbackUpdate
from backend.models.user_model import User, normalize_role

router = APIRouter(prefix="/api/feedbacks", tags=["Feedbacks"])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback introuvable")
SUPERVISION_ROLES = {"admin", "ministry_manager", "validator"}
DELETE_ALL_ROLES = {"admin", "ministry_manager"}


@router.get("", response_model=list[FeedbackRead])
async def list_feedbacks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Feedback).order_by(Feedback.created_at.desc())
    if normalize_role(current_user.role) not in SUPERVISION_ROLES:
        query = query.where(Feedback.reporter_user_id == current_user.id)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    payload: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    feedback = Feedback(
        conversation_id=payload.conversation_id,
        message_id=payload.message_id,
        user_id=current_user.id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return feedback


@router.get("/{feedback_id}", response_model=FeedbackRead)
async def get_feedback(
    feedback_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    feedback = await db.get(Feedback, feedback_id)
    if feedback is None or not _can_access_feedback(current_user, feedback):
        raise NOT_FOUND
    return feedback


@router.patch("/{feedback_id}", response_model=FeedbackRead)
async def update_feedback(
    feedback_id: UUID,
    payload: FeedbackUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    feedback = await db.get(Feedback, feedback_id)
    if feedback is None or not _can_access_feedback(current_user, feedback):
        raise NOT_FOUND
    if payload.rating is not None:
        feedback.rating = payload.rating
    if payload.comment is not None:
        feedback.comment = payload.comment
    await db.commit()
    await db.refresh(feedback)
    return feedback


@router.delete("/{feedback_id}")
async def delete_feedback(
    feedback_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    feedback = await db.get(Feedback, feedback_id)
    if feedback is None or not _can_access_feedback(current_user, feedback, delete=True):
        raise NOT_FOUND
    await db.delete(feedback)
    await db.commit()
    return {"detail": f"Feedback {feedback_id} supprime"}


def _can_access_feedback(current_user: User, feedback: Feedback, delete: bool = False) -> bool:
    role = normalize_role(current_user.role)
    if delete and role in DELETE_ALL_ROLES:
        return True
    if not delete and role in SUPERVISION_ROLES:
        return True
    return feedback.reporter_user_id == current_user.id
