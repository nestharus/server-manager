from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    REPO_ROOT / "infra" / "tests" / "fixtures" / "contracts" / "auth_stack_contract.yml"
)
POMERIUM_SECRET = (
    REPO_ROOT / "gitops" / "channels" / "local" / "auth" / "pomerium" / "secrets-infisicalsecret.yaml"
)


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _pomerium_config() -> str:
    docs = [
        doc
        for doc in yaml.safe_load_all(POMERIUM_SECRET.read_text(encoding="utf-8"))
        if isinstance(doc, dict)
    ]
    return docs[0]["spec"]["managedSecretReference"]["template"]["data"]["config.yaml"]


def test_pomerium_protected_api_route_passes_identity_headers() -> None:
    """INIT-114 / SLICE-R.18: Pomerium route must protect API identity flow."""
    protected = _yaml(FIXTURE)["protected_api"]
    config = _pomerium_config()

    assert f"from: https://{protected['host']}" in config
    assert f"to: http://{protected['backend_service']}" in config
    assert "pass_identity_headers: true" in config


def test_authz_proof_status_contract_is_explicit() -> None:
    """INIT-114 proposal: protected API distinguishes 401, 403, 503, and allow."""
    statuses = _yaml(FIXTURE)["cedar_statuses"]

    assert statuses == {
        "missing_identity": 401,
        "denied_identity": 403,
        "policy_engine_unavailable": 503,
        "allowed_identity": 200,
    }
