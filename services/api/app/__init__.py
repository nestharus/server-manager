"""Humility server-manager API service.

FastAPI application providing the mutation gateway for the Discord
server management platform. Both the web UI and the Discord daemon
route through this API.

Internal architecture follows the ai-workflow layered pattern:
api -> services -> repositories -> infrastructure.
"""

from __future__ import annotations

import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
