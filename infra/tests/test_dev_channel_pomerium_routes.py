from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEV_POMERIUM_CONFIG = (
    REPO_ROOT / "gitops" / "channels" / "dev" / "auth" / "pomerium" / "secrets-infisicalsecret.yaml"
)
DEV_POMERIUM_INGRESS = (
    REPO_ROOT / "gitops" / "channels" / "dev" / "auth" / "pomerium" / "public-intake-rate-limit.yaml"
)

WEB_HOST = "https://web.dev.humility.gg"
PROTECTED_API_HOST = "https://protected-api.dev.humility.gg"
WEB_UPSTREAM = "http://server-manager-web.web.svc.cluster.local:8080"
EXPECTED_BROWSER_ENDPOINTS = {
    "/api/public/applications",
    "/api/public/chapters",
    "/api/public/applications/upload-url",
}


def _yaml_documents(path: Path) -> list[dict[str, Any]]:
    return [
        document
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if isinstance(document, dict)
    ]


def _metadata(resource: dict[str, Any]) -> dict[str, Any]:
    return resource.get("metadata", {}) or {}


def _pomerium_config() -> dict[str, Any]:
    docs = _yaml_documents(DEV_POMERIUM_CONFIG)
    document = next(
        (
            doc
            for doc in docs
            if doc.get("kind") == "InfisicalSecret" and _metadata(doc).get("name") == "pomerium-config"
        ),
        None,
    )
    assert document is not None, f"missing pomerium-config in {DEV_POMERIUM_CONFIG.relative_to(REPO_ROOT)}"

    data = (
        document.get("spec", {})
        .get("managedSecretReference", {})
        .get("template", {})
        .get("data", {})
    )
    config = data.get("config.yaml") or data.get("pomerium-config")
    assert isinstance(config, str), "pomerium-config must carry embedded config.yaml text"

    parsed = yaml.safe_load(config)
    assert isinstance(parsed, dict), "embedded Pomerium config must parse as a YAML mapping"
    return parsed


def _ingress_prefix_paths() -> set[str]:
    docs = _yaml_documents(DEV_POMERIUM_INGRESS)
    ingress = next(
        (
            doc
            for doc in docs
            if doc.get("kind") == "Ingress" and _metadata(doc).get("name") == "web-public-intake"
        ),
        None,
    )
    assert ingress is not None, f"missing web-public-intake in {DEV_POMERIUM_INGRESS.relative_to(REPO_ROOT)}"

    paths: set[str] = set()
    for rule in ingress.get("spec", {}).get("rules", []) or []:
        assert rule.get("host") == "web.dev.humility.gg"
        for path_item in rule.get("http", {}).get("paths", []) or []:
            if path_item.get("pathType") == "Prefix":
                paths.add(path_item.get("path", ""))
    return paths


def test_dev_pomerium_config_parses_with_dev_routes() -> None:
    config = _pomerium_config()

    assert config.get("authenticate_service_url") == "https://authenticate.dev.humility.gg"
    assert config.get("idp_provider_url") == "https://auth.dev.humility.gg/application/o/pomerium/"

    routes = config.get("routes")
    assert isinstance(routes, list), "embedded Pomerium config must include a routes list"
    assert len(routes) >= 10

    sources = {route.get("from") for route in routes if isinstance(route, dict)}
    assert WEB_HOST in sources
    assert PROTECTED_API_HOST in sources
    assert "https://web.local.humility.local" not in sources
    assert "https://protected-api.local.humility.local" not in sources

    web_identity_indexes: list[int] = []
    web_public_indexes: list[int] = []
    for index, route in enumerate(routes):
        assert isinstance(route, dict)
        source = route.get("from", "")
        if source:
            assert ".local.humility.local" not in source
        if source != WEB_HOST:
            continue
        if route.get("allow_public_unauthenticated_access") is True and route.get("to") == WEB_UPSTREAM:
            web_public_indexes.append(index)
        elif route.get("allow_public_unauthenticated_access") is not True:
            web_identity_indexes.append(index)

    assert web_public_indexes, "missing public web catch-all route"
    assert web_identity_indexes, "missing identity-bearing web routes"
    assert all(index < web_public_indexes[0] for index in web_identity_indexes)


def test_dev_pomerium_public_intake_paths_are_prefix_covered() -> None:
    prefix_paths = _ingress_prefix_paths()

    assert "/api/public/applications" in prefix_paths
    assert "/api/public/chapters" in prefix_paths
    for endpoint in EXPECTED_BROWSER_ENDPOINTS:
        assert any(endpoint.startswith(prefix) for prefix in prefix_paths), (
            f"{endpoint} is not covered by a dev Pomerium Prefix ingress path"
        )
