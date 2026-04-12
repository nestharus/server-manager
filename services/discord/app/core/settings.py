"""Discord daemon settings.

Shares the same env vars as the API service but only reads what it
needs. The daemon connects to the gateway and optionally calls the
API service for mutations.
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    humility_env: Literal["production", "staging"] = "staging"
    discord_bot_token: str
    discord_guild_id: int
    discord_staging_guild_id: int | None = None

    # API service URL (for daemon → API calls)
    api_base_url: str = "http://localhost:8000"

    # Supabase (direct access for reads + transcript persistence)
    supabase_db_url: str | None = None

    @property
    def active_guild_id(self) -> int:
        if self.humility_env == "staging" and self.discord_staging_guild_id:
            return self.discord_staging_guild_id
        return self.discord_guild_id


def get_settings() -> Settings:
    return Settings()
