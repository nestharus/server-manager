"""Mutation primitive contracts.

Internal service-layer contracts for the shared `mutate_entity()` primitive.
Not exposed on the HTTP wire. Endpoints translate between `If-Match` headers
and these internal envelopes.

Concurrency: `expected_version` is the version the caller believes is
current. On mismatch against the live `aggregate_heads` row, the primitive
raises `StaleMutationError` (to be translated to HTTP 412). On success,
`MutationResult.etag` is a strong HTTP ETag value (`"<new_version>"`) per
RFC 7232 §3.1 strong comparison.

Redaction: `StateChangeDraft.payload_json` holds the accepted business fact
(authoritative). The primitive's `payload_allowlist` parameter controls
which request-level fields survive into the `activity_actions` audit row;
state-change payloads are not redacted because they record the durable
accepted fact.
"""

from typing import Any

from pydantic import BaseModel, Field


class MutationRequest(BaseModel):
    """Internal mutation envelope derived from the HTTP request.

    Endpoints build this from the `If-Match` header (expected_version) plus
    the authenticated actor context.
    """

    expected_version: int = Field(ge=0)
    actor_kind: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    reason_text: str | None = None


class MutationResult(BaseModel):
    """Internal result returned after an accepted write.

    Endpoints translate this to the outgoing HTTP response with the `ETag`
    header set to `etag`.
    """

    version: int = Field(ge=1)
    etag: str = Field(pattern=r'^"[0-9]+"$')


class StateChangeDraft(BaseModel):
    """Accepted-state-change payload returned by the caller's projection
    callback.

    `change_type` names the business transition (e.g., `chapter_renamed`).
    `payload_json` is the authoritative accepted fact stored in
    `activity_state_changes`. `diff_json` is an optional derived view
    captured at write time for audit ergonomics.
    """

    change_type: str = Field(min_length=1)
    payload_json: dict[str, Any]
    diff_json: dict[str, Any] | None = None


class StaleMutationError(Exception):
    """Raised by `mutate_entity()` when the caller's expected_version does
    not match the live aggregate head.

    Endpoints translate this to HTTP 412 Precondition Failed.
    """

    def __init__(
        self,
        *,
        aggregate_type: str,
        aggregate_id: int,
        expected_version: int,
        current_version: int,
    ) -> None:
        self.aggregate_type = aggregate_type
        self.aggregate_id = aggregate_id
        self.expected_version = expected_version
        self.current_version = current_version
        super().__init__(
            f"stale version on {aggregate_type}#{aggregate_id}: "
            f"expected {expected_version}, current {current_version}"
        )


__all__ = [
    "MutationRequest",
    "MutationResult",
    "StaleMutationError",
    "StateChangeDraft",
]
