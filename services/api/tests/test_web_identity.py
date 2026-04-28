from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

import pytest
import yaml
from httpx import AsyncClient


REPO_ROOT = Path(__file__).resolve().parents[3]
AUTH_STACK_FIXTURE = (
    REPO_ROOT / "infra" / "tests" / "fixtures" / "contracts" / "auth_stack_contract.yml"
)


def _contract() -> dict:
    return yaml.safe_load(AUTH_STACK_FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_me_reads_pomerium_identity_headers(async_client: AsyncClient) -> None:
    contract = _contract()
    identity = contract["oidc_identity"]
    headers = contract["pomerium_headers"]

    response = await async_client.get(
        "/api/v1/me",
        headers={
            headers["subject"]: identity["subject"],
            headers["email"]: identity["email"],
            headers["display_name"]: identity["display_name"],
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "subject": identity["subject"],
        "email": identity["email"],
        "display_name": identity["display_name"],
        "provider": "pomerium",
    }


@pytest.mark.asyncio
async def test_me_rejects_missing_identity(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/v1/me")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["code"] == "identity_missing"


@pytest.mark.asyncio
async def test_web_admin_chapters_requires_identity(
    migrated_async_client: AsyncClient,
) -> None:
    contract = _contract()
    headers = contract["pomerium_headers"]
    identity = contract["oidc_identity"]

    missing = await migrated_async_client.get("/api/v1/web/admin/chapters")
    assert missing.status_code == HTTPStatus.UNAUTHORIZED

    response = await migrated_async_client.get(
        "/api/v1/web/admin/chapters",
        headers={headers["email"]: identity["email"]},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"chapters": []}
