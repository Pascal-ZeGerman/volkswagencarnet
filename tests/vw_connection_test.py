"""Tests for main connection class."""

import sys
import time
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from aiohttp import ClientSession, client_exceptions
import pytest
from volkswagencarnet import vw_connection
from volkswagencarnet.vw_connection import Connection
from volkswagencarnet.vw_exceptions import APIError, AuthenticationError, RedirectError, RequestError


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
    async def test_rate_limit(self):
        """Test that get() returns Throttled state after 429 retry exhaustion.

        Retry logic is centralized in _request(). get() catches the raised
        ClientResponseError with status 429 and returns {"state": "Throttled"}.
        """
        from unittest.mock import AsyncMock

        sess = AsyncMock()

        # noinspection PyArgumentList
        conn = vw_connection.Connection(sess, "", "")

        ri = MagicMock(aiohttp.RequestInfo)
        e = client_exceptions.ClientResponseError(request_info=ri, history=tuple([]))
        e.status = 429

        with patch.object(conn, "_request", side_effect=e):
            res = await conn.get("foo")
            assert res == {"state": "Throttled"}


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
            patch.object(conn, "_get_authorization_code_na", return_value="auth_code_123"),
            patch.object(conn, "_exchange_code_for_tokens", return_value=token_response),
        ):
            result = await conn._login()

        assert result is True
        assert conn._session_tokens["identity"]["access_token"] == "idk_access_token"
        assert conn._session_region == "NA"

    async def test_na_login_bad_credentials(self):
        """Test that bad credentials cause _login_na() to raise AuthenticationError (not return False)."""
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
                "_get_authorization_code_na",
                side_effect=AuthenticationError("Wrong username or password"),
            ),
            pytest.raises(AuthenticationError, match="Wrong username or password"),
        ):
            await conn._login_na()

        assert conn._session_logged_in is False
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
            patch.object(conn, "_get_authorization_code_na", return_value="auth_code_bad"),
            patch.object(conn, "_exchange_code_for_tokens", return_value=bad_token_response),
        ):
            result = await conn._login_na()

        assert result is False

    async def test_na_login_redirect_extraction_failure(self):
        """Test that a redirect failure during NA login raises RedirectError (not returns False)."""
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
                "_get_authorization_code_na",
                side_effect=RedirectError("Too many redirects"),
            ),
            pytest.raises(RedirectError, match="Too many redirects"),
        ):
            await conn._login_na()

        assert conn._session_logged_in is False

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
            patch.object(conn, "_get_authorization_code_na", return_value="auth_code_123"),
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
            patch.object(conn, "_get_authorization_code_na", return_value="auth_code_brand_fail"),
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
            patch.object(conn, "_get_authorization_code_na", return_value="auth_code_reg_fail"),
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
            patch.object(conn, "_get_authorization_code_na", return_value="auth_code_mbb_fail"),
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
            patch.object(conn, "_get_authorization_code_na", return_value="auth_code_refresh"),
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
            patch.object(conn, "_get_authorization_code_na", return_value="auth_code_inject"),
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
            patch.object(conn, "_get_authorization_code_na", return_value="auth_code_cb"),
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
            patch.object(conn, "_get_authorization_code_na", return_value="auth_code_no_cb"),
            patch.object(conn, "_exchange_code_for_tokens", return_value=idk_tokens),
            patch.object(conn, "_exchange_brand_token", return_value=brand_tokens),
            patch.object(conn, "_register_mbb_client", return_value="should-not-be-used"),
            patch.object(conn, "_exchange_mbb_token", return_value=mbb_initial),
            patch.object(conn, "_refresh_mbb_token", return_value=mbb_refreshed),
        ):
            await conn._login_na()

        callback.assert_not_called()


