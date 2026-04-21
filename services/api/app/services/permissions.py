from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection

from app.contracts.actor import ActorIdentity
from app.contracts.authority import AuthorityRequirement
from app.contracts.base import AGGREGATE_SCOPE_MISSING, validated_update
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.contracts.permissions import (
    PermissionDriftNotFoundError,
    PermissionDriftRead,
    PermissionDriftResolutionRequest,
    PermissionIntentCreate,
    PermissionIntentNotFoundError,
    PermissionIntentRead,
    PermissionIntentUpdate,
)
from app.repositories.db import PostgresDatabase
from app.repositories import permissions as permission_repo
from app.services.authority import current_time, evaluate, list_grants_for_grantee
from app.services.mutations import mutate_entity


INTENT_CREATE_PAYLOAD_ALLOWLIST: set[str] = {
    "kind",
    "scope_kind",
    "scope_id",
    "role_id",
    "channel_id",
    "permission_bits",
    "allow_bits",
    "deny_bits",
    "reason",
    "temporary",
    "expires_at",
}
INTENT_UPDATE_PAYLOAD_ALLOWLIST: set[str] = {
    "reason",
    "temporary",
    "expires_at",
    "permission_bits",
    "allow_bits",
    "deny_bits",
}

DRIFT_RESOLUTION_TARGET_STATUS: dict[str, str] = {
    "acknowledge": "acknowledged",
    "reconcile": "reconciled",
    "accept": "accepted",
}

VALID_DRIFT_TRANSITIONS: dict[tuple[str, str], str] = {
    ("detected", "acknowledge"): "acknowledged",
    ("detected", "reconcile"): "reconciled",
    ("detected", "accept"): "accepted",
    ("acknowledged", "reconcile"): "reconciled",
    ("acknowledged", "accept"): "accepted",
}

DRIFT_TERMINAL_STATUSES = frozenset({"reconciled", "accepted"})

DRIFT_RESOLUTION_PAYLOAD_ALLOWLIST: dict[str, set[str]] = {
    "acknowledge": {"action", "reason", "resolved_by_kind", "resolved_by_id"},
    "reconcile": {"action", "reason", "resolved_by_kind", "resolved_by_id"},
    "accept": {"action", "reason", "resolved_by_kind", "resolved_by_id"},
}

DRIFT_RESOLUTION_ACTION_TYPE: dict[str, str] = {
    "acknowledge": "permission_drift.acknowledge",
    "reconcile": "permission_drift.reconcile",
    "accept": "permission_drift.accept",
}
DRIFT_RESOLUTION_CHANGE_TYPE: dict[str, str] = {
    "acknowledge": "permission_drift.acknowledged",
    "reconcile": "permission_drift.reconciled",
    "accept": "permission_drift.accepted",
}


class InvalidDriftTransitionError(Exception):
    def __init__(self, *, drift_id: UUID, from_state: str, action: str) -> None:
        super().__init__(
            f"drift {drift_id} cannot {action} from state {from_state}"
        )
        self.drift_id = drift_id
        self.from_state = from_state
        self.action = action


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


def _require_scoped_authority(
    permission: str,
    *,
    scope_kind: str,
    scope_id: str | None,
    actor: ActorIdentity,
    db: PostgresDatabase,
) -> None:
    grants = list_grants_for_grantee(db, grantee_id=actor.actor_id)
    decision = evaluate(
        requirement=AuthorityRequirement(
            scope_kind=scope_kind,  # type: ignore[arg-type]
            scope_id=scope_id,
            permission=permission,
        ),
        grants=grants,
        at=current_time(),
    )
    if not decision.allowed:
        raise PermissionError("authority requirement denied")


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


