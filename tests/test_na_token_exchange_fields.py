"""Regression tests for the NA token-exchange request shape.

NA login broke with myVW app 2026.7.28-9380 (2026-07-31) for two reasons,
both confirmed live against VW's server and fixed 2026-08-12:

1. The library sent an ``X-QMAuth`` header on the NA auth-code exchange.
   X-QMAuth is an EMEA-only HMAC header; the NA public PKCE client never sends
   it, and doing so gets HTTP 400 "Internal Service validation failure".

2. The NA token body must include a ``play_integrity_token`` field. Without it
   the AZS server returns HTTP 401 "Unauthorized exception". The server only
   checks the field is present and non-empty (it does not validate the value),
   so a placeholder suffices.

These tests pin both behaviours so they cannot silently regress.
"""

from unittest.mock import AsyncMock

import pytest

from tests.vw_connection_test import _make_connection
from volkswagencarnet.vw_connection import Connection

TOKEN_ENDPOINT = "https://b-h-s.spr.us00.p.con-veh.net/oidc/v1/token"
_FAKE_TOKENS = (
    '{"access_token":"a","refresh_token":"r","id_token":"i","expires_in":3600}'
)


def _connection(country: str) -> tuple[Connection, AsyncMock]:
    """Build a Connection whose session.post returns a fake 200 token response.

    Returns the connection plus the mocked ``session.post`` so callers can
    inspect the exact body/headers that were sent.
    """
    conn = _make_connection(country=country)
    conn._pkce_verifier = "test-code-verifier"

    resp = AsyncMock()
    resp.status = 200
    resp.text = AsyncMock(return_value=_FAKE_TOKENS)
    conn._session.post = AsyncMock(return_value=resp)
    return conn, conn._session.post


class TestNATokenExchangeFields:
    """The NA auth-code exchange must carry play_integrity_token, not X-QMAuth."""

    @pytest.mark.asyncio
    async def test_na_body_includes_play_integrity_token(self):
        conn, post = _connection("US")
        await conn._exchange_code_for_tokens("auth-code", TOKEN_ENDPOINT)

        body = post.call_args.kwargs["data"]
        assert body.get("play_integrity_token"), (
            "NA token exchange must send a non-empty play_integrity_token "
            "(server returns 401 without it)"
        )
        # Sanity: the fields we already knew were correct are still present.
        assert body["client_id"] == conn._client_id
        assert body["grant_type"] == "authorization_code"
        assert body["code_verifier"] == "test-code-verifier"

    @pytest.mark.asyncio
    async def test_na_exchange_does_not_send_xqmauth(self):
        conn, post = _connection("US")
        await conn._exchange_code_for_tokens("auth-code", TOKEN_ENDPOINT)

        headers = post.call_args.kwargs["headers"]
        assert "X-QMAuth" not in headers, (
            "NA is a public PKCE client; X-QMAuth causes HTTP 400"
        )

    @pytest.mark.asyncio
    async def test_na_exchange_sends_app_identity_headers(self):
        conn, post = _connection("US")
        await conn._exchange_code_for_tokens("auth-code", TOKEN_ENDPOINT)

        headers = post.call_args.kwargs["headers"]
        for key in ("x-app-uuid", "x-mobile-session-id", "x-app-version"):
            assert headers.get(key), f"missing NA app-identity header {key}"

    @pytest.mark.asyncio
    async def test_emea_exchange_sends_xqmauth_and_no_play_integrity(self):
        conn, post = _connection("DE")
        await conn._exchange_code_for_tokens("auth-code", TOKEN_ENDPOINT)

        body = post.call_args.kwargs["data"]
        headers = post.call_args.kwargs["headers"]
        assert "play_integrity_token" not in body, "play_integrity_token is NA-only"
        assert "X-QMAuth" in headers, "EMEA still requires X-QMAuth"
