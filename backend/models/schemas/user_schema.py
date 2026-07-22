from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

class UserBase(BaseModel):
    username: str
    first_name: str | None = None
    last_name: str | None = None
    role: str = "user"
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserSelfUpdate(BaseModel):
    """Champs qu'un utilisateur peut modifier sur son propre profil.

    Volontairement restreint à l'identité (prénom / nom) : le rôle et
    l'état actif ne sont modifiables que par un administrateur
    (`PATCH /api/admin/users/{id}`), jamais par l'utilisateur lui-même.
    """

    first_name: str | None = None
    last_name: str | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime | None = None
