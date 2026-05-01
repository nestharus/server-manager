#!/usr/bin/env python3
"""Render per-channel Flux GitOps source manifests into a temp snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

import resolve_platform_channel as resolver
from resolve_platform_channel import ChannelError, write_error


REPO_ROOT = Path(__file__).resolve().parents[2]
GITOPS_ROOT = REPO_ROOT / "gitops"
POLICY_ROOT = REPO_ROOT / "policy"
MARKER_NAME = "gitops-snapshot-marker.yaml"
MARKER_NAMESPACE = "humility-gitops-sentinel"
POLICY_BUNDLE_RELATIVE = Path("policy/cedar/channels/local/services/server-manager-api/policies.json")
GENERATED_POLICY_DIR_RELATIVE = Path(
    "policy/cedar/channels/local/services/server-manager-api/generated/policies"
)
POLICY_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


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


def _copy_policy_tree(out: Path) -> Path:
    snapshot_policy = out / "policy"
    if POLICY_ROOT.is_dir():
        shutil.copytree(POLICY_ROOT, snapshot_policy, dirs_exist_ok=True)
    else:
        snapshot_policy.mkdir(parents=True)
    return snapshot_policy


def _load_policy_bundle(policy_file: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(policy_file.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing canonical Cedar policy file: {policy_file}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid Cedar policy JSON: {exc}") from exc

    if not isinstance(payload, list):
        raise ValueError("canonical Cedar policy JSON must be a list")
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Cedar policy entry {index} must be an object")
    return payload


def _materialize_cedar_policy_files(out: Path) -> None:
    policy_file = out / POLICY_BUNDLE_RELATIVE
    generated_dir = out / GENERATED_POLICY_DIR_RELATIVE
    policies = _load_policy_bundle(policy_file)
    seen_ids: set[str] = set()

    if generated_dir.exists():
        shutil.rmtree(generated_dir)
    generated_dir.mkdir(parents=True)

    for index, policy in enumerate(policies):
        if "id" not in policy:
            raise ValueError(f"Cedar policy entry {index} is missing id")
        if "content" not in policy:
            raise ValueError(f"Cedar policy entry {index} is missing content")

        policy_id = policy["id"]
        content = policy["content"]
        if not isinstance(policy_id, str) or not policy_id:
            raise ValueError(f"Cedar policy entry {index} has an invalid id")
        if not POLICY_ID_PATTERN.fullmatch(policy_id):
            raise ValueError(f"Cedar policy id contains path-unsafe characters: {policy_id}")
        if policy_id in seen_ids:
            raise ValueError(f"duplicate Cedar policy id: {policy_id}")
        if not isinstance(content, str) or content == "":
            raise ValueError(f"Cedar policy {policy_id} has empty content")

        seen_ids.add(policy_id)
        (generated_dir / f"{policy_id}.cedar").write_text(f"{content}\n", encoding="utf-8")

    cedar_files = sorted(
        f"{GENERATED_POLICY_DIR_RELATIVE.as_posix()}/{policy_id}.cedar"
        for policy_id in seen_ids
    )
    (out / ".manifest").write_text("\n".join(cedar_files) + "\n", encoding="utf-8")


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


def _alembic_migrations_digest(repo_root: str | Path) -> str:
    versions_root = Path(repo_root) / "migrations" / "versions"
    if not versions_root.is_dir():
        raise ValueError(f"missing Alembic migrations directory: {versions_root}")

    digest = hashlib.sha256()
    for path in sorted(item for item in versions_root.rglob("*") if item.is_file()):
        relative_path = path.relative_to(versions_root)
        if "__pycache__" in relative_path.parts or path.suffix == ".pyc":
            continue
        relative = relative_path.as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:12]


def _seed_sql_digest(seed_manifest: Path) -> str:
    try:
        documents = list(yaml.safe_load_all(seed_manifest.read_text(encoding="utf-8")))
    except FileNotFoundError as exc:
        raise ValueError(f"missing seed manifest: {seed_manifest}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid seed manifest YAML: {seed_manifest}: {exc}") from exc

    seed_sql: str | None = None
    for document in documents:
        if not isinstance(document, dict):
            continue
        if document.get("kind") != "ConfigMap":
            continue
        metadata = document.get("metadata")
        if (
            not isinstance(metadata, dict)
            or metadata.get("name") != "seed-public-intake-form-payload"
        ):
            continue
        data = document.get("data")
        if not isinstance(data, dict):
            raise ValueError(f"seed ConfigMap data must be an object: {seed_manifest}")
        value = data.get("seed.sql")
        if not isinstance(value, str) or not value:
            raise ValueError(
                f"seed ConfigMap must contain non-empty data.seed.sql: {seed_manifest}"
            )
        seed_sql = value
        break

    if seed_sql is None:
        raise ValueError(f"missing ConfigMap/seed-public-intake-form-payload in {seed_manifest}")

    return hashlib.sha256(seed_sql.encode("utf-8")).hexdigest()[:12]


def _substitute_tokens(path: Path, substitutions: dict[str, str]) -> None:
    content = path.read_text(encoding="utf-8")
    missing = [token for token in substitutions if token not in content]
    if missing:
        raise ValueError(f"missing placeholder token(s) in {path}: {', '.join(missing)}")
    for token, value in substitutions.items():
        content = content.replace(token, value)
    path.write_text(content, encoding="utf-8")


def _render_source_manifests(out: Path, channel_id: str, gitops: dict[str, Any]) -> None:
    source_name = _required_string(gitops.get("kustomization_name"), "gitops.kustomization_name")
    namespace = _required_string(gitops.get("kustomization_namespace"), "gitops.kustomization_namespace")
    decryption_secret_namespace = _required_string(
        gitops.get("decryption_secret_namespace"),
        "gitops.decryption_secret_namespace",
    )
    if decryption_secret_namespace != namespace:
        raise ValueError("gitops.decryption_secret_namespace must match gitops.kustomization_namespace")
    interval = _required_string(gitops.get("interval"), "gitops.interval")
    retry_interval = _required_string(gitops.get("retry_interval"), "gitops.retry_interval")
    source_dir = out / "gitops" / "sources" / channel_id
    server_manager_dir = _source_path(out, gitops) / "applications" / "server-manager"
    alembic_hash = _alembic_migrations_digest(REPO_ROOT)
    seed_manifest = server_manager_dir / "seed-public-intake-form.yaml"
    seed_hash = _seed_sql_digest(seed_manifest)

    _substitute_tokens(
        server_manager_dir / "alembic-migration-job.yaml",
        {"__ALEMBIC_HASH__": alembic_hash},
    )
    _substitute_tokens(seed_manifest, {"__SEED_HASH__": seed_hash})

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
                "force": True,
                "sourceRef": {
                    "kind": "GitRepository",
                    "name": source_name,
                },
                "decryption": {
                    "provider": "sops",
                    "secretRef": {
                        "name": _required_string(gitops.get("sops_age_secret_name"), "gitops.sops_age_secret_name"),
                    },
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
    _copy_policy_tree(out)
    _materialize_cedar_policy_files(out)
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
