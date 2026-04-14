from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

BASE_URL = "/api/v1/chapters"


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _chapter_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "slug": f"chapter-{uuid4().hex[:8]}",
        "display_name": "Dark Nemesis",
        "game": "Warcraft III",
        "description": "Competitive chapter for RTS players.",
    }
    payload.update(overrides)
    return payload


def _assert_optional_timestamp(value: str | None) -> None:
    if value is not None:
        _parse_timestamp(value)


def _assert_chapter_response(
    data: dict[str, object],
    expected_payload: dict[str, object],
    *,
    expected_version: int | None,
    archived: bool,
) -> None:
    UUID(str(data["id"]))
    assert data["slug"] == expected_payload["slug"]
    assert data["display_name"] == expected_payload["display_name"]
    assert data["game"] == expected_payload["game"]
    assert data["description"] == expected_payload["description"]
    assert isinstance(data["created_by_discord_user_id"], int)
    assert isinstance(data["version"], int)
    if expected_version is None:
        assert data["version"] >= 1
    else:
        assert data["version"] == expected_version
    _parse_timestamp(str(data["created_at"]))
    _assert_optional_timestamp(data.get("updated_at"))

    archived_at = data.get("archived_at")
    if archived:
        assert archived_at is not None
        _parse_timestamp(str(archived_at))
    else:
        assert archived_at is None


def _create_chapter(client: TestClient, **overrides: object) -> dict[str, object]:
    payload = _chapter_payload(**overrides)
    response = client.post(f"{BASE_URL}/", json=payload)
    assert response.status_code == HTTPStatus.CREATED, response.text
    data = response.json()
    _assert_chapter_response(data, payload, expected_version=1, archived=False)
    return data


@pytest.mark.parametrize(
    "invalid_slug",
    [
        "has spaces",
        "Uppercase",
        f"chapter-{('a' * 51)}",
    ],
)
def test_create_chapter_with_invalid_slug_returns_422(client: TestClient, invalid_slug: str) -> None:
    response = client.post(f"{BASE_URL}/", json=_chapter_payload(slug=invalid_slug))

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_create_chapter_returns_201(client: TestClient) -> None:
    payload = _chapter_payload()

    response = client.post(f"{BASE_URL}/", json=payload)

    assert response.status_code == HTTPStatus.CREATED
    _assert_chapter_response(
        response.json(),
        payload,
        expected_version=1,
        archived=False,
    )


def test_create_chapter_with_duplicate_slug_returns_409(client: TestClient) -> None:
    payload = _chapter_payload()

    first_response = client.post(f"{BASE_URL}/", json=payload)
    second_response = client.post(f"{BASE_URL}/", json=payload)

    assert first_response.status_code == HTTPStatus.CREATED
    assert second_response.status_code == HTTPStatus.CONFLICT


def test_create_chapter_with_missing_required_fields_returns_422(client: TestClient) -> None:
    response = client.post(f"{BASE_URL}/", json={"slug": "chapter-missing"})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_list_chapters_returns_empty_list_when_no_chapters_exist(client: TestClient) -> None:
    response = client.get(f"{BASE_URL}/")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"items": [], "total": 0}


def test_list_chapters_returns_200_and_list_response(client: TestClient) -> None:
    created = _create_chapter(client)

    response = client.get(f"{BASE_URL}/")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == created["id"]


def test_list_chapters_excludes_archived_by_default(client: TestClient) -> None:
    active = _create_chapter(client, display_name="Active Chapter")
    archived = _create_chapter(client, display_name="Archived Chapter")
    archive_response = client.post(f"{BASE_URL}/{archived['id']}/archive")
    assert archive_response.status_code == HTTPStatus.OK, archive_response.text

    response = client.get(f"{BASE_URL}/")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    returned_ids = {item["id"] for item in data["items"]}
    assert active["id"] in returned_ids
    assert archived["id"] not in returned_ids
    assert data["total"] == 1


def test_list_chapters_with_include_archived_returns_archived_items(client: TestClient) -> None:
    active = _create_chapter(client, display_name="Active Chapter")
    archived = _create_chapter(client, display_name="Archived Chapter")
    archive_response = client.post(f"{BASE_URL}/{archived['id']}/archive")
    assert archive_response.status_code == HTTPStatus.OK, archive_response.text

    response = client.get(f"{BASE_URL}/", params={"include_archived": True})

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    returned_ids = {item["id"] for item in data["items"]}
    assert returned_ids == {active["id"], archived["id"]}
    assert data["total"] == 2


def test_get_chapter_returns_200(client: TestClient) -> None:
    created = _create_chapter(client)

    response = client.get(f"{BASE_URL}/{created['id']}")

    assert response.status_code == HTTPStatus.OK
    _assert_chapter_response(
        response.json(),
        {
            "slug": created["slug"],
            "display_name": created["display_name"],
            "game": created["game"],
            "description": created["description"],
        },
        expected_version=1,
        archived=False,
    )


