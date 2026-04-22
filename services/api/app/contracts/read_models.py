from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.contracts.authority import AuthorityGrantRead, PendingApplicationRef, PendingTicketRef

class _ReadModelContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReadModelCursorRead(_ReadModelContract):
    projection_name: str
    last_processed_id: int
    last_processed_at: datetime | None
    version: int


class OperationalOverviewRead(_ReadModelContract):
    scope_kind: Literal["global", "chapter"]
    scope_id: str | None
    open_applications_count: int
    open_tickets_count: int
    pending_deferred_effects_count: int
    permission_drift_count: int
    stale_projections: list[str]
    stale_since: datetime | None
    is_stale: bool


class InheritedFromEntry(_ReadModelContract):
    predecessor_grant_id: UUID
    predecessor_member_id: str
    scope_kind: str
    scope_id: str | None
    revoked_at: datetime | None


class StaleHandoffEntry(_ReadModelContract):
    predecessor_grant_id: UUID
    predecessor_member_id: str
    pending_application_ids: list[UUID]
    pending_ticket_ids: list[UUID]


class LeadershipContextRead(_ReadModelContract):
    member_id: str
    generated_at: datetime
    active_grants: list[AuthorityGrantRead]
    inherited_from: list[InheritedFromEntry]
    current_applications: list[PendingApplicationRef]
    current_tickets: list[PendingTicketRef]
    stale_handoff: list[StaleHandoffEntry]
    is_stale: bool
    projector_is_stale: bool


__all__ = [
    "InheritedFromEntry",
    "LeadershipContextRead",
    "OperationalOverviewRead",
    "ReadModelCursorRead",
    "StaleHandoffEntry",
]
