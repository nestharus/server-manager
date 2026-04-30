from __future__ import annotations

from http import HTTPStatus
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from httpx import AsyncClient

from app.repositories.db import PostgresDatabase

from .chapter_selector_fixtures import seed_chapter


pytestmark = pytest.mark.asyncio

PUBLIC_CHAPTERS_URL = "/api/v1/public/chapters"


async def _get_public_chapters(
    client: AsyncClient,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    response = await client.get(PUBLIC_CHAPTERS_URL, headers=headers)
    return response.status_code, response.json()


def _collect_dependency_names(dependant: Any) -> set[str]:
    names: set[str] = set()
    for dependency in getattr(dependant, "dependencies", ()):
        if dependency.call is not None:
            names.add(dependency.call.__name__)
        names.update(_collect_dependency_names(dependency))
    return names


async def test_public_chapters_returns_only_active(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-2;
    named_risk=public_chapter_list_exposes_only_active_minimal_shape; level=api;
    source=.tmp/init-135/phase6/step6a-contract.md#TG-2.
    """
    active_id = seed_chapter(governance_db, name="Bravo", state="active")
    seed_chapter(governance_db, name="Alpha proposed", state="proposed")
    seed_chapter(governance_db, name="Charlie archived", state="archived")

    status_code, body = await _get_public_chapters(migrated_async_client)

    assert status_code == HTTPStatus.OK
    assert body == {"chapters": [{"id": active_id, "name": "Bravo"}]}


async def test_public_chapters_orders_by_name_asc(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-2;
    named_risk=public_chapter_list_exposes_only_active_minimal_shape; level=api;
    source=.tmp/init-135/phase6/step6a-contract.md#TG-2.
    """
    seed_chapter(governance_db, name="Zulu", state="active")
    seed_chapter(governance_db, name="Alpha", state="active")
    seed_chapter(governance_db, name="Echo", state="active")

    status_code, body = await _get_public_chapters(migrated_async_client)

    assert status_code == HTTPStatus.OK
    assert [chapter["name"] for chapter in body["chapters"]] == ["Alpha", "Echo", "Zulu"]


async def test_public_chapters_caps_at_200(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-2;
    named_risk=public_chapter_list_exposes_only_active_minimal_shape; level=api;
    source=.tmp/init-135/phase6/step6a-contract.md#TG-2.
    """
    for index in range(201):
        seed_chapter(governance_db, name=f"Chapter {index:03d}", state="active")

    status_code, body = await _get_public_chapters(migrated_async_client)

    assert status_code == HTTPStatus.OK
    assert len(body["chapters"]) == 200
    assert body["chapters"][0]["name"] == "Chapter 000"
    assert body["chapters"][-1]["name"] == "Chapter 199"


async def test_public_chapters_returns_id_and_name_only(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-2;
    named_risk=public_chapter_list_exposes_only_active_minimal_shape; level=api;
    source=.tmp/init-135/phase6/step6a-contract.md#TG-2.
    """
    seed_chapter(governance_db, name="Minimal", state="active")

    status_code, body = await _get_public_chapters(migrated_async_client)

    assert status_code == HTTPStatus.OK
    assert set(body) == {"chapters"}
    assert body["chapters"]
    assert set(body["chapters"][0]) == {"id", "name"}


async def test_public_chapters_returns_empty_list_when_no_actives(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-2;
    named_risk=public_chapter_list_exposes_only_active_minimal_shape; level=api;
    source=.tmp/init-135/phase6/step6a-contract.md#TG-2.
    """
    seed_chapter(governance_db, name="Not yet", state="proposed")

    status_code, body = await _get_public_chapters(migrated_async_client)

    assert status_code == HTTPStatus.OK
    assert body == {"chapters": []}


async def test_public_chapters_no_auth_required(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-2;
    named_risk=public_chapter_list_exposes_only_active_minimal_shape; level=api;
    source=.tmp/init-135/phase6/step6a-contract.md#TG-2-F4.
    """
    seed_chapter(governance_db, name="No Auth", state="active")

    status_code, body = await _get_public_chapters(migrated_async_client)

    assert status_code == HTTPStatus.OK
    assert body["chapters"] == [{"id": body["chapters"][0]["id"], "name": "No Auth"}]


async def test_public_chapters_ignores_pomerium_claim_headers(
    migrated_async_client: AsyncClient,
    governance_db: PostgresDatabase,
) -> None:
    """Risk annotation: group=TG-2;
    named_risk=public_chapter_list_exposes_only_active_minimal_shape; level=api;
    source=.tmp/init-135/phase6/step6a-contract.md#TG-2-F4.
    """
    seed_chapter(governance_db, name="Public", state="active")

    no_headers = await migrated_async_client.get(PUBLIC_CHAPTERS_URL)
    with_headers = await migrated_async_client.get(
        PUBLIC_CHAPTERS_URL,
        headers={
            "x-pomerium-claim-email": "officer@example.test",
            "x-pomerium-claim-sub": "pomerium-subject",
            "x-pomerium-claim-discord-user-id": "123456789012345678",
        },
    )

    assert no_headers.status_code == HTTPStatus.OK, no_headers.text
    assert with_headers.status_code == HTTPStatus.OK, with_headers.text
    assert with_headers.json() == no_headers.json()


def test_public_chapters_endpoint_dependency_tree_is_identity_free(app: FastAPI) -> None:
    """Risk annotation: group=TG-2;
    named_risk=public_chapter_list_exposes_only_active_minimal_shape; level=api;
    source=.tmp/init-135/phase6/step6a-contract.md#TG-2-F4.
    """
    forbidden = {
        "get_pomerium_principal",
        "verify_applicant_receipt",
        "authorize_public_intake",
    }
    route = next(
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path == PUBLIC_CHAPTERS_URL
        and "GET" in route.methods
    )

    dependency_names = _collect_dependency_names(route.dependant)

    assert dependency_names.isdisjoint(forbidden)
