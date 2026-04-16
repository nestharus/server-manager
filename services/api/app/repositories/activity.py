"""In-memory append-only stores for activity actions and state changes.

These implement the storage layer described in the Activity/Audit Model
proposal (sections 3 and hookpoints 2.1-2.2). Both stores are append-only:
no update or delete operations exist.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.contracts.activity import ActionRecord, ActionStatus, StateChangeRecord


class InMemoryActionStore:
    def __init__(self) -> None:
        self._records: list[ActionRecord] = []
        self._next_id = 1

    def append(
        self,
        *,
        action_type: str,
        aggregate_type: str,
        aggregate_id: int,
        actor_kind: str,
        actor_id: str,
        request_surface: str,
        request_json: dict[str, Any],
        status: str,
        reason_text: str | None = None,
    ) -> ActionRecord:
        record = ActionRecord(
            id=self._next_id,
            action_type=action_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            actor_kind=actor_kind,
            actor_id=actor_id,
            request_surface=request_surface,
            request_json=request_json,
            status=ActionStatus(status),
            reason_text=reason_text,
            recorded_at=datetime.now(timezone.utc),
        )
        self._records.append(record)
        self._next_id += 1
        return record

    def list_by_aggregate(
        self, aggregate_type: str, aggregate_id: int,
    ) -> list[ActionRecord]:
        return [
            r
            for r in self._records
            if r.aggregate_type == aggregate_type and r.aggregate_id == aggregate_id
        ]


class InMemoryStateChangeStore:
    def __init__(self) -> None:
        self._records: list[StateChangeRecord] = []
        self._next_id = 1
        self._seq_index: set[tuple[str, int, int]] = set()

    def append(
        self,
        *,
        action_id: int,
        aggregate_type: str,
        aggregate_id: int,
        aggregate_seq: int,
        change_type: str,
        payload_json: dict[str, Any],
        diff_json: dict[str, Any] | None = None,
    ) -> StateChangeRecord:
        key = (aggregate_type, aggregate_id, aggregate_seq)
        if key in self._seq_index:
            raise ValueError(
                f"Duplicate sequence {aggregate_seq} for "
                f"({aggregate_type}, {aggregate_id})"
            )

        record = StateChangeRecord(
            id=self._next_id,
            action_id=action_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            aggregate_seq=aggregate_seq,
            change_type=change_type,
            payload_json=payload_json,
            diff_json=diff_json,
            recorded_at=datetime.now(timezone.utc),
        )
        self._records.append(record)
        self._seq_index.add(key)
        self._next_id += 1
        return record

    def list_by_aggregate(
        self, aggregate_type: str, aggregate_id: int,
    ) -> list[StateChangeRecord]:
        return sorted(
            [
                r
                for r in self._records
                if r.aggregate_type == aggregate_type
                and r.aggregate_id == aggregate_id
            ],
            key=lambda r: r.aggregate_seq,
        )
