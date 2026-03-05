"""
E2E tests for North America token refresh — direct method calls.

Covers TEST-04 (IDK token refresh). Brand/MBB tokens do not exist on
the NA Car-Net API (b-h-s.spr.us00.p.con-veh.net) — those tests are marked xfail.

These tests require real VW credentials and a live network connection.
Run with: pytest tests/e2e/test_na_token_refresh.py -v
"""
import logging
import time

import pytest
import pytest_asyncio

from tests.e2e.conftest import _truncate_token

_log = logging.getLogger(__name__)


def _soft_assert(failures: list, condition: bool, msg: str) -> None:
    """Collect assertion failures; caller raises at end with full list."""
    if not condition:
        failures.append(msg)


@pytest.mark.asyncio(loop_scope="module")
class TestNATokenRefresh:
    """Direct token refresh method calls for IDK (TEST-04). Brand/MBB not applicable."""

    pytestmark = pytest.mark.asyncio(loop_scope="module")

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

    @pytest.mark.xfail(reason="NA Car-Net uses IDK-only auth — MBB token not present")
    async def test_mbb_token_refresh_returns_new_token(self, na_connection):
        """MBB token refresh — not applicable for NA Car-Net (IDK-only)."""
        mbb_entry = na_connection._na_tokens.get("mbb", {})
        assert mbb_entry.get("access_token"), "MBB token not present"

    @pytest.mark.xfail(reason="NA Car-Net uses IDK-only auth — Brand token not present")
    async def test_brand_token_refresh_returns_non_empty(self, na_connection):
        """Brand token refresh — not applicable for NA Car-Net (IDK-only)."""
        await na_connection._refresh_brand_token()
        brand_token = na_connection._na_tokens.get("brand", {}).get("access_token", "")
        assert brand_token

    @pytest.mark.xfail(reason="NA Car-Net uses IDK-only auth — Brand token not present")
    async def test_brand_token_present_after_full_login(self, na_connection):
        """Brand token persistence — not applicable for NA Car-Net (IDK-only)."""
        brand_entry = na_connection._na_tokens.get("brand", {})
        assert brand_entry.get("access_token")

    async def test_na_tokens_expiry_in_future(self, na_connection):
        """IDK token has expires_at in the future."""
        now = time.time()
        failures = []
        # Only check IDK — Brand/MBB not applicable for NA Car-Net
        entry = na_connection._na_tokens.get("idk", {})
        exp = entry.get("expires_at")
        if exp is not None:
            _soft_assert(failures, exp > now, f"idk token expired: exp={exp}, now={now}")
        else:
            _log.warning("idk token has no 'expires_at' field")
        if failures:
            raise AssertionError("Token expiry failures:\n" + "\n".join(f"  - {f}" for f in failures))
