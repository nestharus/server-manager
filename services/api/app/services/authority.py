from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection

from app.contracts.actor import ActorIdentity
from app.contracts.authority import (
    AuthorityDecisionRead,
    AuthorityGrantListRead,
    AuthorityGrantRead,
    AuthorityGrantTransferRequest,
    AuthorityRequirement,
    DenialReason,
    DepartingRoleEntry,
    DuplicateActiveGrantError,
    GrantAlreadyRevokedError,
    GrantAlreadyTransferredError,
    InvalidHolderIdError,
    PendingApplicationRef,
    PendingTicketRef,
    SUCCESSION_TRANSFER_REVOCATION_REASON,
    SuccessionPlanRead,
)
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.repositories.applications import ApplicationsRepository
from app.repositories.authority import AuthorityRepository
from app.repositories.chapter_roles import ChapterRolesRepository
from app.repositories.members import MembersRepository
from app.repositories.mutations import get_head_for_update
from app.repositories.roster import RosterRepository
from app.repositories.tickets import TicketsRepository
from app.services._helpers.authority import (
    _collect_actor_grant_aliases,
    _collect_member_aliases,
    _require_scoped_authority,
)
from app.services.mutations import _format_etag

OPEN_APPLICATION_STATES = frozenset(
    {
        "submitted",
        "queued",
        "claimed",
        "in_review",
        "interview",
        "waitlisted",
    }
)


def current_time() -> datetime:
    return datetime.now(UTC)


def _make_request(
    *,
    expected_version: int,
    actor: tuple[str, str],
    request_surface: str,
) -> MutationRequest:
    return MutationRequest(
        expected_version=expected_version,
        actor_kind=actor[0],
        actor_id=actor[1],
        reason_text=None,
        request_surface=request_surface,
    )


def _row_to_read(row: dict[str, Any]) -> AuthorityGrantRead:
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


