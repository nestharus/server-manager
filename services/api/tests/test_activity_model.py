"""Tests for the Activity/Audit Model.

These tests encode the specification from the Activity/Audit Model proposal
(planning/plans/proposals/activity-audit-model.md). They are written test-first and
will fail until the implementation is complete.

Sections:
1. Activity action and state change contract validation (Pydantic models)
2. ETag/If-Match header flow (self-contained proof of the HTTP concurrency
   pattern that replaces body-version locking)
3. Activity stream append-only invariant
4. Chapters-as-first-aggregate proof-of-concept
"""

import importlib
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ===========================================================================
# Section 1 — Activity action and state change contract validation
#
# Validates that Pydantic models for activity actions, state changes, and
# aggregate heads have the correct field shapes, required fields, and
# validation rules per the proposal (sections 3-5).
# ===========================================================================


def _load_activity_contracts() -> tuple:
    """Import activity contract models, failing clearly if the module is missing."""
    try:
        module = importlib.import_module("app.contracts.activity")
    except ModuleNotFoundError as exc:
        pytest.fail(
            f"Expected contract module app.contracts.activity to exist: {exc}"
        )

    return (
        module.ActionStatus,
        module.ActionRecord,
        module.StateChangeRecord,
        module.AggregateHead,
    )


def _valid_action_record_payload() -> dict[str, Any]:
    """Minimal valid payload for an ActionRecord per proposal section 5."""
    return {
        "id": 1,
        "action_type": "chapter.create",
        "aggregate_type": "chapter",
        "aggregate_id": 42,
        "actor_kind": "user",
        "actor_id": "user-123",
        "request_surface": "api:/api/v1/chapters",
        "request_json": {"name": "Humility Seattle", "slug": "humility-seattle"},
        "status": "accepted",
        "reason_text": None,
        "recorded_at": datetime(2026, 4, 15, tzinfo=UTC),
    }


def _valid_state_change_payload() -> dict[str, Any]:
    """Minimal valid payload for a StateChangeRecord per proposal section 5."""
    return {
        "id": 1,
        "action_id": 1,
        "aggregate_type": "chapter",
        "aggregate_id": 42,
        "aggregate_seq": 1,
        "change_type": "chapter.created",
        "payload_json": {
            "name": "Humility Seattle",
            "slug": "humility-seattle",
            "status": "provisioning",
        },
        "diff_json": None,
        "recorded_at": datetime(2026, 4, 15, tzinfo=UTC),
    }


def _valid_aggregate_head_payload() -> dict[str, Any]:
    """Minimal valid payload for an AggregateHead per proposal section 3."""
    return {
        "aggregate_type": "chapter",
        "aggregate_id": 42,
        "current_seq": 1,
        "latest_change_id": 1,
    }


# --- ActionStatus enum tests ---


def test_action_status_has_exactly_four_members() -> None:
    ActionStatus, _, _, _ = _load_activity_contracts()

    assert set(ActionStatus.__members__) == {"accepted", "rejected", "failed", "noop"}
    assert len(ActionStatus.__members__) == 4


def test_action_status_values_are_strings() -> None:
    ActionStatus, _, _, _ = _load_activity_contracts()

    assert all(isinstance(member.value, str) for member in ActionStatus)


# --- ActionRecord contract tests ---


def test_action_record_accepts_valid_payload() -> None:
    _, ActionRecord, _, _ = _load_activity_contracts()
    payload = _valid_action_record_payload()

    record = ActionRecord(**payload)

    assert record.id == 1
    assert record.action_type == "chapter.create"
    assert record.aggregate_type == "chapter"
    assert record.aggregate_id == 42
    assert record.actor_kind == "user"
    assert record.actor_id == "user-123"
    assert record.request_surface == "api:/api/v1/chapters"
    assert record.request_json == {"name": "Humility Seattle", "slug": "humility-seattle"}
    assert record.reason_text is None
    assert record.recorded_at == datetime(2026, 4, 15, tzinfo=UTC)


