from __future__ import annotations

from typing import Any
from uuid import UUID

from app.contracts.applications_transcript import (
    ApplicationTranscriptEntry,
    ApplicationTranscriptMessageEntry,
    ApplicationTranscriptRead,
    ApplicationTranscriptStateChangeEntry,
)
from app.repositories.applications import ApplicationsRepository
from app.services.application_messages import ApplicationMessagesService


def _state_diff(row: dict[str, Any]) -> tuple[str | None, str | None]:
    diff_json = row.get("diff_json") or {}
    state_diff = diff_json.get("state") if isinstance(diff_json, dict) else None
    if not isinstance(state_diff, dict):
        return None, None
    return state_diff.get("old"), state_diff.get("new")


def _state_change_to_entry(row: dict[str, Any]) -> ApplicationTranscriptStateChangeEntry:
    from_state, to_state = _state_diff(row)
    return ApplicationTranscriptStateChangeEntry(
        occurred_at=row["recorded_at"],
        change_type=row["change_type"],
        from_state=from_state,
        to_state=to_state,
        actor_kind=row["actor_kind"],
        actor_id=row["actor_id"],
        aggregate_seq=int(row["aggregate_seq"]),
    )


def _message_to_entry(message: Any) -> ApplicationTranscriptMessageEntry:
    return ApplicationTranscriptMessageEntry(
        occurred_at=message.created_at,
        message_seq=message.message_seq,
        author_actor_kind=message.author_actor_kind,
        author_actor_id=message.author_actor_id,
        visibility=message.visibility,
        body_markdown=message.body_markdown,
    )


class ApplicationTranscriptService:
    def __init__(
        self,
        applications_repo: ApplicationsRepository,
        application_messages_service: ApplicationMessagesService,
    ) -> None:
        self._applications_repo = applications_repo
        self._application_messages_service = application_messages_service

    def read_application_transcript(
        self,
        *,
        application_id: UUID,
        viewer_actor_kind: str,
        viewer_actor_id: str,
    ) -> ApplicationTranscriptRead:
        messages = self._application_messages_service.read_application_messages(
            application_id=application_id,
            viewer_actor_kind=viewer_actor_kind,
            viewer_actor_id=viewer_actor_id,
        )
        state_change_rows = self._applications_repo.list_application_state_changes(
            application_id=application_id,
        )

        entries: list[ApplicationTranscriptEntry] = [
            *[_state_change_to_entry(row) for row in state_change_rows],
            *[_message_to_entry(message) for message in messages],
        ]
        entries.sort(key=lambda entry: entry.occurred_at)
        return ApplicationTranscriptRead(application_id=application_id, entries=entries)


__all__ = ["ApplicationTranscriptService"]
