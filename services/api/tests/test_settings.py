import pytest
from pydantic import ValidationError

from app.contracts.runtime_settings import (
    API_SETTINGS_SOURCE,
    ApiSettingsRead,
    SettingsConstructionError,
)
from app.core.settings import Settings, load_settings


ALL_SETTINGS_ENV_VARS = (
    "APP_NAME",
    "APP_VERSION",
    "PLATFORM_CHANNEL",
    "PLATFORM_TENANT",
    "DEBUG",
    "API_PREFIX",
    "DISCORD_BOT_TOKEN",
    "DISCORD_GUILD_ID",
    "DISCORD_STAGING_GUILD_ID",
    "SUPABASE_DB_URL",
    "SUPABASE_SERVICE_KEY",
    "GOOGLE_CLOUD_VISION_KEY",
    "GEMINI_API_KEY",
    "Z_AI_API_KEY",
    "MINIMAX_API_KEY",
)


def _clear_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_var in ALL_SETTINGS_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_settings_env(monkeypatch)
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token-value")
    monkeypatch.setenv("DISCORD_GUILD_ID", "900000000000000001")
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")


def test_settings_succeeds_with_all_required_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)

    settings = Settings()

    assert isinstance(settings, Settings)


def test_settings_requires_discord_bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_requires_discord_guild_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv("DISCORD_GUILD_ID", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_requires_supabase_db_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_requires_supabase_service_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_rejects_non_integer_discord_guild_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("DISCORD_GUILD_ID", "abc")

    with pytest.raises(ValidationError):
        Settings()


def test_staging_guild_id_defaults_to_none_when_omitted(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv("DISCORD_STAGING_GUILD_ID", raising=False)

    settings = Settings()

    assert settings.discord_staging_guild_id is None


def test_staging_guild_id_is_parsed_as_int(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("DISCORD_STAGING_GUILD_ID", "12345")

    settings = Settings()

    assert settings.discord_staging_guild_id == 12345


def test_provider_keys_default_to_none_when_omitted(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)

    settings = Settings()

    assert settings.google_cloud_vision_key is None
    assert settings.gemini_api_key is None
    assert settings.z_ai_api_key is None
    assert settings.minimax_api_key is None


def test_repr_does_not_contain_discord_bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)

    settings = Settings()

    assert "test-token-value" not in repr(settings)


def test_repr_does_not_contain_supabase_db_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)

    settings = Settings()

    assert "postgresql://user:pass@localhost:5432/db" not in repr(settings)


def test_repr_does_not_contain_supabase_service_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)

    settings = Settings()

    assert "test-service-key" not in repr(settings)


def test_app_name_defaults_to_server_manager_api(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)

    settings = Settings()

    assert settings.app_name == "server-manager-api"


def test_app_version_defaults_to_0_1_0(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)

    settings = Settings()

    assert settings.app_version == "0.1.0"


def test_platform_labels_default_to_local_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)

    settings = Settings()

    assert settings.platform_channel == "local"
    assert settings.platform_tenant == "platform"


def test_debug_defaults_to_false(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)

    settings = Settings()

    assert settings.debug is False


def test_api_prefix_defaults_to_api_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)

    settings = Settings()

    assert settings.api_prefix == "/api/v1"


def test_settings_reads_values_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("APP_NAME", "custom-api")
    monkeypatch.setenv("APP_VERSION", "9.9.9")
    monkeypatch.setenv("PLATFORM_CHANNEL", "staging")
    monkeypatch.setenv("PLATFORM_TENANT", "ops")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("API_PREFIX", "/internal")
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "custom-token")
    monkeypatch.setenv("DISCORD_GUILD_ID", "123456")
    monkeypatch.setenv("DISCORD_STAGING_GUILD_ID", "654321")
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://override:pass@localhost:5432/custom")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "custom-service-key")
    monkeypatch.setenv("GOOGLE_CLOUD_VISION_KEY", "vision-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("Z_AI_API_KEY", "z-ai-key")
    monkeypatch.setenv("MINIMAX_API_KEY", "minimax-key")

    settings = Settings()

    assert settings.app_name == "custom-api"
    assert settings.app_version == "9.9.9"
    assert settings.platform_channel == "staging"
    assert settings.platform_tenant == "ops"
    assert settings.debug is True
    assert settings.api_prefix == "/internal"
    assert settings.discord_bot_token == "custom-token"
    assert settings.discord_guild_id == 123456
    assert settings.discord_staging_guild_id == 654321
    assert settings.supabase_db_url == "postgresql://override:pass@localhost:5432/custom"
    assert settings.supabase_service_key == "custom-service-key"
    assert settings.google_cloud_vision_key == "vision-key"
    assert settings.gemini_api_key == "gemini-key"
    assert settings.z_ai_api_key == "z-ai-key"
    assert settings.minimax_api_key == "minimax-key"


def test_settings_to_read_returns_api_settings_read_narrow_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)

    read = Settings().to_read()

    assert isinstance(read, ApiSettingsRead)
    assert set(read.model_fields.keys()) == {
        "database_url",
        "supabase_service_key",
        "app_version",
    }
    assert read.database_url == "postgresql://user:pass@localhost:5432/db"
    assert read.supabase_service_key == "test-service-key"
    assert read.app_version == "0.1.0"


def test_api_settings_read_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ApiSettingsRead(
            database_url="postgresql://x",
            supabase_service_key="k",
            app_version="0.0.1",
            foo="bar",
        )


def test_load_settings_raises_settings_construction_error_on_missing_env_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_settings_env(monkeypatch)

    with pytest.raises(SettingsConstructionError):
        load_settings()


def test_settings_construction_error_names_missing_env_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_settings_env(monkeypatch)

    with pytest.raises(SettingsConstructionError) as exc_info:
        load_settings()

    missing = set(exc_info.value.missing_env_vars)
    assert missing == {
        "DISCORD_BOT_TOKEN",
        "DISCORD_GUILD_ID",
        "SUPABASE_DB_URL",
        "SUPABASE_SERVICE_KEY",
    }


def test_api_settings_source_matches_service_code_env_vars() -> None:
    required = {
        "DISCORD_BOT_TOKEN",
        "DISCORD_GUILD_ID",
        "SUPABASE_DB_URL",
        "SUPABASE_SERVICE_KEY",
    }
    optional = set(ALL_SETTINGS_ENV_VARS) - required

    assert API_SETTINGS_SOURCE.required_env_vars == frozenset(required)
    assert API_SETTINGS_SOURCE.optional_env_vars == frozenset(optional)
