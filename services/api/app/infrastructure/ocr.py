from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict


class OcrExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str
    extracted_fields: dict[str, Any]
    confidence: Decimal


class OcrProvider(Protocol):
    async def extract(
        self,
        attachment_ref: str,
        rule_hint: str | None = None,
    ) -> OcrExtractionResult: ...


class OcrProviderNotConfiguredError(Exception):
    def __init__(self) -> None:
        super().__init__("OCR provider not configured")


class StubOcrProvider:
    async def extract(
        self,
        attachment_ref: str,
        rule_hint: str | None = None,
    ) -> OcrExtractionResult:
        raise OcrProviderNotConfiguredError()


__all__ = [
    "OcrExtractionResult",
    "OcrProvider",
    "OcrProviderNotConfiguredError",
    "StubOcrProvider",
]
