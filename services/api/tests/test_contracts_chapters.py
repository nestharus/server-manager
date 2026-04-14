import importlib
import sys
from datetime import UTC
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.contracts.base import VersionedMixin


def _load_chapter_contracts() -> tuple[type, type, type, type]:
    try:
        module = importlib.import_module("app.contracts.chapters")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Expected contract module app.contracts.chapters to exist: {exc}")

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
        "version": 0,
    }


def test_chapter_status_has_exactly_three_expected_members() -> None:
    ChapterStatus, _, _, _ = _load_chapter_contracts()

    assert list(ChapterStatus.__members__) == ["active", "archived", "provisioning"]
    assert len(ChapterStatus.__members__) == 3


def test_chapter_status_values_are_strings() -> None:
    ChapterStatus, _, _, _ = _load_chapter_contracts()

    assert ChapterStatus.active.value == "active"
    assert ChapterStatus.archived.value == "archived"
    assert ChapterStatus.provisioning.value == "provisioning"
    assert all(isinstance(member.value, str) for member in ChapterStatus)


def test_chapter_create_accepts_valid_name_and_slug() -> None:
    _, ChapterCreate, _, _ = _load_chapter_contracts()

    model = ChapterCreate(name="Humility Seattle", slug="humility-seattle")

    assert model.name == "Humility Seattle"
    assert model.slug == "humility-seattle"


def test_chapter_create_rejects_empty_name() -> None:
    _, ChapterCreate, _, _ = _load_chapter_contracts()

    with pytest.raises(ValidationError):
        ChapterCreate(name="", slug="humility-seattle")


@pytest.mark.parametrize("slug", ["Humility", "bad slug", "bad_slug", "bad!slug"])
def test_chapter_create_rejects_invalid_slug_characters(slug: str) -> None:
    _, ChapterCreate, _, _ = _load_chapter_contracts()

    with pytest.raises(ValidationError):
        ChapterCreate(name="Humility Seattle", slug=slug)


@pytest.mark.parametrize("slug", ["-humility", "humility-"])
def test_chapter_create_rejects_slug_with_leading_or_trailing_hyphen(slug: str) -> None:
    _, ChapterCreate, _, _ = _load_chapter_contracts()

    with pytest.raises(ValidationError):
        ChapterCreate(name="Humility Seattle", slug=slug)


def test_chapter_create_has_no_version_field() -> None:
    _, ChapterCreate, _, _ = _load_chapter_contracts()

    assert "version" not in ChapterCreate.model_fields


def test_chapter_read_inherits_from_versioned_mixin() -> None:
    _, _, ChapterRead, _ = _load_chapter_contracts()

    assert issubclass(ChapterRead, VersionedMixin)


@pytest.mark.parametrize(
    "missing_field",
    [
        "id",
        "name",
        "slug",
        "status",
        "discord_category_id",
        "discord_officer_role_id",
        "discord_member_role_id",
        "created_at",
        "version",
    ],
)
def test_chapter_read_requires_all_fields(missing_field: str) -> None:
    _, _, ChapterRead, _ = _load_chapter_contracts()
    payload = _valid_chapter_read_payload()
    payload.pop(missing_field)

    with pytest.raises(ValidationError):
        ChapterRead(**payload)


def test_chapter_read_accepts_none_for_discord_ids() -> None:
    _, _, ChapterRead, _ = _load_chapter_contracts()

    model = ChapterRead(**_valid_chapter_read_payload())

    assert model.discord_category_id is None
    assert model.discord_officer_role_id is None
    assert model.discord_member_role_id is None


def test_chapter_update_inherits_from_versioned_mixin() -> None:
    _, _, _, ChapterUpdate = _load_chapter_contracts()

    assert issubclass(ChapterUpdate, VersionedMixin)


def test_chapter_update_requires_version_and_all_other_fields_are_optional() -> None:
    _, _, _, ChapterUpdate = _load_chapter_contracts()

    with pytest.raises(ValidationError):
        ChapterUpdate()

    model = ChapterUpdate(version=0)

    assert model.version == 0
    assert model.name is None
    assert model.slug is None
    assert model.status is None
    assert model.discord_category_id is None
    assert model.discord_officer_role_id is None
    assert model.discord_member_role_id is None


@pytest.mark.parametrize("slug", ["Humility", "bad slug", "bad_slug", "-humility", "humility-"])
def test_chapter_update_validates_slug_pattern_when_provided(slug: str) -> None:
    _, _, _, ChapterUpdate = _load_chapter_contracts()

    with pytest.raises(ValidationError):
        ChapterUpdate(version=0, slug=slug)


