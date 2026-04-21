from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


ChapterState = Literal[
    "proposed",
    "provisioning",
    "active",
    "provisioning_failed",
    "probation",
    "archiving",
    "archived",
]
ChapterId = str
OriginatingActorKind = Literal["user", "service"]
ChapterGovernanceAction = Literal["suspend", "restore", "archive"]
ArchiveRunStatus = Literal["in_progress", "completed", "cancelled"]
ArchiveBlockerKind = Literal[
    "application",
    "ticket",
    "authority_grant",
    "deferred_effect",
    "roster_entry",
    "chapter_role",
    "discord_resource",
    "manual_review",
]


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


class ChapterGovernanceTransitionRequest(_ChapterModel):
    action: ChapterGovernanceAction
    to_state: Literal["probation", "active", "archiving"]
    reason: str = Field(min_length=1)
    originating_actor_kind: OriginatingActorKind = "user"
    originating_actor_id: str = Field(min_length=1)

    @field_validator("reason", "originating_actor_id")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped


class ChapterArchivePlanSectionRead(_ChapterModel):
    count: int = Field(ge=0)
    sample_ids: list[str] = Field(default_factory=list)
    has_more: bool = False


class ChapterArchiveBlockerRead(_ChapterModel):
    kind: ArchiveBlockerKind
    item_id: str
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChapterArchivePlanRead(_ChapterModel):
    chapter_id: ChapterId
    chapter_state: ChapterState
    generated_at: datetime
    pending_applications: ChapterArchivePlanSectionRead
    open_tickets: ChapterArchivePlanSectionRead
    active_authority_grants: ChapterArchivePlanSectionRead
    unresolved_deferred_effects: ChapterArchivePlanSectionRead
    active_roster_entries: ChapterArchivePlanSectionRead
    chapter_roles: ChapterArchivePlanSectionRead
    discord_resources: ChapterDiscordResources
    blockers: list[ChapterArchiveBlockerRead] = Field(default_factory=list)


class ChapterArchiveExecuteRequest(_ChapterModel):
    archive_reason: str = Field(min_length=1)

    @field_validator("archive_reason")
    @classmethod
    def validate_archive_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("archive_reason must not be blank")
        return stripped


class ChapterArchiveStatusRead(_ChapterModel):
    archive_run_id: UUID | None = None
    chapter_id: ChapterId
    chapter_state: ChapterState
    status: ArchiveRunStatus | None = None
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    archive_reason: str | None = None
    initiated_by_kind: str | None = None
    initiated_by_id: str | None = None
    initiated_at: datetime | None = None
    completed_at: datetime | None = None
    manual_review_items: list[ChapterArchiveBlockerRead] = Field(default_factory=list)
    plan: ChapterArchivePlanRead | None = None


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


class InvalidChapterGovernanceTransitionError(Exception):
    def __init__(
        self,
        *,
        chapter_id: str,
        action: str,
        from_state: str,
        to_state: str,
    ) -> None:
        self.chapter_id = chapter_id
        self.action = action
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"invalid chapter governance transition for {chapter_id}: "
            f"{from_state} --{action}--> {to_state}"
        )


class ChapterArchiveInProgressError(Exception):
    def __init__(self, *, archive_run_id: UUID, correlation_id: UUID) -> None:
        self.archive_run_id = archive_run_id
        self.correlation_id = correlation_id
        super().__init__(f"chapter archive already in progress: {archive_run_id}")


class ChapterArchivePrerequisitesError(Exception):
    def __init__(self, *, chapter_id: str, state: str) -> None:
        self.chapter_id = chapter_id
        self.state = state
        super().__init__(f"chapter {chapter_id} cannot be archived from {state}")


__all__ = [
    "ChapterCreate",
    "ChapterArchiveBlockerRead",
    "ChapterArchiveExecuteRequest",
    "ChapterArchiveInProgressError",
    "ChapterArchivePlanRead",
    "ChapterArchivePlanSectionRead",
    "ChapterArchivePrerequisitesError",
    "ChapterArchiveStatusRead",
    "ChapterGovernanceAction",
    "ChapterGovernanceTransitionRequest",
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
    "InvalidChapterGovernanceTransitionError",
    "InvalidChapterTransitionError",
]
