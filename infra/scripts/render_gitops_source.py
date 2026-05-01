"""Importable module wrapper for render-gitops-source.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path


_SCRIPT_PATH = Path(__file__).with_name("render-gitops-source.py")
_SPEC = importlib.util.spec_from_file_location("_render_gitops_source_script", _SCRIPT_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"unable to load {_SCRIPT_PATH}")

_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

for _name in dir(_MODULE):
    if _name.startswith("__") and _name not in {"__doc__", "__all__"}:
        continue
    globals()[_name] = getattr(_MODULE, _name)