class NATokenLifecycleTest(IsolatedAsyncioTestCase):
    """Test NA token lifecycle management: endpoint classification, per-token refresh, cascade, and validation."""

    def _make_na_conn(self, **kwargs):
        """Create a Connection with country='US' and mocked session."""
        session = AsyncMock()
        session._cookie_jar = MagicMock()
        session._cookie_jar._cookies = {}
        return Connection(session, "user@example.com", "password", country="US", **kwargs)

    def _na_tokens_fixture(self, expires_at_offset=7200):
        """Return populated _na_tokens dict with future expires_at values."""
        now = time.time()
        return {
            "idk": {
                "access_token": "idk_at",
                "refresh_token": "idk_rt",
                "id_token": "idk_id",
                "expires_at": now + expires_at_offset,
                "issued_at": now,
            },
            "brand": {
                "access_token": "brand_at",
                "refresh_token": "brand_rt",
                "expires_at": now + expires_at_offset,
                "issued_at": now,
            },
            "mbb": {
                "access_token": "mbb_at",
                "refresh_token": "mbb_rt",
                "expires_at": now + expires_at_offset,
                "issued_at": now,
            },
        }

    # --- Group A: _classify_endpoint() ---

    async def test_classify_endpoint_idk_for_base_api_url(self):
        """_classify_endpoint returns 'idk' for Cariad BFF base API URLs."""
        conn = self._make_na_conn()
        conn._base_api = "https://b-h-s.spr.us00.p.con-veh.net"
        result = conn._classify_endpoint("https://b-h-s.spr.us00.p.con-veh.net/vehicle/v2/vehicles")
        assert result == "idk"

    async def test_classify_endpoint_mbb_for_mbb_host(self):
        """_classify_endpoint returns 'mbb' for MBB OAuth service URLs."""
        conn = self._make_na_conn()
        result = conn._classify_endpoint("https://mbboauth-1d.prd.ece.vwg-connect.com/mbbcoauth/mobile/oauth2/v1/token")
        assert result == "mbb"

    async def test_classify_endpoint_brand_for_volkswagen_token_path(self):
        """_classify_endpoint returns 'brand' for brand token path URLs."""
        conn = self._make_na_conn()
        conn._base_api = "https://b-h-s.spr.us00.p.con-veh.net"
        result = conn._classify_endpoint("https://b-h-s.spr.us00.p.con-veh.net/login/v1/volkswagen/token")
        assert result == "brand"

    async def test_classify_endpoint_raises_for_unknown_url(self):
        """_classify_endpoint raises ValueError for unknown NA URLs."""
        conn = self._make_na_conn()
        conn._base_api = "https://b-h-s.spr.us00.p.con-veh.net"
        with pytest.raises(ValueError):
            conn._classify_endpoint("https://unknown.example.com/api")

    # --- Group B: EMEA guard ---

    async def test_classify_endpoint_always_returns_idk_for_emea(self):
        """_classify_endpoint always returns 'idk' for EMEA connections (never raises)."""
        session = AsyncMock()
        session._cookie_jar = MagicMock()
        session._cookie_jar._cookies = {}
        conn = Connection(session, "user@example.com", "password", country="DE")
        result = conn._classify_endpoint("https://unknown.example.com/anything")
        assert result == "idk"

    # --- Group C: _refresh_idk_token() ---

    async def test_idk_refresh_updates_na_tokens_and_session_mirror(self):
        """_refresh_idk_token updates na_tokens, session_tokens mirror, and Authorization header."""
        conn = self._make_na_conn()
        conn._na_tokens = self._na_tokens_fixture()
        conn._na_token_endpoint = "https://id.example.com/token"
        # Pre-populate identity entry so mirror update doesn't KeyError
        conn._session_tokens["identity"] = {"access_token": "old_at"}

        # Remove brand so cascade doesn't fire
        del conn._na_tokens["brand"]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "access_token": "new_at",
            "refresh_token": "new_rt",
            "id_token": "new_id",
            "expires_in": 3600,
        })

        mock_post = AsyncMock(return_value=mock_response)
        with patch.object(conn._session, "post", mock_post):
            await conn._refresh_idk_token()

        assert conn._na_tokens["idk"]["access_token"] == "new_at"
        assert conn._session_tokens["identity"]["access_token"] == "new_at"
        assert "Bearer new_at" in conn._session_headers["Authorization"]

    async def test_idk_refresh_triggers_brand_cascade(self):
        """_refresh_idk_token calls _refresh_brand_token() when brand key is present."""
        conn = self._make_na_conn()
        conn._na_tokens = self._na_tokens_fixture()
        conn._na_token_endpoint = "https://id.example.com/token"
        # Ensure identity entry exists for mirror update
        conn._session_tokens["identity"] = {"access_token": "old_at"}

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "access_token": "new_at",
            "refresh_token": "new_rt",
            "id_token": "new_id",
            "expires_in": 3600,
        })

        mock_brand_refresh = AsyncMock()

        mock_post = AsyncMock(return_value=mock_response)
        with (
            patch.object(conn._session, "post", mock_post),
            patch.object(conn, "_refresh_brand_token", mock_brand_refresh),
        ):
            await conn._refresh_idk_token()

        assert mock_brand_refresh.call_count == 1

    async def test_idk_refresh_retries_up_to_three_times(self):
        """IDK refresh retries up to 3 times on failure; body contains refresh_token,
        grant_type=refresh_token, and code_verifier (no X-QMAuth — server rejects it with HTTP 400)."""
        conn = self._make_na_conn()
        conn._na_tokens = self._na_tokens_fixture()
        conn._na_token_endpoint = "https://id.example.com/token"
        # Pre-populate identity entry so mirror update doesn't KeyError
        conn._session_tokens["identity"] = {"access_token": "old_at"}

        fail_response = AsyncMock()
        fail_response.status = 500
        fail_response.text = AsyncMock(return_value="Server Error")

        success_response = AsyncMock()
        success_response.status = 200
        success_response.json = AsyncMock(return_value={
            "access_token": "recovered_at",
            "refresh_token": "recovered_rt",
            "id_token": "recovered_id",
            "expires_in": 3600,
        })
        # Remove brand to avoid cascade
        del conn._na_tokens["brand"]

        mock_session_post = AsyncMock(side_effect=[fail_response, fail_response, success_response])

        with patch.object(conn._session, "post", mock_session_post):
            with patch("asyncio.sleep", AsyncMock()):
                await conn._refresh_idk_token()

        assert mock_session_post.call_count == 3
        # Verify all calls sent correct body parameters (no X-QMAuth — server rejects it with HTTP 400)
        for call in mock_session_post.call_args_list:
            data = call[1].get("data", {})
            assert data.get("refresh_token") == "idk_rt"
            assert data.get("grant_type") == "refresh_token"
            assert data.get("code_verifier") is not None

    async def test_idk_refresh_raises_after_max_retries(self):
        """_refresh_idk_token raises AuthenticationError after 3 failed attempts."""
        from volkswagencarnet.vw_exceptions import AuthenticationError as VWAuthError

        conn = self._make_na_conn()
        conn._na_tokens = self._na_tokens_fixture()
        conn._na_token_endpoint = "https://id.example.com/token"

        fail_response = AsyncMock()
        fail_response.status = 500
        fail_response.text = AsyncMock(return_value="Server Error")

        mock_session_post = AsyncMock(return_value=fail_response)

        with patch.object(conn._session, "post", mock_session_post):
            with patch("asyncio.sleep", AsyncMock()):
                with pytest.raises(VWAuthError):
                    await conn._refresh_idk_token()

        assert mock_session_post.call_count == 3

    # --- Group D: _refresh_brand_token() ---

    async def test_brand_refresh_calls_exchange_brand_token_with_current_idk(self):
        """_refresh_brand_token calls _exchange_brand_token with current IDK access_token."""
        conn = self._make_na_conn()
        conn._na_tokens = self._na_tokens_fixture()
        conn._na_tokens["idk"]["access_token"] = "current_idk_at"

        mock_exchange = AsyncMock(return_value={
            "access_token": "new_brand_at",
            "refresh_token": "new_brand_rt",
            "expires_in": 3600,
        })

        with patch.object(conn, "_exchange_brand_token", mock_exchange):
            await conn._refresh_brand_token()

        assert mock_exchange.call_args[0][0] == "current_idk_at"
        assert conn._na_tokens["brand"]["access_token"] == "new_brand_at"

    # --- Group E: _refresh_mbb_from_refresh_token() ---

    async def test_mbb_refresh_uses_existing_refresh_token(self):
        """_refresh_mbb_from_refresh_token calls _refresh_mbb_token with stored refresh_token."""
        conn = self._make_na_conn()
        conn._xclient_id = "xclient-123"
        conn._na_tokens = self._na_tokens_fixture()
        conn._na_tokens["mbb"]["refresh_token"] = "mbb_rt"

        mock_refresh_mbb = AsyncMock(return_value={
            "access_token": "new_mbb_at",
            "refresh_token": "new_mbb_rt",
            "expires_in": 3600,
        })

        with patch.object(conn, "_refresh_mbb_token", mock_refresh_mbb):
            await conn._refresh_mbb_from_refresh_token()

        # Verify the stored refresh_token was passed
        call_kwargs = mock_refresh_mbb.call_args
        assert call_kwargs[1].get("refresh_token") == "mbb_rt" or call_kwargs[0][0] == "mbb_rt"
        assert conn._na_tokens["mbb"]["access_token"] == "new_mbb_at"

    async def test_mbb_refresh_falls_back_to_re_exchange_on_failure(self):
        """_refresh_mbb_from_refresh_token falls back to re-exchange via IDK id_token on refresh failure."""
        from volkswagencarnet.vw_exceptions import AuthenticationError as VWAuthError

        conn = self._make_na_conn()
        conn._xclient_id = "xclient-123"
        conn._na_tokens = self._na_tokens_fixture()
        conn._na_tokens["mbb"]["refresh_token"] = "mbb_rt"
        conn._na_tokens["idk"]["id_token"] = "idk_id"

        # First _refresh_mbb_token call fails (primary), second succeeds (fallback after re-exchange)
        mock_refresh_mbb = AsyncMock(side_effect=[
            VWAuthError("refresh failed"),
            {"access_token": "fallback_at", "refresh_token": "fallback_rt", "expires_in": 3600},
        ])
        mock_exchange_mbb = AsyncMock(return_value={
            "access_token": "init_at",
            "refresh_token": "init_rt",
        })

        with (
            patch.object(conn, "_refresh_mbb_token", mock_refresh_mbb),
            patch.object(conn, "_exchange_mbb_token", mock_exchange_mbb),
        ):
            await conn._refresh_mbb_from_refresh_token()

        assert conn._na_tokens["mbb"]["access_token"] == "fallback_at"
        assert mock_exchange_mbb.call_count == 1  # fallback path triggered

    # --- Group F: _validate_na_tokens() ---

    async def test_validate_na_tokens_no_refresh_when_tokens_fresh(self):
        """_validate_na_tokens returns True without refreshing any tokens when all tokens are fresh."""
        conn = self._make_na_conn()
        conn._na_tokens = self._na_tokens_fixture(expires_at_offset=7200)  # 2 hours out
        conn._na_auth_level = "full"

        mock_idk_refresh = AsyncMock()
        mock_brand_refresh = AsyncMock()
        mock_mbb_refresh = AsyncMock()

        with (
            patch.object(conn, "_refresh_idk_token", mock_idk_refresh),
            patch.object(conn, "_refresh_brand_token", mock_brand_refresh),
            patch.object(conn, "_refresh_mbb_from_refresh_token", mock_mbb_refresh),
        ):
            result = await conn._validate_na_tokens()

        assert result is True
        assert mock_idk_refresh.call_count == 0
        assert mock_brand_refresh.call_count == 0
        assert mock_mbb_refresh.call_count == 0

    async def test_validate_na_tokens_refreshes_idk_within_15min_window(self):
        """_validate_na_tokens refreshes IDK when it expires within 15-minute window."""
        conn = self._make_na_conn()
        conn._na_tokens = self._na_tokens_fixture(expires_at_offset=7200)
        conn._na_auth_level = "full"
        # Override IDK to expire within 15-min window (< 900 seconds)
        conn._na_tokens["idk"]["expires_at"] = time.time() + 500

        mock_idk_refresh = AsyncMock()

        with patch.object(conn, "_refresh_idk_token", mock_idk_refresh):
            result = await conn._validate_na_tokens()

        assert result is True
        assert mock_idk_refresh.call_count == 1

    async def test_validate_na_tokens_skipped_for_idk_only_auth_level_mbb(self):
        """_validate_na_tokens skips brand and MBB refresh when auth level is idk_only."""
        conn = self._make_na_conn()
        conn._na_tokens = self._na_tokens_fixture(expires_at_offset=7200)
        conn._na_auth_level = "idk_only"
        # Make brand and idk expiring (brand within window)
        conn._na_tokens["brand"]["expires_at"] = time.time() + 100

        mock_brand_refresh = AsyncMock()
        mock_mbb_refresh = AsyncMock()

        with (
            patch.object(conn, "_refresh_brand_token", mock_brand_refresh),
            patch.object(conn, "_refresh_mbb_from_refresh_token", mock_mbb_refresh),
        ):
            await conn._validate_na_tokens()

        assert mock_brand_refresh.call_count == 0  # idk_only skips brand
        assert mock_mbb_refresh.call_count == 0    # idk_only skips mbb

    # --- Group G: validate_tokens() NA branch ---

    async def test_validate_tokens_routes_na_to_validate_na_tokens(self):
        """validate_tokens() routes NA connections to _validate_na_tokens()."""
        conn = self._make_na_conn()
        conn._na_tokens = self._na_tokens_fixture()

        mock_validate_na = AsyncMock(return_value=True)

        with patch.object(conn, "_validate_na_tokens", mock_validate_na):
            result = await conn.validate_tokens()

        assert result is True
        assert mock_validate_na.call_count == 1

    # --- Group H: _request() 401 inline retry ---

    async def test_request_401_triggers_inline_refresh_and_retry_for_na(self):
        """_request() retries once after inline token refresh on 401 for NA connections."""
        conn = self._make_na_conn()
        conn._na_tokens = self._na_tokens_fixture()
        conn._base_api = "https://b-h-s.spr.us00.p.con-veh.net"

        # Mock 401 response (first call)
        mock_response_401 = MagicMock()
        mock_response_401.status = 401
        mock_response_401.raise_for_status = MagicMock()  # does not raise

        # Mock 200 response (second call - retry)
        mock_response_ok = MagicMock()
        mock_response_ok.status = 200
        mock_response_ok.json = AsyncMock(return_value={"data": "ok"})
        mock_response_ok.raise_for_status = MagicMock()
        mock_response_ok.cookies = {}
        mock_response_ok.headers = {}

        # Build async context manager mocks
        cm_401 = MagicMock()
        cm_401.__aenter__ = AsyncMock(return_value=mock_response_401)
        cm_401.__aexit__ = AsyncMock(return_value=False)

        cm_ok = MagicMock()
        cm_ok.__aenter__ = AsyncMock(return_value=mock_response_ok)
        cm_ok.__aexit__ = AsyncMock(return_value=False)

        mock_session_request = MagicMock(side_effect=[cm_401, cm_ok])
        mock_idk_refresh = AsyncMock()

        with (
            patch.object(conn._session, "request", mock_session_request),
            patch.object(conn, "_classify_endpoint", return_value="idk"),
            patch.object(conn, "_refresh_idk_token", mock_idk_refresh),
            patch.object(conn, "update_service_status", AsyncMock()),
        ):
            result = await conn._request("GET", "https://b-h-s.spr.us00.p.con-veh.net/vehicle/v2/vehicles")

        assert mock_idk_refresh.call_count == 1
        assert mock_session_request.call_count == 2  # original + retry

    async def test_request_401_not_triggered_for_emea(self):
        """_request() 401 inline retry is NOT triggered for EMEA connections."""
        from aiohttp import client_exceptions as aiohttp_exc
        import aiohttp

        session = AsyncMock()
        session._cookie_jar = MagicMock()
        session._cookie_jar._cookies = {}
        conn = Connection(session, "user@example.com", "password", country="DE")

        # EMEA 401 path: ClientResponseError is raised by raise_for_status
        ri = MagicMock(aiohttp.RequestInfo)
        e = aiohttp_exc.ClientResponseError(request_info=ri, history=tuple([]))
        e.status = 401

        mock_response_401 = MagicMock()
        mock_response_401.status = 401
        mock_response_401.raise_for_status = MagicMock(side_effect=e)

        cm_401 = MagicMock()
        cm_401.__aenter__ = AsyncMock(return_value=mock_response_401)
        cm_401.__aexit__ = AsyncMock(return_value=False)

        # Use MagicMock directly (not return_value kwarg) so session.request returns cm_401 synchronously
        mock_session_request = MagicMock(return_value=cm_401)

        with (
            patch.object(conn._session, "request", mock_session_request),
            patch.object(conn, "update_service_status", AsyncMock()),
        ):
            # EMEA 401: get() catches ClientResponseError 401 -> sets _session_logged_in=False
            result = await conn.get("https://emea.bff.cariad.digital/vehicle/v2/vehicles")

        # For EMEA, get() handles 401 by setting logged_in=False and returning status_code dict
        assert result == {"status_code": 401}
        assert conn._session_logged_in is False
        # Inline 401 retry guard only activates for NA (session_region == "NA")
        # EMEA path does not attempt token refresh — raise_for_status raises ClientResponseError
        assert mock_session_request.call_count == 1  # no retry for EMEA


