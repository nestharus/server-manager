from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


ChapterState = Literal["proposed", "provisioning", "active", "provisioning_failed"]
ChapterId = str
OriginatingActorKind = Literal["user", "service"]


class _ChapterModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChapterDiscordResources(_ChapterModel):
    category_id: str | None = None
    role_ids: dict[str, str] = Field(default_factory=dict)
    channel_ids: dict[str, str] = Field(default_factory=dict)


class ChapterCreate(_ChapterModel):
    name: str = Field(min_length=1, max_length=100)
    template_id: UUID
    configuration: dict[str, Any] = Field(default_factory=dict)
    originating_actor_kind: OriginatingActorKind = "user"
    originating_actor_id: str = Field(min_length=1)


class ChapterRead(_ChapterModel):
    id: ChapterId
    name: str
    template_id: UUID
    template_snapshot: dict[str, Any]
    configuration: dict[str, Any]
    state: ChapterState
    discord_resources: ChapterDiscordResources
    created_at: datetime
    version: int = Field(ge=1)


class ChapterTransitionRequest(_ChapterModel):
    to_state: ChapterState
    reason: str = Field(min_length=1)
    originating_actor_kind: OriginatingActorKind = "user"
    originating_actor_id: str = Field(min_length=1)


class ChapterResourcesPatchRequest(_ChapterModel):
    resources: ChapterDiscordResources


class ChapterTransitionRead(_ChapterModel):
    id: UUID
    chapter_id: ChapterId
    aggregate_seq: int = Field(ge=1)
    from_state: ChapterState
    to_state: ChapterState
    actor_kind: str
    actor_id: str
    originating_actor_kind: str | None = None
    originating_actor_id: str | None = None
    reason: str
    recorded_at: datetime
    version: int = Field(ge=1)


class ChapterNotFoundError(Exception):
    def __init__(self, chapter_id: str) -> None:
        self.chapter_id = chapter_id
        super().__init__(f"chapter {chapter_id} was not found")


class ChapterDuplicateNameError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"chapter name already exists: {name}")


class InvalidChapterTransitionError(Exception):
    def __init__(self, *, chapter_id: str, from_state: str, to_state: str) -> None:
        self.chapter_id = chapter_id
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"invalid chapter transition for {chapter_id}: {from_state} -> {to_state}"
        )


class IncompleteProvisioningError(Exception):
    def __init__(self, *, missing: str) -> None:
        self.missing = missing
        super().__init__(f"incomplete provisioning: missing {missing}")


__all__ = [
    "ChapterCreate",
    "ChapterDiscordResources",
    "ChapterDuplicateNameError",
    "ChapterId",
    "ChapterNotFoundError",
    "ChapterRead",
    "ChapterResourcesPatchRequest",
    "ChapterState",
    "ChapterTransitionRead",
    "ChapterTransitionRequest",
    "IncompleteProvisioningError",
    "InvalidChapterTransitionError",
]
