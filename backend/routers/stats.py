"""Statistiques agrégées pour le tableau de bord.

Fournit des chiffres réels calculés sur la base (conversations, documents),
en remplacement des valeurs codées en dur du frontend. Accessible à tout
utilisateur authentifié (données agrégées, non nominatives).
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.deps import get_current_user
from backend.models.conversation_models import Conversation
from backend.models.document_models import Document
from backend.models.user_model import User

router = APIRouter(prefix="/api/stats", tags=["Statistiques"])

# Libellés lisibles des statuts de document (le backend stocke des codes).
STATUS_LABELS = {
    Document.STATUS_ACTIVE: "Actifs",
    Document.STATUS_PROCESSING: "En traitement",
    Document.STATUS_FAILED: "Refusés",
}
STATUS_TO_API = {
    Document.STATUS_ACTIVE: "active",
    Document.STATUS_PROCESSING: "processing",
    Document.STATUS_FAILED: "failed",
}


async def _count(db: AsyncSession, model, *conditions) -> int:
    stmt = select(func.count()).select_from(model)
    for condition in conditions:
        stmt = stmt.where(condition)
    return int((await db.execute(stmt)).scalar_one())


@router.get("")
async def get_statistics(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Chiffres du tableau de bord (conversations du mois, documents)."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_start = (month_start - timedelta(days=1)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    week_ago = now - timedelta(days=7)

    # --- Conversations : ce mois-ci vs le mois précédent ---
    current_month = await _count(db, Conversation, Conversation.created_at >= month_start)
    previous_month = await _count(
        db,
        Conversation,
        Conversation.created_at >= prev_month_start,
        Conversation.created_at < month_start,
    )
    if previous_month > 0:
        change_percent = round((current_month - previous_month) / previous_month * 100, 1)
    else:
        change_percent = 100.0 if current_month > 0 else 0.0

    # --- Documents : total, récents (7 j), répartition par statut ---
    total_documents = await _count(db, Document)
    recent_documents = await _count(db, Document, Document.created_at >= week_ago)

    status_rows = (
        await db.execute(select(Document._status, func.count()).group_by(Document._status))
    ).all()
    by_status = [
        {
            "status": STATUS_TO_API.get(status, status),
            "label": STATUS_LABELS.get(status, status or "Inconnu"),
            "count": int(count),
            "percentage": round(count / total_documents * 100) if total_documents else 0,
        }
        for status, count in sorted(status_rows, key=lambda r: r[1], reverse=True)
    ]

    return {
        "conversations": {
            "current_month": current_month,
            "previous_month": previous_month,
            "change_percent": change_percent,
        },
        "documents": {
            "total": total_documents,
            "recent": recent_documents,
            "by_status": by_status,
        },
    }
