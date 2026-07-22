"""SQLAlchemy model for the users table.

This project is connected to the PostgreSQL schema prepared by the SIOU
knowledge-base project. The public API of SIOU2 still exposes `username`,
`first_name` and `last_name`; internally those values are backed by the
existing `email` and `full_name` columns.
"""

from datetime import datetime, timezone
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import ENUM, UUID

from backend.core.database import Base


ROLE_TO_DATABASE = {
    "admin": "administrateur",
    "administrator": "administrateur",
    "user": "usager_anonyme",
    "validator": "point_focal",
}

ROLE_TO_API = {
    "administrateur": "admin",
    "usager_anonyme": "user",
    "point_focal": "validator",
}

USER_ROLE_TYPE = ENUM(
    "usager_anonyme",
    "secretaire",
    "point_focal",
    "responsable_ministere",
    "administrateur",
    name="user_role",
    create_type=False,
).with_variant(String(50), "sqlite")


def to_database_role(role: str | None) -> str:
    if not role:
        return "usager_anonyme"
    return ROLE_TO_DATABASE.get(role, role)


def to_api_role(role: str | None) -> str:
    if not role:
        return "user"
    return ROLE_TO_API.get(role, role)


class User(Base):
    """User record stored in PostgreSQL."""

    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    full_name = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=False)
    _role = Column("role", USER_ROLE_TYPE, default="usager_anonyme")
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    @property
    def username(self) -> str:
        return self.email or str(self.id)

    @username.setter
    def username(self, value: str) -> None:
        self.email = value

    @property
    def first_name(self) -> str | None:
        if not self.full_name:
            return None
        return self.full_name.split(" ", 1)[0]

    @first_name.setter
    def first_name(self, value: str | None) -> None:
        last = self.last_name
        self.full_name = " ".join(part for part in [value, last] if part).strip() or None

    @property
    def last_name(self) -> str | None:
        if not self.full_name:
            return None
        if " " not in self.full_name:
            return self.full_name
        return self.full_name.split(" ", 1)[1]

    @last_name.setter
    def last_name(self, value: str | None) -> None:
        first = self.first_name
        self.full_name = " ".join(part for part in [first, value] if part).strip() or None

    @property
    def role(self) -> str:
        return to_api_role(str(self._role))

    @role.setter
    def role(self, value: str) -> None:
        self._role = to_database_role(value)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"

    def is_admin(self) -> bool:
        """Check if user has admin privileges."""
        return str(self._role) in {"admin", "administrateur"} or str(self.role) == "admin"

    #def is_validator(self) -> bool:
     #   """Check if user has validator privileges."""
      #  return self.role == "validator"
