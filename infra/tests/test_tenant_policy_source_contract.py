from __future__ import annotations

from infra.tests.fixtures.cedar_policy_source import (
    TENANT_VALIDATOR,
    bootstrap_job_name,
    canonical_policies,
    text,
)


def _has_permit(contents: str, principal: str, resource: str) -> bool:
    return (
        f'permit(principal == {principal}, '
        f'action == Action::"tenant:channel:access", resource == {resource});'
    ) in contents


def test_tenant_cedar_policies_preserve_allow_allow_deny_contract() -> None:
    """Risk annotation: group=TG-5; named_risk=tenant_policy_not_materialized_or_loaded;
    level=particular-integration; source=proposals/03-cedar-policy-source.md#test-intent-track T5;
    assumptions=A5.
    """
    contents = "\n".join(policy["content"] for policy in canonical_policies())

    assert _has_permit(contents, 'Tenant::"sample"', 'TenantChannel::"sample:local"')
    assert _has_permit(contents, 'Tenant::"sample"', 'TenantChannel::"sample:dev"')
    assert not _has_permit(contents, 'Tenant::"sample"', 'TenantChannel::"other:local"')


def test_tenant_validator_runs_cedar_probes_only_after_policy_id_gate() -> None:
    """Risk annotation: group=TG-5; named_risk=tenant_authorization_probe_before_hydration_gate;
    level=particular-integration; source=proposals/03-cedar-policy-source.md#contract C5.2;
    assumptions=A1,A2,A3,A5.
    """
    validator = text(TENANT_VALIDATOR)

    assert bootstrap_job_name() not in validator
    assert validator.find("/v1/policies") != -1
    assert validator.find("/v1/policies") < validator.find("/v1/is_authorized")
    assert 'Tenant::\\"sample\\"' in validator
    assert 'TenantChannel::\\"sample:local\\"' in validator
    assert 'TenantChannel::\\"sample:dev\\"' in validator
    assert 'TenantChannel::\\"other:local\\"' in validator
