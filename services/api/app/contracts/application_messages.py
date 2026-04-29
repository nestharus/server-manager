from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


APPLICATION_MESSAGE_PERMISSION = "application.message"

ApplicationMessageVisibility = Literal["applicant_visible", "officer_only"]


class _ApplicationMessageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApplicationMessageAppendRequest(_ApplicationMessageModel):
    body_markdown: str = Field(min_length=1)
    visibility: ApplicationMessageVisibility
    client_message_id: str | None = None
    author_actor_kind: Literal["user", "service", "system"]
    author_actor_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_author(self) -> "ApplicationMessageAppendRequest":
        if not self.author_actor_id.strip():
            raise ValueError("author_actor_id must not be blank")
        return self


class ApplicationMessageRead(_ApplicationMessageModel):
    id: UUID
    application_id: UUID
    message_seq: int = Field(ge=1)
    author_actor_kind: str
    author_actor_id: str
    visibility: ApplicationMessageVisibility
    body_markdown: str
    client_message_id: str | None = None
    correlation_id: UUID
    causation_id: UUID | None = None
    created_at: datetime


class ApplicationMessageListRead(_ApplicationMessageModel):
    items: list[ApplicationMessageRead]


class ApplicationMessageVisibilityError(ValueError):
    pass


class ApplicationMessageAppendForbiddenError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class ApplicationMessageForbiddenError(ApplicationMessageAppendForbiddenError):
    pass


__all__ = [
    "APPLICATION_MESSAGE_PERMISSION",
    "ApplicationMessageAppendForbiddenError",
    "ApplicationMessageForbiddenError",
    "ApplicationMessageAppendRequest",
    "ApplicationMessageListRead",
    "ApplicationMessageRead",
    "ApplicationMessageVisibility",
    "ApplicationMessageVisibilityError",
]
