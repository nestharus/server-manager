"""Uvicorn entry point.

Run with: cd services/api && uv run uvicorn app.main:app --reload
"""

from app.core.factory import create_api_app

app = create_api_app()
