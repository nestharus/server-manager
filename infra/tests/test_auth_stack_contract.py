from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    REPO_ROOT / "infra" / "tests" / "fixtures" / "contracts" / "auth_stack_contract.yml"
)


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_pomerium_protected_api_route_contract_requires_identity_headers() -> None:
    """INIT-114 / SLICE-R.18: Pomerium route must protect API identity flow."""
    contract = _yaml(FIXTURE)
    protected = contract["protected_api"]
    headers = contract["pomerium_headers"]

    assert protected == {
        "host": "protected-api.local.humility.local",
        "route": "/api/v1/protected/authz-proof",
        "identity_header_required": True,
        "pass_identity_headers": True,
        "backend_service": "server-manager-api",
        "allowed_identity": "sample@local.humility.local",
    }
    assert headers == {
        "subject": "x-pomerium-claim-sub",
        "email": "x-pomerium-claim-email",
        "display_name": "x-pomerium-claim-name",
    }


def test_authz_proof_status_contract_is_explicit() -> None:
    """INIT-114 proposal: protected API distinguishes 401, 403, 503, and allow."""
    statuses = _yaml(FIXTURE)["cedar_statuses"]

    assert statuses == {
        "missing_identity": 401,
        "denied_identity": 403,
        "policy_engine_unavailable": 503,
        "allowed_identity": 200,
    }


def test_cedar_decision_matrix_covers_allow_and_deny_identities() -> None:
    """INIT-114 sample policy must prove both sides of the Cedar decision."""
    contract = _yaml(FIXTURE)
    decisions = contract["cedar_decisions"]

    assert decisions == [
        {
            "principal": 'User::"sample@local.humility.local"',
            "action": 'Action::"api:read"',
            "resource": 'Resource::"server-manager-api"',
            "effect": "allow",
        },
        {
            "principal": 'User::"other@local.humility.local"',
            "action": 'Action::"api:read"',
            "resource": 'Resource::"server-manager-api"',
            "effect": "deny",
        },
    ]


def test_api_proof_cases_map_to_required_statuses_and_cedar_requests() -> None:
    """Step 6b fixture keeps API proof behavior outside durable test bodies."""
    contract = _yaml(FIXTURE)
    statuses = contract["cedar_statuses"]
    cases = {case["name"]: case for case in contract["api_proof_cases"]}

    assert set(cases) == {
        "missing_identity",
        "denied_identity",
        "policy_engine_unavailable",
        "allowed_identity",
    }
    assert cases["missing_identity"]["expected_status"] == statuses["missing_identity"]
    assert cases["missing_identity"]["authorizer_called"] is False
    assert cases["denied_identity"]["expected_status"] == statuses["denied_identity"]
    assert cases["denied_identity"]["expected_request"] == {
        key: contract["cedar_decisions"][1][key]
        for key in ("principal", "action", "resource")
    }
    assert (
        cases["policy_engine_unavailable"]["expected_status"]
        == statuses["policy_engine_unavailable"]
    )
    assert cases["policy_engine_unavailable"]["cedar_unavailable"] is True
    assert cases["allowed_identity"]["expected_status"] == statuses["allowed_identity"]
    assert cases["allowed_identity"]["expected_response"]["decision"] == "Allow"


def test_playwright_auth_fixture_targets_protected_oauth_route() -> None:
    """Browser proof starts at Pomerium and authenticates through Authentik."""
    contract = _yaml(FIXTURE)
    protected = contract["protected_api"]
    identity = contract["oidc_identity"]
    browser = contract["playwright_auth"]

    assert browser == {
        "entry_host": protected["host"],
        "entry_path": protected["route"],
        "oidc_provider_host": "auth.local.humility.local",
        "authenticate_host": "authenticate.local.humility.local",
        "login_identity": identity["email"],
        "expected_authorized_status": 200,
    }
