from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = REPO_ROOT / "infra" / "scripts" / "run-local-buildkite-pipeline.py"
FIXTURE_DIR = REPO_ROOT / "infra" / "tests" / "fixtures" / "contracts"


def load_runner():
    spec = importlib.util.spec_from_file_location("local_buildkite_runner", RUNNER_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_fixture_pipeline_accepts_command_wait_and_artifact_steps() -> None:
    """RISK-AUDIT-A3 / INIT-109: runner behavior, not full pipeline key order."""
    runner = load_runner()

    top_env, steps = runner.load_pipeline(FIXTURE_DIR / "buildkite_runner_pipeline.yml")

    command_steps = [step for step in steps if isinstance(step, runner.CommandStep)]
    assert top_env["CHANNEL_ID"] == "local"
    assert [type(step).__name__ for step in steps] == [
        "CommandStep",
        "WaitStep",
        "CommandStep",
    ]
    assert [step.key for step in command_steps] == ["first-command", "artifact-command"]
    assert getattr(command_steps[1], "artifact_paths") == [
        ".tmp/buildkite-local/artifact-command.txt"
    ]


def test_select_steps_preserves_requested_order() -> None:
    """INIT-109 proposal Slice 3: repeated --step-key selects requested order."""
    runner = load_runner()
    _, steps = runner.load_pipeline(FIXTURE_DIR / "buildkite_runner_pipeline.yml")

    selected = runner.select_steps(steps, ["artifact-command", "first-command"])

    assert [step.key for step in selected] == ["artifact-command", "first-command"]


def test_unknown_step_key_fails() -> None:
    """INIT-109 proposal Slice 3: unknown local step keys fail fast."""
    runner = load_runner()
    _, steps = runner.load_pipeline(FIXTURE_DIR / "buildkite_runner_pipeline.yml")

    with pytest.raises(runner.LocalPipelineError, match="unknown step key"):
        runner.select_steps(steps, ["missing"])


def test_unsupported_block_step_fails() -> None:
    """INIT-109 contract lines L017-L020: local mode rejects unsupported steps."""
    runner = load_runner()

    with pytest.raises(runner.LocalPipelineError, match="unsupported local step type"):
        runner.load_pipeline(FIXTURE_DIR / "buildkite_unsupported_block.yml")


def test_dry_run_executes_no_commands(capsys: pytest.CaptureFixture[str]) -> None:
    """INIT-109 proposal Slice 3: dry-run prints commands without running them."""
    runner = load_runner()
    step = runner.CommandStep(index=1, key="x", label="X", command="exit 99", env={})

    result = runner.run_steps(top_env={"A": "B"}, steps=[step], dry_run=True)

    assert result == 0
    assert "exit 99" in capsys.readouterr().out
