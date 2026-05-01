from __future__ import annotations

from pathlib import Path
from typing import Any

import json
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
GITOPS_ROOT = REPO_ROOT / "gitops"
CEDAR_ROOT = REPO_ROOT / "policy" / "cedar"

PLUGIN_NAME = "public-intake-rate-limit"
PUBLIC_TRIGGER_PATHS = {
    "/api/v1/public/applications",
    "/api/v1/public/chapters",
    "/api/public/applications",
    "/api/public/chapters",
    "/api/applications",
}
PUBLIC_TRIGGER_NAMES = {
    "server-manager-public-intake-api",
    "web-public-intake",
    "public-intake-rate-limit",
}
API_PUBLIC_PATHS = {"/api/v1/public/applications", "/api/v1/public/chapters"}
WEB_PUBLIC_PATHS = {
    "/api/public/applications",
    "/api/public/chapters",
    "/api/applications",
}
WEB_UPSTREAM = "http://server-manager-web.web.svc.cluster.local:8080"


def _failure(channel: str, kind: str, item: str, detail: str | None = None) -> str:
    suffix = f"{kind} {item}" if detail is None else f"{kind} {item}: {detail}"
    return f"public-intake channel tripwire failed for {channel}: {suffix}"


def _yaml_documents(path: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if isinstance(document, dict):
            docs.append(document)
    return docs


def _yaml_documents_for_trigger(path: Path) -> list[dict[str, Any]]:
    try:
        return _yaml_documents(path)
    except yaml.YAMLError:
        return []


def _metadata(resource: dict[str, Any]) -> dict[str, Any]:
    return resource.get("metadata", {}) or {}


def _annotations(resource: dict[str, Any]) -> dict[str, str]:
    return _metadata(resource).get("annotations", {}) or {}


def _resource_named(
    docs: list[dict[str, Any]], kind: str, name: str, namespace: str | None = None
) -> dict[str, Any] | None:
    for document in docs:
        metadata = _metadata(document)
        if document.get("kind") != kind or metadata.get("name") != name:
            continue
        if namespace is not None and metadata.get("namespace") != namespace:
            continue
        return document
    return None


def _iter_ingress_paths(resource: dict[str, Any]) -> list[tuple[str | None, dict[str, Any]]]:
    paths: list[tuple[str | None, dict[str, Any]]] = []
    for rule in resource.get("spec", {}).get("rules", []) or []:
        for path in rule.get("http", {}).get("paths", []) or []:
            paths.append((rule.get("host"), path))
    return paths


def _kustomization_entries(resource: dict[str, Any]) -> list[str]:
    entries: list[str] = []
    for key in ("resources", "bases", "components"):
        values = resource.get(key, []) or []
        if isinstance(values, list):
            entries.extend(value for value in values if isinstance(value, str))
    return entries


def _is_public_intake_relevant(app_dir: Path) -> bool:
    if not app_dir.is_dir():
        return False

    for path in sorted(app_dir.glob("*.y*ml")):
        docs = _yaml_documents_for_trigger(path)
        if path.name == "public-intake-rate-limit.yaml" and docs:
            return True
        for document in docs:
            metadata = _metadata(document)
            if metadata.get("name") in PUBLIC_TRIGGER_NAMES:
                return True
            if document.get("kind") == "Ingress":
                paths = {path_item.get("path") for _, path_item in _iter_ingress_paths(document)}
                if paths & PUBLIC_TRIGGER_PATHS:
                    return True
            if document.get("kind") == "Kustomization" and (
                "public-intake-rate-limit.yaml" in _kustomization_entries(document)
            ):
                return True
    return False


def discover_channels(gitops_root: Path = GITOPS_ROOT) -> list[str]:
    channels_root = gitops_root / "channels"
    if not channels_root.is_dir():
        return []

    channels: list[str] = []
    for channel_dir in sorted(path for path in channels_root.iterdir() if path.is_dir()):
        if channel_dir.name == "local":
            continue
        app_dir = channel_dir / "applications" / "server-manager"
        if _is_public_intake_relevant(app_dir):
            channels.append(channel_dir.name)
    return channels


def _read_yaml_item(
    channel: str, path: Path, item: str, failures: list[str]
) -> list[dict[str, Any]] | None:
    if not path.is_file():
        failures.append(_failure(channel, "missing", item))
        return None
    try:
        return _yaml_documents(path)
    except yaml.YAMLError as exc:
        failures.append(_failure(channel, "invalid", item, str(exc).splitlines()[0]))
        return None


def _read_json_item(
    channel: str, path: Path, item: str, failures: list[str]
) -> Any | None:
    if not path.is_file():
        failures.append(_failure(channel, "missing", item))
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append(_failure(channel, "invalid", item, str(exc)))
        return None


def _expected_backend(path_item: dict[str, Any], service_name: str, port: int) -> bool:
    service = path_item.get("backend", {}).get("service", {}) or {}
    return service.get("name") == service_name and service.get("port", {}).get("number") == port


def _validate_ingress_paths(
    channel: str,
    ingress: dict[str, Any],
    item: str,
    expected_host: str,
    expected_paths: set[str],
    service_name: str,
    port: int,
    failures: list[str],
) -> None:
    if _annotations(ingress).get("konghq.com/plugins") != PLUGIN_NAME:
        failures.append(_failure(channel, "invalid", item, "missing kong plugin annotation"))

    seen: set[str] = set()
    observed_hosts: set[str] = set()
    for host, path_item in _iter_ingress_paths(ingress):
        observed_hosts.add(host or "<missing>")
        path = path_item.get("path")
        if path not in expected_paths:
            continue
        if host != expected_host:
            failures.append(_failure(channel, "invalid", item, f"host {host} is not {expected_host}"))
            continue
        if path_item.get("pathType") != "Prefix":
            failures.append(_failure(channel, "invalid", item, f"path {path} is not Prefix"))
            continue
        if not _expected_backend(path_item, service_name, port):
            failures.append(
                _failure(channel, "invalid", item, f"path {path} does not route to {service_name}:{port}")
            )
            continue
        seen.add(path)

    missing = expected_paths - seen
    if missing:
        host_detail = f" on hosts {sorted(observed_hosts)}" if observed_hosts else ""
        failures.append(_failure(channel, "invalid", item, f"missing paths {sorted(missing)}{host_detail}"))


def _validate_api_rate_limit(channel: str, gitops_root: Path, failures: list[str]) -> None:
    path = (
        gitops_root
        / "channels"
        / channel
        / "applications"
        / "server-manager"
        / "public-intake-rate-limit.yaml"
    )
    docs = _read_yaml_item(channel, path, "api-rate-limit-yaml", failures)
    if docs is None:
        return

    plugin = _resource_named(docs, "KongPlugin", PLUGIN_NAME, "server-manager")
    if plugin is None:
        failures.append(_failure(channel, "missing", "api-rate-limit-kongplugin"))

    ingress = _resource_named(docs, "Ingress", "server-manager-public-intake-api")
    if ingress is None:
        failures.append(_failure(channel, "missing", "api-rate-limit-ingress"))
        return

    _validate_ingress_paths(
        channel,
        ingress,
        "api-rate-limit-ingress",
        f"api.{channel}.humility.gg",
        API_PUBLIC_PATHS,
        "server-manager-api",
        8000,
        failures,
    )


def _validate_pomerium_rate_limit(channel: str, gitops_root: Path, failures: list[str]) -> None:
    path = gitops_root / "channels" / channel / "auth" / "pomerium" / "public-intake-rate-limit.yaml"
    docs = _read_yaml_item(channel, path, "pomerium-rate-limit-yaml", failures)
    if docs is None:
        return

    ingress = _resource_named(docs, "Ingress", "web-public-intake", "auth-system")
    if ingress is None:
        failures.append(_failure(channel, "missing", "pomerium-rate-limit-ingress"))
        return

    _validate_ingress_paths(
        channel,
        ingress,
        "pomerium-rate-limit-ingress",
        f"web.{channel}.humility.gg",
        WEB_PUBLIC_PATHS,
        "pomerium-proxy",
        80,
        failures,
    )


def _policy_content_by_id(policies: Any) -> dict[str, str]:
    if not isinstance(policies, list):
        return {}
    return {
        policy["id"]: policy.get("content", "")
        for policy in policies
        if isinstance(policy, dict) and isinstance(policy.get("id"), str)
    }


def _validate_cedar_policies(channel: str, cedar_root: Path, failures: list[str]) -> None:
    path = cedar_root / "channels" / channel / "services" / "server-manager-api" / "policies.json"
    policies = _read_json_item(channel, path, "cedar-policies-json", failures)
    if policies is None:
        failures.extend(
            [
                _failure(channel, "missing", "cedar-public-intake-allow"),
                _failure(channel, "missing", "cedar-public-intake-no-read"),
            ]
        )
        return

    principal = f'Public::"web-intake.{channel}"'
    local_principal = 'Public::"web-intake.local"'
    by_id = _policy_content_by_id(policies)
    expected = {
        "cedar-public-intake-allow": (
            "public-intake-allow",
            "permit(",
            principal,
            'Action::"application:submit_public"',
            'Resource::"server-manager-api:public-applications"',
        ),
        "cedar-public-intake-no-read": (
            "public-intake-no-read",
            "forbid(",
            principal,
            'Action::"api:read"',
            'Resource::"server-manager-api"',
        ),
    }
    for item, (policy_id, effect, expected_principal, action, resource) in expected.items():
        content = by_id.get(policy_id)
        if content is None:
            failures.append(_failure(channel, "missing", item))
            continue
        if local_principal in content and channel != "local":
            failures.append(
                _failure(channel, "invalid", item, f'principal {local_principal} is not {expected_principal}')
            )
            continue
        missing_parts = [
            part for part in (effect, expected_principal, action, resource) if part not in content
        ]
        if missing_parts:
            failures.append(_failure(channel, "invalid", item, f"missing {missing_parts}"))


def _pomerium_config_documents(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rendered: list[dict[str, Any]] = []
    for document in docs:
        data = (
            document.get("spec", {})
            .get("managedSecretReference", {})
            .get("template", {})
            .get("data", {})
        )
        config = data.get("config.yaml") or data.get("pomerium-config")
        if not isinstance(config, str):
            continue
        for rendered_doc in yaml.safe_load_all(config):
            if isinstance(rendered_doc, dict):
                rendered.append(rendered_doc)
    return rendered


def _validate_pomerium_routes(channel: str, gitops_root: Path, failures: list[str]) -> None:
    path = gitops_root / "channels" / channel / "auth" / "pomerium" / "secrets-infisicalsecret.yaml"
    docs = _read_yaml_item(channel, path, "pomerium-secrets-yaml", failures)
    if docs is None:
        failures.extend(
            [
                _failure(channel, "missing", "pomerium-public-route"),
                _failure(channel, "missing", "pomerium-route-ordering"),
            ]
        )
        return

    try:
        configs = _pomerium_config_documents(docs)
    except yaml.YAMLError as exc:
        failures.append(_failure(channel, "invalid", "pomerium-routes", str(exc).splitlines()[0]))
        return
    routes = next((config.get("routes") for config in configs if isinstance(config.get("routes"), list)), None)
    if routes is None:
        failures.append(_failure(channel, "invalid", "pomerium-routes", "no routes list found"))
        return

    expected_from = f"https://web.{channel}.humility.gg"
    identity_indexes: list[int] = []
    public_indexes: list[int] = []
    for index, route in enumerate(routes):
        if not isinstance(route, dict) or route.get("from") != expected_from:
            continue
        is_public = route.get("allow_public_unauthenticated_access") is True
        is_identity = not is_public
        if is_identity:
            identity_indexes.append(index)
        if is_public and route.get("to") == WEB_UPSTREAM:
            public_indexes.append(index)

    if not public_indexes:
        failures.append(_failure(channel, "missing", "pomerium-public-route"))
        return
    if not identity_indexes:
        failures.append(_failure(channel, "missing", "pomerium-route-ordering"))
        return
    if not all(index < public_indexes[0] for index in identity_indexes):
        failures.append(
            _failure(
                channel,
                "invalid",
                "pomerium-route-ordering",
                f"identity-bearing route for web.{channel}.humility.gg appears after public catch-all",
            )
        )


def _resolve_roots(
    gitops_root: Path | None = None, cedar_root: Path | None = None, root: Path | None = None
) -> tuple[Path, Path]:
    if root is not None:
        return root / "gitops", root / "policy" / "cedar"
    return gitops_root or GITOPS_ROOT, cedar_root or CEDAR_ROOT


def verify_substrate(
    channel: str,
    gitops_root: Path | None = None,
    cedar_root: Path | None = None,
    *,
    root: Path | None = None,
) -> list[str]:
    gitops, cedar = _resolve_roots(gitops_root, cedar_root, root)
    failures: list[str] = []
    _validate_api_rate_limit(channel, gitops, failures)
    _validate_pomerium_rate_limit(channel, gitops, failures)
    _validate_cedar_policies(channel, cedar, failures)
    _validate_pomerium_routes(channel, gitops, failures)
    return failures


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _api_rate_limit_yaml(channel: str) -> str:
    return f"""\
apiVersion: configuration.konghq.com/v1
kind: KongPlugin
metadata:
  name: public-intake-rate-limit
  namespace: server-manager
plugin: rate-limiting
config:
  minute: 5
  hour: 50
  policy: local
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: server-manager-public-intake-api
  namespace: server-manager
  annotations:
    konghq.com/plugins: public-intake-rate-limit
spec:
  rules:
    - host: api.{channel}.humility.gg
      http:
        paths:
          - path: /api/v1/public/applications
            pathType: Prefix
            backend:
              service:
                name: server-manager-api
                port:
                  number: 8000
          - path: /api/v1/public/chapters
            pathType: Prefix
            backend:
              service:
                name: server-manager-api
                port:
                  number: 8000
"""


def _pomerium_rate_limit_yaml(channel: str) -> str:
    return f"""\
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web-public-intake
  namespace: auth-system
  annotations:
    konghq.com/plugins: public-intake-rate-limit
spec:
  rules:
    - host: web.{channel}.humility.gg
      http:
        paths:
          - path: /api/public/applications
            pathType: Prefix
            backend:
              service:
                name: pomerium-proxy
                port:
                  number: 80
          - path: /api/public/chapters
            pathType: Prefix
            backend:
              service:
                name: pomerium-proxy
                port:
                  number: 80
          - path: /api/applications
            pathType: Prefix
            backend:
              service:
                name: pomerium-proxy
                port:
                  number: 80
"""


def _cedar_policies_json(channel: str) -> str:
    return json.dumps(
        [
            {
                "id": "public-intake-allow",
                "content": (
                    f'permit(principal == Public::"web-intake.{channel}", '
                    'action == Action::"application:submit_public", '
                    'resource == Resource::"server-manager-api:public-applications");'
                ),
            },
            {
                "id": "public-intake-no-read",
                "content": (
                    f'forbid(principal == Public::"web-intake.{channel}", '
                    'action == Action::"api:read", resource == Resource::"server-manager-api");'
                ),
            },
        ],
        indent=2,
    )


def _pomerium_secrets_yaml(channel: str) -> str:
    return f"""\
apiVersion: secrets.infisical.com/v1alpha1
kind: InfisicalSecret
metadata:
  name: pomerium-config
  namespace: auth-system
spec:
  managedSecretReference:
    template:
      data:
        config.yaml: |
          routes:
            - from: https://web.{channel}.humility.gg
              path: /api/me
              to: {WEB_UPSTREAM}
              pass_identity_headers: true
              allow_any_authenticated_user: true
            - from: https://web.{channel}.humility.gg
              to: {WEB_UPSTREAM}
              allow_public_unauthenticated_access: true
"""


def _write_complete_substrate(root: Path, channel: str) -> None:
    _write(
        root / "gitops" / "channels" / channel / "applications" / "server-manager" / "public-intake-rate-limit.yaml",
        _api_rate_limit_yaml(channel),
    )
    _write(
        root / "gitops" / "channels" / channel / "auth" / "pomerium" / "public-intake-rate-limit.yaml",
        _pomerium_rate_limit_yaml(channel),
    )
    _write(
        root
        / "policy"
        / "cedar"
        / "channels"
        / channel
        / "services"
        / "server-manager-api"
        / "policies.json",
        _cedar_policies_json(channel),
    )
    _write(
        root / "gitops" / "channels" / channel / "auth" / "pomerium" / "secrets-infisicalsecret.yaml",
        _pomerium_secrets_yaml(channel),
    )


def test_repository_state_passes() -> None:
    channels = discover_channels(GITOPS_ROOT)
    failures: list[str] = []
    for channel in channels:
        failures.extend(verify_substrate(channel, GITOPS_ROOT, CEDAR_ROOT))
    assert failures == [], "\n".join(failures)


def test_partial_synthetic_channel_fails(tmp_path: Path) -> None:
    channel = "dev"
    _write(
        tmp_path
        / "gitops"
        / "channels"
        / channel
        / "applications"
        / "server-manager"
        / "public-intake-rate-limit.yaml",
        _api_rate_limit_yaml(channel),
    )

    assert discover_channels(tmp_path / "gitops") == [channel]

    failures = verify_substrate(channel, root=tmp_path)
    failure_text = "\n".join(failures)
    assert failures, "expected incomplete public-intake substrate to fail"
    for expected in (
        f"public-intake channel tripwire failed for {channel}: missing pomerium-rate-limit-yaml",
        f"public-intake channel tripwire failed for {channel}: missing cedar-policies-json",
        f"public-intake channel tripwire failed for {channel}: missing cedar-public-intake-allow",
        f"public-intake channel tripwire failed for {channel}: missing cedar-public-intake-no-read",
        f"public-intake channel tripwire failed for {channel}: missing pomerium-secrets-yaml",
        f"public-intake channel tripwire failed for {channel}: missing pomerium-public-route",
        f"public-intake channel tripwire failed for {channel}: missing pomerium-route-ordering",
    ):
        assert expected in failure_text


def test_full_synthetic_channel_passes(tmp_path: Path) -> None:
    channel = "dev"
    _write_complete_substrate(tmp_path, channel)

    assert discover_channels(tmp_path / "gitops") == [channel]
    assert verify_substrate(channel, root=tmp_path) == []
