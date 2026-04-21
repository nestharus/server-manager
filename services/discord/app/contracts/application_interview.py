from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _ApplicationInterviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApplicationInterviewCommand(_ApplicationInterviewModel):
    application_id: str = Field(min_length=1)
    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("reason must not be blank")
        return stripped


class ApplicationInterviewResult(_ApplicationInterviewModel):
    success: bool
    application_id: str
    thread_id: str | None = None
    response_text: str


__all__ = ["ApplicationInterviewCommand", "ApplicationInterviewResult"]
