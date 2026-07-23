from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.deps import get_current_user, require_role
from backend.models.notification_model import Notification, NotificationRead as NotificationReadModel
from backend.models.schemas import (
    NotificationCountRead,
    NotificationCreate,
    NotificationRead,
    NotificationUpdate,
)
from backend.models.user_model import User
from backend.models.user_model import normalize_role
from backend.services.notification_service import (
    create_notification,
    is_currently_visible,
    is_visible_for_role,
    normalize_target_role,
    validate_notification_values,
)

router = APIRouter(tags=["Notifications"])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification introuvable")


def _to_read_schema(notification: Notification, read_map: dict[UUID, datetime]) -> NotificationRead:
    read_at = read_map.get(notification.id)
    return NotificationRead(
        id=notification.id,
        title=notification.title,
        message=notification.message,
        notification_type=notification.notification_type,
        priority=notification.priority,
        target_role=notification.target_role,
        is_system=bool(notification.is_system),
        is_active=bool(notification.is_active),
        action_url=notification.action_url,
        metadata=notification.notification_metadata,
        created_by=notification.created_by,
        starts_at=notification.starts_at,
        expires_at=notification.expires_at,
        created_at=notification.created_at,
        updated_at=notification.updated_at,
        is_read=read_at is not None,
        read_at=read_at,
    )


async def _user_read_map(db: AsyncSession, user_id: UUID) -> dict[UUID, datetime]:
    result = await db.execute(select(NotificationReadModel).where(NotificationReadModel.user_id == user_id))
    return {row.notification_id: row.read_at for row in result.scalars().all()}


async def _visible_notifications(db: AsyncSession, current_user: User) -> list[Notification]:
    now = datetime.now(timezone.utc)
    role = normalize_role(current_user.role)
    result = await db.execute(
        select(Notification)
        .where(
            Notification.is_active.is_(True),
            or_(Notification.target_role == "all", Notification.target_role == role),
            or_(Notification.starts_at.is_(None), Notification.starts_at <= now),
            or_(Notification.expires_at.is_(None), Notification.expires_at > now),
        )
        .order_by(Notification.created_at.desc())
    )
    return [
        notification
        for notification in result.scalars().all()
        if is_currently_visible(notification, now) and is_visible_for_role(notification, current_user.role)
    ]


@router.get("/api/notifications", response_model=list[NotificationRead])
async def list_my_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notifications = await _visible_notifications(db, current_user)
    read_map = await _user_read_map(db, current_user.id)
    return [_to_read_schema(notification, read_map) for notification in notifications]


@router.get("/api/notifications/unread-count", response_model=NotificationCountRead)
async def unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notifications = await _visible_notifications(db, current_user)
    read_map = await _user_read_map(db, current_user.id)
    return NotificationCountRead(unread_count=sum(1 for item in notifications if item.id not in read_map))


@router.post("/api/notifications/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = await db.get(Notification, notification_id)
    if notification is None or not is_currently_visible(notification) or not is_visible_for_role(notification, current_user.role):
        raise NOT_FOUND

    result = await db.execute(
        select(NotificationReadModel).where(
            NotificationReadModel.notification_id == notification_id,
            NotificationReadModel.user_id == current_user.id,
        )
    )
    read = result.scalar_one_or_none()
    if read is None:
        read = NotificationReadModel(notification_id=notification_id, user_id=current_user.id)
        db.add(read)
        await db.commit()
        await db.refresh(read)

    return _to_read_schema(notification, {notification_id: read.read_at})


@router.post("/api/notifications/read-all", response_model=NotificationCountRead)
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notifications = await _visible_notifications(db, current_user)
    read_map = await _user_read_map(db, current_user.id)
    for notification in notifications:
        if notification.id not in read_map:
            db.add(NotificationReadModel(notification_id=notification.id, user_id=current_user.id))
    await db.commit()
    return NotificationCountRead(unread_count=0)


@router.get("/api/admin/notifications", response_model=list[NotificationRead])
async def list_admin_notifications(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await db.execute(select(Notification).order_by(Notification.created_at.desc()))
    return [_to_read_schema(notification, {}) for notification in result.scalars().all()]


@router.post("/api/admin/notifications", response_model=NotificationRead, status_code=status.HTTP_201_CREATED)
async def create_admin_notification(
    payload: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    try:
        notification = await create_notification(
            db,
            title=payload.title,
            message=payload.message,
            notification_type=payload.notification_type,
            priority=payload.priority,
            target_role=payload.target_role,
            created_by=current_user.id,
            is_system=payload.is_system,
            is_active=payload.is_active,
            action_url=payload.action_url,
            starts_at=payload.starts_at,
            expires_at=payload.expires_at,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _to_read_schema(notification, {})


@router.patch("/api/admin/notifications/{notification_id}", response_model=NotificationRead)
async def update_admin_notification(
    notification_id: UUID,
    payload: NotificationUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    notification = await db.get(Notification, notification_id)
    if notification is None:
        raise NOT_FOUND

    for field_name in ("title", "message", "notification_type", "priority", "action_url", "starts_at", "expires_at", "is_active"):
        value = getattr(payload, field_name)
        if value is not None:
            setattr(notification, field_name, value)
    if payload.target_role is not None:
        notification.target_role = normalize_target_role(payload.target_role)
    if payload.metadata is not None:
        notification.notification_metadata = payload.metadata

    try:
        validate_notification_values(notification.target_role, notification.notification_type, notification.priority)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    await db.commit()
    await db.refresh(notification)
    return _to_read_schema(notification, {})


@router.delete("/api/admin/notifications/{notification_id}")
async def delete_admin_notification(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    notification = await db.get(Notification, notification_id)
    if notification is None:
        raise NOT_FOUND
    await db.delete(notification)
    await db.commit()
    return {"detail": f"Notification {notification_id} supprimee"}
