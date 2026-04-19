from __future__ import annotations

from app.contracts.audit import AuditContextRead, AuditEntryRead, CorrelationHeadersRead
from app.repositories.audit import fetch_audit_entry
from app.repositories.db import PostgresDatabase


def get_audit_entry(db: PostgresDatabase, id: int) -> AuditEntryRead:
    with db.connection() as connection:
        row = fetch_audit_entry(connection, id)
    if row is None:
        raise LookupError(f"audit entry {id} was not found")

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
