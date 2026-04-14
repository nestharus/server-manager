"""Shared test fixtures for the API service.

Provides a configured FastAPI test client with test-specific settings.
No real database — tests mock the repository layer.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_chapter_repository
from app.core.factory import create_app
from app.core.settings import Settings
from app.repositories.chapter_repository import InMemoryChapterRepository


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        humility_env="staging",
        discord_bot_token="test-token",
        discord_guild_id=1,
        discord_staging_guild_id=2,
        supabase_db_url="postgresql://test:test@localhost:5432/test",
        supabase_service_key="test-service-key",
    )


@pytest.fixture
def chapter_repository() -> InMemoryChapterRepository:
    return InMemoryChapterRepository()


@pytest.fixture
def client(test_settings: Settings, chapter_repository: InMemoryChapterRepository) -> TestClient:
    application = create_app(test_settings)
    application.dependency_overrides[get_chapter_repository] = lambda: chapter_repository
    return TestClient(application)