# ---------------------------------------------------------------------------
# Phase 23-01: Comprehensive Connection tests
# ---------------------------------------------------------------------------

VIN = "WVWTEST1234567890"
BASE_API = "https://emea.bff.cariad.digital"


def _make_connection(country="DE", **overrides):
    """Create a Connection with mocked session for testing."""
    session = AsyncMock(spec=ClientSession)
    session._cookie_jar = MagicMock()
    session._cookie_jar._cookies = {}
    conn = Connection(session, "test@example.com", "password123", country=country)
    conn._base_api = BASE_API
    for k, v in overrides.items():
        setattr(conn, k, v)
    return conn


def _mock_action_response():
    """Create a mock raw response that _handle_action_result can parse."""
    mock_resp = AsyncMock()
    mock_resp.json = AsyncMock(return_value={"data": {"requestID": "req-123"}})
    return mock_resp


# ---------------------------------------------------------------------------
# EMEA OAuth Flow Tests
# ---------------------------------------------------------------------------
class TestEmeaOAuthFlow:
    """Test EMEA OAuth login flow components."""

    @pytest.mark.asyncio
    async def test_get_openid_config_returns_endpoints(self):
        """Mock session.get to return openid config, verify returned dict has auth and token endpoints."""
        conn = _make_connection()
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "authorization_endpoint": "https://identity.vwgroup.io/oidc/v1/authorize",
            "token_endpoint": "https://emea.bff.cariad.digital/login/v1/idk/token",
            "issuer": "https://identity.vwgroup.io",
        })
        conn._session.get = AsyncMock(return_value=mock_resp)
        result = await conn.get_openid_config()
        assert "authorization_endpoint" in result
        assert "token_endpoint" in result

    @pytest.mark.asyncio
    async def test_login_emea_full_flow(self):
        """Test EMEA login via _login() dispatching to EMEA path with mocked sub-methods."""
        conn = _make_connection()
        openid_config = {
            "authorization_endpoint": "https://identity.vwgroup.io/oidc/v1/authorize",
            "token_endpoint": "https://emea.bff.cariad.digital/login/v1/idk/token",
            "issuer": "https://identity.vwgroup.io",
        }
        token_response = {
            "access_token": "emea_at",
            "id_token": "emea_id",
            "refresh_token": "emea_rt",
            "token_type": "Bearer",
        }
        with (
            patch.object(conn, "get_openid_config", return_value=openid_config),
            patch.object(conn, "_get_authorization_code", return_value="emea_code_123"),
            patch.object(conn, "_exchange_code_for_tokens", return_value=token_response),
        ):
            result = await conn._login()

        assert result is True
        assert conn._session_tokens["identity"]["access_token"] == "emea_at"
        assert conn._session_region == "EMEA"

    @pytest.mark.asyncio
    async def test_login_emea_invalid_credentials(self):
        """Mock auth that raises AuthenticationError, verify _login returns False."""
        conn = _make_connection()
        openid_config = {
            "authorization_endpoint": "https://identity.vwgroup.io/oidc/v1/authorize",
            "token_endpoint": "https://emea.bff.cariad.digital/login/v1/idk/token",
            "issuer": "https://identity.vwgroup.io",
        }
        with (
            patch.object(conn, "get_openid_config", return_value=openid_config),
            patch.object(
                conn,
                "_get_authorization_code",
                side_effect=AuthenticationError("Invalid credentials"),
            ),
        ):
            result = await conn._login()

        # _login() catches AuthenticationError and returns False
        assert result is False

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_success(self):
        """Mock token endpoint POST, verify tokens parsed correctly."""
        conn = _make_connection()
        conn._na_token_endpoint = None  # EMEA path
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.text = AsyncMock(return_value='{"access_token":"test_at","refresh_token":"test_rt","id_token":"test_id","token_type":"Bearer","expires_in":3600}')

        mock_post = AsyncMock(return_value=mock_resp)
        with patch.object(conn._session, "post", mock_post):
            result = await conn._exchange_code_for_tokens(
                "test_code",
                "https://emea.bff.cariad.digital/login/v1/idk/token",
            )

        assert result["access_token"] == "test_at"
        assert result["refresh_token"] == "test_rt"

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_error(self):
        """Mock token endpoint returning 400, verify AuthenticationError raised."""
        conn = _make_connection()
        conn._na_token_endpoint = None  # EMEA path
        mock_resp = AsyncMock()
        mock_resp.status = 400
        mock_resp.text = AsyncMock(return_value='{"error":"invalid_grant"}')

        mock_post = AsyncMock(return_value=mock_resp)
        with patch.object(conn._session, "post", mock_post):
            with pytest.raises(AuthenticationError, match="Token exchange failed"):
                await conn._exchange_code_for_tokens(
                    "bad_code",
                    "https://emea.bff.cariad.digital/login/v1/idk/token",
                )


