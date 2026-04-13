from pydantic import Field
from pydantic_settings import BaseSettings


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
