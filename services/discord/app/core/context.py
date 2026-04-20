from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator
from uuid import UUID

from app.contracts.audit import AuditContextRead, CorrelationHeadersRead


CURRENT_AUDIT_CONTEXT: ContextVar[AuditContextRead | None] = ContextVar(
    "CURRENT_AUDIT_CONTEXT",
    default=None,
)


class MissingCorrelationContextError(Exception):
    def __init__(self) -> None:
        super().__init__("missing correlation context")


def get_current_audit_context() -> AuditContextRead | None:
    return CURRENT_AUDIT_CONTEXT.get()


def build_audit_context(
    *,
    correlation_id: UUID,
    causation_id: UUID | None,
) -> AuditContextRead:
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=causation_id,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=causation_id,
        ),
    )


@contextmanager
def use_audit_context(ctx: AuditContextRead) -> Iterator[None]:
    token = CURRENT_AUDIT_CONTEXT.set(ctx)
    try:
        yield
    finally:
        CURRENT_AUDIT_CONTEXT.reset(token)


__all__ = [
    "CURRENT_AUDIT_CONTEXT",
    "MissingCorrelationContextError",
    "build_audit_context",
    "get_current_audit_context",
    "use_audit_context",
]
