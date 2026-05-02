from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "infra" / "tests" / "validate_kong_kic_translation_local.sh"
KONG_NAMESPACE_PATTERN = (
    r"(?:-n|--namespace)\s+(?:\"?\$KONG_NAMESPACE\"?|kong-system)"
)


def _validator_text() -> str:
    return VALIDATOR.read_text(encoding="utf-8")


def test_validator_pins_kong_system_namespace() -> None:
    validator = _validator_text()

    assert 'KONG_NAMESPACE="kong-system"' in validator


def test_validator_port_forwards_admin_api_https_port_8444() -> None:
    validator = _validator_text()

    assert 'KONG_ADMIN_PORT="8444"' in validator or re.search(
        r'(?:\$\{?LOCAL_PORT\}?|[0-9]+):8444\b', validator
    ), (
        "Kong Admin API must be reached through HTTPS port 8444"
    )


def test_validator_uses_insecure_curl_for_self_signed_admin_api_tls() -> None:
    validator = _validator_text()

    assert re.search(r"\bcurl\b[\s\S]*(?:--insecure|-k)\b", validator), (
        "Admin API curl calls must allow Kong's self-signed local TLS certificate"
    )


def test_validator_port_forwards_kong_deployment_in_kong_system_namespace() -> None:
    validator = _validator_text()

    assert "kubectl" in validator
    assert "port-forward" in validator
    assert re.search(r"\bdeploy(?:ment)?/kong-kong\b", validator), (
        "Admin API port-forward must target the kong-kong deployment"
    )
    assert re.search(KONG_NAMESPACE_PATTERN, validator), (
        "Admin API port-forward must run in the kong-system namespace"
    )


def test_validator_cleans_up_port_forward_on_exit_interrupt_and_terminate() -> None:
    validator = _validator_text()

    trap_lines = [
        line for line in validator.splitlines() if re.search(r"\btrap\b", line)
    ]
    assert any(
        "EXIT" in line and "INT" in line and "TERM" in line for line in trap_lines
    ), "port-forward cleanup trap must cover EXIT, INT, and TERM"


def test_validator_handles_routes_pagination() -> None:
    validator = _validator_text()

    assert re.search(r"/routes(?!/)", validator), "validator must read GET /routes"
    assert re.search(r"\b(?:while|until)\b[\s\S]*(?:\.next|\"next\")", validator), (
        "GET /routes must walk Kong pagination using the next field"
    )


def test_validator_handles_route_plugin_pagination() -> None:
    validator = _validator_text()

    assert re.search(r"/routes/(?:[^\"' ]+|\$\{?[^}\"'/]+\}?)/plugins", validator), (
        "route-scoped plugins must be read from GET /routes/<id>/plugins"
    )
    assert len(re.findall(r"\b(?:while|until)\b", validator)) >= 2, (
        "routes and route-scoped plugin walks must each use a pagination loop"
    )
    assert len(re.findall(r"(?:\.next|\"next\")", validator)) >= 2, (
        "routes and route-scoped plugin walks must each follow Kong's next field"
    )


def test_validator_checks_required_admin_path_negative_not_vacuous_pass() -> None:
    validator = _validator_text()

    assert "/api/v1/web/admin/chapters" in validator
    admin_path_index = validator.index("/api/v1/web/admin/chapters")
    nearby_admin_negative = validator[admin_path_index : admin_path_index + 4000]
    assert "rate-limiting" in nearby_admin_negative
    assert re.search(r"\b(?:fail|die)\b", nearby_admin_negative), (
        "required admin-path negative must fail loudly instead of passing vacuously"
    )
