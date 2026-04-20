"""Base contract helpers."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from app.contracts.policies import POLICY_AGGREGATE_SCOPE_MISSING


AGGREGATE_SCOPE_MISSING = POLICY_AGGREGATE_SCOPE_MISSING

ModelT = TypeVar("ModelT", bound=BaseModel)


def validated_update(current: ModelT, patch: dict[str, Any]) -> ModelT:
    merged = current.model_dump(mode="python")
    merged.update(patch)
    validated = type(current).model_validate(merged)
    if not isinstance(validated, type(current)):
        raise TypeError(
            "validated_update changed model type; update patches must preserve shape"
        )
    return validated


__all__: list[str] = []
