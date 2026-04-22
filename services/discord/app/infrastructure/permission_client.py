from __future__ import annotations

from typing import Any
from uuid import UUID

from app.contracts.api_transport import (
    ApiTransportError,
    ApiTransportRequest,
    ApiTransportResponse,
)
from app.contracts.permissions import (
    DiscordPermissionSnapshotEntry,
    DiscordReconciliationRunRead,
)
from app.infrastructure.api_client import ApiClient


SERVICE_ACTOR_ID = "permission-reconciler"


class PermissionApiHttpError(Exception):
    def __init__(
        self,
        *,
        status: int,
        reason: str,
        body: dict[str, Any] | None = None,
    ) -> None:
        self.status = status
        self.reason = reason
        self.body = body
        super().__init__(f"{status}: {reason}")


class PermissionApiConflictError(PermissionApiHttpError):
    pass


class PermissionApiPreconditionFailedError(PermissionApiHttpError):
    pass


def _parse_reason(response: ApiTransportResponse) -> str:
    body = response.body or {}
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, dict):
        message = detail.get("message")
        if isinstance(message, str):
            return message
    return f"API returned status {response.status}"


def _raise_for_status(response: ApiTransportResponse) -> None:
    if response.status < 400:
        return
    reason = _parse_reason(response)
    if response.status == 409:
        raise PermissionApiConflictError(
            status=response.status, reason=reason, body=response.body,
        )
    if response.status == 412:
        raise PermissionApiPreconditionFailedError(
            status=response.status, reason=reason, body=response.body,
        )
    raise PermissionApiHttpError(
        status=response.status, reason=reason, body=response.body,
    )


class PermissionApiClient:
    def __init__(
        self,
        api_client: ApiClient,
        *,
        service_actor_id: str = SERVICE_ACTOR_ID,
    ) -> None:
        self._api = api_client
        self._actor_id = service_actor_id

    def _service_headers(self) -> dict[str, str]:
        return {
            "X-Actor-Kind": "service",
            "X-Actor-Id": self._actor_id,
        }

    async def create_reconciliation_run(
        self,
        *,
        scope_kind: str,
        scope_id: str | None,
        originating_actor_kind: str,
        originating_actor_id: str,
    ) -> DiscordReconciliationRunRead:
        try:
            response = await self._api.call(
                ApiTransportRequest(
                    method="POST",
                    path="/api/v1/permission-reconciliation/runs",
                    headers=self._service_headers(),
                    body={
                        "scope_kind": scope_kind,
                        "scope_id": scope_id,
                        "originating_actor_kind": originating_actor_kind,
                        "originating_actor_id": originating_actor_id,
                    },
                )
            )
        except ApiTransportError as error:
            raise PermissionApiHttpError(
                status=error.status, reason=error.reason, body=error.body,
            ) from error
        _raise_for_status(response)
        return DiscordReconciliationRunRead.model_validate(response.body)

    async def submit_snapshot(
        self,
        *,
        run_id: UUID,
        entries: list[DiscordPermissionSnapshotEntry],
    ) -> DiscordReconciliationRunRead:
        try:
            response = await self._api.call(
                ApiTransportRequest(
                    method="POST",
                    path=f"/api/v1/permission-reconciliation/runs/{run_id}/snapshots",
                    headers=self._service_headers(),
                    body={
                        "entries": [
                            entry.model_dump(mode="json") for entry in entries
                        ],
                    },
                )
            )
        except ApiTransportError as error:
            raise PermissionApiHttpError(
                status=error.status, reason=error.reason, body=error.body,
            ) from error
        _raise_for_status(response)
        return DiscordReconciliationRunRead.model_validate(response.body)


__all__ = [
    "PermissionApiClient",
    "PermissionApiConflictError",
    "PermissionApiHttpError",
    "PermissionApiPreconditionFailedError",
    "SERVICE_ACTOR_ID",
]
