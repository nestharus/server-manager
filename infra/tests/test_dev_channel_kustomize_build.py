from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEV_KUSTOMIZATION = REPO_ROOT / "gitops" / "channels" / "dev"


def _metadata(resource: dict[str, Any]) -> dict[str, Any]:
    return resource.get("metadata", {}) or {}


def test_dev_channel_kustomize_build_contains_public_intake_substrate() -> None:
    kustomize = shutil.which("kustomize")
    if kustomize is None:
        pytest.skip("kustomize binary is not available")

    result = subprocess.run(
        [kustomize, "build", str(DEV_KUSTOMIZATION)],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr

    docs = [
        document
        for document in yaml.safe_load_all(result.stdout)
        if isinstance(document, dict)
    ]
    names_by_kind = {
        (document.get("kind"), _metadata(document).get("namespace"), _metadata(document).get("name"))
        for document in docs
    }

    assert ("KongPlugin", "server-manager", "public-intake-rate-limit") in names_by_kind
    assert ("Ingress", "server-manager", "server-manager-public-intake-api") in names_by_kind
    assert ("Ingress", "auth-system", "web-public-intake") in names_by_kind
    assert ("InfisicalSecret", "auth-system", "pomerium-config") in names_by_kind
    assert "api.dev.humility.gg" in result.stdout
    assert "web.dev.humility.gg" in result.stdout
