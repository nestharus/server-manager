from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection

from app.contracts.actor import ActorIdentity
from app.contracts.base import AGGREGATE_SCOPE_MISSING, validated_update
from app.contracts.mutations import (
    MutationRequest,
    MutationResult,
    StaleMutationError,
    StateChangeDraft,
)
from app.contracts.permissions import (
    ExpiredIntentRenewalError,
    NonTemporaryIntentRenewalError,
    PermissionDriftNotFoundError,
    PermissionDriftRead,
    PermissionDriftResolutionRequest,
    PermissionExpirySweepResult,
    PermissionIntentNotFoundError,
    PermissionIntentRead,
    PermissionIntentRenewalRequest,
    PermissionIntentUpdate,
    RenewalExpiresAtInPastError,
)
from app.repositories.permissions import PermissionsRepository
from app.services._helpers.authority import _require_scoped_authority

logger = logging.getLogger(__name__)

PERMISSION_EXPIRER_ACTOR_ID = "permission-expirer"
PERMISSION_EXPIRY_DEFAULT_BATCH_SIZE = 50

INTENT_ACTION_TYPE: dict[str, str] = {
    "create": "permission_intent.create",
    "update": "permission_intent.update",
    "renew": "permission_intent.renew",
    "expire": "permission_intent.expire",
}
INTENT_CHANGE_TYPE: dict[str, str] = {
    "created": "permission_intent.created",
    "updated": "permission_intent.updated",
    "renewed": "permission_intent.renewed",
    "expired": "permission_intent.expired",
}
DRIFT_ACTION_TYPE: dict[str, str] = {
    "create": "permission_drift.create",
    "detect_expired": "permission_drift.detect_expired",
}
DRIFT_CHANGE_TYPE: dict[str, str] = {
    "created": "permission_drift.created",
    "detected_expired": "permission_drift.detected_expired",
}

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
INTENT_RENEW_PAYLOAD_ALLOWLIST = frozenset({"new_expires_at", "reason"})
INTENT_EXPIRE_PAYLOAD_ALLOWLIST = frozenset({"expired_at", "source"})

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
EXPIRY_DRIFT_CREATE_PAYLOAD_ALLOWLIST = frozenset(
    {
        "drift_id",
        "permission_intent_id",
        "intent_version",
        "scope_kind",
        "scope_id",
        "role_id",
        "channel_id",
        "kind",
        "status",
    }
)


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

