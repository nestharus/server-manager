"""Read-model pipeline: counts stay fresh from synchronous projections; staleness signals projector liveness only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from app.contracts.actor import ActorIdentity
from app.contracts.authority import AuthorityGrantRead, PendingApplicationRef, PendingTicketRef
from app.contracts.read_models import (
    InheritedFromEntry,
    LeadershipContextRead,
    OperationalOverviewRead,
    ReadModelCursorRead,
    StaleHandoffEntry,
)
from app.repositories.applications import list_open_applications_for_owner_ids
from app.repositories.authority import fetch_grants_by_ids, list_active_grants_for_grantee_ids
from app.repositories.db import PostgresDatabase
from app.repositories.read_models import (
    advance_cursor,
    count_active_drift,
    count_open_applications,
    count_open_tickets,
    count_pending_deferred_effects,
    load_cursor,
    max_event_id_settled,
)
from app.repositories.tickets import list_open_tickets_for_owner_ids
from app.services.authority import OPEN_APPLICATION_STATES, _collect_member_aliases, _require_scoped_authority


OPERATIONAL_OVERVIEW_PROJECTION_NAME = "operational_overview"
PROJECTION_NAMES: frozenset[str] = frozenset({OPERATIONAL_OVERVIEW_PROJECTION_NAME})

MIN_AGE_SECONDS = 5
STALE_EVENT_THRESHOLD = 100
STALE_TIME_THRESHOLD = timedelta(minutes=5)

PENDING_DEFERRED_EFFECT_STATUSES: frozenset[str] = frozenset(
    {"queued", "claimed", "failed"}
)
ACTIVE_DRIFT_STATUSES: frozenset[str] = frozenset({"detected", "acknowledged"})

_OVERVIEW_PERMISSION = "operational_overview.read"


class CursorNotSeededError(RuntimeError):
    pass


class InvalidScopeError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class _Staleness:
    projections: list[str]
    since: datetime | None
    is_stale: bool


def _cursor_row_to_read(row: dict[str, Any]) -> ReadModelCursorRead:
    return ReadModelCursorRead(
        projection_name=row["projection_name"],
        last_processed_id=int(row["last_processed_id"]),
        last_processed_at=row["last_processed_at"],
        version=int(row["version"]),
    )


def _grant_row_to_read(row: dict[str, Any]) -> AuthorityGrantRead:
    return AuthorityGrantRead(
        id=row["id"],
        grantee_id=row["grantee_id"],
        scope_kind=row["scope_kind"],
        scope_id=row["scope_id"],
        permissions=frozenset(row["permissions"]),
        expires_at=row["expires_at"],
        revoked_at=row["revoked_at"],
        revoked_by=row.get("revoked_by"),
        revocation_reason=row.get("revocation_reason"),
        predecessor_grant_id=row["predecessor_grant_id"],
    )


def _compute_staleness(
    cursor_lag_events: int,
    last_processed_at: datetime | None,
    *,
    now: datetime,
) -> _Staleness:
    stale_by_lag = cursor_lag_events > STALE_EVENT_THRESHOLD
    stale_by_time = (
        cursor_lag_events > 0
        and last_processed_at is not None
        and (now - last_processed_at) > STALE_TIME_THRESHOLD
    )
    is_stale = stale_by_lag or stale_by_time
    return _Staleness(
        projections=[OPERATIONAL_OVERVIEW_PROJECTION_NAME] if is_stale else [],
        since=last_processed_at if is_stale else None,
        is_stale=is_stale,
    )


def advance_operational_overview_cursor(
    db: PostgresDatabase,
    *,
    now: datetime,
    min_age_seconds: int = MIN_AGE_SECONDS,
) -> ReadModelCursorRead:
    with db.connection() as connection, connection.transaction():
        cursor = load_cursor(
            connection,
            projection_name=OPERATIONAL_OVERVIEW_PROJECTION_NAME,
            for_update=True,
        )
        if cursor is None:
            raise CursorNotSeededError(
                "read_model_cursors missing seed for "
                f"{OPERATIONAL_OVERVIEW_PROJECTION_NAME!r}"
            )

        settled_event_id = max_event_id_settled(
            connection,
            min_age_seconds=min_age_seconds,
        )
        if settled_event_id <= cursor.last_processed_id:
            return cursor

        updated = advance_cursor(
            connection,
            projection_name=OPERATIONAL_OVERVIEW_PROJECTION_NAME,
            last_processed_id=settled_event_id,
            last_processed_at=now,
            expected_version=cursor.version,
        )
    return _cursor_row_to_read(updated)


def read_operational_overview(
    db: PostgresDatabase,
    *,
    scope_kind: Literal["global", "chapter"],
    scope_id: str | None,
    actor: ActorIdentity,
    now: datetime,
) -> OperationalOverviewRead:
    if scope_kind == "chapter" and not scope_id:
        raise InvalidScopeError("scope_id is required when scope_kind='chapter'")
    if scope_kind == "global" and scope_id is not None:
        raise InvalidScopeError("scope_id must be omitted when scope_kind='global'")

    _require_scoped_authority(
        _OVERVIEW_PERMISSION,
        scope_kind=scope_kind,
        scope_id=scope_id,
        actor=actor,
        db=db,
    )

    with db.connection() as connection:
        open_applications_count = count_open_applications(
            connection,
            states=OPEN_APPLICATION_STATES,
            scope_kind=scope_kind,
            scope_id=scope_id,
        )
        open_tickets_count = count_open_tickets(
            connection,
            scope_kind=scope_kind,
            scope_id=scope_id,
        )
        pending_deferred_effects_count = (
            0
            if scope_kind == "chapter"
            else count_pending_deferred_effects(
                connection,
                statuses=PENDING_DEFERRED_EFFECT_STATUSES,
            )
        )
        permission_drift_count = count_active_drift(
            connection,
            statuses=ACTIVE_DRIFT_STATUSES,
            scope_kind=scope_kind,
            scope_id=scope_id,
        )
        visible_head_id = max_event_id_settled(
            connection, min_age_seconds=MIN_AGE_SECONDS
        )
        cursor = load_cursor(
            connection,
            projection_name=OPERATIONAL_OVERVIEW_PROJECTION_NAME,
        )

    if cursor is None:
        raise CursorNotSeededError(
            "read_model_cursors missing seed for "
            f"{OPERATIONAL_OVERVIEW_PROJECTION_NAME!r}"
        )

    staleness = _compute_staleness(
        max(0, visible_head_id - cursor.last_processed_id),
        cursor.last_processed_at,
        now=now,
    )
    return OperationalOverviewRead(
        scope_kind=scope_kind,
        scope_id=scope_id,
        open_applications_count=open_applications_count,
        open_tickets_count=open_tickets_count,
        pending_deferred_effects_count=pending_deferred_effects_count,
        permission_drift_count=permission_drift_count,
        stale_projections=staleness.projections,
        stale_since=staleness.since,
        is_stale=staleness.is_stale,
    )


def read_leadership_context(
    db: PostgresDatabase,
    *,
    member_id: str,
    actor: ActorIdentity,
    now: datetime,
) -> LeadershipContextRead:
    _require_scoped_authority(
        "leadership_context.read",
        scope_kind="global",
        scope_id=None,
        actor=actor,
        db=db,
    )

    with db.connection() as connection:
        member_text_aliases, member_uuid_aliases = _collect_member_aliases(
            connection,
            [member_id],
            synthetic_policy="reject",
        )
        active_grant_rows = list_active_grants_for_grantee_ids(
            connection,
            grantee_ids=member_text_aliases,
        )
        predecessor_ids = [
            row["predecessor_grant_id"]
            for row in active_grant_rows
            if row["predecessor_grant_id"] is not None
        ]
        predecessor_rows = {
            row["id"]: row
            for row in fetch_grants_by_ids(connection, grant_ids=predecessor_ids)
        }
        current_application_rows = list_open_applications_for_owner_ids(
            connection,
            owner_ids=member_uuid_aliases,
            states=sorted(OPEN_APPLICATION_STATES),
        )
        current_ticket_rows = list_open_tickets_for_owner_ids(
            connection,
            owner_ids=member_text_aliases,
        )
        stale_handoff: list[StaleHandoffEntry] = []
        inherited_from: list[InheritedFromEntry] = []
        for grant_row in active_grant_rows:
            predecessor_id = grant_row["predecessor_grant_id"]
            if predecessor_id is None:
                continue
            predecessor = predecessor_rows.get(predecessor_id)
            if predecessor is None:
                continue
            inherited_from.append(
                InheritedFromEntry(
                    predecessor_grant_id=predecessor["id"],
                    predecessor_member_id=predecessor["grantee_id"],
                    scope_kind=grant_row["scope_kind"],
                    scope_id=grant_row["scope_id"],
                    revoked_at=predecessor["revoked_at"],
                )
            )
            predecessor_text_aliases, predecessor_uuid_aliases = _collect_member_aliases(
                connection,
                [predecessor["grantee_id"]],
                synthetic_policy="reject",
            )
            pending_application_rows = list_open_applications_for_owner_ids(
                connection,
                owner_ids=predecessor_uuid_aliases,
                states=sorted(OPEN_APPLICATION_STATES),
                scope_kind=grant_row["scope_kind"],
                scope_id=grant_row["scope_id"],
            )
            pending_ticket_rows = list_open_tickets_for_owner_ids(
                connection,
                owner_ids=predecessor_text_aliases,
                scope_kind=grant_row["scope_kind"],
                scope_id=grant_row["scope_id"],
            )
            if pending_application_rows or pending_ticket_rows:
                stale_handoff.append(
                    StaleHandoffEntry(
                        predecessor_grant_id=predecessor["id"],
                        predecessor_member_id=predecessor["grantee_id"],
                        pending_application_ids=[row["id"] for row in pending_application_rows],
                        pending_ticket_ids=[row["id"] for row in pending_ticket_rows],
                    )
                )

        visible_head_id = max_event_id_settled(
            connection,
            min_age_seconds=MIN_AGE_SECONDS,
        )
        cursor = load_cursor(
            connection,
            projection_name=OPERATIONAL_OVERVIEW_PROJECTION_NAME,
        )

    if cursor is None:
        raise CursorNotSeededError(
            "read_model_cursors missing seed for "
            f"{OPERATIONAL_OVERVIEW_PROJECTION_NAME!r}"
        )

    staleness = _compute_staleness(
        max(0, visible_head_id - cursor.last_processed_id),
        cursor.last_processed_at,
        now=now,
    )
    return LeadershipContextRead(
        member_id=member_id,
        generated_at=now,
        active_grants=[_grant_row_to_read(row) for row in active_grant_rows],
        inherited_from=inherited_from,
        current_applications=[
            PendingApplicationRef(
                application_id=row["id"],
                owner_id=str(row["owner_id"]),
                state=str(row["state"]),
            )
            for row in current_application_rows
        ],
        current_tickets=[
            PendingTicketRef(
                ticket_id=row["id"],
                owner_id=str(row["owner_id"]),
                state=str(row["state"]),
            )
            for row in current_ticket_rows
        ],
        stale_handoff=stale_handoff,
        is_stale=bool(stale_handoff),
        projector_is_stale=staleness.is_stale,
    )


__all__ = [
    "ACTIVE_DRIFT_STATUSES",
    "CursorNotSeededError",
    "InvalidScopeError",
    "MIN_AGE_SECONDS",
    "OPEN_APPLICATION_STATES",
    "OPERATIONAL_OVERVIEW_PROJECTION_NAME",
    "PENDING_DEFERRED_EFFECT_STATUSES",
    "PROJECTION_NAMES",
    "STALE_EVENT_THRESHOLD",
    "STALE_TIME_THRESHOLD",
    "advance_operational_overview_cursor",
    "read_leadership_context",
    "read_operational_overview",
]
