from __future__ import annotations

from app.contracts.audit import AuditContextRead
from app.contracts.interactions import InteractionEnvelope
from app.core.context import build_audit_context


def build_request_context_from_envelope(
    envelope: InteractionEnvelope,
) -> AuditContextRead:
    return build_audit_context(
        correlation_id=envelope.correlation_id,
        causation_id=envelope.causation_id,
    )


__all__ = ["build_request_context_from_envelope"]
