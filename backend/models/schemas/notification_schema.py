from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NotificationBase(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    message: str = Field(min_length=2, max_length=3000)
    notification_type: str = Field(default="info", max_length=50)
    priority: str = Field(default="normal", max_length=30)
    target_role: str = Field(default="all", max_length=50)
    action_url: str | None = Field(default=None, max_length=500)
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    metadata: dict | None = None


class NotificationCreate(NotificationBase):
    is_system: bool = False
    is_active: bool = True


class NotificationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    message: str | None = Field(default=None, min_length=2, max_length=3000)
    notification_type: str | None = Field(default=None, max_length=50)
    priority: str | None = Field(default=None, max_length=30)
    target_role: str | None = Field(default=None, max_length=50)
    action_url: str | None = Field(default=None, max_length=500)
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    is_active: bool | None = None
    metadata: dict | None = None


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    message: str
    notification_type: str
    priority: str
    target_role: str
    is_system: bool
    is_active: bool
    action_url: str | None = None
    metadata: dict | None = None
    created_by: UUID | None = None
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    is_read: bool = False
    read_at: datetime | None = None


class NotificationCountRead(BaseModel):
    unread_count: int
