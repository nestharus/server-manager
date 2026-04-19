from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from psycopg import Connection
from psycopg_pool import ConnectionPool
from sqlalchemy import MetaData

DATABASE_URL_ENV_VARS = ("DATABASE_URL", "SUPABASE_DB_URL")

metadata = MetaData(
    naming_convention={
        "pk": "pk_%(table_name)s",
        "fk": "fk_%(table_name)s__%(column_0_name)s__%(referred_table_name)s",
        "uq": "uq_%(table_name)s__%(column_0_name)s",
        "ix": "ix_%(table_name)s__%(column_0_name)s",
        "ck": "ck_%(table_name)s__%(constraint_name)s",
    }
)


def resolve_database_url(explicit_url: str | None = None) -> str:
    if explicit_url:
        return explicit_url

    for env_var in DATABASE_URL_ENV_VARS:
        value = os.getenv(env_var)
        if value:
            return value

    raise RuntimeError(
        "database URL is required via DATABASE_URL or SUPABASE_DB_URL",
    )


class PostgresDatabase:
    def __init__(
        self,
        dsn: str | None = None,
        *,
        min_size: int = 1,
        max_size: int = 4,
    ) -> None:
        self._dsn = resolve_database_url(dsn)
        self._pool = ConnectionPool(
            conninfo=self._dsn,
            min_size=min_size,
            max_size=max_size,
            kwargs={"autocommit": True},
            open=True,
        )

    @contextmanager
    def connection(self) -> Iterator[Connection[Any]]:
        with self._pool.connection() as connection:
            yield connection

    @contextmanager
    def transaction(self) -> Iterator[Connection[Any]]:
        with self._pool.connection() as connection, connection.transaction():
            yield connection

    def current_revision(self) -> str:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT version_num FROM alembic_version",
            ).fetchall()

        if len(rows) != 1:
            raise RuntimeError(
                f"alembic_version has {len(rows)} rows; expected exactly 1 "
                "(branched migrations are not supported)"
            )

        return str(rows[0][0])

    def close(self) -> None:
        self._pool.close()
