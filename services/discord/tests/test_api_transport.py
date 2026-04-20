"""WU-009D / AC3: Discord → API transport with correlation propagation.

Tests fail now and pass after the SLICE-006 code agent implements:
- `app.contracts.api_transport` with `ApiTransportRequest`, `ApiTransportResponse`,
  `ApiTransportError`, `ApiUnreachableError`
- `app.infrastructure.api_client.ApiClient`
- `app.core.context` with `use_audit_context`, `MissingCorrelationContextError`
  and a Discord-local `AuditContextRead`
"""

from __future__ import annotations

from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.contracts.api_transport import (
    ApiTransportError,
    ApiTransportRequest,
    ApiTransportResponse,
    ApiUnreachableError,  # noqa: F401 — imported to assert contract symbol exists
)
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.core.context import MissingCorrelationContextError, use_audit_context
from app.infrastructure.api_client import ApiClient


def _make_audit_context(
    *,
    correlation_id: UUID,
    causation_id: UUID | None = None,
) -> AuditContextRead:
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=causation_id,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=causation_id,
        ),
    )


def _build_client(
    transport: httpx.MockTransport, *, base_url: str = "http://stub.api"
) -> ApiClient:
    httpx_client = httpx.AsyncClient(transport=transport, base_url=base_url)
    return ApiClient(base_url=base_url, client=httpx_client)


@pytest.mark.asyncio()
async def test_api_client_sets_correlation_headers_from_context_var(
    api_client_stub: httpx.MockTransport,
) -> None:
    client = _build_client(api_client_stub)
    correlation_id = uuid4()
    request = ApiTransportRequest(method="GET", path="/api/v1/health")

    with use_audit_context(_make_audit_context(correlation_id=correlation_id)):
        await client.call(request)

    recorded = api_client_stub.requests  # type: ignore[attr-defined]
    assert len(recorded) == 1
    assert recorded[0].headers.get("X-Correlation-Id") == str(correlation_id)


@pytest.mark.asyncio()
async def test_api_client_sets_causation_header_when_present(
    api_client_stub: httpx.MockTransport,
) -> None:
    client = _build_client(api_client_stub)
    correlation_id = uuid4()
    causation_id = uuid4()
    request = ApiTransportRequest(method="GET", path="/api/v1/health")

    with use_audit_context(
        _make_audit_context(
            correlation_id=correlation_id, causation_id=causation_id
        )
    ):
        await client.call(request)

    recorded = api_client_stub.requests  # type: ignore[attr-defined]
    assert len(recorded) == 1
    assert recorded[0].headers.get("X-Causation-Id") == str(causation_id)


@pytest.mark.asyncio()
async def test_api_client_omits_causation_header_when_none(
    api_client_stub: httpx.MockTransport,
) -> None:
    client = _build_client(api_client_stub)
    correlation_id = uuid4()
    request = ApiTransportRequest(method="GET", path="/api/v1/health")

    with use_audit_context(
        _make_audit_context(correlation_id=correlation_id, causation_id=None)
    ):
        await client.call(request)

    recorded = api_client_stub.requests  # type: ignore[attr-defined]
    assert len(recorded) == 1
    assert "X-Causation-Id" not in recorded[0].headers


@pytest.mark.asyncio()
async def test_api_client_raises_missing_correlation_context_error_without_context(
    api_client_stub: httpx.MockTransport,
) -> None:
    client = _build_client(api_client_stub)
    request = ApiTransportRequest(method="GET", path="/api/v1/health")

    with pytest.raises(MissingCorrelationContextError):
        await client.call(request)


@pytest.mark.asyncio()
async def test_api_client_returns_typed_response(
    api_client_stub: httpx.MockTransport,
) -> None:
    api_client_stub.queue_response(  # type: ignore[attr-defined]
        status_code=200, json={"ok": True}
    )
    client = _build_client(api_client_stub)
    request = ApiTransportRequest(method="GET", path="/api/v1/health")

    with use_audit_context(_make_audit_context(correlation_id=uuid4())):
        response = await client.call(request)

    assert isinstance(response, ApiTransportResponse)
    assert response.status == 200
    assert response.body == {"ok": True}
    assert isinstance(response.headers, dict)


def test_api_transport_request_validates_method() -> None:
    with pytest.raises(ValidationError):
        ApiTransportRequest(method="HEAD", path="/api/v1/health")  # type: ignore[arg-type]


@pytest.mark.asyncio()
async def test_api_client_propagates_error_status(
    api_client_stub: httpx.MockTransport,
) -> None:
    api_client_stub.queue_response(  # type: ignore[attr-defined]
        status_code=503, json={"detail": "unavailable"}
    )
    client = _build_client(api_client_stub)
    request = ApiTransportRequest(method="GET", path="/api/v1/ready")

    with use_audit_context(_make_audit_context(correlation_id=uuid4())):
        with pytest.raises(ApiTransportError):
            await client.call(request)

    api_client_stub.queue_response(  # type: ignore[attr-defined]
        status_code=404, json={"detail": "not found"}
    )
    with use_audit_context(_make_audit_context(correlation_id=uuid4())):
        response = await client.call(
            ApiTransportRequest(method="GET", path="/api/v1/missing")
        )

    assert isinstance(response, ApiTransportResponse)
    assert response.status == 404
