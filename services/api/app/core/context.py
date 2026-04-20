from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator
from uuid import UUID, uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead


logger = logging.getLogger(__name__)

CURRENT_AUDIT_CONTEXT: ContextVar[AuditContextRead | None] = ContextVar(
    "CURRENT_AUDIT_CONTEXT",
    default=None,
)


class MissingCorrelationContextError(Exception):
    def __init__(self) -> None:
        super().__init__("missing correlation context")


def get_current_audit_context() -> AuditContextRead | None:
    return CURRENT_AUDIT_CONTEXT.get()


def resolve_register_correlation(
    explicit: UUID | None,
    *,
    allow_new_root: bool,
) -> AuditContextRead:
    if explicit is not None:
        return AuditContextRead(
            correlation_id=explicit,
            causation_id=None,
            headers=CorrelationHeadersRead(
                x_correlation_id=explicit,
                x_causation_id=None,
            ),
        )

    current = get_current_audit_context()
    if current is not None:
        return current

    if not allow_new_root:
        raise MissingCorrelationContextError()

    correlation_id = uuid4()
    logger.warning(
        "missing registration correlation context; generated root correlation %s",
        correlation_id,
    )
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=None,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=None,
        ),
    )


@contextmanager
def use_audit_context(ctx: AuditContextRead) -> Iterator[None]:
    token = CURRENT_AUDIT_CONTEXT.set(ctx)
    try:
        yield
    finally:
        CURRENT_AUDIT_CONTEXT.reset(token)


def _parse_header_uuid(value: str | None) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        raw_correlation = request.headers.get("X-Correlation-Id")
        correlation_id = _parse_header_uuid(raw_correlation)
        if correlation_id is None:
            correlation_id = uuid4()
            if raw_correlation is None:
                logger.warning("missing X-Correlation-Id; generated root correlation")
            else:
                logger.warning("malformed X-Correlation-Id %r; generated root correlation", raw_correlation)

        causation_id = _parse_header_uuid(request.headers.get("X-Causation-Id"))
        ctx = AuditContextRead(
            correlation_id=correlation_id,
            causation_id=causation_id,
            headers=CorrelationHeadersRead(
                x_correlation_id=correlation_id,
                x_causation_id=causation_id,
            ),
        )

        with use_audit_context(ctx):
            response = await call_next(request)

        response.headers["X-Correlation-Id"] = str(correlation_id)
        if causation_id is not None:
            response.headers["X-Causation-Id"] = str(causation_id)
        return response


__all__ = [
    "CURRENT_AUDIT_CONTEXT",
    "CorrelationMiddleware",
    "MissingCorrelationContextError",
    "get_current_audit_context",
    "resolve_register_correlation",
    "use_audit_context",
]
