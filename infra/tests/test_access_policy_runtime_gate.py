from __future__ import annotations

from infra.tests.fixtures.cedar_policy_source import (
    ACCESS_POLICY_VALIDATOR,
    AUTH_STACK_VALIDATOR,
    SERVICE_IDENTITY_VALIDATOR,
    TENANT_VALIDATOR,
    bootstrap_job_name,
    canonical_policy_ids,
    has_wait_longer_than_polling_interval,
    text,
)


def test_access_policy_validator_waits_for_canonical_policy_ids_not_bootstrap_job() -> None:
    """Risk annotation: group=TG-3; named_risk=ready_opal_client_empty_cedar_store;
    level=end-to-end; source=planning/proposals/03-cedar-policy-source.md#test-intent-track T3;
    assumptions=A1,A2,A3.
    """
    validator = text(ACCESS_POLICY_VALIDATOR)

    assert bootstrap_job_name() not in validator
    assert "rollout status deployment/opal-client --timeout=180s" in validator
    assert "http://opal-client:8180/v1/policies" in validator
    assert "120" in validator
    assert "missing" in validator.lower()
    assert "policy IDs" in validator or "policy ids" in validator.lower()
    for policy_id in canonical_policy_ids():
        assert policy_id not in validator, "validator must derive canonical IDs from policies.json"


def test_all_runtime_validators_use_policy_id_gate_before_authorization_probes() -> None:
    """Risk annotation: group=TG-3; named_risk=bootstrap_completion_retained_as_hydration_gate;
    level=end-to-end; source=planning/proposals/03-cedar-policy-source.md#contract C5.1,C5.2,C5.6;
    assumptions=A1,A2,A3.
    """
    for script in (
        ACCESS_POLICY_VALIDATOR,
        TENANT_VALIDATOR,
        AUTH_STACK_VALIDATOR,
        SERVICE_IDENTITY_VALIDATOR,
    ):
        body = text(script)
        assert bootstrap_job_name() not in body, script
        policy_probe = body.find("/v1/policies")
        auth_probe = body.find("/v1/is_authorized")
        assert policy_probe != -1, script
        if auth_probe != -1:
            assert policy_probe < auth_probe, script


def test_access_policy_validator_rechecks_hydration_after_one_polling_interval() -> None:
    """Risk annotation: group=TG-7; named_risk=opal_polling_cycle_erases_cedar_policies;
    level=end-to-end; source=planning/proposals/03-cedar-policy-source.md#test-intent-track T7;
    assumptions=A1,A2.
    """
    validator = text(ACCESS_POLICY_VALIDATOR)

    assert has_wait_longer_than_polling_interval(validator)
    assert validator.count("/v1/policies") >= 2
    assert validator.count("/v1/is_authorized") >= 2
