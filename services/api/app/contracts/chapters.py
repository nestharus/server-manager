from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ChapterStatus(str, Enum):
    active = "active"
    archived = "archived"
    provisioning = "provisioning"


class ChapterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(max_length=50, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ChapterRead(BaseModel):
    id: int
    name: str
    slug: str
    status: ChapterStatus
    discord_category_id: int | None
    discord_officer_role_id: int | None
    discord_member_role_id: int | None
    created_at: datetime


class ChapterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    slug: str | None = Field(
        default=None,
        max_length=50,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    status: ChapterStatus | None = None
    discord_category_id: int | None = None
    discord_officer_role_id: int | None = None
    discord_member_role_id: int | None = None


__all__ = [
    "ChapterCreate",
    "ChapterRead",
    "ChapterStatus",
    "ChapterUpdate",
]
