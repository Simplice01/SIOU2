"""
SQLAlchemy models for Conversation system.
Based on backend/models/db/conversation.sql
"""

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from datetime import datetime, timezone
import uuid

from backend.core.database import Base
from .user_model import User

class Conversation(Base):
    """
    Conversation model representing the conversations table.

    Columns:
    - id: UUID primary key
    - user_id: Foreign key to users table
    - title: Conversation title
    - created_at: Creation timestamp
    - updated_at: Last update timestamp
    """

    __tablename__ = "conversations"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    title = Column(String(255), default="Nouvelle recherche")
    channel = Column(String(50), default="web")
    user_context = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    contains_personal_data = Column(Boolean, default=False)
    retention_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user = relationship("User", backref="conversations")
    messages = relationship("Message", backref="conversation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Conversation {self.title} (User: {self.user_id})>"

class Message(Base):
    """
    Message model representing the messages table.

    Columns:
    - id: UUID primary key
    - conversation_id: Foreign key to conversations table
    - sender_type: 'human' or 'ia'
    - content: Message text content
    - model_used: LLM model used (for IA messages)
    - prompt_tokens: Number of prompt tokens (for IA messages)
    - completion_tokens: Number of completion tokens (for IA messages)
    - latency_ms: Generation latency in milliseconds (for IA messages)
    - created_at: Message timestamp
    """

    __tablename__ = "messages"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    _role = Column("role", String(50), nullable=False)
    content = Column(Text, nullable=False)

    # LLMOps section (only for IA messages)
    model_used = Column(String(100))  # e.g., 'mistral-7b-instruct'
    prompt_tokens = Column(Integer)   # Tokens in question + system context
    completion_tokens = Column(Integer)  # Tokens in AI response
    latency_ms = Column(Integer)      # Generation time in milliseconds
    confidence_score = Column(Float, nullable=True)
    refusal_reason = Column(Text, nullable=True)
    message_metadata = Column("metadata", JSON().with_variant(JSONB(), "postgresql"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    sources = relationship("MessageSource", backref="message", cascade="all, delete-orphan")

    @property
    def sender_type(self) -> str:
        if self._role == "assistant":
            return "ia"
        if self._role == "user":
            return "human"
        return str(self._role)

    @sender_type.setter
    def sender_type(self, value: str) -> None:
        self._role = {"ia": "assistant", "human": "user"}.get(value, value)

    def __repr__(self):
        return f"<Message {self.sender_type}: {self.content[:50]}...>"


class MessageSource(Base):
    """
    Message source model representing the message_sources table.

    Columns:
    - id: UUID primary key
    - message_id: Foreign key to messages table
    - chunk_id: Foreign key to document_chunks table
    - similarity_score: Similarity score from vector search
    - created_at: Creation timestamp
    """

    __tablename__ = "message_sources"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    chunk_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    page = Column(Integer, nullable=True)
    _score = Column("score", Float)
    citation = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    @property
    def similarity_score(self) -> float | None:
        return self._score

    @similarity_score.setter
    def similarity_score(self, value: float | None) -> None:
        self._score = value

    def __repr__(self):
        return f"<MessageSource {self.id} (Score: {self.similarity_score})>"
