import asyncio
import importlib.util
import inspect
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

try:
    import discord
    from discord.ext import commands
except ModuleNotFoundError:  # pragma: no cover - dependency should exist in normal test runs
    discord = None
    commands = None


DAEMON_ENTRY_PATH = Path(__file__).resolve().parents[1] / "daemon.py"
EXPECTED_ENV_PATH = DAEMON_ENTRY_PATH.with_name(".env")
EXPECTED_BASE_PATH = DAEMON_ENTRY_PATH.resolve().parent
EXPECTED_GUILD_ID = 900000000000000001


def run(coro):
    return asyncio.run(coro)


def import_daemon_entry(monkeypatch, *, dotenv_loader=None):
    if not DAEMON_ENTRY_PATH.exists():
        pytest.fail(f"Could not import daemon.py: {DAEMON_ENTRY_PATH} does not exist")

    loader = dotenv_loader or Mock()
    monkeypatch.setattr("dotenv.load_dotenv", loader)

    module_name = "daemon_entry_under_test"
    sys.modules.pop(module_name, None)

    spec = importlib.util.spec_from_file_location(module_name, DAEMON_ENTRY_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        pytest.fail(f"Could not import daemon.py: missing module spec for {DAEMON_ENTRY_PATH}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover - import failures should fail loudly
        pytest.fail(f"Could not import daemon.py: {exc!r}")

    return module, loader


def require_runtime_config_loader(module):
    for name in ("get_config", "get_runtime_config", "load_runtime_config"):
        loader = getattr(module, name, None)
        if loader is not None:
            if not callable(loader):
                pytest.fail(f"daemon.py {name} must be callable")
            return loader
    pytest.fail(
        "Missing expected config helper. Tried: "
        "daemon.py:get_config, daemon.py:get_runtime_config, daemon.py:load_runtime_config"
    )


def require_intents_builder(module):
    for name in ("build_intents", "make_intents"):
        builder = getattr(module, name, None)
        if builder is not None:
            if not callable(builder):
                pytest.fail(f"daemon.py {name} must be callable")
            return builder
    pytest.fail("Missing expected intents helper. Tried: daemon.py:build_intents, daemon.py:make_intents")


def require_bot_subclass(module):
    if commands is None:  # pragma: no cover - defensive
        pytest.fail("discord.ext.commands is required for daemon entry tests")

    matches = [
        (name, value)
        for name, value in vars(module).items()
        if inspect.isclass(value) and issubclass(value, commands.Bot) and value is not commands.Bot
    ]

    if not matches:
        pytest.fail("daemon.py must define a commands.Bot subclass for startup-owned state")
    if len(matches) > 1:
        names = ", ".join(name for name, _ in matches)
        pytest.fail(f"daemon.py defines multiple Bot subclasses; expected exactly one. Found: {names}")
    return matches[0]


def patch_attr_if_present(monkeypatch, owner, name, replacement):
    if hasattr(owner, name):
        monkeypatch.setattr(owner, name, replacement)


def test_module_loads_repo_local_dotenv(monkeypatch):
    _, dotenv_loader = import_daemon_entry(monkeypatch)

    dotenv_loader.assert_called_once_with(EXPECTED_ENV_PATH)


def test_runtime_config_requires_discord_bot_token(monkeypatch):
    module, _ = import_daemon_entry(monkeypatch)
    get_config = require_runtime_config_loader(module)

    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.setenv("DISCORD_GUILD_ID", str(EXPECTED_GUILD_ID))
    monkeypatch.delenv("DATABASE_PATH", raising=False)

    with pytest.raises(RuntimeError, match="DISCORD_BOT_TOKEN"):
        get_config()


def test_runtime_config_requires_discord_guild_id(monkeypatch):
    module, _ = import_daemon_entry(monkeypatch)
    get_config = require_runtime_config_loader(module)

    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    monkeypatch.delenv("DISCORD_GUILD_ID", raising=False)
    monkeypatch.delenv("DATABASE_PATH", raising=False)

    with pytest.raises(RuntimeError, match="DISCORD_GUILD_ID"):
        get_config()


def test_runtime_config_requires_integer_discord_guild_id(monkeypatch):
    module, _ = import_daemon_entry(monkeypatch)
    get_config = require_runtime_config_loader(module)

    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    monkeypatch.setenv("DISCORD_GUILD_ID", "not-an-int")
    monkeypatch.delenv("DATABASE_PATH", raising=False)

    with pytest.raises(RuntimeError, match="DISCORD_GUILD_ID"):
        get_config()


def test_bot_subclass_owns_setup_hook_for_command_sync(monkeypatch):
    module, _ = import_daemon_entry(monkeypatch)
    _, bot_type = require_bot_subclass(module)

    setup_hook = getattr(bot_type, "setup_hook", None)
    if setup_hook is None:
        pytest.fail("Bot subclass must define setup_hook() for guild command registration and sync")
    assert inspect.iscoroutinefunction(setup_hook)


def test_build_intents_enables_guilds_and_members_without_message_content(monkeypatch):
    if discord is None:  # pragma: no cover - defensive
        pytest.fail("discord.py must be installed for daemon entry tests")

    module, _ = import_daemon_entry(monkeypatch)
    build_intents = require_intents_builder(module)

    default_intents = discord.Intents.none()
    default_intents.guilds = False
    default_intents.members = False
    default_intents.message_content = False
    default_spy = Mock(return_value=default_intents)
    monkeypatch.setattr(module.discord.Intents, "default", default_spy)

    intents = build_intents()

    default_spy.assert_called_once_with()
    assert intents is default_intents
    assert intents.guilds is True
    assert intents.members is True
    assert intents.message_content is False


def test_main_uses_repo_root_default_database_path_and_always_closes_db(monkeypatch):
    module, _ = import_daemon_entry(monkeypatch)
    bot_class_name, _ = require_bot_subclass(module)

    sentinel_config = object()
    connection = Mock()
    connection.execute = Mock()
    load_config = Mock(return_value=sentinel_config)
    open_database = Mock(return_value=connection)
    close_database = Mock()
    build_intents = Mock(return_value=object())

    patch_attr_if_present(monkeypatch, module, "load_config", load_config)
    patch_attr_if_present(monkeypatch, module, "open_database", open_database)
    patch_attr_if_present(monkeypatch, module, "close_database", close_database)
    patch_attr_if_present(monkeypatch, module, "build_intents", build_intents)
    monkeypatch.setattr("daemon.config.load_config", load_config)
    monkeypatch.setattr("daemon.db.open_database", open_database)
    monkeypatch.setattr("daemon.db.close_database", close_database)

    forbidden_resolver = Mock(side_effect=AssertionError("daemon.py must not call resolve_database_config()"))
    patch_attr_if_present(monkeypatch, module, "resolve_database_config", forbidden_resolver)
    monkeypatch.setattr("daemon.db.resolve_database_config", forbidden_resolver)

    constructed = []

    class FakeBot:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.start = AsyncMock(side_effect=RuntimeError("gateway start failed"))
            self.close = AsyncMock()
            constructed.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(module, bot_class_name, FakeBot)
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    monkeypatch.setenv("DISCORD_GUILD_ID", str(EXPECTED_GUILD_ID))
    monkeypatch.delenv("DATABASE_PATH", raising=False)

    with pytest.raises(RuntimeError, match="gateway start failed"):
        run(module.main())

    load_config.assert_called_once_with(EXPECTED_BASE_PATH)
    open_database.assert_called_once_with(EXPECTED_BASE_PATH / "discord.db")
    close_database.assert_called_once_with(connection)
    build_intents.assert_called_once_with()
    assert any(
        "busy_timeout" in call.args[0].lower() and "5000" in call.args[0]
        for call in connection.execute.call_args_list
    )

    assert len(constructed) == 1
    constructor_values = list(constructed[0].args) + list(constructed[0].kwargs.values())
    assert EXPECTED_GUILD_ID in constructor_values
    assert sentinel_config in constructor_values
    assert connection in constructor_values
    assert build_intents.return_value in constructor_values
    assert constructed[0].start.await_args.args[0] == "token"


def test_main_prefers_database_path_from_environment(monkeypatch):
    module, _ = import_daemon_entry(monkeypatch)
    bot_class_name, _ = require_bot_subclass(module)

    events = []
    db_path = Path("/tmp/custom-daemon.db")
    sentinel_config = object()
    connection = Mock()
    connection.execute = Mock()

    def load_config(base_path):
        events.append(("config", base_path))
        return sentinel_config

    def open_database(path):
        events.append(("open_database", path))
        return connection

    def close_database(conn):
        events.append(("close_database", conn))

    build_intents = Mock(return_value=object())

    patch_attr_if_present(monkeypatch, module, "load_config", load_config)
    patch_attr_if_present(monkeypatch, module, "open_database", open_database)
    patch_attr_if_present(monkeypatch, module, "close_database", close_database)
    patch_attr_if_present(monkeypatch, module, "build_intents", build_intents)
    monkeypatch.setattr("daemon.config.load_config", load_config)
    monkeypatch.setattr("daemon.db.open_database", open_database)
    monkeypatch.setattr("daemon.db.close_database", close_database)

    class FakeBot:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.start = AsyncMock(side_effect=self._start)
            self.close = AsyncMock()

        async def _start(self, token, *args, **kwargs):
            events.append(("start", token))

        async def __aenter__(self):
            events.append(("enter_bot", None))
            return self

        async def __aexit__(self, exc_type, exc, tb):
            events.append(("exit_bot", exc_type))
            return False

    monkeypatch.setattr(module, bot_class_name, FakeBot)
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    monkeypatch.setenv("DISCORD_GUILD_ID", str(EXPECTED_GUILD_ID))
    monkeypatch.setenv("DATABASE_PATH", str(db_path))

    run(module.main())

    assert events[:3] == [
        ("config", EXPECTED_BASE_PATH),
        ("open_database", db_path),
        ("enter_bot", None),
    ]
    assert ("start", "token") in events
    assert events[-1] == ("close_database", connection)
