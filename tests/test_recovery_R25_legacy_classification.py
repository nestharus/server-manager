from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION_FIXTURE = (
    ROOT / "infra/tests/fixtures/recovery-R25/legacy_test_classification.json"
)
LEGACY_TEST_DIRS = (
    "tests",
    "services/api/tests",
    "services/discord/tests",
)
ALLOWED_DISPOSITIONS = {
    "KEEP_AS_IS",
    "MODERNIZE",
    "MIGRATE",
    "DELETE_AND_REWRITE",
}


def _load_fixture() -> dict[str, Any]:
    with CLASSIFICATION_FIXTURE.open(encoding="utf-8") as handle:
        return json.load(handle)


def _current_legacy_test_paths(fixture: dict[str, Any]) -> set[str]:
    non_legacy_slice_tests = set(fixture.get("non_legacy_slice_tests", []))
    paths: set[str] = set()
    for directory in LEGACY_TEST_DIRS:
        for path in (ROOT / directory).glob("test*.py"):
            relative_path = path.relative_to(ROOT).as_posix()
            if relative_path not in non_legacy_slice_tests:
                paths.add(relative_path)
    return paths


def _entries_by_path() -> dict[str, dict[str, Any]]:
    entries = _load_fixture()["entries"]
    paths = [entry["path"] for entry in entries]
    duplicates = sorted(path for path, count in Counter(paths).items() if count > 1)
    assert duplicates == [], f"duplicate SLICE-R.25 classifications: {duplicates}"
    return {entry["path"]: entry for entry in entries}


def _ci_lane_for(entry: dict[str, Any], fixture: dict[str, Any]) -> str:
    if entry.get("ci_lane"):
        return entry["ci_lane"]
    for prefix, lane in fixture["ci_lanes"].items():
        if entry["path"].startswith(prefix):
            return lane
    return ""


def test_every_current_legacy_test_file_has_exactly_one_classification() -> None:
    fixture = _load_fixture()
    entries_by_path = _entries_by_path()
    classified = set(entries_by_path)
    current = _current_legacy_test_paths(fixture)
    stale_without_completion_evidence: list[str] = []

    for path in sorted(classified - current):
        entry = entries_by_path[path]
        disposition = entry["disposition"]
        if disposition not in {"MIGRATE", "DELETE_AND_REWRITE"}:
            stale_without_completion_evidence.append(
                f"{path}: stale {disposition} classification"
            )
        elif not entry.get("replacement_paths") and not entry.get("residual_risk"):
            stale_without_completion_evidence.append(
                f"{path}: stale {disposition} classification lacks "
                "replacement_paths or residual_risk"
            )

    assert current <= classified, (
        "SLICE-R.25 requires every current legacy test file under tests/, "
        "services/api/tests/, and services/discord/tests/ to have exactly one "
        "classification.\n"
        f"Missing classifications: {sorted(current - classified)}"
    )
    assert stale_without_completion_evidence == []


def test_classifications_name_contract_fixture_source_and_ci_lane() -> None:
    fixture = _load_fixture()
    missing: list[str] = []

    for entry in fixture["entries"]:
        path = entry["path"]
        if entry.get("disposition") not in ALLOWED_DISPOSITIONS:
            missing.append(f"{path}: invalid disposition {entry.get('disposition')!r}")
        if not entry.get("contract_source"):
            missing.append(f"{path}: missing contract_source")
        if not entry.get("fixture_source"):
            missing.append(f"{path}: missing fixture_source")
        if not _ci_lane_for(entry, fixture):
            missing.append(f"{path}: missing ci_lane")

    assert missing == []


def test_disposition_actions_are_complete_before_slice_can_go_green() -> None:
    errors: list[str] = []

    for entry in _load_fixture()["entries"]:
        source_path = ROOT / entry["path"]
        disposition = entry["disposition"]
        replacement_paths = entry.get("replacement_paths", [])
        residual_risk = entry.get("residual_risk")
        modernization_evidence = entry.get("modernization_evidence", [])

        if disposition == "KEEP_AS_IS":
            if not source_path.exists():
                errors.append(f"{entry['path']}: KEEP_AS_IS source is missing")
        elif disposition == "MODERNIZE":
            if not source_path.exists():
                errors.append(f"{entry['path']}: MODERNIZE source is missing")
            if not modernization_evidence:
                errors.append(
                    f"{entry['path']}: MODERNIZE requires modernization_evidence"
                )
        elif disposition == "MIGRATE":
            if source_path.exists():
                errors.append(
                    f"{entry['path']}: MIGRATE source still exists in legacy location"
                )
            if not replacement_paths:
                errors.append(f"{entry['path']}: MIGRATE requires replacement_paths")
            for replacement_path in replacement_paths:
                if not (ROOT / replacement_path).exists():
                    errors.append(
                        f"{entry['path']}: replacement {replacement_path} is missing"
                    )
        elif disposition == "DELETE_AND_REWRITE":
            if source_path.exists():
                errors.append(
                    f"{entry['path']}: DELETE_AND_REWRITE source still exists"
                )
            if not replacement_paths and not residual_risk:
                errors.append(
                    f"{entry['path']}: DELETE_AND_REWRITE requires "
                    "replacement_paths or residual_risk"
                )
            for replacement_path in replacement_paths:
                if not (ROOT / replacement_path).exists():
                    errors.append(
                        f"{entry['path']}: replacement {replacement_path} is missing"
                    )

    assert errors == []
