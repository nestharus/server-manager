from __future__ import annotations

from pathlib import Path
from typing import Any

import json
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_GITOPS = REPO_ROOT / "gitops" / "channels" / "local"
WEB_CONTRACT = REPO_ROOT / "infra" / "tests" / "fixtures" / "web-ui" / "contract.json"
PLUGIN_NAME = "public-intake-rate-limit"
KONG_LOCAL = LOCAL_GITOPS / "ingress" / "kong"


def _yaml_documents(path: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if isinstance(document, dict):
            document["_source_path"] = str(path.relative_to(REPO_ROOT))
            docs.append(document)
    return docs


def _local_resources() -> list[dict[str, Any]]:
    candidates = sorted(
        [
            *(
                LOCAL_GITOPS / "applications" / "server-manager"
            ).glob("*.yaml"),
            *(LOCAL_GITOPS / "auth" / "pomerium").glob("*.yaml"),
        ]
    )
    required = [
        LOCAL_GITOPS / "auth" / "pomerium" / "ingress.yaml",
        LOCAL_GITOPS / "auth" / "pomerium" / "public-intake-rate-limit.yaml",
        LOCAL_GITOPS / "applications" / "server-manager" / "api-ingress.yaml",
        LOCAL_GITOPS / "applications" / "server-manager" / "public-intake-rate-limit.yaml",
    ]
    for path in required:
        assert path.is_file(), f"missing expected local GitOps manifest: {path.relative_to(REPO_ROOT)}"
    docs: list[dict[str, Any]] = []
    for path in candidates:
        docs.extend(_yaml_documents(path))
    return docs


def _web_submit_endpoint() -> str:
    return json.loads(WEB_CONTRACT.read_text(encoding="utf-8"))["form"]["submit"]["endpoint"]


def _metadata(resource: dict[str, Any]) -> dict[str, Any]:
    return resource.get("metadata", {})


def _annotations(resource: dict[str, Any]) -> dict[str, str]:
    return _metadata(resource).get("annotations", {}) or {}


def _ingress_paths(resource: dict[str, Any]) -> list[tuple[str, str]]:
    paths: list[tuple[str, str]] = []
    for rule in resource.get("spec", {}).get("rules", []):
        host = rule.get("host")
        for path in rule.get("http", {}).get("paths", []):
            paths.append((host, path.get("path")))
    return paths


def _plugin_annotation(resource: dict[str, Any]) -> str | None:
    return _annotations(resource).get("konghq.com/plugins")


def _kong_version_file(name: str) -> Path:
    paths = {
        "readme": KONG_LOCAL / "README.md",
        "kustomization": KONG_LOCAL / "kustomization.yaml",
        "values": KONG_LOCAL / "render-values.yaml",
        "rendered": KONG_LOCAL / "rendered" / "kong-3.2.0.yaml",
    }
    path = paths[name]
    assert path.is_file(), f"missing expected local Kong version file: {path.relative_to(REPO_ROOT)}"
    return path


def _single_yaml_document(name: str) -> dict[str, Any]:
    docs = _yaml_documents(_kong_version_file(name))
    assert len(docs) == 1, f"expected one YAML document in Kong {name} file, got {len(docs)}"
    return docs[0]


def _kong_deployment() -> dict[str, Any]:
    for document in _yaml_documents(_kong_version_file("rendered")):
        if (
            document.get("kind") == "Deployment"
            and _metadata(document).get("name") == "kong-kong"
            and _metadata(document).get("namespace") == "kong-system"
        ):
            return document
    raise AssertionError("missing kong-kong Deployment in rendered Kong manifest")


def _kong_containers_by_name() -> dict[str, dict[str, Any]]:
    pod_spec = _kong_deployment()["spec"]["template"]["spec"]
    containers = [*pod_spec.get("containers", []), *pod_spec.get("initContainers", [])]
    return {container["name"]: container for container in containers}


def _annotated_ingress_path_details() -> list[tuple[str, str, str | None, str]]:
    details: list[tuple[str, str, str | None, str]] = []
    for ingress in [r for r in _local_resources() if r.get("kind") == "Ingress"]:
        if _plugin_annotation(ingress) != PLUGIN_NAME:
            continue
        source = ingress["_source_path"]
        for rule in ingress.get("spec", {}).get("rules", []):
            host = rule.get("host")
            for path in rule.get("http", {}).get("paths", []):
                details.append((host, path.get("path"), path.get("pathType"), source))
    return details


def test_tg_1a_readme_chart_version_is_3_2_0() -> None:
    """Risk annotation: group=TG-1; named_risk=kong_version_pin_drift;
    level=particular-integration; source=planning/proposals/30-bl-014-kong-version-pin.md.
    """
    readme = _kong_version_file("readme").read_text(encoding="utf-8")
    got = ", ".join(line.strip() for line in readme.splitlines() if "--version" in line)
    assert "--version 3.2.0" in readme, (
        "Kong Helm chart version drifted in README render command: "
        f"expected `--version 3.2.0`, got {got or 'no --version line'}"
    )


def test_tg_1b_kustomization_references_rendered_chart_3_2_0() -> None:
    """Risk annotation: group=TG-1; named_risk=kong_version_pin_drift;
    level=particular-integration; source=planning/proposals/30-bl-014-kong-version-pin.md.
    """
    resources = _single_yaml_document("kustomization").get("resources", [])
    assert "rendered/kong-3.2.0.yaml" in resources, (
        "Kong rendered manifest reference drifted in kustomization: "
        f"expected `rendered/kong-3.2.0.yaml`, got {resources}"
    )


def test_tg_1c_rendered_chart_label_is_kong_3_2_0() -> None:
    """Risk annotation: group=TG-1; named_risk=kong_version_pin_drift;
    level=particular-integration; source=planning/proposals/30-bl-014-kong-version-pin.md.
    """
    labels = _kong_deployment()["spec"]["template"]["metadata"].get("labels", {})
    assert labels.get("helm.sh/chart") == "kong-3.2.0", (
        "Kong rendered chart label drifted on kong-kong Deployment: "
        f"expected `helm.sh/chart: kong-3.2.0`, got {labels.get('helm.sh/chart')}"
    )


def test_tg_1d_render_values_gateway_image_is_kong_3_9() -> None:
    """Risk annotation: group=TG-1; named_risk=kong_version_pin_drift;
    level=particular-integration; source=planning/proposals/30-bl-014-kong-version-pin.md.
    """
    image = _single_yaml_document("values").get("image", {})
    got = f"{image.get('repository')}:{image.get('tag')}"
    assert image.get("repository") == "kong" and image.get("tag") == "3.9", (
        "Kong Gateway image drifted in render-values: expected `kong:3.9`, "
        f"got {got}"
    )


def test_tg_1e_rendered_gateway_image_is_kong_3_9() -> None:
    """Risk annotation: group=TG-1; named_risk=kong_version_pin_drift;
    level=particular-integration; source=planning/proposals/30-bl-014-kong-version-pin.md.
    """
    containers = _kong_containers_by_name()
    for name in ("clear-stale-pid", "proxy"):
        got = containers.get(name, {}).get("image")
        assert got == "kong:3.9", (
            "Kong Gateway image drifted on kong-kong Deployment: "
            f"expected `kong:3.9`, got {name}={got}"
        )


def test_tg_1f_render_values_kic_image_is_3_5() -> None:
    """Risk annotation: group=TG-1; named_risk=kong_version_pin_drift;
    level=particular-integration; source=planning/proposals/30-bl-014-kong-version-pin.md.
    """
    image = _single_yaml_document("values").get("ingressController", {}).get("image", {})
    got = f"{image.get('repository')}:{image.get('tag')}"
    assert (
        image.get("repository") == "kong/kubernetes-ingress-controller"
        and image.get("tag") == "3.5"
    ), (
        "KIC image drifted in render-values: expected "
        f"`kong/kubernetes-ingress-controller:3.5`, got {got}"
    )


def test_tg_1g_rendered_kic_image_is_3_5() -> None:
    """Risk annotation: group=TG-1; named_risk=kong_version_pin_drift;
    level=particular-integration; source=planning/proposals/30-bl-014-kong-version-pin.md.
    """
    got = _kong_containers_by_name().get("ingress-controller", {}).get("image")
    assert got == "kong/kubernetes-ingress-controller:3.5", (
        "KIC image drifted on kong-kong Deployment: expected "
        f"`kong/kubernetes-ingress-controller:3.5`, got {got}"
    )


def test_tg_1h_kongplugin_crd_bundle_annotation_is_v1_5_2() -> None:
    """Risk annotation: group=TG-1; named_risk=kong_version_pin_drift;
    level=particular-integration; source=planning/proposals/30-bl-014-kong-version-pin.md.
    """
    crd = next(
        (
            document
            for document in _yaml_documents(_kong_version_file("rendered"))
            if document.get("kind") == "CustomResourceDefinition"
            and _metadata(document).get("name") == "kongplugins.configuration.konghq.com"
        ),
        None,
    )
    assert crd is not None, "missing KongPlugin CRD in rendered Kong manifest"
    got = _annotations(crd).get("kubernetes-configuration.konghq.com/version")
    assert got == "v1.5.2", (
        "Kong CRD bundle annotation drifted on KongPlugin CRD: "
        f"expected `v1.5.2`, got {got}"
    )


def test_tg_2a_server_manager_side_path_set_covers_public_intake_routes() -> None:
    """Risk annotation: group=TG-2; named_risk=public_intake_route_set_drift;
    level=particular-integration; source=planning/proposals/30-bl-014-kong-version-pin.md.
    """
    details = _annotated_ingress_path_details()
    covered = {(host, path) for host, path, _, _ in details}
    source = ", ".join(sorted({item[3] for item in details}))
    for expected in (
        ("api.local.humility.local", "/api/v1/public/applications"),
        ("api.local.humility.local", "/api/v1/public/chapters"),
    ):
        assert expected in covered, f"missing server-manager public-intake path {expected} in {source}"
    upload = "/api/v1/public/applications/upload-url"
    assert any(
        host == "api.local.humility.local" and upload.startswith(path)
        for host, path, _, _ in details
    ), f"missing server-manager upload-url Prefix coverage for {upload} in {source}"


def test_tg_2b_pomerium_side_path_set_covers_public_intake_routes() -> None:
    """Risk annotation: group=TG-2; named_risk=public_intake_route_set_drift;
    level=particular-integration; source=planning/proposals/30-bl-014-kong-version-pin.md.
    """
    details = _annotated_ingress_path_details()
    covered = {(host, path) for host, path, _, _ in details}
    source = ", ".join(sorted({item[3] for item in details}))
    for expected in (
        ("web.local.humility.local", _web_submit_endpoint()),
        ("web.local.humility.local", "/api/public/chapters"),
        ("web.local.humility.local", "/api/applications"),
    ):
        assert expected in covered, f"missing Pomerium public-intake path {expected} in {source}"
    upload = "/api/public/applications/upload-url"
    assert any(
        host == "web.local.humility.local" and upload.startswith(path)
        for host, path, _, _ in details
    ), f"missing Pomerium upload-url Prefix coverage for {upload} in {source}"


def test_tg_2c_upload_url_is_covered_by_prefix_type_parent() -> None:
    """Risk annotation: group=TG-2; named_risk=public_intake_route_set_drift;
    level=particular-integration; source=planning/proposals/30-bl-014-kong-version-pin.md.
    """
    details = _annotated_ingress_path_details()
    expected = (
        ("api.local.humility.local", "/api/v1/public/applications/upload-url"),
        ("web.local.humility.local", "/api/public/applications/upload-url"),
    )
    for host, upload in expected:
        matches = [
            (path, path_type, source)
            for item_host, path, path_type, source in details
            if item_host == host and upload.startswith(path)
        ]
        assert any(path_type == "Prefix" for _, path_type, _ in matches), (
            f"upload-url path {host}{upload} is not covered by a Prefix-type "
            f"public-intake parent; got {matches}"
        )


def test_tg_3_anti_list_plugin_annotation_not_applied_to_adjacent_ingresses() -> None:
    """Risk annotation: group=TG-3; named_risk=public_intake_route_set_drift;
    level=particular-integration; source=planning/proposals/30-bl-014-kong-version-pin.md.
    """
    adjacent = (
        ("api.local.humility.local", "/api/v1/web/"),
        ("web.local.humility.local", "/auth/discord"),
        ("api.local.humility.local", "/api/v1/health"),
    )
    for ingress in [r for r in _local_resources() if r.get("kind") == "Ingress"]:
        for host, path in _ingress_paths(ingress):
            for adjacent_host, adjacent_path in adjacent:
                handles_adjacent = host == adjacent_host and adjacent_path.startswith(path)
                assert not (handles_adjacent and _plugin_annotation(ingress) == PLUGIN_NAME), (
                    f"public-intake plugin applied to adjacent route {adjacent_host}{adjacent_path} "
                    f"via {host}{path} in {ingress['_source_path']}"
                )


def test_tg_3_path_anti_list_not_in_public_intake_covered_route_set() -> None:
    """Risk annotation: group=TG-3; named_risk=public_intake_route_set_drift;
    level=particular-integration; source=planning/proposals/30-bl-014-kong-version-pin.md.
    """
    forbidden = {"/api/v1/web/admin", "/auth/discord/me", "/api/v1/health"}
    for host, path, _, source in _annotated_ingress_path_details():
        for forbidden_path in forbidden:
            assert not forbidden_path.startswith(path), (
                f"public-intake plugin covered forbidden path {forbidden_path} "
                f"via {host}{path} in {source}"
            )


def test_tg_4_kong_version_files_exist() -> None:
    """Risk annotation: group=TG-4; named_risk=kong_version_pin_drift;
    level=particular-integration; source=planning/proposals/30-bl-014-kong-version-pin.md.
    """
    for name in ("readme", "kustomization", "values", "rendered"):
        _kong_version_file(name)


def test_public_intake_kong_plugin_has_documented_rate_limit_config() -> None:
    """Risk annotation: group=TG-7; named_risk=public_rate_limit_absent_or_misbound;
    level=particular-integration; source=planning/proposals/02-public-application-intake.md#§7 AS-5.
    """
    plugins = [
        resource
        for resource in _local_resources()
        if resource.get("kind") == "KongPlugin"
        and _metadata(resource).get("name") == PLUGIN_NAME
    ]

    assert len(plugins) == 1
    plugin = plugins[0]
    assert _metadata(plugin).get("namespace") == "server-manager"
    assert plugin["plugin"] == "rate-limiting"
    assert plugin["config"]["minute"] == 5
    assert plugin["config"]["hour"] == 50
    assert plugin["config"]["policy"] == "local"


def test_public_intake_plugin_is_bound_only_to_public_submit_paths() -> None:
    """Risk annotation: group=TG-7; named_risk=public_rate_limit_absent_or_misbound;
    level=particular-integration; source=planning/proposals/02-public-application-intake.md#§7 AS-5.
    """
    ingresses = [
        resource for resource in _local_resources() if resource.get("kind") == "Ingress"
    ]
    annotated_paths = {
        path
        for ingress in ingresses
        if _plugin_annotation(ingress) == PLUGIN_NAME
        for path in _ingress_paths(ingress)
    }

    assert (
        "web.local.humility.local",
        "/api/applications",
    ) in annotated_paths
    assert (
        "web.local.humility.local",
        _web_submit_endpoint(),
    ) in annotated_paths
    assert (
        "api.local.humility.local",
        "/api/v1/public/applications",
    ) in annotated_paths

    web_catch_all = next(
        ingress
        for ingress in ingresses
        if _metadata(ingress).get("name") == "web"
        and ("web.local.humility.local", "/") in _ingress_paths(ingress)
    )
    protected_api = next(
        ingress for ingress in ingresses if _metadata(ingress).get("name") == "protected-api"
    )
    authenticated_api = next(
        ingress
        for ingress in ingresses
        if _metadata(ingress).get("name") == "server-manager-api"
        and ("api.local.humility.local", "/") in _ingress_paths(ingress)
    )

    assert _plugin_annotation(web_catch_all) != PLUGIN_NAME
    assert _plugin_annotation(protected_api) != PLUGIN_NAME
    assert _plugin_annotation(authenticated_api) != PLUGIN_NAME
