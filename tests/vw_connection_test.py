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


class NAThreeTokenTest(IsolatedAsyncioTestCase):
    """Test NA three-token chain: IDK, Brand, and MBB acquisition."""

    def _make_na_conn(self, **kwargs):
        """Create a Connection with country='US' and mocked session."""
        mock_session = AsyncMock()
        mock_session._cookie_jar = MagicMock()
        mock_session._cookie_jar._cookies = {}
        return Connection(mock_session, "user@example.com", "password", country="US", **kwargs)

    def _idk_fixtures(self):
        """Return standard openid_config and idk_tokens fixtures."""
        openid_config = {
            "authorization_endpoint": "https://identity.na.vwgroup.io/authorize",
            "token_endpoint": "https://identity.na.vwgroup.io/token",
            "issuer": "https://identity.na.vwgroup.io",
        }
        idk_tokens = {
            "access_token": "idk_at",
            "id_token": "idk_id",
            "refresh_token": "idk_rt",
            "token_type": "Bearer",
        }
        return openid_config, idk_tokens

    async def test_na_full_three_token_login_success(self):
        """Test full three-token chain succeeds and all tokens are stored."""
        conn = self._make_na_conn()
        openid_config, idk_tokens = self._idk_fixtures()
        brand_tokens = {"access_token": "brand_at", "refresh_token": "brand_rt"}
        mbb_initial = {"access_token": "mbb_at_1", "refresh_token": "mbb_rt_1"}
        mbb_refreshed = {"access_token": "mbb_at_2", "refresh_token": "mbb_rt_2"}

        with (
            patch.object(conn, "get_openid_config", return_value=openid_config),
            patch.object(conn, "_get_authorization_code", return_value="auth_code_123"),
            patch.object(conn, "_exchange_code_for_tokens", return_value=idk_tokens),
            patch.object(conn, "_exchange_brand_token", return_value=brand_tokens),
            patch.object(conn, "_register_mbb_client", return_value="xclient-001"),
            patch.object(conn, "_exchange_mbb_token", return_value=mbb_initial),
            patch.object(conn, "_refresh_mbb_token", return_value=mbb_refreshed),
        ):
            result = await conn._login_na()

        assert result is True
        assert conn._na_auth_level == "full"
        assert conn._xclient_id == "xclient-001"
        assert conn._na_tokens["idk"]["access_token"] == "idk_at"
        assert conn._na_tokens["brand"]["access_token"] == "brand_at"
        assert conn._na_tokens["mbb"]["access_token"] == "mbb_at_2"  # refreshed token
        assert conn._session_tokens["identity"]["access_token"] == "idk_at"  # COMPAT-04

    async def test_na_brand_failure_falls_back_to_idk_only(self):
        """Test that brand exchange failure falls back to IDK-only auth level."""
        conn = self._make_na_conn()
        openid_config, idk_tokens = self._idk_fixtures()

        with (
            patch.object(conn, "get_openid_config", return_value=openid_config),
            patch.object(conn, "_get_authorization_code", return_value="auth_code_brand_fail"),
            patch.object(conn, "_exchange_code_for_tokens", return_value=idk_tokens),
            patch.object(
                conn,
                "_exchange_brand_token",
                side_effect=AuthenticationError("brand exchange failed"),
            ),
        ):
            result = await conn._login_na()

        assert result is True
        assert conn._na_auth_level == "idk_only"
        assert "brand" not in conn._na_tokens
        assert "mbb" not in conn._na_tokens

    async def test_na_mbb_registration_failure_falls_back_to_idk_only(self):
        """Test that MBB registration failure falls back to IDK-only auth level."""
        conn = self._make_na_conn()
        openid_config, idk_tokens = self._idk_fixtures()
        brand_tokens = {"access_token": "brand_at", "refresh_token": "brand_rt"}

        with (
            patch.object(conn, "get_openid_config", return_value=openid_config),
            patch.object(conn, "_get_authorization_code", return_value="auth_code_reg_fail"),
            patch.object(conn, "_exchange_code_for_tokens", return_value=idk_tokens),
            patch.object(conn, "_exchange_brand_token", return_value=brand_tokens),
            patch.object(
                conn,
                "_register_mbb_client",
                side_effect=AuthenticationError("registration failed"),
            ),
        ):
            result = await conn._login_na()

        assert result is True
        assert conn._na_auth_level == "idk_only"
        assert "mbb" not in conn._na_tokens

    async def test_na_mbb_token_exchange_failure_falls_back_to_idk_only(self):
        """Test that MBB token exchange failure falls back to IDK-only auth level."""
        conn = self._make_na_conn()
        openid_config, idk_tokens = self._idk_fixtures()
        brand_tokens = {"access_token": "brand_at", "refresh_token": "brand_rt"}

        with (
            patch.object(conn, "get_openid_config", return_value=openid_config),
            patch.object(conn, "_get_authorization_code", return_value="auth_code_mbb_fail"),
            patch.object(conn, "_exchange_code_for_tokens", return_value=idk_tokens),
            patch.object(conn, "_exchange_brand_token", return_value=brand_tokens),
            patch.object(conn, "_register_mbb_client", return_value="xclient-002"),
            patch.object(
                conn,
                "_exchange_mbb_token",
                side_effect=AuthenticationError("MBB exchange failed"),
            ),
        ):
            result = await conn._login_na()

        assert result is True
        assert conn._na_auth_level == "idk_only"

    async def test_na_mbb_refresh_called_immediately_after_initial_grant(self):
        """Test that _refresh_mbb_token is called once with initial MBB refresh_token."""
        conn = self._make_na_conn()
        openid_config, idk_tokens = self._idk_fixtures()
        brand_tokens = {"access_token": "brand_at", "refresh_token": "brand_rt"}
        mbb_initial = {"access_token": "mbb_at_1", "refresh_token": "mbb_rt_1"}
        mbb_refreshed = {"access_token": "mbb_at_2", "refresh_token": "mbb_rt_2"}

        mock_refresh = AsyncMock(return_value=mbb_refreshed)

        with (
            patch.object(conn, "get_openid_config", return_value=openid_config),
            patch.object(conn, "_get_authorization_code", return_value="auth_code_refresh"),
            patch.object(conn, "_exchange_code_for_tokens", return_value=idk_tokens),
            patch.object(conn, "_exchange_brand_token", return_value=brand_tokens),
            patch.object(conn, "_register_mbb_client", return_value="xclient-003"),
            patch.object(conn, "_exchange_mbb_token", return_value=mbb_initial),
            patch.object(conn, "_refresh_mbb_token", mock_refresh),
        ):
            await conn._login_na()

        assert mock_refresh.call_count == 1
        # Verify the initial refresh_token was passed to _refresh_mbb_token
        call_kwargs = mock_refresh.call_args
        assert call_kwargs[1]["refresh_token"] == "mbb_rt_1"

    async def test_na_injected_xclient_id_skips_registration(self):
        """Test that a caller-injected xclientId bypasses _register_mbb_client."""
        conn = self._make_na_conn(xclient_id="injected-123")
        openid_config, idk_tokens = self._idk_fixtures()
        brand_tokens = {"access_token": "brand_at", "refresh_token": "brand_rt"}
        mbb_initial = {"access_token": "mbb_at_1", "refresh_token": "mbb_rt_1"}
        mbb_refreshed = {"access_token": "mbb_at_2", "refresh_token": "mbb_rt_2"}

        mock_register = AsyncMock(return_value="should-not-be-called")

        with (
            patch.object(conn, "get_openid_config", return_value=openid_config),
            patch.object(conn, "_get_authorization_code", return_value="auth_code_inject"),
            patch.object(conn, "_exchange_code_for_tokens", return_value=idk_tokens),
            patch.object(conn, "_exchange_brand_token", return_value=brand_tokens),
            patch.object(conn, "_register_mbb_client", mock_register),
            patch.object(conn, "_exchange_mbb_token", return_value=mbb_initial),
            patch.object(conn, "_refresh_mbb_token", return_value=mbb_refreshed),
        ):
            result = await conn._login_na()

        mock_register.assert_not_called()
        assert conn._xclient_id == "injected-123"  # unchanged, not overwritten
        assert result is True
        assert conn._na_auth_level == "full"

    async def test_na_on_xclient_id_callback_fired_for_new_registration(self):
        """Test that on_xclient_id callback fires when a new xclientId is registered."""
        callback = MagicMock()
        conn = self._make_na_conn(on_xclient_id=callback)
        openid_config, idk_tokens = self._idk_fixtures()
        brand_tokens = {"access_token": "brand_at", "refresh_token": "brand_rt"}
        mbb_initial = {"access_token": "mbb_at_1", "refresh_token": "mbb_rt_1"}
        mbb_refreshed = {"access_token": "mbb_at_2", "refresh_token": "mbb_rt_2"}

        with (
            patch.object(conn, "get_openid_config", return_value=openid_config),
            patch.object(conn, "_get_authorization_code", return_value="auth_code_cb"),
            patch.object(conn, "_exchange_code_for_tokens", return_value=idk_tokens),
            patch.object(conn, "_exchange_brand_token", return_value=brand_tokens),
            patch.object(conn, "_register_mbb_client", return_value="new-xclient"),
            patch.object(conn, "_exchange_mbb_token", return_value=mbb_initial),
            patch.object(conn, "_refresh_mbb_token", return_value=mbb_refreshed),
        ):
            await conn._login_na()

        assert callback.call_count == 1
        assert callback.call_args[0][0] == "new-xclient"

    async def test_na_on_xclient_id_callback_not_fired_for_injected_id(self):
        """Test that on_xclient_id callback does NOT fire when xclientId is caller-injected."""
        callback = MagicMock()
        conn = self._make_na_conn(xclient_id="injected-456", on_xclient_id=callback)
        openid_config, idk_tokens = self._idk_fixtures()
        brand_tokens = {"access_token": "brand_at", "refresh_token": "brand_rt"}
        mbb_initial = {"access_token": "mbb_at_1", "refresh_token": "mbb_rt_1"}
        mbb_refreshed = {"access_token": "mbb_at_2", "refresh_token": "mbb_rt_2"}

        with (
            patch.object(conn, "get_openid_config", return_value=openid_config),
            patch.object(conn, "_get_authorization_code", return_value="auth_code_no_cb"),
            patch.object(conn, "_exchange_code_for_tokens", return_value=idk_tokens),
            patch.object(conn, "_exchange_brand_token", return_value=brand_tokens),
            patch.object(conn, "_register_mbb_client", return_value="should-not-be-used"),
            patch.object(conn, "_exchange_mbb_token", return_value=mbb_initial),
            patch.object(conn, "_refresh_mbb_token", return_value=mbb_refreshed),
        ):
            await conn._login_na()

        callback.assert_not_called()
