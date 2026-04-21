"""Discord daemon package entry point."""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime
from urllib.parse import urlparse

import discord
import httpx

from app.contracts.api_transport import ApiUnreachableError
from app.commands import (
    register_application_review_commands,
    register_application_submission_commands,
    register_chapter_commands,
    register_ticket_commands,
)
from app.contracts.runtime import CommandSyncError, DiscordLoginError, DiscordRuntimeRead
from app.core.bot import HumilityBot
from app.core.settings import (
    Settings,
    SettingsConstructionError,
    load_settings as _core_load_settings,
)
from app.infrastructure.api_client import ApiClient


logger = logging.getLogger(__name__)

_CORE_SETTINGS_TYPE = Settings


def load_settings() -> Settings:
    if Settings is _CORE_SETTINGS_TYPE:
        return _core_load_settings()
    return Settings()


async def check_api_reachability(
    *,
    base_url: str,
    client: httpx.AsyncClient,
) -> None:
    try:
        response = await client.get("/api/v1/health")
    except httpx.HTTPError as error:
        raise ApiUnreachableError(
            base_url=base_url,
            reason=str(error) or error.__class__.__name__,
        ) from error
    if response.status_code >= 400:
        raise ApiUnreachableError(
            base_url=base_url,
            reason=f"health probe returned status {response.status_code}",
        )


def build_api_client(*, settings: Settings, client: httpx.AsyncClient) -> ApiClient:
    return ApiClient(base_url=settings.api_base_url, client=client)


def build_bot_with_registry(*, settings: Settings, api_client: ApiClient) -> HumilityBot:
    bot = HumilityBot(settings, api_client=api_client)
    if hasattr(bot, "register_interaction_handler"):
        register_application_review_commands(bot)
        register_application_submission_commands(bot)
        register_chapter_commands(bot)
        register_ticket_commands(bot)
    return bot


async def sync_command_tree(bot: HumilityBot) -> None:
    registry = getattr(bot, "registry", None)
    if registry is None or not hasattr(registry, "has_handlers") or not registry.has_handlers():
        return
    try:
        await bot.tree.sync(guild=discord.Object(id=bot.settings.discord_guild_id))
    except discord.DiscordException as error:
        raise CommandSyncError(reason=str(error) or error.__class__.__name__) from error


async def run_discord_daemon(settings: Settings | None = None) -> DiscordRuntimeRead:
    resolved_settings = settings if settings is not None else load_settings()
    started_at = datetime.now(tz=UTC)

    async with httpx.AsyncClient(
        base_url=resolved_settings.api_base_url,
        timeout=2.0,
    ) as http_client:
        await check_api_reachability(
            base_url=resolved_settings.api_base_url,
            client=http_client,
        )
        api_client = build_api_client(settings=resolved_settings, client=http_client)
        bot = build_bot_with_registry(settings=resolved_settings, api_client=api_client)

        try:
            try:
                await bot.start(resolved_settings.discord_bot_token)
                # Note: in production with a live Discord gateway,
                # bot.start() does not return until disconnect, so
                # command-tree sync must happen via Bot.setup_hook when
                # concrete handlers ship in a later slice. Phase 0
                # registers no handlers and so this call is a no-op
                # either during start (test stub path) or after
                # disconnect (production).
                await sync_command_tree(bot)
            except KeyboardInterrupt:
                return DiscordRuntimeRead(
                    status="stopped",
                    api_base_url=resolved_settings.api_base_url,
                    started_at=started_at,
                    missing_dependency=None,
                )
            except (
                discord.LoginFailure,
                discord.GatewayNotFound,
                discord.PrivilegedIntentsRequired,
            ) as error:
                raise DiscordLoginError(
                    reason=str(error) or error.__class__.__name__
                ) from error
        finally:
            await bot.close()

    return DiscordRuntimeRead(
        status="stopped",
        api_base_url=resolved_settings.api_base_url,
        started_at=started_at,
        missing_dependency=None,
    )


async def main() -> int:
    """Run the Discord daemon."""
    discord.utils.setup_logging()
    try:
        settings = load_settings()
    except SettingsConstructionError as exc:
        if exc.missing_env_vars:
            logger.exception(
                "Failed to construct Discord settings. Missing required env vars: %s",
                ", ".join(exc.missing_env_vars),
            )
        else:
            logger.exception("Failed to construct Discord settings.")
        return 1

    try:
        runtime = await run_discord_daemon(settings)
    except KeyboardInterrupt:
        return 0
    except (ApiUnreachableError, DiscordLoginError, CommandSyncError):
        logger.exception("Discord daemon failed to start.")
        return 1

    return 0 if runtime.missing_dependency is None else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
