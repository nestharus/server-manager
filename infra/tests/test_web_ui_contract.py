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
    """SLICE-R.22: the durable fixture describes behavior, not dependency versions."""
    contract = _json(FIXTURE)

    assert contract["routes"]["public"]["path"] == "/"
    assert contract["routes"]["admin"]["requires_auth"] is True
    assert contract["auth"]["unauthenticated_api_status"] == 401
    assert contract["form"]["submit"]["method"] == "POST"
    assert contract["form"]["submit"]["success_status"] == 201
    assert {field["name"] for field in contract["form"]["fields"]} == {
        "character_name",
        "application_text",
    }
    assert set(contract["ui_libraries"]) == {"ark", "fontawesome", "tanstack"}
    assert "package_versions" not in contract


def test_playwright_spec_covers_route_auth_submit_and_ui_libraries() -> None:
    """SLICE-R.22: browser tests must encode the independent behavior contract."""
    spec = _text(PLAYWRIGHT_SPEC)

    for required in [
        "web UI routes public and auth-gated surfaces",
        "web UI submits the application form through the API contract",
        "web UI keeps Ark FontAwesome and TanStack controls integrated",
        "contract.json",
        "page.route",
        "unauthenticated_api_status",
        "success_status",
        "ui_libraries",
    ]:
        assert required in spec

    assert "Dark Nemesis application" not in spec
    assert "2.0.0-beta" not in spec


def test_shell_validator_keeps_runtime_ingress_reachability_strict() -> None:
    """SLICE-R.22: cluster proof must fail on no pods or curl 000."""
    validator = _text(VALIDATOR)

    for required in [
        "assert_contract_fixture",
        "assert_runtime",
        "rollout status deployment/server-manager-web",
        '[[ "$public_code" != "000" ]]',
        '[[ "$admin_code" != "000" ]]',
        "unauthenticated_api_status",
    ]:
        assert required in validator

    assert "solid-js" not in validator
    assert "@tanstack/solid-router" not in validator


def test_e2e_wrapper_does_not_turn_missing_browser_flow_into_success() -> None:
    """SLICE-R.22: the web UI E2E wrapper cannot skip OAuth/browser proof green."""
    wrapper = _text(E2E_WRAPPER)

    assert "run-browser-flow.sh" in wrapper
    assert "e2e_skip_flow" not in wrapper
    assert "Playwright completed web UI OAuth and navigation flow" in wrapper
