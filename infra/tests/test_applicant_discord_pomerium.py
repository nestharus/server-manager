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
        and "path" not in route
        and route.get("to") == "http://server-manager-web.web.svc.cluster.local:8080"
    )


def _find_web_route(**criteria: str) -> tuple[int, dict[str, Any]]:
    matches = [
        (index, route)
        for index, route in enumerate(_web_routes())
        if all(route.get(key) == value for key, value in criteria.items())
    ]
    assert len(matches) == 1
    return matches[0]


def _matches(route: dict[str, Any], request_path: str) -> bool:
    if "path" in route:
        return route["path"] == request_path
    if "prefix" in route:
        return request_path.startswith(route["prefix"])
    return True


def _first_web_route_for(request_path: str) -> dict[str, Any]:
    return next(route for route in _web_routes() if _matches(route, request_path))


def _assert_identity_web_route(route: dict[str, Any]) -> None:
    assert route["to"] == "http://server-manager-web.web.svc.cluster.local:8080"
    assert route["preserve_host_header"] is True
    assert route["pass_identity_headers"] is True
    assert route["allow_any_authenticated_user"] is True


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


def test_pomerium_idp_scopes_include_discord_user_id_exactly() -> None:
    """Risk annotation: group=TG-4; named_risk=idp_scope_missing;
    level=static-config; source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-4.
    """
    config = _managed_pomerium_config()

    assert set(config["idp_scopes"].split()) == {
        "openid",
        "email",
        "profile",
        "discord_user_id",
    }


def test_pomerium_jwt_claims_headers_include_exact_identity_claims() -> None:
    """Risk annotation: group=TG-4; named_risk=jwt_claim_headers_drift;
    level=static-config; source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-4.
    """
    headers = _managed_pomerium_config()["jwt_claims_headers"]

    assert headers == {
        "x-pomerium-claim-email": "email",
        "x-pomerium-claim-sub": "sub",
        "x-pomerium-claim-groups": "groups",
        "x-pomerium-claim-name": "name",
        "x-pomerium-claim-discord-user-id": "discord_user_id",
    }


def test_identity_bearing_web_routes_precede_public_catch_all() -> None:
    """Risk annotation: group=TG-4; named_risk=identity_route_order;
    level=static-config; source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-4.
    """
    catch_all_index = _web_catch_all_index()
    route_specs = [
        {"path": "/api/me"},
        {"prefix": "/api/web/admin/"},
        {"prefix": "/api/web/officer/"},
        {"path": "/applications/queue"},
        {"prefix": "/applications/queue/"},
        {"prefix": "/applications/"},
    ]

    for criteria in route_specs:
        index, route = _find_web_route(**criteria)
        _assert_identity_web_route(route)
        assert index < catch_all_index


def test_pomerium_route_matching_avoids_api_and_queue_collisions() -> None:
    """Risk annotation: group=TG-4; named_risk=route_collision;
    level=static-config; source=.tmp/init-133B-i/phase6/step6a-contract.md#TG-4.
    """
    assert _first_web_route_for("/api/me").get("path") == "/api/me"
    assert _first_web_route_for("/applications/queue").get("path") == "/applications/queue"
    assert _first_web_route_for("/applications/queue/").get("prefix") == "/applications/queue/"
    assert (
        _first_web_route_for("/applications/11111111-1111-4111-8111-111111111111").get(
            "prefix"
        )
        == "/applications/"
    )

    assert _first_web_route_for("/api/me-foo").get("path") != "/api/me"
    assert _first_web_route_for("/api/members/abc").get("path") != "/api/me"
    assert _first_web_route_for("/applications/queue-foo").get("path") != "/applications/queue"
    bare_applications_route = _first_web_route_for("/applications")
    assert bare_applications_route.get("path") != "/applications/queue"
    assert bare_applications_route.get("prefix") != "/applications/"


def test_applications_detail_route_is_after_queue_and_before_catch_all() -> None:
    """Risk annotation: group=TG-3; named_risk=detail_route_order;
    level=static-config; source=.tmp/init-133B-ii/phase6/step6a-contract.md#TG-3.
    """
    catch_all_index = _web_catch_all_index()
    queue_path_index, queue_path_route = _find_web_route(path="/applications/queue")
    queue_prefix_index, queue_prefix_route = _find_web_route(prefix="/applications/queue/")
    detail_prefix_index, detail_prefix_route = _find_web_route(prefix="/applications/")

    _assert_identity_web_route(queue_path_route)
    _assert_identity_web_route(queue_prefix_route)
    _assert_identity_web_route(detail_prefix_route)
    assert queue_path_index < detail_prefix_index
    assert queue_prefix_index < detail_prefix_index
    assert detail_prefix_index < catch_all_index
