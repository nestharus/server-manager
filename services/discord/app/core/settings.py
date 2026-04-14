from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None)

    discord_bot_token: str = Field(repr=False)
    discord_guild_id: int = Field(gt=0)
    supabase_db_url: str = Field(repr=False)
