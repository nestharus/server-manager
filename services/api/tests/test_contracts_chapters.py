import importlib
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _load_chapter_contracts() -> tuple[type, type, type, type]:
    module = importlib.import_module("app.contracts.chapters")
    return (
        module.ChapterStatus,
        module.ChapterCreate,
        module.ChapterRead,
        module.ChapterUpdate,
    )


def _valid_chapter_read_payload() -> dict:
    return {
        "id": 1,
        "name": "Humility Seattle",
        "slug": "humility-seattle",
        "status": "active",
        "discord_category_id": None,
        "discord_officer_role_id": None,
        "discord_member_role_id": None,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    }


def test_chapter_status_has_exactly_three_expected_members() -> None:
    ChapterStatus, _, _, _ = _load_chapter_contracts()

    assert list(ChapterStatus.__members__) == ["active", "archived", "provisioning"]


def test_chapter_create_accepts_valid_name_and_slug() -> None:
    _, ChapterCreate, _, _ = _load_chapter_contracts()

    model = ChapterCreate(name="Humility Seattle", slug="humility-seattle")

    assert model.name == "Humility Seattle"
    assert model.slug == "humility-seattle"


@pytest.mark.parametrize("slug", ["Humility", "bad slug", "bad_slug", "-humility", "humility-"])
def test_chapter_create_rejects_invalid_slug_characters(slug: str) -> None:
    _, ChapterCreate, _, _ = _load_chapter_contracts()

    with pytest.raises(ValidationError):
        ChapterCreate(name="Humility Seattle", slug=slug)


def test_chapter_create_has_no_version_field() -> None:
    _, ChapterCreate, _, _ = _load_chapter_contracts()

    assert "version" not in ChapterCreate.model_fields


def test_chapter_read_requires_all_declared_fields() -> None:
    _, _, ChapterRead, _ = _load_chapter_contracts()
    payload = _valid_chapter_read_payload()
    payload.pop("created_at")

    with pytest.raises(ValidationError):
        ChapterRead(**payload)


def test_chapter_read_does_not_expose_body_version_field() -> None:
    _, _, ChapterRead, _ = _load_chapter_contracts()

    assert "version" not in ChapterRead.model_fields


def test_chapter_update_has_optional_fields_and_no_version() -> None:
    _, _, _, ChapterUpdate = _load_chapter_contracts()

    model = ChapterUpdate()

    assert model.name is None
    assert model.slug is None
    assert model.status is None
    assert "version" not in ChapterUpdate.model_fields


@pytest.mark.parametrize("slug", ["Humility", "bad slug", "bad_slug", "-humility", "humility-"])
def test_chapter_update_validates_slug_pattern_when_provided(slug: str) -> None:
    _, _, _, ChapterUpdate = _load_chapter_contracts()

    with pytest.raises(ValidationError):
        ChapterUpdate(slug=slug)
