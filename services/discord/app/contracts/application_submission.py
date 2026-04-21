from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _ApplicationSubmissionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApplicationSubmissionCommand(_ApplicationSubmissionModel):
    scope_kind: str = Field(min_length=1)
    scope_id: str | None = None
    responses: dict[str, Any]


class ApplicationSubmissionResult(_ApplicationSubmissionModel):
    success: bool
    application_id: str | None = None
    response_text: str


__all__ = ["ApplicationSubmissionCommand", "ApplicationSubmissionResult"]
