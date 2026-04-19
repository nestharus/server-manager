from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.contracts.scope import ScopeKind


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


class AuthorityDecision(BaseModel):
    allowed: bool


class GrantAlreadyRevokedError(Exception):
    def __init__(self, grant_id: UUID) -> None:
        self.grant_id = grant_id
        super().__init__(f"authority grant {grant_id} is already revoked")


__all__ = [
    "AuthorityDecision",
    "AuthorityGrantRead",
    "AuthorityRequirement",
    "GrantAlreadyRevokedError",
]