def test_get_chapter_with_nonexistent_uuid_returns_404(client: TestClient) -> None:
    response = client.get(f"{BASE_URL}/{uuid4()}")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_get_archived_chapter_returns_404(client: TestClient) -> None:
    created = _create_chapter(client)
    archive_response = client.post(f"{BASE_URL}/{created['id']}/archive")
    assert archive_response.status_code == HTTPStatus.OK, archive_response.text

    response = client.get(f"{BASE_URL}/{created['id']}")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_update_chapter_with_current_version_returns_200(client: TestClient) -> None:
    created = _create_chapter(client)
    payload = {
        "display_name": "Dark Nemesis Reforged",
        "game": "Warcraft III: Reforged",
        "description": "Updated chapter description.",
        "version": created["version"],
    }

    response = client.patch(f"{BASE_URL}/{created['id']}", json=payload)

    assert response.status_code == HTTPStatus.OK
    _assert_chapter_response(
        response.json(),
        {
            "slug": created["slug"],
            "display_name": payload["display_name"],
            "game": payload["game"],
            "description": payload["description"],
        },
        expected_version=2,
        archived=False,
    )


def test_update_chapter_with_stale_version_returns_409(client: TestClient) -> None:
    created = _create_chapter(client)
    first_update = client.patch(
        f"{BASE_URL}/{created['id']}",
        json={"display_name": "First Update", "version": created["version"]},
    )
    assert first_update.status_code == HTTPStatus.OK, first_update.text

    stale_update = client.patch(
        f"{BASE_URL}/{created['id']}",
        json={"display_name": "Stale Update", "version": created["version"]},
    )

    assert stale_update.status_code == HTTPStatus.CONFLICT


def test_update_chapter_with_no_fields_to_change_still_increments_version(client: TestClient) -> None:
    created = _create_chapter(client)

    response = client.patch(
        f"{BASE_URL}/{created['id']}",
        json={"version": created["version"]},
    )

    assert response.status_code == HTTPStatus.OK
    _assert_chapter_response(
        response.json(),
        {
            "slug": created["slug"],
            "display_name": created["display_name"],
            "game": created["game"],
            "description": created["description"],
        },
        expected_version=2,
        archived=False,
    )


def test_update_archived_chapter_returns_409(client: TestClient) -> None:
    created = _create_chapter(client)
    archive_response = client.post(f"{BASE_URL}/{created['id']}/archive")
    assert archive_response.status_code == HTTPStatus.OK, archive_response.text

    response = client.patch(
        f"{BASE_URL}/{created['id']}",
        json={"display_name": "Should Fail", "version": created["version"]},
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {"detail": "Chapter is archived"}


def test_update_chapter_with_invalid_field_values_returns_422(client: TestClient) -> None:
    created = _create_chapter(client)

    response = client.patch(
        f"{BASE_URL}/{created['id']}",
        json={"display_name": "", "version": created["version"]},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_archive_chapter_returns_200_and_sets_archived_at(client: TestClient) -> None:
    created = _create_chapter(client)

    response = client.post(f"{BASE_URL}/{created['id']}/archive")

    assert response.status_code == HTTPStatus.OK
    _assert_chapter_response(
        response.json(),
        {
            "slug": created["slug"],
            "display_name": created["display_name"],
            "game": created["game"],
            "description": created["description"],
        },
        expected_version=None,
        archived=True,
    )


def test_archive_chapter_twice_returns_409(client: TestClient) -> None:
    created = _create_chapter(client)
    first_response = client.post(f"{BASE_URL}/{created['id']}/archive")
    assert first_response.status_code == HTTPStatus.OK, first_response.text

    second_response = client.post(f"{BASE_URL}/{created['id']}/archive")

    assert second_response.status_code == HTTPStatus.CONFLICT
    assert second_response.json() == {"detail": "Chapter already archived"}


def test_archive_hides_chapter_from_subsequent_get(client: TestClient) -> None:
    created = _create_chapter(client)
    archive_response = client.post(f"{BASE_URL}/{created['id']}/archive")
    assert archive_response.status_code == HTTPStatus.OK, archive_response.text

    response = client.get(f"{BASE_URL}/{created['id']}")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_optimistic_locking_rejects_second_update_from_stale_read(client: TestClient) -> None:
    created = _create_chapter(client)
    assert created["version"] == 1

    first_update = client.patch(
        f"{BASE_URL}/{created['id']}",
        json={"display_name": "Version Two", "version": 1},
    )
    assert first_update.status_code == HTTPStatus.OK, first_update.text
    first_updated = first_update.json()
    assert first_updated["version"] == 2

    read_one = client.get(f"{BASE_URL}/{created['id']}")
    read_two = client.get(f"{BASE_URL}/{created['id']}")
    assert read_one.status_code == HTTPStatus.OK, read_one.text
    assert read_two.status_code == HTTPStatus.OK, read_two.text
    assert read_one.json()["version"] == 2
    assert read_two.json()["version"] == 2

    update_from_first_read = client.patch(
        f"{BASE_URL}/{created['id']}",
        json={"game": "Version Three", "version": read_one.json()["version"]},
    )
    assert update_from_first_read.status_code == HTTPStatus.OK, update_from_first_read.text
    assert update_from_first_read.json()["version"] == 3

    update_from_second_read = client.patch(
        f"{BASE_URL}/{created['id']}",
        json={"game": "Should Conflict", "version": read_two.json()["version"]},
    )

    assert update_from_second_read.status_code == HTTPStatus.CONFLICT
