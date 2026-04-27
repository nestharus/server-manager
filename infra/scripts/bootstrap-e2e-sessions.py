#!/usr/bin/env python3
"""Generate reusable Playwright storageState files for local infra E2E flows."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "infra/tests/e2e/lib/playwright/run-browser-flow.sh"
DEFAULT_KUBECONFIG = Path.home() / ".kube/humility-local.yaml"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kubeconfig", default=str(DEFAULT_KUBECONFIG))
    parser.add_argument("--flow", choices=["auth-stack", "web-ui"], action="append")
    args = parser.parse_args()

    flows = args.flow or ["auth-stack", "web-ui"]
    log_dir = REPO_ROOT / ".tmp/init-119-e2e/session-bootstrap"
    log_dir.mkdir(parents=True, exist_ok=True)

    for flow in flows:
        subprocess.run(
            [str(RUNNER), flow, args.kubeconfig, str(log_dir / f"{flow}.log")],
            cwd=REPO_ROOT,
            check=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
