"""Contract tests for WU-004: authority grant foundation.

Pins the evaluator's allow/deny table, the grant/revoke round-trip, and
the documented JSON shape that AC2 requires. The evaluator tests are
pure over manufactured ``AuthorityGrantRead`` values; the persistence
tests round-trip through real Postgres via shared testcontainers.

Actor tuple convention: ``actor=(actor_kind, actor_id)``. The proposal
says ``actor`` is a single parameter passed through to ``mutate_entity``,
which needs both halves to build ``MutationRequest.actor_kind/actor_id``.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.authority import (
    AuthorityDecisionRead,
    AuthorityGrantRead,
    AuthorityRequirement,
    GrantAlreadyRevokedError,
)
from app.core.context import use_audit_context
from app.repositories.applications import ApplicationsRepository
from app.repositories.authority import AuthorityRepository
from app.repositories.chapter_roles import ChapterRolesRepository
from app.repositories.db import PostgresDatabase
from app.repositories.members import MembersRepository
from app.repositories.roster import RosterRepository
from app.repositories.tickets import TicketsRepository
from app.services.authority import (
    AuthorityService,
    current_time,
    evaluate,
)
from app.services.mutations import mutate_entity


ACTOR = ("user", "admin")


def _make_audit_context() -> AuditContextRead:
    cid = uuid4()
    headers = CorrelationHeadersRead(x_correlation_id=cid, x_causation_id=None)
    return AuditContextRead(correlation_id=cid, causation_id=None, headers=headers)


def _fetch_grants(database_url: str) -> list[dict[str, Any]]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT id, grantee_id, scope_kind, scope_id, permissions,
                   expires_at, revoked_at, predecessor_grant_id, created_at
            FROM authority_grants
            WHERE grantee_id = 'u1'
            ORDER BY created_at, id
            """
        ).fetchall()


def _make_grant(
    *,
    scope_kind: str = "chapter",
    scope_id: str | None = "ch-1",
    permissions: frozenset[str] = frozenset({"chapter.manage"}),
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
    predecessor_grant_id: UUID | None = None,
) -> AuthorityGrantRead:
    return AuthorityGrantRead(
        id=uuid4(),
        grantee_id="u1",
        scope_kind=scope_kind,
        scope_id=scope_id,
        permissions=permissions,
        expires_at=expires_at,
        revoked_at=revoked_at,
        predecessor_grant_id=predecessor_grant_id,
    )


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


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Grant persistence (AC2 — "grants persist scope, permission set, ...")
# ---------------------------------------------------------------------------


