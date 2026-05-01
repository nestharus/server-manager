from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.contracts.scope import ScopeKind


FIELD_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
APPLICATION_REASSIGN_ACTION_TYPE = "application.reassign"
APPLICATION_REASSIGN_CHANGE_TYPE = "application.reassigned"
APPLICATION_REASSIGN_PAYLOAD_ALLOWLIST = frozenset({"new_owner_id"})
JSONValue: TypeAlias = Any
_VISIBLE_WHEN_SCALAR_SOURCE_TYPES = frozenset(
    {"short", "long", "number", "select", "boolean"}
)


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
    interview = "interview"
    waitlisted = "waitlisted"
    approved = "approved"
    denied = "denied"
    withdrawn = "withdrawn"


class ApplicationTransitionAction(str, Enum):
    route = "route"
    claim = "claim"
    review = "review"
    request_interview = "request_interview"
    waitlist = "waitlist"
    reassign = "reassign"
    reactivate = "reactivate"
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
        if self.scope_kind in {"chapter", "member"}:
            if self.scope_id is None or not self.scope_id.strip():
                raise ValueError(f"{self.scope_kind} scope requires scope_id")
            object.__setattr__(self, "scope_id", self.scope_id.strip())
        return self

    def as_persisted(self) -> dict[str, str | None]:
        return {"scope_kind": self.scope_kind, "scope_id": self.scope_id}


def _is_visible_when_scalar(value: Any) -> bool:
    return isinstance(value, str | int | float | bool)


class FormFieldVisibleWhen(_ApplicationModel):
    field_id: str
    op: Literal["eq", "neq", "in", "not_in"]
    value: JSONValue

    @field_validator("field_id")
    @classmethod
    def validate_field_id(cls, value: str) -> str:
        if not FIELD_ID_PATTERN.fullmatch(value):
            raise ValueError("visible_when field_id must match ^[a-z][a-z0-9_]{0,63}$")
        return value

    @model_validator(mode="after")
    def validate_value_shape(self) -> "FormFieldVisibleWhen":
        if self.op in {"eq", "neq"}:
            if not _is_visible_when_scalar(self.value):
                raise ValueError("visible_when eq/neq value must be a scalar")
            return self

        if not isinstance(self.value, list):
            raise ValueError("visible_when in/not_in value must be a list")
        if not self.value:
            raise ValueError("visible_when in/not_in value must not be empty")
        if any(not _is_visible_when_scalar(item) for item in self.value):
            raise ValueError("visible_when in/not_in values must be scalars")
        if len(self.value) != len(set(self.value)):
            raise ValueError("visible_when in/not_in values must be unique")
        return self


class _BaseFormField(_ApplicationModel):
    id: str
    label: str
    required: bool = False
    page: int = Field(default=1, ge=1)
    visible_when: FormFieldVisibleWhen | None = None

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


class _NoOptionsMixin(_BaseFormField):
    options: None = None
    type: str


class FormFieldShort(_NoOptionsMixin):
    type: Literal["short"]
    max_length: int | None = None

    @model_validator(mode="after")
    def validate_short_shape(self) -> "FormFieldShort":
        if self.max_length is not None and not 1 <= self.max_length <= 256:
            raise ValueError("short max_length must be between 1 and 256")
        return self


class FormFieldLong(_NoOptionsMixin):
    type: Literal["long"]
    max_length: int | None = None

    @model_validator(mode="after")
    def validate_long_shape(self) -> "FormFieldLong":
        if self.max_length is not None and not 1 <= self.max_length <= 4096:
            raise ValueError("long max_length must be between 1 and 4096")
        return self


class FormFieldNumber(_BaseFormField):
    type: Literal["number"]
    max_length: None = None
    options: None = None


class _OptionsField(_BaseFormField):
    max_length: None = None
    options: list[str]

    @model_validator(mode="after")
    def validate_options_shape(self) -> "_OptionsField":
        if not 1 <= len(self.options) <= 50:
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
        object.__setattr__(self, "options", normalized)
        return self


class FormFieldSelect(_OptionsField):
    type: Literal["select"]


class FormFieldMultiSelect(_OptionsField):
    type: Literal["multi_select"]


