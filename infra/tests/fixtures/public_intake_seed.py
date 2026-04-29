from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import yaml

from infra.tests.fixtures.public_intake_seed_contract import (
    SEED_CONFIGMAP_NAME,
    SEED_MANIFEST_RELATIVE_PATH,
    SeedSqlRun,
)


@pytest.fixture(scope="session")
def public_intake_seed_manifest_path(repo_root: Path) -> Path:
    return repo_root / SEED_MANIFEST_RELATIVE_PATH


@pytest.fixture(scope="session")
def public_intake_seed_manifest_documents(
    public_intake_seed_manifest_path: Path,
) -> list[dict]:
    assert public_intake_seed_manifest_path.is_file()
    documents = [
        document
        for document in yaml.safe_load_all(
            public_intake_seed_manifest_path.read_text(encoding="utf-8")
        )
        if document
    ]
    assert documents
    return documents


@pytest.fixture(scope="session")
def public_intake_seed_sql(
    public_intake_seed_manifest_documents: list[dict],
) -> str:
    configmap = next(
        (
            document
            for document in public_intake_seed_manifest_documents
            if document.get("kind") == "ConfigMap"
            and document.get("metadata", {}).get("name") == SEED_CONFIGMAP_NAME
        ),
        None,
    )
    assert configmap is not None
    seed_sql = configmap.get("data", {}).get("seed.sql")
    assert isinstance(seed_sql, str)
    assert seed_sql.strip()
    return seed_sql


@pytest.fixture()
def fresh_public_intake_postgres_dsn() -> Iterator[str]:
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16") as container:
        yield container.get_connection_url().replace("+psycopg2", "").replace(
            "+psycopg",
            "",
        )


@pytest.fixture()
def fresh_migrated_public_intake_db(
    fresh_public_intake_postgres_dsn: str,
    alembic_runner: Callable[..., object],
) -> str:
    result = alembic_runner(fresh_public_intake_postgres_dsn, "upgrade", "head")
    assert result.returncode == 0, (
        "alembic upgrade head failed for a clean public-intake seed database.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    return fresh_public_intake_postgres_dsn


@pytest.fixture()
def public_intake_seed_runner(
    public_intake_seed_sql: str,
) -> Callable[[str], SeedSqlRun]:
    def run(database_url: str) -> SeedSqlRun:
        import psycopg
        from psycopg.rows import dict_row

        notices: list[str] = []

        def capture_notice(diagnostic) -> None:
            message = getattr(diagnostic, "message_primary", None)
            notices.append(str(message or diagnostic))

        with psycopg.connect(database_url, row_factory=dict_row) as connection:
            connection.add_notice_handler(capture_notice)
            cursor = connection.execute(public_intake_seed_sql)
            rows = tuple(dict(row) for row in cursor.fetchall()) if cursor.description else ()
        return SeedSqlRun(notices=tuple(notices), rows=rows)

    return run
