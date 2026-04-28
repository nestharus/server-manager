from __future__ import annotations

import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    REPO_ROOT / "infra" / "tests" / "fixtures" / "contracts" / "observability_contract.yml"
)
OBS_DIR = REPO_ROOT / "gitops" / "channels" / "local" / "observability"


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

    assert dashboards
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
