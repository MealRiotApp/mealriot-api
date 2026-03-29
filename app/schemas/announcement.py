from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime


class AnnouncementCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str | None = None


class AnnouncementUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    body: str | None = None
    active: bool | None = None


class AnnouncementOut(BaseModel):
    id: UUID
    title: str
    body: str | None
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
