from __future__ import annotations

from typing import Any, Mapping

from app.contracts.audit import AuditContextRead, AuditEntryRead, CorrelationHeadersRead
from app.repositories.audit import AuditRepository


def _build_audit_entry_read(row: Mapping[str, Any]) -> AuditEntryRead:
    return AuditEntryRead(
        id=int(row["id"]),
        recorded_at=row["recorded_at"],
        actor_kind=str(row["actor_kind"]),
        actor_id=str(row["actor_id"]),
        action_type=str(row["action_type"]),
        aggregate_type=str(row["aggregate_type"]),
        aggregate_id=str(row["aggregate_id"]),
        status=str(row["status"]),
        correlation=AuditContextRead(
            correlation_id=row["correlation_id"],
            causation_id=row["causation_id"],
            headers=CorrelationHeadersRead(
                x_correlation_id=row["correlation_id"],
                x_causation_id=row["causation_id"],
            ),
        ),
        scope_kind=row["scope_kind"],
        scope_id=row["scope_id"],
        request_surface=str(row["request_surface"]),
        reason_text=row["reason_text"],
    )


class AuditService:
    def __init__(self, audit_repo: AuditRepository, mutations_callable) -> None:
        self._audit_repo = audit_repo
        self._mutations_callable = mutations_callable

    def get_audit_entry(self, id: int) -> AuditEntryRead:
        row = self._audit_repo.fetch_audit_entry(id)
        if row is None:
            raise LookupError(f"audit entry {id} was not found")

        return _build_audit_entry_read(row)
