#!/usr/bin/env python3
"""Generate a channel backend config from resolved channel JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from resolve_platform_channel import ChannelError, write_error


BACKEND_KEYS = ("bucket", "key", "region")


def _load_resolved(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("resolved channel JSON must contain an object")
    return data


def _state_value(resolved: dict[str, Any], key: str) -> str:
    state = resolved.get("state")
    if not isinstance(state, dict):
        raise ValueError("resolved channel JSON must contain state object")
    value = state.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"state.{key} must be a non-empty string")
    return value


def render_backend(resolved: dict[str, Any]) -> str:
    lines = [f'{key} = "{_state_value(resolved, key)}"' for key in BACKEND_KEYS]
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
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        write_error(ChannelError("schema_invalid", "resolved", str(exc)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
