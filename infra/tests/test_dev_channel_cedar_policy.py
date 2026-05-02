from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
POLICIES_PATH = (
    REPO_ROOT / "policy" / "cedar" / "channels" / "dev" / "services" / "server-manager-api" / "policies.json"
)
DEV_PUBLIC_PRINCIPAL = 'Public::"web-intake.dev"'
LOCAL_PUBLIC_PRINCIPAL = 'Public::"web-intake.local"'
EXISTING_DEV_POLICIES = {
    "dev-server-manager-api-user-read": (
        'permit(principal == User::"sample@dev.humility.gg", action == Action::"api:read", '
        'resource == Resource::"server-manager-api");'
    ),
    "dev-server-manager-api-buildkite-deploy": (
        'permit(principal == Service::"buildkite-agent.dev", action == Action::"api:ci:deploy", '
        'resource == Resource::"server-manager-api");'
    ),
    "dev-cluster-api-crossplane-reconcile": (
        'permit(principal == Service::"crossplane-provider.dev", '
        'action == Action::"cluster:claim:reconcile", resource == Resource::"cluster-api");'
    ),
}


def _policies() -> list[dict[str, Any]]:
    policies = json.loads(POLICIES_PATH.read_text(encoding="utf-8"))
    assert isinstance(policies, list), "dev policies.json must contain a JSON array"
    return policies


def _content_by_id(policies: list[dict[str, Any]]) -> dict[str, str]:
    return {
        policy["id"]: policy.get("content", "")
        for policy in policies
        if isinstance(policy, dict) and isinstance(policy.get("id"), str)
    }


def test_dev_cedar_public_intake_policies_are_channel_derived() -> None:
    raw = POLICIES_PATH.read_text(encoding="utf-8")
    assert LOCAL_PUBLIC_PRINCIPAL not in raw

    policies = _policies()
    by_id = _content_by_id(policies)
    public_policy_ids = {
        policy["id"]
        for policy in policies
        if isinstance(policy, dict) and DEV_PUBLIC_PRINCIPAL in policy.get("content", "")
    }
    assert public_policy_ids == {"public-intake-allow", "public-intake-no-read"}

    allow = by_id.get("public-intake-allow")
    assert allow is not None
    assert "permit(" in allow
    assert DEV_PUBLIC_PRINCIPAL in allow
    assert 'Action::"application:submit_public"' in allow
    assert 'Resource::"server-manager-api:public-applications"' in allow

    no_read = by_id.get("public-intake-no-read")
    assert no_read is not None
    assert "forbid(" in no_read
    assert DEV_PUBLIC_PRINCIPAL in no_read
    assert 'Action::"api:read"' in no_read
    assert 'Resource::"server-manager-api"' in no_read

    for policy_id in public_policy_ids:
        content = by_id[policy_id]
        assert 'Service::"' not in content
        assert 'User::"' not in content
        assert 'Tenant::"' not in content
        assert re.search(r"^(permit|forbid)\(.+\);$", content) is not None


def test_dev_cedar_existing_policies_remain_verbatim() -> None:
    by_id = _content_by_id(_policies())

    for policy_id, content in EXISTING_DEV_POLICIES.items():
        assert by_id.get(policy_id) == content
