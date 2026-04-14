from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Protocol

from app.contracts.chapters import ChapterStatus


class ChapterNotFoundError(Exception):
    def __init__(self, chapter_id: int) -> None:
        self.chapter_id = chapter_id
        super().__init__(f"Chapter {chapter_id} was not found")


class ChapterVersionConflictError(Exception):
    def __init__(self, chapter_id: int, expected_version: int, actual_version: int) -> None:
        self.chapter_id = chapter_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Chapter {chapter_id} version mismatch: "
            f"expected {expected_version}, found {actual_version}"
        )


@dataclass(slots=True, frozen=True)
class ChapterRecord:
    id: int
    name: str
    slug: str
    status: ChapterStatus
    discord_category_id: int | None
    discord_officer_role_id: int | None
    discord_member_role_id: int | None
    created_at: datetime
    version: int


class ChapterRepository(Protocol):
    def create(self, *, name: str, slug: str) -> ChapterRecord: ...

    def list(self) -> list[ChapterRecord]: ...

    def get(self, chapter_id: int) -> ChapterRecord | None: ...

    def update(
        self,
        chapter_id: int,
        *,
        expected_version: int,
        updates: dict[str, object],
    ) -> ChapterRecord: ...

    def archive(self, chapter_id: int) -> ChapterRecord: ...


class InMemoryChapterRepository:
    def __init__(self) -> None:
        self._chapters: dict[int, ChapterRecord] = {}
        self._next_id = 1

    def create(self, *, name: str, slug: str) -> ChapterRecord:
        chapter = ChapterRecord(
            id=self._next_id,
            name=name,
            slug=slug,
            status=ChapterStatus.provisioning,
            discord_category_id=None,
            discord_officer_role_id=None,
            discord_member_role_id=None,
            created_at=datetime.now(timezone.utc),
            version=0,
        )
        self._chapters[chapter.id] = chapter
        self._next_id += 1
        return chapter

    def list(self) -> list[ChapterRecord]:
        return [self._chapters[chapter_id] for chapter_id in sorted(self._chapters)]

    def get(self, chapter_id: int) -> ChapterRecord | None:
        return self._chapters.get(chapter_id)

    def update(
        self,
        chapter_id: int,
        *,
        expected_version: int,
        updates: dict[str, object],
    ) -> ChapterRecord:
        current = self._require_chapter(chapter_id)
        self._assert_version(current, expected_version)

        updated = replace(current, **updates, version=current.version + 1)
        self._chapters[chapter_id] = updated
        return updated

    def archive(self, chapter_id: int) -> ChapterRecord:
        current = self._require_chapter(chapter_id)
        updated = replace(
            current,
            status=ChapterStatus.archived,
            version=current.version + 1,
        )
        self._chapters[chapter_id] = updated
        return updated

    def _require_chapter(self, chapter_id: int) -> ChapterRecord:
        chapter = self._chapters.get(chapter_id)
        if chapter is None:
            raise ChapterNotFoundError(chapter_id)
        return chapter

    def _assert_version(self, chapter: ChapterRecord, expected_version: int) -> None:
        if chapter.version != expected_version:
            raise ChapterVersionConflictError(
                chapter.id,
                expected_version=expected_version,
                actual_version=chapter.version,
            )
