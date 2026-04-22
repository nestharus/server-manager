from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.rows import dict_row

from app.contracts.actor import ActorIdentity
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.contracts.permissions import (
    ChannelRolePermissionSnapshotEntry,
    GuildRolePermissionSnapshotEntry,
    PermissionReconciliationRunCreate,
    PermissionReconciliationRunRead,
    PermissionSnapshotEntry,
)
from app.repositories import permissions as permission_repo
from app.repositories.db import PostgresDatabase
from app.services.mutations import mutate_entity
from app.services.permissions import _require_scoped_authority


VALID_RUN_TRANSITIONS: dict[tuple[str, str], str] = {
    ("requested", "submit_snapshot"): "snapshot_submitted",
    ("snapshot_submitted", "reconcile"): "reconciled",
    ("snapshot_submitted", "fail"): "failed",
    ("requested", "fail"): "failed",
}

RUN_TERMINAL_STATUSES = frozenset({"reconciled", "failed"})

RUN_CREATE_PAYLOAD_ALLOWLIST: set[str] = {
    "scope_kind",
    "scope_id",
    "originating_actor_kind",
    "originating_actor_id",
}

RUN_ADVANCE_PAYLOAD_ALLOWLIST: dict[str, set[str]] = {
    "submit_snapshot": {"entry_count"},
    "reconcile": {"drift_count"},
    "fail": {"failure_reason"},
}

RUN_ACTION_TYPE: dict[str, str] = {
    "create": "permission_reconciliation_run.create",
    "submit_snapshot": "permission_reconciliation_run.submit_snapshot",
    "reconcile": "permission_reconciliation_run.reconcile",
    "fail": "permission_reconciliation_run.fail",
}

RUN_CHANGE_TYPE: dict[str, str] = {
    "create": "permission_reconciliation_run.created",
    "submit_snapshot": "permission_reconciliation_run.snapshot_submitted",
    "reconcile": "permission_reconciliation_run.reconciled",
    "fail": "permission_reconciliation_run.failed",
}

DRIFT_CREATE_PAYLOAD_ALLOWLIST: set[str] = {
    "drift_id",
    "reconciliation_run_id",
    "permission_intent_id",
    "intent_version",
    "scope_kind",
    "scope_id",
    "role_id",
    "channel_id",
    "kind",
    "status",
}


class ReconciliationRunNotFoundError(LookupError):
    def __init__(self, run_id: UUID) -> None:
        self.run_id = run_id
        super().__init__(f"permission reconciliation run {run_id} was not found")


class ReconciliationRunConflictError(Exception):
    def __init__(self, *, run_id: UUID, status: str) -> None:
        super().__init__(f"run {run_id} in status {status}")
        self.run_id = run_id
        self.status = status


def _current_time() -> datetime:
    return datetime.now(UTC)


def _requested_by(
    actor: ActorIdentity,
    request: PermissionReconciliationRunCreate,
) -> tuple[str, str]:
    if (
        actor.actor_kind == "service"
        and request.originating_actor_kind
        and request.originating_actor_id
    ):
        return request.originating_actor_kind, request.originating_actor_id
    return actor.actor_kind, actor.actor_id


def _make_request(
    *,
    expected_version: int,
    actor: ActorIdentity,
    request_surface: str,
    reason_text: str | None = None,
) -> MutationRequest:
    return MutationRequest(
        expected_version=expected_version,
        actor_kind=actor.actor_kind,
        actor_id=actor.actor_id,
        reason_text=reason_text,
        request_surface=request_surface,
    )


def _read_head_version(db: PostgresDatabase, run_id: UUID) -> int:
    with db.connection() as connection:
        row = connection.execute(
            """
            SELECT current_seq FROM aggregate_heads
             WHERE aggregate_type = 'permission_reconciliation_run'
               AND aggregate_id = %s
            """,
            (str(run_id),),
        ).fetchone()
    if row is None:
        raise ReconciliationRunNotFoundError(run_id)
    return int(row[0])


