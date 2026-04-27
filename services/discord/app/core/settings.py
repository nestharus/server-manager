from __future__ import annotations

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.contracts.runtime_settings import (
    DISCORD_SETTINGS_SOURCE,
    DiscordSettingsRead,
    SettingsConstructionError,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None)

    discord_bot_token: str = Field(repr=False)
    discord_guild_id: int = Field(gt=0)
    api_base_url: str = Field(min_length=1)
    discord_dry_run: bool = False

    def to_read(self) -> DiscordSettingsRead:
        return DiscordSettingsRead(
            discord_bot_token=self.discord_bot_token,
            discord_guild_id=self.discord_guild_id,
            api_base_url=self.api_base_url,
            required_bot_permissions=(
                "MANAGE_ROLES",
                "MANAGE_CHANNELS",
                "VIEW_CHANNEL",
            ),
        )


def _field_name_to_env_var(field_name: str) -> str:
    return field_name.upper()


def _missing_env_vars_from_error(error: ValidationError) -> list[str]:
    required_env_vars = DISCORD_SETTINGS_SOURCE.required_env_vars
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
