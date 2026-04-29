from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.core.settings import Settings
from app.services import applicant_discord_auth
from app.services.applicant_discord_auth import ApplicantAuthError, ApplicantReceiptError


router = APIRouter(prefix="/auth/discord", tags=["applicant-discord-auth"])


@router.get("/start")
def start_discord_auth(
    request: Request,
    return_to: Annotated[str, Query()] = "/applications",
) -> RedirectResponse:
    settings: Settings = request.app.state.settings
    flow = applicant_discord_auth.create_auth_flow(
        redirect_uri=settings.applicant_discord_redirect_uri,
        return_to=return_to,
    )
    _auth_flows(request)[flow.state] = flow
    authorize_url = applicant_discord_auth.build_authorize_url(
        authorize_url=settings.authentik_authorize_url,
        client_id=settings.applicant_oidc_client_id,
        flow=flow,
    )
    return RedirectResponse(authorize_url, status_code=302)


@router.get("/callback")
def discord_auth_callback(
    request: Request,
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    if not code or not state:
        raise HTTPException(status_code=400, detail="code and state are required")

    flow = _auth_flows(request).pop(state, None)
    if flow is None:
        raise HTTPException(status_code=400, detail="invalid state")

    settings: Settings = request.app.state.settings
    client_secret = settings.applicant_oidc_client_secret.get_secret_value()
    signing_key = settings.applicant_receipt_signing_key.get_secret_value()

    try:
        id_token = applicant_discord_auth.exchange_code_for_id_token(
            token_url=settings.authentik_token_url,
            code=code,
            client_id=settings.applicant_oidc_client_id,
            client_secret=client_secret,
            redirect_uri=flow.redirect_uri,
            code_verifier=flow.code_verifier,
        )
        claims = applicant_discord_auth.validate_id_token(
            id_token=id_token,
            jwks_url=settings.authentik_jwks_url,
            issuer_url=settings.authentik_issuer_url,
            audience=settings.applicant_oidc_client_id,
        )
        receipt = applicant_discord_auth.sign_applicant_receipt(
            discord_user_id=claims["discord_user_id"],
            signing_key=signing_key,
            ttl_seconds=settings.applicant_receipt_ttl_seconds,
        )
    except ApplicantAuthError as exc:
        raise HTTPException(status_code=401, detail="Discord authentication failed") from exc

    response = RedirectResponse(flow.return_to, status_code=302)
    response.set_cookie(
        "applicant_receipt",
        receipt,
        max_age=settings.applicant_receipt_ttl_seconds,
        path="/applications",
        secure=True,
        httponly=True,
        samesite="Lax",
    )
    return response


@router.get("/me")
def me(
    request: Request,
    applicant_receipt: Annotated[str | None, Cookie()] = None,
) -> dict[str, str]:
    if not applicant_receipt:
        raise HTTPException(status_code=401, detail="authentication required")

    settings: Settings = request.app.state.settings
    try:
        payload = applicant_discord_auth.verify_applicant_receipt(
            applicant_receipt,
            signing_key=settings.applicant_receipt_signing_key.get_secret_value(),
        )
    except ApplicantReceiptError as exc:
        raise HTTPException(status_code=401, detail="authentication required") from exc

    return {"discord_user_id": payload["discord_user_id"]}


def _auth_flows(request: Request) -> dict[str, applicant_discord_auth.ApplicantAuthFlow]:
    flows = getattr(request.app.state, "applicant_discord_auth_flows", None)
    if flows is None:
        flows = {}
        request.app.state.applicant_discord_auth_flows = flows
    return flows
