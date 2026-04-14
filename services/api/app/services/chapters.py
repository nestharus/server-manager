from __future__ import annotations

from app.contracts.chapters import ChapterCreate, ChapterRead, ChapterUpdate
from app.repositories.chapters import ChapterNotFoundError, ChapterRecord, ChapterRepository


class ChapterService:
    def __init__(self, repository: ChapterRepository) -> None:
        self._repository = repository

    def create_chapter(self, chapter: ChapterCreate) -> ChapterRead:
        created = self._repository.create(name=chapter.name, slug=chapter.slug)
        return self._to_read(created)

    def list_chapters(self) -> list[ChapterRead]:
        return [self._to_read(chapter) for chapter in self._repository.list()]

    def get_chapter(self, chapter_id: int) -> ChapterRead:
        chapter = self._repository.get(chapter_id)
        if chapter is None:
            raise ChapterNotFoundError(chapter_id)
        return self._to_read(chapter)

    def update_chapter(self, chapter_id: int, chapter: ChapterUpdate) -> ChapterRead:
        updates = chapter.model_dump(exclude={"version"}, exclude_unset=True)
        updated = self._repository.update(
            chapter_id,
            expected_version=chapter.version,
            updates=updates,
        )
        return self._to_read(updated)

    def archive_chapter(self, chapter_id: int) -> ChapterRead:
        archived = self._repository.archive(chapter_id)
        return self._to_read(archived)

    def _to_read(self, chapter: ChapterRecord) -> ChapterRead:
        return ChapterRead(
            id=chapter.id,
            name=chapter.name,
            slug=chapter.slug,
            status=chapter.status,
            discord_category_id=chapter.discord_category_id,
            discord_officer_role_id=chapter.discord_officer_role_id,
            discord_member_role_id=chapter.discord_member_role_id,
            created_at=chapter.created_at,
            version=chapter.version,
        )
