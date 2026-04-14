from datetime import datetime
from http import HTTPStatus

from fastapi.testclient import TestClient


BASE_URL = "/api/v1/chapters"


def _chapter_create_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Humility Seattle",
        "slug": "humility-seattle",
    }
    payload.update(overrides)
    return payload


def _chapter_update_payload(version: int = 0, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {"version": version}
    payload.update(overrides)
    return payload


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _assert_chapter_read(
    payload: dict[str, object],
    *,
    expected_name: str,
    expected_slug: str,
    expected_status: str,
    expected_version: int,
) -> None:
    assert isinstance(payload["id"], int)
    assert payload["id"] > 0
    assert payload["name"] == expected_name
    assert payload["slug"] == expected_slug
    assert payload["status"] == expected_status
    assert payload["version"] == expected_version
    assert payload["discord_category_id"] is None
    assert payload["discord_officer_role_id"] is None
    assert payload["discord_member_role_id"] is None
    assert isinstance(payload["created_at"], str)
    assert _parse_timestamp(payload["created_at"])


def _create_chapter(client: TestClient, **overrides: object) -> dict[str, object]:
    response = client.post(BASE_URL, json=_chapter_create_payload(**overrides))

    assert response.status_code == HTTPStatus.CREATED
    return response.json()


def test_create_chapter_returns_created_with_server_managed_fields(client: TestClient) -> None:
    payload = _create_chapter(client)

    _assert_chapter_read(
        payload,
        expected_name="Humility Seattle",
        expected_slug="humility-seattle",
        expected_status="provisioning",
        expected_version=0,
    )


def test_create_chapter_assigns_distinct_server_ids(client: TestClient) -> None:
    first = _create_chapter(client, name="Humility Seattle", slug="humility-seattle")
    second = _create_chapter(client, name="Humility Portland", slug="humility-portland")

    assert first["id"] != second["id"]


def test_create_chapter_rejects_empty_name_at_http_boundary(client: TestClient) -> None:
    response = client.post(BASE_URL, json=_chapter_create_payload(name=""))

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_create_chapter_rejects_invalid_slug_at_http_boundary(client: TestClient) -> None:
    response = client.post(BASE_URL, json=_chapter_create_payload(slug="Bad Slug"))

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_list_chapters_returns_empty_list_when_no_chapters_exist(client: TestClient) -> None:
    response = client.get(BASE_URL)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == []


def test_list_chapters_returns_created_chapters_with_read_shape(client: TestClient) -> None:
    created = _create_chapter(client)
    response = client.get(BASE_URL)

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    _assert_chapter_read(
        body[0],
        expected_name="Humility Seattle",
        expected_slug="humility-seattle",
        expected_status="provisioning",
        expected_version=0,
    )
    assert body[0]["id"] == created["id"]


def test_list_chapters_includes_archived_chapters_with_archived_status(client: TestClient) -> None:
    created = _create_chapter(client)
    archive_response = client.post(f"{BASE_URL}/{created['id']}/archive")
    list_response = client.get(BASE_URL)

    assert archive_response.status_code == HTTPStatus.OK
    assert list_response.status_code == HTTPStatus.OK
    assert list_response.json() == [archive_response.json()]


def test_get_chapter_by_id_returns_the_current_chapter_representation(client: TestClient) -> None:
    created = _create_chapter(client)
    response = client.get(f"{BASE_URL}/{created['id']}")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == created


def test_get_chapter_by_id_returns_404_for_unknown_chapter(client: TestClient) -> None:
    response = client.get(f"{BASE_URL}/999999")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_update_chapter_with_current_version_succeeds_and_increments_version(
    client: TestClient,
) -> None:
    created = _create_chapter(client)
    response = client.patch(
        f"{BASE_URL}/{created['id']}",
        json=_chapter_update_payload(version=created["version"], name="Humility Portland"),
    )

    assert response.status_code == HTTPStatus.OK
    _assert_chapter_read(
        response.json(),
        expected_name="Humility Portland",
        expected_slug="humility-seattle",
        expected_status="provisioning",
        expected_version=1,
    )


def test_update_chapter_changes_are_visible_on_subsequent_get(client: TestClient) -> None:
    created = _create_chapter(client)
    update_response = client.patch(
        f"{BASE_URL}/{created['id']}",
        json=_chapter_update_payload(
            version=created["version"],
            name="Humility Portland",
            slug="humility-portland",
        ),
    )
    get_response = client.get(f"{BASE_URL}/{created['id']}")

    assert update_response.status_code == HTTPStatus.OK
    assert get_response.status_code == HTTPStatus.OK
    assert get_response.json() == update_response.json()


def test_update_chapter_can_change_status_and_discord_ids(client: TestClient) -> None:
    created = _create_chapter(client)
    response = client.patch(
        f"{BASE_URL}/{created['id']}",
        json=_chapter_update_payload(
            version=created["version"],
            status="active",
            discord_category_id=1001,
            discord_officer_role_id=1002,
            discord_member_role_id=1003,
        ),
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["status"] == "active"
    assert body["discord_category_id"] == 1001
    assert body["discord_officer_role_id"] == 1002
    assert body["discord_member_role_id"] == 1003
    assert body["version"] == 1


def test_update_chapter_with_stale_version_returns_conflict(client: TestClient) -> None:
    created = _create_chapter(client)
    first_update = client.patch(
        f"{BASE_URL}/{created['id']}",
        json=_chapter_update_payload(version=created["version"], name="Humility Portland"),
    )
    stale_update = client.patch(
        f"{BASE_URL}/{created['id']}",
        json=_chapter_update_payload(version=created["version"], name="Humility Denver"),
    )

    assert first_update.status_code == HTTPStatus.OK
    assert stale_update.status_code == HTTPStatus.CONFLICT


def test_update_chapter_requires_version_field(client: TestClient) -> None:
    created = _create_chapter(client)
    response = client.patch(
        f"{BASE_URL}/{created['id']}",
        json={"name": "Humility Portland"},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_update_chapter_rejects_invalid_slug_at_http_boundary(client: TestClient) -> None:
    created = _create_chapter(client)
    response = client.patch(
        f"{BASE_URL}/{created['id']}",
        json=_chapter_update_payload(version=created["version"], slug="Bad Slug"),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_update_chapter_rejects_empty_name_at_http_boundary(client: TestClient) -> None:
    created = _create_chapter(client)
    response = client.patch(
        f"{BASE_URL}/{created['id']}",
        json=_chapter_update_payload(version=created["version"], name=""),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_update_chapter_returns_404_for_unknown_chapter(client: TestClient) -> None:
    response = client.patch(
        f"{BASE_URL}/999999",
        json=_chapter_update_payload(version=0, name="Humility Portland"),
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_archive_chapter_marks_chapter_archived_in_response(client: TestClient) -> None:
    created = _create_chapter(client)
    response = client.post(f"{BASE_URL}/{created['id']}/archive")

    assert response.status_code == HTTPStatus.OK
    _assert_chapter_read(
        response.json(),
        expected_name="Humility Seattle",
        expected_slug="humility-seattle",
        expected_status="archived",
        expected_version=1,
    )


def test_archive_chapter_preserves_id_and_created_timestamp(client: TestClient) -> None:
    created = _create_chapter(client)
    response = client.post(f"{BASE_URL}/{created['id']}/archive")

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["id"] == created["id"]
    assert body["created_at"] == created["created_at"]


def test_archived_chapter_remains_readable_via_get(client: TestClient) -> None:
    created = _create_chapter(client)
    archived = client.post(f"{BASE_URL}/{created['id']}/archive")
    get_response = client.get(f"{BASE_URL}/{created['id']}")

    assert archived.status_code == HTTPStatus.OK
    assert get_response.status_code == HTTPStatus.OK
    assert get_response.json() == archived.json()


def test_archived_chapter_remains_listable_and_is_not_hard_deleted(client: TestClient) -> None:
    created = _create_chapter(client)
    archived = client.post(f"{BASE_URL}/{created['id']}/archive")
    list_response = client.get(BASE_URL)

    assert archived.status_code == HTTPStatus.OK
    assert list_response.status_code == HTTPStatus.OK
    assert any(item["id"] == created["id"] for item in list_response.json())
    assert any(item["status"] == "archived" for item in list_response.json())


def test_archive_unknown_chapter_returns_404(client: TestClient) -> None:
    response = client.post(f"{BASE_URL}/999999/archive")

    assert response.status_code == HTTPStatus.NOT_FOUND
