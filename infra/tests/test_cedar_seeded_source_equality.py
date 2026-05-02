from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from infra.tests.fixtures.cedar_policy_source import (
    canonical_policy_map,
    generated_policy_dir,
    generated_policy_map,
    render_snapshot,
    run_renderer_with_policy_payload,
)


def test_seeded_cedar_files_equal_canonical_policy_source() -> None:
    """Risk annotation: group=TG-1; named_risk=seeded_policy_source_drift;
    level=component; source=planning/proposals/03-cedar-policy-source.md#test-intent-track T1;
    assumptions=A3,A5.
    """
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp) / "gitops-source"

        render_snapshot(snapshot)

        assert generated_policy_map(snapshot) == canonical_policy_map()


def test_seeded_cedar_render_removes_stale_generated_files() -> None:
    """Risk annotation: group=TG-1; named_risk=stale_generated_cedar_policy;
    level=component; source=planning/proposals/03-cedar-policy-source.md#test-intent-track T1;
    assumptions=A3,A5.
    """
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp) / "gitops-source"

        render_snapshot(snapshot)
        stale = generated_policy_dir(snapshot) / "garbage-id.cedar"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("", encoding="utf-8")

        render_snapshot(snapshot)

        assert not stale.exists()
        assert generated_policy_map(snapshot) == canonical_policy_map()


@pytest.mark.parametrize(
    ("payload", "message_fragments"),
    [
        (
            [
                {"id": "duplicate-id", "content": 'permit(principal, action, resource);'},
                {"id": "duplicate-id", "content": 'permit(principal, action, resource);'},
            ],
            ("duplicate", "duplicate-id"),
        ),
        ([{"content": 'permit(principal, action, resource);'}], ("id",)),
        ([{"id": "missing-content"}], ("content",)),
        ([{"id": "empty-content", "content": ""}], ("empty",)),
        ([{"id": "../escape", "content": 'permit(principal, action, resource);'}], ("id",)),
        ({"id": "not-a-list"}, ("list",)),
        ("not valid json", ("json",)),
    ],
)
def test_seeded_cedar_materializer_rejects_invalid_policy_json(
    payload: object,
    message_fragments: tuple[str, ...],
) -> None:
    """Risk annotation: group=TG-1; named_risk=invalid_policy_source_accepted;
    level=component; source=planning/proposals/03-cedar-policy-source.md#contract C1;
    assumptions=A3,A5.
    """
    serialized = payload if isinstance(payload, str) else json.dumps(payload)
    with tempfile.TemporaryDirectory() as tmp:
        result = run_renderer_with_policy_payload(Path(tmp), serialized)

    assert result.returncode != 0
    error = result.stderr.lower()
    for fragment in message_fragments:
        assert fragment in error