def create_reconciliation_run(
    db: PostgresDatabase,
    *,
    request: PermissionReconciliationRunCreate,
    actor: ActorIdentity,
) -> tuple[PermissionReconciliationRunRead, MutationResult]:
    _require_scoped_authority(
        "permission_reconciliation_run.write",
        scope_kind=request.scope_kind,
        scope_id=request.scope_id,
        actor=actor,
        db=db,
    )

    run_id = uuid4()
    requested_by_kind, requested_by_id = _requested_by(actor, request)
    aggregate_id = str(run_id)

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        permission_repo.insert_reconciliation_run(
            connection,
            row={
                "id": run_id,
                "scope_kind": request.scope_kind,
                "scope_id": request.scope_id,
                "requested_by_kind": requested_by_kind,
                "requested_by_id": requested_by_id,
            },
        )
        return StateChangeDraft(
            change_type=RUN_CHANGE_TYPE["create"],
            payload_json={
                "status": "requested",
                "scope_kind": request.scope_kind,
                "scope_id": request.scope_id,
                "requested_by_kind": requested_by_kind,
                "requested_by_id": requested_by_id,
            },
        )

    result = mutate_entity(
        db=db,
        aggregate_type="permission_reconciliation_run",
        aggregate_id=aggregate_id,
        request=_make_request(
            expected_version=0,
            actor=actor,
            request_surface="api:/api/v1/permission-reconciliation/runs",
        ),
        action_type=RUN_ACTION_TYPE["create"],
        action_payload={
            "scope_kind": request.scope_kind,
            "scope_id": request.scope_id,
            "originating_actor_kind": request.originating_actor_kind,
            "originating_actor_id": request.originating_actor_id,
        },
        payload_allowlist=RUN_CREATE_PAYLOAD_ALLOWLIST,
        mutate_projection=mutate_projection,
        scope_kind=request.scope_kind,
        scope_id=request.scope_id,
    )
    return read_reconciliation_run(db, run_id), result


def read_reconciliation_run(
    db: PostgresDatabase,
    run_id: UUID,
) -> PermissionReconciliationRunRead:
    with db.connection() as connection:
        row = permission_repo.fetch_reconciliation_run(connection, run_id)
        if row is None:
            raise ReconciliationRunNotFoundError(run_id)
        drift_ids = permission_repo.list_drift_ids_by_run(connection, run_id)
    payload = dict(row)
    payload["drift_ids"] = drift_ids
    return PermissionReconciliationRunRead.model_validate(payload)


def _advance_run_submit(
    connection: Connection[Any],
    *,
    run_id: UUID,
    actor: ActorIdentity,
    entry_count: int,
    expected_version: int,
) -> None:
    now = _current_time()

    def mutate_projection(active_connection: Connection[Any]) -> StateChangeDraft:
        permission_repo.update_reconciliation_run_status(
            active_connection,
            run_id=run_id,
            status="snapshot_submitted",
            snapshot_submitted_at=now,
        )
        return StateChangeDraft(
            change_type=RUN_CHANGE_TYPE["submit_snapshot"],
            payload_json={
                "status": "snapshot_submitted",
                "snapshot_submitted_at": now.isoformat(),
                "entry_count": entry_count,
            },
            diff_json={"from": "requested", "to": "snapshot_submitted"},
        )

    mutate_entity(
        db=None,  # type: ignore[arg-type]
        aggregate_type="permission_reconciliation_run",
        aggregate_id=str(run_id),
        request=_make_request(
            expected_version=expected_version,
            actor=actor,
            request_surface=(
                f"api:/api/v1/permission-reconciliation/runs/{run_id}/snapshots"
            ),
        ),
        action_type=RUN_ACTION_TYPE["submit_snapshot"],
        action_payload={"entry_count": entry_count},
        payload_allowlist=RUN_ADVANCE_PAYLOAD_ALLOWLIST["submit_snapshot"],
        mutate_projection=mutate_projection,
        scope_kind=None,
        scope_id=None,
        connection=connection,
    )


def _advance_run_reconciled(
    connection: Connection[Any],
    *,
    run_id: UUID,
    actor: ActorIdentity,
    drift_ids: list[UUID],
    expected_version: int,
) -> None:
    now = _current_time()

    def mutate_projection(active_connection: Connection[Any]) -> StateChangeDraft:
        permission_repo.update_reconciliation_run_status(
            active_connection,
            run_id=run_id,
            status="reconciled",
            reconciled_at=now,
        )
        return StateChangeDraft(
            change_type=RUN_CHANGE_TYPE["reconcile"],
            payload_json={
                "status": "reconciled",
                "reconciled_at": now.isoformat(),
                "drift_count": len(drift_ids),
                "drift_ids": [str(d) for d in drift_ids],
            },
            diff_json={"from": "snapshot_submitted", "to": "reconciled"},
        )

    mutate_entity(
        db=None,  # type: ignore[arg-type]
        aggregate_type="permission_reconciliation_run",
        aggregate_id=str(run_id),
        request=_make_request(
            expected_version=expected_version,
            actor=actor,
            request_surface=(
                f"api:/api/v1/permission-reconciliation/runs/{run_id}/snapshots"
            ),
        ),
        action_type=RUN_ACTION_TYPE["reconcile"],
        action_payload={"drift_count": len(drift_ids)},
        payload_allowlist=RUN_ADVANCE_PAYLOAD_ALLOWLIST["reconcile"],
        mutate_projection=mutate_projection,
        scope_kind=None,
        scope_id=None,
        connection=connection,
    )


