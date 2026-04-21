from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _ApplicationWaitlistModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApplicationWaitlistCommand(_ApplicationWaitlistModel):
    application_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reason must not be blank")
        return stripped


class ApplicationReactivateCommand(_ApplicationWaitlistModel):
    application_id: str = Field(min_length=1)
    new_owner_id: str | None = None
    reason: str | None = None

    @field_validator("new_owner_id", "reason")
    @classmethod
    def validate_optional_nonblank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("optional fields must not be blank")
        return stripped


class ApplicationWaitlistResult(_ApplicationWaitlistModel):
    success: bool
    application_id: str
    state: str | None = None
    response_text: str


__all__ = [
    "ApplicationReactivateCommand",
    "ApplicationWaitlistCommand",
    "ApplicationWaitlistResult",
]
