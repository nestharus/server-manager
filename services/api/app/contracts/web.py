from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _WebModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CurrentPrincipalRead(_WebModel):
    subject: str
    email: str | None = None
    display_name: str | None = None
    provider: Literal["pomerium"] = "pomerium"


class AdminChapterSummaryRead(_WebModel):
    id: str
    name: str
    state: str
    version: int = Field(ge=1)
    created_at: datetime


class AdminChapterListRead(_WebModel):
    chapters: list[AdminChapterSummaryRead]
