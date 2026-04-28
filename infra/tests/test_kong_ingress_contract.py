from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    REPO_ROOT / "infra" / "tests" / "fixtures" / "contracts" / "kong_ingress_contract.yml"
)
MINIO_INGRESS = (
    REPO_ROOT
    / "gitops"
    / "channels"
    / "local"
    / "ingress"
    / "default-services"
    / "minio"
    / "ingress.yaml"
)
MINIO_ALIAS = MINIO_INGRESS.with_name("alias-service.yaml")


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _contract() -> dict:
    return _yaml(FIXTURE)["local_route"]


def test_minio_ingress_routes_intended_host_to_backend_health_path() -> None:
    """INIT-110 / SLICE-R.14: route, host, and backend health are behavior."""
    expected = _contract()
    ingress = _yaml(MINIO_INGRESS)
    rule = ingress["spec"]["rules"][0]
    path = rule["http"]["paths"][0]

    assert ingress["spec"]["ingressClassName"] == expected["ingress_class"]
    assert rule["host"] == expected["host"]
    assert expected["proof_path"].startswith(path["path"])
    assert path["pathType"] == "Prefix"
    assert path["backend"]["service"] == {
        "name": expected["backend_service"],
        "port": {"number": expected["backend_port"]},
    }


def test_minio_ingress_declares_tls_certificate_for_the_route_host() -> None:
    """INIT-110 handoff: TLS readiness is required for the sample route."""
    expected = _contract()
    ingress = _yaml(MINIO_INGRESS)

    assert ingress["spec"]["tls"] == [
        {"hosts": [expected["host"]], "secretName": expected["tls_secret"]}
    ]


def test_local_dns_alias_targets_the_kong_proxy_service() -> None:
    """INIT-110 architecture: local aliases preserve Host routing through Kong."""
    expected = _contract()
    alias = _yaml(MINIO_ALIAS)

    assert alias["metadata"]["namespace"] == expected["alias_namespace"]
    assert alias["spec"]["externalName"] == expected["proxy_service_dns"]
