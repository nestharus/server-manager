from __future__ import annotations

import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    REPO_ROOT / "infra" / "tests" / "fixtures" / "contracts" / "access_policy_matrix.yml"
)
POLICY_DIR = (
    REPO_ROOT
    / "policy"
    / "cedar"
    / "channels"
    / "local"
    / "services"
    / "server-manager-api"
)
OPAL_CONFIG_MAP = (
    REPO_ROOT
    / "gitops"
    / "channels"
    / "local"
    / "auth"
    / "opal-cedar"
    / "access-policy-configmap.yaml"
)


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _policies() -> list[dict]:
    return json.loads((POLICY_DIR / "policies.json").read_text(encoding="utf-8"))


def _permits(policies: list[dict], principal: str, action: str, resource: str) -> bool:
    needles = [f"principal == {principal}", f"action == {action}", f"resource == {resource}"]
    return any(all(needle in policy.get("content", "") for needle in needles) for policy in policies)


def test_cedar_policy_decisions_match_the_contract_matrix() -> None:
    """INIT-115 / SLICE-R.19: assert allow/deny behavior, not policy-id literals."""
    fixture = _yaml(FIXTURE)
    policies = _policies()

    for case in fixture["decisions"]:
        permitted = _permits(
            policies,
            principal=case["principal"],
            action=case["action"],
            resource=case["resource"],
        )
        assert permitted is (case["effect"] == "allow"), case


def test_opal_bundle_loads_parseable_policy_without_token_material() -> None:
    """INIT-115 handoff: bundle load is required and committed tokens are forbidden."""
    fixture = _yaml(FIXTURE)
    config_map = _yaml(OPAL_CONFIG_MAP)
    bundle_policies = json.loads(config_map["data"]["policies.json"])
    service_identities = (POLICY_DIR / "service-identities.json").read_text(
        encoding="utf-8"
    )
    combined = json.dumps(bundle_policies) + service_identities

    assert bundle_policies
    assert all("content" in policy for policy in bundle_policies)
    for forbidden in fixture["token_safety"]["forbidden_substrings"]:
        assert forbidden not in combined
