from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection

from app.contracts.base import AGGREGATE_SCOPE_MISSING, validated_update
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.contracts.permissions import (
    PermissionDriftRead,
    PermissionIntentCreate,
    PermissionIntentRead,
    PermissionIntentUpdate,
)
from app.repositories.db import PostgresDatabase
from app.repositories.permissions import (
    fetch_permission_drift,
    fetch_permission_intent,
    insert_permission_drift,
    insert_permission_intent,
    update_permission_drift_status as update_permission_drift_status_row,
    update_permission_intent_row,
)
from app.services.mutations import mutate_entity


def build_permission_intent_aggregate_id(
    *,
    scope_kind: str,
    scope_id: str | None,
    role_id: str,
    channel_id: str | None,
) -> str:
    return (
        f"permission_intent|{scope_kind}"
        f"|{scope_id if scope_id is not None else AGGREGATE_SCOPE_MISSING}"
        f"|role:{role_id}"
        f"|channel:{channel_id if channel_id is not None else AGGREGATE_SCOPE_MISSING}"
    )


def _make_request(
    *,
    expected_version: int,
    request_surface: str,
) -> MutationRequest:
    return MutationRequest(
        expected_version=expected_version,
        actor_kind="system",
        actor_id="permissions-service",
        reason_text=None,
        request_surface=request_surface,
    )


def _to_permission_intent_row(model: Any) -> dict[str, Any]:
    data = model.model_dump(mode="python")
    data["permission_bits"] = (
        None if data.get("permission_bits") is None else int(data["permission_bits"])
    )
    data["allow_bits"] = (
        None if data.get("allow_bits") is None else int(data["allow_bits"])
    )
    data["deny_bits"] = (
        None if data.get("deny_bits") is None else int(data["deny_bits"])
    )
    return data


def _to_permission_drift_row(model: PermissionDriftRead) -> dict[str, Any]:
    data = model.model_dump(mode="python")
    for field in (
        "actual_bits",
        "actual_allow_bits",
        "actual_deny_bits",
        "intended_bits",
        "intended_allow_bits",
        "intended_deny_bits",
    ):
        data[field] = None if data.get(field) is None else int(data[field])
    return data


def _fetch_current_version(
    connection: Connection[Any],
    *,
    aggregate_type: str,
    aggregate_id: str,
) -> int | None:
    row = connection.execute(
        """
        SELECT current_seq
        FROM aggregate_heads
        WHERE aggregate_type = %s AND aggregate_id = %s
        """,
        (aggregate_type, aggregate_id),
    ).fetchone()
    if row is None:
        return None
    return int(row[0])


def create_permission_intent(
    db: PostgresDatabase,
    request: Any,
) -> MutationResult:
    intent_id = uuid4()
    aggregate_id = build_permission_intent_aggregate_id(
        scope_kind=request.scope_kind,
        scope_id=request.scope_id,
        role_id=request.role_id,
        channel_id=getattr(request, "channel_id", None),
    )

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        row = _to_permission_intent_row(
            PermissionIntentRead.model_validate(
                {"id": intent_id, **request.model_dump(mode="python")}
            )
        )
        insert_permission_intent(connection, row=row)
        payload = PermissionIntentRead.model_validate(
            {"id": intent_id, **request.model_dump(mode="python")}
        ).model_dump(mode="json")
        return StateChangeDraft(
            change_type="permission_intent.created",
            payload_json=payload,
        )

    return mutate_entity(
        db=db,
        aggregate_type="permission_intent",
        aggregate_id=aggregate_id,
        request=_make_request(
            expected_version=0,
            request_surface="service:permissions.create_permission_intent",
        ),
        action_type="permission_intent.create",
        action_payload=request.model_dump(mode="json"),
        payload_allowlist=set(request.model_dump().keys()),
        mutate_projection=mutate_projection,
        scope_kind=request.scope_kind,
        scope_id=request.scope_id,
    )


