from __future__ import annotations

import json
import logging
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, ValidationError

from app.contracts.authz import CedarAuthorizationDecision

logger = logging.getLogger(__name__)


class CedarAuthorizationUnavailableError(RuntimeError):
    pass


class CedarAuthorizationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    principal: str
    action: str
    resource: str

    def to_payload(self) -> dict[str, str]:
        return self.model_dump()


class CedarAuthorizationClient:
    def __init__(self, base_url: str, *, timeout_seconds: float = 2.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def is_authorized(self, request: CedarAuthorizationRequest) -> CedarAuthorizationDecision:
        payload = json.dumps(request.to_payload()).encode("utf-8")
        http_request = Request(
            f"{self._base_url}/v1/is_authorized",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(http_request, timeout=self._timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            logger.warning("Cedar HTTP error %s: %s", exc.code, body)
            raise CedarAuthorizationUnavailableError(
                f"Cedar returned HTTP {exc.code}: {body}"
            ) from exc
        except URLError as exc:
            logger.warning("Cedar network error: %s", exc)
            raise CedarAuthorizationUnavailableError(str(exc)) from exc
        except (socket.timeout, TimeoutError) as exc:
            logger.warning(
                "Cedar request timed out after %s seconds",
                self._timeout_seconds,
            )
            raise CedarAuthorizationUnavailableError(
                f"Cedar request timed out after {self._timeout_seconds} seconds"
            ) from exc

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise CedarAuthorizationUnavailableError("invalid Cedar response") from exc
        try:
            return CedarAuthorizationDecision.model_validate(data)
        except ValidationError as exc:
            raise CedarAuthorizationUnavailableError(
                "invalid Cedar response schema"
            ) from exc