class PermissionsService:
    def __init__(
        self,
        permissions_repo: PermissionsRepository,
        mutations_callable: Callable[..., MutationResult],
    ) -> None:
        self.permissions_repo = permissions_repo
        self.mutations_callable = mutations_callable

    def create_permission_intent(
        self,
        request: Any,
        *,
        actor: ActorIdentity,
    ) -> tuple[Any, MutationResult]:
        db = self.permissions_repo.db
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
            self.permissions_repo._insert_permission_intent_on(connection, row=row)
            payload = PermissionIntentRead.model_validate(
                {"id": intent_id, **request.model_dump(mode="python")}
            ).model_dump(mode="json")
            return StateChangeDraft(
                change_type=INTENT_CHANGE_TYPE["created"],
                payload_json=payload,
            )

        result = self.mutations_callable(
            aggregate_type="permission_intent",
            aggregate_id=aggregate_id,
            request=_make_request(
                expected_version=0,
                actor=actor,
                request_surface="api:/api/v1/permission-intents",
            ),
            action_type=INTENT_ACTION_TYPE["create"],
            action_payload=request_payload,
            payload_allowlist=INTENT_CREATE_PAYLOAD_ALLOWLIST,
            mutate_projection=mutate_projection,
            scope_kind=request.scope_kind,
            scope_id=request.scope_id,
        )
        return self.read_permission_intent(intent_id), result

    def update_permission_intent(
        self,
        intent_id: UUID,
        *,
        expected_version: int,
        patch: dict[str, Any],
        actor: ActorIdentity,
    ) -> tuple[Any, MutationResult]:
        db = self.permissions_repo.db
        current_row = self.permissions_repo.fetch_permission_intent(intent_id)
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
            updated_count = self.permissions_repo._update_permission_intent_row_on(
                connection,
                intent_id=intent_id,
                row=row,
            )
            if updated_count != 1:
                raise PermissionIntentNotFoundError(intent_id)
            return StateChangeDraft(
                change_type=INTENT_CHANGE_TYPE["updated"],
                payload_json=updated.model_dump(mode="json"),
            )

        result = self.mutations_callable(
            aggregate_type="permission_intent",
            aggregate_id=aggregate_id,
            request=_make_request(
                expected_version=expected_version,
                actor=actor,
                request_surface=f"api:/api/v1/permission-intents/{intent_id}",
            ),
            action_type=INTENT_ACTION_TYPE["update"],
            action_payload=validated_patch,
            payload_allowlist=INTENT_UPDATE_PAYLOAD_ALLOWLIST,
            mutate_projection=mutate_projection,
            scope_kind=current.scope_kind,
            scope_id=current.scope_id,
        )
        return self.read_permission_intent(intent_id), result

    def renew_permission_intent(
        self,
        intent_id: UUID,
        *,
        expected_version: int,
        request: PermissionIntentRenewalRequest,
        actor: ActorIdentity,
    ) -> tuple[Any, MutationResult]:
        db = self.permissions_repo.db
        current = self.read_permission_intent(intent_id)

        _require_scoped_authority(
            "permission_intent.write",
            scope_kind=current.scope_kind,
            scope_id=current.scope_id,
            actor=actor,
            db=db,
        )

        now = datetime.now(UTC)
        if not current.temporary:
            raise NonTemporaryIntentRenewalError(intent_id)
        if current.expired_at is not None or (
            current.expires_at is not None and current.expires_at <= now
        ):
            raise ExpiredIntentRenewalError(intent_id)
        if request.expires_at <= now:
            raise RenewalExpiresAtInPastError(intent_id)

        updated = validated_update(
            current,
            {"expires_at": request.expires_at},
        )
        aggregate_id = build_permission_intent_aggregate_id(
            scope_kind=current.scope_kind,
            scope_id=current.scope_id,
            role_id=current.role_id,
            channel_id=getattr(current, "channel_id", None),
        )

        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            row = _to_permission_intent_row(updated)
            updated_count = self.permissions_repo._update_permission_intent_row_on(
                connection,
                intent_id=intent_id,
                row=row,
            )
            if updated_count != 1:
                raise PermissionIntentNotFoundError(intent_id)
            return StateChangeDraft(
                change_type=INTENT_CHANGE_TYPE["renewed"],
                payload_json=updated.model_dump(mode="json"),
            )

        result = self.mutations_callable(
            aggregate_type="permission_intent",
            aggregate_id=aggregate_id,
            request=_make_request(
                expected_version=expected_version,
                actor=actor,
                request_surface=f"api:/api/v1/permission-intents/{intent_id}/renew",
                reason_text=request.reason,
            ),
            action_type=INTENT_ACTION_TYPE["renew"],
            action_payload={
                "new_expires_at": request.expires_at.isoformat(),
                "reason": request.reason,
            },
            payload_allowlist=INTENT_RENEW_PAYLOAD_ALLOWLIST,
            mutate_projection=mutate_projection,
            scope_kind=current.scope_kind,
            scope_id=current.scope_id,
        )
        return self.read_permission_intent(intent_id), result

    def read_permission_intent(
        self,
        intent_id: UUID,
    ) -> Any:
        row = self.permissions_repo.fetch_permission_intent(intent_id)
        if row is None:
            raise PermissionIntentNotFoundError(intent_id)
        return PermissionIntentRead.model_validate(row)

    def list_permission_intents(
        self,
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
        db = self.permissions_repo.db
        _require_scoped_authority(
            "permission_intent.read",
            scope_kind=scope_kind,
            scope_id=scope_id,
            actor=actor,
            db=db,
        )
        rows = self.permissions_repo.list_permission_intents(
                scope_kind=scope_kind,
                scope_id=scope_id,
                role_id=role_id,
                channel_id=channel_id,
                kind=kind,
                temporary=temporary,
                include_expired=include_expired,
            )
        return [PermissionIntentRead.model_validate(row) for row in rows]

    def expire_temporary_permission_intents(
        self,
        *,
        actor: ActorIdentity,
        now: datetime | None = None,
        batch_size: int | None = None,
        source: str = "worker_sweep",
    ) -> PermissionExpirySweepResult:
        db = self.permissions_repo.db
        _require_scoped_authority(
            "permission_intent.write",
            scope_kind="global",
            scope_id=None,
            actor=actor,
            db=db,
        )

        resolved_now = now or datetime.now(UTC)
        resolved_batch_size = batch_size or PERMISSION_EXPIRY_DEFAULT_BATCH_SIZE
        rows = self.permissions_repo.select_expirable_intents(
            now=resolved_now,
            batch_size=resolved_batch_size,
        )

        expired_intent_ids: list[UUID] = []
        drift_ids: list[UUID] = []
        errored = 0
        inspected = 0
        for row in rows:
            inspected += 1
            intent = PermissionIntentRead.model_validate(row)
            try:
                with db.transaction() as connection:
                    expired_intent, drift = self._expire_single_intent_on(
                        connection,
                        intent=intent,
                        actor=actor,
                        now=resolved_now,
                        source=source,
                    )
            except StaleMutationError:
                logger.debug(
                    "permission-expiry skipped stale intent %s",
                    intent.id,
                )
                continue
            except Exception:
                logger.exception("permission-expiry failed for intent %s", intent.id)
                errored += 1
                continue
            expired_intent_ids.append(expired_intent.id)
            drift_ids.append(drift.id)

        return PermissionExpirySweepResult(
            expired_intent_ids=expired_intent_ids,
            drift_ids=drift_ids,
            inspected_count=inspected,
            expired_count=len(expired_intent_ids),
            errored_count=errored,
        )

    def read_permission_drift(
        self,
        drift_id: UUID,
    ) -> PermissionDriftRead:
        row = self.permissions_repo.fetch_permission_drift(drift_id)
        if row is None:
            raise PermissionDriftNotFoundError(drift_id)
        return PermissionDriftRead.model_validate(row)

    def list_permission_drift(
        self,
        *,
        actor: ActorIdentity,
        scope_kind: str | None,
        scope_id: str | None,
        status: list[str] | None = None,
        role_id: str | None = None,
        reconciliation_run_id: UUID | None = None,
        has_intent: bool | None = None,
    ) -> list[PermissionDriftRead]:
        db = self.permissions_repo.db
        _require_scoped_authority(
            "permission_drift.read",
            scope_kind=scope_kind or "global",
            scope_id=scope_id,
            actor=actor,
            db=db,
        )
        rows = self.permissions_repo.list_permission_drift(
                status=status,
                scope_kind=scope_kind,
                scope_id=scope_id,
                role_id=role_id,
                reconciliation_run_id=reconciliation_run_id,
                has_intent=has_intent,
            )
        return [PermissionDriftRead.model_validate(row) for row in rows]

    def _expire_single_intent_on(
        self,
        connection: Connection[Any],
        *,
        intent: Any,
        actor: ActorIdentity,
        now: datetime,
        source: str,
    ) -> tuple[Any, PermissionDriftRead]:
        aggregate_id = build_permission_intent_aggregate_id(
            scope_kind=intent.scope_kind,
            scope_id=intent.scope_id,
            role_id=intent.role_id,
            channel_id=getattr(intent, "channel_id", None),
        )

        expected_version = _read_intent_head_version(
            connection,
            aggregate_id=aggregate_id,
            intent_id=intent.id,
        )

        def mutate_projection_expire(active: Connection[Any]) -> StateChangeDraft:
            updated_count = self.permissions_repo._mark_intent_expired_row_on(
                active,
                intent_id=intent.id,
                expired_at=now,
            )
            if updated_count != 1:
                raise PermissionIntentNotFoundError(intent.id)
            updated = intent.model_copy(update={"expired_at": now})
            return StateChangeDraft(
                change_type=INTENT_CHANGE_TYPE["expired"],
                payload_json=updated.model_dump(mode="json"),
            )

        expire_result = self.mutations_callable(
            aggregate_type="permission_intent",
            aggregate_id=aggregate_id,
            request=_make_request(
                expected_version=expected_version,
                actor=actor,
                request_surface="worker:permission_expiry",
            ),
            action_type=INTENT_ACTION_TYPE["expire"],
            action_payload={
                "expired_at": now.isoformat(),
                "source": source,
            },
            payload_allowlist=INTENT_EXPIRE_PAYLOAD_ALLOWLIST,
            mutate_projection=mutate_projection_expire,
            scope_kind=intent.scope_kind,
            scope_id=intent.scope_id,
            connection=connection,
        )
        drift = self._create_expiry_drift_on(
            connection,
            intent=intent,
            intent_version_after_expire=expire_result.version,
            actor=actor,
            now=now,
        )
        expired_intent = intent.model_copy(update={"expired_at": now})
        return expired_intent, drift

    def _create_expiry_drift_on(
        self,
        connection: Connection[Any],
        *,
        intent: Any,
        intent_version_after_expire: int,
        actor: ActorIdentity,
        now: datetime,
    ) -> PermissionDriftRead:
        drift = PermissionDriftRead.model_validate(
            {
                "id": uuid4(),
                "permission_intent_id": intent.id,
                "intent_version": intent_version_after_expire,
                "scope_kind": intent.scope_kind,
                "scope_id": intent.scope_id,
                "role_id": intent.role_id,
                "channel_id": getattr(intent, "channel_id", None),
                "kind": intent.kind,
                "reconciliation_run_id": None,
                "intended_bits": getattr(intent, "permission_bits", None),
                "intended_allow_bits": getattr(intent, "allow_bits", None),
                "intended_deny_bits": getattr(intent, "deny_bits", None),
                "actual_bits": None,
                "actual_allow_bits": None,
                "actual_deny_bits": None,
                "status": "detected",
                "detected_at": now,
            }
        )
        action_payload = {
            "drift_id": str(drift.id),
            "permission_intent_id": str(intent.id),
            "intent_version": intent_version_after_expire,
            "scope_kind": intent.scope_kind,
            "scope_id": intent.scope_id,
            "role_id": intent.role_id,
            "channel_id": getattr(intent, "channel_id", None),
            "kind": intent.kind,
            "status": "detected",
        }

        def mutate_projection_drift(active: Connection[Any]) -> StateChangeDraft:
            self.permissions_repo._insert_permission_drift_on(
                active,
                row=_to_permission_drift_row(drift),
            )
            return StateChangeDraft(
                change_type=DRIFT_CHANGE_TYPE["detected_expired"],
                payload_json=drift.model_dump(mode="json"),
            )

        self.mutations_callable(
            aggregate_type="permission_drift",
            aggregate_id=str(drift.id),
            request=_make_request(
                expected_version=0,
                actor=actor,
                request_surface="worker:permission_expiry",
            ),
            action_type=DRIFT_ACTION_TYPE["detect_expired"],
            action_payload=action_payload,
            payload_allowlist=EXPIRY_DRIFT_CREATE_PAYLOAD_ALLOWLIST,
            mutate_projection=mutate_projection_drift,
            scope_kind=intent.scope_kind,
            scope_id=intent.scope_id,
            connection=connection,
        )
        return drift

    def resolve_permission_drift(
        self,
        *,
        drift_id: UUID,
        request: PermissionDriftResolutionRequest,
        expected_version: int,
        actor: ActorIdentity,
    ) -> tuple[PermissionDriftRead, MutationResult]:
        db = self.permissions_repo.db
        current = self.read_permission_drift(drift_id)

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

        resolved_kind, resolved_id = _drift_originating_actor(request, actor)
        resolved_at = datetime.now(UTC)
        resolution_reason = request.reason

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
            updated = self.permissions_repo._update_permission_drift_resolution_on(
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
                    "resolved_at": resolved_at.isoformat(),
                    "resolution_reason": resolution_reason,
                },
                diff_json={"from": from_state, "to": next_status},
            )

        result = self.mutations_callable(
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
        post_update = PermissionDriftRead.model_validate(
            {
                **current.model_dump(mode="python"),
                "status": next_status,
                "resolved_by_kind": resolved_kind,
                "resolved_by_id": resolved_id,
                "resolved_at": resolved_at,
                "resolution_reason": resolution_reason,
            }
        )
        return post_update, result

    def create_permission_drift(
        self,
        *,
        request: PermissionDriftRead,
        actor: ActorIdentity,
        expected_version: int = 0,
    ) -> MutationResult:
        aggregate_id = str(request.id)

        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            self.permissions_repo._insert_permission_drift_on(
                connection, row=_to_permission_drift_row(request)
            )
            return StateChangeDraft(
                change_type=DRIFT_CHANGE_TYPE["created"],
                payload_json=request.model_dump(mode="json"),
            )

        return self.mutations_callable(
            aggregate_type="permission_drift",
            aggregate_id=aggregate_id,
            request=_make_request(
                expected_version=expected_version,
                actor=actor,
                request_surface="service:permissions.create_permission_drift",
            ),
            action_type=DRIFT_ACTION_TYPE["create"],
            action_payload=request.model_dump(mode="json"),
            payload_allowlist=set(request.model_dump().keys()),
            mutate_projection=mutate_projection,
            scope_kind=request.scope_kind,
            scope_id=request.scope_id,
        )


def _read_intent_head_version(
    connection: Connection[Any],
    *,
    aggregate_id: str,
    intent_id: UUID,
) -> int:
    row = connection.execute(
        """
        SELECT current_seq
          FROM aggregate_heads
         WHERE aggregate_type = 'permission_intent'
           AND aggregate_id = %s
        """,
        (aggregate_id,),
    ).fetchone()
    if row is None:
        raise PermissionIntentNotFoundError(intent_id)
    return int(row[0])

def _drift_originating_actor(
    request: PermissionDriftResolutionRequest,
    actor: ActorIdentity,
) -> tuple[str, str]:
    if actor.actor_kind == "service":
        kind = request.resolved_by_kind or actor.actor_kind
        ident = request.resolved_by_id or actor.actor_id
        return kind, ident
    return actor.actor_kind, actor.actor_id