# ---------------------------------------------------------------------------
# Token Management Tests
# ---------------------------------------------------------------------------
class TestTokenManagement:
    """Test token validation and refresh paths for both regions."""

    @pytest.mark.asyncio
    async def test_validate_tokens_emea_fresh_tokens_no_refresh(self):
        """Set EMEA tokens with long expiry, verify no refresh call."""
        import jwt as pyjwt

        conn = _make_connection()
        # Create fake JWT tokens with far-future expiry
        future_exp = int(time.time()) + 7200
        fake_payload = {"exp": future_exp, "sub": "test"}
        # Use a simple unsigned token for testing
        fake_token = pyjwt.encode(fake_payload, "secret", algorithm="HS256")
        conn._session_tokens["identity"] = {
            "access_token": fake_token,
            "id_token": fake_token,
            "refresh_token": "rt",
        }

        mock_refresh = AsyncMock(return_value=True)
        with patch.object(conn, "refresh_tokens", mock_refresh):
            result = await conn.validate_tokens()

        assert result is True
        mock_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_tokens_emea_expired_triggers_refresh(self):
        """Set near-expired EMEA tokens, verify refresh is called."""
        import jwt as pyjwt

        conn = _make_connection()
        # Create tokens that expire in the past
        past_exp = int(time.time()) - 100
        fake_payload = {"exp": past_exp, "sub": "test"}
        fake_token = pyjwt.encode(fake_payload, "secret", algorithm="HS256")
        conn._session_tokens["identity"] = {
            "access_token": fake_token,
            "id_token": fake_token,
            "refresh_token": "rt",
        }

        mock_refresh = AsyncMock(return_value=True)
        with patch.object(conn, "refresh_tokens", mock_refresh):
            result = await conn.validate_tokens()

        assert result is True
        mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_tokens_na_refreshes_idk_only(self):
        """For NA connection, verify only IDK refresh (no Brand/MBB) when idk_only."""
        conn = _make_connection(country="US")
        now = time.time()
        conn._na_tokens = {
            "idk": {
                "access_token": "idk_at",
                "refresh_token": "idk_rt",
                "id_token": "idk_id",
                "expires_at": now + 500,  # within 15-min window
                "issued_at": now,
            },
        }
        conn._na_auth_level = "idk_only"

        mock_idk_refresh = AsyncMock()
        mock_brand_refresh = AsyncMock()
        mock_mbb_refresh = AsyncMock()

        with (
            patch.object(conn, "_refresh_idk_token", mock_idk_refresh),
            patch.object(conn, "_refresh_brand_token", mock_brand_refresh),
            patch.object(conn, "_refresh_mbb_from_refresh_token", mock_mbb_refresh),
        ):
            result = await conn.validate_tokens()

        assert result is True
        mock_idk_refresh.assert_called_once()
        mock_brand_refresh.assert_not_called()
        mock_mbb_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_failure_triggers_full_relogin(self):
        """Mock refresh failure for EMEA, verify doLogin() would be needed."""
        import jwt as pyjwt

        conn = _make_connection()
        past_exp = int(time.time()) - 100
        fake_payload = {"exp": past_exp, "sub": "test"}
        fake_token = pyjwt.encode(fake_payload, "secret", algorithm="HS256")
        conn._session_tokens["identity"] = {
            "access_token": fake_token,
            "id_token": fake_token,
            "refresh_token": "rt",
        }

        mock_refresh = AsyncMock(return_value=False)
        with patch.object(conn, "refresh_tokens", mock_refresh):
            result = await conn.validate_tokens()

        # When refresh fails, validate_tokens returns False (caller should re-login)
        assert result is False