def create_permission_intent(
    db: PostgresDatabase,
    request: Any,
    *,
    actor: ActorIdentity,
) -> tuple[Any, MutationResult]:
    _require_scoped_authority(
        "permission_intent.write",
        scope_kind=request.scope_kind,
        scope_id=request.scope_id,
        actor=actor,
        db=db,
    )

    intent_id = uuid4()
    aggregate_id = build_permission_intent_aggregate_id(
        scope_kind=request.scope_kind,
        scope_id=request.scope_id,
        role_id=request.role_id,
        channel_id=getattr(request, "channel_id", None),
    )
    request_payload = request.model_dump(mode="json")

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        row = _to_permission_intent_row(
            PermissionIntentRead.model_validate(
                {"id": intent_id, **request.model_dump(mode="python")}
            )
        )
        permission_repo.insert_permission_intent(connection, row=row)
        payload = PermissionIntentRead.model_validate(
            {"id": intent_id, **request.model_dump(mode="python")}
        ).model_dump(mode="json")
        return StateChangeDraft(
            change_type="permission_intent.created",
            payload_json=payload,
        )

    result = mutate_entity(
        db=db,
        aggregate_type="permission_intent",
        aggregate_id=aggregate_id,
        request=_make_request(
            expected_version=0,
            actor=actor,
            request_surface="api:/api/v1/permission-intents",
        ),
        action_type="permission_intent.create",
        action_payload=request_payload,
        payload_allowlist=INTENT_CREATE_PAYLOAD_ALLOWLIST,
        mutate_projection=mutate_projection,
        scope_kind=request.scope_kind,
        scope_id=request.scope_id,
    )
    return read_permission_intent(db, intent_id), result


def update_permission_intent(
    db: PostgresDatabase,
    intent_id: UUID,
    *,
    expected_version: int,
    patch: dict[str, Any],
    actor: ActorIdentity,
) -> tuple[Any, MutationResult]:
    with db.connection() as connection:
        current_row = permission_repo.fetch_permission_intent(connection, intent_id)
    if current_row is None:
        raise PermissionIntentNotFoundError(intent_id)

    current = PermissionIntentRead.model_validate(current_row)
    _require_scoped_authority(
        "permission_intent.write",
        scope_kind=current.scope_kind,
        scope_id=current.scope_id,
        actor=actor,
        db=db,
    )

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
        updated_count = permission_repo.update_permission_intent_row(
            connection,
            intent_id=intent_id,
            row=row,
        )
        if updated_count != 1:
            raise PermissionIntentNotFoundError(intent_id)
        return StateChangeDraft(
            change_type="permission_intent.updated",
            payload_json=updated.model_dump(mode="json"),
        )

    result = mutate_entity(
        db=db,
        aggregate_type="permission_intent",
        aggregate_id=aggregate_id,
        request=_make_request(
            expected_version=expected_version,
            actor=actor,
            request_surface=f"api:/api/v1/permission-intents/{intent_id}",
        ),
        action_type="permission_intent.update",
        action_payload=validated_patch,
        payload_allowlist=INTENT_UPDATE_PAYLOAD_ALLOWLIST,
        mutate_projection=mutate_projection,
        scope_kind=current.scope_kind,
        scope_id=current.scope_id,
    )
    return read_permission_intent(db, intent_id), result


def read_permission_intent(
    db: PostgresDatabase,
    intent_id: UUID,
) -> Any:
    with db.connection() as connection:
        row = permission_repo.fetch_permission_intent(connection, intent_id)
    if row is None:
        raise PermissionIntentNotFoundError(intent_id)
    return PermissionIntentRead.model_validate(row)


def list_permission_intents(
    db: PostgresDatabase,
    *,
    actor: ActorIdentity,
    scope_kind: str,
    scope_id: str | None,
    role_id: str | None = None,
    channel_id: str | None = None,
    kind: str | None = None,
    temporary: bool | None = None,
    include_expired: bool = False,
) -> list[Any]:
    _require_scoped_authority(
        "permission_intent.read",
        scope_kind=scope_kind,
        scope_id=scope_id,
        actor=actor,
        db=db,
    )
    with db.connection() as connection:
        rows = permission_repo.list_permission_intents(
            connection,
            scope_kind=scope_kind,
            scope_id=scope_id,
            role_id=role_id,
            channel_id=channel_id,
            kind=kind,
            temporary=temporary,
            include_expired=include_expired,
        )
    return [PermissionIntentRead.model_validate(row) for row in rows]


def read_permission_drift(
    db: PostgresDatabase,
    drift_id: UUID,
) -> PermissionDriftRead:
    with db.connection() as connection:
        row = permission_repo.fetch_permission_drift(connection, drift_id)
    if row is None:
        raise PermissionDriftNotFoundError(drift_id)
    return PermissionDriftRead.model_validate(row)


def list_permission_drift(
    db: PostgresDatabase,
    *,
    actor: ActorIdentity,
    scope_kind: str | None,
    scope_id: str | None,
    status: list[str] | None = None,
    role_id: str | None = None,
    reconciliation_run_id: UUID | None = None,
    has_intent: bool | None = None,
) -> list[PermissionDriftRead]:
    _require_scoped_authority(
        "permission_drift.read",
        scope_kind=scope_kind or "global",
        scope_id=scope_id,
        actor=actor,
        db=db,
    )
    with db.connection() as connection:
        rows = permission_repo.list_permission_drift(
            connection,
            status=status,
            scope_kind=scope_kind,
            scope_id=scope_id,
            role_id=role_id,
            reconciliation_run_id=reconciliation_run_id,
            has_intent=has_intent,
        )
    return [PermissionDriftRead.model_validate(row) for row in rows]


