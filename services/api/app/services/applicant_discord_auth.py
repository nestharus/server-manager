from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException
import jwt
from jwt import PyJWKClient
from pydantic import BaseModel
from starlette.requests import Request as StarletteRequest


DISCORD_SNOWFLAKE_RE = re.compile(r"^[0-9]{17,20}$")
RECEIPT_TTL_SECONDS = 600


class ApplicantAuthError(Exception):
    pass


class ApplicantReceiptError(Exception):
    pass


@dataclass(frozen=True)
class ApplicantAuthFlow:
    state: str
    code_verifier: str
    code_challenge: str
    redirect_uri: str
    return_to: str


class DiscordIdentity(BaseModel):
    discord_user_id: str


def create_auth_flow(*, redirect_uri: str, return_to: str) -> ApplicantAuthFlow:
    code_verifier = secrets.token_urlsafe(48)
    code_challenge = _pkce_challenge(code_verifier)
    return ApplicantAuthFlow(
        state=secrets.token_urlsafe(32),
        code_verifier=code_verifier,
        code_challenge=code_challenge,
        redirect_uri=redirect_uri,
        return_to=_safe_return_to(return_to),
    )


def build_authorize_url(
    *,
    authorize_url: str,
    client_id: str,
    flow: ApplicantAuthFlow,
) -> str:
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": flow.redirect_uri,
            "response_type": "code",
            "scope": "openid",
            "state": flow.state,
            "code_challenge": flow.code_challenge,
            "code_challenge_method": "S256",
        }
    )
    separator = "&" if "?" in authorize_url else "?"
    return f"{authorize_url}{separator}{query}"


def exchange_code_for_id_token(
    *,
    token_url: str,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code_verifier: str,
) -> str:
    body = urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }
    ).encode("utf-8")
    request = Request(
        token_url,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise ApplicantAuthError("token exchange failed") from exc

    id_token = payload.get("id_token")
    if not isinstance(id_token, str) or not id_token:
        raise ApplicantAuthError("token response missing id_token")
    return id_token


def validate_id_token(
    *,
    id_token: str,
    jwks_url: str,
    issuer_url: str,
    audience: str,
) -> dict[str, Any]:
    try:
        signing_key = PyJWKClient(jwks_url).get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer_url,
        )
    except Exception as exc:
        raise ApplicantAuthError("id token validation failed") from exc

    discord_user_id = claims.get("discord_user_id") or claims.get("sub")
    if not isinstance(discord_user_id, str) or not DISCORD_SNOWFLAKE_RE.match(
        discord_user_id
    ):
        raise ApplicantAuthError("id token missing Discord snowflake")
    claims["discord_user_id"] = discord_user_id
    return claims


def sign_applicant_receipt(
    *,
    discord_user_id: str,
    signing_key: str,
    issued_at: datetime | None = None,
    ttl_seconds: int = RECEIPT_TTL_SECONDS,
) -> str:
    if not DISCORD_SNOWFLAKE_RE.match(discord_user_id):
        raise ApplicantReceiptError("invalid Discord snowflake")
    now = issued_at or datetime.now(UTC)
    iat = int(now.timestamp())
    payload = {
        "discord_user_id": discord_user_id,
        "iat": iat,
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, signing_key, algorithm="HS256")


def verify_applicant_receipt_jwt(
    token: str,
    *,
    signing_key: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["HS256"],
            options={
                "require": ["discord_user_id", "iat", "exp"],
                "verify_aud": False,
                "verify_exp": False,
                "verify_iat": False,
            },
        )
    except Exception as exc:
        raise ApplicantReceiptError("receipt signature invalid") from exc

    if set(payload) != {"discord_user_id", "iat", "exp"}:
        raise ApplicantReceiptError("receipt claims invalid")
    if not isinstance(payload["discord_user_id"], str) or not DISCORD_SNOWFLAKE_RE.match(
        payload["discord_user_id"]
    ):
        raise ApplicantReceiptError("receipt Discord snowflake invalid")

    current_ts = int((now or datetime.now(UTC)).timestamp())
    try:
        iat = int(payload["iat"])
        exp = int(payload["exp"])
    except (TypeError, ValueError) as exc:
        raise ApplicantReceiptError("receipt timestamps invalid") from exc
    if exp <= current_ts or iat > current_ts:
        raise ApplicantReceiptError("receipt expired")
    return payload


def verify_applicant_receipt(
    request: StarletteRequest,
    *,
    signing_key: str | None = None,
    now: datetime | None = None,
) -> DiscordIdentity | dict[str, Any]:
    if isinstance(request, str):
        if signing_key is None:
            raise TypeError("signing_key is required when verifying a receipt token")
        return verify_applicant_receipt_jwt(
            request,
            signing_key=signing_key,
            now=now,
        )

    cookie = request.cookies.get("applicant_receipt")
    if not cookie:
        _raise_applicant_receipt_required()

    settings = request.app.state.settings
    try:
        payload = verify_applicant_receipt_jwt(
            cookie,
            signing_key=settings.applicant_receipt_signing_key.get_secret_value(),
            now=now,
        )
    except ApplicantReceiptError as exc:
        raise _applicant_receipt_required_error() from exc

    return DiscordIdentity(discord_user_id=payload["discord_user_id"])


def _applicant_receipt_required_error() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={
            "code": "applicant_receipt_required",
            "message": "Discord login is required to submit.",
        },
    )


def _raise_applicant_receipt_required() -> None:
    raise _applicant_receipt_required_error()


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _safe_return_to(return_to: str) -> str:
    if not return_to.startswith("/") or return_to.startswith("//"):
        return "/applications"
    return return_to