@pytest.mark.parametrize(
    "missing_field",
    [
        "id",
        "action_type",
        "aggregate_type",
        "aggregate_id",
        "actor_kind",
        "actor_id",
        "request_surface",
        "request_json",
        "status",
        "recorded_at",
    ],
)
def test_action_record_requires_mandatory_fields(missing_field: str) -> None:
    _, ActionRecord, _, _ = _load_activity_contracts()
    payload = _valid_action_record_payload()
    payload.pop(missing_field)

    with pytest.raises(ValidationError):
        ActionRecord(**payload)


@pytest.mark.parametrize("status", ["accepted", "rejected", "failed", "noop"])
def test_action_record_accepts_valid_status_values(status: str) -> None:
    _, ActionRecord, _, _ = _load_activity_contracts()
    payload = _valid_action_record_payload()
    payload["status"] = status

    record = ActionRecord(**payload)

    assert record.status.value == status


def test_action_record_rejects_invalid_status() -> None:
    _, ActionRecord, _, _ = _load_activity_contracts()
    payload = _valid_action_record_payload()
    payload["status"] = "invalid_status"

    with pytest.raises(ValidationError):
        ActionRecord(**payload)


def test_action_record_allows_none_for_reason_text() -> None:
    _, ActionRecord, _, _ = _load_activity_contracts()
    payload = _valid_action_record_payload()

    record = ActionRecord(**payload)

    assert record.reason_text is None


def test_action_record_allows_string_for_reason_text_on_rejection() -> None:
    _, ActionRecord, _, _ = _load_activity_contracts()
    payload = _valid_action_record_payload()
    payload["status"] = "rejected"
    payload["reason_text"] = "Duplicate slug"

    record = ActionRecord(**payload)

    assert record.reason_text == "Duplicate slug"


# --- StateChangeRecord contract tests ---


def test_state_change_record_accepts_valid_payload() -> None:
    _, _, StateChangeRecord, _ = _load_activity_contracts()
    payload = _valid_state_change_payload()

    record = StateChangeRecord(**payload)

    assert record.id == 1
    assert record.action_id == 1
    assert record.aggregate_type == "chapter"
    assert record.aggregate_id == 42
    assert record.aggregate_seq == 1
    assert record.change_type == "chapter.created"
    assert record.payload_json == {
        "name": "Humility Seattle",
        "slug": "humility-seattle",
        "status": "provisioning",
    }
    assert record.diff_json is None
    assert record.recorded_at == datetime(2026, 4, 15, tzinfo=UTC)


@pytest.mark.parametrize(
    "missing_field",
    [
        "id",
        "action_id",
        "aggregate_type",
        "aggregate_id",
        "aggregate_seq",
        "change_type",
        "payload_json",
        "recorded_at",
    ],
)
def test_state_change_record_requires_mandatory_fields(missing_field: str) -> None:
    _, _, StateChangeRecord, _ = _load_activity_contracts()
    payload = _valid_state_change_payload()
    payload.pop(missing_field)

    with pytest.raises(ValidationError):
        StateChangeRecord(**payload)


def test_state_change_record_allows_none_for_diff_json() -> None:
    """diff_json is optional — None for creates, populated for updates."""
    _, _, StateChangeRecord, _ = _load_activity_contracts()
    payload = _valid_state_change_payload()
    payload["diff_json"] = None

    record = StateChangeRecord(**payload)

    assert record.diff_json is None


def test_state_change_record_accepts_dict_for_diff_json() -> None:
    _, _, StateChangeRecord, _ = _load_activity_contracts()
    payload = _valid_state_change_payload()
    payload["diff_json"] = {"name": {"old": "Seattle", "new": "Portland"}}

    record = StateChangeRecord(**payload)

    assert record.diff_json == {"name": {"old": "Seattle", "new": "Portland"}}


