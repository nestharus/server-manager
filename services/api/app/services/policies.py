from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from psycopg import Connection

from app.contracts.actor import ActorIdentity
from app.contracts.mutations import MutationRequest, StateChangeDraft
from app.contracts.policies import (
    POLICY_AGGREGATE_SCOPE_MISSING,
    PolicyConfirmRequest,
    PolicyVersionNotFoundError,
    PolicyPreviewRead,
    PolicyPreviewRequest,
    PolicyPreviewTokenMismatchError,
    PolicyVersionRead,
    _canonicalize_content,
)
from app.repositories.policies import PoliciesRepository
from app.services.mutations import _format_etag


def _policy_aggregate_id(
    policy_type: str,
    scope_kind: str,
    scope_id: str | None,
) -> str:
    return f"{policy_type}|{scope_kind}|{scope_id if scope_id is not None else POLICY_AGGREGATE_SCOPE_MISSING}"


def _policy_preview_digest(
    policy_type: str,
    scope_kind: str,
    scope_id: str | None,
    expected_current_version: int,
    content: dict[str, Any],
) -> str:
    digest_input = "|".join(
        [
            policy_type,
            scope_kind,
            scope_id if scope_id is not None else POLICY_AGGREGATE_SCOPE_MISSING,
            str(expected_current_version),
            _canonicalize_content(content),
        ]
    )
    return hashlib.blake2b(
        digest_input.encode("ascii"),
        digest_size=16,
    ).hexdigest()


def _diff_top_level(
    current_content: dict[str, Any],
    next_content: dict[str, Any],
) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    for key in sorted(set(current_content) | set(next_content)):
        if current_content.get(key) != next_content.get(key):
            diffs.append({"key": key})
    return diffs


def _row_to_policy_version_read(row: dict[str, Any]) -> PolicyVersionRead:
    return PolicyVersionRead(
        id=row["id"],
        policy_type=row["policy_type"],
        scope_kind=row["scope_kind"],
        scope_id=row["scope_id"],
        version_number=int(row["version_number"]),
        effective_at=row["effective_at"],
    )


class PoliciesService:
    def __init__(
        self,
        policies_repo: PoliciesRepository,
        mutations_callable,
    ) -> None:
        self._policies_repo = policies_repo
        self._mutations_callable = mutations_callable

    def preview(self, request: PolicyPreviewRequest) -> PolicyPreviewRead:
        latest = self._policies_repo.fetch_latest_version(
            request.policy_type,
            request.scope_kind,
            request.scope_id,
        )

        current_version = 0 if latest is None else int(latest["version_number"])
        current_content = {} if latest is None else dict(latest["content"])
        return PolicyPreviewRead(
            preview_token=_policy_preview_digest(
                request.policy_type,
                request.scope_kind,
                request.scope_id,
                request.expected_current_version,
                request.content,
            ),
            current_version=current_version,
            affected_objects=_diff_top_level(current_content, request.content),
            rollback_summary=current_content,
        )

    def confirm(
        self,
        request: PolicyConfirmRequest,
        *,
        actor: ActorIdentity,
    ) -> tuple[PolicyVersionRead, str]:
        expected_token = _policy_preview_digest(
            request.policy_type,
            request.scope_kind,
            request.scope_id,
            request.expected_current_version,
            request.content,
        )
        if expected_token != request.preview_token:
            raise PolicyPreviewTokenMismatchError()

        aggregate_id = _policy_aggregate_id(
            request.policy_type,
            request.scope_kind,
            request.scope_id,
        )
        created_effective_at = datetime.now(UTC)
        created_id = uuid4()
        created_version_number = request.expected_current_version + 1

        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            self._policies_repo._insert_policy_version_on(
                connection,
                row={
                    "id": created_id,
                    "policy_type": request.policy_type,
                    "scope_kind": request.scope_kind,
                    "scope_id": request.scope_id,
                    "version_number": created_version_number,
                    "content": request.content,
                    "effective_at": created_effective_at,
                },
            )
            return StateChangeDraft(
                change_type="policy_version.confirmed",
                payload_json={
                    "policy_type": request.policy_type,
                    "scope_kind": request.scope_kind,
                    "scope_id": request.scope_id,
                    "version_number": created_version_number,
                },
            )

        result = self._mutations_callable(
            aggregate_type="policy_version",
            aggregate_id=aggregate_id,
            request=MutationRequest(
                expected_version=request.expected_current_version,
                actor_kind=actor.actor_kind,
                actor_id=actor.actor_id,
                reason_text=None,
                request_surface="service:policies.confirm",
            ),
            action_type="policy.confirm",
            action_payload={},
            payload_allowlist=None,
            mutate_projection=mutate_projection,
            scope_kind=request.scope_kind,
            scope_id=request.scope_id,
        )
        return (
            PolicyVersionRead(
                id=created_id,
                policy_type=request.policy_type,
                scope_kind=request.scope_kind,
                scope_id=request.scope_id,
                version_number=created_version_number,
                effective_at=created_effective_at,
            ),
            result.etag,
        )

    def get_current_policy_version(
        self,
        *,
        policy_type: str,
        scope_kind: str,
        scope_id: str | None,
    ) -> tuple[PolicyVersionRead, str]:
        row = self._policies_repo.fetch_current_policy_version(
            policy_type=policy_type,
            scope_kind=scope_kind,
            scope_id=scope_id,
        )
        if row is None:
            raise PolicyVersionNotFoundError(
                policy_type=policy_type,
                scope_kind=scope_kind,
                scope_id=scope_id,
            )
        read = _row_to_policy_version_read(row)
        return read, _format_etag(read.version_number)


__all__ = ["PoliciesService"]
