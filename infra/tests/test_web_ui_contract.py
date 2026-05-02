from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "infra" / "tests" / "fixtures" / "web-ui" / "contract.json"
PLAYWRIGHT_SPEC = REPO_ROOT / "services" / "web" / "tests" / "compat.spec.ts"
VALIDATOR = REPO_ROOT / "infra" / "tests" / "validate_web_ui_local.sh"
E2E_WRAPPER = REPO_ROOT / "infra" / "tests" / "e2e" / "tests" / "19-web-ui.sh"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_web_ui_fixture_defines_behavior_contract_not_package_pins() -> None:
    """TG-7 risk annotation: spa_receipt_gate_contract_drift; level=component;
    source=.tmp/init-128/phase6/step6a-contract.md#C7-C8.
    """
    contract = _json(FIXTURE)

    assert contract["routes"]["public"]["path"] == "/"
    assert contract["routes"]["admin"]["requires_auth"] is True
    assert contract["auth"]["unauthenticated_api_status"] == 401
    assert contract["auth"]["applicant"] == {
        "me_endpoint": "/auth/discord/me",
        "start_endpoint": "/auth/discord/start?return_to=/applications",
        "receipt_cookie": "applicant_receipt",
        "login_button_name": "Login with Discord",
        "identity_indicator_prefix": "Logged in as Discord ",
        "receipt_required_error_code": "applicant_receipt_required",
    }
    assert contract["form"]["submit"]["endpoint"] == "/api/public/applications"
    assert contract["form"]["submit"]["method"] == "POST"
    assert contract["form"]["submit"]["success_status"] == 201
    assert contract["form"]["submit"]["success_application_id"]
    assert contract["form"]["submit"]["client_application_id_pattern"]
    assert {field["name"] for field in contract["form"]["fields"]} == {
        "character_name",
        "application_text",
    }
    assert {field["name"] for field in contract["form"]["submit"]["payload_fields"]} == {
        "scope.scope_kind",
        "scope.scope_id",
        "responses.character_name",
        "responses.application_text",
    }
    assert set(contract["ui_libraries"]) == {"ark", "fontawesome", "tanstack"}
    assert "package_versions" not in contract


def test_playwright_spec_covers_route_auth_submit_and_ui_libraries() -> None:
    """TG-7 risk annotation: spa_receipt_gate_contract_drift; level=component;
    source=.tmp/init-128/phase6/step6a-contract.md#C7-C8.
    """
    spec = _text(PLAYWRIGHT_SPEC)

    for required in [
        "web UI routes public and auth-gated surfaces",
        "applications page without receipt shows only Discord login",
        "applications page with valid receipt shows form and Discord identity",
        "application form submits with a valid receipt and shows success",
        "application submit with expired receipt redirects to Discord auth start",
        "web UI keeps Ark FontAwesome and TanStack controls integrated",
        "contract.json",
        "page.route",
        "applicant_receipt",
        "applicant_receipt_required",
        "Logged in as Discord 123456789012345678",
        "unauthenticated_api_status",
        "success_status",
        "client_application_id_pattern",
        "#submit-status",
        "ui_libraries",
    ]:
        assert required in spec

    assert "Dark Nemesis application" not in spec
    assert "2.0.0-beta" not in spec


def test_shell_validator_keeps_runtime_ingress_reachability_strict() -> None:
    """TG-9 risk annotation: e2e_fixture_false_green; level=end-to-end;
    source=planning/proposals/02-public-application-intake.md#§9 AS-1 AS-3 AS-4 AS-5.
    """
    validator = _text(VALIDATOR)

    for required in [
        "assert_contract_fixture",
        "assert_runtime",
        "/api/public/applications",
        "rollout status deployment/server-manager-web",
        '[[ "$public_code" != "000" ]]',
        '[[ "$admin_code" != "000" ]]',
        "unauthenticated_api_status",
    ]:
        assert required in validator

    assert "solid-js" not in validator
    assert "@tanstack/solid-router" not in validator


def test_e2e_wrapper_does_not_turn_missing_browser_flow_into_success() -> None:
    """TG-8 risk annotation: e2e_receipt_required_submit_false_green;
    level=end-to-end; source=.tmp/init-128/phase6/step6a-contract.md#C9.
    """
    wrapper = _text(E2E_WRAPPER)

    assert "run-browser-flow.sh" in wrapper
    assert "assert_public_submit_persisted" in wrapper
    assert "server-manager-e2e-fixtures" in wrapper
    assert "E2E_APPLICANT_RECEIPT_SIGNING_KEY" in wrapper
    assert "m.kind = 'discord'" in wrapper
    assert "e2e_skip_flow" not in wrapper
    assert "Playwright completed web UI OAuth and navigation flow" in wrapper
