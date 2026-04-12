"""Application settings loaded from environment variables.

Uses pydantic-settings for validation and type coercion. All secrets
come from env vars (Railway injects them in production, .env for local dev).
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Environment identification
    humility_env: Literal["production", "staging"] = "staging"

    # Discord
    discord_bot_token: str
    discord_guild_id: int
    discord_staging_guild_id: int | None = None

    # Supabase Postgres
    supabase_db_url: str

    # OCR - primary
    google_cloud_vision_key: str | None = None

    # OCR - LLM fallback
    z_ai_api_key: str | None = None
    gemini_api_key: str | None = None
    minimax_api_key: str | None = None

    @property
    def active_guild_id(self) -> int:
        if self.humility_env == "staging" and self.discord_staging_guild_id:
            return self.discord_staging_guild_id
        return self.discord_guild_id


def get_settings() -> Settings:
    return Settings()
