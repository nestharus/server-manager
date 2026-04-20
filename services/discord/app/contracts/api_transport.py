from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiTransportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"]
    path: str = Field(min_length=1)
    query: dict[str, str] | None = None
    body: dict[str, Any] | None = None


class ApiTransportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: int
    body: dict[str, Any] | None = None
    headers: dict[str, str]


class ApiTransportError(Exception):
    def __init__(
        self,
        *,
        status: int,
        body: dict[str, Any] | None,
        reason: str,
    ) -> None:
        self.status = status
        self.body = body
        self.reason = reason
        super().__init__(reason)


class ApiUnreachableError(Exception):
    def __init__(
        self,
        *,
        base_url: str,
        reason: str,
        missing_dependency: str = "api_reachability",
    ) -> None:
        self.base_url = base_url
        self.reason = reason
        self.missing_dependency = missing_dependency
        super().__init__(f"{base_url}: {reason}")


__all__ = [
    "ApiTransportError",
    "ApiTransportRequest",
    "ApiTransportResponse",
    "ApiUnreachableError",
]
