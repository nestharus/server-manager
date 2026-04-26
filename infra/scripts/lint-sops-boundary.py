#!/usr/bin/env python3
"""Enforce the bootstrap-only SOPS boundary."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SOPS_SENTINEL_FILE = Path("gitops/bootstrap/sops-sentinel.enc.yaml")
INFISICAL_BOOTSTRAP_FILE = Path("gitops/bootstrap/infisical-server-bootstrap.enc.yaml")
ALLOWED_ENCRYPTED_FILES = {
    SOPS_SENTINEL_FILE,
    INFISICAL_BOOTSTRAP_FILE,
}
INFISICAL_BOOTSTRAP_STRINGDATA_KEYS = {
    "ENCRYPTION_KEY",
    "AUTH_SECRET",
    "SITE_URL",
    "DB_CONNECTION_URI",
    "REDIS_URL",
    "POSTGRES_PASSWORD",
    "POSTGRES_POSTGRES_PASSWORD",
    "REDIS_PASSWORD",
    "INFISICAL_AUTO_BOOTSTRAP_EMAIL",
    "INFISICAL_AUTO_BOOTSTRAP_PASSWORD",
}
INFISICAL_BOOTSTRAP_ALLOWED_KEY_PATHS = {
    f"stringData.{key}" for key in INFISICAL_BOOTSTRAP_STRINGDATA_KEYS
}
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

    if set(encrypted_files) != ALLOWED_ENCRYPTED_FILES:
        failures.append(
            "encrypted file set must be exactly "
            f"{', '.join(str(path) for path in sorted(ALLOWED_ENCRYPTED_FILES))}; "
            f"found {', '.join(str(path) for path in encrypted_files) or '<none>'}"
        )

    for relative_path in encrypted_files:
        if relative_path.parts[:2] != ("gitops", "bootstrap"):
            failures.append(f"encrypted file outside gitops/bootstrap: {relative_path}")

        if relative_path not in ALLOWED_ENCRYPTED_FILES:
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

        if relative_path == INFISICAL_BOOTSTRAP_FILE:
            if not isinstance(document, dict):
                failures.append(f"{relative_path}: expected YAML mapping")
                continue
            if document.get("apiVersion") != "v1":
                failures.append(f"{relative_path}: apiVersion must be v1")
            if document.get("kind") != "Secret":
                failures.append(f"{relative_path}: kind must be Secret")
            metadata = document.get("metadata")
            if not isinstance(metadata, dict):
                failures.append(f"{relative_path}: metadata must be a mapping")
            else:
                if metadata.get("name") != "infisical-server-bootstrap":
                    failures.append(f"{relative_path}: metadata.name must be infisical-server-bootstrap")
                if metadata.get("namespace") != "infisical-system":
                    failures.append(f"{relative_path}: metadata.namespace must be infisical-system")
            if document.get("type") != "Opaque":
                failures.append(f"{relative_path}: type must be Opaque")
            string_data = document.get("stringData")
            if not isinstance(string_data, dict):
                failures.append(f"{relative_path}: stringData must be a mapping")
            else:
                found_keys = set(str(key) for key in string_data)
                if found_keys != INFISICAL_BOOTSTRAP_STRINGDATA_KEYS:
                    failures.append(
                        f"{relative_path}: stringData keys must be exactly "
                        f"{', '.join(sorted(INFISICAL_BOOTSTRAP_STRINGDATA_KEYS))}; "
                        f"found {', '.join(sorted(found_keys)) or '<none>'}"
                    )

        for key_path, match in _walk_keys(document):
            if relative_path == INFISICAL_BOOTSTRAP_FILE and key_path in INFISICAL_BOOTSTRAP_ALLOWED_KEY_PATHS:
                continue
            failures.append(f"runtime-secret-shaped key in {relative_path}: {key_path} ({match})")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    print(
        "PASS: SOPS encrypted file boundary is bootstrap-only "
        f"({', '.join(str(path) for path in sorted(ALLOWED_ENCRYPTED_FILES))})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
