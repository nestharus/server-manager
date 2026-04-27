from __future__ import annotations


pytest_plugins = ["infra.tests.fixtures.operator_webhooks"]

NAMESPACE = "crossplane-system"


def test_crossplane_system_webhook_reachable_from_apiserver(admission_dry_run):
    """Risk: webhook-unreachable-blocks-CRD-apply; level: particular-integration."""
    result = admission_dry_run(NAMESPACE)

    assert result.returncode == 0, result.diagnostic


def test_crossplane_system_webhook_reachable_from_same_namespace_pod(
    probe_pod,
    webhook_endpoint,
):
    """Risk: webhook-isolated-from-namespace-traffic; level: particular-integration."""
    endpoint = webhook_endpoint(NAMESPACE)

    result = probe_pod(
        NAMESPACE,
        [endpoint.service_probe_url, endpoint.direct_pod_probe_url],
    )

    assert result.all_reached, result.diagnostic


def test_crossplane_system_webhook_observability_scrape_preserved(
    observability_scrape,
):
    """Risk: observability-scrape-regressed; level: particular-integration."""
    result = observability_scrape(NAMESPACE)

    assert result.reached, result.diagnostic


def test_crossplane_system_webhook_unintended_access_denied(
    denied_probe_namespace,
    probe_pod,
    webhook_endpoint,
):
    """Risk: unintended-namespace-access; level: particular-integration."""
    endpoint = webhook_endpoint(NAMESPACE)

    result = probe_pod(
        denied_probe_namespace,
        [endpoint.service_probe_url, endpoint.direct_pod_probe_url],
    )

    assert result.all_denied, result.diagnostic
