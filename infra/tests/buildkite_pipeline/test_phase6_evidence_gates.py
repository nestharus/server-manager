import re
from typing import Any

from infra.tests.fixtures.buildkite_phase6_evidence import (
    Phase6EvidenceGateContract,
    phase6_evidence_gate_contract,  # noqa: F401
    phase6_sample_report_paths,  # noqa: F401
)
from infra.tests.fixtures.buildkite_pipeline import buildkite_pipeline_family  # noqa: F401


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "\n".join(_as_text(item) for item in value)
    if isinstance(value, dict):
        return "\n".join(_as_text(item) for item in value.values())
    return str(value)


def _flatten_steps(steps: object) -> list[dict[str, Any]]:
    if not isinstance(steps, list):
        return []

    flattened: list[dict[str, Any]] = []
    for step in steps:
        if isinstance(step, dict):
            flattened.append(step)
            flattened.extend(_flatten_steps(step.get("steps")))
    return flattened


def _pipeline_steps(buildkite_pipeline_family: Any) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for pipeline in buildkite_pipeline_family.pipelines:
        steps.extend(_flatten_steps(pipeline.get("steps", [])))
    return steps


def _command_text(step: dict[str, Any]) -> str:
    return "\n".join(
        [
            _as_text(step.get("command")),
            _as_text(step.get("commands")),
        ]
    )


def _step_text(step: dict[str, Any]) -> str:
    fields = (
        "label",
        "name",
        "key",
        "command",
        "commands",
        "artifact_paths",
        "plugins",
    )
    return "\n".join(_as_text(step.get(field)) for field in fields)


def _all_pipeline_text(buildkite_pipeline_family: Any) -> str:
    return "\n".join(_step_text(step) for step in _pipeline_steps(buildkite_pipeline_family))


def _gate_steps_for(
    buildkite_pipeline_family: Any,
    *needles: str,
) -> list[dict[str, Any]]:
    return [
        step
        for step in _pipeline_steps(buildkite_pipeline_family)
        if all(needle in _step_text(step) for needle in needles)
    ]


def _uses_verdict_grep(command: str) -> bool:
    return bool(re.search(r"\b(grep|rg)\b", command)) and "Verdict" in command


def _has_explicit_nonzero_failure(command: str) -> bool:
    return bool(
        re.search(r"\b(exit|return)\s+[1-9]\d*\b", command)
        or re.search(
            r"(^|[;\n])\s*false\s*($|[;\n])",
            command,
        )
    )


def test_phase6_sample_report_fixture_matches_required_artifact_paths(
    phase6_sample_report_paths,
):
    assert {path.name for path in phase6_sample_report_paths} == {
        "RED_PHASE.md",
        "GREEN_PHASE.md",
        "step6b-output-index.md",
        "step6c-consumption.md",
        "process-tree-audit.md",
    }


def test_phase6_evidence_artifacts_are_collected_from_predictable_scratch_paths(
    buildkite_pipeline_family,
    phase6_evidence_gate_contract: Phase6EvidenceGateContract,
):
    pipeline_text = _all_pipeline_text(buildkite_pipeline_family)

    for artifact in phase6_evidence_gate_contract.required_artifact_paths:
        assert artifact.path in pipeline_text, (
            f"Buildkite must collect {artifact.name} from the predictable "
            f"scratch path {artifact.path}"
        )


def test_red_and_green_phase_reports_have_blocking_verdict_grep_steps(
    buildkite_pipeline_family,
    phase6_evidence_gate_contract: Phase6EvidenceGateContract,
):
    for rule in phase6_evidence_gate_contract.verdict_rules:
        gate_steps = _gate_steps_for(
            buildkite_pipeline_family,
            rule.report_name,
            rule.accepted_verdict,
        )

        assert gate_steps, (
            f"expected a Buildkite gate step for {rule.name} that reads "
            f"{rule.report_name} and accepts only {rule.accepted_verdict}"
        )

        assert any(_uses_verdict_grep(_command_text(step)) for step in gate_steps), (
            f"{rule.name} must enforce the report with verdict-grep semantics"
        )
        assert any(_has_explicit_nonzero_failure(_command_text(step)) for step in gate_steps), (
            f"{rule.name} must exit non-zero when the verdict is missing or non-confirming"
        )
        assert not any("|| true" in _command_text(step) for step in gate_steps), (
            f"{rule.name} must not mask verdict-grep failures"
        )


def test_phase6_gate_fails_missing_artifacts_blocked_collection_and_process_blocks(
    buildkite_pipeline_family,
    phase6_evidence_gate_contract: Phase6EvidenceGateContract,
):
    candidate_steps = [
        step
        for step in _pipeline_steps(buildkite_pipeline_family)
        if "RED_PHASE.md" in _step_text(step) and "GREEN_PHASE.md" in _step_text(step)
    ]

    assert candidate_steps, "expected a Buildkite Phase 6 evidence gate step"

    gate_text = "\n".join(_command_text(step) for step in candidate_steps)
    for failure_input in phase6_evidence_gate_contract.required_failure_inputs:
        assert failure_input in gate_text, (
            f"Phase 6 gate must fail when {failure_input} is missing or blocking"
        )

    assert any(term in gate_text for term in phase6_evidence_gate_contract.process_blocking_terms), (
        "Phase 6 gate must inspect process-tree blocking verdicts"
    )
    assert _has_explicit_nonzero_failure(gate_text), (
        "Phase 6 gate must have an explicit non-zero failure path"
    )


def test_artifact_upload_is_diagnostic_not_the_evidence_gate(
    buildkite_pipeline_family,
):
    phase6_steps = _gate_steps_for(buildkite_pipeline_family, "RED_PHASE.md", "GREEN_PHASE.md")

    assert phase6_steps, "expected Phase 6 Buildkite steps for evidence reports"
    assert any(_uses_verdict_grep(_command_text(step)) for step in phase6_steps), (
        "Phase 6 evidence must be enforced by a command gate, not only artifact upload"
    )
    assert not all("artifact_paths" in _step_text(step) and not _command_text(step) for step in phase6_steps), (
        "Phase 6 artifact collection is diagnostic and cannot be the only gate"
    )
