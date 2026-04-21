from __future__ import annotations

import ast
from pathlib import Path


SLICE_TESTS = (
    "test_chapter_governance.py",
    "test_chapter_archive_plan.py",
    "test_chapter_archive_execution.py",
    "test_archive_boundaries.py",
)


def test_slice_023_tests_cite_acceptance_criteria(api_root: Path) -> None:
    """AC1: every SLICE-023 test documents the acceptance criterion it proves."""
    for relative in SLICE_TESTS:
        path = api_root / "tests" / relative
        module = ast.parse(path.read_text())
        for node in module.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                docstring = ast.get_docstring(node)
                assert docstring is not None, f"{relative}:{node.name} missing docstring"
                assert docstring.startswith(("AC1", "AC2", "AC3", "AC4")), (
                    f"{relative}:{node.name} docstring must start with AC1-AC4"
                )


def test_archive_worker_has_no_discord_mutation_surface(repo_root: Path) -> None:
    """AC2: archive worker does not import or call Discord mutation handlers."""
    source = (
        repo_root / "services" / "api" / "app" / "tasks" / "archive.py"
    ).read_text()
    forbidden = ("discord.py", "discord.", "create_channel", "delete_channel", "edit_channel")
    for token in forbidden:
        assert token not in source


def test_archive_worker_uses_service_handlers_for_consequences(repo_root: Path) -> None:
    """AC4: archive consequences go through service handlers instead of direct state SQL."""
    source = (
        repo_root / "services" / "api" / "app" / "tasks" / "archive.py"
    ).read_text()
    assert "transition_ticket(" in source
    assert "transition_application(" in source
    assert "revoke_authority(" in source
    assert "UPDATE tickets" not in source
    assert "UPDATE applications" not in source
    assert "UPDATE authority_grants" not in source


def test_no_governance_alias_or_cancelled_deferred_status(repo_root: Path) -> None:
    """AC1: governance accepts no probation alias and deferred statuses stay bounded."""
    source = (
        repo_root / "services" / "api" / "app" / "services" / "chapters.py"
    ).read_text()
    assert '"probation":' not in source
    deferred_source = "\n".join(
        path.read_text()
        for path in (
            repo_root / "services" / "api" / "app"
        ).rglob("*deferred_effect*.py")
    )
    scheduler_contract = (
        repo_root / "services" / "api" / "app" / "contracts" / "scheduler.py"
    ).read_text()
    assert "claim_status" not in deferred_source
    assert "claim_status" not in scheduler_contract
    assert '"cancelled"' not in deferred_source
    assert "'cancelled'" not in deferred_source
    assert '"cancelled"' not in scheduler_contract
    assert "'cancelled'" not in scheduler_contract


def test_migration_seed_is_exact_match_and_chains_to_wu_022(repo_root: Path) -> None:
    """AC4: migration uses exact service grant matching and the approved down revision."""
    source = (
        repo_root
        / "migrations"
        / "versions"
        / "wu-042_chapter_governance.py"
    ).read_text()
    assert 'down_revision = "wu_022_applications"' in source
    assert "permissions @>" in source
    assert "::jsonb @> permissions" in source
    assert "scope_kind = 'chapter'" in source
