"""Tests for main connection class."""

import sys
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from aiohttp import client_exceptions
import pytest
from volkswagencarnet import vw_connection
from volkswagencarnet.vw_connection import Connection
from volkswagencarnet.vw_exceptions import AuthenticationError, RedirectError


class TwoVehiclesConnection(Connection):
    """Connection that return two vehicles."""

    ALLOW_RATE_LIMIT_DELAY = False

    # noinspection PyUnusedLocal
    # noinspection PyMissingConstructor
    def __init__(self, sess, username="", password="", **kwargs):
        """Init."""
        super().__init__(session=sess, username=username, password=password)

    async def doLogin(self, tries=1):
        """No-op update."""
        return True

    async def update(self):
        """No-op update."""
        return True

    @property
    def vehicles(self):
        """Return the vehicles."""
        vehicle1 = vw_connection.Vehicle(None, "vin1")
        vehicle2 = vw_connection.Vehicle(None, "vin2")
        return [vehicle1, vehicle2]


@pytest.mark.skipif(
    condition=sys.version_info < (3, 11), reason="Test incompatible with Python < 3.11"
)
def test_clear_cookies(connection) -> None:
    """Check that we can clear old cookies."""
    assert len(connection._session._cookie_jar._cookies) > 0
    connection._clear_cookies()
    assert len(connection._session._cookie_jar._cookies) == 0


class SendCommandsTest(IsolatedAsyncioTestCase):
    """Test command sending."""

    async def test_set_schedule(self):
        """Test set schedule."""
        pass


class RateLimitTest(IsolatedAsyncioTestCase):
    """Test that rate limiting towards VW works."""

    invocations = 0

    async def rateLimitedFunction(self, url, vin=""):
        """Limit calls test function."""
        ri = MagicMock(aiohttp.RequestInfo)
        e = client_exceptions.ClientResponseError(request_info=ri, history=tuple([]))
        e.status = 429
        self.invocations = self.invocations + 1
        raise e

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        condition=sys.version_info < (3, 11),
        reason="Test incompatible with Python < 3.11",
    )
    @patch(
        "volkswagencarnet.vw_connection.Connection",
        spec_set=vw_connection.Connection,
        new=TwoVehiclesConnection,
    )
    @patch("volkswagencarnet.vw_connection.MAX_RETRIES_ON_RATE_LIMIT", 1)
    async def test_rate_limit(self):
        """Test rate limiting functionality."""

        from unittest.mock import AsyncMock

        sess = AsyncMock()

        # noinspection PyArgumentList
        conn = vw_connection.Connection(sess, "", "")

        self.invocations = 0
        with patch.object(conn, "_request", self.rateLimitedFunction):
            res = await conn.get("foo")
            assert res == {"status_code": 429}
        assert self.invocations == vw_connection.MAX_RETRIES_ON_RATE_LIMIT + 1


class NAOAuthLoginTest(IsolatedAsyncioTestCase):
    """Test NA OAuth login flow."""

    def _make_na_conn(self):
        """Create a Connection with country='US' and mocked session."""
        mock_session = AsyncMock()
        mock_session._cookie_jar = MagicMock()
        mock_session._cookie_jar._cookies = {}
        conn = Connection(mock_session, "user@example.com", "password", country="US")
        return conn

    async def test_na_login_success(self):
        """Test successful NA login via the _login() dispatch chain."""
        conn = self._make_na_conn()

        openid_config = {
            "authorization_endpoint": "https://identity.na.vwgroup.io/authorize",
            "token_endpoint": "https://identity.na.vwgroup.io/token",
            "issuer": "https://identity.na.vwgroup.io",
        }
        token_response = {
            "access_token": "idk_access_token",
            "id_token": "idk_id_token",
            "token_type": "Bearer",
            "refresh_token": "idk_refresh_token",
        }

        # Call _login() — validates that _login() dispatches to _login_na() for NA
        with (
            patch.object(conn, "get_openid_config", return_value=openid_config),
            patch.object(conn, "_get_authorization_code", return_value="auth_code_123"),
            patch.object(conn, "_exchange_code_for_tokens", return_value=token_response),
        ):
            result = await conn._login()

        assert result is True
        assert conn._session_tokens["identity"]["access_token"] == "idk_access_token"
        assert conn._session_region == "NA"

    async def test_na_login_bad_credentials(self):
        """Test that bad credentials cause login to return False without raising."""
        conn = self._make_na_conn()

        openid_config = {
            "authorization_endpoint": "https://identity.na.vwgroup.io/authorize",
            "token_endpoint": "https://identity.na.vwgroup.io/token",
            "issuer": "https://identity.na.vwgroup.io",
        }

        with (
            patch.object(conn, "get_openid_config", return_value=openid_config),
            patch.object(
                conn,
                "_get_authorization_code",
                side_effect=AuthenticationError("Wrong username or password"),
            ),
        ):
            result = await conn._login_na()

        assert result is False
        assert "identity" not in conn._session_tokens

    async def test_na_login_token_exchange_failure(self):
        """Test that a token exchange failure (missing required keys) returns False."""
        conn = self._make_na_conn()

        openid_config = {
            "authorization_endpoint": "https://identity.na.vwgroup.io/authorize",
            "token_endpoint": "https://identity.na.vwgroup.io/token",
            "issuer": "https://identity.na.vwgroup.io",
        }
        # Missing required keys (access_token, id_token, token_type)
        bad_token_response = {"error": "invalid_grant", "error_description": "Token expired"}

        with (
            patch.object(conn, "get_openid_config", return_value=openid_config),
            patch.object(conn, "_get_authorization_code", return_value="auth_code_bad"),
            patch.object(conn, "_exchange_code_for_tokens", return_value=bad_token_response),
        ):
            result = await conn._login_na()

        assert result is False

    async def test_na_login_redirect_extraction_failure(self):
        """Test that a redirect failure during login returns False."""
        conn = self._make_na_conn()

        openid_config = {
            "authorization_endpoint": "https://identity.na.vwgroup.io/authorize",
            "token_endpoint": "https://identity.na.vwgroup.io/token",
            "issuer": "https://identity.na.vwgroup.io",
        }

        with (
            patch.object(conn, "get_openid_config", return_value=openid_config),
            patch.object(
                conn,
                "_get_authorization_code",
                side_effect=RedirectError("Too many redirects"),
            ),
        ):
            result = await conn._login_na()

        assert result is False

    async def test_na_login_network_error(self):
        """Test that a network error during login returns False without raising."""
        conn = self._make_na_conn()

        with patch.object(
            conn,
            "get_openid_config",
            side_effect=client_exceptions.ClientConnectionError(),
        ):
            result = await conn._login_na()

        assert result is False

    async def test_emea_login_not_routed_to_na(self):
        """Test that EMEA connections do not dispatch to _login_na()."""
        mock_session = AsyncMock()
        mock_session._cookie_jar = MagicMock()
        mock_session._cookie_jar._cookies = {}
        conn = Connection(mock_session, "user@example.com", "password")  # No country = DE = EMEA

        assert conn._session_region == "EMEA"
        assert conn._session_region != "NA"

        # Confirm _login() would not dispatch to _login_na() for this connection
        with patch.object(conn, "_login_na") as mock_na:
            with patch.object(conn, "get_openid_config", side_effect=AuthenticationError("stop")):
                await conn._login()
            mock_na.assert_not_called()
