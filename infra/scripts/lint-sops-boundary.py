#!/usr/bin/env python3
"""Enforce the INIT-102 bootstrap-only SOPS boundary."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_FILE = Path("gitops/bootstrap/sops-sentinel.enc.yaml")
RUNTIME_SECRET_PATTERNS = (
    re.compile(r"^infisical", re.IGNORECASE),
    re.compile(r"discord.*token", re.IGNORECASE),
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"secret_access_key$", re.IGNORECASE),
    re.compile(r"api_key$", re.IGNORECASE),
)


def _encrypted_files() -> list[Path]:
    gitops = REPO_ROOT / "gitops"
    if not gitops.is_dir():
        return []
    return sorted(path.relative_to(REPO_ROOT) for path in gitops.glob("**/*.enc.yaml") if path.is_file())


def _runtime_secret_match(value: str) -> str | None:
    normalized = value.replace("-", "_")
    for pattern in RUNTIME_SECRET_PATTERNS:
        if pattern.search(normalized):
            return pattern.pattern
    return None


def _walk_keys(value: Any, path: tuple[str, ...] = ()) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            match = _runtime_secret_match(key_text)
            current_path = (*path, key_text)
            if match:
                matches.append((".".join(current_path), match))
            matches.extend(_walk_keys(child, current_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            matches.extend(_walk_keys(child, (*path, str(index))))
    return matches


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML: {exc}") from exc


def main() -> int:
    failures: list[str] = []
    encrypted_files = _encrypted_files()

    if encrypted_files != [ALLOWED_FILE]:
        failures.append(
            "encrypted file set must be exactly "
            f"{ALLOWED_FILE}; found {', '.join(str(path) for path in encrypted_files) or '<none>'}"
        )

    for relative_path in encrypted_files:
        if relative_path.parts[:2] != ("gitops", "bootstrap"):
            failures.append(f"encrypted file outside gitops/bootstrap: {relative_path}")

        for part in relative_path.parts:
            match = _runtime_secret_match(part)
            if match:
                failures.append(f"runtime-secret-shaped path component in {relative_path}: {part} ({match})")

        absolute_path = REPO_ROOT / relative_path
        try:
            document = _load_yaml(absolute_path)
        except ValueError as exc:
            failures.append(f"{relative_path}: {exc}")
            continue

        for key_path, match in _walk_keys(document):
            failures.append(f"runtime-secret-shaped key in {relative_path}: {key_path} ({match})")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    print(f"PASS: SOPS encrypted file boundary is bootstrap-only ({ALLOWED_FILE})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
