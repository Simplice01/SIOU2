"""Database models for the SIOU2 document system.

SIOU2 is now connected to the PostgreSQL schema prepared in the SIOU project.
The API keeps its historical field names while the ORM maps them to the richer
database tables already deployed on Render.
"""

from datetime import datetime, timezone
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import relationship

from backend.core.database import Base

ORGANIZATION_TYPE = ENUM(
    "ministere",
    "direction",
    "agence",
    "societe",
    "cellule",
    "programme",
    "guichet",
    "service",
    name="organization_type",
    create_type=False,
).with_variant(String(50), "sqlite")

SOURCE_KIND = ENUM(
    "pdf_officiel",
    "word_interne",
    "excel_interne",
    "html_portail",
    "api_officielle",
    "rss",
    "saisie_backoffice",
    "scraping",
    name="source_kind",
    create_type=False,
).with_variant(String(50), "sqlite")

DOCUMENT_TYPE = ENUM(
    "decret",
    "arrete",
    "accord",
    "statuts",
    "fiche_service",
    "procedure",
    "evenement",
    "page_web",
    "document_interne",
    "autre",
    name="document_type",
    create_type=False,
).with_variant(String(50), "sqlite")

PUBLICATION_STATUS = ENUM(
    "brouillon",
    "soumis_validation",
    "valide",
    "publie",
    "archive",
    "rejete",
    name="publication_status",
    create_type=False,
).with_variant(String(50), "sqlite")


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    name = Column(Text, nullable=False)
    acronym = Column(Text, unique=True, nullable=True)
    type = Column(ORGANIZATION_TYPE, nullable=False, default="service")
    description = Column(Text, nullable=True)
    missions = Column(Text, nullable=True)
    address = Column(Text, nullable=True)
    city = Column(Text, nullable=True)
    country = Column(Text, nullable=False, default="Bénin")
    phone = Column(Text, nullable=True)
    email = Column(Text, nullable=True)
    website = Column(Text, nullable=True)
    opening_hours = Column(Text, nullable=True)
    source_note = Column(Text, nullable=True)
    organization_metadata = Column("metadata", JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SourceFile(Base):
    __tablename__ = "source_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    kind = Column(SOURCE_KIND, nullable=False, default="pdf_officiel")
    original_filename = Column(Text, nullable=False)
    storage_uri = Column(Text, nullable=True)
    external_url = Column(Text, nullable=True)
    mime_type = Column(Text, nullable=True)
    sha256 = Column(Text, nullable=False, unique=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    page_count = Column(Integer, nullable=True)
    language = Column(Text, nullable=False, default="fr")
    legal_basis = Column(Text, nullable=True)
    collected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    source_metadata = Column("metadata", JSON().with_variant(JSONB(), "postgresql"), nullable=True)


class Document(Base):
    __tablename__ = "documents"

    STATUS_PROCESSING = "brouillon"
    STATUS_ACTIVE = "publie"
    STATUS_FAILED = "rejete"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    source_file_id = Column(UUID(as_uuid=True), ForeignKey("source_files.id", ondelete="SET NULL"), nullable=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    title = Column(Text, nullable=False)
    _type = Column("type", DOCUMENT_TYPE, nullable=False, default="autre")
    reference_number = Column(Text, nullable=True)
    official_date = Column(DateTime(timezone=True), nullable=True)
    publication_date = Column(DateTime(timezone=True), nullable=True)
    validity_start = Column(DateTime(timezone=True), nullable=True)
    validity_end = Column(DateTime(timezone=True), nullable=True)
    _status = Column("status", PUBLICATION_STATUS, nullable=False, default=STATUS_PROCESSING)
    summary = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)
    normalized_text = Column(Text, nullable=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    validated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    last_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    next_review_at = Column(DateTime(timezone=True), nullable=True)
    document_metadata = Column("metadata", JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    source_file = relationship("SourceFile")
    organization = relationship("Organization")
    uploader = relationship("User", foreign_keys=[owner_user_id], backref="uploaded_documents")
    chunks = relationship("DocumentChunk", backref="document", cascade="all, delete-orphan")

    @property
    def file_path(self) -> str:
        source_file = self.__dict__.get("source_file")
        if source_file is not None:
            return source_file.storage_uri or source_file.original_filename
        return str((self.document_metadata or {}).get("file_path", ""))

    @file_path.setter
    def file_path(self, value: str) -> None:
        metadata = dict(self.document_metadata or {})
        metadata["file_path"] = value
        self.document_metadata = metadata

    @property
    def file_type(self) -> str:
        source_file = self.__dict__.get("source_file")
        if source_file is not None and source_file.original_filename:
            suffix = source_file.original_filename.rsplit(".", 1)[-1].lower()
            if suffix:
                return suffix
        return str(self._type)

    @file_type.setter
    def file_type(self, value: str) -> None:
        self._type = {
            "pdf": "autre",
            "docx": "document_interne",
            "md": "document_interne",
            "txt": "document_interne",
        }.get(value, value)

    @property
    def status(self) -> str:
        return {
            self.STATUS_ACTIVE: "active",
            self.STATUS_PROCESSING: "processing",
            self.STATUS_FAILED: "failed",
        }.get(str(self._status), str(self._status))

    @status.setter
    def status(self, value: str) -> None:
        self._status = {
            "active": self.STATUS_ACTIVE,
            "processing": self.STATUS_PROCESSING,
            "failed": self.STATUS_FAILED,
        }.get(value, value)

    @property
    def uploaded_by(self):
        return self.owner_user_id

    @uploaded_by.setter
    def uploaded_by(self, value) -> None:
        self.owner_user_id = value

    def __repr__(self):
        return f"<Document {self.title} ({self.status})>"

    def is_processed(self) -> bool:
        return str(self._status) in {self.STATUS_ACTIVE, "active", "valide"}

    def has_failed(self) -> bool:
        return str(self._status) in {self.STATUS_FAILED, "failed", "archive"}


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    chunk_index = Column(Integer, nullable=False, default=0)
    page_start = Column(Integer)
    page_end = Column(Integer)
    section_title = Column(Text, nullable=True)
    contextual_title = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)
    char_count = Column(Integer, nullable=True)
    embedding_model = Column(Text, nullable=False, default="text-embedding-3-small")
    embedding = Column(Vector(1536), nullable=True)
    chunk_metadata = Column("metadata", JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    message_sources = relationship("MessageSource", backref="document_chunk")

    @property
    def page_number(self) -> int | None:
        return self.page_start

    @page_number.setter
    def page_number(self, value: int | None) -> None:
        self.page_start = value
        self.page_end = value

    def __repr__(self):
        return f"<DocumentChunk {self.id} (Doc: {self.document_id}, Page: {self.page_number})>"
