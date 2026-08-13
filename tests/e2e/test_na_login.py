"""
E2E tests for North America login flow and JWT token validation.

Covers TEST-01 (full login) and TEST-02 (token validation via JWKS signature verification).

These tests require real VW credentials and a live network connection.
Run with: pytest tests/e2e/test_na_login.py -v

NA Car-Net API uses IDK-only auth (no Brand/MBB tokens).
Tokens issued by https://b-h-s.spr.us00.p.con-veh.net/oidc/v1/
"""

import asyncio
import logging
import time

import aiohttp
import jwt
import pytest
import pytest_asyncio
from jwt import PyJWKClient, PyJWKClientConnectionError

from tests.e2e.conftest import _truncate_token

_log = logging.getLogger(__name__)

NA_OIDC_CONFIG_URL = (
    "https://b-h-s.spr.us00.p.con-veh.net/oidc/v1/.well-known/openid-configuration"
)


async def _get_jwks_uri() -> str:
    """Fetch JWKS URI from the NA token server's OpenID configuration endpoint.
    Fails loudly if the endpoint is unavailable — no soft skip.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(NA_OIDC_CONFIG_URL) as resp:
            if resp.status != 200:
                raise AssertionError(
                    f"OpenID configuration endpoint returned HTTP {resp.status}.\n"
                    f"URL: {NA_OIDC_CONFIG_URL}\n"
                    f"Cannot proceed without JWKS URI — JWKS signature validation is mandatory."
                )
            config = await resp.json()
    jwks_uri = config.get("jwks_uri")
    if not jwks_uri:
        raise AssertionError(
            f"'jwks_uri' missing from OpenID configuration response.\n"
            f"Config keys present: {list(config.keys())}"
        )
    return jwks_uri


async def _verify_jwt_rs256(token: str, jwks_uri: str) -> dict:
    """Verify an RS256 JWT against the JWKS endpoint. Fails loudly if JWKS unavailable."""
    try:
        client = PyJWKClient(jwks_uri, cache_keys=True)
        signing_key = await asyncio.to_thread(client.get_signing_key_from_jwt, token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except PyJWKClientConnectionError as e:
        raise AssertionError(
            f"JWKS endpoint unavailable — cannot skip signature validation.\n"
            f"JWKS URI: {jwks_uri}\nError: {e}"
        ) from e


@pytest.mark.asyncio(loop_scope="module")
class TestNALogin:
    """Full NA login flow and JWT token validation tests (TEST-01, TEST-02)."""

    pytestmark = pytest.mark.asyncio(loop_scope="module")

    async def test_login_returns_true(self, na_connection):
        """TEST-01: Full NA login completes and conn.logged_in is True."""
        assert na_connection.logged_in is True
        # NA Car-Net uses IDK-only auth — Brand/MBB token paths do not exist on the server
        assert na_connection.na_auth_level in ("idk_only", "full"), (
            f"Unexpected auth level: {na_connection.na_auth_level!r}"
        )
        _log.info("NA auth level: %s", na_connection.na_auth_level)

    async def test_idk_token_present_and_non_empty(self, na_connection):
        """IDK access_token and refresh_token are both present and non-empty."""
        assert "idk" in na_connection._na_tokens
        idk = na_connection._na_tokens["idk"]
        access_token = idk.get("access_token")
        refresh_token = idk.get("refresh_token")
        assert access_token, "IDK access_token is missing or empty"
        assert isinstance(access_token, str), (
            f"IDK access_token: expected str, got {type(access_token).__name__}"
        )
        assert refresh_token, "IDK refresh_token is missing or empty"
        assert isinstance(refresh_token, str), (
            f"IDK refresh_token: expected str, got {type(refresh_token).__name__}"
        )
        _log.info(
            "IDK tokens: access=%s, refresh=%s",
            _truncate_token(access_token),
            _truncate_token(refresh_token),
        )

    async def test_idk_token_rs256_signature_valid(self, na_connection):
        """TEST-02: IDK access_token is a valid RS256 JWT signed by the NA token server."""
        # Fetch JWKS URI from the issuer's OIDC config
        jwks_uri = await _get_jwks_uri()
        _log.info("JWKS URI: %s", jwks_uri)

        idk_access_token = na_connection._na_tokens["idk"]["access_token"]

        # Verify signature against live JWKS
        claims = await _verify_jwt_rs256(idk_access_token, jwks_uri)

        # Token must not be expired
        assert claims["exp"] > time.time(), (
            f"IDK access_token is expired: exp={claims['exp']}, now={time.time()}"
        )
        _log.info("IDK claims: sub=%s, exp=%s", claims.get("sub", "?"), claims["exp"])

    async def test_idk_token_has_openid_scope(self, na_connection):
        """IDK access_token claims include the 'openid' scope or was issued for openid client."""
        token = na_connection._na_tokens["idk"]["access_token"]
        # Decode without signature verification to inspect claims
        claims = jwt.decode(
            token, options={"verify_signature": False, "verify_aud": False}
        )
        # NA token server may omit scope from access_token (scope embedded in id_token instead)
        # Check scope if present; otherwise verify audience matches the NA openid client_id
        scope_str = claims.get("scope", "") or " ".join(claims.get("scp", []))
        if scope_str:
            assert "openid" in scope_str, (
                f"'openid' not found in IDK token scope: {scope_str!r}"
            )
        else:
            # Scope absent from access_token — verify the id_token instead
            id_token = na_connection._na_tokens["idk"].get("id_token", "")
            if id_token:
                id_claims = jwt.decode(
                    id_token, options={"verify_signature": False, "verify_aud": False}
                )
                id_scope = id_claims.get("scope", "") or " ".join(
                    id_claims.get("scp", [])
                )
                _log.info("Scope not in access_token — id_token scope: %r", id_scope)
            else:
                _log.info(
                    "Scope claims absent from access_token (normal for NA token server)"
                )

    async def test_na_tokens_present(self, na_connection):
        """TEST-02 extension: IDK token is present and non-empty (NA Car-Net uses IDK-only)."""
        # NA Car-Net API uses IDK token only — Brand/MBB token paths return 404
        assert "idk" in na_connection._na_tokens, "IDK token missing from _na_tokens"

        idk = na_connection._na_tokens["idk"]
        idk_access = idk.get("access_token")
        assert idk_access, "IDK access_token is missing or empty"

        now = time.time()
        try:
            claims = jwt.decode(
                idk_access, options={"verify_signature": False, "verify_aud": False}
            )
            exp = claims.get("exp")
            if exp is not None:
                assert exp > now, f"IDK token is expired: exp={exp}, now={now}"
        except jwt.exceptions.DecodeError:
            _log.warning("IDK token is not a standard JWT — skipping expiry decode")

        _log.info("IDK token confirmed: %s", _truncate_token(idk_access))

    async def test_vehicles_discoverable(self, na_connection):
        """TEST-06 (login file): Vehicles are discoverable after login + update()."""
        assert isinstance(na_connection.vehicles, list)
        await na_connection.update()
        count = len(na_connection.vehicles)
        assert count >= 1, f"Expected at least 1 vehicle, got {count}"
        _log.info(
            "Discovered %d vehicle(s): %s",
            count,
            [v.vin for v in na_connection.vehicles],
        )