def test_state_change_aggregate_seq_must_be_positive() -> None:
    """Sequence numbers start at 1 (proposal section 4, hookpoint 2.3)."""
    _, _, StateChangeRecord, _ = _load_activity_contracts()
    payload = _valid_state_change_payload()
    payload["aggregate_seq"] = 0

    with pytest.raises(ValidationError):
        StateChangeRecord(**payload)


# --- AggregateHead contract tests ---


def test_aggregate_head_accepts_valid_payload() -> None:
    _, _, _, AggregateHead = _load_activity_contracts()
    payload = _valid_aggregate_head_payload()

    head = AggregateHead(**payload)

    assert head.aggregate_type == "chapter"
    assert head.aggregate_id == 42
    assert head.current_seq == 1
    assert head.latest_change_id == 1


@pytest.mark.parametrize(
    "missing_field",
    ["aggregate_type", "aggregate_id", "current_seq", "latest_change_id"],
)
def test_aggregate_head_requires_all_fields(missing_field: str) -> None:
    _, _, _, AggregateHead = _load_activity_contracts()
    payload = _valid_aggregate_head_payload()
    payload.pop(missing_field)

    with pytest.raises(ValidationError):
        AggregateHead(**payload)


def test_aggregate_head_current_seq_must_be_positive() -> None:
    _, _, _, AggregateHead = _load_activity_contracts()
    payload = _valid_aggregate_head_payload()
    payload["current_seq"] = 0

    with pytest.raises(ValidationError):
        AggregateHead(**payload)


# ===========================================================================
# Section 2 — ETag/If-Match header flow
#
# A self-contained minimal FastAPI app that proves the ETag/If-Match HTTP
# concurrency pattern. This replaces the body-version pattern tested in
# test_contracts_base.py and encodes the new contract from the proposal
# (sections 4 and 7).
#
# These tests pass independently of the implementation — they demonstrate
# the target HTTP contract.
# ===========================================================================


class _ETagItemCreate(BaseModel):
    name: str


class _ETagItemUpdate(BaseModel):
    name: str


def _build_etag_entity_app() -> FastAPI:
    """Minimal FastAPI app with ETag/If-Match concurrency.

    Mirrors the contract from the proposal:
    - Create returns ETag (initial head = seq 1)
    - Get returns ETag
    - Update requires If-Match, returns new ETag
    - Stale If-Match -> 412 Precondition Failed
    - Missing If-Match -> 428 Precondition Required
    - Response body has no version field
    """
    app = FastAPI()
    store: dict[int, dict[str, Any]] = {}
    heads: dict[int, int] = {}
    next_id = {"value": 1}

    @app.post("/items", status_code=201)
    def create_item(body: _ETagItemCreate, response: Response) -> dict:
        item_id = next_id["value"]
        next_id["value"] += 1
        store[item_id] = {"id": item_id, "name": body.name}
        heads[item_id] = 1
        response.headers["etag"] = f'"{heads[item_id]}"'
        return store[item_id]

    @app.get("/items/{item_id}")
    def get_item(item_id: int, response: Response) -> dict:
        if item_id not in store:
            raise HTTPException(status_code=404)
        response.headers["etag"] = f'"{heads[item_id]}"'
        return store[item_id]

    @app.put("/items/{item_id}")
    def update_item(
        item_id: int, body: _ETagItemUpdate, request: Request, response: Response,
    ) -> dict:
        if item_id not in store:
            raise HTTPException(status_code=404)
        if_match = request.headers.get("if-match")
        if if_match is None:
            raise HTTPException(
                status_code=428, detail="If-Match header required",
            )
        current_etag = f'"{heads[item_id]}"'
        if if_match != current_etag:
            raise HTTPException(status_code=412, detail="Precondition Failed")
        store[item_id]["name"] = body.name
        heads[item_id] += 1
        response.headers["etag"] = f'"{heads[item_id]}"'
        return store[item_id]

    return app


