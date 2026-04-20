"""Contract tests for WU-005: policy version preview-confirm foundation.

Pins AC3: preview is read-only, stale-preview confirm raises a typed
``PolicyPreviewTokenMismatchError`` (distinct from OCC staleness),
confirm with a matching digest persists the next version, and
policy-version read contracts do not reintroduce body-level version
fields.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from pydantic import ValidationError
from psycopg.rows import dict_row

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.actor import ActorIdentity
from app.contracts.mutations import StaleMutationError
from app.contracts.policies import (
    PolicyConfirmRequest,
    PolicyPreviewRequest,
    PolicyPreviewTokenMismatchError,
    PolicyVersionRead,
)
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.policies import confirm as policy_confirm
from app.services.policies import preview as policy_preview


POLICY_TYPE = "test_policy"


def _make_audit_context() -> AuditContextRead:
    cid = uuid4()
    headers = CorrelationHeadersRead(x_correlation_id=cid, x_causation_id=None)
    return AuditContextRead(correlation_id=cid, causation_id=None, headers=headers)


def _expected_aggregate_id(
    policy_type: str,
    scope_kind: str,
    scope_id: str | None,
) -> str:
    """Mirror ``_policy_aggregate_id`` from proposal §3 WU-005 line 184–186.

    Using ``|`` as separator and empty-string sentinel for ``None`` scope_id.
    """

    tail = scope_id if scope_id is not None else ""
    return f"{policy_type}|{scope_kind}|{tail}"


def _seed_policy_version(
    database_url: str,
    *,
    policy_type: str,
    scope_kind: str,
    scope_id: str | None,
    version_number: int,
    content: dict[str, Any],
) -> UUID:
    """Direct-INSERT a ``policy_versions`` row + ``aggregate_heads`` entry so
    preview/confirm see a known baseline."""

    row_id = uuid4()
    aggregate_id = _expected_aggregate_id(policy_type, scope_kind, scope_id)

    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO policy_versions (
                id, policy_type, scope_kind, scope_id,
                version_number, content, effective_at
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                row_id,
                policy_type,
                scope_kind,
                scope_id,
                version_number,
                json.dumps(content),
                datetime.now(UTC),
            ),
        )
        conn.execute(
            """
            INSERT INTO aggregate_heads (
                aggregate_type, aggregate_id, current_seq, latest_change_id
            )
            VALUES (%s, %s, %s, NULL)
            """,
            ("policy_version", aggregate_id, version_number),
        )

    return row_id


def _fetch_policy_versions(database_url: str) -> list[dict[str, Any]]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT id, policy_type, scope_kind, scope_id,
                   version_number, content, effective_at
            FROM policy_versions
            ORDER BY version_number ASC, id ASC
            """
        ).fetchall()


