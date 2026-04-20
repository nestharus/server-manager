from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict


class ApiTestHarnessRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    app_fixture_name: Literal["app"]
    async_client_fixture_names: frozenset[Literal["async_client", "migrated_async_client"]]
    db_dsn_fixture_names: frozenset[Literal["migrated_postgres_db", "governance_dsn"]]
    audit_context_helper: Literal["app.core.context:use_audit_context"]


API_TEST_HARNESS: Final[ApiTestHarnessRead] = ApiTestHarnessRead(
    app_fixture_name="app",
    async_client_fixture_names=frozenset({"async_client", "migrated_async_client"}),
    db_dsn_fixture_names=frozenset({"migrated_postgres_db", "governance_dsn"}),
    audit_context_helper="app.core.context:use_audit_context",
)
