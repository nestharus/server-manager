from __future__ import annotations

import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX = REPO_ROOT / "infra" / "tests" / "fixtures" / "contracts" / "access_policy_matrix.yml"
VALIDATOR = REPO_ROOT / "infra" / "tests" / "validate_access_policy_local.sh"

PUBLIC_PRINCIPAL = 'Public::"web-intake.local"'
PUBLIC_SUBMIT_ACTION = 'Action::"application:submit_public"'
API_READ_ACTION = 'Action::"api:read"'
PUBLIC_RESOURCE = 'Resource::"server-manager-api:public-applications"'
API_RESOURCE = 'Resource::"server-manager-api"'


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _repo_path(relative_path: str) -> Path:
    path = REPO_ROOT / relative_path
    assert path.is_file(), f"missing fixture path: {relative_path}"
    return path


def _policies(fixture: dict) -> list[dict]:
    return json.loads(_repo_path(fixture["bundle"]["policy_file"]).read_text(encoding="utf-8"))


def _service_identities(fixture: dict) -> dict:
    return json.loads(
        _repo_path(fixture["bundle"]["service_identity_file"]).read_text(encoding="utf-8")
    )


def _policy_contents(policies: list[dict]) -> str:
    return "\n".join(policy["content"] for policy in policies)


def test_access_policy_matrix_contains_public_submit_allow_and_read_deny() -> None:
    """Risk annotation: group=TG-6; named_risk=public_policy_fixture_gap;
    level=particular-integration; source=proposals/02-public-application-intake.md#§6 AS-4.
    """
    fixture = _yaml(MATRIX)
    decisions = fixture["decisions"]

    assert {
        "principal": PUBLIC_PRINCIPAL,
        "action": PUBLIC_SUBMIT_ACTION,
        "resource": PUBLIC_RESOURCE,
        "effect": "allow",
    } in decisions
    assert {
        "principal": PUBLIC_PRINCIPAL,
        "action": API_READ_ACTION,
        "resource": API_RESOURCE,
        "effect": "deny",
    } in decisions


def test_public_intake_policy_bundle_contains_matching_permit_and_forbid() -> None:
    """Risk annotation: group=TG-6; named_risk=public_policy_fixture_gap;
    level=particular-integration; source=proposals/02-public-application-intake.md#§6 AS-4.
    """
    fixture = _yaml(MATRIX)
    contents = _policy_contents(_policies(fixture))

    assert (
        f"permit(principal == {PUBLIC_PRINCIPAL}, "
        f"action == {PUBLIC_SUBMIT_ACTION}, resource == {PUBLIC_RESOURCE});"
    ) in contents
    assert (
        f"forbid(principal == {PUBLIC_PRINCIPAL}, "
        f"action == {API_READ_ACTION}, resource == {API_RESOURCE});"
    ) in contents


def test_public_intake_does_not_add_service_identity() -> None:
    """Risk annotation: group=TG-6; named_risk=public_service_identity_scope_creep;
    level=particular-integration; source=proposals/02-public-application-intake.md#§6 AS-4.
    """
    fixture = _yaml(MATRIX)
    identities = _service_identities(fixture)
    serialized = json.dumps(identities, sort_keys=True)

    assert "web-intake" not in serialized
    assert "public-intake" not in serialized
    assert "application:submit_public" not in serialized
    assert "Public::" not in serialized


def test_access_policy_validator_remains_matrix_driven_for_public_intake() -> None:
    """Risk annotation: group=TG-6; named_risk=validator_public_policy_drift;
    level=particular-integration; source=proposals/02-public-application-intake.md#§6 AS-4.
    """
    validator = VALIDATOR.read_text(encoding="utf-8")

    assert "policies.json" in validator
    assert "service-identities.json" in validator
    assert "GitOps ConfigMap policy differs from policy repo" in validator
    assert "application:submit_public" not in validator
    assert "web-intake.local" not in validator
