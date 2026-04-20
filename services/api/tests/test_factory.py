import sys
from pathlib import Path

import pytest
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.core.factory as factory_module
from app.contracts.runtime_settings import SettingsConstructionError
from app.core.factory import create_app
from app.core.settings import Settings


REQUIRED_ENV_VARS = {
    "DISCORD_BOT_TOKEN": "test-token-value",
    "DISCORD_GUILD_ID": "900000000000000001",
    "SUPABASE_DB_URL": "postgresql://user:pass@localhost:5432/db",
    "SUPABASE_SERVICE_KEY": "test-service-key",
}


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in REQUIRED_ENV_VARS.items():
        monkeypatch.setenv(key, value)


def _clear_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in REQUIRED_ENV_VARS:
        monkeypatch.delenv(key, raising=False)


def test_create_app_is_importable_from_factory_module() -> None:
    assert callable(create_app)
    assert create_app.__module__ == "app.core.factory"


def test_create_app_without_args_returns_fastapi_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)

    app = create_app()

    assert isinstance(app, FastAPI)


def test_create_app_with_provided_settings_uses_same_object_and_skips_settings_init(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)
    settings = Settings()

    def fail_if_called() -> Settings:
        raise AssertionError("Settings() should not be instantiated when settings is provided")

    monkeypatch.setattr(factory_module, "Settings", fail_if_called)

    app = create_app(settings=settings)

    assert app.state.settings is settings


def test_create_app_sets_title_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    settings = Settings()

    app = create_app(settings=settings)

    assert app.title == settings.app_name


def test_create_app_sets_version_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    settings = Settings()

    app = create_app(settings=settings)

    assert app.version == settings.app_version


def test_create_app_sets_debug_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    settings = Settings()

    app = create_app(settings=settings)

    assert app.debug == settings.debug


def test_create_app_stores_used_settings_on_app_state(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    settings = Settings()

    app = create_app(settings=settings)

    assert app.state.settings is settings


def test_create_app_without_env_vars_raises_settings_construction_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_required_env(monkeypatch)

    with pytest.raises(SettingsConstructionError):
        create_app()