# ---------------------------------------------------------------------------
# Action Methods Tests
# ---------------------------------------------------------------------------
class TestActionMethods:
    """Test every Connection action method."""

    @pytest.mark.asyncio
    async def test_setCharging_start(self):
        """Test setCharging with start action."""
        conn = _make_connection()
        conn.post = AsyncMock(return_value=_mock_action_response())
        result = await conn.setCharging(VIN, action="start")
        assert result is not None
        assert result.get("id") == "req-123"
        conn.post.assert_called_once()
        call_url = conn.post.call_args[0][0]
        assert "charging/start" in call_url

    @pytest.mark.asyncio
    async def test_setCharging_stop(self):
        """Test setCharging with stop action (falsy)."""
        conn = _make_connection()
        conn.post = AsyncMock(return_value=_mock_action_response())
        result = await conn.setCharging(VIN, action=False)
        assert result is not None
        call_url = conn.post.call_args[0][0]
        assert "charging/stop" in call_url

    @pytest.mark.asyncio
    async def test_setClimater_start(self):
        """Test setClimater with start action and data."""
        conn = _make_connection()
        conn.post = AsyncMock(return_value=_mock_action_response())
        data = {"targetTemperature_C": 22}
        result = await conn.setClimater(VIN, data=data, action="start")
        assert result is not None
        call_url = conn.post.call_args[0][0]
        assert "climatisation/start" in call_url

    @pytest.mark.asyncio
    async def test_setClimater_stop(self):
        """Test setClimater with stop action."""
        conn = _make_connection()
        conn.post = AsyncMock(return_value=_mock_action_response())
        result = await conn.setClimater(VIN, data={}, action=False)
        assert result is not None
        call_url = conn.post.call_args[0][0]
        assert "climatisation/stop" in call_url

    @pytest.mark.asyncio
    async def test_setClimaterSettings(self):
        """Test setClimaterSettings sends PUT to correct endpoint."""
        conn = _make_connection()
        conn.put = AsyncMock(return_value=_mock_action_response())
        data = {"targetTemperature_C": 20}
        result = await conn.setClimaterSettings(VIN, data=data)
        assert result is not None
        call_url = conn.put.call_args[0][0]
        assert "climatisation/settings" in call_url

    @pytest.mark.asyncio
    async def test_setClimatisationTimers(self):
        """Test setClimatisationTimers sends PUT to timers endpoint."""
        conn = _make_connection()
        conn.put = AsyncMock(return_value=_mock_action_response())
        data = {"timers": []}
        result = await conn.setClimatisationTimers(VIN, data=data)
        assert result is not None
        call_url = conn.put.call_args[0][0]
        assert "climatisation/timers" in call_url

    @pytest.mark.asyncio
    async def test_setAuxiliary_start(self):
        """Test setAuxiliary with start action."""
        conn = _make_connection()
        conn.post = AsyncMock(return_value=_mock_action_response())
        result = await conn.setAuxiliary(VIN, data={}, action="start")
        assert result is not None
        call_url = conn.post.call_args[0][0]
        assert "auxiliaryheating/start" in call_url

    @pytest.mark.asyncio
    async def test_setAuxiliary_stop(self):
        """Test setAuxiliary with stop action."""
        conn = _make_connection()
        conn.post = AsyncMock(return_value=_mock_action_response())
        result = await conn.setAuxiliary(VIN, data={}, action=False)
        assert result is not None
        call_url = conn.post.call_args[0][0]
        assert "auxiliaryheating/stop" in call_url

    @pytest.mark.asyncio
    async def test_setAuxiliaryHeatingTimers(self):
        """Test setAuxiliaryHeatingTimers sends PUT to timers endpoint."""
        conn = _make_connection()
        conn.put = AsyncMock(return_value=_mock_action_response())
        data = {"timers": []}
        result = await conn.setAuxiliaryHeatingTimers(VIN, data=data)
        assert result is not None
        call_url = conn.put.call_args[0][0]
        assert "auxiliaryheating/timers" in call_url

    @pytest.mark.asyncio
    async def test_setWindowHeater_start(self):
        """Test setWindowHeater with start action."""
        conn = _make_connection()
        conn.post = AsyncMock(return_value=_mock_action_response())
        result = await conn.setWindowHeater(VIN, action="start")
        assert result is not None
        call_url = conn.post.call_args[0][0]
        assert "windowheating/start" in call_url

    @pytest.mark.asyncio
    async def test_setWindowHeater_stop(self):
        """Test setWindowHeater with stop action."""
        conn = _make_connection()
        conn.post = AsyncMock(return_value=_mock_action_response())
        result = await conn.setWindowHeater(VIN, action=False)
        assert result is not None
        call_url = conn.post.call_args[0][0]
        assert "windowheating/stop" in call_url

    @pytest.mark.asyncio
    async def test_setLock_lock(self):
        """Test setLock with lock=True."""
        conn = _make_connection()
        conn.post = AsyncMock(return_value=_mock_action_response())
        conn.check_spin_state = AsyncMock(return_value=True)
        result = await conn.setLock(VIN, lock=True, spin="1234")
        assert result is not None
        call_url = conn.post.call_args[0][0]
        assert "access/lock" in call_url

    @pytest.mark.asyncio
    async def test_setLock_unlock(self):
        """Test setLock with lock=False."""
        conn = _make_connection()
        conn.post = AsyncMock(return_value=_mock_action_response())
        conn.check_spin_state = AsyncMock(return_value=True)
        result = await conn.setLock(VIN, lock=False, spin="1234")
        assert result is not None
        call_url = conn.post.call_args[0][0]
        assert "access/unlock" in call_url

    @pytest.mark.asyncio
    async def test_setHonkAndFlash(self):
        """Test setHonkAndFlash sends correct position data."""
        conn = _make_connection()
        conn.post = AsyncMock(return_value=_mock_action_response())
        conn.check_spin_state = AsyncMock(return_value=True)
        position = {"lat": 52.520, "lng": 13.405}
        result = await conn.setHonkAndFlash(VIN, position=position)
        assert result is not None
        call_url = conn.post.call_args[0][0]
        assert "honkandflash" in call_url
        # Verify position data is in the json payload
        call_kwargs = conn.post.call_args[1]
        json_data = call_kwargs.get("json", {})
        assert json_data["userPosition"]["latitude"] == 52.520
        assert json_data["userPosition"]["longitude"] == 13.405

    @pytest.mark.asyncio
    async def test_setChargingSettings(self):
        """Test setChargingSettings sends PUT to charging settings."""
        conn = _make_connection()
        conn.put = AsyncMock(return_value=_mock_action_response())
        data = {"maxChargeCurrentAC": "maximum"}
        result = await conn.setChargingSettings(VIN, data=data)
        assert result is not None
        call_url = conn.put.call_args[0][0]
        assert "charging/settings" in call_url

    @pytest.mark.asyncio
    async def test_setChargingCareModeSettings(self):
        """Test setChargingCareModeSettings sends PUT to care settings."""
        conn = _make_connection()
        conn.put = AsyncMock(return_value=_mock_action_response())
        data = {"batteryCareMode": "activated"}
        result = await conn.setChargingCareModeSettings(VIN, data=data)
        assert result is not None
        call_url = conn.put.call_args[0][0]
        assert "charging/care/settings" in call_url

    @pytest.mark.asyncio
    async def test_setReadinessBatterySupport(self):
        """Test setReadinessBatterySupport sends PUT to batterysupport."""
        conn = _make_connection()
        conn.put = AsyncMock(return_value=_mock_action_response())
        data = {"batterySupportEnabled": True}
        result = await conn.setReadinessBatterySupport(VIN, data=data)
        assert result is not None
        call_url = conn.put.call_args[0][0]
        assert "readiness/batterysupport" in call_url

    @pytest.mark.asyncio
    async def test_setDepartureProfiles(self):
        """Test setDepartureProfiles sends PUT to departure profiles."""
        conn = _make_connection()
        conn.put = AsyncMock(return_value=_mock_action_response())
        data = {"profiles": []}
        result = await conn.setDepartureProfiles(VIN, data=data)
        assert result is not None
        call_url = conn.put.call_args[0][0]
        assert "departure/profiles" in call_url

    @pytest.mark.asyncio
    async def test_setDepartureTimers(self):
        """Test setDepartureTimers sends PUT to departure timers."""
        conn = _make_connection()
        conn.put = AsyncMock(return_value=_mock_action_response())
        data = {"timers": []}
        result = await conn.setDepartureTimers(VIN, data=data)
        assert result is not None
        call_url = conn.put.call_args[0][0]
        assert "departure/timers" in call_url

    @pytest.mark.asyncio
    async def test_action_method_raises_api_error_on_exception(self):
        """Test that action methods wrap exceptions in APIError."""
        conn = _make_connection()
        conn.post = AsyncMock(side_effect=Exception("network failure"))
        with pytest.raises(APIError, match="setCharging"):
            await conn.setCharging(VIN, action="start")


