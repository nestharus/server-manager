from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class _ChapterRoleModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChapterRoleRead(_ChapterRoleModel):
    id: UUID
    chapter_id: str = Field(min_length=1)
    template_id: UUID | None = None
    name: str = Field(min_length=1)
    ordinal: int = Field(ge=0)
    triggers_succession: bool
    created_at: datetime


class ChapterRoleCreate(_ChapterRoleModel):
    chapter_id: str = Field(min_length=1)
    template_id: UUID | None = None
    name: str = Field(min_length=1)
    ordinal: int = Field(ge=0)
    triggers_succession: bool


__all__ = ["ChapterRoleCreate", "ChapterRoleRead"]