@pytest.fixture()
def etag_app() -> FastAPI:
    return _build_etag_entity_app()


@pytest.mark.asyncio()
async def test_etag_create_returns_etag_header(etag_app: FastAPI) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=etag_app), base_url="http://test",
    ) as client:
        resp = await client.post("/items", json={"name": "Humility"})

    assert resp.status_code == 201
    assert "etag" in resp.headers
    etag = resp.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')


@pytest.mark.asyncio()
async def test_etag_get_returns_matching_etag(etag_app: FastAPI) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=etag_app), base_url="http://test",
    ) as client:
        create_resp = await client.post("/items", json={"name": "Humility"})
        item_id = create_resp.json()["id"]

        get_resp = await client.get(f"/items/{item_id}")

    assert get_resp.status_code == 200
    assert get_resp.headers["etag"] == create_resp.headers["etag"]


@pytest.mark.asyncio()
async def test_etag_update_with_current_etag_succeeds_and_advances(
    etag_app: FastAPI,
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=etag_app), base_url="http://test",
    ) as client:
        create_resp = await client.post("/items", json={"name": "Humility"})
        item_id = create_resp.json()["id"]
        etag = create_resp.headers["etag"]

        update_resp = await client.put(
            f"/items/{item_id}",
            json={"name": "Updated"},
            headers={"if-match": etag},
        )

    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Updated"
    assert "etag" in update_resp.headers
    assert update_resp.headers["etag"] != etag


@pytest.mark.asyncio()
async def test_etag_update_with_stale_etag_returns_412(etag_app: FastAPI) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=etag_app), base_url="http://test",
    ) as client:
        create_resp = await client.post("/items", json={"name": "Humility"})
        item_id = create_resp.json()["id"]
        stale_etag = create_resp.headers["etag"]

        await client.put(
            f"/items/{item_id}",
            json={"name": "First Update"},
            headers={"if-match": stale_etag},
        )

        conflict_resp = await client.put(
            f"/items/{item_id}",
            json={"name": "Stale Update"},
            headers={"if-match": stale_etag},
        )

    assert conflict_resp.status_code == 412


@pytest.mark.asyncio()
async def test_etag_update_without_if_match_returns_428(etag_app: FastAPI) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=etag_app), base_url="http://test",
    ) as client:
        create_resp = await client.post("/items", json={"name": "Humility"})
        item_id = create_resp.json()["id"]

        resp = await client.put(
            f"/items/{item_id}",
            json={"name": "No Precondition"},
        )

    assert resp.status_code == 428


@pytest.mark.asyncio()
async def test_etag_sequential_updates_advance_etag_monotonically(
    etag_app: FastAPI,
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=etag_app), base_url="http://test",
    ) as client:
        create_resp = await client.post("/items", json={"name": "v0"})
        item_id = create_resp.json()["id"]
        etags = [create_resp.headers["etag"]]

        for i in range(1, 4):
            resp = await client.put(
                f"/items/{item_id}",
                json={"name": f"v{i}"},
                headers={"if-match": etags[-1]},
            )
            assert resp.status_code == 200
            etags.append(resp.headers["etag"])

    assert len(set(etags)) == 4
    for j in range(len(etags) - 1):
        assert etags[j] != etags[j + 1]


@pytest.mark.asyncio()
async def test_etag_response_body_has_no_version_field(etag_app: FastAPI) -> None:
    """Concurrency metadata is in ETag headers, not the response body."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=etag_app), base_url="http://test",
    ) as client:
        resp = await client.post("/items", json={"name": "Humility"})

    assert "version" not in resp.json()


@pytest.mark.asyncio()
async def test_etag_get_after_update_returns_new_etag(etag_app: FastAPI) -> None:
    """GET after a successful update reflects the advanced ETag."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=etag_app), base_url="http://test",
    ) as client:
        create_resp = await client.post("/items", json={"name": "Humility"})
        item_id = create_resp.json()["id"]
        etag = create_resp.headers["etag"]

        update_resp = await client.put(
            f"/items/{item_id}",
            json={"name": "Updated"},
            headers={"if-match": etag},
        )
        new_etag = update_resp.headers["etag"]

        get_resp = await client.get(f"/items/{item_id}")

    assert get_resp.headers["etag"] == new_etag


