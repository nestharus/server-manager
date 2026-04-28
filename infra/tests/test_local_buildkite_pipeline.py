from __future__ import annotations

import importlib.util
import json
import shlex
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


def test_empty_step_selection_keeps_declared_local_surface() -> None:
    """INIT-109 L015/L030: default selection runs all command steps."""
    runner = load_runner()
    _, steps = runner.load_pipeline(FIXTURE_DIR / "buildkite_runner_pipeline.yml")

    selected = runner.select_steps(steps, [])

    command_keys = [
        step.key for step in selected if isinstance(step, runner.CommandStep)
    ]
    assert command_keys == ["first-command", "artifact-command"]


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


@pytest.mark.parametrize(
    ("fixture_name", "contract_line"),
    [
        ("buildkite_unsupported_block.yml", "L017"),
        ("buildkite_unsupported_trigger.yml", "L018"),
        ("buildkite_unsupported_input.yml", "L019"),
        ("buildkite_unsupported_group.yml", "L020"),
    ],
)
def test_unsupported_step_types_fail(fixture_name: str, contract_line: str) -> None:
    """INIT-109 L017-L020: local mode rejects unsupported Buildkite step types."""
    runner = load_runner()

    with pytest.raises(
        runner.LocalPipelineError,
        match=f"unsupported local step type.*{contract_line}|unsupported local step type",
    ):
        runner.load_pipeline(FIXTURE_DIR / fixture_name)


def test_run_steps_merges_env_and_preserves_process_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """INIT-109 L021-L026: process, top-level, and step env become command env."""
    runner = load_runner()
    output_path = tmp_path / "env.json"
    monkeypatch.setenv("PROCESS_ONLY", "from-process")
    code = (
        "import json, os, pathlib\n"
        f"pathlib.Path({str(output_path)!r}).write_text("
        "json.dumps({"
        "'PROCESS_ONLY': os.environ.get('PROCESS_ONLY'),"
        "'TOP_ONLY': os.environ.get('TOP_ONLY'),"
        "'SHARED_VALUE': os.environ.get('SHARED_VALUE'),"
        "'STEP_ONLY': os.environ.get('STEP_ONLY'),"
        "'BUILDKITE_LOCAL': os.environ.get('BUILDKITE_LOCAL'),"
        "'BUILDKITE': os.environ.get('BUILDKITE')"
        "}, sort_keys=True), encoding='utf-8')"
    )
    step = runner.CommandStep(
        index=1,
        key="env-contract",
        label="Env contract",
        command=f"{shlex.quote(sys.executable)} -c {shlex.quote(code)}",
        env={"SHARED_VALUE": "step", "STEP_ONLY": "present"},
    )

    result = runner.run_steps(
        top_env={"TOP_ONLY": "present", "SHARED_VALUE": "top"},
        steps=[step],
        dry_run=False,
    )

    assert result == 0
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "BUILDKITE": "true",
        "BUILDKITE_LOCAL": "true",
        "PROCESS_ONLY": "from-process",
        "SHARED_VALUE": "step",
        "STEP_ONLY": "present",
        "TOP_ONLY": "present",
    }


def test_run_steps_stops_after_first_command_failure(tmp_path: Path) -> None:
    """INIT-109 L027: a failed command stops later local pipeline commands."""
    runner = load_runner()
    sentinel = tmp_path / "should-not-exist.txt"
    second_code = (
        "from pathlib import Path; "
        f"Path({str(sentinel)!r}).write_text('ran', encoding='utf-8')"
    )
    second_command = (
        f"{shlex.quote(sys.executable)} -c {shlex.quote(second_code)}"
    )
    steps = [
        runner.CommandStep(index=1, key="fail", label="Fail", command="exit 7", env={}),
        runner.CommandStep(
            index=2,
            key="after-fail",
            label="After fail",
            command=second_command,
            env={},
        ),
    ]

    result = runner.run_steps(top_env={}, steps=steps, dry_run=False)

    assert result == 7
    assert not sentinel.exists()


def test_dry_run_executes_no_commands(capsys: pytest.CaptureFixture[str]) -> None:
    """INIT-109 proposal Slice 3: dry-run prints commands without running them."""
    runner = load_runner()
    step = runner.CommandStep(index=1, key="x", label="X", command="exit 99", env={})

    result = runner.run_steps(top_env={"A": "B"}, steps=[step], dry_run=True)

    assert result == 0
    assert "exit 99" in capsys.readouterr().out
