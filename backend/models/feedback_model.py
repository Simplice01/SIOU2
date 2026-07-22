"""Feedback model mapped to the existing SIOU `feedback_reports` table."""

from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, Text
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

from backend.core.database import Base

FEEDBACK_STATUS = ENUM(
    "nouveau",
    "en_analyse",
    "corrige",
    "rejete",
    "archive",
    name="feedback_status",
    create_type=False,
).with_variant(String(50), "sqlite")


class Feedback(Base):
    __tablename__ = "feedback_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    reporter_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    description = Column(Text, nullable=False)
    expected_answer = Column(Text, nullable=True)
    status = Column(FEEDBACK_STATUS, nullable=False, default="nouveau")
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_note = Column(Text, nullable=True)
    feedback_metadata = Column("metadata", JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @property
    def user_id(self):
        return self.reporter_user_id

    @user_id.setter
    def user_id(self, value) -> None:
        self.reporter_user_id = value

    @property
    def rating(self) -> int:
        value = (self.feedback_metadata or {}).get("rating")
        return int(value) if value is not None else 3

    @rating.setter
    def rating(self, value: int) -> None:
        metadata = dict(self.feedback_metadata or {})
        metadata["rating"] = value
        self.feedback_metadata = metadata

    @property
    def comment(self) -> str | None:
        return self.description

    @comment.setter
    def comment(self, value: str | None) -> None:
        self.description = value or "Feedback sans commentaire."