def update_permission_intent(
    db: PostgresDatabase,
    intent_id: UUID,
    *,
    expected_version: int,
    patch: dict[str, Any],
) -> MutationResult:
    with db.connection() as connection:
        current_row = fetch_permission_intent(connection, intent_id)
    if current_row is None:
        raise LookupError(f"permission intent {intent_id} was not found")

    current = PermissionIntentRead.model_validate(current_row)
    validated_patch = PermissionIntentUpdate.model_validate(patch).model_dump(
        mode="python",
        exclude_unset=True,
    )
    updated = validated_update(current, validated_patch)
    aggregate_id = build_permission_intent_aggregate_id(
        scope_kind=current.scope_kind,
        scope_id=current.scope_id,
        role_id=current.role_id,
        channel_id=getattr(current, "channel_id", None),
    )

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        row = _to_permission_intent_row(updated)
        updated_count = update_permission_intent_row(
            connection,
            intent_id=intent_id,
            row=row,
        )
        if updated_count != 1:
            raise LookupError(f"permission intent {intent_id} was not found")
        return StateChangeDraft(
            change_type="permission_intent.updated",
            payload_json=updated.model_dump(mode="json"),
        )

    return mutate_entity(
        db=db,
        aggregate_type="permission_intent",
        aggregate_id=aggregate_id,
        request=_make_request(
            expected_version=expected_version,
            request_surface="service:permissions.update_permission_intent",
        ),
        action_type="permission_intent.update",
        action_payload=validated_patch,
        payload_allowlist=set(validated_patch.keys()),
        mutate_projection=mutate_projection,
        scope_kind=current.scope_kind,
        scope_id=current.scope_id,
    )


def read_permission_intent(
    db: PostgresDatabase,
    intent_id: UUID,
) -> Any:
    with db.connection() as connection:
        row = fetch_permission_intent(connection, intent_id)
    if row is None:
        raise LookupError(f"permission intent {intent_id} was not found")
    return PermissionIntentRead.model_validate(row)


def create_permission_drift(
    db: PostgresDatabase,
    *,
    request: PermissionDriftRead,
    expected_version: int = 0,
) -> MutationResult:
    aggregate_id = str(request.id)

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        insert_permission_drift(connection, row=_to_permission_drift_row(request))
        return StateChangeDraft(
            change_type="permission_drift.created",
            payload_json=request.model_dump(mode="json"),
        )

    return mutate_entity(
        db=db,
        aggregate_type="permission_drift",
        aggregate_id=aggregate_id,
        request=_make_request(
            expected_version=expected_version,
            request_surface="service:permissions.create_permission_drift",
        ),
        action_type="permission_drift.create",
        action_payload=request.model_dump(mode="json"),
        payload_allowlist=set(request.model_dump().keys()),
        mutate_projection=mutate_projection,
    )


def update_permission_drift_status(
    db: PostgresDatabase,
    *,
    drift_id: UUID,
    status: str,
    expected_version: int | None = None,
) -> MutationResult:
    current = read_permission_drift(db, drift_id)
    updated = validated_update(current, {"status": status})
    aggregate_id = str(drift_id)
    if expected_version is None:
        with db.connection() as connection:
            current_head = _fetch_current_version(
                connection,
                aggregate_type="permission_drift",
                aggregate_id=aggregate_id,
            )
        expected_version = current_head if current_head is not None else 0

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        updated_count = update_permission_drift_status_row(
            connection,
            drift_id=drift_id,
            status=updated.status,
        )
        if updated_count != 1:
            raise LookupError(f"permission drift {drift_id} was not found")
        return StateChangeDraft(
            change_type="permission_drift.status_updated",
            payload_json=updated.model_dump(mode="json"),
        )

    return mutate_entity(
        db=db,
        aggregate_type="permission_drift",
        aggregate_id=aggregate_id,
        request=_make_request(
            expected_version=expected_version,
            request_surface="service:permissions.update_permission_drift_status",
        ),
        action_type="permission_drift.update_status",
        action_payload={"status": updated.status},
        payload_allowlist={"status"},
        mutate_projection=mutate_projection,
    )


def read_permission_drift(
    db: PostgresDatabase,
    drift_id: UUID,
) -> PermissionDriftRead:
    with db.connection() as connection:
        row = fetch_permission_drift(connection, drift_id)
    if row is None:
        raise LookupError(f"permission drift {drift_id} was not found")
    return PermissionDriftRead.model_validate(row)

