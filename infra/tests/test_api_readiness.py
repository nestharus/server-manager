"""WU-010D / AC1: API readiness surface.

Tests fail now and pass after the SLICE-006 code agent implements:
- `ServiceReadinessRead`, `DependencyStatusRead` in `app.contracts.runtime`
- `GET /api/v1/ready` returning `ServiceReadinessRead` with `database`,
  `migrations`, `scheduler` probes
- `SchedulerLoop.is_running` and `app.state.scheduler_loop`

These tests rely on the API conftest fixtures (`migrated_async_client`,
`app`) being available under `infra/tests/`; the code agent wires that up.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

_API_SERVICE_PATH = Path(__file__).resolve().parents[2] / "services" / "api"
if str(_API_SERVICE_PATH) not in sys.path:
    sys.path.insert(0, str(_API_SERVICE_PATH))

from fastapi import FastAPI  # noqa: E402

from app.contracts.runtime import (  # noqa: E402
    DependencyStatusRead,
    ServiceReadinessRead,
)


pytestmark = pytest.mark.asyncio()


async def test_ready_endpoint_returns_ready_when_all_dependencies_ok(
    migrated_async_client: httpx.AsyncClient,
) -> None:
    response = await migrated_async_client.get("/api/v1/ready")

    assert response.status_code == 200
    parsed = ServiceReadinessRead.model_validate(response.json())
    assert parsed.status == "ready"
    by_name = {dep.name: dep for dep in parsed.dependencies}
    assert set(by_name) == {"database", "migrations", "scheduler"}
    for dep in parsed.dependencies:
        assert dep.status == "ok"


async def test_ready_endpoint_not_ready_when_scheduler_stopped(
    migrated_async_client: httpx.AsyncClient,
    app: FastAPI,
) -> None:
    await app.state.scheduler_loop.stop()

    response = await migrated_async_client.get("/api/v1/ready")

    assert response.status_code == 503
    parsed = ServiceReadinessRead.model_validate(response.json())
    assert parsed.status == "not_ready"
    by_name = {dep.name: dep for dep in parsed.dependencies}
    assert by_name["scheduler"].status == "not_ready"


async def test_ready_endpoint_dependency_shape(
    migrated_async_client: httpx.AsyncClient,
) -> None:
    response = await migrated_async_client.get("/api/v1/ready")

    parsed = ServiceReadinessRead.model_validate(response.json())
    assert parsed.dependencies, "readiness must enumerate dependencies"
    for dep in parsed.dependencies:
        assert isinstance(dep, DependencyStatusRead)
        assert dep.name
        assert dep.status in {"ok", "degraded", "not_ready"}
        assert dep.reason is None or isinstance(dep.reason, str)


async def test_ready_endpoint_not_ready_when_migrations_missing(
    migrated_async_client: httpx.AsyncClient,
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _no_revision() -> str:
        return ""

    monkeypatch.setattr(app.state.db, "current_revision", _no_revision)

    response = await migrated_async_client.get("/api/v1/ready")

    assert response.status_code == 503
    parsed = ServiceReadinessRead.model_validate(response.json())
    assert parsed.status == "not_ready"
    by_name = {dep.name: dep for dep in parsed.dependencies}
    assert by_name["migrations"].status == "not_ready"
    assert by_name["migrations"].reason