def _advance_run_failed(
    db: PostgresDatabase,
    *,
    run_id: UUID,
    actor: ActorIdentity,
    failure_reason: str,
) -> None:
    now = _current_time()
    current = read_reconciliation_run(db, run_id)
    prior_status = current.status
    if prior_status not in ("requested", "snapshot_submitted"):
        return
    expected_version = _read_head_version(db, run_id)
    snapshot_submitted_override = (
        now if current.snapshot_submitted_at is None else None
    )

    def mutate_projection(active_connection: Connection[Any]) -> StateChangeDraft:
        permission_repo.update_reconciliation_run_status(
            active_connection,
            run_id=run_id,
            status="failed",
            snapshot_submitted_at=snapshot_submitted_override,
            failed_at=now,
            failure_reason=failure_reason,
        )
        return StateChangeDraft(
            change_type=RUN_CHANGE_TYPE["fail"],
            payload_json={
                "status": "failed",
                "failed_at": now.isoformat(),
                "failure_reason": failure_reason,
            },
            diff_json={"from": prior_status, "to": "failed"},
        )

    mutate_entity(
        db=db,
        aggregate_type="permission_reconciliation_run",
        aggregate_id=str(run_id),
        request=_make_request(
            expected_version=expected_version,
            actor=actor,
            request_surface=(
                f"api:/api/v1/permission-reconciliation/runs/{run_id}/snapshots"
            ),
        ),
        action_type=RUN_ACTION_TYPE["fail"],
        action_payload={"failure_reason": failure_reason},
        payload_allowlist=RUN_ADVANCE_PAYLOAD_ALLOWLIST["fail"],
        mutate_projection=mutate_projection,
        scope_kind=None,
        scope_id=None,
    )


def _entry_channel_id(entry: PermissionSnapshotEntry) -> str | None:
    return getattr(entry, "channel_id", None)


def _entry_masks(entry: PermissionSnapshotEntry) -> dict[str, str | None]:
    if isinstance(entry, GuildRolePermissionSnapshotEntry):
        return {
            "actual_bits": entry.permission_bits,
            "actual_allow_bits": None,
            "actual_deny_bits": None,
        }
    if isinstance(entry, ChannelRolePermissionSnapshotEntry):
        return {
            "actual_bits": None,
            "actual_allow_bits": entry.allow_bits,
            "actual_deny_bits": entry.deny_bits,
        }
    raise TypeError(f"unknown snapshot entry kind: {type(entry)!r}")


def _intent_masks(intent: dict[str, Any]) -> dict[str, str | None]:
    if intent["kind"] == "guild_role":
        return {
            "intended_bits": intent.get("permission_bits"),
            "intended_allow_bits": None,
            "intended_deny_bits": None,
        }
    return {
        "intended_bits": None,
        "intended_allow_bits": intent.get("allow_bits"),
        "intended_deny_bits": intent.get("deny_bits"),
    }


def _cleared_actual_masks(kind: str) -> dict[str, str | None]:
    if kind == "guild_role":
        return {
            "actual_bits": "0",
            "actual_allow_bits": None,
            "actual_deny_bits": None,
        }
    return {
        "actual_bits": None,
        "actual_allow_bits": "0",
        "actual_deny_bits": "0",
    }


def _masks_equal(
    intent_masks: dict[str, str | None],
    entry_masks: dict[str, str | None],
) -> bool:
    return (
        intent_masks.get("intended_bits") == entry_masks.get("actual_bits")
        and intent_masks.get("intended_allow_bits")
        == entry_masks.get("actual_allow_bits")
        and intent_masks.get("intended_deny_bits")
        == entry_masks.get("actual_deny_bits")
    )


