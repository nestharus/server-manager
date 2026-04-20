from __future__ import annotations

from typing import Any

import httpx

from app.contracts.api_transport import (
    ApiTransportError,
    ApiTransportRequest,
    ApiTransportResponse,
    ApiUnreachableError,
)
from app.core.context import MissingCorrelationContextError, get_current_audit_context


class ApiClient:
    def __init__(self, *, base_url: str, client: httpx.AsyncClient) -> None:
        self._base_url = base_url
        self._client = client

    @property
    def base_url(self) -> str:
        return self._base_url

    async def call(self, request: ApiTransportRequest) -> ApiTransportResponse:
        ctx = get_current_audit_context()
        if ctx is None:
            raise MissingCorrelationContextError()

        headers = {"X-Correlation-Id": str(ctx.correlation_id)}
        if ctx.causation_id is not None:
            headers["X-Causation-Id"] = str(ctx.causation_id)

        try:
            response = await self._client.request(
                method=request.method,
                url=request.path,
                params=request.query,
                json=request.body,
                headers=headers,
            )
        except httpx.HTTPError as error:
            raise ApiUnreachableError(
                base_url=self._base_url,
                reason=str(error) or error.__class__.__name__,
            ) from error

        body = _response_body(response)
        typed_response = ApiTransportResponse(
            status=response.status_code,
            body=body,
            headers=dict(response.headers),
        )

        if response.status_code >= 500:
            raise ApiTransportError(
                status=response.status_code,
                body=body,
                reason=f"API returned status {response.status_code}",
            )

        return typed_response


def _response_body(response: httpx.Response) -> dict[str, Any] | None:
    if not response.content:
        return None
    try:
        payload = response.json()
    except ValueError:
        return {"detail": response.text}
    if isinstance(payload, dict):
        return payload
    return {"detail": payload}


__all__ = ["ApiClient"]
