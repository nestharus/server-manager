from __future__ import annotations

from pathlib import Path
from typing import Any

import json
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_GITOPS = REPO_ROOT / "gitops" / "channels" / "local"
WEB_CONTRACT = REPO_ROOT / "infra" / "tests" / "fixtures" / "web-ui" / "contract.json"
PLUGIN_NAME = "public-intake-rate-limit"


def _yaml_documents(path: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if isinstance(document, dict):
            document["_source_path"] = str(path.relative_to(REPO_ROOT))
            docs.append(document)
    return docs


def _local_resources() -> list[dict[str, Any]]:
    candidates = sorted(
        [
            *(
                LOCAL_GITOPS / "applications" / "server-manager"
            ).glob("*.yaml"),
            *(LOCAL_GITOPS / "auth" / "pomerium").glob("*.yaml"),
        ]
    )
    required = [
        LOCAL_GITOPS / "auth" / "pomerium" / "ingress.yaml",
        LOCAL_GITOPS / "applications" / "server-manager" / "api-ingress.yaml",
    ]
    for path in required:
        assert path.is_file(), f"missing expected local GitOps manifest: {path.relative_to(REPO_ROOT)}"
    docs: list[dict[str, Any]] = []
    for path in candidates:
        docs.extend(_yaml_documents(path))
    return docs


def _web_submit_endpoint() -> str:
    return json.loads(WEB_CONTRACT.read_text(encoding="utf-8"))["form"]["submit"]["endpoint"]


def _metadata(resource: dict[str, Any]) -> dict[str, Any]:
    return resource.get("metadata", {})


def _annotations(resource: dict[str, Any]) -> dict[str, str]:
    return _metadata(resource).get("annotations", {}) or {}


def _ingress_paths(resource: dict[str, Any]) -> list[tuple[str, str]]:
    paths: list[tuple[str, str]] = []
    for rule in resource.get("spec", {}).get("rules", []):
        host = rule.get("host")
        for path in rule.get("http", {}).get("paths", []):
            paths.append((host, path.get("path")))
    return paths


def _plugin_annotation(resource: dict[str, Any]) -> str | None:
    return _annotations(resource).get("konghq.com/plugins")


def test_public_intake_kong_plugin_has_documented_rate_limit_config() -> None:
    """Risk annotation: group=TG-7; named_risk=public_rate_limit_absent_or_misbound;
    level=particular-integration; source=proposals/02-public-application-intake.md#§7 AS-5.
    """
    plugins = [
        resource
        for resource in _local_resources()
        if resource.get("kind") == "KongPlugin"
        and _metadata(resource).get("name") == PLUGIN_NAME
    ]

    assert len(plugins) == 1
    plugin = plugins[0]
    assert _metadata(plugin).get("namespace") == "server-manager"
    assert plugin["plugin"] == "rate-limiting"
    assert plugin["config"]["minute"] == 5
    assert plugin["config"]["hour"] == 50
    assert plugin["config"]["policy"] == "local"


def test_public_intake_plugin_is_bound_only_to_public_submit_paths() -> None:
    """Risk annotation: group=TG-7; named_risk=public_rate_limit_absent_or_misbound;
    level=particular-integration; source=proposals/02-public-application-intake.md#§7 AS-5.
    """
    ingresses = [
        resource for resource in _local_resources() if resource.get("kind") == "Ingress"
    ]
    annotated_paths = {
        path
        for ingress in ingresses
        if _plugin_annotation(ingress) == PLUGIN_NAME
        for path in _ingress_paths(ingress)
    }

    assert (
        "web.local.humility.local",
        "/api/applications",
    ) in annotated_paths
    assert (
        "web.local.humility.local",
        _web_submit_endpoint(),
    ) in annotated_paths
    assert (
        "api.local.humility.local",
        "/api/v1/public/applications",
    ) in annotated_paths

    web_catch_all = next(
        ingress
        for ingress in ingresses
        if _metadata(ingress).get("name") == "web"
        and ("web.local.humility.local", "/") in _ingress_paths(ingress)
    )
    protected_api = next(
        ingress for ingress in ingresses if _metadata(ingress).get("name") == "protected-api"
    )
    authenticated_api = next(
        ingress
        for ingress in ingresses
        if _metadata(ingress).get("name") == "server-manager-api"
        and ("api.local.humility.local", "/") in _ingress_paths(ingress)
    )

    assert _plugin_annotation(web_catch_all) != PLUGIN_NAME
    assert _plugin_annotation(protected_api) != PLUGIN_NAME
    assert _plugin_annotation(authenticated_api) != PLUGIN_NAME