def _normalize_nonblank_text(value: str, *, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be blank")
    return stripped


def _normalize_holder_id(value: str, *, field_name: str) -> str:
    holder_id = _normalize_nonblank_text(value, field_name=field_name)
    try:
        UUID(holder_id)
        return holder_id
    except ValueError:
        if holder_id.isdigit():
            return holder_id
    raise InvalidHolderIdError(f"{field_name} must be a UUID or Discord ID string")


def evaluate(
    requirement: AuthorityRequirement,
    grants: list[AuthorityGrantRead],
    *,
    at: datetime,
) -> AuthorityDecisionRead:
    has_any_grant = False
    has_scope_match = False
    has_permission_match = False
    saw_expired = False

    for grant in grants:
        has_any_grant = True
        if grant.scope_kind != requirement.scope_kind:
            continue
        if grant.scope_id is not None and grant.scope_id != requirement.scope_id:
            continue
        has_scope_match = True
        if requirement.permission not in grant.permissions:
            continue
        has_permission_match = True
        if grant.expires_at is not None and grant.expires_at <= at:
            saw_expired = True
            continue
        if grant.revoked_at is not None:
            continue
        return AuthorityDecisionRead(
            allowed=True,
            grant_id=grant.id,
            denial_reason=None,
            override_used=False,
        )

    denial_reason: DenialReason
    if not has_any_grant:
        denial_reason = "no_matching_grant"
    elif not has_scope_match:
        denial_reason = "scope_mismatch"
    elif not has_permission_match:
        denial_reason = "permission_missing"
    elif saw_expired:
        denial_reason = "grant_expired"
    else:
        denial_reason = "grant_revoked"

    return AuthorityDecisionRead(
        allowed=False,
        grant_id=None,
        denial_reason=denial_reason,
        override_used=False,
    )


class AuthorityService:
    def __init__(
        self,
        authority_repo: AuthorityRepository,
        members_repo: MembersRepository,
        roster_repo: RosterRepository,
        chapter_roles_repo: ChapterRolesRepository,
        applications_repo: ApplicationsRepository,
        tickets_repo: TicketsRepository,
        mutations_callable,
    ) -> None:
        self._authority_repo = authority_repo
        self._members_repo = members_repo
        self._roster_repo = roster_repo
        self._chapter_roles_repo = chapter_roles_repo
        self._applications_repo = applications_repo
        self._tickets_repo = tickets_repo
        self._mutations_callable = mutations_callable

    def _fetch_grant_row_on(
        self,
        connection: Connection[Any],
        grant_id: UUID,
    ) -> dict[str, Any]:
        row = self._authority_repo._fetch_grant_on(connection, grant_id=grant_id)
        if row is None:
            raise LookupError(f"authority grant {grant_id} was not found")
        return row

    def _find_active_duplicate_grant_on(
        self,
        connection: Connection[Any],
        *,
        grantee_id: str,
        scope_kind: str,
        scope_id: str | None,
        permissions: frozenset[str],
    ) -> AuthorityGrantRead | None:
        row = self._authority_repo._find_active_duplicate_grant_for_update_on(
            connection,
            grantee_id=grantee_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            permissions=permissions,
            at=current_time(),
        )
        if row is None:
            return None
        return _row_to_read(row)

    def _collect_actor_grant_aliases_on(
        self,
        connection: Connection[Any],
        actor_id: str,
    ) -> list[str]:
        return _collect_actor_grant_aliases(
            members_repo=self._members_repo,
            connection=connection,
            actor_id=actor_id,
        )

    def grant_authority(
        self,
        *,
        grantee_id: str,
        scope_kind: str,
        scope_id: str | None,
        permissions: frozenset[str],
        expires_at: datetime | None,
        predecessor_grant_id: UUID | None,
        actor: tuple[str, str],
    ) -> AuthorityGrantRead:
        with self._authority_repo.db.transaction() as connection:
            return self._grant_authority_on(
                connection,
                grantee_id=grantee_id,
                scope_kind=scope_kind,
                scope_id=scope_id,
                permissions=permissions,
                expires_at=expires_at,
                predecessor_grant_id=predecessor_grant_id,
                actor=actor,
            )

    def _grant_authority_on(
        self,
        connection: Connection[Any],
        *,
        grantee_id: str,
        scope_kind: str,
        scope_id: str | None,
        permissions: frozenset[str],
        expires_at: datetime | None,
        predecessor_grant_id: UUID | None,
        actor: tuple[str, str],
    ) -> AuthorityGrantRead:
        grant_id = uuid4()
        duplicate = self._find_active_duplicate_grant_on(
            connection,
            grantee_id=grantee_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            permissions=permissions,
        )
        if duplicate is not None:
            raise DuplicateActiveGrantError(duplicate.id)

        def mutate_projection(active_connection: Connection[Any]) -> StateChangeDraft:
            self._authority_repo._insert_grant_on(
                active_connection,
                grant_row={
                    "id": grant_id,
                    "grantee_id": grantee_id,
                    "scope_kind": scope_kind,
                    "scope_id": scope_id,
                    "permissions": permissions,
                    "expires_at": expires_at,
                    "revoked_at": None,
                    "revoked_by": None,
                    "revocation_reason": None,
                    "predecessor_grant_id": predecessor_grant_id,
                },
            )
            return StateChangeDraft(
                change_type="authority_grant.created",
                payload_json={
                    "grant_id": str(grant_id),
                    "grantee_id": grantee_id,
                    "scope_kind": scope_kind,
                    "scope_id": scope_id,
                    "permissions": sorted(permissions),
                    "expires_at": None if expires_at is None else expires_at.isoformat(),
                    "predecessor_grant_id": (
                        None
                        if predecessor_grant_id is None
                        else str(predecessor_grant_id)
                    ),
                },
            )

        self._mutations_callable(
            connection=connection,
            aggregate_type="authority_grant",
            aggregate_id=str(grant_id),
            request=_make_request(
                expected_version=0,
                actor=actor,
                request_surface="service:authority.grant",
            ),
            action_type="authority.grant",
            action_payload={},
            payload_allowlist=None,
            mutate_projection=mutate_projection,
            scope_kind=scope_kind,
            scope_id=scope_id,
        )
        return _row_to_read(self._fetch_grant_row_on(connection, grant_id))

    def revoke_authority(
        self,
        *,
        grant_id: UUID,
        actor: tuple[str, str],
        revoked_by: str,
        reason: str,
        expected_version: int | None = None,
    ) -> AuthorityGrantRead:
        with self._authority_repo.db.transaction() as connection:
            return self._revoke_authority_on(
                connection,
                grant_id=grant_id,
                actor=actor,
                revoked_by=revoked_by,
                reason=reason,
                expected_version=expected_version,
            )

    def _revoke_authority_on(
        self,
        connection: Connection[Any],
        *,
        grant_id: UUID,
        actor: tuple[str, str],
        revoked_by: str,
        reason: str,
        expected_version: int | None = None,
    ) -> AuthorityGrantRead:
        row = self._fetch_grant_row_on(connection, grant_id)
        revoked_at = current_time()

        def mutate_projection(active_connection: Connection[Any]) -> StateChangeDraft:
            updated = self._authority_repo._update_revoked_with_reason_on(
                active_connection,
                grant_id=grant_id,
                revoked_at=revoked_at,
                revoked_by=revoked_by,
                revocation_reason=reason,
            )
            if updated != 1:
                raise GrantAlreadyRevokedError(grant_id)
            return StateChangeDraft(
                change_type="authority_grant.revoked",
                payload_json={
                    "grant_id": str(grant_id),
                    "revoked_at": revoked_at.isoformat(),
                    "revoked_by": revoked_by,
                    "revocation_reason": reason,
                },
            )

        self._mutations_callable(
            connection=connection,
            aggregate_type="authority_grant",
            aggregate_id=str(grant_id),
            request=_make_request(
                expected_version=(
                    int(row["current_seq"])
                    if expected_version is None
                    else expected_version
                ),
                actor=actor,
                request_surface="service:authority.revoke",
            ),
            action_type="authority.revoke",
            action_payload={},
            payload_allowlist=None,
            mutate_projection=mutate_projection,
            scope_kind=row["scope_kind"],
            scope_id=row["scope_id"],
        )
        return _row_to_read(self._fetch_grant_row_on(connection, grant_id))

    def require_scoped_authority(
        self,
        permission: str,
        *,
        scope_kind: str,
        scope_id: str | None,
        actor: ActorIdentity,
    ) -> None:
        _require_scoped_authority(
            authority_repo=self._authority_repo,
            members_repo=self._members_repo,
            permission=permission,
            scope_kind=scope_kind,
            scope_id=scope_id,
            actor=actor,
        )

    def list_authority_grants(
        self,
        *,
        grantee_id: str,
        scope_kind: str | None = None,
        scope_id: str | None = None,
        include_revoked: bool = False,
        limit: int = 50,
        after_id: UUID | None = None,
    ) -> AuthorityGrantListRead:
        rows = self._authority_repo.list_grants(
            grantee_id=grantee_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            include_revoked=include_revoked,
            limit=limit + 1,
            after_id=after_id,
        )
        items = [_row_to_read(row) for row in rows[:limit]]
        next_cursor = items[-1].id if len(rows) > limit and items else None
        return AuthorityGrantListRead(items=items, next_cursor=next_cursor)

    def get_authority_grant(
        self,
        *,
        grant_id: UUID,
    ) -> tuple[AuthorityGrantRead, str]:
        with self._authority_repo.db.connection() as connection:
            row = self._fetch_grant_row_on(connection, grant_id)
        return _row_to_read(row), _format_etag(int(row["current_seq"]))

    def compute_succession_plan(
        self,
        *,
        chapter_id: str,
        actor: ActorIdentity,
    ) -> SuccessionPlanRead:
        with self._authority_repo.db.connection() as connection:
            return self._compute_succession_plan_on(
                connection,
                chapter_id=chapter_id,
                actor=actor,
            )

    def _compute_succession_plan_on(
        self,
        connection: Connection[Any],
        *,
        chapter_id: str,
        actor: ActorIdentity,
    ) -> SuccessionPlanRead:
        _require_scoped_authority(
            authority_repo=self._authority_repo,
            members_repo=self._members_repo,
            permission="succession_plan.read",
            scope_kind="chapter",
            scope_id=chapter_id,
            actor=actor,
            connection=connection,
        )
        roles = self._chapter_roles_repo._list_succession_triggering_roles_on(
            connection,
            chapter_id=chapter_id,
        )
        holders = {
            row["role_id"]: row
            for row in self._roster_repo._list_latest_role_holders_on(
                connection,
                chapter_id=chapter_id,
                role_ids=[row["id"] for row in roles],
            )
        }

        departing_roles: list[DepartingRoleEntry] = []
        holder_ids: list[str] = []
        for role in roles:
            holder = holders.get(role["id"])
            holder_member_id: str | None = None
            departure_signal = "active"
            if holder is not None:
                holder_member_id = _normalize_holder_id(
                    holder["member_id"],
                    field_name="holder_id",
                )
                holder_ids.append(holder_member_id)
                if holder["status"] == "removed":
                    departure_signal = "roster_removed"
            departing_roles.append(
                DepartingRoleEntry(
                    role_id=role["id"],
                    holder_member_id=holder_member_id,
                    triggers_succession=bool(role["triggers_succession"]),
                    departure_signal=departure_signal,  # type: ignore[arg-type]
                )
            )

        grant_aliases, application_owner_ids = _collect_member_aliases(
            members_repo=self._members_repo,
            connection=connection,
            member_ids=holder_ids,
            synthetic_policy="omit",
        )
        grant_rows = self._authority_repo._list_active_grants_for_grantee_ids_on(
            connection,
            grantee_ids=grant_aliases,
            scope_kind="chapter",
            scope_id=chapter_id,
        )
        application_rows = (
            self._applications_repo._list_open_applications_for_owner_ids_on(
                connection,
                owner_ids=application_owner_ids,
                states=sorted(OPEN_APPLICATION_STATES),
                scope_kind="chapter",
                scope_id=chapter_id,
            )
        )
        ticket_rows = self._tickets_repo._list_open_tickets_for_owner_ids_on(
            connection,
            owner_ids=grant_aliases,
            scope_kind="chapter",
            scope_id=chapter_id,
        )

        return SuccessionPlanRead(
            chapter_id=chapter_id,
            generated_at=current_time(),
            departing_roles=departing_roles,
            affected_grants=[_row_to_read(row) for row in grant_rows],
            pending_applications=[
                PendingApplicationRef(
                    application_id=row["id"],
                    owner_id=str(row["owner_id"]),
                    state=str(row["state"]),
                )
                for row in application_rows
            ],
            pending_tickets=[
                PendingTicketRef(
                    ticket_id=row["id"],
                    owner_id=str(row["owner_id"]),
                    state=str(row["state"]),
                )
                for row in ticket_rows
            ],
            successor_designated=False,
            successor_member_id=None,
        )

    def transfer_authority_grant(
        self,
        *,
        grant_id: UUID,
        expected_version: int,
        request: AuthorityGrantTransferRequest,
        actor: ActorIdentity,
    ) -> tuple[AuthorityGrantRead, MutationResult, bool]:
        successor_id = _normalize_holder_id(
            request.successor_id,
            field_name="successor_id",
        )
        _normalize_nonblank_text(request.reason, field_name="reason")

        with self._authority_repo.db.connection() as connection:
            predecessor = self._fetch_grant_row_on(connection, grant_id)

        self.require_scoped_authority(
            "authority_grant.transfer",
            scope_kind=predecessor["scope_kind"],
            scope_id=predecessor["scope_id"],
            actor=actor,
        )

        with self._authority_repo.db.transaction() as connection:
            get_head_for_update(
                connection,
                aggregate_type="authority_grant",
                aggregate_id=str(grant_id),
            )
            existing_successor = self._authority_repo._find_successor_grant_on(
                connection,
                predecessor_grant_id=grant_id,
            )
            if existing_successor is not None:
                if existing_successor["grantee_id"] == successor_id:
                    successor_row = self._fetch_grant_row_on(
                        connection,
                        existing_successor["id"],
                    )
                    successor_version = int(successor_row["current_seq"])
                    return (
                        _row_to_read(successor_row),
                        MutationResult(
                            version=successor_version,
                            etag=_format_etag(successor_version),
                        ),
                        False,
                    )
                raise GrantAlreadyTransferredError(existing_successor["id"])
            if predecessor["revoked_at"] is not None:
                raise GrantAlreadyRevokedError(grant_id)

            successor = self._grant_authority_on(
                connection,
                grantee_id=successor_id,
                scope_kind=predecessor["scope_kind"],
                scope_id=predecessor["scope_id"],
                permissions=frozenset(predecessor["permissions"]),
                expires_at=predecessor["expires_at"],
                predecessor_grant_id=grant_id,
                actor=(actor.actor_kind, actor.actor_id),
            )
            self._revoke_authority_on(
                connection,
                grant_id=grant_id,
                actor=(actor.actor_kind, actor.actor_id),
                revoked_by=actor.actor_id,
                reason=SUCCESSION_TRANSFER_REVOCATION_REASON,
                expected_version=expected_version,
            )
            successor_row = self._fetch_grant_row_on(connection, successor.id)
            successor_version = int(successor_row["current_seq"])
            return (
                successor,
                MutationResult(
                    version=successor_version,
                    etag=_format_etag(successor_version),
                ),
                True,
            )

    def list_grants_for_grantee(
        self,
        *,
        grantee_id: str,
    ) -> list[AuthorityGrantRead]:
        rows = self._authority_repo.list_grants(
            grantee_id=grantee_id,
            include_revoked=True,
            limit=None,
            after_id=None,
        )
        return [_row_to_read(row) for row in rows]

    def get_authority_grants_by_ids(
        self,
        *,
        grant_ids: list[UUID],
    ) -> list[AuthorityGrantRead]:
        rows = self._authority_repo.fetch_grants_by_ids(grant_ids=grant_ids)
        return [_row_to_read(row) for row in rows]


__all__ = [
    "OPEN_APPLICATION_STATES",
    "AuthorityService",
    "current_time",
    "evaluate",
]
