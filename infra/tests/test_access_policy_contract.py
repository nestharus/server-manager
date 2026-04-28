from __future__ import annotations

import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    REPO_ROOT / "infra" / "tests" / "fixtures" / "contracts" / "access_policy_matrix.yml"
)


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _fixture() -> dict:
    return _yaml(FIXTURE)


def _repo_path(relative_path: str) -> Path:
    path = REPO_ROOT / relative_path
    assert path.is_file(), f"missing access-policy contract path: {relative_path}"
    return path


def _policies(fixture: dict) -> list[dict]:
    return json.loads(
        _repo_path(fixture["bundle"]["policy_file"]).read_text(encoding="utf-8")
    )


def _service_identities(fixture: dict) -> dict:
    return json.loads(
        _repo_path(fixture["bundle"]["service_identity_file"]).read_text(
            encoding="utf-8"
        )
    )


def _opal_bundle_policies(fixture: dict) -> list[dict]:
    config_map = _yaml(_repo_path(fixture["bundle"]["gitops_configmap"]))
    return json.loads(config_map["data"]["policies.json"])


def _permits(policies: list[dict], principal: str, action: str, resource: str) -> bool:
    needles = [f"principal == {principal}", f"action == {action}", f"resource == {resource}"]
    return any(all(needle in policy.get("content", "") for needle in needles) for policy in policies)


def test_cedar_policy_decisions_match_the_contract_matrix() -> None:
    """INIT-115 / SLICE-R.19: assert allow/deny behavior, not policy-id literals."""
    fixture = _fixture()
    policies = _policies(fixture)

    for case in fixture["decisions"]:
        permitted = _permits(
            policies,
            principal=case["principal"],
            action=case["action"],
            resource=case["resource"],
        )
        assert permitted is (case["effect"] == "allow"), case


def test_gitops_bundle_loads_the_contract_policy_set() -> None:
    """INIT-115 handoff: OPAL bundle must load the same policy set as the repo."""
    fixture = _fixture()
    repo_policies = _policies(fixture)
    bundle_policies = _opal_bundle_policies(fixture)

    assert bundle_policies
    assert all("content" in policy for policy in bundle_policies)
    assert sorted(bundle_policies, key=lambda policy: policy["id"]) == sorted(
        repo_policies,
        key=lambda policy: policy["id"],
    )


def test_service_identities_cover_machine_principals_in_the_matrix() -> None:
    """INIT-115 proposal: Buildkite and Crossplane map to Cedar Service principals."""
    fixture = _fixture()
    service_identities = _service_identities(fixture)
    principals = {
        identity["cedar_principal"]
        for identity in service_identities["identities"].values()
    }

    for expected in fixture["required_service_identities"].values():
        assert expected in principals


def test_bundle_fixtures_do_not_commit_operator_secret_material() -> None:
    """INIT-115 anti-scope: no committed credential material in policy fixtures."""
    fixture = _fixture()
    bundle_policies = _opal_bundle_policies(fixture)
    service_identities = _repo_path(
        fixture["bundle"]["service_identity_file"]
    ).read_text(encoding="utf-8")
    combined = json.dumps(bundle_policies) + service_identities

    for forbidden in fixture["token_safety"]["forbidden_substrings"]:
        assert forbidden not in combined
