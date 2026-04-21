from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.contracts.chapters import (
    ChapterCreate,
    ChapterDiscordResources,
    ChapterRead,
    ChapterResourcesPatchRequest,
    ChapterTransitionRequest,
)


def test_chapter_create_contract_uses_template_uuid_and_originating_actor() -> None:
    template_id = uuid4()
    model = ChapterCreate(
        name="Humility Seattle",
        template_id=template_id,
        originating_actor_id="1001",
    )

    assert model.template_id == template_id
    assert model.originating_actor_kind == "user"
    assert model.configuration == {}


def test_chapter_read_contract_exposes_uuid_string_id_and_version() -> None:
    read = ChapterRead(
        id=str(uuid4()),
        name="Humility Seattle",
        template_id=uuid4(),
        template_snapshot={},
        configuration={},
        state="proposed",
        discord_resources=ChapterDiscordResources(),
        created_at=datetime(2026, 4, 20, tzinfo=UTC),
        version=1,
    )

    assert isinstance(read.id, str)
    assert read.version == 1


def test_chapter_transition_request_allows_retry_state() -> None:
    model = ChapterTransitionRequest(
        to_state="provisioning",
        reason="retry",
        originating_actor_id="1001",
    )

    assert model.to_state == "provisioning"


def test_chapter_resources_patch_wraps_structured_resources() -> None:
    model = ChapterResourcesPatchRequest(
        resources={
            "category_id": "cat-1",
            "role_ids": {"officer": "role-1"},
            "channel_ids": {"general": "chan-1"},
        }
    )

    assert model.resources.category_id == "cat-1"
    assert model.resources.role_ids == {"officer": "role-1"}
