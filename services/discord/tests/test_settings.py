import pytest
from pydantic import ValidationError

from app.core.settings import Settings


def test_settings_construction_with_all_required_fields_succeeds() -> None:
    settings = Settings(
        discord_bot_token="test-token",
        discord_guild_id=1,
        supabase_db_url="postgresql://test",
    )

    assert settings.discord_bot_token == "test-token"
    assert isinstance(settings.discord_guild_id, int)
    assert settings.discord_guild_id == 1
    assert settings.supabase_db_url == "postgresql://test"


def test_missing_discord_bot_token_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_GUILD_ID", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(
            discord_guild_id=1,
            supabase_db_url="postgresql://test",
        )

    assert "discord_bot_token" in str(exc_info.value)


def test_missing_discord_guild_id_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_GUILD_ID", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(
            discord_bot_token="test-token",
            supabase_db_url="postgresql://test",
        )

    assert "discord_guild_id" in str(exc_info.value)


def test_missing_supabase_db_url_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_GUILD_ID", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(
            discord_bot_token="test-token",
            discord_guild_id=1,
        )

    assert "supabase_db_url" in str(exc_info.value)


def test_repr_does_not_contain_token_value() -> None:
    settings = Settings(
        discord_bot_token="super-secret-token",
        discord_guild_id=1,
        supabase_db_url="postgresql://test",
    )

    assert "super-secret-token" not in repr(settings)


def test_repr_does_not_contain_db_url_value() -> None:
    settings = Settings(
        discord_bot_token="test-token",
        discord_guild_id=1,
        supabase_db_url="postgresql://secret-db",
    )

    assert "postgresql://secret-db" not in repr(settings)


def test_settings_reads_values_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "env-token")
    monkeypatch.setenv("DISCORD_GUILD_ID", "42")
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://env-db")

    settings = Settings()

    assert settings.discord_bot_token == "env-token"
    assert settings.discord_guild_id == 42
    assert settings.supabase_db_url == "postgresql://env-db"