# ---------------------------------------------------------------------------
# Data Fetch Methods Tests
# ---------------------------------------------------------------------------
class TestDataFetchMethods:
    """Test all data fetch methods."""

    @pytest.mark.asyncio
    async def test_getSelectiveStatus_returns_data(self):
        """Test getSelectiveStatus returns service data."""
        conn = _make_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn.get = AsyncMock(return_value={
            "charging": {"chargingState": "readyForCharging"},
            "climatisation": {"climatisationState": "off"},
        })
        result = await conn.getSelectiveStatus(VIN, services=["charging", "climatisation"])
        assert result is not None
        assert "refreshTimestamp" in result
        assert "charging" in result

    @pytest.mark.asyncio
    async def test_getSelectiveStatus_returns_false_on_invalid_tokens(self):
        """Test getSelectiveStatus returns False when token validation fails."""
        conn = _make_connection()
        conn.validate_tokens = AsyncMock(return_value=False)
        result = await conn.getSelectiveStatus(VIN, services=["charging"])
        assert result is False

    @pytest.mark.asyncio
    async def test_getVehicleData_returns_data(self):
        """Test getVehicleData returns vehicle data for matching VIN."""
        conn = _make_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn.get = AsyncMock(return_value={
            "data": [
                {"vin": VIN, "nickname": "My Car", "model": "ID.4"},
                {"vin": "OTHER_VIN", "nickname": "Other Car"},
            ]
        })
        result = await conn.getVehicleData(VIN)
        assert result is not None
        assert result["vehicle"]["vin"] == VIN

    @pytest.mark.asyncio
    async def test_getVehicleData_returns_false_for_unknown_vin(self):
        """Test getVehicleData returns False for VIN not in response."""
        conn = _make_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn.get = AsyncMock(return_value={
            "data": [{"vin": "OTHER_VIN", "nickname": "Other Car"}]
        })
        result = await conn.getVehicleData(VIN)
        assert result is False

    @pytest.mark.asyncio
    async def test_getParkingPosition_returns_data(self):
        """Test getParkingPosition returns position data."""
        conn = _make_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn.get = AsyncMock(return_value={
            "data": {"lat": 52.520, "lng": 13.405}
        })
        result = await conn.getParkingPosition(VIN)
        assert result is not None
        assert result["isMoving"] is False
        assert result["parkingposition"]["lat"] == 52.520

    @pytest.mark.asyncio
    async def test_getParkingPosition_204_is_moving(self):
        """Test getParkingPosition returns isMoving=True on 204."""
        conn = _make_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn.get = AsyncMock(return_value={"status_code": 204})
        result = await conn.getParkingPosition(VIN)
        assert result is not None
        assert result["isMoving"] is True

    @pytest.mark.asyncio
    async def test_getTripLast_returns_data(self):
        """Test getTripLast returns trip data."""
        conn = _make_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn.get = AsyncMock(return_value={
            "data": {"tripId": "123", "averageSpeed_kmph": 45}
        })
        result = await conn.getTripLast(VIN)
        assert result is not None
        assert "trip_last" in result

    @pytest.mark.asyncio
    async def test_getTripRefuel_returns_data(self):
        """Test getTripRefuel returns trip since last refuel."""
        conn = _make_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn.get = AsyncMock(return_value={
            "data": {"tripId": "456", "fuelConsumption_lper100km": 6.5}
        })
        result = await conn.getTripRefuel(VIN)
        assert result is not None
        assert "trip_refuel" in result

    @pytest.mark.asyncio
    async def test_getTripLongterm_returns_data(self):
        """Test getTripLongterm returns longterm trip data."""
        conn = _make_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn.get = AsyncMock(return_value={
            "data": {"tripId": "789", "totalDistance_km": 15000}
        })
        result = await conn.getTripLongterm(VIN)
        assert result is not None
        assert "trip_longterm" in result

    @pytest.mark.asyncio
    async def test_getPendingRequests_returns_data(self):
        """Test getPendingRequests returns pending request data."""
        conn = _make_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn.get = AsyncMock(return_value={
            "data": [{"id": "req-1", "status": "in_progress"}]
        })
        result = await conn.getPendingRequests(VIN)
        assert result is not None
        assert "refreshTimestamp" in result

    @pytest.mark.asyncio
    async def test_getOperationList_returns_data(self):
        """Test getOperationList returns capabilities."""
        conn = _make_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn.get = AsyncMock(return_value={
            "capabilities": [
                {"id": "charging", "status": [200]},
                {"id": "climatisation", "status": [200]},
            ]
        })
        result = await conn.getOperationList(VIN)
        assert result is not None
        assert "capabilities" in result

    @pytest.mark.asyncio
    async def test_getOperationList_handles_status_code_error(self):
        """Test getOperationList handles error status code."""
        conn = _make_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn.get = AsyncMock(return_value={"status_code": 404})
        result = await conn.getOperationList(VIN)
        assert result is not None
        assert result.get("status_code") == 404

    @pytest.mark.asyncio
    async def test_get_request_status_returns_status(self):
        """Test get_request_status translates pending request status."""
        conn = _make_connection()
        conn._session_logged_in = True
        conn.validate_tokens = AsyncMock(return_value=True)
        conn.getPendingRequests = AsyncMock(return_value={
            "data": [
                {"id": "req-abc", "status": "request_successful"},
                {"id": "req-other", "status": "in_progress"},
            ]
        })
        result = await conn.get_request_status(VIN, requestId="req-abc")
        assert result == "Success"

    @pytest.mark.asyncio
    async def test_get_request_status_in_progress(self):
        """Test get_request_status returns In Progress."""
        conn = _make_connection()
        conn._session_logged_in = True
        conn.validate_tokens = AsyncMock(return_value=True)
        conn.getPendingRequests = AsyncMock(return_value={
            "data": [{"id": "req-1", "status": "in_progress"}]
        })
        result = await conn.get_request_status(VIN, requestId="req-1")
        assert result == "In Progress"

    @pytest.mark.asyncio
    async def test_get_request_status_failed(self):
        """Test get_request_status returns Failed."""
        conn = _make_connection()
        conn._session_logged_in = True
        conn.validate_tokens = AsyncMock(return_value=True)
        conn.getPendingRequests = AsyncMock(return_value={
            "data": [{"id": "req-1", "status": "request_fail"}]
        })
        result = await conn.get_request_status(VIN, requestId="req-1")
        assert result == "Failed"

    @pytest.mark.asyncio
    async def test_get_request_status_unknown_id_returns_unknown(self):
        """Test get_request_status returns Unknown for unmatched request ID."""
        conn = _make_connection()
        conn._session_logged_in = True
        conn.validate_tokens = AsyncMock(return_value=True)
        conn.getPendingRequests = AsyncMock(return_value={
            "data": [{"id": "req-other", "status": "successful"}]
        })
        result = await conn.get_request_status(VIN, requestId="req-nonexistent")
        assert result == "Unknown"

    @pytest.mark.asyncio
    async def test_data_fetch_returns_false_on_exception(self):
        """Test that data fetch methods return False on exceptions."""
        conn = _make_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn.get = AsyncMock(side_effect=Exception("network error"))
        result = await conn.getTripLast(VIN)
        assert result is False