def _intent_head_version(
    connection: Connection[Any],
    *,
    scope_kind: str,
    scope_id: str | None,
    role_id: str,
    channel_id: str | None,
) -> int:
    from app.contracts.base import AGGREGATE_SCOPE_MISSING
    from app.services.permissions import build_permission_intent_aggregate_id

    aggregate_id = build_permission_intent_aggregate_id(
        scope_kind=scope_kind,
        scope_id=scope_id,
        role_id=role_id,
        channel_id=channel_id,
    )
    _ = AGGREGATE_SCOPE_MISSING
    with connection.cursor(row_factory=dict_row) as cursor:
        row = cursor.execute(
            """
            SELECT current_seq FROM aggregate_heads
             WHERE aggregate_type = 'permission_intent'
               AND aggregate_id = %s
            """,
            (aggregate_id,),
        ).fetchone()
    if row is None:
        return 0
    return int(row["current_seq"])


def _build_drift_rows(
    connection: Connection[Any],
    *,
    run: PermissionReconciliationRunRead,
    entries: list[PermissionSnapshotEntry],
) -> list[dict[str, Any]]:
    intents = permission_repo.list_permission_intents(
        connection,
        scope_kind=run.scope_kind,
        scope_id=run.scope_id,
        include_expired=False,
    )
    intent_by_key: dict[tuple[str, str, str | None], dict[str, Any]] = {}
    for intent in intents:
        key = (intent["kind"], intent["role_id"], intent.get("channel_id"))
        intent_by_key[key] = intent

    snapshot_by_key: dict[tuple[str, str, str | None], PermissionSnapshotEntry] = {}
    for entry in entries:
        key = (entry.kind, entry.role_id, _entry_channel_id(entry))
        snapshot_by_key[key] = entry

    all_keys = sorted(
        set(intent_by_key.keys()) | set(snapshot_by_key.keys()),
        key=lambda k: (k[0], k[1], k[2] or ""),
    )

    rows: list[dict[str, Any]] = []
    for key in all_keys:
        kind, role_id, channel_id = key
        intent = intent_by_key.get(key)
        entry = snapshot_by_key.get(key)

        if intent is not None and entry is not None:
            intent_masks = _intent_masks(intent)
            entry_masks = _entry_masks(entry)
            if _masks_equal(intent_masks, entry_masks):
                continue
            intent_version = _intent_head_version(
                connection,
                scope_kind=run.scope_kind,
                scope_id=run.scope_id,
                role_id=role_id,
                channel_id=channel_id,
            )
            rows.append(
                {
                    "id": uuid4(),
                    "permission_intent_id": intent["id"],
                    "intent_version": intent_version,
                    "scope_kind": run.scope_kind,
                    "scope_id": run.scope_id,
                    "role_id": role_id,
                    "channel_id": channel_id,
                    "kind": kind,
                    "reconciliation_run_id": run.id,
                    **intent_masks,
                    **entry_masks,
                    "status": "detected",
                }
            )
        elif intent is not None and entry is None:
            intent_masks = _intent_masks(intent)
            cleared = _cleared_actual_masks(kind)
            intent_version = _intent_head_version(
                connection,
                scope_kind=run.scope_kind,
                scope_id=run.scope_id,
                role_id=role_id,
                channel_id=channel_id,
            )
            rows.append(
                {
                    "id": uuid4(),
                    "permission_intent_id": intent["id"],
                    "intent_version": intent_version,
                    "scope_kind": run.scope_kind,
                    "scope_id": run.scope_id,
                    "role_id": role_id,
                    "channel_id": channel_id,
                    "kind": kind,
                    "reconciliation_run_id": run.id,
                    **intent_masks,
                    **cleared,
                    "status": "detected",
                }
            )
        else:
            # entry-only
            entry_masks = _entry_masks(entry)  # type: ignore[arg-type]
            rows.append(
                {
                    "id": uuid4(),
                    "permission_intent_id": None,
                    "intent_version": None,
                    "scope_kind": run.scope_kind,
                    "scope_id": run.scope_id,
                    "role_id": role_id,
                    "channel_id": channel_id,
                    "kind": kind,
                    "reconciliation_run_id": run.id,
                    "intended_bits": None,
                    "intended_allow_bits": None,
                    "intended_deny_bits": None,
                    **entry_masks,
                    "status": "detected",
                }
            )
    return rows


def _drift_row_by_id(
    drift_rows: list[dict[str, Any]],
    drift_id: UUID,
) -> dict[str, Any]:
    for row in drift_rows:
        if row["id"] == drift_id:
            return row
    raise LookupError(f"drift row {drift_id} not found in batch")


