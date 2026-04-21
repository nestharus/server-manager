from __future__ import annotations

from pathlib import Path


FORBIDDEN_PATTERNS = (
    "from forms",
    "import forms",
    "forms.dark_nemesis",
    "dark-nemesis.yaml",
    "forms/dark-nemesis.yaml",
)


def test_no_legacy_forms_import_remains(repo_root: Path) -> None:
    roots = [
        repo_root / "services" / "api" / "app",
        repo_root / "services" / "discord" / "app",
    ]
    offenders: list[str] = []
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text()
            for pattern in FORBIDDEN_PATTERNS:
                if pattern in text:
                    offenders.append(f"{path.relative_to(repo_root)}: {pattern}")
    assert offenders == []
