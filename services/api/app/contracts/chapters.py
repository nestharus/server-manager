"""Chapter contracts.

Defines the API boundary for chapter CRUD operations. Chapters are the
top-level organizational unit — each chapter has its own roles,
channels, forms, activity rules, and member roster.
"""

from __future__ import annotations

import datetime
from uuid import UUID

from pydantic import Field

from app.contracts.base import BaseContract, SoftDeleteMixin, TimestampMixin, VersionedMixin


class ChapterCreate(BaseContract):
    """Request body for creating a new chapter."""

    slug: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9-]+$")
    display_name: str = Field(min_length=1, max_length=100)
    game: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)


class ChapterUpdate(BaseContract):
    """Request body for updating a chapter. Requires version for optimistic locking."""

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    game: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    version: int


class ChapterResponse(BaseContract, VersionedMixin, TimestampMixin, SoftDeleteMixin):
    """Response body for a chapter."""

    id: UUID
    slug: str
    display_name: str
    game: str
    description: str | None
    created_by_discord_user_id: int


class ChapterListResponse(BaseContract):
    """Paginated list of chapters."""

    items: list[ChapterResponse]
    total: int
