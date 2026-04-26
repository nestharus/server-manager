#!/usr/bin/env python3
"""Spawn an ephemeral child channel definition under .tmp."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from resolve_platform_channel import ChannelError, REPO_ROOT, resolve_channel, write_error


CHANNEL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TMP_ROOT = REPO_ROOT / ".tmp"
INFRA_CHANNELS = REPO_ROOT / "infra" / "channels"
INFRA_ROOTS = REPO_ROOT / "infra" / "roots"


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _validated_output_dir(raw_out: str, child_id: str) -> Path:
    out_path = Path(raw_out)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path

    resolved = out_path.resolve(strict=False)
    tmp_root = TMP_ROOT.resolve(strict=False)
    channels_root = INFRA_CHANNELS.resolve(strict=False)
    roots_root = INFRA_ROOTS.resolve(strict=False)

    if not _is_relative_to(resolved, tmp_root):
        raise ChannelError(
            "schema_invalid",
            child_id,
            "spawn output path must be under .tmp/",
        )

    if _is_relative_to(resolved, channels_root) or _is_relative_to(resolved, roots_root):
        raise ChannelError(
            "schema_invalid",
            child_id,
            "spawn output path must not be under infra/channels/ or infra/roots/",
        )

    return resolved


def _child_yaml(parent: dict[str, Any], suffix: str) -> dict[str, Any]:
    parent_id = str(parent["id"])
    child_id = f"{parent_id}-{suffix}"
    if not CHANNEL_ID_RE.fullmatch(suffix):
        raise ChannelError("schema_invalid", child_id, f"invalid suffix {suffix!r}")
    if not CHANNEL_ID_RE.fullmatch(child_id):
        raise ChannelError("schema_invalid", child_id, f"invalid child id {child_id!r}")

    return {
        "schema_version": 1,
        "id": child_id,
        "parent": parent_id,
        "exposure": parent["exposure"],
        "tenant": suffix,
        "allow_ephemeral_children": False,
        "enabled_platforms": parent["enabled_platforms"],
    }


def spawn_channel(parent_id: str, suffix: str, out: str) -> Path:
    parent = resolve_channel(parent_id)
    child_id = f"{parent_id}-{suffix}"

    if not parent.get("allow_ephemeral_children", False):
        raise ChannelError(
            "ephemeral_children_disabled",
            parent_id,
            f"channel {parent_id!r} does not allow ephemeral children",
        )

    output_dir = _validated_output_dir(out, child_id)
    payload = _child_yaml(parent, suffix)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "channel.yaml"
    output_file.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return output_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", required=True, help="parent channel id")
    parser.add_argument("--suffix", required=True, help="ephemeral child suffix")
    parser.add_argument("--out", required=True, help="output directory; must be under .tmp/")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        spawn_channel(args.parent, args.suffix, args.out)
        return 0
    except ChannelError as exc:
        write_error(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
