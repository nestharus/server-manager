from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.rows import dict_row


AlembicRunner = Callable[..., subprocess.CompletedProcess[str]]


def _assert_alembic_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        "alembic command failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def _members_kind_revision(repo_root: Path) -> tuple[str, str]:
    candidates = [
        path
        for path in (repo_root / "migrations/versions").glob("*.py")
        if "members_kind" in path.name
        or "members kind" in path.read_text(encoding="utf-8").lower()
    ]
    assert candidates, "missing Alembic migration for members kind discriminator"
    assert len(candidates) == 1, f"ambiguous members kind migrations: {candidates}"

    source = candidates[0].read_text(encoding="utf-8")
    revision = re.search(r'^revision\s*=\s*["\']([^"\']+)["\']', source, re.M)
    down_revision = re.search(r'^down_revision\s*=\s*["\']([^"\']+)["\']', source, re.M)
    assert revision is not None, f"missing revision in {candidates[0]}"
    assert down_revision is not None, f"missing down_revision in {candidates[0]}"
    return revision.group(1), down_revision.group(1)


def _column_metadata(database_url: str) -> dict[str, str | None] | None:
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        row = connection.execute(
            """
            SELECT data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'members'
              AND column_name = 'kind'
            """
        ).fetchone()
    return None if row is None else dict(row)


def _kind_check_constraints(database_url: str) -> list[dict[str, str]]:
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        return [
            dict(row)
            for row in connection.execute(
                """
                SELECT c.conname, pg_get_constraintdef(c.oid) AS definition
                FROM pg_constraint AS c
                JOIN pg_class AS t ON t.oid = c.conrelid
                JOIN pg_namespace AS n ON n.oid = t.relnamespace
                WHERE n.nspname = 'public'
                  AND t.relname = 'members'
                  AND c.contype = 'c'
                  AND pg_get_constraintdef(c.oid) LIKE '%kind%'
                ORDER BY c.conname
                """
            ).fetchall()
        ]


def _insert_legacy_member(
    connection: psycopg.Connection[object],
    *,
    member_id: UUID,
    discord_user_id: str,
) -> None:
    connection.execute(
        """
        INSERT INTO members (id, discord_user_id, joined_at, status)
        VALUES (%s, %s, %s, 'active')
        """,
        (member_id, discord_user_id, datetime.now(UTC)),
    )


def _member_kinds(database_url: str) -> dict[str, str]:
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        return {
            str(row["discord_user_id"]): str(row["kind"])
            for row in connection.execute(
                """
                SELECT discord_user_id, kind
                FROM members
                ORDER BY discord_user_id
                """
            ).fetchall()
        }


def test_members_kind_migration_adds_not_null_checked_column(
    fresh_postgres_dsn: str,
    alembic_runner: AlembicRunner,
    repo_root: Path,
) -> None:
    """Risk annotation: group=TG-1; named_risk=migration_constraint_drift;
    level=component; source=.tmp/init-125a/phase6/step6a-contract.md#C1 and
    planning/proposals/06-members-kind.md#Migration-unit.
    """
    revision, _down_revision = _members_kind_revision(repo_root)

    _assert_alembic_ok(alembic_runner(fresh_postgres_dsn, "upgrade", revision))

    metadata = _column_metadata(fresh_postgres_dsn)
    assert metadata is not None
    assert metadata["data_type"] == "text"
    assert metadata["is_nullable"] == "NO"
    assert metadata["column_default"] is None

    constraints = _kind_check_constraints(fresh_postgres_dsn)
    assert len(constraints) == 1
    definition = constraints[0]["definition"]
    assert "kind" in definition
    assert "discord" in definition
    assert "public_intake" in definition

    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(fresh_postgres_dsn, autocommit=True) as connection:
            connection.execute(
                """
                INSERT INTO members (id, discord_user_id, joined_at, status, kind)
                VALUES (%s, %s, %s, 'active', 'linked_pending')
                """,
                (uuid4(), "999999999999999999", datetime.now(UTC)),
            )


def test_members_kind_migration_backfills_legacy_rows_and_rerun_is_noop(
    fresh_postgres_dsn: str,
    alembic_runner: AlembicRunner,
    repo_root: Path,
) -> None:
    """Risk annotation: group=TG-1; named_risk=migration_backfill_misclassification;
    level=component; source=.tmp/init-125a/phase6/step6a-contract.md#C1 and
    planning/proposals/06-members-kind.md#Assumption-register-A1.
    """
    revision, down_revision = _members_kind_revision(repo_root)
    _assert_alembic_ok(alembic_runner(fresh_postgres_dsn, "upgrade", down_revision))

    with psycopg.connect(fresh_postgres_dsn, autocommit=True) as connection:
        _insert_legacy_member(
            connection,
            member_id=uuid4(),
            discord_user_id="public:abcdef0123456789abcdef0123456789",
        )
        _insert_legacy_member(
            connection,
            member_id=uuid4(),
            discord_user_id="123456789012345678",
        )

    _assert_alembic_ok(alembic_runner(fresh_postgres_dsn, "upgrade", revision))

    assert _member_kinds(fresh_postgres_dsn) == {
        "123456789012345678": "discord",
        "public:abcdef0123456789abcdef0123456789": "public_intake",
    }

    _assert_alembic_ok(alembic_runner(fresh_postgres_dsn, "upgrade", revision))

    assert _member_kinds(fresh_postgres_dsn) == {
        "123456789012345678": "discord",
        "public:abcdef0123456789abcdef0123456789": "public_intake",
    }


def test_members_kind_migration_downgrade_drops_column_and_constraint(
    fresh_postgres_dsn: str,
    alembic_runner: AlembicRunner,
    repo_root: Path,
) -> None:
    """Risk annotation: group=TG-1; named_risk=migration_downgrade_contract_drift;
    level=component; source=.tmp/init-125a/phase6/step6a-contract.md#C1 and
    planning/proposals/06-members-kind.md#Migration-rollback.
    """
    revision, down_revision = _members_kind_revision(repo_root)
    _assert_alembic_ok(alembic_runner(fresh_postgres_dsn, "upgrade", revision))
    assert _column_metadata(fresh_postgres_dsn) is not None
    assert _kind_check_constraints(fresh_postgres_dsn)

    _assert_alembic_ok(alembic_runner(fresh_postgres_dsn, "downgrade", down_revision))

    assert _column_metadata(fresh_postgres_dsn) is None
    assert _kind_check_constraints(fresh_postgres_dsn) == []
