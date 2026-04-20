from __future__ import annotations

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings

from app.contracts.runtime_settings import (
    API_SETTINGS_SOURCE,
    ApiSettingsRead,
    SettingsConstructionError,
)


class Settings(BaseSettings):
    app_name: str = "server-manager-api"
    app_version: str = "0.1.0"
    debug: bool = False
    api_prefix: str = "/api/v1"

    discord_bot_token: str = Field(..., repr=False)
    discord_guild_id: int
    discord_staging_guild_id: int | None = None

    supabase_db_url: str = Field(..., repr=False)
    supabase_service_key: str = Field(..., repr=False)

    google_cloud_vision_key: str | None = Field(default=None, repr=False)
    gemini_api_key: str | None = Field(default=None, repr=False)
    z_ai_api_key: str | None = Field(default=None, repr=False)
    minimax_api_key: str | None = Field(default=None, repr=False)

    def to_read(self) -> ApiSettingsRead:
        return ApiSettingsRead(
            database_url=self.supabase_db_url,
            supabase_service_key=self.supabase_service_key,
            app_version=self.app_version,
        )


def _field_name_to_env_var(field_name: str) -> str:
    return field_name.upper()


def _missing_env_vars_from_error(error: ValidationError) -> list[str]:
    required_env_vars = API_SETTINGS_SOURCE.required_env_vars
    missing_env_vars = {
        _field_name_to_env_var(str(details["loc"][0]))
        for details in error.errors()
        if details["type"] == "missing" and details.get("loc")
    }
    return sorted(env_var for env_var in missing_env_vars if env_var in required_env_vars)


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        missing_env_vars = _missing_env_vars_from_error(exc)
        raise SettingsConstructionError(missing_env_vars, exc) from exc
