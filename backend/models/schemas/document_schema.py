from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentBase(BaseModel):
    title: str
    file_path: str
    file_type: str
    status: str = "processing"
    uploaded_by: UUID | None = None


class DocumentCreate(DocumentBase):
    pass


class DocumentIngestRequest(BaseModel):
    """Corps de POST /api/documents/ingest : le texte brut à découper et indexer."""

    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    file_type: str = "md"
    chunk_size: int = Field(default=400, ge=100, le=4000)
    chunk_overlap: int = Field(default=40, ge=0, le=1000)


class DocumentUpdate(BaseModel):
    title: str | None = None
    file_path: str | None = None
    file_type: str | None = None
    status: str | None = None
    uploaded_by: UUID | None = None


class DocumentRead(DocumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DocumentChunkBase(BaseModel):
    document_id: UUID
    content: str
    page_number: int | None = None


class DocumentChunkCreate(DocumentChunkBase):
    embedding: list[float] | None = None


class DocumentChunkRead(DocumentChunkBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime | None = None