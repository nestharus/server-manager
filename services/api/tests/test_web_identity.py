from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_me_reads_pomerium_identity_headers(async_client: AsyncClient) -> None:
    response = await async_client.get(
        "/api/v1/me",
        headers={
            "x-pomerium-claim-sub": "user-123",
            "x-pomerium-claim-email": "user@example.test",
            "x-pomerium-claim-name": "Example User",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "subject": "user-123",
        "email": "user@example.test",
        "display_name": "Example User",
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
    missing = await migrated_async_client.get("/api/v1/web/admin/chapters")
    assert missing.status_code == HTTPStatus.UNAUTHORIZED

    response = await migrated_async_client.get(
        "/api/v1/web/admin/chapters",
        headers={"x-pomerium-claim-email": "admin@example.test"},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"chapters": []}
