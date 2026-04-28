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
    return _yaml(FIXTURE)


def test_minio_ingress_routes_intended_host_to_backend_health_path() -> None:
    """INIT-110 / SLICE-R.14: route, host, and backend health are behavior."""
    expected = _contract()
    route = expected["local_route"]
    health = expected["backend_health"]
    ingress = _yaml(MINIO_INGRESS)
    rule = ingress["spec"]["rules"][0]
    path = rule["http"]["paths"][0]

    assert ingress["metadata"]["name"] == route["ingress_name"]
    assert ingress["metadata"]["namespace"] == route["ingress_namespace"]
    assert ingress["spec"]["ingressClassName"] == route["ingress_class"]
    assert rule["host"] == route["host"]
    assert health["proof_path"].startswith(path["path"])
    assert path["pathType"] == "Prefix"
    assert path["backend"]["service"] == {
        "name": health["backend_service"],
        "port": {"number": health["backend_port"]},
    }


def test_minio_ingress_declares_certificate_contract_for_the_route_host() -> None:
    """INIT-110 handoff: cert-manager TLS readiness is required."""
    expected = _contract()
    route = expected["local_route"]
    certificate = expected["certificate"]
    ingress = _yaml(MINIO_INGRESS)

    annotations = ingress["metadata"]["annotations"]
    for key, value in certificate["annotations"].items():
        assert annotations[key] == value
    assert ingress["spec"]["tls"] == [
        {"hosts": [route["host"]], "secretName": certificate["tls_secret"]}
    ]


def test_local_dns_alias_targets_the_kong_proxy_service() -> None:
    """INIT-110 architecture: local aliases preserve Host routing through Kong."""
    expected = _contract()
    dns = expected["local_dns"]
    alias = _yaml(MINIO_ALIAS)

    assert alias["metadata"]["namespace"] == dns["alias_namespace"]
    assert alias["spec"]["type"] == "ExternalName"
    assert alias["spec"]["externalName"] == dns["proxy_service_dns"]
