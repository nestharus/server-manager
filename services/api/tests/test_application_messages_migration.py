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
from psycopg.types.json import Jsonb


AlembicRunner = Callable[..., subprocess.CompletedProcess[str]]


EXPECTED_COLUMNS = [
    "id",
    "application_id",
    "message_seq",
    "author_actor_kind",
    "author_actor_id",
    "visibility",
    "body_markdown",
    "client_message_id",
    "correlation_id",
    "causation_id",
    "created_at",
]


def _assert_alembic_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        "alembic command failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def _application_messages_revision(repo_root: Path) -> tuple[str, str]:
    candidates = [
        path
        for path in (repo_root / "migrations/versions").glob("*.py")
        if "application_messages" in path.name
    ]
    assert candidates, "missing Alembic migration for application_messages"
    assert len(candidates) == 1, f"ambiguous application_messages migrations: {candidates}"

    source = candidates[0].read_text(encoding="utf-8")
    revision = re.search(r'^revision\s*=\s*["\']([^"\']+)["\']', source, re.M)
    down_revision = re.search(r'^down_revision\s*=\s*["\']([^"\']+)["\']', source, re.M)
    assert revision is not None, f"missing revision in {candidates[0]}"
    assert down_revision is not None, f"missing down_revision in {candidates[0]}"
    return revision.group(1), down_revision.group(1)


def _table_exists(database_url: str, table_name: str) -> bool:
    with psycopg.connect(database_url) as connection:
        row = connection.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = %s
            )
            """,
            (table_name,),
        ).fetchone()
    assert row is not None
    return bool(row[0])


def _column_metadata(database_url: str) -> list[dict[str, str | None]]:
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        return [
            dict(row)
            for row in connection.execute(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'application_messages'
                ORDER BY ordinal_position
                """
            ).fetchall()
        ]


def _visibility_check_constraints(database_url: str) -> list[dict[str, str]]:
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
                  AND t.relname = 'application_messages'
                  AND c.contype = 'c'
                  AND pg_get_constraintdef(c.oid) LIKE '%visibility%'
                ORDER BY c.conname
                """
            ).fetchall()
        ]


def _application_fk(database_url: str) -> dict[str, str] | None:
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        row = connection.execute(
            """
            SELECT c.conname,
                   c.confdeltype,
                   pg_get_constraintdef(c.oid) AS definition
            FROM pg_constraint AS c
            JOIN pg_class AS t ON t.oid = c.conrelid
            JOIN pg_namespace AS n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public'
              AND t.relname = 'application_messages'
              AND c.contype = 'f'
              AND pg_get_constraintdef(c.oid) LIKE '%applications(id)%'
            """
        ).fetchone()
    return None if row is None else dict(row)


def _client_message_index(database_url: str) -> str | None:
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        row = connection.execute(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'application_messages'
              AND indexdef ILIKE '%UNIQUE%'
              AND indexdef LIKE '%client_message_id%'
            """
        ).fetchone()
    return None if row is None else str(row["indexdef"])


