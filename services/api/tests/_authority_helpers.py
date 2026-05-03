from __future__ import annotations

from datetime import datetime
from functools import partial
from typing import Any
from uuid import UUID

from psycopg import Connection

from app.contracts.actor import ActorIdentity
from app.contracts.members import MemberCreate
from app.repositories.applications import ApplicationsRepository
from app.repositories.authority import AuthorityRepository
from app.repositories.chapter_roles import ChapterRolesRepository
from app.repositories.db import PostgresDatabase
from app.repositories.members import MembersRepository
from app.repositories.roster import RosterRepository
from app.repositories.tickets import TicketsRepository
from app.services.authority import AuthorityService
from app.services.members import MembersService
from app.services.mutations import mutate_entity


def _authority_service(db: PostgresDatabase) -> AuthorityService:
    return AuthorityService(
        authority_repo=AuthorityRepository(db),
        members_repo=MembersRepository(db),
        roster_repo=RosterRepository(db),
        chapter_roles_repo=ChapterRolesRepository(db),
        applications_repo=ApplicationsRepository(db),
        tickets_repo=TicketsRepository(db),
        mutations_callable=partial(mutate_entity, db=db),
    )


def grant_authority(
    db: PostgresDatabase,
    *,
    grantee_id: str,
    scope_kind: str,
    scope_id: str | None,
    permissions: frozenset[str],
    expires_at: datetime | None,
    predecessor_grant_id: UUID | None,
    actor: tuple[str, str],
    connection: Connection[Any] | None = None,
):
    service = _authority_service(db)
    if connection is not None:
        return service._grant_authority_on(
            connection,
            grantee_id=grantee_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            permissions=permissions,
            expires_at=expires_at,
            predecessor_grant_id=predecessor_grant_id,
            actor=actor,
        )
    return service.grant_authority(
        grantee_id=grantee_id,
        scope_kind=scope_kind,
        scope_id=scope_id,
        permissions=permissions,
        expires_at=expires_at,
        predecessor_grant_id=predecessor_grant_id,
        actor=actor,
    )


def revoke_authority(
    db: PostgresDatabase,
    *,
    grant_id: UUID,
    actor: tuple[str, str],
    revoked_by: str,
    reason: str,
    connection: Connection[Any] | None = None,
):
    service = _authority_service(db)
    if connection is not None:
        return service._revoke_authority_on(
            connection,
            grant_id=grant_id,
            actor=actor,
            revoked_by=revoked_by,
            reason=reason,
        )
    return service.revoke_authority(
        grant_id=grant_id,
        actor=actor,
        revoked_by=revoked_by,
        reason=reason,
    )


def create_or_get_member(
    db: PostgresDatabase,
    request: MemberCreate,
    actor: ActorIdentity,
):
    service = MembersService(
        members_repo=MembersRepository(db),
        mutations_callable=partial(mutate_entity, db=db),
    )
    return service.create_or_get_member(request, actor)
