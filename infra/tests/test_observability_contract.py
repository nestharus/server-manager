from __future__ import annotations

import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    REPO_ROOT / "infra" / "tests" / "fixtures" / "contracts" / "observability_contract.yml"
)
OBS_DIR = REPO_ROOT / "gitops" / "channels" / "local" / "observability"
VALIDATOR = REPO_ROOT / "infra" / "tests" / "validate_observability_local.sh"
E2E_OBSERVABILITY = REPO_ROOT / "infra" / "tests" / "e2e" / "tests" / "18-observability.sh"


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _yaml_docs(path: Path) -> list[dict]:
    return [
        doc
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if isinstance(doc, dict)
    ]


def test_service_monitors_discover_required_platform_targets_without_order_snapshot() -> None:
    """SLICE-R.21: scrape target discoverability replaces ordered snapshots."""
    expected = set(_yaml(FIXTURE)["scrape_targets"])
    docs = _yaml_docs(OBS_DIR / "service-monitors" / "service-monitors.yaml")
    names = {
        doc["metadata"]["name"]
        for doc in docs
        if doc.get("kind") == "ServiceMonitor"
    }

    assert expected <= names


def test_dashboards_are_provisioned_with_tenant_filtering() -> None:
    """SLICE-R.21 / INIT-116 handoff: dashboards must be tenant-aware."""
    expected = _yaml(FIXTURE)["dashboards"]
    config = _yaml(OBS_DIR / "dashboards" / "grafana-dashboards.yaml")
    dashboards = [json.loads(payload) for payload in config["data"].values()]
    dashboard_uids = {dashboard["uid"] for dashboard in dashboards}

    assert dashboards
    assert set(expected["required_uids"]) <= dashboard_uids
    for dashboard in dashboards:
        variables = dashboard["templating"]["list"]
        assert any(
            variable["name"] == expected["required_tenant_variable"]
            for variable in variables
        )


def test_sample_alerts_are_ingestable_by_prometheus_rules() -> None:
    """SLICE-R.21: sample alert ingestion is behavior; rule order is not."""
    expected = set(_yaml(FIXTURE)["sample_alerts"])
    config = _yaml(OBS_DIR / "prometheus" / "rules-configmap.yaml")
    rules = yaml.safe_load(config["data"]["alerts.yml"])
    alert_names = {
        rule["alert"]
        for group in rules["groups"]
        for rule in group["rules"]
    }

    assert expected <= alert_names


def test_sample_log_query_contract_is_explicit() -> None:
    """SLICE-R.21: log-query behavior is retained as a residual runtime contract."""
    sample_log_query = _yaml(FIXTURE)["sample_log_query"]

    assert sample_log_query["selector"] == '{namespace="server-manager"}'
    assert sample_log_query["contains"] == "server-manager-api"


def test_runtime_probe_fixtures_live_outside_validator_bodies() -> None:
    """SLICE-R.21 fixture source: target query, dashboard, alert, and log proofs."""
    contract = _yaml(FIXTURE)
    validator = VALIDATOR.read_text(encoding="utf-8")
    e2e = E2E_OBSERVABILITY.read_text(encoding="utf-8")

    assert contract["prometheus_target_query"]["endpoint"] == "/api/v1/targets"
    assert contract["prometheus_target_query"]["require_active_targets"] is True
    assert contract["prometheus_target_query"]["require_all_up"] is True

    dashboard = contract["dashboard_provisioning"]
    assert dashboard["configmap"] == "grafana-dashboards"
    assert {"flux-gitops-health.json", "cnpg.json"} <= set(dashboard["required_files"])

    sample_alert = contract["sample_alert"]
    assert sample_alert["alertname"] == "Init117SampleAlert"
    assert sample_alert["labels"]["tenant"] == "platform"

    sample_log = contract["sample_log"]
    assert sample_log["stream"]["job"] == "init-117-proof"
    assert sample_log["message"] in sample_log["query"]

    assert str(FIXTURE.relative_to(REPO_ROOT)) in validator
    assert "validate_observability_local.sh" in e2e
    assert "--static-only" not in e2e


def test_observability_networkpolicies_do_not_isolate_operator_webhooks() -> None:
    """SLICE-R.21 must not recreate the INIT-117 webhook-isolating policy shape."""
    guard = _yaml(FIXTURE)["webhook_isolation_guard"]
    forbidden_source = guard["forbidden_source_namespace"]
    forbidden_namespaces = set(guard["webhook_namespaces"])
    offending: list[str] = []

    for path in sorted(OBS_DIR.glob("**/*.yaml")):
        for doc in _yaml_docs(path):
            if doc.get("kind") != "NetworkPolicy":
                continue
            metadata = doc.get("metadata", {})
            namespace = metadata.get("namespace")
            if namespace not in forbidden_namespaces:
                continue

            spec = doc.get("spec", {})
            if spec.get("podSelector") != {} or "Ingress" not in spec.get("policyTypes", []):
                continue

            ingress = spec.get("ingress", [])
            from_rules = [
                source
                for rule in ingress
                for source in rule.get("from", [])
            ]
            source_namespaces = {
                source.get("namespaceSelector", {})
                .get("matchLabels", {})
                .get("kubernetes.io/metadata.name")
                for source in from_rules
            }
            if source_namespaces == {forbidden_source}:
                offending.append(
                    f"{path.relative_to(REPO_ROOT)}:{namespace}/{metadata.get('name')}"
                )

    assert offending == []
