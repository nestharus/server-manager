from __future__ import annotations

from uuid import UUID

from app.contracts.audit import AUDIT_CHAIN_MAX_ROWS, AuditEntryListRead
from app.repositories.audit import AuditRepository
from app.services.audit import _build_audit_entry_read


class AuditChainTooLargeError(Exception):
    def __init__(self, correlation_id: UUID, row_count: int) -> None:
        self.correlation_id = correlation_id
        self.row_count = row_count
        super().__init__(
            f"audit chain for correlation {correlation_id} exceeds "
            f"{AUDIT_CHAIN_MAX_ROWS} rows ({row_count} rows found)"
        )


def _build_audit_entry_list(
    *,
    correlation_id: UUID,
    rows: list[dict],
) -> AuditEntryListRead:
    if len(rows) > AUDIT_CHAIN_MAX_ROWS:
        raise AuditChainTooLargeError(correlation_id, len(rows))

    items = [_build_audit_entry_read(row) for row in rows]
    return AuditEntryListRead(items=items, total=len(items))


class AuditQueriesService:
    def __init__(self, audit_repo: AuditRepository) -> None:
        self._audit_repo = audit_repo

    def get_audit_entries_by_correlation(
        self,
        correlation_id: UUID,
    ) -> AuditEntryListRead:
        rows = self._audit_repo.list_audit_entries_by_correlation(
            correlation_id=correlation_id,
            limit=AUDIT_CHAIN_MAX_ROWS + 1,
        )
        return _build_audit_entry_list(correlation_id=correlation_id, rows=rows)

    def get_audit_entry_chain(
        self,
        entry_id: int,
    ) -> AuditEntryListRead:
        row = self._audit_repo.fetch_audit_entry(entry_id)
        if row is None:
            raise LookupError(f"audit entry {entry_id} was not found")
        correlation_id = row["correlation_id"]
        rows = self._audit_repo.list_audit_entries_by_correlation(
            correlation_id=correlation_id,
            limit=AUDIT_CHAIN_MAX_ROWS + 1,
        )
        return _build_audit_entry_list(correlation_id=correlation_id, rows=rows)


__all__ = [
    "AuditChainTooLargeError",
    "AuditQueriesService",
]
