from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
RENDERER = REPO_ROOT / "infra" / "scripts" / "render-gitops-source.py"
LOCAL_ROOT = REPO_ROOT / "gitops" / "channels" / "local"
OPAL_VALUES = LOCAL_ROOT / "auth" / "opal-cedar" / "render-values.yaml"
OPAL_RENDERED = LOCAL_ROOT / "auth" / "opal-cedar" / "rendered" / "opal-0.0.29.yaml"
ACCESS_POLICY_MATRIX = (
    REPO_ROOT / "infra" / "tests" / "fixtures" / "contracts" / "access_policy_matrix.yml"
)
ACCESS_POLICY_VALIDATOR = REPO_ROOT / "infra" / "tests" / "validate_access_policy_local.sh"
TENANT_VALIDATOR = REPO_ROOT / "infra" / "tests" / "validate_tenant_isolation_local.sh"
AUTH_STACK_VALIDATOR = REPO_ROOT / "infra" / "tests" / "validate_auth_stack_local.sh"
SERVICE_IDENTITY_VALIDATOR = REPO_ROOT / "infra" / "scripts" / "verify-service-identity-claim.sh"

POLICY_FILE_RELATIVE = (
    "policy/cedar/channels/local/services/server-manager-api/policies.json"
)
GENERATED_POLICIES_RELATIVE = (
    "policy/cedar/channels/local/services/server-manager-api/generated/policies"
)
EXPECTED_OPAL_REPO_URL = (
    "http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git"
)
POLLING_INTERVAL_SECONDS = 30


def bootstrap_job_name() -> str:
    return "cedar-access-policy-" + "bootstrap"


def bundle_config_map_name() -> str:
    return "cedar-access-policy-" + "bundle"


@dataclass(frozen=True)
class RenderResult:
    returncode: int
    stderr: str


def yaml_document(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def yaml_documents(path: Path) -> list[dict[str, Any]]:
    return [
        doc
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if isinstance(doc, dict)
    ]


def access_policy_matrix() -> dict[str, Any]:
    return yaml_document(ACCESS_POLICY_MATRIX)


def repo_path(relative_path: str) -> Path:
    path = REPO_ROOT / relative_path
    assert path.is_file(), f"missing repo fixture path: {relative_path}"
    return path


def canonical_policy_file() -> Path:
    return repo_path(POLICY_FILE_RELATIVE)


def canonical_policies(path: Path | None = None) -> list[dict[str, str]]:
    policies = json.loads((path or canonical_policy_file()).read_text(encoding="utf-8"))
    assert isinstance(policies, list), "canonical policy bundle must be a JSON list"
    return policies


def canonical_policy_map(path: Path | None = None) -> dict[str, str]:
    return {policy["id"]: policy["content"] + "\n" for policy in canonical_policies(path)}


def canonical_policy_ids(path: Path | None = None) -> list[str]:
    return sorted(canonical_policy_map(path))


def generated_policy_dir(snapshot_root: Path, fixture: dict[str, Any] | None = None) -> Path:
    if fixture is not None:
        relative = fixture["bundle"]["seeded_policy_files"]
    else:
        relative = GENERATED_POLICIES_RELATIVE
    return snapshot_root / relative


def generated_policy_map(snapshot_root: Path, fixture: dict[str, Any] | None = None) -> dict[str, str]:
    policy_dir = generated_policy_dir(snapshot_root, fixture)
    assert policy_dir.is_dir(), f"missing generated Cedar policy dir: {policy_dir}"
    return {
        policy_file.stem: policy_file.read_text(encoding="utf-8")
        for policy_file in sorted(policy_dir.glob("*.cedar"))
    }


def run_renderer(out: Path, channel: str = "local") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RENDERER), "--channel", channel, "--out", str(out)],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )


def render_snapshot(out: Path, channel: str = "local") -> None:
    result = run_renderer(out, channel)
    assert result.returncode == 0, (
        "render-gitops-source.py failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def _load_renderer_module() -> Any:
    scripts_dir = str(REPO_ROOT / "infra" / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(
        "init121_render_gitops_source_contract",
        RENDERER,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_renderer_with_policy_payload(work_dir: Path, payload: str) -> RenderResult:
    fake_root = work_dir / "repo"
    policy_file = fake_root / POLICY_FILE_RELATIVE
    policy_file.parent.mkdir(parents=True)
    policy_file.write_text(payload, encoding="utf-8")
    (fake_root / "gitops" / "channels" / "local").mkdir(parents=True)

    renderer = _load_renderer_module()
    renderer.REPO_ROOT = fake_root
    renderer.GITOPS_ROOT = fake_root / "gitops"
    renderer.POLICY_ROOT = fake_root / "policy"
    resolved = {
        "id": "local",
        "gitops": {
            "source_kind": "git",
            "kustomization_name": "humility-local",
            "kustomization_namespace": "flux-system",
            "decryption_secret_namespace": "flux-system",
            "interval": "1m",
            "retry_interval": "30s",
            "git_url": EXPECTED_OPAL_REPO_URL,
            "git_ref": "refs/heads/main",
            "path": "./gitops/channels/local",
            "prune": True,
            "wait": True,
            "sops_age_secret_name": "sops-age",
        },
    }
    try:
        renderer.render(resolved, work_dir / "out")
    except Exception as exc:  # noqa: BLE001 - test helper reports contract failures.
        return RenderResult(returncode=1, stderr=str(exc))
    return RenderResult(returncode=0, stderr="")


def local_root_documents() -> list[dict[str, Any]]:
    kubectl = shutil.which("kubectl")
    if kubectl is not None:
        result = subprocess.run(
            [
                kubectl,
                "kustomize",
                "--load-restrictor=LoadRestrictionsNone",
                str(LOCAL_ROOT),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        return [
            doc
            for doc in yaml.safe_load_all(result.stdout)
            if isinstance(doc, dict)
        ]

    kustomization = yaml_document(LOCAL_ROOT / "kustomization.yaml")
    docs: list[dict[str, Any]] = []
    for relative in kustomization.get("resources", []):
        path = LOCAL_ROOT / relative
        if path.is_file():
            docs.extend(yaml_documents(path))
    return docs


def deployment_env(docs: list[dict[str, Any]], deployment_name: str) -> dict[str, str]:
    for doc in docs:
        if doc.get("kind") != "Deployment":
            continue
        if doc.get("metadata", {}).get("name") != deployment_name:
            continue
        containers = doc["spec"]["template"]["spec"]["containers"]
        env: dict[str, str] = {}
        for container in containers:
            for item in container.get("env", []):
                if "name" in item and "value" in item:
                    env[item["name"]] = str(item["value"])
        return env
    raise AssertionError(f"missing Deployment/{deployment_name}")


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def files_containing(root: Path, needle: str) -> list[Path]:
    matches: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            haystack = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if needle in haystack:
            matches.append(path)
    return sorted(matches)


def has_wait_longer_than_polling_interval(script: str) -> bool:
    marker_names = ("POLLING_INTERVAL", "OPAL_POLICY_REPO_POLLING_INTERVAL")
    if any(marker in script for marker in marker_names):
        return True
    for line in script.splitlines():
        stripped = line.strip()
        if not stripped.startswith("sleep "):
            continue
        value = stripped.removeprefix("sleep ").split()[0]
        if value.isdigit() and int(value) > POLLING_INTERVAL_SECONDS:
            return True
    return False


def with_fake_path(path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{path}{os.pathsep}{env.get('PATH', '')}"
    return env
