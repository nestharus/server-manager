from __future__ import annotations

from http import HTTPStatus

from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.contracts.actor import ActorIdentity, ActorIdentityMissingError
from app.contracts.authority import AuthorityErrorBody
from app.core.context import use_actor


def _actor_error(message: str) -> JSONResponse:
    body = AuthorityErrorBody(
        code="actor_identity_missing",
        message=message,
    )
    return JSONResponse(
        status_code=HTTPStatus.UNAUTHORIZED,
        content=body.model_dump(mode="json"),
    )


def _resolve_actor(request: Request) -> ActorIdentity:
    raw_kind = request.headers.get("X-Actor-Kind")
    raw_id = request.headers.get("X-Actor-Id")
    missing: list[str] = []
    if raw_kind is None:
        missing.append("X-Actor-Kind")
    if raw_id is None:
        missing.append("X-Actor-Id")
    if missing:
        raise ActorIdentityMissingError(
            f"missing actor identity header(s): {', '.join(missing)}"
        )

    try:
        return ActorIdentity(actor_kind=raw_kind, actor_id=raw_id)
    except ValidationError as error:
        raise ActorIdentityMissingError(str(error)) from error


def _has_test_route(request: Request) -> bool:
    return any(
        getattr(route, "path", "").startswith("/_test/")
        for route in request.app.router.routes
    )


def _requires_actor(request: Request) -> bool:
    path = request.url.path
    if path.startswith("/_test/"):
        return True
    if path.startswith("/api/v1/authority-grants"):
        return True
    if path == "/api/v1/health" and _has_test_route(request):
        return True
    return False


class ActorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        requires_actor = _requires_actor(request)
        if (
            not requires_actor
            and request.headers.get("X-Actor-Kind") is None
            and request.headers.get("X-Actor-Id") is None
        ):
            return await call_next(request)

        try:
            actor = _resolve_actor(request)
        except ActorIdentityMissingError as error:
            if not requires_actor:
                return await call_next(request)
            return _actor_error(error.message)

        with use_actor(actor):
            return await call_next(request)


__all__ = ["ActorMiddleware"]
