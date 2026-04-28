import re

from infra.tests.fixtures.buildkite_pipeline import (
    buildkite_pipeline_family,
    required_cluster_runtime_validators,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "\n".join(_as_text(item) for item in value)
    if isinstance(value, dict):
        return "\n".join(_as_text(item) for item in value.values())
    return str(value)


def _step_command_text(step: dict) -> str:
    return _as_text(step.get("command", ""))


def _step_text(step: dict) -> str:
    fields = ("label", "key", "command", "trigger", "if", "branches", "name")
    return "\n".join(_as_text(step.get(field, "")) for field in fields)


def _flatten_steps(steps: object) -> list[dict]:
    if not isinstance(steps, list):
        return []

    flattened: list[dict] = []
    for step in steps:
        if isinstance(step, dict):
            flattened.append(step)
            flattened.extend(_flatten_steps(step.get("steps")))
    return flattened


def _steps_from_sources(sources: tuple[dict, ...]) -> list[dict]:
    steps: list[dict] = []
    for source in sources:
        steps.extend(_flatten_steps(source.get("steps", [])))
    return steps


def _validator_steps(steps: list[dict], validators: tuple[str, ...]) -> list[dict]:
    return [
        step
        for step in steps
        if any(validator in _step_command_text(step) for validator in validators)
    ]


def test_cluster_pipeline_or_cluster_aware_main_lane_exists(
    buildkite_pipeline_family,
    required_cluster_runtime_validators,
):
    cluster_steps = _steps_from_sources(buildkite_pipeline_family.cluster_sources)
    validator_steps = _validator_steps(cluster_steps, required_cluster_runtime_validators)

    if buildkite_pipeline_family.cluster is not None:
        assert validator_steps, "dedicated cluster pipeline must include runtime validators"
        return

    assert validator_steps, (
        "expected .buildkite/pipeline-cluster.yml or cluster-aware runtime "
        "validator steps in .buildkite/pipeline.yml"
    )


def test_required_runtime_validators_run_in_cluster_mode(
    buildkite_pipeline_family,
    required_cluster_runtime_validators,
):
    cluster_steps = _steps_from_sources(buildkite_pipeline_family.cluster_sources)

    for validator in required_cluster_runtime_validators:
        matching_steps = [
            step for step in cluster_steps if validator in _step_command_text(step)
        ]
        assert matching_steps, f"missing cluster-lane validator command for {validator}"

        for step in matching_steps:
            command = _step_command_text(step)
            assert "--cluster" in command, f"{validator} must run with --cluster"
            assert "--static-only" not in command, (
                f"{validator} must not present static-only execution as runtime proof"
            )


def test_humility_local_cluster_bringup_precedes_runtime_validators(
    buildkite_pipeline_family,
    required_cluster_runtime_validators,
):
    cluster_steps = _steps_from_sources(buildkite_pipeline_family.cluster_sources)
    validator_indexes = [
        index
        for index, step in enumerate(cluster_steps)
        if any(
            validator in _step_command_text(step)
            for validator in required_cluster_runtime_validators
        )
    ]
    assert validator_indexes, "cluster lane must include runtime validator commands"

    before_first_validator = cluster_steps[: min(validator_indexes)]
    bringup_steps = [
        step
        for step in before_first_validator
        if "humility-local" in _step_text(step).lower()
        and re.search(r"\b(k3d|cluster|kubectl)\b", _step_text(step).lower())
    ]

    assert bringup_steps, (
        "cluster lane must bring up or verify the humility-local cluster before "
        "runtime validators run"
    )


def test_pr_gated_cluster_merge_readiness_is_named(buildkite_pipeline_family):
    readiness_steps = [
        step
        for step in buildkite_pipeline_family.combined_steps
        if re.search(
            r"cluster.*merge.*read(?:y|iness)|merge.*read(?:y|iness).*cluster",
            _step_text(step),
            re.I,
        )
    ]
    assert readiness_steps, "cluster merge-readiness trigger or condition must be named"

    assert any(
        re.search(r"pull[_ -]?request|build\.pull_request|\bpr\b", _step_text(step), re.I)
        for step in readiness_steps
    ), "cluster merge-readiness lane must be PR-gated"


def test_nightly_aggregate_cluster_runtime_coverage_is_named(buildkite_pipeline_family):
    nightly_sources = buildkite_pipeline_family.nightly_sources
    nightly_text = "\n".join(
        [str(source.path) for source in nightly_sources]
        + [_step_text(step) for step in _steps_from_sources(nightly_sources)]
    )

    assert re.search(r"nightly", nightly_text, re.I), (
        "nightly aggregate trigger or pipeline must be named"
    )
    assert re.search(r"aggregate", nightly_text, re.I), (
        "nightly aggregate trigger or pipeline must identify aggregate coverage"
    )
    assert re.search(r"cluster|runtime", nightly_text, re.I), (
        "nightly aggregate coverage must identify cluster/runtime validation"
    )
