from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = REPO_ROOT / "infra" / "scripts" / "run-local-buildkite-pipeline.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("local_buildkite_runner", RUNNER_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_pipeline_accepts_command_and_wait_steps() -> None:
    runner = load_runner()

    top_env, steps = runner.load_pipeline(REPO_ROOT / ".buildkite" / "pipeline.yml")

    assert top_env["CHANNEL_ID"] == "local"
    assert [type(step).__name__ for step in steps].count("WaitStep") == 1
    assert [step.key for step in steps if isinstance(step, runner.CommandStep)] == [
        "init-109-smoke",
        "unit-tests",
        "init-111-data-plane-static",
        "init-113-application-workloads-static",
        "init-114-auth-stack-static",
        "init-115-access-policy-static",
        "registry-build-push",
        "init-113-build-images",
    ]


def test_select_steps_preserves_requested_order() -> None:
    runner = load_runner()
    _, steps = runner.load_pipeline(REPO_ROOT / ".buildkite" / "pipeline.yml")

    selected = runner.select_steps(steps, ["registry-build-push", "init-109-smoke"])

    assert [step.key for step in selected] == ["registry-build-push", "init-109-smoke"]


def test_unknown_step_key_fails() -> None:
    runner = load_runner()
    _, steps = runner.load_pipeline(REPO_ROOT / ".buildkite" / "pipeline.yml")

    with pytest.raises(runner.LocalPipelineError, match="unknown step key"):
        runner.select_steps(steps, ["missing"])


def test_unsupported_step_type_fails(tmp_path: Path) -> None:
    runner = load_runner()
    pipeline = tmp_path / "pipeline.yml"
    pipeline.write_text(
        """
steps:
  - block: "ship it"
""",
        encoding="utf-8",
    )

    with pytest.raises(runner.LocalPipelineError, match="unsupported local step type"):
        runner.load_pipeline(pipeline)


def test_dry_run_executes_no_commands(capsys: pytest.CaptureFixture[str]) -> None:
    runner = load_runner()
    top_env = {"A": "B"}
    step = runner.CommandStep(index=1, key="x", label="X", command="exit 99", env={})

    result = runner.run_steps(top_env=top_env, steps=[step], dry_run=True)

    assert result == 0
    assert "exit 99" in capsys.readouterr().out
