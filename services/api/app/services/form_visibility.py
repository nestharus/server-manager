from __future__ import annotations

from typing import Any

from app.contracts.applications import ApplicationFormField


def evaluate_visibility(
    fields: list[ApplicationFormField],
    responses: dict[str, Any],
) -> dict[str, bool]:
    visibility: dict[str, bool] = {}

    for field in fields:
        predicate = field.visible_when
        if predicate is None:
            visibility[field.id] = True
            continue

        source_id = predicate.field_id
        if not visibility.get(source_id, False) or source_id not in responses:
            visibility[field.id] = False
            continue

        source_value = responses[source_id]
        if predicate.op == "eq":
            visibility[field.id] = source_value == predicate.value
        elif predicate.op == "neq":
            visibility[field.id] = source_value != predicate.value
        elif predicate.op == "in":
            visibility[field.id] = source_value in predicate.value
        else:
            visibility[field.id] = source_value not in predicate.value

    return visibility


__all__ = ["evaluate_visibility"]
