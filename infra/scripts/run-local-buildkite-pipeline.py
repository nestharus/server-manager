#!/usr/bin/env python3
"""Execute the local subset of the Buildkite pipeline contract."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PIPELINE = REPO_ROOT / ".buildkite" / "pipeline.yml"


class LocalPipelineError(Exception):
    """Raised when the local pipeline cannot be executed."""


@dataclass(frozen=True)
class CommandStep:
    index: int
    key: str | None
    label: str
    command: str
    env: dict[str, str]
    artifact_paths: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WaitStep:
    index: int


PipelineStep = CommandStep | WaitStep


def _string_map(value: Any, *, field: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise LocalPipelineError(f"{field} must be a mapping")

    output: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise LocalPipelineError(f"{field} keys must be strings")
        output[key] = str(item)
    return output


def _string_list(value: Any, *, field: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        raise LocalPipelineError(f"{field} must be a string or list")

    output: list[str] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str):
            raise LocalPipelineError(f"{field}[{index}] must be a string")
        output.append(item)
    return output


def load_pipeline(path: Path) -> tuple[dict[str, str], list[PipelineStep]]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LocalPipelineError(f"pipeline not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise LocalPipelineError(f"invalid pipeline YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise LocalPipelineError("pipeline must be a YAML mapping")

    top_env = _string_map(data.get("env"), field="env")
    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list):
        raise LocalPipelineError("steps must be a list")

    steps: list[PipelineStep] = []
    for index, raw_step in enumerate(raw_steps, start=1):
        if raw_step == "wait" or (isinstance(raw_step, dict) and "wait" in raw_step):
            steps.append(WaitStep(index=index))
            continue

        if not isinstance(raw_step, dict):
            raise LocalPipelineError(f"step {index} must be a mapping or wait")

        unsupported = sorted(set(raw_step) & {"block", "input", "trigger", "group"})
        if unsupported:
            raise LocalPipelineError(f"step {index} uses unsupported local step type: {unsupported[0]}")

        command = raw_step.get("command")
        if not isinstance(command, str) or not command.strip():
            raise LocalPipelineError(f"step {index} command must be a non-empty string")

        key = raw_step.get("key")
        if key is not None and not isinstance(key, str):
            raise LocalPipelineError(f"step {index} key must be a string")

        label = raw_step.get("label")
        if not isinstance(label, str) or not label.strip():
            label = key or f"step-{index}"

        steps.append(
            CommandStep(
                index=index,
                key=key,
                label=label,
                command=command,
                env=_string_map(raw_step.get("env"), field=f"steps[{index}].env"),
                artifact_paths=_string_list(
                    raw_step.get("artifact_paths"),
                    field=f"steps[{index}].artifact_paths",
                ),
            )
        )

    return top_env, steps


def select_steps(steps: list[PipelineStep], selected_keys: list[str]) -> list[CommandStep]:
    command_steps = [step for step in steps if isinstance(step, CommandStep)]
    if not selected_keys:
        return command_steps

    by_key = {step.key: step for step in command_steps if step.key is not None}
    missing = [key for key in selected_keys if key not in by_key]
    if missing:
        raise LocalPipelineError(f"unknown step key: {missing[0]}")

    return [by_key[key] for key in selected_keys]


def run_steps(
    *,
    top_env: dict[str, str],
    steps: list[CommandStep],
    dry_run: bool,
) -> int:
    for step in steps:
        print(f"--- local-buildkite step {step.index}: {step.label}")
        print(step.command)
        if dry_run:
            continue

        env = os.environ.copy()
        env.update(top_env)
        env.update(step.env)
        env["BUILDKITE"] = "true"
        env["BUILDKITE_LOCAL"] = "true"
        env.setdefault("BUILDKITE_BRANCH", _git_value("rev-parse", "--abbrev-ref", "HEAD"))
        env.setdefault("BUILDKITE_COMMIT", _git_value("rev-parse", "HEAD"))

        result = subprocess.run(
            ["bash", "-lc", step.command],
            cwd=REPO_ROOT,
            env=env,
            check=False,
        )
        if result.returncode != 0:
            return result.returncode
    return 0


def _git_value(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return "local"
    return result.stdout.strip() or "local"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline", default=str(DEFAULT_PIPELINE), help="pipeline YAML path")
    parser.add_argument("--step-key", action="append", default=[], help="run only the selected command step key")
    parser.add_argument("--dry-run", action="store_true", help="print selected commands without executing")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        top_env, steps = load_pipeline(Path(args.pipeline))
        selected = select_steps(steps, args.step_key)
        return run_steps(top_env=top_env, steps=selected, dry_run=args.dry_run)
    except LocalPipelineError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
