from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .user_schema import UserRead


class ConversationBase(BaseModel):
    user_id: UUID | None = None
    title: str = "Nouvelle recherche"


class ConversationCreate(ConversationBase):
    pass


class ConversationUpdate(BaseModel):
    title: str | None = None
    user_id: UUID | None = None


class ConversationRead(ConversationBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MessageBase(BaseModel):
    conversation_id: UUID
    sender_type: str
    content: str


class MessageCreate(MessageBase):
    model_used: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: int | None = None


class MessageRead(MessageBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    model_used: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: int | None = None
    created_at: datetime | None = None


class MessageSourceBase(BaseModel):
    message_id: UUID
    chunk_id: UUID | None = None
    similarity_score: float | None = None


class MessageSourceRead(MessageSourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime | None = None


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None
    document_ids: list[UUID] = Field(default_factory=list)


class SourceCitation(BaseModel):
    title: str
    meta: str
    document_id: UUID | None = None
    score: float | None = None


class ChatResponse(BaseModel):
    text: str
    sources: list[SourceCitation] = Field(default_factory=list)
    confidence: float = 0.0
    model: str
    conversation_id: UUID | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """Corps de la requête POST /api/auth/login."""

    username: str
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    """Corps de la requête POST /api/auth/refresh."""

    refresh_token: str


class AuthResponse(TokenPair):
    """Réponse de POST /api/auth/login : les deux jetons plus l'utilisateur connecté."""

    user: UserRead


class MessageSourceCitationRead(BaseModel):
    title: str
    page_number: int | None = None
    score: float | None = None
    user: UserRead