class FormFieldBoolean(_BaseFormField):
    type: Literal["boolean"]
    max_length: None = None
    options: None = None


class FormFieldChapterSelect(_BaseFormField):
    type: Literal["chapter_select"]
    required: Literal[True] = True
    visible_when: None = None
    placeholder: str | None = None
    max_length: None = None
    options: None = None

    @field_validator("placeholder")
    @classmethod
    def validate_placeholder(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("chapter_select placeholder must not be blank")
        if len(stripped) > 160:
            raise ValueError("chapter_select placeholder must be 160 characters or fewer")
        return stripped


ApplicationFormField: TypeAlias = Annotated[
    FormFieldShort
    | FormFieldLong
    | FormFieldNumber
    | FormFieldSelect
    | FormFieldMultiSelect
    | FormFieldBoolean
    | FormFieldChapterSelect,
    Field(discriminator="type"),
]

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

    @model_validator(mode="after")
    def validate_chapter_select_contract(self) -> "FormDefinitionPublish":
        chapter_select_fields = [
            field for field in self.fields if field.type == "chapter_select"
        ]
        if not chapter_select_fields:
            return self
        if len(chapter_select_fields) > 1:
            raise ValueError("forms may contain at most one chapter_select field")
        if self.scope.scope_kind != "global" or self.scope.scope_id is not None:
            raise ValueError("chapter_select fields are allowed only on global forms")
        if self.routing_rules.review_scope is not None:
            raise ValueError("chapter_select forms must not set routing_rules.review_scope")
        return self

    @model_validator(mode="after")
    def validate_visible_when_graph(self) -> "FormDefinitionPublish":
        seen_ids: dict[str, ApplicationFormField] = {}
        for field in self.fields:
            if field.visible_when is None:
                seen_ids[field.id] = field
                continue

            if field.type == "chapter_select":
                raise ValueError("chapter_select fields cannot set visible_when")

            source = seen_ids.get(field.visible_when.field_id)
            if source is None:
                raise ValueError(
                    f"visible_when source must reference an earlier field: {field.visible_when.field_id}"
                )
            if source.type not in _VISIBLE_WHEN_SCALAR_SOURCE_TYPES:
                raise ValueError(
                    f"visible_when source must be a scalar field: {field.visible_when.field_id}"
                )
            seen_ids[field.id] = field
        return self


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


class PublicApplicationSubmission(_ApplicationModel):
    scope: ApplicationScope
    responses: dict[str, JSONValue]
    client_application_id: str | None = None

    @field_validator("responses")
    @classmethod
    def _responses_non_empty(cls, value: dict[str, JSONValue]) -> dict[str, JSONValue]:
        if not value:
            raise ValueError("responses must be a non-empty object")
        return value

    @field_validator("client_application_id")
    @classmethod
    def _trim_client_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("client_application_id may not be blank")
        return trimmed


class PublicApplicationSubmissionReceipt(_ApplicationModel):
    message: str
    application_id: UUID


class ApplicationTransitionRequest(_ApplicationModel):
    action: ApplicationTransitionAction
    notes: str | None = None
    decision_reason: str | None = None
    thread_id: str | None = None
    reason: str | None = None
    new_owner_id: UUID | None = None
    # Originating actor fields are honored only for service-authenticated callers.
    # User and system callers are normalized to the authenticated actor in the
    # application service, so request bodies cannot spoof audit origin.
    originating_actor_kind: Literal["user", "service", "system"] | None = None
    originating_actor_id: str | None = None

    @field_validator("notes", "decision_reason", "thread_id", "reason", "originating_actor_id")
    @classmethod
    def validate_optional_nonblank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("optional string fields must not be blank")
        return stripped


class ApplicationInterviewRequest(_ApplicationModel):
    thread_id: str | None = None
    reason: str | None = None
    originating_actor_kind: Literal["user", "service", "system"]
    originating_actor_id: str = Field(min_length=1)

    @field_validator("thread_id", "reason")
    @classmethod
    def validate_optional_nonblank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("optional string fields must not be blank")
        return stripped

    @field_validator("originating_actor_id")
    @classmethod
    def validate_originating_actor_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("originating_actor_id must not be blank")
        return stripped


class ApplicationWaitlistRequest(_ApplicationModel):
    reason: str
    originating_actor_kind: Literal["user", "service", "system"]
    originating_actor_id: str = Field(min_length=1)

    @field_validator("reason", "originating_actor_id")
    @classmethod
    def validate_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank")
        return stripped


class ApplicationReactivateRequest(_ApplicationModel):
    new_owner_id: UUID | None = None
    reason: str | None = None
    originating_actor_kind: Literal["user", "service", "system"]
    originating_actor_id: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def validate_optional_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("reason must not be blank")
        return stripped

    @field_validator("originating_actor_id")
    @classmethod
    def validate_originating_actor_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("originating_actor_id must not be blank")
        return stripped


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
    interview_thread_id: str | None = None
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


class ApplicationListRead(_ApplicationModel):
    items: list[ApplicationRead]
    next_after_id: UUID | None = None


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


class ApplicationWaitlistReasonRequiredError(Exception):
    def __init__(self) -> None:
        super().__init__("reason is required for waitlist")


class ApplicationReactivateOwnerRequiredError(Exception):
    def __init__(self) -> None:
        super().__init__("reactivate requires an existing owner or new_owner_id")


class ApplicationInterviewThreadMismatchError(Exception):
    def __init__(
        self,
        *,
        current_thread_id: str,
        requested_thread_id: str | None,
    ) -> None:
        self.current_thread_id = current_thread_id
        self.requested_thread_id = requested_thread_id
        super().__init__("application interview thread id does not match stored thread")


class ApplicationAlreadyClaimedError(Exception):
    def __init__(self, *, application: ApplicationRead) -> None:
        self.application = application
        super().__init__("application is already claimed")


class ApplicationNotOwnerError(Exception):
    def __init__(self, *, current_owner_id: UUID | None, actor_id: UUID) -> None:
        self.current_owner_id = current_owner_id
        self.actor_id = actor_id
        super().__init__("application is owned by a different reviewer")


class DuplicateApplicationCreateError(Exception):
    def __init__(self, application: ApplicationRead) -> None:
        self.application = application
        super().__init__(f"application {application.id} already exists for client_application_id")


class InvalidApplicationResponseError(ValueError):
    pass


class ApplicationListForbiddenError(Exception):
    def __init__(self) -> None:
        super().__init__("application list authority requirement denied")


__all__ = [
    "APPLICATION_REASSIGN_ACTION_TYPE",
    "APPLICATION_REASSIGN_CHANGE_TYPE",
    "APPLICATION_REASSIGN_PAYLOAD_ALLOWLIST",
    "ApplicationAlreadyClaimedError",
    "ApplicationCreate",
    "ApplicationDecisionReasonRequiredError",
    "ApplicationFormField",
    "ApplicationInterviewRequest",
    "ApplicationInterviewThreadMismatchError",
    "ApplicationListForbiddenError",
    "ApplicationListRead",
    "ApplicationNotFoundError",
    "ApplicationNotOwnerError",
    "ApplicationRead",
    "ApplicationReactivateOwnerRequiredError",
    "ApplicationReactivateRequest",
    "ApplicationReviewNotesRequiredError",
    "ApplicationReviewRead",
    "ApplicationRoutingRules",
    "ApplicationScope",
    "ApplicationState",
    "ApplicationSubmission",
    "ApplicationTransitionAction",
    "ApplicationTransitionRequest",
    "ApplicationWaitlistReasonRequiredError",
    "ApplicationWaitlistRequest",
    "DuplicateApplicationCreateError",
    "FormDefinitionCreate",
    "FormDefinitionNotFoundError",
    "FormDefinitionPublish",
    "FormDefinitionRead",
    "FormFieldBoolean",
    "FormFieldChapterSelect",
    "FormFieldLong",
    "FormFieldMultiSelect",
    "FormFieldNumber",
    "FormFieldSelect",
    "FormFieldSpec",
    "FormFieldShort",
    "FormFieldVisibleWhen",
    "FormRoutingRules",
    "FormStatus",
    "FormTargetType",
    "InvalidApplicationResponseError",
    "InvalidApplicationTransitionError",
    "JSONValue",
    "PublicApplicationSubmission",
    "PublicApplicationSubmissionReceipt",
]