def _drift_originating_actor(
    request: PermissionDriftResolutionRequest,
    actor: ActorIdentity,
) -> tuple[str, str]:
    if actor.actor_kind == "service":
        kind = request.resolved_by_kind or actor.actor_kind
        ident = request.resolved_by_id or actor.actor_id
        return kind, ident
    return actor.actor_kind, actor.actor_id


def resolve_permission_drift(
    db: PostgresDatabase,
    *,
    drift_id: UUID,
    request: PermissionDriftResolutionRequest,
    expected_version: int,
    actor: ActorIdentity,
) -> tuple[PermissionDriftRead, MutationResult]:
    current = read_permission_drift(db, drift_id)

    _require_scoped_authority(
        "permission_drift.write",
        scope_kind=current.scope_kind,
        scope_id=current.scope_id,
        actor=actor,
        db=db,
    )

    if current.status in DRIFT_TERMINAL_STATUSES:
        raise InvalidDriftTransitionError(
            drift_id=drift_id,
            from_state=current.status,
            action=request.action,
        )
    next_status = VALID_DRIFT_TRANSITIONS.get((current.status, request.action))
    if next_status is None:
        raise InvalidDriftTransitionError(
            drift_id=drift_id,
            from_state=current.status,
            action=request.action,
        )

    is_terminal = next_status in DRIFT_TERMINAL_STATUSES
    if is_terminal:
        resolved_kind, resolved_id = _drift_originating_actor(request, actor)
        resolved_at: datetime | None = datetime.now(UTC)
    else:
        resolved_kind, resolved_id, resolved_at = None, None, None
    resolution_reason = request.reason if is_terminal else None

    aggregate_id = str(drift_id)
    action_payload = {
        "action": request.action,
        "reason": request.reason,
        "resolved_by_kind": resolved_kind,
        "resolved_by_id": resolved_id,
    }

    action_type = DRIFT_RESOLUTION_ACTION_TYPE[request.action]
    change_type = DRIFT_RESOLUTION_CHANGE_TYPE[request.action]
    from_state = current.status

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        updated = permission_repo.update_permission_drift_resolution(
            connection,
            drift_id=drift_id,
            status=next_status,
            resolved_by_kind=resolved_kind,
            resolved_by_id=resolved_id,
            resolved_at=resolved_at,
            resolution_reason=resolution_reason,
        )
        if updated != 1:
            raise PermissionDriftNotFoundError(drift_id)
        return StateChangeDraft(
            change_type=change_type,
            payload_json={
                "status": next_status,
                "resolved_by_kind": resolved_kind,
                "resolved_by_id": resolved_id,
                "resolved_at": None if resolved_at is None else resolved_at.isoformat(),
                "resolution_reason": resolution_reason,
            },
            diff_json={"from": from_state, "to": next_status},
        )

    result = mutate_entity(
        db=db,
        aggregate_type="permission_drift",
        aggregate_id=aggregate_id,
        request=_make_request(
            expected_version=expected_version,
            actor=actor,
            request_surface=f"api:/api/v1/permission-drift/{drift_id}/resolve",
        ),
        action_type=action_type,
        action_payload=action_payload,
        payload_allowlist=DRIFT_RESOLUTION_PAYLOAD_ALLOWLIST[request.action],
        mutate_projection=mutate_projection,
        scope_kind=current.scope_kind,
        scope_id=current.scope_id,
    )
    return read_permission_drift(db, drift_id), result


def create_permission_drift(
    db: PostgresDatabase,
    *,
    request: PermissionDriftRead,
    actor: ActorIdentity,
    expected_version: int = 0,
) -> MutationResult:
    aggregate_id = str(request.id)

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        permission_repo.insert_permission_drift(
            connection, row=_to_permission_drift_row(request)
        )
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
            actor=actor,
            request_surface="service:permissions.create_permission_drift",
        ),
        action_type="permission_drift.create",
        action_payload=request.model_dump(mode="json"),
        payload_allowlist=set(request.model_dump().keys()),
        mutate_projection=mutate_projection,
        scope_kind=request.scope_kind,
        scope_id=request.scope_id,
    )