def _fetch_activity_actions(database_url: str) -> list[dict[str, Any]]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT id, aggregate_type, aggregate_id, action_type, status,
                   actor_kind, actor_id
            FROM activity_actions
            ORDER BY id
            """
        ).fetchall()


@pytest.fixture()
def governance_db(governance_dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn=governance_dsn)
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# preview() read-only semantics (AC3 first bullet)
# ---------------------------------------------------------------------------


def test_preview_is_read_only_and_returns_current_version_and_flat_diff(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """``preview(...)`` must not mutate persisted state and must return the
    current version, a flat top-level key diff, and a non-empty hex
    ``preview_token``."""

    existing_content = {"a": 1, "b": 2}
    _seed_policy_version(
        governance_dsn,
        policy_type=POLICY_TYPE,
        scope_kind="global",
        scope_id=None,
        version_number=5,
        content=existing_content,
    )

    before_rows = _fetch_policy_versions(governance_dsn)
    assert len(before_rows) == 1

    request = PolicyPreviewRequest(
        policy_type=POLICY_TYPE,
        scope_kind="global",
        scope_id=None,
        expected_current_version=5,
        content={"a": 1, "b": 3, "c": 4},
    )

    result = policy_preview(governance_db, request)

    after_rows = _fetch_policy_versions(governance_dsn)
    assert after_rows == before_rows, "preview must not write to policy_versions"

    assert result.current_version == 5
    assert isinstance(result.preview_token, str)
    assert result.preview_token != ""
    # Hex-only: blake2b hexdigest over canonical bytes.
    int(result.preview_token, 16)
    assert isinstance(result.affected_objects, list)
    # Flat top-level keys 'b' (changed) and 'c' (added) both differ.
    assert len(result.affected_objects) == 2


def test_preview_rejects_non_json_serializable_content() -> None:
    """The model_validator on ``PolicyPreviewRequest`` must reject content
    that ``json.dumps(..., allow_nan=False)`` cannot canonicalize — NaN,
    ``Infinity``, and non-string dict keys all fail here.
    """

    with pytest.raises(ValidationError):
        PolicyPreviewRequest(
            policy_type=POLICY_TYPE,
            scope_kind="global",
            scope_id=None,
            expected_current_version=0,
            content={"k": float("nan")},
        )


# ---------------------------------------------------------------------------
# confirm() digest-mismatch path (AC3 second bullet, Scope F-1 trace)
# ---------------------------------------------------------------------------


def test_confirm_recomputes_digest_and_raises_policy_preview_token_mismatch_error(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """If the confirm payload differs from the preview that issued the
    token, ``confirm(...)`` must raise ``PolicyPreviewTokenMismatchError``
    — distinct from OCC staleness.
    """

    existing_content = {"a": 1}
    _seed_policy_version(
        governance_dsn,
        policy_type=POLICY_TYPE,
        scope_kind="global",
        scope_id=None,
        version_number=1,
        content=existing_content,
    )

    preview_content = {"a": 2}
    preview_request = PolicyPreviewRequest(
        policy_type=POLICY_TYPE,
        scope_kind="global",
        scope_id=None,
        expected_current_version=1,
        content=preview_content,
    )

    token = policy_preview(governance_db, preview_request).preview_token

    # Caller tampers with content between preview and confirm.
    mutated_content = {"a": 99}
    confirm_request = PolicyConfirmRequest(
        preview_token=token,
        policy_type=POLICY_TYPE,
        scope_kind="global",
        scope_id=None,
        expected_current_version=1,
        content=mutated_content,
    )

    with use_audit_context(_make_audit_context()):
        with pytest.raises(PolicyPreviewTokenMismatchError):
            policy_confirm(
                governance_db,
                confirm_request,
                actor=ActorIdentity(actor_kind="user", actor_id="admin"),
            )


def test_confirm_with_matching_digest_persists_next_version(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """AC3 implied: when preview and confirm agree, the confirm must append
    a new ``policy_versions`` row at ``version_number = expected + 1`` and
    return ``(PolicyVersionRead, etag)`` with that version."""

    _seed_policy_version(
        governance_dsn,
        policy_type=POLICY_TYPE,
        scope_kind="global",
        scope_id=None,
        version_number=2,
        content={"a": 1},
    )

    next_content = {"a": 2}
    preview_request = PolicyPreviewRequest(
        policy_type=POLICY_TYPE,
        scope_kind="global",
        scope_id=None,
        expected_current_version=2,
        content=next_content,
    )
    token = policy_preview(governance_db, preview_request).preview_token

    confirm_request = PolicyConfirmRequest(
        preview_token=token,
        policy_type=POLICY_TYPE,
        scope_kind="global",
        scope_id=None,
        expected_current_version=2,
        content=next_content,
    )

    with use_audit_context(_make_audit_context()):
        created, etag = policy_confirm(
            governance_db,
            confirm_request,
            actor=ActorIdentity(actor_kind="user", actor_id="admin"),
        )

    assert created.version_number == 3
    assert etag == '"3"'

    versions = _fetch_policy_versions(governance_dsn)
    # The seeded row plus the new confirmed row.
    assert len(versions) == 2
    assert versions[-1]["version_number"] == 3


# ---------------------------------------------------------------------------
# Stale-preview OCC distinction (Scope F-2 trace)
# ---------------------------------------------------------------------------


def test_confirm_with_stale_expected_version_raises_stale_mutation_error(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """Two callers preview at version 1. First commits → aggregate_heads at
    2. Second calls confirm with the same token (digest matches its own
    preview input), but ``mutate_entity()``'s OCC gate sees
    ``expected_version=1`` vs ``current_seq=2`` and raises
    ``StaleMutationError`` — not ``PolicyPreviewTokenMismatchError``.
    """

    _seed_policy_version(
        governance_dsn,
        policy_type=POLICY_TYPE,
        scope_kind="global",
        scope_id=None,
        version_number=1,
        content={"a": 1},
    )

    preview_content = {"a": 2}
    preview_request = PolicyPreviewRequest(
        policy_type=POLICY_TYPE,
        scope_kind="global",
        scope_id=None,
        expected_current_version=1,
        content=preview_content,
    )
    token = policy_preview(governance_db, preview_request).preview_token

    confirm_request = PolicyConfirmRequest(
        preview_token=token,
        policy_type=POLICY_TYPE,
        scope_kind="global",
        scope_id=None,
        expected_current_version=1,
        content=preview_content,
    )

    # First caller wins.
    with use_audit_context(_make_audit_context()):
        policy_confirm(
            governance_db,
            confirm_request,
            actor=ActorIdentity(actor_kind="user", actor_id="admin"),
        )

    # Second caller replays the same confirm: digest still matches the
    # preview input, but aggregate_heads has advanced past v1.
    with use_audit_context(_make_audit_context()):
        with pytest.raises(StaleMutationError):
            policy_confirm(
                governance_db,
                confirm_request,
                actor=ActorIdentity(actor_kind="user", actor_id="admin"),
            )


# ---------------------------------------------------------------------------
# Aggregate-id stability (preview vs confirm formatter convergence)
# ---------------------------------------------------------------------------


def test_policy_aggregate_id_is_stable_across_preview_and_confirm(
    governance_db: PostgresDatabase,
    governance_dsn: str,
) -> None:
    """The aggregate-id formatter used by preview and confirm must agree so
    the OCC gate targets the same ``aggregate_heads`` row. After a
    successful confirm, the ``activity_actions`` row's ``aggregate_id``
    equals the documented formatter output.
    """

    _seed_policy_version(
        governance_dsn,
        policy_type=POLICY_TYPE,
        scope_kind="global",
        scope_id=None,
        version_number=1,
        content={"a": 1},
    )

    expected_aggregate_id = _expected_aggregate_id(POLICY_TYPE, "global", None)

    preview_request = PolicyPreviewRequest(
        policy_type=POLICY_TYPE,
        scope_kind="global",
        scope_id=None,
        expected_current_version=1,
        content={"a": 2},
    )
    token = policy_preview(governance_db, preview_request).preview_token

    confirm_request = PolicyConfirmRequest(
        preview_token=token,
        policy_type=POLICY_TYPE,
        scope_kind="global",
        scope_id=None,
        expected_current_version=1,
        content={"a": 2},
    )
    with use_audit_context(_make_audit_context()):
        policy_confirm(
            governance_db,
            confirm_request,
            actor=ActorIdentity(actor_kind="user", actor_id="admin"),
        )

    actions = _fetch_activity_actions(governance_dsn)
    policy_actions = [
        a for a in actions if a["aggregate_type"] == "policy_version"
    ]
    assert len(policy_actions) >= 1
    for action in policy_actions:
        assert action["aggregate_id"] == expected_aggregate_id


# ---------------------------------------------------------------------------
# Contract-shape pins (AC3 last bullet, synthesis D7)
# ---------------------------------------------------------------------------


def test_policy_version_read_does_not_expose_body_version_field() -> None:
    """``PolicyVersionRead`` carries ``version_number`` (aggregate-seq
    lineage) but must NOT carry a body-level ``version`` field."""

    fields = PolicyVersionRead.model_fields
    assert "version" not in fields
    assert "version_number" in fields


def test_policy_version_round_trips_to_documented_json() -> None:
    """AC3 last bullet: the ``PolicyVersionRead`` shape round-trips through
    JSON preserving scope and version lineage without adding
    implementation-only fields."""

    original = PolicyVersionRead(
        id=uuid4(),
        policy_type=POLICY_TYPE,
        scope_kind="chapter",
        scope_id="ch-1",
        version_number=7,
        effective_at=datetime(2026, 4, 19, tzinfo=UTC),
    )

    restored = PolicyVersionRead.model_validate_json(original.model_dump_json())

    assert restored.id == original.id
    assert restored.policy_type == original.policy_type
    assert restored.scope_kind == original.scope_kind
    assert restored.scope_id == original.scope_id
    assert restored.version_number == original.version_number
    assert restored.effective_at == original.effective_at