# ---------------------------------------------------------------------------
# Service Status Tests
# ---------------------------------------------------------------------------
class TestServiceStatus:
    """Test service status tracking."""

    @pytest.mark.asyncio
    async def test_update_service_status_stores_up(self):
        """Test that 200 response sets service status to Up."""
        conn = _make_connection()
        await conn.update_service_status("vehicle/v2/vehicles", 200)
        assert conn._service_status["vehicles"] == "Up"

    @pytest.mark.asyncio
    async def test_update_service_status_stores_unauthorized(self):
        """Test that 401 response sets service status to Unauthorized."""
        conn = _make_connection()
        await conn.update_service_status("selectivestatus", 401)
        assert conn._service_status["selectivestatus"] == "Unauthorized"

    @pytest.mark.asyncio
    async def test_update_service_status_stores_rate_limited(self):
        """Test that 429 response sets service status to Rate limited."""
        conn = _make_connection()
        await conn.update_service_status("token", 429)
        assert conn._service_status["token"] == "Rate limited"

    @pytest.mark.asyncio
    async def test_update_service_status_stores_down(self):
        """Test that 500 response sets service status to Down."""
        conn = _make_connection()
        await conn.update_service_status("parkingposition", 500)
        assert conn._service_status["parkingposition"] == "Down"

    @pytest.mark.asyncio
    async def test_get_service_status_returns_stored(self):
        """Test get_service_status returns full status dict."""
        conn = _make_connection()
        await conn.update_service_status("token", 200)
        result = await conn.get_service_status()
        assert result["token"] == "Up"

    @pytest.mark.asyncio
    async def test_get_service_status_default_empty(self):
        """Test get_service_status returns default dict for fresh connection."""
        conn = _make_connection()
        result = await conn.get_service_status()
        assert isinstance(result, dict)
