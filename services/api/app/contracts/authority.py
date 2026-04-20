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


class AuthorityGrantListRead(BaseModel):
    items: list[AuthorityGrantRead]
    next_cursor: UUID | None = None


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
        "duplicate_active_grant",
        "stale_grant_version",
        "invalid_override_reason",
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


__all__ = [
    "AuthorityDecisionRead",
    "AuthorityErrorBody",
    "AuthorityGrantCreate",
    "AuthorityGrantListRead",
    "AuthorityGrantRead",
    "AuthorityGrantRevoke",
    "AuthorityRequirement",
    "DenialReason",
    "DuplicateActiveGrantError",
    "GrantAlreadyRevokedError",
]