def test_grant_authority_creates_persisted_row_with_scope_and_permissions(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """``grant_authority()`` must persist a row whose scope, permission set,
    and predecessor link match the call arguments exactly."""

    service = _authority_service(governance_db)
    with use_audit_context(_make_audit_context()):
        grant = service.grant_authority(
            grantee_id="u1",
            scope_kind="chapter",
            scope_id="ch-1",
            permissions=frozenset({"chapter.manage"}),
            expires_at=None,
            predecessor_grant_id=None,
            actor=ACTOR,
        )

    # SLICE-008 D2: grant_authority() now returns AuthorityGrantRead. The
    # version/ETag live on the HTTP response headers, not on the business
    # return value.
    assert isinstance(grant, AuthorityGrantRead)
    assert grant.grantee_id == "u1"
    assert grant.scope_kind == "chapter"
    assert grant.scope_id == "ch-1"
    assert grant.permissions == frozenset({"chapter.manage"})
    assert grant.expires_at is None
    assert grant.revoked_at is None
    assert grant.predecessor_grant_id is None

    rows = _fetch_grants(governance_dsn)
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == grant.id
    assert row["grantee_id"] == "u1"
    assert row["scope_kind"] == "chapter"
    assert row["scope_id"] == "ch-1"
    assert set(row["permissions"]) == {"chapter.manage"}
    assert row["expires_at"] is None
    assert row["revoked_at"] is None
    assert row["predecessor_grant_id"] is None


# ---------------------------------------------------------------------------
# Evaluator allow/deny table
# ---------------------------------------------------------------------------


def test_evaluate_allows_matching_scope_and_permission() -> None:
    """One active grant whose scope_kind, scope_id, and permission all match
    the requirement must produce ``AuthorityDecision(allowed=True)``."""

    grant = _make_grant(
        scope_kind="chapter",
        scope_id="ch-1",
        permissions=frozenset({"chapter.manage"}),
    )
    requirement = AuthorityRequirement(
        scope_kind="chapter",
        scope_id="ch-1",
        permission="chapter.manage",
    )

    decision = evaluate(requirement=requirement, grants=[grant], at=current_time())

    assert isinstance(decision, AuthorityDecisionRead)
    assert decision.allowed is True
    assert decision.grant_id == grant.id
    assert decision.denial_reason is None
    assert decision.override_used is False


def test_evaluate_denies_revoked_grants() -> None:
    """A revoked grant must not satisfy a requirement."""

    now = current_time()
    grant = _make_grant(revoked_at=now - timedelta(minutes=1))
    requirement = AuthorityRequirement(
        scope_kind="chapter",
        scope_id="ch-1",
        permission="chapter.manage",
    )

    decision = evaluate(requirement=requirement, grants=[grant], at=now)

    assert decision.allowed is False


def test_evaluate_denies_expired_grants() -> None:
    """A grant whose ``expires_at`` is in the past must not satisfy a
    requirement, even if the scope and permission match."""

    now = current_time()
    grant = _make_grant(expires_at=now - timedelta(seconds=1))
    requirement = AuthorityRequirement(
        scope_kind="chapter",
        scope_id="ch-1",
        permission="chapter.manage",
    )

    decision = evaluate(requirement=requirement, grants=[grant], at=now)

    assert decision.allowed is False


def test_evaluate_denies_scope_mismatch() -> None:
    """A grant for ``chapter/ch-1`` must not satisfy a requirement for
    ``chapter/ch-2``."""

    grant = _make_grant(scope_id="ch-1")
    requirement = AuthorityRequirement(
        scope_kind="chapter",
        scope_id="ch-2",
        permission="chapter.manage",
    )

    decision = evaluate(requirement=requirement, grants=[grant], at=current_time())

    assert decision.allowed is False


def test_evaluate_denies_permission_not_in_set() -> None:
    """A grant whose permission set does not contain the requirement
    permission must not satisfy the requirement — exact set membership,
    no prefix/wildcard."""

    grant = _make_grant(permissions=frozenset({"chapter.read"}))
    requirement = AuthorityRequirement(
        scope_kind="chapter",
        scope_id="ch-1",
        permission="chapter.manage",
    )

    decision = evaluate(requirement=requirement, grants=[grant], at=current_time())

    assert decision.allowed is False


def test_evaluate_allows_null_scope_id_for_any_scope_id() -> None:
    """A grant with ``scope_id=None`` ("any chapter of this kind") must
    satisfy a requirement with a specific ``scope_id`` of the same kind."""

    grant = _make_grant(scope_id=None)
    requirement = AuthorityRequirement(
        scope_kind="chapter",
        scope_id="ch-anything",
        permission="chapter.manage",
    )

    decision = evaluate(requirement=requirement, grants=[grant], at=current_time())

    assert decision.allowed is True


# ---------------------------------------------------------------------------
# Revoke idempotency guard
# ---------------------------------------------------------------------------


def test_revoke_authority_second_call_raises_grant_already_revoked_error(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """The revoke path uses ``WHERE id = %s AND revoked_at IS NULL``; a
    second revoke call sees a zero rowcount and must raise
    ``GrantAlreadyRevokedError``."""

    service = _authority_service(governance_db)
    with use_audit_context(_make_audit_context()):
        service.grant_authority(
            grantee_id="u1",
            scope_kind="chapter",
            scope_id="ch-1",
            permissions=frozenset({"chapter.manage"}),
            expires_at=None,
            predecessor_grant_id=None,
            actor=ACTOR,
        )

    rows = _fetch_grants(governance_dsn)
    assert len(rows) == 1
    grant_id: UUID = rows[0]["id"]

    with use_audit_context(_make_audit_context()):
        service.revoke_authority(
            grant_id=grant_id,
            actor=ACTOR,
            revoked_by="admin",
            reason="cleanup",
        )

        with pytest.raises(GrantAlreadyRevokedError):
            service.revoke_authority(
                grant_id=grant_id,
                actor=ACTOR,
                revoked_by="admin",
                reason="second attempt",
            )


# ---------------------------------------------------------------------------
# Contract-shape pins (AC2 last bullet, synthesis D7)
# ---------------------------------------------------------------------------


def test_authority_grant_read_does_not_expose_body_version_field() -> None:
    """Synthesis D7: governance read contracts must NOT expose body-level
    ``version`` fields — concurrency stays in ``MutationResult.etag``.
    """

    assert "version" not in AuthorityGrantRead.model_fields


def test_authority_grant_round_trips_to_documented_json() -> None:
    """AC2 last bullet: round-trip through JSON preserves every field of
    the documented shape and does NOT introduce implementation-only fields.
    """

    original = _make_grant(
        scope_kind="chapter",
        scope_id="ch-1",
        permissions=frozenset({"chapter.manage", "chapter.read"}),
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        revoked_at=None,
        predecessor_grant_id=uuid4(),
    )

    restored = AuthorityGrantRead.model_validate_json(original.model_dump_json())

    assert restored.id == original.id
    assert restored.grantee_id == original.grantee_id
    assert restored.scope_kind == original.scope_kind
    assert restored.scope_id == original.scope_id
    assert restored.permissions == original.permissions
    assert restored.expires_at == original.expires_at
    assert restored.revoked_at == original.revoked_at
    assert restored.predecessor_grant_id == original.predecessor_grant_id


def test_predecessor_grant_id_self_reference_is_rejected_at_db(
    governance_dsn: str,
) -> None:
    """The table-level ``CHECK (predecessor_grant_id != id)`` must block
    self-referential rows at INSERT time, even against raw SQL."""

    row_id = uuid4()
    with psycopg.connect(governance_dsn, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                """
                INSERT INTO authority_grants (
                    id, grantee_id, scope_kind, scope_id,
                    permissions, expires_at, revoked_at,
                    predecessor_grant_id
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                """,
                (
                    row_id,
                    "u1",
                    "chapter",
                    "ch-1",
                    '["chapter.manage"]',
                    None,
                    None,
                    row_id,
                ),
            )