def _seed_application(connection: psycopg.Connection[object]) -> UUID:
    member_id = uuid4()
    form_id = uuid4()
    application_id = uuid4()
    connection.execute(
        """
        INSERT INTO members (id, discord_user_id, joined_at, status, kind)
        VALUES (%s, %s, %s, 'active', 'discord')
        """,
        (member_id, str(10**17 + (uuid4().int % 10**17)), datetime.now(UTC)),
    )
    connection.execute(
        """
        INSERT INTO form_definitions (
            id, scope_kind, scope_id, version, name, target_type, fields,
            routing_rules, status, published_by_kind, published_by_id
        )
        VALUES (
            %s, 'chapter', 'chapter-1', 1, 'Application Messages Form',
            'chapter_membership', %s, %s, 'current', 'user', 'operator'
        )
        """,
        (
            form_id,
            Jsonb(
                [
                    {
                        "id": "nickname",
                        "type": "short",
                        "label": "Nickname",
                        "required": True,
                    }
                ]
            ),
            Jsonb(
                {
                    "schema_version": 1,
                    "queue": "chapter_officers",
                    "review_scope": {
                        "scope_kind": "chapter",
                        "scope_id": "chapter-1",
                    },
                }
            ),
        ),
    )
    connection.execute(
        """
        INSERT INTO applications (
            id, applicant_id, form_definition_id, form_version, form_snapshot,
            target_scope_kind, target_scope_id, responses, state, submitted_at,
            queued_at
        )
        VALUES (
            %s, %s, %s, 1, %s, 'chapter', 'chapter-1', %s, 'queued', %s, %s
        )
        """,
        (
            application_id,
            member_id,
            form_id,
            Jsonb(
                {
                    "form_version": 1,
                    "target_scope": {
                        "scope_kind": "chapter",
                        "scope_id": "chapter-1",
                    },
                    "fields": [
                        {
                            "id": "nickname",
                            "type": "short",
                            "label": "Nickname",
                            "required": True,
                        }
                    ],
                }
            ),
            Jsonb({"nickname": "Ada"}),
            datetime.now(UTC),
            datetime.now(UTC),
        ),
    )
    return application_id


