"""WU-009C / AC4: Discord interaction registry + dispatch.

Tests fail now and pass after the SLICE-006 code agent implements:
- `app.contracts.interactions` with `InteractionEnvelope`, `InteractionResult`,
  `DuplicateHandlerError`, `HandlerNotFoundError`
- `app.commands.InteractionRegistry` (re-exported from `commands/__init__.py`)
- `app.core.context` with `CURRENT_AUDIT_CONTEXT`, `use_audit_context`
- `HumilityBot.register_interaction_handler` + `HumilityBot.dispatch_interaction`
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.commands import InteractionRegistry
from app.contracts.interactions import (
    DuplicateHandlerError,
    HandlerNotFoundError,
    InteractionEnvelope,
    InteractionResult,
)
from app.core.bot import HumilityBot
from app.core.context import CURRENT_AUDIT_CONTEXT


def _make_envelope(
    *,
    correlation_id: UUID | None = None,
    command_name: str = "ping",
    arguments: dict[str, Any] | None = None,
) -> InteractionEnvelope:
    return InteractionEnvelope(
        interaction_id="interaction-1",
        correlation_id=correlation_id if correlation_id is not None else uuid4(),
        causation_id=None,
        actor_kind="discord_user",
        actor_id="1001",
        guild_id="900000000000000001",
        command_name=command_name,
        arguments=arguments if arguments is not None else {},
    )


@pytest.mark.asyncio()
async def test_interaction_registry_register_and_dispatch() -> None:
    registry = InteractionRegistry()
    seen: list[InteractionEnvelope] = []

    async def handler(envelope: InteractionEnvelope) -> InteractionResult:
        seen.append(envelope)
        return InteractionResult(success=True, response_text="pong")

    registry.register("ping", handler)
    envelope = _make_envelope(command_name="ping")

    result = await registry.dispatch(envelope)

    assert isinstance(result, InteractionResult)
    assert result.success is True
    assert result.response_text == "pong"
    assert len(seen) == 1
    assert seen[0] is envelope


def test_interaction_registry_register_duplicate_raises() -> None:
    registry = InteractionRegistry()

    async def handler(envelope: InteractionEnvelope) -> InteractionResult:
        return InteractionResult(success=True)

    registry.register("ping", handler)
    with pytest.raises(DuplicateHandlerError):
        registry.register("ping", handler)


@pytest.mark.asyncio()
async def test_interaction_registry_dispatch_unknown_raises() -> None:
    registry = InteractionRegistry()
    envelope = _make_envelope(command_name="does-not-exist")

    with pytest.raises(HandlerNotFoundError):
        await registry.dispatch(envelope)


def test_interaction_envelope_contract_shape() -> None:
    fields = InteractionEnvelope.model_fields
    expected = {
        "interaction_id",
        "correlation_id",
        "causation_id",
        "actor_kind",
        "actor_id",
        "guild_id",
        "command_name",
        "arguments",
    }
    assert expected.issubset(set(fields))


def test_interaction_result_defaults_to_ephemeral() -> None:
    result = InteractionResult(success=True)
    assert result.ephemeral is True
    assert result.response_text is None


@pytest.mark.asyncio()
async def test_dispatch_wraps_handler_in_audit_context() -> None:
    registry = InteractionRegistry()
    captured: dict[str, Any] = {}

    async def handler(envelope: InteractionEnvelope) -> InteractionResult:
        ctx = CURRENT_AUDIT_CONTEXT.get()
        captured["ctx"] = ctx
        return InteractionResult(success=True)

    registry.register("ping", handler)
    correlation_id = uuid4()
    envelope = _make_envelope(
        correlation_id=correlation_id, command_name="ping"
    )

    await registry.dispatch(envelope)

    ctx = captured["ctx"]
    assert ctx is not None
    assert ctx.correlation_id == correlation_id


@pytest.mark.asyncio()
async def test_bot_dispatch_interaction_uses_registry(
    bot: HumilityBot,
    interaction_factory: Callable[..., Any],
) -> None:
    calls: list[InteractionEnvelope] = []

    async def handler(envelope: InteractionEnvelope) -> InteractionResult:
        calls.append(envelope)
        return InteractionResult(success=True, response_text="pong")

    bot.register_interaction_handler("ping", handler)

    raw = interaction_factory()
    raw.id = "interaction-42"
    raw.data = {"name": "ping", "options": []}

    await bot.dispatch_interaction(raw)

    assert len(calls) == 1
    assert calls[0].command_name == "ping"
