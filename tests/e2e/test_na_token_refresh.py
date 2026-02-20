"""
E2E tests for North America token refresh — direct method calls for all three token types.

Covers TEST-04 (direct token refresh method calls: IDK, Brand, MBB).
No pytest.skip guards — na_connection fixture guarantees na_auth_level == "full"
before any test in this module runs.

These tests require real VW credentials and a live network connection.
Run with: pytest tests/e2e/test_na_token_refresh.py -v
"""
import logging
import time

import pytest
import pytest_asyncio

from tests.e2e.conftest import _truncate_token

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Soft-assert helper (independent copy — keeps files self-contained)
# ---------------------------------------------------------------------------


def _soft_assert(failures: list, condition: bool, msg: str) -> None:
    """Collect assertion failures; caller raises at end with full list."""
    if not condition:
        failures.append(msg)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestNATokenRefresh:
    """Direct token refresh method calls for IDK, Brand, and MBB (TEST-04)."""

    pytestmark = pytest.mark.asyncio

    async def test_idk_token_refresh_returns_new_token(self, na_connection):
        """TEST-04: _refresh_idk_token() completes and IDK access_token is non-empty after refresh."""
        token_before = na_connection._na_tokens.get("idk", {}).get("access_token", "")
        await na_connection._refresh_idk_token()
        token_after = na_connection._na_tokens.get("idk", {}).get("access_token", "")
        assert token_after, "IDK access_token is empty after refresh"
        assert isinstance(token_after, str)
        _log.info(
            "IDK refresh: before=%s, after=%s",
            _truncate_token(token_before),
            _truncate_token(token_after),
        )

    async def test_mbb_token_refresh_returns_new_token(self, na_connection):
        """TEST-04: _refresh_mbb_token() returns a valid token dict with non-empty access_token."""
        # No pytest.skip guard — fixture guarantees na_auth_level == "full", so MBB token is present
        mbb_entry = na_connection._na_tokens.get("mbb", {})
        refresh_tok = mbb_entry.get("refresh_token")
        xclient_id = na_connection._xclient_id
        assert refresh_tok, "MBB refresh_token missing from _na_tokens['mbb']"
        assert xclient_id, "conn._xclient_id is None — cannot refresh MBB token"
        new_tokens = await na_connection._refresh_mbb_token(refresh_tok, xclient_id)
        assert new_tokens, "_refresh_mbb_token() returned empty result"
        assert new_tokens.get("access_token"), "new MBB access_token is empty"
        _log.info(
            "MBB refresh returned access_token: %s",
            _truncate_token(new_tokens.get("access_token", "")),
        )

    async def test_brand_token_refresh_returns_non_empty(self, na_connection):
        """TEST-04: _refresh_brand_token() completes and Brand access_token is non-empty."""
        # No pytest.skip guard — fixture guarantees na_auth_level == "full", so Brand token is present
        await na_connection._refresh_brand_token()
        brand_token = na_connection._na_tokens.get("brand", {}).get("access_token", "")
        assert brand_token, "Brand access_token is empty after _refresh_brand_token() call"
        assert isinstance(brand_token, str)
        _log.info("Brand refresh returned access_token: %s", _truncate_token(brand_token))

    async def test_brand_token_present_after_full_login(self, na_connection):
        """Brand access_token persists in _na_tokens['brand'] after full login."""
        # No pytest.skip guard — fixture guarantees na_auth_level == "full", so Brand token is always present
        brand_entry = na_connection._na_tokens.get("brand", {})
        assert brand_entry.get("access_token"), "Brand access_token missing from _na_tokens['brand']"
        _log.info(
            "Brand access_token: %s",
            _truncate_token(brand_entry.get("access_token", "")),
        )

    async def test_na_tokens_expiry_in_future(self, na_connection):
        """All three token types have expires_at in the future (if the field is set)."""
        now = time.time()
        failures = []
        # No pytest.skip guard — fixture guarantees full auth for all three token types
        for token_key in ("idk", "brand", "mbb"):
            entry = na_connection._na_tokens.get(token_key, {})
            exp = entry.get("expires_at")
            if exp is not None:
                _soft_assert(
                    failures,
                    exp > now,
                    f"{token_key} token expired: exp={exp}, now={now}",
                )
            else:
                _log.warning(
                    "%s token has no 'expires_at' field in _na_tokens — cannot assert expiry",
                    token_key,
                )
        if failures:
            raise AssertionError(
                "Token expiry failures:\n" + "\n".join(f"  - {f}" for f in failures)
            )
