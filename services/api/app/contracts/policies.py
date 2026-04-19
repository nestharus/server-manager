from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.contracts.scope import ScopeKind


POLICY_AGGREGATE_SCOPE_MISSING = ""


def _canonicalize_content(content: dict[str, Any]) -> str:
    try:
        return json.dumps(
            content,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("policy content must be canonical JSON") from exc


class PolicyPreviewRequest(BaseModel):
    policy_type: str = Field(min_length=1)
    scope_kind: ScopeKind
    scope_id: str | None = None
    expected_current_version: int = Field(ge=0)
    content: dict[str, Any]

    @model_validator(mode="after")
    def validate_content(self) -> "PolicyPreviewRequest":
        _canonicalize_content(self.content)
        return self


class PolicyPreviewRead(BaseModel):
    preview_token: str = Field(min_length=1)
    current_version: int = Field(ge=0)
    affected_objects: list[dict[str, Any]]
    rollback_summary: dict[str, Any]


class PolicyConfirmRequest(BaseModel):
    preview_token: str = Field(min_length=1)
    policy_type: str = Field(min_length=1)
    scope_kind: ScopeKind
    scope_id: str | None = None
    expected_current_version: int = Field(ge=0)
    content: dict[str, Any]

    @model_validator(mode="after")
    def validate_content(self) -> "PolicyConfirmRequest":
        _canonicalize_content(self.content)
        return self


class PolicyVersionRead(BaseModel):
    id: UUID
    policy_type: str
    scope_kind: ScopeKind
    scope_id: str | None = None
    version_number: int = Field(ge=1)
    effective_at: datetime


class PolicyPreviewTokenMismatchError(Exception):
    def __init__(self) -> None:
        super().__init__("policy preview token does not match confirm payload")


__all__ = [
    "POLICY_AGGREGATE_SCOPE_MISSING",
    "PolicyConfirmRequest",
    "PolicyPreviewRead",
    "PolicyPreviewRequest",
    "PolicyPreviewTokenMismatchError",
    "PolicyVersionRead",
    "_canonicalize_content",
]
