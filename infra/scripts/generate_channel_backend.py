#!/usr/bin/env python3
"""Generate backend.tfbackend from resolved platform channel JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from resolve_platform_channel import ChannelError, write_error


S3_BACKEND_KEYS = ("bucket", "key", "region", "endpoint")


def _load_resolved(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise ChannelError("file_not_found", "resolved", f"resolved channel file not found: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError("resolved channel JSON must contain an object")
    return data


def _required_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _state_value(state: dict[str, Any], key: str) -> str:
    value = state.get(key)
    if key == "endpoint" and value is None:
        region = _state_value(state, "region")
        value = f"https://{region}1.vultrobjects.com"
    if not isinstance(value, str) or not value:
        raise ValueError(f"state.{key} must be a non-empty string")
    return value


def _backend_type(resolved: dict[str, Any]) -> str:
    state = _required_mapping(resolved.get("state"), "state")
    backend = state.get("backend")
    if backend is not None:
        if backend not in {"local", "s3-compatible"}:
            raise ValueError("state.backend must be local or s3-compatible when present")
        return str(backend)

    if resolved.get("id") == "local":
        return "local"
    return "s3-compatible"


def render_backend(resolved: dict[str, Any]) -> str:
    backend = _backend_type(resolved)
    if backend == "local":
        return "# local backend: no backend-config arguments are required\n"

    state = _required_mapping(resolved.get("state"), "state")
    lines = [f'{key} = "{_state_value(state, key)}"' for key in S3_BACKEND_KEYS]
    lines.append("skip_credentials_validation = true")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolved", required=True, help="path to resolved channel JSON")
    parser.add_argument("--out", required=True, help="output backend config path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        resolved = _load_resolved(Path(args.resolved))
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_backend(resolved), encoding="utf-8")
        return 0
    except ChannelError as exc:
        write_error(exc)
        return 1
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        write_error(ChannelError("schema_invalid", "resolved", str(exc)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