@pytest.mark.parametrize("name", ["", "x" * 101])
def test_chapter_update_validates_name_length_when_provided(name: str) -> None:
    _, _, _, ChapterUpdate = _load_chapter_contracts()

    with pytest.raises(ValidationError):
        ChapterUpdate(version=0, name=name)


# ---------------------------------------------------------------------------
# Optimistic locking behavior tests
#
# These encode the contract from AGENTS.md that all versioned entities must
# satisfy:  read -> version N,  update with N -> N+1,  stale update -> conflict.
#
# A minimal in-memory store simulates persistence so the tests exercise the
# optimistic locking flow using the chapter contracts directly.  No HTTP layer
# exists yet, so stale-version conflicts surface as ValueError.
# ---------------------------------------------------------------------------


class _ChapterStore:
    """Minimal in-memory store that enforces optimistic locking via chapter contracts."""

    def __init__(self) -> None:
        self._data: dict[int, dict] = {}
        self._next_id = 1

    def create(self, payload: dict) -> object:
        _, ChapterCreate, ChapterRead, _ = _load_chapter_contracts()
        validated = ChapterCreate(**payload)
        item_id = self._next_id
        self._next_id += 1
        record = {
            "id": item_id,
            "name": validated.name,
            "slug": validated.slug,
            "status": "provisioning",
            "discord_category_id": None,
            "discord_officer_role_id": None,
            "discord_member_role_id": None,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "version": 0,
        }
        self._data[item_id] = record
        return ChapterRead(**record)

    def read(self, item_id: int) -> object:
        _, _, ChapterRead, _ = _load_chapter_contracts()
        return ChapterRead(**self._data[item_id])

    def update(self, item_id: int, payload: dict) -> object:
        _, _, ChapterRead, ChapterUpdate = _load_chapter_contracts()
        validated = ChapterUpdate(**payload)
        current = self._data[item_id]
        if validated.version != current["version"]:
            raise ValueError(
                f"Stale version: got {validated.version}, expected {current['version']}"
            )
        for field in ("name", "slug", "status", "discord_category_id",
                       "discord_officer_role_id", "discord_member_role_id"):
            value = getattr(validated, field, None)
            if value is not None:
                current[field] = value
        current["version"] += 1
        return ChapterRead(**current)


@pytest.fixture()
def chapter_store() -> _ChapterStore:
    return _ChapterStore()


def test_optimistic_locking_read_returns_version_n(chapter_store: _ChapterStore) -> None:
    """Read entity -> get version N."""
    entity = chapter_store.create({"name": "Humility Seattle", "slug": "humility-seattle"})
    read = chapter_store.read(entity.id)
    assert read.version == 0


def test_optimistic_locking_update_with_version_n_succeeds_version_becomes_n_plus_1(
    chapter_store: _ChapterStore,
) -> None:
    """Update with version N -> succeeds, version becomes N+1."""
    entity = chapter_store.create({"name": "Humility Seattle", "slug": "humility-seattle"})

    updated = chapter_store.update(
        entity.id, {"version": entity.version, "name": "Humility Portland"},
    )

    assert updated.version == entity.version + 1


def test_optimistic_locking_stale_version_raises_conflict(
    chapter_store: _ChapterStore,
) -> None:
    """Update with stale version -> raises ValueError (contract-level 409)."""
    entity = chapter_store.create({"name": "Humility Seattle", "slug": "humility-seattle"})

    # First update succeeds: version 0 -> 1
    chapter_store.update(entity.id, {"version": 0, "name": "Humility Portland"})

    # Second update with stale version 0 -> conflict
    with pytest.raises(ValueError, match="Stale version"):
        chapter_store.update(entity.id, {"version": 0, "name": "Stale Name"})


def test_optimistic_locking_sequential_updates_increment_version_monotonically(
    chapter_store: _ChapterStore,
) -> None:
    """Sequential updates with correct versions increment monotonically."""
    entity = chapter_store.create({"name": "v0", "slug": "humility-seattle"})

    r1 = chapter_store.update(entity.id, {"version": 0, "name": "v1"})
    r2 = chapter_store.update(entity.id, {"version": 1, "name": "v2"})
    r3 = chapter_store.update(entity.id, {"version": 2, "name": "v3"})

    assert r1.version == 1
    assert r2.version == 2
    assert r3.version == 3
