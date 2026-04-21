from __future__ import annotations

import subprocess
from pathlib import Path


def test_no_daemon_tickets_import_remains() -> None:
    # AC4, D17
    repo_root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        [
            "rg",
            "-n",
            r"(import daemon\\.db|from daemon\\.db import|daemon_db\\.)",
            "services/api/app",
            "services/discord/app",
        ],
        cwd=repo_root,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 1, result.stdout + result.stderr