def _record_drift_created(
    connection: Connection[Any],
    *,
    drift_id: UUID,
    drift_row: dict[str, Any],
    actor: ActorIdentity,
) -> None:
    action_payload = {
        "drift_id": str(drift_id),
        "reconciliation_run_id": (
            None
            if drift_row["reconciliation_run_id"] is None
            else str(drift_row["reconciliation_run_id"])
        ),
        "permission_intent_id": (
            None
            if drift_row["permission_intent_id"] is None
            else str(drift_row["permission_intent_id"])
        ),
        "intent_version": drift_row["intent_version"],
        "scope_kind": drift_row["scope_kind"],
        "scope_id": drift_row["scope_id"],
        "role_id": drift_row["role_id"],
        "channel_id": drift_row["channel_id"],
        "kind": drift_row["kind"],
        "status": drift_row["status"],
    }

    def mutate_projection(active_connection: Connection[Any]) -> StateChangeDraft:
        return StateChangeDraft(
            change_type="permission_drift.created",
            payload_json={
                **action_payload,
                "actual_bits": drift_row.get("actual_bits"),
                "actual_allow_bits": drift_row.get("actual_allow_bits"),
                "actual_deny_bits": drift_row.get("actual_deny_bits"),
                "intended_bits": drift_row.get("intended_bits"),
                "intended_allow_bits": drift_row.get("intended_allow_bits"),
                "intended_deny_bits": drift_row.get("intended_deny_bits"),
            },
        )

    mutate_entity(
        db=None,  # type: ignore[arg-type]
        aggregate_type="permission_drift",
        aggregate_id=str(drift_id),
        request=_make_request(
            expected_version=0,
            actor=actor,
            request_surface="service:permission_reconciliation._record_drift_created",
        ),
        action_type="permission_drift.create",
        action_payload=action_payload,
        payload_allowlist=DRIFT_CREATE_PAYLOAD_ALLOWLIST,
        mutate_projection=mutate_projection,
        scope_kind=drift_row["scope_kind"],
        scope_id=drift_row["scope_id"],
        connection=connection,
    )


def submit_reconciliation_snapshot(
    db: PostgresDatabase,
    *,
    run_id: UUID,
    entries: list[PermissionSnapshotEntry],
    actor: ActorIdentity,
) -> tuple[PermissionReconciliationRunRead, MutationResult]:
    existing = read_reconciliation_run(db, run_id)

    _require_scoped_authority(
        "permission_reconciliation_run.write",
        scope_kind=existing.scope_kind,
        scope_id=existing.scope_id,
        actor=actor,
        db=db,
    )

    if existing.status in RUN_TERMINAL_STATUSES:
        if existing.status == "reconciled":
            head_version = _read_head_version(db, run_id)
            return existing, MutationResult(
                version=head_version,
                etag=f'"{head_version}"',
            )
        raise ReconciliationRunConflictError(
            run_id=run_id, status=existing.status,
        )
    if existing.status != "requested":
        raise ReconciliationRunConflictError(
            run_id=run_id, status=existing.status,
        )

    try:
        with db.transaction() as connection:
            submit_expected = _read_head_version(db, run_id)
            _advance_run_submit(
                connection,
                run_id=run_id,
                actor=actor,
                entry_count=len(entries),
                expected_version=submit_expected,
            )
            drift_rows = _build_drift_rows(
                connection, run=existing, entries=entries,
            )
            new_drift_ids = permission_repo.insert_permission_drift_batch(
                connection, rows=drift_rows,
            )
            for drift_id in new_drift_ids:
                _record_drift_created(
                    connection,
                    drift_id=drift_id,
                    drift_row=_drift_row_by_id(drift_rows, drift_id),
                    actor=actor,
                )
            run_drift_ids = permission_repo.list_drift_ids_by_run(
                connection, run_id,
            )
            reconcile_expected = submit_expected + 1
            _advance_run_reconciled(
                connection,
                run_id=run_id,
                actor=actor,
                drift_ids=run_drift_ids,
                expected_version=reconcile_expected,
            )
    except Exception as error:
        _advance_run_failed(
            db,
            run_id=run_id,
            actor=actor,
            failure_reason=repr(error)[:500],
        )
        raise

    head_version = _read_head_version(db, run_id)
    return read_reconciliation_run(db, run_id), MutationResult(
        version=head_version,
        etag=f'"{head_version}"',
    )
