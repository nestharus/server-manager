from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RESOLVER_PATH = REPO_ROOT / "infra" / "scripts" / "resolve_platform_channel.py"
_RESOLVER_MODULE = None


def load_resolver():
    global _RESOLVER_MODULE
    if _RESOLVER_MODULE is not None:
        return _RESOLVER_MODULE

    spec = importlib.util.spec_from_file_location("resolve_platform_channel", RESOLVER_PATH)
    if spec is None:
        raise FileNotFoundError(f"resolver module not found at {RESOLVER_PATH}")
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"resolver module has no loader: {RESOLVER_PATH}")
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _RESOLVER_MODULE = module
    return module


def test_local_auth_stack_contract() -> None:
    resolver = load_resolver()
    channel = resolver.resolve_channel("local")
    auth_stack = channel["auth_stack"]

    assert auth_stack["namespace"] == "auth-system"
    assert auth_stack["authentik"] == {
        "chart_name": "authentik/authentik",
        "chart_version": "2026.2.2",
        "image": "ghcr.io/goauthentik/server:2026.2.2",
        "host": "auth.local.humility.local",
        "database_cluster_name": "authentik-postgres",
        "database_name": "authentik",
        "database_owner": "authentik",
        "infisical_project": "platform-auth",
        "infisical_environment": "local",
        "infisical_path": "/auth/local/authentik",
    }
    assert auth_stack["pomerium"]["chart_version"] == "34.0.1"
    assert auth_stack["pomerium"]["authenticate_host"] == (
        "authenticate.local.humility.local"
    )
    assert auth_stack["pomerium"]["proxy_host"] == (
        "protected-api.local.humility.local"
    )
    assert auth_stack["opal_cedar"] == {
        "chart_name": "permitio/opal",
        "chart_version": "0.0.29",
        "server_image": "docker.io/permitio/opal-server:0.7.12",
        "client_image": "docker.io/permitio/opal-client-cedar:0.7.12",
        "proof_path": "/v1/is_authorized",
    }
    assert auth_stack["protected_api"] == {
        "host": "protected-api.local.humility.local",
        "backend_service": "server-manager-api",
        "backend_namespace": "server-manager",
        "backend_port": 8000,
        "proof_path": "/api/v1/protected/authz-proof",
    }
