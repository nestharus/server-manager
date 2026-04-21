from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.contracts.scope import ScopeKind


FIELD_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class _ApplicationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FormStatus(str, Enum):
    current = "current"
    archived = "archived"


class FormTargetType(str, Enum):
    chapter_membership = "chapter_membership"
    officer_candidacy = "officer_candidacy"
    role_assignment = "role_assignment"
    custom = "custom"


class ApplicationState(str, Enum):
    submitted = "submitted"
    queued = "queued"
    claimed = "claimed"
    in_review = "in_review"
    approved = "approved"
    denied = "denied"
    withdrawn = "withdrawn"


class ApplicationTransitionAction(str, Enum):
    route = "route"
    claim = "claim"
    review = "review"
    approve = "approve"
    deny = "deny"
    withdraw = "withdraw"


class ApplicationScope(_ApplicationModel):
    scope_kind: ScopeKind
    scope_id: str | None = None

    @model_validator(mode="after")
    def validate_scope_id(self) -> "ApplicationScope":
        if self.scope_kind == "global" and self.scope_id is not None:
            raise ValueError("global scope must not set scope_id")
        if self.scope_kind in {"chapter", "member"} and (
            self.scope_id is None or not self.scope_id.strip()
        ):
            raise ValueError(f"{self.scope_kind} scope requires scope_id")
        return self

    def as_persisted(self) -> dict[str, str | None]:
        return {"scope_kind": self.scope_kind, "scope_id": self.scope_id}


class ApplicationFormField(_ApplicationModel):
    id: str
    type: Literal["short", "long", "number", "select", "multi_select", "boolean"]
    label: str
    required: bool = False
    max_length: int | None = None
    options: list[str] | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not FIELD_ID_PATTERN.fullmatch(value):
            raise ValueError("field id must match ^[a-z][a-z0-9_]{0,63}$")
        return value

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field label must not be blank")
        if len(stripped) > 160:
            raise ValueError("field label must be 160 characters or fewer")
        return stripped

    @model_validator(mode="after")
    def validate_shape(self) -> "ApplicationFormField":
        if self.type == "short":
            if self.options is not None:
                raise ValueError("short fields must not set options")
            if self.max_length is not None and not 1 <= self.max_length <= 256:
                raise ValueError("short max_length must be between 1 and 256")
            return self
        if self.type == "long":
            if self.options is not None:
                raise ValueError("long fields must not set options")
            if self.max_length is not None and not 1 <= self.max_length <= 4096:
                raise ValueError("long max_length must be between 1 and 4096")
            return self
        if self.type in {"number", "boolean"}:
            if self.max_length is not None or self.options is not None:
                raise ValueError(f"{self.type} fields must not set max_length or options")
            return self
        if self.type in {"select", "multi_select"}:
            if self.max_length is not None:
                raise ValueError(f"{self.type} fields must not set max_length")
            if self.options is None or not 1 <= len(self.options) <= 50:
                raise ValueError(f"{self.type} fields require 1-50 options")
            normalized: list[str] = []
            seen: set[str] = set()
            for option in self.options:
                stripped = option.strip()
                if not stripped:
                    raise ValueError("select options must not be blank")
                if stripped in seen:
                    raise ValueError("select options must be unique")
                seen.add(stripped)
                normalized.append(stripped)
            self.options = normalized
            return self
        return self


FormFieldSpec = ApplicationFormField


class FormRoutingRules(_ApplicationModel):
    schema_version: Literal[1] = 1
    queue: Literal["chapter_officers"] = "chapter_officers"
    review_scope: ApplicationScope | None = None


ApplicationRoutingRules = FormRoutingRules


class FormDefinitionPublish(_ApplicationModel):
    name: str = Field(min_length=1, max_length=160)
    target_type: FormTargetType
    scope: ApplicationScope
    fields: list[ApplicationFormField] = Field(min_length=1)
    routing_rules: FormRoutingRules

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped

    @field_validator("fields")
    @classmethod
    def validate_unique_field_ids(
        cls,
        value: list[ApplicationFormField],
    ) -> list[ApplicationFormField]:
        seen: set[str] = set()
        for field in value:
            if field.id in seen:
                raise ValueError(f"duplicate field id: {field.id}")
            seen.add(field.id)
        return value


FormDefinitionCreate = FormDefinitionPublish


