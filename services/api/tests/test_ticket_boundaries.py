from __future__ import annotations

import re
from pathlib import Path


def test_no_daemon_tickets_import_remains() -> None:
    # AC4, D17
    repo_root = Path(__file__).resolve().parents[3]
    pattern = re.compile(
        r"(?:\bimport\s+daemon\.db\b|\bfrom\s+daemon\.db\s+import\b|\bdaemon_db\.)"
    )
    matches: list[str] = []
    for root in (repo_root / "services/api/app", repo_root / "services/discord/app"):
        for path in root.rglob("*.py"):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.search(line):
                    rel = path.relative_to(repo_root)
                    matches.append(f"{rel}:{lineno}:{line}")
    assert not matches, "\n".join(matches)
