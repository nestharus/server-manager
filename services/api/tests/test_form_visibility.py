from __future__ import annotations

from typing import Any

import pytest


def _field(
    field_id: str,
    *,
    field_type: str = "short",
    visible_when: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "id": field_id,
        "type": field_type,
        "label": field_id.replace("_", " ").title(),
        "required": False,
    }
    if field_type in {"short", "long"}:
        raw["max_length"] = 64 if field_type == "short" else 4000
    if field_type == "select":
        raw["options"] = ["yes", "no", "maybe"]
    if visible_when is not None:
        raw["visible_when"] = visible_when
    return raw


def _visibility(
    fields: list[dict[str, Any]],
    responses: dict[str, Any],
) -> dict[str, bool]:
    from pydantic import TypeAdapter

    from app.contracts.applications import ApplicationFormField
    from app.services.form_visibility import evaluate_visibility

    parsed_fields = TypeAdapter(list[ApplicationFormField]).validate_python(fields)
    return evaluate_visibility(parsed_fields, responses)


def test_evaluate_visibility_returns_true_for_field_with_no_visible_when() -> None:
    """Risk annotation: group=TG-2;
    named_risk=visibility_evaluator_deterministic_under_each_op_and_missing_or_hidden_source;
    level=unit; source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-2.
    """
    assert _visibility([_field("always")], {}) == {"always": True}


@pytest.mark.parametrize(
    ("op", "predicate_value", "source_response", "expected"),
    [
        pytest.param("eq", "yes", "yes", True, id="eq-true"),
        pytest.param("eq", "yes", "no", False, id="eq-false"),
        pytest.param("neq", "yes", "no", True, id="neq-true"),
        pytest.param("neq", "yes", "yes", False, id="neq-false"),
        pytest.param("in", ["yes", "maybe"], "yes", True, id="in-true"),
        pytest.param("in", ["yes", "maybe"], "no", False, id="in-false"),
        pytest.param("not_in", ["yes", "maybe"], "no", True, id="not-in-true"),
        pytest.param("not_in", ["yes", "maybe"], "yes", False, id="not-in-false"),
    ],
)
def test_evaluate_visibility_operator_semantics(
    op: str,
    predicate_value: Any,
    source_response: Any,
    expected: bool,
) -> None:
    """Risk annotation: group=TG-2;
    named_risk=visibility_evaluator_deterministic_under_each_op_and_missing_or_hidden_source;
    level=unit; source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-2.
    """
    fields = [
        _field("source"),
        _field(
            "dependent",
            visible_when={"field_id": "source", "op": op, "value": predicate_value},
        ),
    ]

    assert _visibility(fields, {"source": source_response}) == {
        "source": True,
        "dependent": expected,
    }


@pytest.mark.parametrize(
    ("op", "predicate_value"),
    [
        pytest.param("eq", "yes", id="eq"),
        pytest.param("neq", "yes", id="neq"),
        pytest.param("in", ["yes"], id="in"),
        pytest.param("not_in", ["yes"], id="not-in"),
    ],
)
def test_evaluate_visibility_missing_source_response_is_false_under_all_ops(
    op: str,
    predicate_value: Any,
) -> None:
    """Risk annotation: group=TG-2;
    named_risk=visibility_evaluator_deterministic_under_each_op_and_missing_or_hidden_source;
    level=unit; source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-2-F1.
    """
    fields = [
        _field("source"),
        _field(
            "dependent",
            visible_when={"field_id": "source", "op": op, "value": predicate_value},
        ),
    ]

    assert _visibility(fields, {}) == {"source": True, "dependent": False}


@pytest.mark.parametrize(
    ("op", "predicate_value", "hidden_source_response"),
    [
        pytest.param("eq", "yes", "yes", id="eq"),
        pytest.param("neq", "yes", "no", id="neq"),
        pytest.param("in", ["yes"], "yes", id="in"),
        pytest.param("not_in", ["yes"], "no", id="not-in"),
    ],
)
def test_evaluate_visibility_hidden_source_response_is_false_under_all_ops(
    op: str,
    predicate_value: Any,
    hidden_source_response: Any,
) -> None:
    """Risk annotation: group=TG-2;
    named_risk=visibility_evaluator_deterministic_under_each_op_and_missing_or_hidden_source;
    level=unit; source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-2-F1.
    """
    fields = [
        _field("gate", field_type="boolean"),
        _field(
            "source",
            visible_when={"field_id": "gate", "op": "eq", "value": True},
        ),
        _field(
            "dependent",
            visible_when={"field_id": "source", "op": op, "value": predicate_value},
        ),
    ]

    assert _visibility(fields, {"gate": False, "source": hidden_source_response}) == {
        "gate": True,
        "source": False,
        "dependent": False,
    }


def test_evaluate_visibility_chained_a_b_c_visible_when_a_visible_b_visible() -> None:
    """Risk annotation: group=TG-2;
    named_risk=visibility_evaluator_deterministic_under_each_op_and_missing_or_hidden_source;
    level=unit; source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-2.
    """
    fields = [
        _field("a", field_type="select"),
        _field("b", visible_when={"field_id": "a", "op": "eq", "value": "yes"}),
        _field("c", visible_when={"field_id": "b", "op": "eq", "value": "value"}),
    ]

    assert _visibility(fields, {"a": "yes", "b": "value"}) == {
        "a": True,
        "b": True,
        "c": True,
    }


def test_evaluate_visibility_chained_a_hides_b_propagates_to_c() -> None:
    """Risk annotation: group=TG-2;
    named_risk=visibility_evaluator_deterministic_under_each_op_and_missing_or_hidden_source;
    level=unit; source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-2-F1.
    """
    fields = [
        _field("a", field_type="select"),
        _field("b", visible_when={"field_id": "a", "op": "eq", "value": "yes"}),
        _field("c", visible_when={"field_id": "b", "op": "eq", "value": "value"}),
    ]

    assert _visibility(fields, {"a": "no", "b": "value"}) == {
        "a": True,
        "b": False,
        "c": False,
    }


def test_evaluate_visibility_preserves_authored_field_order() -> None:
    """Risk annotation: group=TG-2;
    named_risk=visibility_evaluator_deterministic_under_each_op_and_missing_or_hidden_source;
    level=unit; source=.tmp/init-136-multi-page/phase6/step6a-contract.md#TG-2.
    """
    fields = [
        _field(
            "dependent",
            visible_when={"field_id": "source", "op": "eq", "value": "yes"},
        ),
        _field("source"),
    ]

    assert _visibility(fields, {"source": "yes"}) == {
        "dependent": False,
        "source": True,
    }
