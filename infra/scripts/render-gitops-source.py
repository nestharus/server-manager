#!/usr/bin/env python3
"""Render per-channel Flux GitOps source manifests into a temp snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

import resolve_platform_channel as resolver
from resolve_platform_channel import ChannelError, write_error


REPO_ROOT = Path(__file__).resolve().parents[2]
GITOPS_ROOT = REPO_ROOT / "gitops"
MARKER_NAME = "gitops-snapshot-marker.yaml"
MARKER_NAMESPACE = "humility-gitops-sentinel"


def _load_resolved(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise ChannelError("file_not_found", "resolved", f"resolved channel file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ChannelError("schema_invalid", "resolved", f"invalid resolved channel JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ChannelError("schema_invalid", "resolved", "resolved channel JSON must contain an object")
    channel_id = _required_string(data.get("id"), "id")
    resolver.validate_resolved_channel(data, channel_id)
    return data


def _required_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _required_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _required_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _git_ref(git_ref: str) -> dict[str, str]:
    if git_ref.startswith("refs/heads/"):
        return {"branch": git_ref.removeprefix("refs/heads/")}
    if git_ref.startswith("refs/tags/"):
        return {"tag": git_ref.removeprefix("refs/tags/")}
    return {"branch": git_ref}


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(payload, sort_keys=False)
    path.write_text(rendered, encoding="utf-8")


def _copy_gitops_tree(out: Path) -> Path:
    snapshot_gitops = out / "gitops"
    if GITOPS_ROOT.is_dir():
        shutil.copytree(GITOPS_ROOT, snapshot_gitops, dirs_exist_ok=True)
    else:
        snapshot_gitops.mkdir(parents=True)
    return snapshot_gitops


def _source_path(out: Path, gitops: dict[str, Any]) -> Path:
    relative_path = _required_string(gitops.get("path"), "gitops.path")
    if not relative_path.startswith("./"):
        raise ValueError("gitops.path must start with ./")
    return out / relative_path[2:]


def _tree_digest(root: Path, ignored_relative_paths: set[str] | None = None) -> str:
    ignored_relative_paths = ignored_relative_paths or set()
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in ignored_relative_paths:
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:12]


def _render_source_manifests(out: Path, channel_id: str, gitops: dict[str, Any]) -> None:
    source_name = _required_string(gitops.get("kustomization_name"), "gitops.kustomization_name")
    namespace = _required_string(gitops.get("kustomization_namespace"), "gitops.kustomization_namespace")
    interval = _required_string(gitops.get("interval"), "gitops.interval")
    retry_interval = _required_string(gitops.get("retry_interval"), "gitops.retry_interval")
    source_dir = out / "gitops" / "sources" / channel_id

    _write_yaml(
        source_dir / "gitrepository.yaml",
        {
            "apiVersion": "source.toolkit.fluxcd.io/v1",
            "kind": "GitRepository",
            "metadata": {
                "name": source_name,
                "namespace": namespace,
            },
            "spec": {
                "interval": interval,
                "retryInterval": retry_interval,
                "url": _required_string(gitops.get("git_url"), "gitops.git_url"),
                "ref": _git_ref(_required_string(gitops.get("git_ref"), "gitops.git_ref")),
            },
        },
    )
    _write_yaml(
        source_dir / "kustomization.yaml",
        {
            "apiVersion": "kustomize.toolkit.fluxcd.io/v1",
            "kind": "Kustomization",
            "metadata": {
                "name": source_name,
                "namespace": namespace,
            },
            "spec": {
                "interval": interval,
                "retryInterval": retry_interval,
                "path": _required_string(gitops.get("path"), "gitops.path"),
                "prune": _required_bool(gitops.get("prune"), "gitops.prune"),
                "wait": _required_bool(gitops.get("wait"), "gitops.wait"),
                "sourceRef": {
                    "kind": "GitRepository",
                    "name": source_name,
                },
            },
        },
    )
    _write_yaml(
        source_dir / "kustomization.kustomize.yaml",
        {
            "apiVersion": "kustomize.config.k8s.io/v1beta1",
            "kind": "Kustomization",
            "resources": [
                "gitrepository.yaml",
                "kustomization.yaml",
            ],
        },
    )


def _render_marker(out: Path, gitops: dict[str, Any]) -> Path:
    source_path = _source_path(out, gitops)
    source_path.mkdir(parents=True, exist_ok=True)
    generated_dir = source_path / "generated"
    marker_path = generated_dir / MARKER_NAME
    source_sha = _tree_digest(source_path, {f"generated/{MARKER_NAME}"})
    _write_yaml(
        marker_path,
        {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "gitops-snapshot-marker",
                "namespace": MARKER_NAMESPACE,
            },
            "data": {
                "source_sha": source_sha,
            },
        },
    )
    return marker_path


def render(resolved: dict[str, Any], out: Path) -> None:
    channel_id = _required_string(resolved.get("id"), "id")
    gitops = _required_mapping(resolved.get("gitops"), "gitops")
    if gitops.get("source_kind") != "git":
        raise ValueError("gitops.source_kind must be git")

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    _copy_gitops_tree(out)
    _render_source_manifests(out, channel_id, gitops)
    _render_marker(out, gitops)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--channel", help="channel id to resolve before rendering")
    source.add_argument("--resolved", help="resolved channel JSON to render")
    parser.add_argument("--out", required=True, help="snapshot output directory")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        resolved = resolver.resolve_channel(args.channel) if args.channel else _load_resolved(Path(args.resolved))
        render(resolved, Path(args.out))
        return 0
    except ChannelError as exc:
        write_error(exc)
        return 1
    except (OSError, ValueError) as exc:
        write_error(ChannelError("gitops_render_failed", args.channel or "resolved", str(exc)))
        return 1


if __name__ == "__main__":
    sys.exit(main())
