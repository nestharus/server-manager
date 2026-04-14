"""Chapter business logic and audit hooks."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.contracts.chapters import ChapterCreate, ChapterResponse, ChapterUpdate
from app.repositories.chapter_repository import (
    AbstractChapterRepository,
    ChapterArchivedError,
    ChapterCreateRecord,
    ChapterNotFoundError,
    ChapterUpdateRecord,
    ChapterVersionConflictError,
    DuplicateChapterSlugError,
)

logger = logging.getLogger(__name__)


class AuditService:
    """Minimal audit stub for mutation logging until persistence lands."""

    async def log_mutation(
        self,
        action: str,
        *,
        chapter_id: UUID,
        payload: dict[str, Any],
    ) -> None:
        logger.info(
            "audit mutation action=%s chapter_id=%s payload=%s",
            action,
            chapter_id,
            payload,
        )


class ChapterService:
    """Application service for chapter CRUD behavior."""

    def __init__(
        self,
        repository: AbstractChapterRepository,
        audit_service: AuditService,
    ) -> None:
        self._repository = repository
        self._audit_service = audit_service

    async def create_chapter(
        self,
        body: ChapterCreate,
        *,
        created_by_discord_user_id: int = 0,  # TODO: inject from auth context when auth is wired
    ) -> ChapterResponse:
        record = await self._repository.create(
            ChapterCreateRecord(
                slug=body.slug,
                display_name=body.display_name,
                game=body.game,
                description=body.description,
                created_by_discord_user_id=created_by_discord_user_id,
            )
        )
        await self._audit_service.log_mutation(
            "chapter.create",
            chapter_id=record.id,
            payload=body.model_dump(),
        )
        return ChapterResponse.model_validate(record)

    async def list_chapters(self, *, include_archived: bool = False) -> list[ChapterResponse]:
        records = await self._repository.list(include_archived=include_archived)
        return [ChapterResponse.model_validate(record) for record in records]

    async def get_chapter(self, chapter_id: UUID) -> ChapterResponse:
        record = await self._repository.get_by_id(chapter_id)
        if record is None:
            raise ChapterNotFoundError(str(chapter_id))
        return ChapterResponse.model_validate(record)

    async def update_chapter(self, chapter_id: UUID, body: ChapterUpdate) -> ChapterResponse:
        record = await self._repository.update(
            chapter_id,
            expected_version=body.version,
            changes=ChapterUpdateRecord(
                display_name=body.display_name,
                game=body.game,
                description=body.description,
            ),
            fields_to_update=body.model_fields_set - {"version"},
        )
        await self._audit_service.log_mutation(
            "chapter.update",
            chapter_id=record.id,
            payload=body.model_dump(),
        )
        return ChapterResponse.model_validate(record)

    async def archive_chapter(self, chapter_id: UUID) -> ChapterResponse:
        record = await self._repository.archive(chapter_id)
        await self._audit_service.log_mutation(
            "chapter.archive",
            chapter_id=record.id,
            payload={},
        )
        return ChapterResponse.model_validate(record)


__all__ = [
    "AuditService",
    "ChapterArchivedError",
    "ChapterNotFoundError",
    "ChapterService",
    "ChapterVersionConflictError",
    "DuplicateChapterSlugError",
]