# ===========================================================================
# Section 3 — Activity stream append-only invariant
#
# Tests that in-memory activity stores enforce append-only semantics:
# records can be inserted and queried but never updated or deleted.
# Per proposal section 3, state changes are the source of truth for
# audit history and aggregate evolution.
# ===========================================================================


def _load_activity_store() -> Any:
    """Import the in-memory activity store, failing clearly if missing."""
    try:
        module = importlib.import_module("app.repositories.activity")
    except ModuleNotFoundError as exc:
        pytest.fail(
            f"Expected repository module app.repositories.activity to exist: {exc}"
        )
    return module


# --- InMemoryActionStore tests ---


def test_action_store_append_creates_record_with_auto_id() -> None:
    mod = _load_activity_store()
    store = mod.InMemoryActionStore()

    record = store.append(
        action_type="chapter.create",
        aggregate_type="chapter",
        aggregate_id=1,
        actor_kind="user",
        actor_id="user-1",
        request_surface="api:/api/v1/chapters",
        request_json={"name": "Test"},
        status="accepted",
    )

    assert record.id >= 1
    assert record.action_type == "chapter.create"
    assert record.status.value == "accepted"


def test_action_store_ids_are_monotonically_increasing() -> None:
    mod = _load_activity_store()
    store = mod.InMemoryActionStore()

    r1 = store.append(
        action_type="chapter.create",
        aggregate_type="chapter",
        aggregate_id=1,
        actor_kind="user",
        actor_id="user-1",
        request_surface="api",
        request_json={},
        status="accepted",
    )
    r2 = store.append(
        action_type="chapter.update",
        aggregate_type="chapter",
        aggregate_id=1,
        actor_kind="user",
        actor_id="user-1",
        request_surface="api",
        request_json={},
        status="accepted",
    )

    assert r2.id > r1.id


def test_action_store_has_no_update_method() -> None:
    """Append-only: no update capability."""
    mod = _load_activity_store()
    store = mod.InMemoryActionStore()

    assert not hasattr(store, "update")


def test_action_store_has_no_delete_method() -> None:
    """Append-only: no delete capability."""
    mod = _load_activity_store()
    store = mod.InMemoryActionStore()

    assert not hasattr(store, "delete")


def test_action_store_records_rejected_actions() -> None:
    """Rejected actions are recorded for audit but do not advance concurrency."""
    mod = _load_activity_store()
    store = mod.InMemoryActionStore()

    record = store.append(
        action_type="chapter.update",
        aggregate_type="chapter",
        aggregate_id=1,
        actor_kind="user",
        actor_id="user-1",
        request_surface="api",
        request_json={},
        status="rejected",
        reason_text="Duplicate slug",
    )

    assert record.status.value == "rejected"
    assert record.reason_text == "Duplicate slug"


def test_action_store_list_by_aggregate_returns_matching_records() -> None:
    mod = _load_activity_store()
    store = mod.InMemoryActionStore()

    store.append(
        action_type="chapter.create",
        aggregate_type="chapter",
        aggregate_id=1,
        actor_kind="user",
        actor_id="user-1",
        request_surface="api",
        request_json={},
        status="accepted",
    )
    store.append(
        action_type="chapter.create",
        aggregate_type="chapter",
        aggregate_id=2,
        actor_kind="user",
        actor_id="user-1",
        request_surface="api",
        request_json={},
        status="accepted",
    )

    actions = store.list_by_aggregate("chapter", 1)

    assert len(actions) == 1
    assert actions[0].aggregate_id == 1


