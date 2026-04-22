from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.contracts.scope import ScopeKind

DenialReason = Literal[
    "no_matching_grant",
    "scope_mismatch",
    "permission_missing",
    "grant_expired",
    "grant_revoked",
]
DepartureSignal = Literal["active", "roster_removed"]
HandoffFailureReason = Literal["occ_conflict", "unauthorized", "invalid_state"]

SUCCESSION_TRANSFER_REVOCATION_REASON = "succession_transfer"


class AuthorityGrantRead(BaseModel):
    id: UUID
    grantee_id: str = Field(min_length=1)
    scope_kind: ScopeKind
    scope_id: str | None = None
    permissions: frozenset[str]
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_by: str | None = None
    revocation_reason: str | None = None
    predecessor_grant_id: UUID | None = None


class AuthorityGrantCreate(BaseModel):
    grantee_id: str = Field(min_length=1)
    scope_kind: ScopeKind
    scope_id: str | None = None
    permissions: frozenset[str] = Field(min_length=1)
    expires_at: datetime | None = None
    predecessor_grant_id: UUID | None = None


class AuthorityGrantRevoke(BaseModel):
    reason: str = Field(min_length=1)


class AuthorityGrantTransferRequest(BaseModel):
    successor_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class AuthorityGrantListRead(BaseModel):
    items: list[AuthorityGrantRead]
    next_cursor: UUID | None = None


class DepartingRoleEntry(BaseModel):
    role_id: UUID
    holder_member_id: str | None = None
    triggers_succession: bool
    departure_signal: DepartureSignal


class PendingApplicationRef(BaseModel):
    application_id: UUID
    owner_id: str
    state: str


class PendingTicketRef(BaseModel):
    ticket_id: UUID
    owner_id: str
    state: str


class SuccessionPlanRead(BaseModel):
    chapter_id: str
    generated_at: datetime
    departing_roles: list[DepartingRoleEntry]
    affected_grants: list[AuthorityGrantRead]
    pending_applications: list[PendingApplicationRef]
    pending_tickets: list[PendingTicketRef]
    successor_designated: bool
    successor_member_id: str | None = None


class LeadershipHandoffRequest(BaseModel):
    successor_member_id: str = Field(min_length=1)


class HandoffFailure(BaseModel):
    item_id: UUID
    reason: HandoffFailureReason
    detail: str


class HandoffResult(BaseModel):
    transferred: list[UUID]
    already_owned: list[UUID]
    failed: list[HandoffFailure]


class AuthorityRequirement(BaseModel):
    scope_kind: ScopeKind
    scope_id: str | None = None
    permission: str = Field(min_length=1)


class AuthorityDecisionRead(BaseModel):
    allowed: bool
    grant_id: UUID | None = None
    denial_reason: DenialReason | None = None
    override_used: bool = False


class AuthorityErrorBody(BaseModel):
    code: Literal[
        "authority_decision_denied",
        "actor_identity_missing",
        "grant_not_found",
        "grant_already_revoked",
        "grant_already_transferred",
        "duplicate_active_grant",
        "stale_grant_version",
        "invalid_override_reason",
        "invalid_holder_id",
        "projection_not_initialized",
    ]
    message: str
    decision: AuthorityDecisionRead | None = None
    existing_grant_id: UUID | None = None


class DuplicateActiveGrantError(Exception):
    def __init__(self, existing_grant_id: UUID) -> None:
        self.existing_grant_id = existing_grant_id
        super().__init__(f"active duplicate authority grant {existing_grant_id} already exists")


class GrantAlreadyRevokedError(Exception):
    def __init__(self, grant_id: UUID) -> None:
        self.grant_id = grant_id
        super().__init__(f"authority grant {grant_id} is already revoked")


class GrantAlreadyTransferredError(Exception):
    def __init__(self, existing_grant_id: UUID) -> None:
        self.existing_grant_id = existing_grant_id
        super().__init__(
            f"authority grant already transferred to successor {existing_grant_id}"
        )


class InvalidHolderIdError(ValueError):
    pass


__all__ = [
    "AuthorityDecisionRead",
    "AuthorityErrorBody",
    "AuthorityGrantCreate",
    "AuthorityGrantListRead",
    "AuthorityGrantRead",
    "AuthorityGrantRevoke",
    "AuthorityGrantTransferRequest",
    "AuthorityRequirement",
    "DepartingRoleEntry",
    "DenialReason",
    "DuplicateActiveGrantError",
    "GrantAlreadyTransferredError",
    "GrantAlreadyRevokedError",
    "HandoffFailure",
    "HandoffFailureReason",
    "HandoffResult",
    "InvalidHolderIdError",
    "LeadershipHandoffRequest",
    "PendingApplicationRef",
    "PendingTicketRef",
    "SUCCESSION_TRANSFER_REVOCATION_REASON",
    "SuccessionPlanRead",
]
