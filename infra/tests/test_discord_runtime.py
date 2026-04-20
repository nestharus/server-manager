"""WU-010E / AC2: Discord runtime entrypoint.

Tests fail now and pass after the SLICE-006 code agent implements:
- `app.contracts.runtime` with `DiscordRuntimeRead`, `DiscordLoginError`,
  `CommandSyncError` (and re-exports `ApiUnreachableError`)
- `app.__main__.run_discord_daemon(settings=...) -> DiscordRuntimeRead`
  with ordered typed-error boot: settings → api reachability → discord login
  → command-tree sync.
"""

from __future__ import annotations

import sys
from pathlib import Path

import discord
import pytest

_DISCORD_SERVICE_PATH = Path(__file__).resolve().parents[2] / "services" / "discord"
if str(_DISCORD_SERVICE_PATH) not in sys.path:
    sys.path.insert(0, str(_DISCORD_SERVICE_PATH))

from app.__main__ import run_discord_daemon  # noqa: E402
from app.contracts.api_transport import ApiUnreachableError  # noqa: E402
from app.contracts.runtime import (  # noqa: E402
    CommandSyncError,  # noqa: F401 — imported to assert contract symbol exists
    DiscordLoginError,
    DiscordRuntimeRead,
)
from app.contracts.runtime_settings import SettingsConstructionError  # noqa: E402
from app.core.bot import HumilityBot  # noqa: E402
from app.core.settings import Settings  # noqa: E402


REQUIRED_ENV_VARS = ("DISCORD_BOT_TOKEN", "DISCORD_GUILD_ID", "API_BASE_URL")


def _discord_settings() -> Settings:
    return Settings(
        discord_bot_token="test-token",
        discord_guild_id=900000000000000001,
        api_base_url="http://stub.api",
    )


@pytest.mark.asyncio()
async def test_run_discord_daemon_returns_runtime_read_on_success_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.__main__ as main_module

    settings = _discord_settings()

    async def _noop_start(self: HumilityBot, token: str, *args, **kwargs) -> None:
        return None

    async def _noop_close(self: HumilityBot) -> None:
        return None

    async def _noop_reachability(*, base_url: str, client) -> None:
        return None

    monkeypatch.setattr(HumilityBot, "start", _noop_start, raising=False)
    monkeypatch.setattr(HumilityBot, "close", _noop_close, raising=False)
    monkeypatch.setattr(main_module, "check_api_reachability", _noop_reachability)

    result = await run_discord_daemon(settings)

    assert isinstance(result, DiscordRuntimeRead)
    assert result.status == "stopped"
    assert result.missing_dependency is None


@pytest.mark.asyncio()
async def test_run_discord_daemon_api_unreachable_raises_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        discord_bot_token="test-token",
        discord_guild_id=900000000000000001,
        api_base_url="http://127.0.0.1:1",
    )

    with pytest.raises(ApiUnreachableError) as exc_info:
        await run_discord_daemon(settings)

    error = exc_info.value
    assert getattr(error, "base_url", None) == "http://127.0.0.1:1"
    assert getattr(error, "reason", None)
    assert getattr(error, "missing_dependency", None) in {
        "api_base_url",
        "api_reachability",
    }


@pytest.mark.asyncio()
async def test_run_discord_daemon_discord_login_failure_raises_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _discord_settings()

    async def _raise_login_failure(
        self: HumilityBot, token: str, *args, **kwargs
    ) -> None:
        raise discord.LoginFailure("invalid token")

    async def _noop_close(self: HumilityBot) -> None:
        return None

    async def _noop_reachability(*, base_url: str, client) -> None:
        return None

    import app.__main__ as main_module
    monkeypatch.setattr(HumilityBot, "start", _raise_login_failure, raising=False)
    monkeypatch.setattr(HumilityBot, "close", _noop_close, raising=False)
    monkeypatch.setattr(main_module, "check_api_reachability", _noop_reachability)

    with pytest.raises(DiscordLoginError) as exc_info:
        await run_discord_daemon(settings)

    assert getattr(exc_info.value, "missing_dependency", None) == "discord_login"


@pytest.mark.asyncio()
async def test_run_discord_daemon_sets_missing_dependency_when_command_sync_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.__main__ as main_module
    from app.contracts.runtime import CommandSyncError

    settings = _discord_settings()

    async def _noop_reachability(*, base_url: str, client) -> None:
        return None

    async def _raise_command_sync(bot: HumilityBot) -> None:
        raise CommandSyncError(reason="test command sync failure")

    async def _noop_start(self: HumilityBot, token: str, *args, **kwargs) -> None:
        return None

    async def _noop_close(self: HumilityBot) -> None:
        return None

    monkeypatch.setattr(HumilityBot, "start", _noop_start, raising=False)
    monkeypatch.setattr(HumilityBot, "close", _noop_close, raising=False)
    monkeypatch.setattr(main_module, "check_api_reachability", _noop_reachability)
    monkeypatch.setattr(main_module, "sync_command_tree", _raise_command_sync)

    with pytest.raises(CommandSyncError) as exc_info:
        await run_discord_daemon(settings)

    assert getattr(exc_info.value, "missing_dependency", None) == "command_tree_sync"


@pytest.mark.asyncio()
async def test_run_discord_daemon_missing_env_var_raises_settings_construction_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in REQUIRED_ENV_VARS:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(SettingsConstructionError) as exc_info:
        await run_discord_daemon()

    assert exc_info.value.missing_env_vars


def test_discord_runtime_read_shape() -> None:
    fields = DiscordRuntimeRead.model_fields
    expected = {"status", "api_base_url", "started_at", "missing_dependency"}
    assert expected.issubset(set(fields))
