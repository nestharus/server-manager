from __future__ import annotations

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings

from app.contracts.runtime_settings import (
    API_SETTINGS_SOURCE,
    ApiSettingsRead,
    SettingsConstructionError,
)


class Settings(BaseSettings):
    app_name: str = "server-manager-api"
    app_version: str = "0.1.0"
    platform_channel: str = "local"
    platform_tenant: str = "platform"
    debug: bool = False
    api_prefix: str = "/api/v1"

    discord_bot_token: str = Field(..., repr=False)
    discord_guild_id: int
    discord_staging_guild_id: int | None = None
    web_public_base_url: str = Field(...)
    global_applications_review_channel_id: str | None = None
    global_application_managers_role_id: str | None = None
    global_primary_guild_channel_url: str | None = None

    supabase_db_url: str = Field(..., repr=False)
    supabase_service_key: str = Field(..., repr=False)

    google_cloud_vision_key: str | None = Field(default=None, repr=False)
    gemini_api_key: str | None = Field(default=None, repr=False)
    z_ai_api_key: str | None = Field(default=None, repr=False)
    minimax_api_key: str | None = Field(default=None, repr=False)
    cedar_authorization_url: str = (
        "http://opal-client.auth-system.svc.cluster.local:8180"
    )
    applicant_oidc_client_id: str = "humility-local-server-manager-applicant"
    applicant_oidc_client_secret: SecretStr = Field(
        default=SecretStr("local-applicant-oidc-client-secret"), repr=False
    )
    authentik_jwks_url: str = (
        "https://auth.local.humility.local/application/o/server-manager-applicant/jwks/"
    )
    authentik_token_url: str = "https://auth.local.humility.local/application/o/token/"
    authentik_authorize_url: str = (
        "https://auth.local.humility.local/application/o/authorize/"
    )
    authentik_issuer_url: str = (
        "https://auth.local.humility.local/application/o/server-manager-applicant/"
    )
    applicant_discord_redirect_uri: str = (
        "https://web.local.humility.local/auth/discord/callback"
    )
    applicant_receipt_signing_key: SecretStr = Field(
        default=SecretStr("local-applicant-receipt-signing-key-change-me"),
        repr=False,
    )
    applicant_receipt_ttl_seconds: int = 600
    s3_endpoint: str = Field(...)
    s3_region: str = "us-east-1"
    s3_bucket: str = Field(...)
    s3_access_key_id: SecretStr = Field(..., repr=False)
    s3_secret_access_key: SecretStr = Field(..., repr=False)

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
