from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _ApplicationReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApplicationReviewCommand(_ApplicationReviewModel):
    application_id: str = Field(min_length=1)
    action: Literal["claim", "approve", "deny"]
    notes: str | None = None
    decision_reason: str | None = None


class ApplicationReviewResult(_ApplicationReviewModel):
    success: bool
    application_id: str
    state: str | None = None
    response_text: str


__all__ = ["ApplicationReviewCommand", "ApplicationReviewResult"]
