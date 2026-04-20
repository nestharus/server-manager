from __future__ import annotations

from app.contracts.interactions import (
    DuplicateHandlerError,
    HandlerNotFoundError,
    InteractionEnvelope,
    InteractionHandler,
    InteractionResult,
)
from app.core.context import use_audit_context
from app.core.request_context import build_request_context_from_envelope


class InteractionRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, InteractionHandler] = {}

    def register(
        self,
        command_name: str,
        handler: InteractionHandler,
    ) -> InteractionHandler:
        if command_name in self._handlers:
            raise DuplicateHandlerError(command_name)
        self._handlers[command_name] = handler
        return handler

    async def dispatch(self, envelope: InteractionEnvelope) -> InteractionResult:
        handler = self._handlers.get(envelope.command_name)
        if handler is None:
            raise HandlerNotFoundError(envelope.command_name)
        with use_audit_context(build_request_context_from_envelope(envelope)):
            return await handler(envelope)

    def has_handlers(self) -> bool:
        return bool(self._handlers)


__all__ = ["InteractionRegistry"]
