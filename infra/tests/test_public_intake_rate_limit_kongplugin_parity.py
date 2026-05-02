from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
CHANNELS_ROOT = REPO_ROOT / "gitops" / "channels"
CANONICAL_PLUGIN_PATH = (
    CHANNELS_ROOT
    / "local"
    / "applications"
    / "server-manager"
    / "public-intake-rate-limit.yaml"
)
PLUGIN_NAME = "public-intake-rate-limit"
EXPECTED_PLUGIN = "rate-limiting"
EXPECTED_CONFIG = {
    "minute": 5,
    "hour": 50,
    "policy": "local",
    "fault_tolerant": True,
    "hide_client_headers": False,
}


def _yaml_paths() -> list[Path]:
    return sorted(
        {
            *CHANNELS_ROOT.rglob("*.yaml"),
            *CHANNELS_ROOT.rglob("*.yml"),
        }
    )


def _channel_for(path: Path) -> str:
    return path.relative_to(CHANNELS_ROOT).parts[0]


def _source_path(path: Path) -> str:
    channel_relative = path.relative_to(CHANNELS_ROOT)
    return str(Path(*channel_relative.parts[1:]))


def _yaml_documents(path: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if isinstance(document, dict):
            document["_source_path"] = _source_path(path)
            document["_channel"] = _channel_for(path)
            docs.append(document)
    return docs


def _all_channel_documents() -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in _yaml_paths():
        docs.extend(_yaml_documents(path))
    return docs


def _metadata(resource: dict[str, Any]) -> dict[str, Any]:
    return resource.get("metadata", {}) or {}


def _namespace(resource: dict[str, Any]) -> str:
    return _metadata(resource).get("namespace") or "default"


def _name(resource: dict[str, Any]) -> str:
    return _metadata(resource).get("name") or "<missing>"


def _plugin_names(resource: dict[str, Any]) -> set[str]:
    annotation = (_metadata(resource).get("annotations") or {}).get("konghq.com/plugins")
    if not isinstance(annotation, str):
        return set()
    return {name.strip() for name in annotation.split(",") if name.strip()}


def _plugin_index(
    docs: list[dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    plugins: dict[tuple[str, str, str], dict[str, Any]] = {}
    for document in docs:
        if document.get("kind") != "KongPlugin":
            continue
        plugins[(document["_channel"], _namespace(document), _name(document))] = document
    return plugins


def _canonical_plugin() -> dict[str, Any]:
    for document in _yaml_documents(CANONICAL_PLUGIN_PATH):
        if (
            document.get("kind") == "KongPlugin"
            and _name(document) == PLUGIN_NAME
            and _namespace(document) == "server-manager"
        ):
            return document
    raise AssertionError(
        "missing canonical KongPlugin "
        f"local/{_source_path(CANONICAL_PLUGIN_PATH)}:server-manager/{PLUGIN_NAME}"
    )


def _resource_ref(resource: dict[str, Any]) -> str:
    return f"{resource['_channel']}/{resource['_source_path']}:{_name(resource)}:{_namespace(resource)}"


def _config_diff(observed: dict[str, Any]) -> str:
    expected_keys = set(EXPECTED_CONFIG)
    observed_keys = set(observed)
    diffs: list[str] = []
    for key in sorted(expected_keys | observed_keys):
        got = observed.get(key, "<missing>")
        expected = EXPECTED_CONFIG.get(key, "<unexpected>")
        if got != expected:
            diffs.append(f"{key}={got!r} expected={expected!r}")
    return ", ".join(diffs)


def test_every_ingress_with_plugin_annotation_has_matching_kongplugin() -> None:
    docs = _all_channel_documents()
    plugins = _plugin_index(docs)
    orphans = []

    for document in docs:
        if document.get("kind") != "Ingress" or PLUGIN_NAME not in _plugin_names(document):
            continue
        key = (document["_channel"], _namespace(document), PLUGIN_NAME)
        if key not in plugins:
            orphans.append(_resource_ref(document))

    assert not orphans, (
        "orphaned public-intake rate-limit Ingress annotations: "
        + "; ".join(sorted(orphans))
    )


def test_kongplugin_config_matches_canonical() -> None:
    canonical = _canonical_plugin()
    assert canonical.get("plugin") == EXPECTED_PLUGIN
    assert canonical.get("config") == EXPECTED_CONFIG

    failures = []
    for document in _all_channel_documents():
        if document.get("kind") != "KongPlugin" or _name(document) != PLUGIN_NAME:
            continue
        if (
            document["_channel"] == canonical["_channel"]
            and document["_source_path"] == canonical["_source_path"]
            and _namespace(document) == _namespace(canonical)
        ):
            continue

        details = []
        if document.get("plugin") != EXPECTED_PLUGIN:
            details.append(
                f"plugin={document.get('plugin')!r} expected={EXPECTED_PLUGIN!r}"
            )
        config = document.get("config") or {}
        diff = _config_diff(config if isinstance(config, dict) else {"<config>": config})
        if diff:
            details.append(diff)
        if details:
            failures.append(
                f"{document['_channel']}/{document['_source_path']}:"
                f"{_namespace(document)}/{PLUGIN_NAME} "
                + "; ".join(details)
            )

    assert not failures, (
        "public-intake KongPlugin config drift: " + " | ".join(sorted(failures))
    )


def test_kongplugin_present_in_both_channels_auth_system() -> None:
    missing = []

    for channel_dir in sorted(path for path in CHANNELS_ROOT.iterdir() if path.is_dir()):
        path = channel_dir / "auth" / "pomerium" / "public-intake-rate-limit.yaml"
        if not path.is_file():
            continue
        docs = _yaml_documents(path)
        has_annotated_ingress = any(
            document.get("kind") == "Ingress"
            and PLUGIN_NAME in _plugin_names(document)
            for document in docs
        )
        if not has_annotated_ingress:
            continue
        has_auth_plugin = any(
            document.get("kind") == "KongPlugin"
            and _name(document) == PLUGIN_NAME
            and _namespace(document) == "auth-system"
            for document in docs
        )
        if not has_auth_plugin:
            missing.append(channel_dir.name)

    assert not missing, (
        "missing auth-system public-intake KongPlugin in channels: "
        + ", ".join(missing)
    )
