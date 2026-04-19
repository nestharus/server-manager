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


def _chapter_update_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {}
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
) -> None:
    assert isinstance(payload["id"], int)
    assert payload["name"] == expected_name
    assert payload["slug"] == expected_slug
    assert payload["status"] == expected_status
    assert "version" not in payload
    assert payload["discord_category_id"] is None
    assert payload["discord_officer_role_id"] is None
    assert payload["discord_member_role_id"] is None
    assert isinstance(payload["created_at"], str)
    assert _parse_timestamp(payload["created_at"])


def _create_chapter(client: TestClient, **overrides: object) -> tuple[dict[str, object], str]:
    response = client.post(BASE_URL, json=_chapter_create_payload(**overrides))

    assert response.status_code == HTTPStatus.CREATED
    assert "etag" in response.headers
    return response.json(), response.headers["etag"]


def test_create_chapter_returns_created_with_server_managed_fields(client: TestClient) -> None:
    payload, etag = _create_chapter(client)

    _assert_chapter_read(
        payload,
        expected_name="Humility Seattle",
        expected_slug="humility-seattle",
        expected_status="provisioning",
    )
    assert etag == '"1"'


def test_list_chapters_returns_created_chapters_with_read_shape(client: TestClient) -> None:
    created, _ = _create_chapter(client)
    response = client.get(BASE_URL)

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert len(body) == 1
    _assert_chapter_read(
        body[0],
        expected_name="Humility Seattle",
        expected_slug="humility-seattle",
        expected_status="provisioning",
    )
    assert body[0]["id"] == created["id"]


def test_get_chapter_returns_current_representation_and_etag(client: TestClient) -> None:
    created, created_etag = _create_chapter(client)

    response = client.get(f"{BASE_URL}/{created['id']}")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == created
    assert response.headers["etag"] == created_etag


def test_update_chapter_requires_if_match_header(client: TestClient) -> None:
    created, _ = _create_chapter(client)

    response = client.patch(
        f"{BASE_URL}/{created['id']}",
        json=_chapter_update_payload(name="Humility Portland"),
    )

    assert response.status_code == HTTPStatus.PRECONDITION_REQUIRED


def test_update_chapter_with_current_etag_succeeds_and_advances_etag(
    client: TestClient,
) -> None:
    created, etag = _create_chapter(client)
    response = client.patch(
        f"{BASE_URL}/{created['id']}",
        json=_chapter_update_payload(name="Humility Portland"),
        headers={"If-Match": etag},
    )

    assert response.status_code == HTTPStatus.OK
    _assert_chapter_read(
        response.json(),
        expected_name="Humility Portland",
        expected_slug="humility-seattle",
        expected_status="provisioning",
    )
    assert response.headers["etag"] == '"2"'


def test_update_chapter_with_stale_etag_returns_precondition_failed(client: TestClient) -> None:
    created, etag = _create_chapter(client)
    first = client.patch(
        f"{BASE_URL}/{created['id']}",
        json=_chapter_update_payload(name="Humility Portland"),
        headers={"If-Match": etag},
    )
    stale = client.patch(
        f"{BASE_URL}/{created['id']}",
        json=_chapter_update_payload(name="Humility Denver"),
        headers={"If-Match": etag},
    )

    assert first.status_code == HTTPStatus.OK
    assert stale.status_code == HTTPStatus.PRECONDITION_FAILED


def test_archive_chapter_requires_if_match_and_advances_etag(client: TestClient) -> None:
    created, etag = _create_chapter(client)

    missing = client.post(f"{BASE_URL}/{created['id']}/archive")
    archived = client.post(
        f"{BASE_URL}/{created['id']}/archive",
        headers={"If-Match": etag},
    )

    assert missing.status_code == HTTPStatus.PRECONDITION_REQUIRED
    assert archived.status_code == HTTPStatus.OK
    _assert_chapter_read(
        archived.json(),
        expected_name="Humility Seattle",
        expected_slug="humility-seattle",
        expected_status="archived",
    )
    assert archived.headers["etag"] == '"2"'
