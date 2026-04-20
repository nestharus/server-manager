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
                "Failed to construct Discord settings. Missing required env vars: "
                + ", ".join(missing_env_vars)
            )
        else:
            message = "Failed to construct Discord settings."
        super().__init__(message)


class DiscordSettingsRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    discord_bot_token: str = Field(repr=False)
    discord_guild_id: int
    api_base_url: str


DISCORD_SETTINGS_SOURCE: Final[SettingsSourceRead] = SettingsSourceRead(
    required_env_vars=frozenset({"DISCORD_BOT_TOKEN", "DISCORD_GUILD_ID", "API_BASE_URL"}),
    optional_env_vars=frozenset(),
    secret_mounts=frozenset(),
)

