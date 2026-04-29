from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request

from app.contracts.web import CurrentPrincipalRead


router = APIRouter(prefix="/api/v1")


def _header(request: Request, name: str) -> str | None:
    value = request.headers.get(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def _parse_pomerium_groups(value: str | None) -> list[str]:
    if value is None:
        return []
    stripped = value.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        try:
            decoded = json.loads(stripped)
        except json.JSONDecodeError:
            return []
        if isinstance(decoded, list) and all(isinstance(item, str) for item in decoded):
            return [item.strip() for item in decoded if item.strip()]
        return []
    return [part.strip() for part in stripped.split(",") if part.strip()]


def get_pomerium_principal(request: Request) -> CurrentPrincipalRead:
    subject = _header(request, "x-pomerium-claim-sub") or _header(
        request, "x-pomerium-claim-email"
    )
    if subject is None:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "identity_missing",
                "message": "Pomerium identity header is required",
            },
        )
    return CurrentPrincipalRead(
        subject=subject,
        email=_header(request, "x-pomerium-claim-email"),
        display_name=_header(request, "x-pomerium-claim-name"),
        groups=_parse_pomerium_groups(request.headers.get("x-pomerium-claim-groups")),
        discord_user_id=_header(request, "x-pomerium-claim-discord-user-id"),
    )


@router.get("/me", response_model=CurrentPrincipalRead)
def me(request: Request) -> CurrentPrincipalRead:
    return get_pomerium_principal(request)
