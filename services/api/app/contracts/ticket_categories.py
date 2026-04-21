from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.contracts.scope import ScopeKind

TicketPrivacyLevel = Literal["reporter_staff", "staff_only"]


class _TicketCategoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RoutingScope(_TicketCategoryModel):
    scope_kind: ScopeKind
    scope_id: str | None = None
    queue: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_scope_id(self) -> "RoutingScope":
        if self.scope_kind == "global" and self.scope_id is not None:
            raise ValueError("global routing scope must not set scope_id")
        if self.scope_kind in {"chapter", "member"} and self.scope_id is None:
            raise ValueError(f"{self.scope_kind} routing scope requires scope_id")
        return self


class TicketStateDefinition(_TicketCategoryModel):
    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=80)
    terminal: bool


class TicketStateEdge(_TicketCategoryModel):
    from_state: str = Field(alias="from", min_length=1, max_length=64)
    to_state: str = Field(alias="to", min_length=1, max_length=64)
    action: str = Field(min_length=1, max_length=64)
    requires_reason: bool = False
    requires_resolution: bool = False
    allow_owner_change: bool = False
    allow_priority_change: bool = False


class TicketStateMachine(_TicketCategoryModel):
    schema_version: int
    initial_state: str = Field(min_length=1, max_length=64)
    states: list[TicketStateDefinition] = Field(min_length=1)
    edges: list[TicketStateEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_state_machine_shape(self) -> "TicketStateMachine":
        from app.services.ticket_categories import validate_state_machine

        validate_state_machine(self.model_dump(mode="python", by_alias=True))
        return self


TicketSlaConsequence = Literal[
    "notify_owner",
    "notify_scope",
    "flag_for_review",
    "auto_escalate",
]


class TicketSlaThreshold(_TicketCategoryModel):
    elapsed_seconds: int = Field(gt=0)
    consequence: TicketSlaConsequence
    target_state: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_target_state(self) -> "TicketSlaThreshold":
        if self.consequence == "auto_escalate" and self.target_state is None:
            raise ValueError("auto_escalate thresholds require target_state")
        if self.consequence != "auto_escalate" and self.target_state is not None:
            raise ValueError("target_state is only allowed for auto_escalate")
        return self


class TicketSlaRule(_TicketCategoryModel):
    key: str = Field(min_length=1, max_length=64)
    states: list[str] = Field(min_length=1)
    thresholds: list[TicketSlaThreshold] = Field(min_length=1)

    @field_validator("states")
    @classmethod
    def validate_states(cls, value: list[str]) -> list[str]:
        if any(not state.strip() for state in value):
            raise ValueError("states must not contain blanks")
        return value


class TicketSlaRules(_TicketCategoryModel):
    schema_version: int
    rules: list[TicketSlaRule] = Field(default_factory=list)


def _default_sla_rules() -> TicketSlaRules:
    return TicketSlaRules(schema_version=1, rules=[])


class TicketCategoryCreate(_TicketCategoryModel):
    name: str = Field(min_length=1, max_length=100)
    routing_scope: RoutingScope
    privacy_level: TicketPrivacyLevel
    state_machine: TicketStateMachine
    sla_rules: TicketSlaRules = Field(default_factory=_default_sla_rules)

    @model_validator(mode="after")
    def validate_configuration(self) -> "TicketCategoryCreate":
        from app.services.ticket_categories import validate_sla_rules, validate_state_machine

        state_machine = validate_state_machine(
            self.state_machine.model_dump(mode="python", by_alias=True)
        )
        validate_sla_rules(
            self.sla_rules.model_dump(mode="python", by_alias=True),
            state_machine,
        )
        return self


class TicketCategoryPatch(_TicketCategoryModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    routing_scope: RoutingScope | None = None
    privacy_level: TicketPrivacyLevel | None = None
    state_machine: TicketStateMachine | None = None
    sla_rules: TicketSlaRules | None = None

    @model_validator(mode="after")
    def validate_non_empty_patch(self) -> "TicketCategoryPatch":
        if not self.model_fields_set:
            raise TicketCategoryPatchEmptyError()
        return self


class TicketCategoryRead(_TicketCategoryModel):
    id: UUID
    name: str
    routing_scope: RoutingScope
    privacy_level: TicketPrivacyLevel
    state_machine: TicketStateMachine
    sla_rules: TicketSlaRules
    created_at: datetime
    updated_at: datetime
    version: int = Field(ge=1)


class TicketCategoryNotFoundError(Exception):
    def __init__(self, category_id: UUID) -> None:
        self.category_id = category_id
        super().__init__(f"ticket category {category_id} was not found")


class InvalidTicketStateMachineError(ValueError):
    pass


class InvalidTicketSlaRulesError(ValueError):
    pass


class TicketCategoryPatchEmptyError(ValueError):
    def __init__(self) -> None:
        super().__init__("ticket category patch requires at least one field")


__all__ = [
    "InvalidTicketSlaRulesError",
    "InvalidTicketStateMachineError",
    "RoutingScope",
    "TicketCategoryCreate",
    "TicketCategoryNotFoundError",
    "TicketCategoryPatch",
    "TicketCategoryPatchEmptyError",
    "TicketCategoryRead",
    "TicketPrivacyLevel",
    "TicketSlaConsequence",
    "TicketSlaRule",
    "TicketSlaRules",
    "TicketSlaThreshold",
    "TicketStateDefinition",
    "TicketStateEdge",
    "TicketStateMachine",
]