class FormDefinitionRead(_ApplicationModel):
    id: UUID
    name: str
    target_type: FormTargetType
    scope: ApplicationScope
    fields: list[ApplicationFormField]
    routing_rules: FormRoutingRules
    version: int = Field(ge=1)
    status: FormStatus
    published_at: datetime
    archived_at: datetime | None = None
    created_at: datetime


class ApplicationSubmission(_ApplicationModel):
    applicant_id: UUID
    scope: ApplicationScope
    responses: dict[str, Any]
    client_application_id: str | None = None

    @field_validator("client_application_id")
    @classmethod
    def validate_client_application_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("client_application_id must not be blank")
        return stripped


ApplicationCreate = ApplicationSubmission


class ApplicationTransitionRequest(_ApplicationModel):
    action: ApplicationTransitionAction
    notes: str | None = None
    decision_reason: str | None = None


class ApplicationReviewRead(_ApplicationModel):
    id: UUID
    application_id: UUID
    aggregate_seq: int = Field(ge=1)
    reviewer_id: UUID | None = None
    actor_kind: Literal["user", "service", "system"]
    actor_id: str
    action: ApplicationTransitionAction
    from_state: ApplicationState
    to_state: ApplicationState
    notes: str | None = None
    decision_reason: str | None = None
    recorded_at: datetime


class ApplicationRead(_ApplicationModel):
    id: UUID
    applicant_id: UUID
    form_definition_id: UUID
    form_version: int = Field(ge=1)
    form_snapshot: dict[str, Any]
    target_scope: ApplicationScope
    responses: dict[str, Any]
    state: ApplicationState
    owner_id: UUID | None = None
    decision_reason: str | None = None
    submitted_at: datetime
    queued_at: datetime | None = None
    claimed_at: datetime | None = None
    review_started_at: datetime | None = None
    decided_at: datetime | None = None
    withdrawn_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    version: int = Field(ge=1)


class FormDefinitionNotFoundError(Exception):
    def __init__(self, scope: ApplicationScope | None = None, form_definition_id: UUID | None = None) -> None:
        self.scope = scope
        self.form_definition_id = form_definition_id
        if form_definition_id is not None:
            message = f"form definition {form_definition_id} was not found"
        elif scope is not None:
            message = f"current form definition was not found for {scope.scope_kind}:{scope.scope_id}"
        else:
            message = "form definition was not found"
        super().__init__(message)


class ApplicationNotFoundError(Exception):
    def __init__(self, application_id: UUID) -> None:
        self.application_id = application_id
        super().__init__(f"application {application_id} was not found")


class InvalidApplicationTransitionError(Exception):
    def __init__(self, *, application_id: UUID | None, from_state: str, action: str) -> None:
        self.application_id = application_id
        self.from_state = from_state
        self.action = action
        super().__init__(f"invalid application transition: {from_state} --{action}-->")


class ApplicationDecisionReasonRequiredError(Exception):
    def __init__(self, action: str) -> None:
        self.action = action
        super().__init__("decision_reason is required for approve and deny")


class ApplicationReviewNotesRequiredError(Exception):
    def __init__(self) -> None:
        super().__init__("notes are required for review")


class ApplicationAlreadyClaimedError(Exception):
    def __init__(self, *, application: ApplicationRead) -> None:
        self.application = application
        super().__init__("application is already claimed")


class DuplicateApplicationCreateError(Exception):
    def __init__(self, application: ApplicationRead) -> None:
        self.application = application
        super().__init__(f"application {application.id} already exists for client_application_id")


class InvalidApplicationResponseError(ValueError):
    pass


__all__ = [
    "ApplicationAlreadyClaimedError",
    "ApplicationCreate",
    "ApplicationDecisionReasonRequiredError",
    "ApplicationFormField",
    "ApplicationNotFoundError",
    "ApplicationRead",
    "ApplicationReviewNotesRequiredError",
    "ApplicationReviewRead",
    "ApplicationRoutingRules",
    "ApplicationScope",
    "ApplicationState",
    "ApplicationSubmission",
    "ApplicationTransitionAction",
    "ApplicationTransitionRequest",
    "DuplicateApplicationCreateError",
    "FormDefinitionCreate",
    "FormDefinitionNotFoundError",
    "FormDefinitionPublish",
    "FormDefinitionRead",
    "FormFieldSpec",
    "FormRoutingRules",
    "FormStatus",
    "FormTargetType",
    "InvalidApplicationResponseError",
    "InvalidApplicationTransitionError",
]
