from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from infra.tests._messages import SEEDED_POLICY_SOURCE_MISMATCH


REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX = REPO_ROOT / "infra" / "tests" / "fixtures" / "contracts" / "access_policy_matrix.yml"
VALIDATOR = REPO_ROOT / "infra" / "tests" / "validate_access_policy_local.sh"

PUBLIC_PRINCIPAL = 'Public::"web-intake.local"'
PUBLIC_SUBMIT_ACTION = 'Action::"application:submit_public"'
API_READ_ACTION = 'Action::"api:read"'
PUBLIC_RESOURCE = 'Resource::"server-manager-api:public-applications"'
API_RESOURCE = 'Resource::"server-manager-api"'

PAYLOAD_PATTERN = re.compile(
    r"""^[A-Za-z_][A-Za-z0-9_]*="\$\(jq\s+-nc\s+'(\{[^']+\})'\)"$""",
    re.MULTILINE,
)
JQ_OBJECT_KEY_PATTERN = re.compile(r"([,{]\s*)(principal|action|resource):")


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


def _validator_payloads(validator: str) -> list[dict]:
    payloads = []
    matches = PAYLOAD_PATTERN.findall(validator)
    assert matches, "expected at least one jq -nc payload assignment in validator"

    for source in matches:
        json_source = JQ_OBJECT_KEY_PATTERN.sub(r'\1"\2":', source)
        try:
            payloads.append(json.loads(json_source))
        except json.JSONDecodeError as exc:
            raise AssertionError(f"validator jq payload did not parse as JSON: {source}") from exc

    return payloads


def test_access_policy_matrix_contains_public_submit_allow_and_read_deny() -> None:
    """Risk annotation: group=TG-6; named_risk=public_policy_fixture_gap;
    level=particular-integration; source=planning/proposals/03-cedar-policy-source.md#test-intent-track T6;
    assumptions=A5.
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
    level=particular-integration; source=planning/proposals/03-cedar-policy-source.md#test-intent-track T6;
    assumptions=A5.
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
    level=particular-integration; source=planning/proposals/03-cedar-policy-source.md#test-intent-track T6;
    assumptions=A5.
    """
    fixture = _yaml(MATRIX)
    identities = _service_identities(fixture)
    serialized = json.dumps(identities, sort_keys=True)

    assert "web-intake" not in serialized
    assert "public-intake" not in serialized
    assert "application:submit_public" not in serialized
    assert "Public::" not in serialized


def test_access_policy_validator_uses_canonical_seeded_policy_source() -> None:
    """Risk annotation: group=TG-6; named_risk=validator_public_policy_drift;
    level=particular-integration; source=planning/proposals/03-cedar-policy-source.md#contract C5.3,C5.5;
    assumptions=A5.
    """
    validator = VALIDATOR.read_text(encoding="utf-8")

    assert "policies.json" in validator
    assert "service-identities.json" in validator
    assert SEEDED_POLICY_SOURCE_MISMATCH in validator
    assert "GitOps ConfigMap policy differs from policy repo" not in validator


def test_access_policy_validator_contains_public_runtime_probe_payloads() -> None:
    """Risk annotation: group=TG-2; named_risk=validator_public_runtime_probe_drift;
    level=particular-integration; source=planning/proposals/29-bl-012-public-entity-runtime-probe.md;
    assumptions=A8.
    """
    validator = VALIDATOR.read_text(encoding="utf-8")
    triples = {
        (payload.get("principal"), payload.get("action"), payload.get("resource"))
        for payload in _validator_payloads(validator)
    }

    assert (PUBLIC_PRINCIPAL, PUBLIC_SUBMIT_ACTION, PUBLIC_RESOURCE) in triples
    assert (PUBLIC_PRINCIPAL, API_READ_ACTION, API_RESOURCE) in triples


def test_access_policy_validator_die_messages_name_resource_literal() -> None:
    """Risk annotation: group=TG-2; named_risk=validator_public_runtime_probe_drift;
    level=particular-integration; source=planning/proposals/29-bl-012-public-entity-runtime-probe.md;
    assumptions=A8.
    """
    validator = VALIDATOR.read_text(encoding="utf-8")

    assert (
        'Cedar public submit runtime probe expected Allow for '
        'Public::\\"web-intake.local\\" application:submit_public '
        'on Resource::\\"server-manager-api:public-applications\\"'
    ) in validator
    assert (
        'Cedar public read runtime probe expected Deny for '
        'Public::\\"web-intake.local\\" api:read '
        'on Resource::\\"server-manager-api\\"'
    ) in validator


def test_access_policy_validator_decision_checks_wired_for_public_probes() -> None:
    """Risk annotation: group=TG-2; named_risk=validator_public_runtime_probe_drift;
    level=particular-integration; source=planning/proposals/29-bl-012-public-entity-runtime-probe.md;
    assumptions=A8.
    """
    validator = VALIDATOR.read_text(encoding="utf-8")

    public_decision_checks = [
        r"""jq\s+-e\s+'\.decision == "Allow"'\s+<<<"\$\{[^}]+#public_submit=\}""",
        r"""jq\s+-e\s+'\.decision == "Deny"'\s+<<<"\$\{[^}]+#public_read=\}""",
        r"""jq\s+-e\s+'\.decision == "Allow"'\s+<<<"\$\{[^}]+#public_submit_after_poll=\}""",
        r"""jq\s+-e\s+'\.decision == "Deny"'\s+<<<"\$\{[^}]+#public_read_after_poll=\}""",
    ]

    for pattern in public_decision_checks:
        assert re.search(pattern, validator), f"missing public decision check: {pattern}"
