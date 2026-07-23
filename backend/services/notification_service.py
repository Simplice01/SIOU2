"""Business helpers for SIOU notifications."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.notification_model import Notification
from backend.models.user_model import normalize_role

VALID_TARGET_ROLES = {"all", "admin", "user", "secretary", "validator", "ministry_manager"}
VALID_NOTIFICATION_TYPES = {"info", "success", "warning", "danger", "system"}
VALID_PRIORITIES = {"low", "normal", "high", "urgent"}

SYSTEM_NOTIFICATION_TEMPLATES: dict[str, dict] = {
    "document_indexed": {
        "title": "Document disponible",
        "message": "Un nouveau document a ete indexe dans la base documentaire.",
        "notification_type": "system",
        "priority": "normal",
        "target_role": "admin",
    },
    "maintenance": {
        "title": "Maintenance planifiee",
        "message": "Une operation de maintenance est planifiee sur la plateforme SIOU.",
        "notification_type": "warning",
        "priority": "high",
        "target_role": "all",
    },
    "knowledge_update": {
        "title": "Nouvelle information disponible",
        "message": "La base de connaissance SIOU contient de nouvelles informations.",
        "notification_type": "info",
        "priority": "normal",
        "target_role": "all",
    },
}


def normalize_target_role(role: str | None) -> str:
    if role is None or str(role).strip() == "":
        return "all"
    value = str(role).strip()
    if value == "all":
        return value
    return normalize_role(value)


def validate_notification_values(target_role: str, notification_type: str, priority: str) -> None:
    if target_role not in VALID_TARGET_ROLES:
        raise ValueError("Role cible invalide.")
    if notification_type not in VALID_NOTIFICATION_TYPES:
        raise ValueError("Type de notification invalide.")
    if priority not in VALID_PRIORITIES:
        raise ValueError("Priorite de notification invalide.")


def is_visible_for_role(notification: Notification, user_role: str) -> bool:
    target = normalize_target_role(notification.target_role)
    if target == "all":
        return True
    return target == normalize_role(user_role)


def is_currently_visible(notification: Notification, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if not bool(notification.is_active):
        return False
    if notification.starts_at and notification.starts_at > now:
        return False
    if notification.expires_at and notification.expires_at <= now:
        return False
    return True


async def create_notification(
    db: AsyncSession,
    *,
    title: str,
    message: str,
    notification_type: str = "info",
    priority: str = "normal",
    target_role: str = "all",
    created_by: UUID | None = None,
    is_system: bool = False,
    is_active: bool = True,
    action_url: str | None = None,
    starts_at: datetime | None = None,
    expires_at: datetime | None = None,
    metadata: dict | None = None,
) -> Notification:
    target = normalize_target_role(target_role)
    validate_notification_values(target, notification_type, priority)
    notification = Notification(
        title=title,
        message=message,
        notification_type=notification_type,
        priority=priority,
        target_role=target,
        created_by=created_by,
        is_system=is_system,
        is_active=is_active,
        action_url=action_url,
        starts_at=starts_at,
        expires_at=expires_at,
        notification_metadata=metadata,
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return notification


async def emit_system_notification(
    db: AsyncSession,
    template_key: str,
    *,
    overrides: dict | None = None,
) -> Notification:
    template = SYSTEM_NOTIFICATION_TEMPLATES.get(template_key)
    if template is None:
        raise ValueError("Modele de notification systeme inconnu.")
    payload = {**template, **(overrides or {})}
    return await create_notification(db, is_system=True, **payload)
