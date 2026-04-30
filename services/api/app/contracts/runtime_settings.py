from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from services.shared.contracts.settings_source import SettingsSourceRead


class SettingsConstructionError(Exception):
    def __init__(self, missing_env_vars: list[str], underlying: Exception) -> None:
        self.missing_env_vars = missing_env_vars
        self.underlying = underlying
        if missing_env_vars:
            message = (
                "Failed to construct API settings. Missing required env vars: "
                + ", ".join(missing_env_vars)
            )
        else:
            message = "Failed to construct API settings."
        super().__init__(message)


class ApiSettingsRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    database_url: str = Field(repr=False)
    supabase_service_key: str = Field(repr=False)
    app_version: str


API_SETTINGS_SOURCE: Final[SettingsSourceRead] = SettingsSourceRead(
    required_env_vars=frozenset(
        {
            "DISCORD_BOT_TOKEN",
            "DISCORD_GUILD_ID",
            "SUPABASE_DB_URL",
            "SUPABASE_SERVICE_KEY",
            "WEB_PUBLIC_BASE_URL",
        }
    ),
    optional_env_vars=frozenset(
        {
            "APP_NAME",
            "APP_VERSION",
            "PLATFORM_CHANNEL",
            "PLATFORM_TENANT",
            "DEBUG",
            "API_PREFIX",
            "DISCORD_STAGING_GUILD_ID",
            "GLOBAL_APPLICATIONS_REVIEW_CHANNEL_ID",
            "GLOBAL_APPLICATION_MANAGERS_ROLE_ID",
            "GLOBAL_PRIMARY_GUILD_CHANNEL_URL",
            "GOOGLE_CLOUD_VISION_KEY",
            "GEMINI_API_KEY",
            "Z_AI_API_KEY",
            "MINIMAX_API_KEY",
        }
    ),
    secret_mounts=frozenset(),
)
