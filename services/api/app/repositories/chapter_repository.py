"""Chapter repository interfaces and in-memory implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(slots=True)
class ChapterRecord:
    id: UUID
    slug: str
    display_name: str
    game: str
    description: str | None
    created_by_discord_user_id: int
    version: int
    created_at: datetime
    updated_at: datetime | None
    archived_at: datetime | None


@dataclass(slots=True)
class ChapterCreateRecord:
    slug: str
    display_name: str
    game: str
    description: str | None
    created_by_discord_user_id: int


@dataclass(slots=True)
class ChapterUpdateRecord:
    display_name: str | None = None
    game: str | None = None
    description: str | None = None


class ChapterRepositoryError(Exception):
    """Base exception for chapter repository failures."""


class ChapterNotFoundError(ChapterRepositoryError):
    """Raised when a chapter record does not exist."""


class DuplicateChapterSlugError(ChapterRepositoryError):
    """Raised when attempting to create a chapter with an existing slug."""


class ChapterVersionConflictError(ChapterRepositoryError):
    """Raised when optimistic locking rejects an update."""


class ChapterArchivedError(ChapterRepositoryError):
    """Raised when mutating an archived chapter."""


class AbstractChapterRepository(ABC):
    @abstractmethod
    async def create(self, chapter: ChapterCreateRecord) -> ChapterRecord:
        """Persist a new chapter."""

    @abstractmethod
    async def list(self, *, include_archived: bool = False) -> list[ChapterRecord]:
        """Return chapters, optionally including archived rows."""

    @abstractmethod
    async def get_by_id(
        self,
        chapter_id: UUID,
        *,
        include_archived: bool = False,
    ) -> ChapterRecord | None:
        """Fetch a chapter by ID."""

    @abstractmethod
    async def update(
        self,
        chapter_id: UUID,
        *,
        expected_version: int,
        changes: ChapterUpdateRecord,
        fields_to_update: set[str],
    ) -> ChapterRecord:
        """Apply an optimistic-locking update. Only fields in fields_to_update are modified."""

    @abstractmethod
    async def archive(self, chapter_id: UUID) -> ChapterRecord:
        """Soft-delete a chapter."""


class InMemoryChapterRepository(AbstractChapterRepository):
    """Dict-backed repository implementation for tests and local wiring."""

    def __init__(self) -> None:
        self._chapters: dict[UUID, ChapterRecord] = {}
        self._slug_index: dict[str, UUID] = {}

    async def create(self, chapter: ChapterCreateRecord) -> ChapterRecord:
        if chapter.slug in self._slug_index:
            raise DuplicateChapterSlugError(chapter.slug)

        now = datetime.now(UTC)
        record = ChapterRecord(
            id=uuid4(),
            slug=chapter.slug,
            display_name=chapter.display_name,
            game=chapter.game,
            description=chapter.description,
            created_by_discord_user_id=chapter.created_by_discord_user_id,
            version=1,
            created_at=now,
            updated_at=None,
            archived_at=None,
        )
        self._chapters[record.id] = record
        self._slug_index[record.slug] = record.id
        return deepcopy(record)

    async def list(self, *, include_archived: bool = False) -> list[ChapterRecord]:
        records = [
            deepcopy(record)
            for record in self._chapters.values()
            if include_archived or record.archived_at is None
        ]
        return sorted(records, key=lambda record: (record.created_at, str(record.id)))

    async def get_by_id(
        self,
        chapter_id: UUID,
        *,
        include_archived: bool = False,
    ) -> ChapterRecord | None:
        record = self._chapters.get(chapter_id)
        if record is None:
            return None
        if not include_archived and record.archived_at is not None:
            return None
        return deepcopy(record)

    async def update(
        self,
        chapter_id: UUID,
        *,
        expected_version: int,
        changes: ChapterUpdateRecord,
        fields_to_update: set[str],
    ) -> ChapterRecord:
        record = self._chapters.get(chapter_id)
        if record is None:
            raise ChapterNotFoundError(str(chapter_id))
        if record.archived_at is not None:
            raise ChapterArchivedError(str(chapter_id))
        if record.version != expected_version:
            raise ChapterVersionConflictError(str(chapter_id))

        if "display_name" in fields_to_update and changes.display_name is not None:
            record.display_name = changes.display_name
        if "game" in fields_to_update and changes.game is not None:
            record.game = changes.game
        if "description" in fields_to_update:
            record.description = changes.description  # None is a valid value (clear)
        record.version += 1
        record.updated_at = datetime.now(UTC)
        return deepcopy(record)

    async def archive(self, chapter_id: UUID) -> ChapterRecord:
        record = self._chapters.get(chapter_id)
        if record is None:
            raise ChapterNotFoundError(str(chapter_id))
        if record.archived_at is not None:
            raise ChapterArchivedError(str(chapter_id))

        now = datetime.now(UTC)
        record.archived_at = now
        record.updated_at = now
        record.version += 1
        return deepcopy(record)
