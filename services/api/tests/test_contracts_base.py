import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi import HTTPException
from pydantic import BaseModel
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.contracts import VersionedMixin as ExportedVersionedMixin
from app.contracts.base import VersionedMixin


class ExampleVersionedModel(VersionedMixin):
    name: str


# ---------------------------------------------------------------------------
# Schema / field-shape tests
# ---------------------------------------------------------------------------


def test_versioned_mixin_is_importable_from_contracts_package() -> None:
    assert ExportedVersionedMixin is VersionedMixin


def test_versioned_mixin_is_a_pydantic_base_model_subclass() -> None:
    assert issubclass(VersionedMixin, BaseModel)


def test_version_field_is_required() -> None:
    with pytest.raises(ValidationError):
        VersionedMixin()


def test_version_field_accepts_non_negative_integer_values() -> None:
    model = VersionedMixin(version=0)

    assert model.version == 0
    assert isinstance(model.version, int)


def test_version_field_rejects_negative_values() -> None:
    with pytest.raises(ValidationError):
        VersionedMixin(version=-1)


def test_version_field_rejects_non_integer_values() -> None:
    with pytest.raises(ValidationError):
        VersionedMixin(version="not-an-int")


def test_version_field_coerces_numeric_strings_to_int() -> None:
    model = VersionedMixin(version="7")

    assert model.version == 7
    assert isinstance(model.version, int)


def test_json_schema_marks_version_as_required() -> None:
    schema = VersionedMixin.model_json_schema()

    assert "version" in schema["required"]


def test_json_schema_describes_version_as_non_negative_integer() -> None:
    schema = VersionedMixin.model_json_schema()
    version_schema = schema["properties"]["version"]

    assert version_schema["type"] == "integer"
    assert version_schema["minimum"] == 0


def test_subclasses_inherit_version_field() -> None:
    model = ExampleVersionedModel(name="Humility", version=3)

    assert model.name == "Humility"
    assert model.version == 3


# ---------------------------------------------------------------------------
# Optimistic locking behavior tests
#
# These encode the contract from AGENTS.md that all versioned entities must
# satisfy:  read -> version N,  update with N -> N+1,  stale update -> 409.
#
# A minimal in-process FastAPI app is used as the test fixture so the tests
# exercise the HTTP contract (including status codes) without depending on
# any real entity endpoint that doesn't exist yet.
# ---------------------------------------------------------------------------


class _ItemCreate(BaseModel):
    name: str


class _ItemRead(VersionedMixin):
    id: int
    name: str


class _ItemUpdate(VersionedMixin):
    name: str


def _build_versioned_entity_app() -> FastAPI:
    """Return a minimal FastAPI app with create/read/update for a versioned entity."""
    app = FastAPI()
    store: dict[int, dict] = {}
    next_id = {"value": 1}

    @app.post("/items", response_model=_ItemRead, status_code=201)
    def create_item(body: _ItemCreate) -> _ItemRead:
        item_id = next_id["value"]
        next_id["value"] += 1
        store[item_id] = {"id": item_id, "name": body.name, "version": 0}
        return _ItemRead(**store[item_id])

    @app.get("/items/{item_id}", response_model=_ItemRead)
    def read_item(item_id: int) -> _ItemRead:
        if item_id not in store:
            raise HTTPException(status_code=404)
        return _ItemRead(**store[item_id])

    @app.put("/items/{item_id}", response_model=_ItemRead)
    def update_item(item_id: int, body: _ItemUpdate) -> _ItemRead:
        if item_id not in store:
            raise HTTPException(status_code=404)
        current = store[item_id]
        if body.version != current["version"]:
            raise HTTPException(status_code=409, detail="Stale version")
        current["name"] = body.name
        current["version"] += 1
        return _ItemRead(**current)

    return app


@pytest.fixture()
def versioned_app() -> FastAPI:
    return _build_versioned_entity_app()


@pytest.mark.asyncio()
async def test_newly_created_entity_has_version_zero(versioned_app: FastAPI) -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=versioned_app), base_url="http://test") as client:
        resp = await client.post("/items", json={"name": "Humility"})

    assert resp.status_code == 201
    assert resp.json()["version"] == 0


@pytest.mark.asyncio()
async def test_read_entity_returns_current_version(versioned_app: FastAPI) -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=versioned_app), base_url="http://test") as client:
        create_resp = await client.post("/items", json={"name": "Humility"})
        item_id = create_resp.json()["id"]

        read_resp = await client.get(f"/items/{item_id}")

    assert read_resp.status_code == 200
    assert read_resp.json()["version"] == 0


@pytest.mark.asyncio()
async def test_update_with_current_version_succeeds_and_increments(versioned_app: FastAPI) -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=versioned_app), base_url="http://test") as client:
        create_resp = await client.post("/items", json={"name": "Humility"})
        item_id = create_resp.json()["id"]
        current_version = create_resp.json()["version"]

        update_resp = await client.put(
            f"/items/{item_id}",
            json={"name": "Humility Updated", "version": current_version},
        )

    assert update_resp.status_code == 200
    assert update_resp.json()["version"] == current_version + 1


@pytest.mark.asyncio()
async def test_update_with_stale_version_returns_409(versioned_app: FastAPI) -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=versioned_app), base_url="http://test") as client:
        create_resp = await client.post("/items", json={"name": "Humility"})
        item_id = create_resp.json()["id"]
        stale_version = create_resp.json()["version"]

        await client.put(
            f"/items/{item_id}",
            json={"name": "First Update", "version": stale_version},
        )

        conflict_resp = await client.put(
            f"/items/{item_id}",
            json={"name": "Stale Update", "version": stale_version},
        )

    assert conflict_resp.status_code == 409


@pytest.mark.asyncio()
async def test_sequential_updates_increment_version_monotonically(versioned_app: FastAPI) -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=versioned_app), base_url="http://test") as client:
        create_resp = await client.post("/items", json={"name": "v0"})
        item_id = create_resp.json()["id"]

        resp1 = await client.put(f"/items/{item_id}", json={"name": "v1", "version": 0})
        resp2 = await client.put(f"/items/{item_id}", json={"name": "v2", "version": 1})
        resp3 = await client.put(f"/items/{item_id}", json={"name": "v3", "version": 2})

    assert resp1.json()["version"] == 1
    assert resp2.json()["version"] == 2
    assert resp3.json()["version"] == 3
