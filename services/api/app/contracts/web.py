from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.contracts.application_messages import ApplicationMessageVisibility


class _WebModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CurrentPrincipalRead(_WebModel):
    subject: str
    email: str | None = None
    display_name: str | None = None
    provider: Literal["pomerium"] = "pomerium"
    groups: list[str] = []
    discord_user_id: str | None = None


class OfficerApplicationMessageAppendRequest(_WebModel):
    model_config = ConfigDict(extra="ignore")

    body_markdown: str = Field(min_length=1)
    visibility: ApplicationMessageVisibility
    client_message_id: str | None = None

    @field_validator("body_markdown")
    @classmethod
    def body_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("body_markdown must not be blank")
        return value


class AdminChapterSummaryRead(_WebModel):
    id: str
    name: str
    state: str
    version: int = Field(ge=1)
    created_at: datetime


class AdminChapterListRead(_WebModel):
    chapters: list[AdminChapterSummaryRead]
