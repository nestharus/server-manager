"""SLICE-009 WU-016B — Discord correlation-propagation adapter seam (AC4).

Pins the envelope-to-audit-context adapter (``build_request_context_from_envelope``)
as the single owner of ``InteractionEnvelope -> AuditContextRead`` mapping,
and proves end-to-end that Discord-originated API calls preserve correlation
context while leaving missing causation ids null rather than inventing them.

These tests exist so future refactors can't accidentally reintroduce an
inline construction path: the registry must delegate to the helper, and the
helper must round-trip ``causation_id=None`` without replacing it with a
freshly generated UUID.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from app.commands import InteractionRegistry
from app.contracts.api_transport import ApiTransportRequest
from app.contracts.audit import AuditContextRead
from app.contracts.interactions import InteractionEnvelope, InteractionResult
from app.core.context import build_audit_context  # noqa: F401 — imported to pin dependency
from app.core.request_context import build_request_context_from_envelope
from app.infrastructure.api_client import ApiClient


def _make_envelope(
    *,
    correlation_id: UUID,
    causation_id: UUID | None = None,
    command_name: str = "ping",
    arguments: dict[str, Any] | None = None,
) -> InteractionEnvelope:
    return InteractionEnvelope(
        interaction_id="interaction-1",
        correlation_id=correlation_id,
        causation_id=causation_id,
        actor_kind="discord_user",
        actor_id="1001",
        guild_id="900000000000000001",
        command_name=command_name,
        arguments=arguments if arguments is not None else {},
    )


def _build_client(
    transport: httpx.MockTransport, *, base_url: str = "http://stub.api"
) -> ApiClient:
    httpx_client = httpx.AsyncClient(transport=transport, base_url=base_url)
    return ApiClient(base_url=base_url, client=httpx_client)


# ---------------------------------------------------------------------------
# build_request_context_from_envelope — single-owner mapping
# ---------------------------------------------------------------------------


def test_build_request_context_from_envelope_preserves_correlation_id() -> None:
    """The helper must copy the envelope's ``correlation_id`` verbatim onto
    the resulting ``AuditContextRead``; it may never invent a new UUID."""

    correlation_id = uuid4()
    envelope = _make_envelope(correlation_id=correlation_id, causation_id=None)

    ctx = build_request_context_from_envelope(envelope)

    assert isinstance(ctx, AuditContextRead)
    assert ctx.correlation_id == correlation_id
    assert ctx.headers.x_correlation_id == correlation_id


def test_build_request_context_from_envelope_preserves_none_causation() -> None:
    """AC4: when the envelope has ``causation_id=None`` the adapter must
    preserve ``None`` — it must NOT invent a causation UUID locally."""

    envelope = _make_envelope(correlation_id=uuid4(), causation_id=None)

    ctx = build_request_context_from_envelope(envelope)

    assert ctx.causation_id is None
    assert ctx.headers.x_causation_id is None


def test_build_request_context_from_envelope_preserves_set_causation() -> None:
    """When the envelope carries a causation UUID, the adapter must preserve
    it verbatim on both the top-level and the nested headers projection."""

    correlation_id = uuid4()
    causation_id = uuid4()
    envelope = _make_envelope(
        correlation_id=correlation_id, causation_id=causation_id
    )

    ctx = build_request_context_from_envelope(envelope)

    assert ctx.correlation_id == correlation_id
    assert ctx.causation_id == causation_id
    assert ctx.headers.x_causation_id == causation_id


# ---------------------------------------------------------------------------
# InteractionRegistry.dispatch must go through the helper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_interaction_registry_uses_request_context_helper() -> None:
    """Dispatching an envelope with ``correlation=X, causation=None`` must
    seed the ambient audit context observed by the handler to exactly
    ``correlation=X, causation=None``. This pins that the registry flows
    through the named adapter rather than duplicating its own mapping that
    could drift from the helper's invariants."""

    registry = InteractionRegistry()
    captured: dict[str, AuditContextRead | None] = {}

    async def handler(envelope: InteractionEnvelope) -> InteractionResult:
        # Import inside the handler to make the lookup site explicit and
        # avoid stale imports in test modules under reorg.
        from app.core.context import get_current_audit_context

        captured["ctx"] = get_current_audit_context()
        return InteractionResult(success=True)

    registry.register("ping", handler)

    correlation_id = uuid4()
    envelope = _make_envelope(
        correlation_id=correlation_id,
        causation_id=None,
        command_name="ping",
    )

    await registry.dispatch(envelope)

    observed = captured["ctx"]
    assert observed is not None
    assert observed.correlation_id == correlation_id
    assert observed.causation_id is None
    assert observed.headers.x_correlation_id == correlation_id
    assert observed.headers.x_causation_id is None


# ---------------------------------------------------------------------------
# End-to-end AC4: request-context → ApiClient header shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_api_client_after_request_context_omits_null_causation_header(
    api_client_stub: httpx.MockTransport,
) -> None:
    """AC4 end-to-end: starting from a Discord envelope with
    ``causation_id=None``, setting the audit context via the adapter, and
    then issuing an API call, the outbound HTTP request must set
    ``X-Correlation-Id`` but NOT ``X-Causation-Id``."""

    from app.core.context import use_audit_context

    correlation_id = uuid4()
    envelope = _make_envelope(correlation_id=correlation_id, causation_id=None)
    ctx = build_request_context_from_envelope(envelope)

    client = _build_client(api_client_stub)
    request = ApiTransportRequest(method="GET", path="/api/v1/health")

    with use_audit_context(ctx):
        await client.call(request)

    recorded = api_client_stub.requests  # type: ignore[attr-defined]
    assert len(recorded) == 1
    sent = recorded[0]
    assert sent.headers.get("X-Correlation-Id") == str(correlation_id)
    assert "X-Causation-Id" not in sent.headers
