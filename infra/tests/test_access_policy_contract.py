from __future__ import annotations

import json
import tempfile
from pathlib import Path

import yaml

from infra.tests.fixtures.cedar_policy_source import (
    canonical_policy_map,
    generated_policy_map,
    render_snapshot,
)


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


def _seeded_policy_files(fixture: dict) -> dict[str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp) / "gitops-source"
        render_snapshot(snapshot)
        return generated_policy_map(snapshot, fixture)


def _permits(policies: list[dict], principal: str, action: str, resource: str) -> bool:
    needles = [f"principal == {principal}", f"action == {action}", f"resource == {resource}"]
    return any(
        policy.get("content", "").lstrip().startswith("permit(")
        and all(needle in policy.get("content", "") for needle in needles)
        for policy in policies
    )


def test_cedar_policy_decisions_match_the_contract_matrix() -> None:
    """Risk annotation: group=TG-4; named_risk=access_policy_decision_contract_drift;
    level=particular-integration; source=planning/proposals/03-cedar-policy-source.md#test-intent-track T4;
    assumptions=A5.
    """
    fixture = _fixture()
    policies = _policies(fixture)
    required_cases = {
        (
            'User::"sample@local.humility.local"',
            'Action::"api:read"',
            'Resource::"server-manager-api"',
            "allow",
        ),
        (
            'User::"other@local.humility.local"',
            'Action::"api:read"',
            'Resource::"server-manager-api"',
            "deny",
        ),
        (
            'Service::"buildkite-agent.local"',
            'Action::"api:ci:deploy"',
            'Resource::"server-manager-api"',
            "allow",
        ),
        (
            'Service::"buildkite-agent.local"',
            'Action::"api:read"',
            'Resource::"server-manager-api"',
            "deny",
        ),
    }
    matrix_cases = {
        (case["principal"], case["action"], case["resource"], case["effect"])
        for case in fixture["decisions"]
    }

    assert required_cases <= matrix_cases
    for case in fixture["decisions"]:
        permitted = _permits(
            policies,
            principal=case["principal"],
            action=case["action"],
            resource=case["resource"],
        )
        assert permitted is (case["effect"] == "allow"), case


def test_seeded_policy_files_load_the_contract_policy_set() -> None:
    """Risk annotation: group=TG-4; named_risk=generated_seeded_bundle_differs_from_contract;
    level=particular-integration; source=planning/proposals/03-cedar-policy-source.md#contract C5.4;
    assumptions=A3,A5.
    """
    fixture = _fixture()
    seeded_policies = _seeded_policy_files(fixture)

    assert seeded_policies == canonical_policy_map()


def test_service_identities_cover_machine_principals_in_the_matrix() -> None:
    """Risk annotation: group=TG-4; named_risk=service_identity_matrix_principals_missing;
    level=particular-integration; source=planning/proposals/03-cedar-policy-source.md#test-intent-track T4;
    assumptions=A5.
    """
    fixture = _fixture()
    service_identities = _service_identities(fixture)
    principals = {
        identity["cedar_principal"]
        for identity in service_identities["identities"].values()
    }

    for expected in fixture["required_service_identities"].values():
        assert expected in principals


def test_bundle_fixtures_do_not_commit_operator_secret_material() -> None:
    """Risk annotation: group=TG-4; named_risk=operator_secret_material_in_seeded_policy_fixture;
    level=particular-integration; source=planning/proposals/03-cedar-policy-source.md#contract C5.4;
    assumptions=A5.
    """
    fixture = _fixture()
    bundle_policies = _seeded_policy_files(fixture)
    service_identities = _repo_path(
        fixture["bundle"]["service_identity_file"]
    ).read_text(encoding="utf-8")
    combined = json.dumps(bundle_policies, sort_keys=True) + service_identities

    for forbidden in fixture["token_safety"]["forbidden_substrings"]:
        assert forbidden not in combined


def test_access_policy_matrix_uses_seeded_policy_file_bundle_reference() -> None:
    """Risk annotation: group=TG-4; named_risk=matrix_fixture_retains_deleted_configmap_bundle;
    level=particular-integration; source=planning/proposals/03-cedar-policy-source.md#contract C5.5;
    assumptions=A5.
    """
    fixture = _fixture()

    assert "seeded_policy_files" in fixture["bundle"]
    assert "gitops_configmap" not in fixture["bundle"]
