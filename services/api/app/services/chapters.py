from __future__ import annotations

from enum import Enum
from typing import Any

from app.contracts.chapters import ChapterCreate, ChapterRead, ChapterUpdate
from app.repositories.activity import InMemoryActionStore, InMemoryStateChangeStore
from app.repositories.chapters import (
    ChapterNotFoundError,
    ChapterRecord,
    ChapterRepository,
    StalePreconditionError,
)


def _format_etag(seq: int) -> str:
    return f'"{seq}"'


def _record_to_payload(record: ChapterRecord) -> dict[str, Any]:
    return {
        "name": record.name,
        "slug": record.slug,
        "status": record.status.value,
        "discord_category_id": record.discord_category_id,
        "discord_officer_role_id": record.discord_officer_role_id,
        "discord_member_role_id": record.discord_member_role_id,
    }


def _compute_diff(
    old: ChapterRecord, new: ChapterRecord,
) -> dict[str, Any] | None:
    diff: dict[str, Any] = {}
    for field in (
        "name",
        "slug",
        "status",
        "discord_category_id",
        "discord_officer_role_id",
        "discord_member_role_id",
    ):
        old_val = getattr(old, field)
        new_val = getattr(new, field)
        if old_val != new_val:
            if isinstance(old_val, Enum):
                old_val = old_val.value
            if isinstance(new_val, Enum):
                new_val = new_val.value
            diff[field] = {"old": old_val, "new": new_val}
    return diff if diff else None


class ChapterService:
    def __init__(
        self,
        repository: ChapterRepository,
        action_store: InMemoryActionStore,
        state_change_store: InMemoryStateChangeStore,
    ) -> None:
        self._repository = repository
        self._action_store = action_store
        self._state_change_store = state_change_store
        self._heads: dict[int, int] = {}

    def create_chapter(self, chapter: ChapterCreate) -> tuple[ChapterRead, str]:
        created = self._repository.create(name=chapter.name, slug=chapter.slug)

        action = self._action_store.append(
            action_type="chapter.create",
            aggregate_type="chapter",
            aggregate_id=created.id,
            actor_kind="system",
            actor_id="system",
            request_surface="api:/api/v1/chapters",
            request_json={"name": chapter.name, "slug": chapter.slug},
            status="accepted",
        )

        new_seq = 1
        self._state_change_store.append(
            action_id=action.id,
            aggregate_type="chapter",
            aggregate_id=created.id,
            aggregate_seq=new_seq,
            change_type="chapter.created",
            payload_json=_record_to_payload(created),
            diff_json=None,
        )

        self._heads[created.id] = new_seq
        return self._to_read(created), _format_etag(new_seq)

    def list_chapters(self) -> list[ChapterRead]:
        return [self._to_read(chapter) for chapter in self._repository.list()]

    def get_chapter(self, chapter_id: int) -> tuple[ChapterRead, str]:
        chapter = self._repository.get(chapter_id)
        if chapter is None:
            raise ChapterNotFoundError(chapter_id)
        seq = self._heads.get(chapter_id, 1)
        return self._to_read(chapter), _format_etag(seq)

    def update_chapter(
        self,
        chapter_id: int,
        chapter: ChapterUpdate,
        *,
        expected_head: str,
    ) -> tuple[ChapterRead, str]:
        self._check_precondition(chapter_id, expected_head)

        old_record = self._repository.get(chapter_id)
        if old_record is None:
            raise ChapterNotFoundError(chapter_id)

        updates = chapter.model_dump(exclude_unset=True)
        updated = self._repository.update(chapter_id, updates=updates)

        current_seq = self._heads[chapter_id]
        new_seq = current_seq + 1

        action = self._action_store.append(
            action_type="chapter.update",
            aggregate_type="chapter",
            aggregate_id=chapter_id,
            actor_kind="system",
            actor_id="system",
            request_surface=f"api:/api/v1/chapters/{chapter_id}",
            request_json=updates,
            status="accepted",
        )

        self._state_change_store.append(
            action_id=action.id,
            aggregate_type="chapter",
            aggregate_id=chapter_id,
            aggregate_seq=new_seq,
            change_type="chapter.updated",
            payload_json=_record_to_payload(updated),
            diff_json=_compute_diff(old_record, updated),
        )

        self._heads[chapter_id] = new_seq
        return self._to_read(updated), _format_etag(new_seq)

    def archive_chapter(
        self,
        chapter_id: int,
        *,
        expected_head: str,
    ) -> tuple[ChapterRead, str]:
        self._check_precondition(chapter_id, expected_head)

        old_record = self._repository.get(chapter_id)
        if old_record is None:
            raise ChapterNotFoundError(chapter_id)

        archived = self._repository.archive(chapter_id)

        current_seq = self._heads[chapter_id]
        new_seq = current_seq + 1

        action = self._action_store.append(
            action_type="chapter.archive",
            aggregate_type="chapter",
            aggregate_id=chapter_id,
            actor_kind="system",
            actor_id="system",
            request_surface=f"api:/api/v1/chapters/{chapter_id}/archive",
            request_json={},
            status="accepted",
        )

        self._state_change_store.append(
            action_id=action.id,
            aggregate_type="chapter",
            aggregate_id=chapter_id,
            aggregate_seq=new_seq,
            change_type="chapter.archived",
            payload_json=_record_to_payload(archived),
            diff_json=_compute_diff(old_record, archived),
        )

        self._heads[chapter_id] = new_seq
        return self._to_read(archived), _format_etag(new_seq)

    def _check_precondition(self, chapter_id: int, expected_head: str) -> None:
        current_seq = self._heads.get(chapter_id)
        if current_seq is None:
            raise ChapterNotFoundError(chapter_id)
        if _format_etag(current_seq) != expected_head:
            raise StalePreconditionError("chapter", chapter_id)

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
        )
