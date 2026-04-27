from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.contracts.web import CurrentPrincipalRead


router = APIRouter(prefix="/api/v1")


def _header(request: Request, name: str) -> str | None:
    value = request.headers.get(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def get_pomerium_principal(request: Request) -> CurrentPrincipalRead:
    subject = (
        _header(request, "x-pomerium-claim-sub")
        or _header(request, "x-pomerium-claim-email")
        or _header(request, "x-forwarded-email")
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
        email=_header(request, "x-pomerium-claim-email") or _header(request, "x-forwarded-email"),
        display_name=_header(request, "x-pomerium-claim-name"),
    )


@router.get("/me", response_model=CurrentPrincipalRead)
def me(request: Request) -> CurrentPrincipalRead:
    return get_pomerium_principal(request)
