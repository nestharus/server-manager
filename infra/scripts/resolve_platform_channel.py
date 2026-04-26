#!/usr/bin/env python3
"""Resolve a platform channel source YAML into complete JSON."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


REPO_ROOT = Path(__file__).resolve().parents[2]
INFRA_DIR = REPO_ROOT / "infra"
CHANNELS_DIR = INFRA_DIR / "channels"
FIXTURES_DIR = CHANNELS_DIR / "fixtures"
SOURCE_SCHEMA_PATH = INFRA_DIR / "schemas" / "platform-channel.schema.json"
RESOLVED_SCHEMA_PATH = INFRA_DIR / "schemas" / "platform-channel-resolved.schema.json"
MAX_PARENT_DEPTH = 16


class ChannelError(Exception):
    """Structured channel-resolution failure."""

    def __init__(self, code: str, channel: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.channel = channel
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "channel": self.channel, "message": self.message}


def write_error(error: ChannelError) -> None:
    print(json.dumps(error.to_dict(), sort_keys=True), file=sys.stderr)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise ChannelError("file_not_found", str(path), f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ChannelError("schema_invalid", str(path), f"invalid JSON schema: {exc}") from exc

    if not isinstance(data, dict):
        raise ChannelError("schema_invalid", str(path), "schema document must be an object")

    Draft202012Validator.check_schema(data)
    return data


def _validator(path: Path) -> Draft202012Validator:
    return Draft202012Validator(_load_json(path))


def _source_validator() -> Draft202012Validator:
    return _validator(SOURCE_SCHEMA_PATH)


def _resolved_validator() -> Draft202012Validator:
    return _validator(RESOLVED_SCHEMA_PATH)


def _channel_path(channel_id: str) -> Path | None:
    active = CHANNELS_DIR / f"{channel_id}.yaml"
    if active.is_file():
        return active

    fixture = FIXTURES_DIR / f"{channel_id}.yaml"
    if fixture.is_file():
        return fixture

    return None


def _format_validation_error(error: ValidationError) -> str:
    location = ".".join(str(part) for part in error.absolute_path)
    if location:
        return f"{location}: {error.message}"
    return error.message


def validate_source_channel(data: dict[str, Any], channel: str) -> None:
    if data.get("schema_version") != 1:
        raise ChannelError(
            "unknown_schema_version",
            channel,
            f"unsupported schema_version {data.get('schema_version')!r}",
        )

    errors = sorted(_source_validator().iter_errors(data), key=lambda item: list(item.path))
    if errors:
        raise ChannelError("schema_invalid", channel, _format_validation_error(errors[0]))


def validate_resolved_channel(data: dict[str, Any], channel: str) -> None:
    if data.get("schema_version") != 1:
        raise ChannelError(
            "unknown_schema_version",
            channel,
            f"unsupported schema_version {data.get('schema_version')!r}",
        )

    errors = sorted(_resolved_validator().iter_errors(data), key=lambda item: list(item.path))
    if errors:
        raise ChannelError("schema_invalid", channel, _format_validation_error(errors[0]))


def load_source_channel(channel_id: str, requester: str | None = None) -> dict[str, Any]:
    path = _channel_path(channel_id)
    if path is None:
        if requester is None:
            raise ChannelError("channel_not_found", channel_id, f"channel {channel_id!r} was not found")
        raise ChannelError("missing_parent", requester, f"parent channel {channel_id!r} was not found")

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except FileNotFoundError as exc:
        raise ChannelError("file_not_found", channel_id, f"channel file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ChannelError("schema_invalid", channel_id, f"invalid YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise ChannelError("schema_invalid", channel_id, "channel file must contain a YAML object")

    validate_source_channel(data, channel_id)

    declared_id = data.get("id")
    if declared_id != channel_id:
        raise ChannelError(
            "schema_invalid",
            channel_id,
            f"channel file declares id {declared_id!r}, expected {channel_id!r}",
        )

    return data


def _deep_merge(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(parent)
    for key, child_value in child.items():
        parent_value = merged.get(key)
        if isinstance(parent_value, dict) and isinstance(child_value, dict):
            merged[key] = _deep_merge(parent_value, child_value)
        else:
            merged[key] = copy.deepcopy(child_value)
    return merged


def _assert_no_target_merge_conflict(data: dict[str, Any], channel_id: str) -> None:
    cluster = data.get("cluster")
    if not isinstance(cluster, dict):
        return

    target = cluster.get("target")
    if target == "k3d-local" and "vultr_vms" in cluster:
        raise ChannelError(
            "merge_conflict",
            channel_id,
            "cluster.target k3d-local cannot inherit vultr_vms configuration",
        )
    if target == "vultr-vms" and "k3d" in cluster:
        raise ChannelError(
            "merge_conflict",
            channel_id,
            "cluster.target vultr-vms cannot inherit k3d configuration",
        )


def _resolve_unvalidated(channel_id: str, stack: list[str]) -> dict[str, Any]:
    if channel_id in stack or len(stack) >= MAX_PARENT_DEPTH:
        raise ChannelError(
            "circular_parent",
            channel_id,
            f"circular or too-deep parent chain detected at {channel_id!r}",
        )

    data = load_source_channel(channel_id, stack[-1] if stack else None)
    parent = data.get("parent")
    if parent is None:
        return copy.deepcopy(data)

    parent_data = _resolve_unvalidated(str(parent), [*stack, channel_id])
    resolved = _deep_merge(parent_data, data)
    _assert_no_target_merge_conflict(resolved, channel_id)
    return resolved


def resolve_channel(channel_id: str) -> dict[str, Any]:
    resolved = _resolve_unvalidated(channel_id, [])
    resolved.pop("parent", None)
    _assert_no_target_merge_conflict(resolved, channel_id)
    state = resolved.get("state")
    if isinstance(state, dict) and "endpoint" not in state:
        region = state.get("region")
        if isinstance(region, str) and region:
            state["endpoint"] = f"https://{region}1.vultrobjects.com"
    object_storage = resolved.get("object_storage")
    cluster = resolved.get("cluster")
    if (
        isinstance(object_storage, dict)
        and object_storage.get("provider") == "vultr-object-storage"
        and "endpoint" not in object_storage
        and isinstance(cluster, dict)
    ):
        vultr_vms = cluster.get("vultr_vms")
        if isinstance(vultr_vms, dict):
            region = vultr_vms.get("region")
            if isinstance(region, str) and region:
                object_storage["endpoint"] = f"https://{region}1.vultrobjects.com"
    # GitOps, Infisical, and local object-storage blocks are deliberately not defaulted; all fields are operator-supplied.
    validate_resolved_channel(resolved, channel_id)
    return resolved


def write_resolved(channel: dict[str, Any], out_path: Path | None) -> None:
    rendered = json.dumps(channel, indent=2, sort_keys=True) + "\n"
    if out_path is None:
        print(rendered, end="")
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", required=True, help="channel id to resolve")
    parser.add_argument("--out", help="optional output JSON path; defaults to stdout")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        resolved = resolve_channel(args.channel)
        write_resolved(resolved, Path(args.out) if args.out else None)
        return 0
    except ChannelError as exc:
        write_error(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
