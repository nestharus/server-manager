from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
POMERIUM_INFISICAL_SECRET = (
    REPO_ROOT
    / "gitops"
    / "channels"
    / "local"
    / "auth"
    / "pomerium"
    / "secrets-infisicalsecret.yaml"
)


def _managed_pomerium_config() -> dict[str, Any]:
    documents = list(yaml.safe_load_all(POMERIUM_INFISICAL_SECRET.read_text(encoding="utf-8")))
    config_secret = next(
        document
        for document in documents
        if document["kind"] == "InfisicalSecret"
        and document["metadata"]["name"] == "pomerium-config"
    )
    rendered_config = config_secret["spec"]["managedSecretReference"]["template"]["data"][
        "config.yaml"
    ]
    return yaml.safe_load(rendered_config)


def _web_routes() -> list[dict[str, Any]]:
    return [
        route
        for route in _managed_pomerium_config()["routes"]
        if route.get("from") == "https://web.local.humility.local"
    ]


def _applicant_route() -> dict[str, Any]:
    matches = [route for route in _web_routes() if route.get("prefix") == "/auth/discord/"]
    assert len(matches) == 1
    return matches[0]


def _web_catch_all_index() -> int:
    return next(
        index
        for index, route in enumerate(_web_routes())
        if "prefix" not in route
        and route.get("to") == "http://server-manager-web.web.svc.cluster.local:8080"
    )


def test_applicant_discord_route_targets_api_and_is_public() -> None:
    """TG-2 risk annotation: callback_route_shadowed_or_officer_auth_required;
    level=particular-integration; source=INIT-127 C2, A2.
    """
    route = _applicant_route()

    assert route["to"] == "http://server-manager-api.server-manager.svc.cluster.local:8000"
    assert route["allow_public_unauthenticated_access"] is True
    assert route["pass_identity_headers"] is False
    assert route["preserve_host_header"] is True


def test_applicant_discord_route_precedes_web_host_catch_all() -> None:
    """TG-2 risk annotation: callback_route_shadowed_by_web_catch_all;
    level=particular-integration; source=INIT-127 C2, A2.
    """
    routes = _web_routes()
    applicant_indexes = [
        index for index, route in enumerate(routes) if route.get("prefix") == "/auth/discord/"
    ]

    assert len(applicant_indexes) == 1
    assert applicant_indexes[0] < _web_catch_all_index()
