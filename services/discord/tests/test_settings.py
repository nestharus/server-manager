import pytest
from pydantic import ValidationError

from app.contracts.runtime_settings import (
    DISCORD_SETTINGS_SOURCE,
    DiscordSettingsRead,
    SettingsConstructionError,
)
from app.core.settings import Settings, load_settings


ALL_SETTINGS_ENV_VARS = (
    "DISCORD_BOT_TOKEN",
    "DISCORD_GUILD_ID",
    "API_BASE_URL",
)


def _clear_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_var in ALL_SETTINGS_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


def test_settings_construction_with_all_required_fields_succeeds() -> None:
    settings = Settings(
        discord_bot_token="test-token",
        discord_guild_id=1,
        api_base_url="http://api.test",
    )

    assert settings.discord_bot_token == "test-token"
    assert isinstance(settings.discord_guild_id, int)
    assert settings.discord_guild_id == 1
    assert settings.api_base_url == "http://api.test"


def test_missing_discord_bot_token_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_settings_env(monkeypatch)

    with pytest.raises(ValidationError) as exc_info:
        Settings(
            discord_guild_id=1,
            api_base_url="http://api.test",
        )

    assert "discord_bot_token" in str(exc_info.value)


def test_missing_discord_guild_id_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_settings_env(monkeypatch)

    with pytest.raises(ValidationError) as exc_info:
        Settings(
            discord_bot_token="test-token",
            api_base_url="http://api.test",
        )

    assert "discord_guild_id" in str(exc_info.value)


def test_missing_api_base_url_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_settings_env(monkeypatch)

    with pytest.raises(ValidationError) as exc_info:
        Settings(
            discord_bot_token="test-token",
            discord_guild_id=1,
        )

    assert "api_base_url" in str(exc_info.value)


def test_api_base_url_must_be_non_empty_string() -> None:
    with pytest.raises(ValidationError):
        Settings(
            discord_bot_token="test-token",
            discord_guild_id=1,
            api_base_url="",
        )


def test_repr_does_not_contain_token_value() -> None:
    settings = Settings(
        discord_bot_token="super-secret-token",
        discord_guild_id=1,
        api_base_url="http://api.test",
    )

    assert "super-secret-token" not in repr(settings)


def test_settings_reads_values_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "env-token")
    monkeypatch.setenv("DISCORD_GUILD_ID", "42")
    monkeypatch.setenv("API_BASE_URL", "http://env.api")

    settings = Settings()

    assert settings.discord_bot_token == "env-token"
    assert settings.discord_guild_id == 42
    assert settings.api_base_url == "http://env.api"


def test_discord_settings_to_read_returns_discord_settings_read() -> None:
    settings = Settings(
        discord_bot_token="test-token",
        discord_guild_id=1,
        api_base_url="http://api.test",
    )

    read = settings.to_read()

    assert isinstance(read, DiscordSettingsRead)
    assert read.discord_bot_token == "test-token"
    assert read.discord_guild_id == 1
    assert read.api_base_url == "http://api.test"
    assert read.required_bot_permissions == (
        "MANAGE_ROLES",
        "MANAGE_CHANNELS",
        "VIEW_CHANNEL",
    )


def test_discord_settings_construction_error_names_missing_env_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_settings_env(monkeypatch)

    with pytest.raises(SettingsConstructionError) as exc_info:
        load_settings()

    missing = set(exc_info.value.missing_env_vars)
    assert missing == {"DISCORD_BOT_TOKEN", "DISCORD_GUILD_ID", "API_BASE_URL"}


def test_discord_settings_source_matches_service_code_env_vars() -> None:
    assert DISCORD_SETTINGS_SOURCE.required_env_vars == frozenset(
        {"DISCORD_BOT_TOKEN", "DISCORD_GUILD_ID", "API_BASE_URL"}
    )
    assert DISCORD_SETTINGS_SOURCE.optional_env_vars == frozenset()
    assert DISCORD_SETTINGS_SOURCE.secret_mounts == frozenset()
