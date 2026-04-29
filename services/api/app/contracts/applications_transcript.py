from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.application_messages import ApplicationMessageVisibility


class _ApplicationTranscriptModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApplicationTranscriptStateChangeEntry(_ApplicationTranscriptModel):
    type: Literal["state_change"] = "state_change"
    occurred_at: datetime
    change_type: str
    from_state: str | None = None
    to_state: str | None = None
    actor_kind: str
    actor_id: str
    aggregate_seq: int = Field(ge=1)


class ApplicationTranscriptMessageEntry(_ApplicationTranscriptModel):
    type: Literal["message"] = "message"
    occurred_at: datetime
    message_seq: int = Field(ge=1)
    author_actor_kind: str
    author_actor_id: str
    visibility: ApplicationMessageVisibility
    body_markdown: str


ApplicationTranscriptEntry = Annotated[
    ApplicationTranscriptStateChangeEntry | ApplicationTranscriptMessageEntry,
    Field(discriminator="type"),
]


class ApplicationTranscriptRead(_ApplicationTranscriptModel):
    application_id: UUID
    entries: list[ApplicationTranscriptEntry]


class ApplicationTranscriptForbiddenError(Exception):
    pass


__all__ = [
    "ApplicationTranscriptEntry",
    "ApplicationTranscriptForbiddenError",
    "ApplicationTranscriptMessageEntry",
    "ApplicationTranscriptRead",
    "ApplicationTranscriptStateChangeEntry",
]
