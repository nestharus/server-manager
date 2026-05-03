from __future__ import annotations

import base64
import json
import threading
import time
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm


DISCORD_USER_ID = "123456789012345678"
APPLICANT_CLIENT_ID = "server-manager-applicant-test"
APPLICANT_CLIENT_SECRET = "server-manager-applicant-secret"
RECEIPT_SIGNING_KEY = "test-applicant-receipt-signing-key-minimum-length"
AUTHENTIK_AUTHORIZE_URL = "https://auth.local.humility.local/application/o/authorize/"
AUTHENTIK_ISSUER = "https://auth.local.humility.local/application/o/server-manager-applicant/"
REDIRECT_URI = "https://web.local.humility.local/auth/discord/callback"
FROZEN_NOW = datetime(2026, 4, 28, 12, 0, tzinfo=UTC)


class DummyDatabase:
    def close(self) -> None:
        return None


@dataclass
class StartedAuthFlow:
    state: str
    code_challenge: str
    redirect_uri: str


@dataclass
class MockAuthentikServer:
    audience: str = APPLICANT_CLIENT_ID
    issuer: str = AUTHENTIK_ISSUER
    expected_challenge: str | None = None
    requests: list[dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._wrong_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        assert self._server is not None
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    @property
    def token_url(self) -> str:
        return f"{self.base_url}/token"

    @property
    def jwks_url(self) -> str:
        return f"{self.base_url}/jwks"

    def start(self) -> None:
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format: str, *_args: Any) -> None:
                return None

            def do_GET(self) -> None:
                if self.path != "/jwks":
                    self.send_response(404)
                    self.end_headers()
                    return

                body = json.dumps({"keys": [mock._public_jwk()]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self) -> None:
                if self.path != "/token":
                    self.send_response(404)
                    self.end_headers()
                    return

                length = int(self.headers.get("Content-Length", "0"))
                fields = {
                    key: value[-1]
                    for key, value in parse_qs(
                        self.rfile.read(length).decode("utf-8"),
                        keep_blank_values=True,
                    ).items()
                }
                mock.requests.append(fields)

                verifier = fields.get("code_verifier", "")
                if mock.expected_challenge is not None and (
                    _pkce_challenge(verifier) != mock.expected_challenge
                ):
                    self._json_response(401, {"error": "invalid_grant"})
                    return

                self._json_response(
                    200,
                    {
                        "access_token": "fixture-access-token",
                        "expires_in": 300,
                        "id_token": mock.id_token_for_code(fields.get("code", "")),
                        "token_type": "Bearer",
                    },
                )

            def _json_response(self, status: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _public_jwk(self) -> dict[str, Any]:
        jwk = json.loads(RSAAlgorithm.to_jwk(self._private_key.public_key()))
        jwk["kid"] = "applicant-key"
        jwk["use"] = "sig"
        jwk["alg"] = "RS256"
        return jwk

    def id_token_for_code(self, code: str) -> str:
        now = int(time.time())
        payload: dict[str, Any] = {
            "iss": self.issuer,
            "aud": self.audience,
            "sub": DISCORD_USER_ID,
            "discord_user_id": DISCORD_USER_ID,
            "iat": now,
            "exp": now + 300,
        }
        signing_key = self._private_key

        if code == "bad-signature":
            signing_key = self._wrong_private_key
        elif code == "wrong-audience":
            payload["aud"] = "wrong-client"
        elif code == "expired":
            payload["iat"] = now - 900
            payload["exp"] = now - 300

        return jwt.encode(
            payload,
            signing_key,
            algorithm="RS256",
            headers={"kid": "applicant-key"},
        )


def _pkce_challenge(verifier: str) -> str:
    import hashlib

    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _set_auth_env(monkeypatch: pytest.MonkeyPatch, authentik: MockAuthentikServer) -> None:
    values = {
        "DISCORD_BOT_TOKEN": "test-token-value",
        "DISCORD_GUILD_ID": "900000000000000001",
        "SUPABASE_DB_URL": "postgresql://user:pass@localhost:5432/db",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
        "SUPABASE_SERVICE_KEY": "test-service-key",
        "WEB_PUBLIC_BASE_URL": "https://web.test.local",
        "S3_ENDPOINT": "http://minio.test.local:9000",
        "S3_REGION": "us-east-1",
        "S3_BUCKET": "server-manager",
        "S3_ACCESS_KEY_ID": "test-s3-access-key",
        "S3_SECRET_ACCESS_KEY": "test-s3-secret-key",
        "APPLICANT_OIDC_CLIENT_ID": APPLICANT_CLIENT_ID,
        "APPLICANT_OIDC_CLIENT_SECRET": APPLICANT_CLIENT_SECRET,
        "AUTHENTIK_AUTHORIZE_URL": AUTHENTIK_AUTHORIZE_URL,
        "AUTHENTIK_TOKEN_URL": authentik.token_url,
        "AUTHENTIK_JWKS_URL": authentik.jwks_url,
        "AUTHENTIK_ISSUER_URL": AUTHENTIK_ISSUER,
        "APPLICANT_RECEIPT_SIGNING_KEY": RECEIPT_SIGNING_KEY,
        "APPLICANT_RECEIPT_TTL_SECONDS": "600",
        "APPLICANT_DISCORD_REDIRECT_URI": REDIRECT_URI,
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)


@pytest.fixture()
def mock_authentik_server() -> Iterator[MockAuthentikServer]:
    server = MockAuthentikServer()
    server.start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture()
def auth_env(
    monkeypatch: pytest.MonkeyPatch,
    mock_authentik_server: MockAuthentikServer,
) -> None:
    _set_auth_env(monkeypatch, mock_authentik_server)


@pytest.fixture()
def auth_app(auth_env: None):
    from app.core.factory import create_api_app
    from app.core.settings import Settings

    return create_api_app(settings=Settings(), db=DummyDatabase())


@pytest_asyncio.fixture()
async def auth_client(auth_app) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=auth_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture()
async def started_auth_flow(
    auth_client: httpx.AsyncClient,
    mock_authentik_server: MockAuthentikServer,
) -> StartedAuthFlow:
    response = await auth_client.get(
        "/auth/discord/start",
        params={"return_to": "/applications"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers["location"]
    query = parse_qs(urlparse(location).query)
    flow = StartedAuthFlow(
        state=query["state"][0],
        code_challenge=query["code_challenge"][0],
        redirect_uri=query["redirect_uri"][0],
    )
    mock_authentik_server.expected_challenge = flow.code_challenge
    return flow


@pytest.fixture()
def receipt_module():
    import importlib

    return importlib.import_module("app.services.applicant_discord_auth")


@pytest.fixture()
def valid_receipt_token(receipt_module) -> str:
    return receipt_module.sign_applicant_receipt(
        discord_user_id=DISCORD_USER_ID,
        signing_key=RECEIPT_SIGNING_KEY,
        issued_at=FROZEN_NOW,
    )


@pytest.fixture()
def fresh_receipt_token(receipt_module) -> str:
    """Receipt for HTTP tests that verify against real wall-clock time."""
    return receipt_module.sign_applicant_receipt(
        discord_user_id=DISCORD_USER_ID,
        signing_key=RECEIPT_SIGNING_KEY,
        issued_at=datetime.now(UTC),
    )


@pytest.fixture()
def tampered_receipt_token(valid_receipt_token: str) -> str:
    header, payload, signature = valid_receipt_token.split(".")
    decoded_payload = json.loads(base64.urlsafe_b64decode(payload + "=="))
    decoded_payload["discord_user_id"] = "999999999999999999"
    tampered_payload = (
        base64.urlsafe_b64encode(
            json.dumps(decoded_payload, separators=(",", ":")).encode("utf-8")
        )
        .decode("ascii")
        .rstrip("=")
    )
    return f"{header}.{tampered_payload}.{signature}"


@pytest.fixture()
def expired_receipt_token(receipt_module) -> str:
    return receipt_module.sign_applicant_receipt(
        discord_user_id=DISCORD_USER_ID,
        signing_key=RECEIPT_SIGNING_KEY,
        issued_at=FROZEN_NOW - timedelta(seconds=601),
    )


@pytest.mark.asyncio
async def test_start_redirects_to_authentik_authorize_with_state_and_pkce(
    auth_client: httpx.AsyncClient,
) -> None:
    """TG-3 risk annotation: authorize_redirect_missing_state_or_pkce;
    level=unit; source=INIT-127 C3, A3.
    """
    response = await auth_client.get(
        "/auth/discord/start",
        params={"return_to": "/applications"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    location = response.headers["location"]
    parsed = urlparse(location)
    query = parse_qs(parsed.query)

    assert location.startswith(AUTHENTIK_AUTHORIZE_URL)
    assert query["client_id"] == [APPLICANT_CLIENT_ID]
    assert query["redirect_uri"] == [REDIRECT_URI]
    assert query["response_type"] == ["code"]
    assert query["scope"] == ["openid"]
    assert query["state"][0]
    assert query["code_challenge"][0]
    assert query["code_challenge_method"] == ["S256"]


@pytest.mark.asyncio
async def test_callback_exchanges_code_validates_id_token_and_sets_receipt_cookie(
    auth_client: httpx.AsyncClient,
    mock_authentik_server: MockAuthentikServer,
    started_auth_flow: StartedAuthFlow,
) -> None:
    """TG-3 risk annotation: callback_trusts_code_without_exchange_or_jwks;
    level=unit; source=INIT-127 C3, A1, A3.
    """
    response = await auth_client.get(
        "/auth/discord/callback",
        params={"code": "valid", "state": started_auth_flow.state},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"].endswith("/applications")
    assert mock_authentik_server.requests
    token_request = mock_authentik_server.requests[-1]
    assert token_request["grant_type"] == "authorization_code"
    assert token_request["code"] == "valid"
    assert token_request["client_id"] == APPLICANT_CLIENT_ID
    assert token_request["client_secret"] == APPLICANT_CLIENT_SECRET
    assert token_request["redirect_uri"] == started_auth_flow.redirect_uri
    assert token_request["code_verifier"]

    cookie = SimpleCookie(response.headers["set-cookie"])["applicant_receipt"]
    assert cookie.value
    assert cookie["httponly"] is True
    assert cookie["secure"] is True
    assert cookie["samesite"] == "Lax"

    receipt_payload = jwt.decode(
        cookie.value,
        RECEIPT_SIGNING_KEY,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )
    assert set(receipt_payload) == {"discord_user_id", "iat", "exp"}
    assert receipt_payload["discord_user_id"] == DISCORD_USER_ID
    assert receipt_payload["exp"] - receipt_payload["iat"] == 600


@pytest.mark.parametrize(
    ("params", "expected_status"),
    [
        pytest.param({"state": "placeholder"}, 400, id="missing-code"),
        pytest.param({"code": "valid"}, 400, id="missing-state"),
        pytest.param({"code": "valid", "state": "wrong-state"}, 400, id="state-mismatch"),
    ],
)
@pytest.mark.asyncio
async def test_callback_rejects_missing_code_and_csrf_state_errors(
    auth_client: httpx.AsyncClient,
    started_auth_flow: StartedAuthFlow,
    params: dict[str, str],
    expected_status: int,
) -> None:
    """TG-3 risk annotation: callback_csrf_or_parameter_validation_gap;
    level=unit; source=INIT-127 C3, A3.
    """
    if params.get("state") == "placeholder":
        params["state"] = started_auth_flow.state

    response = await auth_client.get(
        "/auth/discord/callback",
        params=params,
        follow_redirects=False,
    )

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "code",
    [
        pytest.param("bad-signature", id="bad-signature"),
        pytest.param("wrong-audience", id="wrong-audience"),
        pytest.param("expired", id="expired"),
    ],
)
@pytest.mark.asyncio
async def test_callback_rejects_invalid_id_tokens(
    auth_client: httpx.AsyncClient,
    started_auth_flow: StartedAuthFlow,
    code: str,
) -> None:
    """TG-3 risk annotation: forged_wrong_audience_or_expired_id_token_accepted;
    level=unit; source=INIT-127 C3, A1, A3.
    """
    response = await auth_client.get(
        "/auth/discord/callback",
        params={"code": code, "state": started_auth_flow.state},
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert "set-cookie" not in response.headers


@pytest.mark.asyncio
async def test_callback_rejects_pkce_verifier_challenge_mismatch(
    auth_client: httpx.AsyncClient,
    mock_authentik_server: MockAuthentikServer,
    started_auth_flow: StartedAuthFlow,
) -> None:
    """TG-3 risk annotation: pkce_verifier_challenge_mismatch_accepted;
    level=unit; source=INIT-127 C3, A3.
    """
    mock_authentik_server.expected_challenge = "mismatched-challenge"

    response = await auth_client.get(
        "/auth/discord/callback",
        params={"code": "valid", "state": started_auth_flow.state},
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert "set-cookie" not in response.headers


def test_receipt_helper_signs_and_verifies_hmac_receipts(receipt_module) -> None:
    """TG-4 risk annotation: receipt_claim_contract_drift;
    level=unit; source=INIT-127 C3/C4, A3.
    """
    token = receipt_module.sign_applicant_receipt(
        discord_user_id=DISCORD_USER_ID,
        signing_key=RECEIPT_SIGNING_KEY,
        issued_at=FROZEN_NOW,
    )

    payload = receipt_module.verify_applicant_receipt(
        token,
        signing_key=RECEIPT_SIGNING_KEY,
        now=FROZEN_NOW + timedelta(seconds=599),
    )

    assert set(payload) == {"discord_user_id", "iat", "exp"}
    assert payload["discord_user_id"] == DISCORD_USER_ID
    assert payload["exp"] - payload["iat"] == 600


def test_receipt_helper_rejects_tampered_wrong_key_and_expired_tokens(
    receipt_module,
    valid_receipt_token: str,
    tampered_receipt_token: str,
    expired_receipt_token: str,
) -> None:
    """TG-4 risk annotation: receipt_forgery_or_expiry_accepted;
    level=unit; source=INIT-127 C3/C4, A3.
    """
    with pytest.raises(receipt_module.ApplicantReceiptError):
        receipt_module.verify_applicant_receipt(
            tampered_receipt_token,
            signing_key=RECEIPT_SIGNING_KEY,
            now=FROZEN_NOW,
        )

    with pytest.raises(receipt_module.ApplicantReceiptError):
        receipt_module.verify_applicant_receipt(
            valid_receipt_token,
            signing_key="wrong-signing-key",
            now=FROZEN_NOW,
        )

    with pytest.raises(receipt_module.ApplicantReceiptError):
        receipt_module.verify_applicant_receipt(
            expired_receipt_token,
            signing_key=RECEIPT_SIGNING_KEY,
            now=FROZEN_NOW,
        )


def test_receipt_ttl_defaults_to_600_seconds(auth_env: None) -> None:
    """TG-4 risk annotation: receipt_ttl_not_bound_to_settings_default;
    level=unit; source=INIT-127 C4, A3.
    """
    from app.core.settings import Settings

    assert Settings().applicant_receipt_ttl_seconds == 600


@pytest.mark.asyncio
async def test_me_returns_discord_user_id_from_valid_cookie(
    auth_client: httpx.AsyncClient,
    fresh_receipt_token: str,
) -> None:
    """TG-5 risk annotation: me_endpoint_ignores_signed_receipt_cookie;
    level=unit; source=INIT-127 C6, A3.
    """
    response = await auth_client.get(
        "/auth/discord/me",
        headers={"Cookie": f"applicant_receipt={fresh_receipt_token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"discord_user_id": DISCORD_USER_ID}


@pytest.mark.parametrize(
    "cookie_header",
    [
        pytest.param(None, id="missing-cookie"),
        pytest.param("applicant_receipt=tampered", id="unparseable-cookie"),
    ],
)
@pytest.mark.asyncio
async def test_me_rejects_missing_or_invalid_cookie(
    auth_client: httpx.AsyncClient,
    cookie_header: str | None,
) -> None:
    """TG-5 risk annotation: me_endpoint_accepts_missing_or_bad_cookie;
    level=unit; source=INIT-127 C6, A3.
    """
    headers = {"Cookie": cookie_header} if cookie_header else {}

    response = await auth_client.get("/auth/discord/me", headers=headers)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_rejects_tampered_and_expired_cookie(
    auth_client: httpx.AsyncClient,
    tampered_receipt_token: str,
    expired_receipt_token: str,
) -> None:
    """TG-5 risk annotation: me_endpoint_accepts_forged_or_expired_receipt;
    level=unit; source=INIT-127 C6, A3.
    """
    for token in (tampered_receipt_token, expired_receipt_token):
        response = await auth_client.get(
            "/auth/discord/me",
            headers={"Cookie": f"applicant_receipt={token}"},
        )
        assert response.status_code == 401