# --- InMemoryStateChangeStore tests ---


def test_state_change_store_append_creates_record() -> None:
    mod = _load_activity_store()
    store = mod.InMemoryStateChangeStore()

    record = store.append(
        action_id=1,
        aggregate_type="chapter",
        aggregate_id=1,
        aggregate_seq=1,
        change_type="chapter.created",
        payload_json={"name": "Test", "slug": "test", "status": "provisioning"},
        diff_json=None,
    )

    assert record.id >= 1
    assert record.aggregate_seq == 1
    assert record.change_type == "chapter.created"


def test_state_change_store_enforces_monotonic_seq_per_aggregate() -> None:
    """Duplicate sequence for the same aggregate must be rejected."""
    mod = _load_activity_store()
    store = mod.InMemoryStateChangeStore()

    store.append(
        action_id=1,
        aggregate_type="chapter",
        aggregate_id=1,
        aggregate_seq=1,
        change_type="chapter.created",
        payload_json={},
        diff_json=None,
    )

    with pytest.raises((ValueError, Exception)):
        store.append(
            action_id=2,
            aggregate_type="chapter",
            aggregate_id=1,
            aggregate_seq=1,
            change_type="chapter.updated",
            payload_json={},
            diff_json=None,
        )


def test_state_change_store_allows_same_seq_for_different_aggregates() -> None:
    """Sequence is per-aggregate, so different aggregates can share seq=1."""
    mod = _load_activity_store()
    store = mod.InMemoryStateChangeStore()

    r1 = store.append(
        action_id=1,
        aggregate_type="chapter",
        aggregate_id=1,
        aggregate_seq=1,
        change_type="chapter.created",
        payload_json={},
        diff_json=None,
    )
    r2 = store.append(
        action_id=2,
        aggregate_type="chapter",
        aggregate_id=2,
        aggregate_seq=1,
        change_type="chapter.created",
        payload_json={},
        diff_json=None,
    )

    assert r1.aggregate_seq == 1
    assert r2.aggregate_seq == 1
    assert r1.id != r2.id


def test_state_change_store_has_no_update_method() -> None:
    """Append-only: no update capability."""
    mod = _load_activity_store()
    store = mod.InMemoryStateChangeStore()

    assert not hasattr(store, "update")


def test_state_change_store_has_no_delete_method() -> None:
    """Append-only: no delete capability."""
    mod = _load_activity_store()
    store = mod.InMemoryStateChangeStore()

    assert not hasattr(store, "delete")


def test_state_change_store_list_by_aggregate_returns_ordered_records() -> None:
    """Querying by aggregate returns state changes in sequence order."""
    mod = _load_activity_store()
    store = mod.InMemoryStateChangeStore()

    store.append(
        action_id=1,
        aggregate_type="chapter",
        aggregate_id=1,
        aggregate_seq=1,
        change_type="chapter.created",
        payload_json={"name": "Original"},
        diff_json=None,
    )
    store.append(
        action_id=2,
        aggregate_type="chapter",
        aggregate_id=1,
        aggregate_seq=2,
        change_type="chapter.updated",
        payload_json={"name": "Updated"},
        diff_json={"name": {"old": "Original", "new": "Updated"}},
    )

    changes = store.list_by_aggregate("chapter", 1)

    assert len(changes) == 2
    assert changes[0].aggregate_seq == 1
    assert changes[1].aggregate_seq == 2
    assert changes[0].change_type == "chapter.created"
    assert changes[1].change_type == "chapter.updated"


def test_state_change_store_records_link_back_to_action_id() -> None:
    """Each state change references the action that caused it."""
    mod = _load_activity_store()
    store = mod.InMemoryStateChangeStore()

    record = store.append(
        action_id=42,
        aggregate_type="chapter",
        aggregate_id=1,
        aggregate_seq=1,
        change_type="chapter.created",
        payload_json={},
        diff_json=None,
    )

    assert record.action_id == 42

