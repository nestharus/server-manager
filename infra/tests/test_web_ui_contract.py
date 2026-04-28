from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    REPO_ROOT / "infra" / "tests" / "fixtures" / "contracts" / "web_ui_contract.yml"
)
POMERIUM_SECRET = (
    REPO_ROOT / "gitops" / "channels" / "local" / "auth" / "pomerium" / "secrets-infisicalsecret.yaml"
)
WEB_GITOPS_DIR = REPO_ROOT / "gitops" / "channels" / "local" / "applications" / "web"


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _pomerium_config() -> str:
    docs = [
        doc
        for doc in yaml.safe_load_all(POMERIUM_SECRET.read_text(encoding="utf-8"))
        if isinstance(doc, dict)
    ]
    return docs[0]["spec"]["managedSecretReference"]["template"]["data"]["config.yaml"]


def test_web_route_exposes_public_front_and_auth_gated_admin_path() -> None:
    """SLICE-R.22: web routing and auth gate replace dependency/version checks."""
    routes = _yaml(FIXTURE)["routes"]
    config = _pomerium_config()

    assert f"from: https://{routes['public_host']}" in config
    assert "allow_public_unauthenticated_access: true" in config
    assert f"prefix: {routes['admin_prefix']}" in config
    assert "pass_identity_headers: true" in config


def test_web_gitops_exposes_a_reachable_service_and_ingress_host() -> None:
    """SLICE-R.22: local ingress reachability must have deployable routing objects."""
    routes = _yaml(FIXTURE)["routes"]
    ingress = _yaml(WEB_GITOPS_DIR / "ingress.yaml")
    service = _yaml(WEB_GITOPS_DIR / "service.yaml")

    assert service["metadata"]["name"] == "server-manager-web"
    assert ingress["spec"]["rules"][0]["host"] == routes["public_host"]
    assert ingress["spec"]["rules"][0]["http"]["paths"][0]["backend"]["service"][
        "name"
    ] == service["metadata"]["name"]


def test_form_submit_contract_fixture_names_controls_and_method() -> None:
    """SLICE-R.22: form behavior is retained as a residual component contract."""
    form = _yaml(FIXTURE)["form"]

    assert form["route"] == "/applications"
    assert form["submit_method"] == "POST"
    assert {control["name"] for control in form["controls"]} == {
        "character_name",
        "application_text",
        "submit",
    }