def _insert_message(
    connection: psycopg.Connection[object],
    *,
    application_id: UUID,
    message_seq: int,
    visibility: str = "applicant_visible",
    client_message_id: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO application_messages (
            id, application_id, message_seq, author_actor_kind,
            author_actor_id, visibility, body_markdown, client_message_id,
            correlation_id, causation_id
        )
        VALUES (%s, %s, %s, 'user', 'author-1', %s, 'Body', %s, %s, NULL)
        """,
        (
            uuid4(),
            application_id,
            message_seq,
            visibility,
            client_message_id,
            uuid4(),
        ),
    )


def test_application_messages_migration_adds_expected_table_shape(
    fresh_postgres_dsn: str,
    alembic_runner: AlembicRunner,
    repo_root: Path,
) -> None:
    """Risk annotation: group=TG-6; named_risk=migration_table_shape_drift;
    level=component; source=.tmp/init-131/phase6/step6a-contract.md#TG-6 and
    proposals/10-application-messages.md#Q3.
    """
    revision, down_revision = _application_messages_revision(repo_root)
    assert revision == "wu_044_application_messages"
    assert down_revision == "wu_043_members_kind"

    _assert_alembic_ok(alembic_runner(fresh_postgres_dsn, "upgrade", down_revision))
    assert not _table_exists(fresh_postgres_dsn, "application_messages")

    _assert_alembic_ok(alembic_runner(fresh_postgres_dsn, "upgrade", revision))

    columns = _column_metadata(fresh_postgres_dsn)
    assert [column["column_name"] for column in columns] == EXPECTED_COLUMNS
    by_name = {str(column["column_name"]): column for column in columns}
    assert by_name["id"]["data_type"] == "uuid"
    assert by_name["application_id"]["data_type"] == "uuid"
    assert by_name["message_seq"]["data_type"] == "bigint"
    assert by_name["visibility"]["data_type"] == "text"
    assert by_name["body_markdown"]["data_type"] == "text"
    assert by_name["client_message_id"]["is_nullable"] == "YES"
    assert by_name["causation_id"]["is_nullable"] == "YES"
    assert by_name["created_at"]["data_type"] == "timestamp with time zone"
    assert by_name["created_at"]["column_default"] is not None


def test_application_messages_migration_enforces_visibility_check(
    fresh_postgres_dsn: str,
    alembic_runner: AlembicRunner,
    repo_root: Path,
) -> None:
    """Risk annotation: group=TG-6; named_risk=visibility_constraint_missing;
    level=component; source=.tmp/init-131/phase6/step6a-contract.md#TG-6 and
    proposals/10-application-messages.md#Q3.
    """
    revision, _down_revision = _application_messages_revision(repo_root)
    _assert_alembic_ok(alembic_runner(fresh_postgres_dsn, "upgrade", revision))

    constraints = _visibility_check_constraints(fresh_postgres_dsn)
    assert len(constraints) == 1
    assert "applicant_visible" in constraints[0]["definition"]
    assert "officer_only" in constraints[0]["definition"]

    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(fresh_postgres_dsn, autocommit=True) as connection:
            application_id = _seed_application(connection)
            _insert_message(
                connection,
                application_id=application_id,
                message_seq=1,
                visibility="public",
            )


def test_application_messages_migration_adds_partial_client_message_unique_index(
    fresh_postgres_dsn: str,
    alembic_runner: AlembicRunner,
    repo_root: Path,
) -> None:
    """Risk annotation: group=TG-6; named_risk=client_message_id_unique_index_missing;
    level=component; source=.tmp/init-131/phase6/step6a-contract.md#TG-6 and
    proposals/10-application-messages.md#Q3.
    """
    revision, _down_revision = _application_messages_revision(repo_root)
    _assert_alembic_ok(alembic_runner(fresh_postgres_dsn, "upgrade", revision))

    indexdef = _client_message_index(fresh_postgres_dsn)
    assert indexdef is not None
    assert "application_id" in indexdef
    assert "client_message_id" in indexdef
    assert "WHERE (client_message_id IS NOT NULL)" in indexdef

    with psycopg.connect(fresh_postgres_dsn, autocommit=True) as connection:
        application_id = _seed_application(connection)
        _insert_message(
            connection,
            application_id=application_id,
            message_seq=1,
            client_message_id=None,
        )
        _insert_message(
            connection,
            application_id=application_id,
            message_seq=2,
            client_message_id=None,
        )
        _insert_message(
            connection,
            application_id=application_id,
            message_seq=3,
            client_message_id="client-message-1",
        )
        with pytest.raises(psycopg.errors.UniqueViolation):
            _insert_message(
                connection,
                application_id=application_id,
                message_seq=4,
                client_message_id="client-message-1",
            )


def test_application_messages_migration_restricts_application_delete(
    fresh_postgres_dsn: str,
    alembic_runner: AlembicRunner,
    repo_root: Path,
) -> None:
    """Risk annotation: group=TG-6; named_risk=application_fk_delete_not_restricted;
    level=component; source=.tmp/init-131/phase6/step6a-contract.md#TG-6 and
    proposals/10-application-messages.md#Q3.
    """
    revision, _down_revision = _application_messages_revision(repo_root)
    _assert_alembic_ok(alembic_runner(fresh_postgres_dsn, "upgrade", revision))

    fk = _application_fk(fresh_postgres_dsn)
    assert fk is not None
    assert fk["confdeltype"] == "r"
    assert "FOREIGN KEY (application_id)" in fk["definition"]
    assert "REFERENCES applications(id)" in fk["definition"]

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with psycopg.connect(fresh_postgres_dsn, autocommit=True) as connection:
            application_id = _seed_application(connection)
            _insert_message(
                connection,
                application_id=application_id,
                message_seq=1,
            )
            connection.execute(
                "DELETE FROM applications WHERE id = %s",
                (application_id,),
            )


def test_application_messages_migration_downgrade_drops_table(
    fresh_postgres_dsn: str,
    alembic_runner: AlembicRunner,
    repo_root: Path,
) -> None:
    """Risk annotation: group=TG-6; named_risk=migration_downgrade_table_drift;
    level=component; source=.tmp/init-131/phase6/step6a-contract.md#TG-6 and
    proposals/10-application-messages.md#Q3.
    """
    revision, down_revision = _application_messages_revision(repo_root)
    _assert_alembic_ok(alembic_runner(fresh_postgres_dsn, "upgrade", revision))
    assert _table_exists(fresh_postgres_dsn, "application_messages")

    _assert_alembic_ok(alembic_runner(fresh_postgres_dsn, "downgrade", down_revision))

    assert not _table_exists(fresh_postgres_dsn, "application_messages")
