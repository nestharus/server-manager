#!/usr/bin/env python3
"""Operator helper for FontAwesome/WebAwesome dashboard token bootstrap.

This script is intentionally conservative. The current local web image can build
without committed token material, and the INIT-119 E2E suite must not scrape or
store dashboard secrets unless an operator explicitly supplies the dashboard
credentials and the target Infisical project is reachable.

Expected inputs:
  FA_USERNAME / FA_PASSWORD for FontAwesome
  WA_USERNAME / WA_PASSWORD for WebAwesome

When a future dashboard flow is needed, use Playwright here and write only to
Infisical project `platform-frontend`, never to Git or stdout.
"""

from __future__ import annotations

import os


def main() -> int:
    missing = [
        name
        for name in ("FA_USERNAME", "FA_PASSWORD", "WA_USERNAME", "WA_PASSWORD")
        if not os.environ.get(name)
    ]
    if missing:
        print(
            "SKIP: FontAwesome/WebAwesome dashboard bootstrap requires env vars: "
            + ", ".join(missing)
        )
        return 0
    print(
        "SKIP: dashboard scraping is not implemented; no FA/WA token was written. "
        "Implement this only when platform-frontend Infisical paths are defined."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
