from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "services/web"
WEB_GITOPS_DIR = REPO_ROOT / "gitops/channels/local/applications/web"
POMERIUM_SECRET = REPO_ROOT / "gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml"


def test_web_package_locks_solid_2_and_frontend_stack() -> None:
    package = json.loads((WEB_DIR / "package.json").read_text(encoding="utf-8"))
    deps = package["dependencies"] | package["devDependencies"]

    assert deps["solid-js"] == "2.0.0-beta.8"
    assert deps["@solidjs/web"] == "2.0.0-beta.8"
    assert deps["vite-plugin-solid"] == "3.0.0-next.5"
    assert deps["@tanstack/solid-router"] == "1.168.25"
    assert deps["@tanstack/solid-query"] == "5.100.5"
    assert deps["@tanstack/solid-form"] == "1.29.1"
    assert deps["@tanstack/solid-table"] == "8.21.3"
    assert deps["@ark-ui/solid"] == "5.36.2"
    assert deps["@typescript/native-preview"] == "7.0.0-dev.20260427.1"


def test_web_uses_vanilla_css_layers_and_no_forbidden_styling_dependency() -> None:
    package_text = (WEB_DIR / "package.json").read_text(encoding="utf-8")
    css = (WEB_DIR / "src/styles/layers.css").read_text(encoding="utf-8")

    assert "@layer reset, tokens, theme, base, components, utilities, overrides;" in css
    assert "oklch(" in css
    for forbidden in ("tailwind", "panda", "styled-components", "@emotion"):
        assert forbidden not in package_text


def test_web_kustomize_renders_raw_manifests_without_helmrelease() -> None:
    result = subprocess.run(
        ["kubectl", "kustomize", str(WEB_GITOPS_DIR)],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "kind: HelmRelease" not in result.stdout
    assert "name: server-manager-web" in result.stdout
    assert "namespace: web" in result.stdout


def test_pomerium_routes_front_public_and_admin_web_paths() -> None:
    docs = [
        doc
        for doc in yaml.safe_load_all(POMERIUM_SECRET.read_text(encoding="utf-8"))
        if isinstance(doc, dict)
    ]
    config = docs[0]["spec"]["managedSecretReference"]["template"]["data"]["config.yaml"]

    assert "from: https://web.local.humility.local" in config
    assert "allow_public_unauthenticated_access: true" in config
    assert "prefix: /admin" in config
    assert "pass_identity_headers: true" in config
