import re
from collections.abc import Iterable
from typing import Any

from infra.tests.fixtures.buildkite_pipeline import buildkite_pipeline  # noqa: F401


def _iter_step_dicts(pipeline: dict[str, Any]) -> Iterable[dict[str, Any]]:
    steps = pipeline.get("steps", [])
    if isinstance(steps, dict):
        steps = [steps]

    for step in steps:
        if not isinstance(step, dict):
            continue
        yield step
        nested_steps = step.get("steps")
        if isinstance(nested_steps, list):
            yield from _iter_step_dicts({"steps": nested_steps})


def _lines(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return value.splitlines()
    if isinstance(value, list):
        lines: list[str] = []
        for item in value:
            lines.extend(_lines(item))
        return lines
    return [str(value)]


def _command_text(step: dict[str, Any]) -> str:
    return "\n".join(_lines(step.get("command")) + _lines(step.get("commands")))


def _step_text(step: dict[str, Any]) -> str:
    fields = [
        step.get("label"),
        step.get("name"),
        step.get("key"),
        step.get("working_directory"),
        _command_text(step),
    ]
    return "\n".join(str(field) for field in fields if field is not None).lower()


def _has_working_dir_or_path(step: dict[str, Any], service_path: str) -> bool:
    text = _step_text(step)
    working_directory = str(step.get("working_directory", "")).strip().rstrip("/")
    return (
        working_directory == service_path
        or service_path in text
        or f"cd {service_path}" in text
        or f"--directory {service_path}" in text
    )


def _runs_pytest_for_service(step: dict[str, Any], service_path: str, tests_path: str) -> bool:
    command = _command_text(step).lower()
    if "pytest" not in command:
        return False
    return tests_path in command or _has_working_dir_or_path(step, service_path)


def _installs_python_dependencies(step: dict[str, Any]) -> bool:
    command = _command_text(step).lower()
    install_commands = (
        "uv sync",
        "pip install",
        "python -m pip install",
        "poetry install",
        "pdm install",
        "pipenv install",
    )
    return any(install_command in command for install_command in install_commands)


def _find_api_test_step(pipeline: dict[str, Any]) -> dict[str, Any] | None:
    for step in _iter_step_dicts(pipeline):
        if _runs_pytest_for_service(step, "services/api", "services/api/tests"):
            return step
    return None


def _find_discord_test_step(pipeline: dict[str, Any]) -> dict[str, Any] | None:
    for step in _iter_step_dicts(pipeline):
        if _runs_pytest_for_service(step, "services/discord", "services/discord/tests"):
            return step
    return None


def _first_index(command: str, patterns: tuple[str, ...]) -> int | None:
    indexes = [command.find(pattern) for pattern in patterns if pattern in command]
    return min(indexes) if indexes else None


def _has_non_green_blocked_reason(step: dict[str, Any]) -> bool:
    text = _step_text(step)
    if "blocked" not in text:
        return False
    if "blocked:" not in text and "reason" not in text:
        return False
    return bool(re.search(r"\bexit\s+[1-9]\d*\b", text) or "\nfalse\n" in f"\n{text}\n")


def _has_docker_preflight_before_tests(step: dict[str, Any]) -> bool:
    command = _command_text(step).lower()
    docker_check = _first_index(
        command,
        (
            "command -v docker",
            "docker info",
            "docker version",
        ),
    )
    test_start = _first_index(command, ("pytest", "testcontainers", "services/api/tests"))
    return (
        docker_check is not None
        and test_start is not None
        and docker_check < test_start
        and _has_non_green_blocked_reason(step)
    )


def _runs_web_tests(step: dict[str, Any]) -> bool:
    text = _step_text(step)
    command = _command_text(step).lower()
    if "services/web" not in text:
        return False
    test_commands = (
        "npm test",
        "npm run test",
        "pnpm test",
        "pnpm run test",
        "yarn test",
        "bun test",
        "vitest",
        "playwright test",
    )
    return any(test_command in command for test_command in test_commands)


def _records_web_blocked(step: dict[str, Any]) -> bool:
    return "services/web" in _step_text(step) and _has_non_green_blocked_reason(step)


def test_pipeline_runs_api_tests(buildkite_pipeline: dict[str, Any]) -> None:
    """Risk: service-tests-not-running-in-ci; level: unit; source: Step 6a contract + coverage audit."""
    api_step = _find_api_test_step(buildkite_pipeline)

    assert api_step is not None, "expected a Buildkite step that runs services/api/tests/"
    assert _installs_python_dependencies(api_step), (
        "expected the API test step to install service dependencies before pytest"
    )
    assert _has_docker_preflight_before_tests(api_step), (
        "expected the API test step to check Docker before running testcontainers-backed tests"
    )


def test_pipeline_runs_discord_tests(buildkite_pipeline: dict[str, Any]) -> None:
    """Risk: service-tests-not-running-in-ci; level: unit; source: Step 6a contract + coverage audit."""
    discord_step = _find_discord_test_step(buildkite_pipeline)

    assert discord_step is not None, "expected a Buildkite step that runs services/discord/tests/"
    assert _installs_python_dependencies(discord_step), (
        "expected the Discord test step to install service dependencies before pytest"
    )


def test_pipeline_handles_web_tests(buildkite_pipeline: dict[str, Any]) -> None:
    """Risk: web-tests-silently-skipped; level: unit; source: Step 6a contract + coverage audit."""
    web_steps = [
        step
        for step in _iter_step_dicts(buildkite_pipeline)
        if _runs_web_tests(step) or _records_web_blocked(step)
    ]

    assert web_steps, (
        "expected a Buildkite step that either runs services/web tests or records BLOCKED with a reason"
    )


def test_pipeline_api_step_has_docker_preflight(buildkite_pipeline: dict[str, Any]) -> None:
    """Risk: docker-preflight-missing; level: unit; source: Step 6a contract + coverage audit."""
    api_step = _find_api_test_step(buildkite_pipeline)

    assert api_step is not None, "expected an API test step before checking Docker pre-flight behavior"
    assert _has_docker_preflight_before_tests(api_step), (
        "expected Docker availability to be checked before pytest can initialize testcontainers"
    )

