#!/usr/bin/env python3
"""Validate active and fixture platform channels."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

import resolve_platform_channel as resolver
from resolve_platform_channel import ChannelError, validate_source_channel, write_error


FORBIDDEN_CHANNEL_FILES = {"customer.yaml", "internal.yaml", "e2e.yaml"}


def _load_yaml(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except FileNotFoundError as exc:
        raise ChannelError("file_not_found", path.stem, f"channel file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ChannelError("schema_invalid", path.stem, f"invalid YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise ChannelError("schema_invalid", path.stem, "channel file must contain a YAML object")
    return data


def _active_channel_paths(registry: Path) -> list[Path]:
    return sorted(path for path in registry.glob("*.yaml") if path.is_file())


def _fixture_channel_paths(registry: Path) -> list[Path]:
    fixtures = registry / "fixtures"
    if not fixtures.is_dir():
        return []
    return sorted(path for path in fixtures.glob("*.yaml") if path.is_file())


def _assert_no_forbidden_files(registry: Path) -> None:
    for path in registry.glob("*.yaml"):
        if path.name in FORBIDDEN_CHANNEL_FILES:
            raise ChannelError(
                "schema_invalid",
                path.stem,
                f"forbidden active channel file exists at {path}",
            )


def _validate_source_files(paths: list[Path]) -> None:
    for path in paths:
        data = _load_yaml(path)
        channel_id = str(data.get("id", path.stem))
        validate_source_channel(data, channel_id)
        if channel_id != path.stem:
            raise ChannelError(
                "schema_invalid",
                path.stem,
                f"channel file declares id {channel_id!r}, expected {path.stem!r}",
            )


def _assert_active_state_key(path: Path, resolved: dict) -> None:
    channel_id = path.stem
    expected_key = f"channels/{channel_id}/terraform.tfstate"
    actual_key = resolved.get("state", {}).get("key")
    if actual_key != expected_key:
        raise ChannelError(
            "schema_invalid",
            channel_id,
            f"state.key must be {expected_key!r}, got {actual_key!r}",
        )


def _assert_active_resolves(path: Path) -> None:
    channel_id = path.stem
    resolved = resolver.resolve_channel(channel_id)
    resolver.validate_resolved_channel(resolved, channel_id)
    _assert_active_state_key(path, resolved)


def validate_registry(registry: Path) -> None:
    if not registry.is_dir():
        raise ChannelError("channel_not_found", str(registry), "channel registry directory is missing")

    original_channels_dir = resolver.CHANNELS_DIR
    original_fixtures_dir = resolver.FIXTURES_DIR
    try:
        resolver.CHANNELS_DIR = registry
        resolver.FIXTURES_DIR = registry / "fixtures"

        _assert_no_forbidden_files(registry)
        active_paths = _active_channel_paths(registry)
        fixture_paths = _fixture_channel_paths(registry)
        _validate_source_files([*active_paths, *fixture_paths])

        for path in active_paths:
            _assert_active_resolves(path)
    finally:
        resolver.CHANNELS_DIR = original_channels_dir
        resolver.FIXTURES_DIR = original_fixtures_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default=str(resolver.CHANNELS_DIR), help="channel registry directory")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        validate_registry(Path(args.registry))
        return 0
    except ChannelError as exc:
        write_error(exc)
        return 1
    except json.JSONDecodeError as exc:
        error = ChannelError("schema_invalid", "registry", f"invalid JSON schema: {exc}")
        write_error(error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
