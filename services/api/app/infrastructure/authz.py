from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.contracts.authz import CedarAuthorizationDecision


class CedarAuthorizationUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class CedarAuthorizationRequest:
    principal: str
    action: str
    resource: str

    def to_payload(self) -> dict[str, str]:
        return {
            "principal": self.principal,
            "action": self.action,
            "resource": self.resource,
        }


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
        except URLError as exc:
            raise CedarAuthorizationUnavailableError(str(exc)) from exc

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise CedarAuthorizationUnavailableError("invalid Cedar response") from exc
        return CedarAuthorizationDecision.model_validate(data)

