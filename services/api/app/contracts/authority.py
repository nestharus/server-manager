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
    predecessor_grant_id: UUID | None = None


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
    ]
    message: str
    decision: AuthorityDecisionRead | None = None


class GrantAlreadyRevokedError(Exception):
    def __init__(self, grant_id: UUID) -> None:
        self.grant_id = grant_id
        super().__init__(f"authority grant {grant_id} is already revoked")


__all__ = [
    "AuthorityDecisionRead",
    "AuthorityErrorBody",
    "AuthorityGrantRead",
    "AuthorityRequirement",
    "DenialReason",
    "GrantAlreadyRevokedError",
]
