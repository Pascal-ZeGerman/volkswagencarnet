"""Unit tests for Phase 22: constants extraction, _fetch_rvs_endpoint helper, and is_na property."""

from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from volkswagencarnet.vw_connection import Connection
from volkswagencarnet.vw_const import (
    APP_VERSION,
    APP_VERSION_SHORT,
    MAX_REDIRECT_DEPTH,
    COUNTRY_TO_LOCALE,
    USER_AGENT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_VIN = "TESTVIN22PHASE001"


def _make_mock_response(status, json_data=None, text_data=""):
    """Build a lightweight mock aiohttp response."""
    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.text = AsyncMock(return_value=text_data)
    mock_resp.json = AsyncMock(return_value=json_data if json_data is not None else {})
    return mock_resp


def _make_na_connection() -> Connection:
    """Create a minimal NA Connection for _fetch_rvs_endpoint testing."""
    sess = MagicMock()
    conn = Connection(sess, "user@test.com", "password", country="US")
    conn._base_api = "https://b-h-s.spr.us00.p.con-veh.net"
    conn._na_tokens = {
        _TEST_VIN: {
            "vehicle_session": {
                "token": "fake.vehicle.token",
                "expires_at": 9999999999,
                "issued_at": 0,
            },
        },
    }
    conn._create_na_vehicle_session = AsyncMock(return_value="refreshed.vehicle.token")
    return conn


# ---------------------------------------------------------------------------
# _fetch_rvs_endpoint tests
# ---------------------------------------------------------------------------


class FetchRvsEndpointTest(IsolatedAsyncioTestCase):
    """Tests for the _fetch_rvs_endpoint helper method."""

    async def test_fetch_rvs_endpoint_200_returns_parsed_json(self):
        """200 response returns parsed JSON dict directly."""
        conn = _make_na_connection()
        expected = {"lockStatus": "LOCKED", "platform": "VW_NA"}
        conn._session.get = AsyncMock(return_value=_make_mock_response(200, json_data=expected))

        result = await conn._fetch_rvs_endpoint(
            url="https://example.com/rvs/v1/vehicle/VIN",
            vin=_TEST_VIN,
            rvs_headers={"Authorization": "Bearer token"},
            label="status",
        )

        assert result == expected

    async def test_fetch_rvs_endpoint_200_unwraps_data_key(self):
        """200 response with {"data": {...}} envelope unwraps the inner dict."""
        conn = _make_na_connection()
        inner = {"latitude": 40.0, "longitude": -74.0}
        conn._session.get = AsyncMock(
            return_value=_make_mock_response(200, json_data={"data": inner})
        )

        result = await conn._fetch_rvs_endpoint(
            url="https://example.com/rvs/v1/location/vehicle/VIN",
            vin=_TEST_VIN,
            rvs_headers={"Authorization": "Bearer token"},
            label="location",
        )

        assert result == inner

    async def test_fetch_rvs_endpoint_401_refreshes_session_and_retries(self):
        """401 triggers session recreation, updates headers, and retries the request."""
        conn = _make_na_connection()
        expected = {"lockStatus": "LOCKED"}
        conn._session.get = AsyncMock(side_effect=[
            _make_mock_response(401),                         # first attempt: 401
            _make_mock_response(200, json_data=expected),     # retry after session refresh
        ])

        headers = {"Authorization": "Bearer old-token"}
        result = await conn._fetch_rvs_endpoint(
            url="https://example.com/rvs/v1/vehicle/VIN",
            vin=_TEST_VIN,
            rvs_headers=headers,
            label="status",
        )

        assert result == expected
        conn._create_na_vehicle_session.assert_called_once_with(_TEST_VIN)
        assert headers["Authorization"] == "Bearer refreshed.vehicle.token"

    async def test_fetch_rvs_endpoint_401_returns_none_when_session_refresh_fails(self):
        """401 with failed session recreation returns None immediately."""
        conn = _make_na_connection()
        conn._create_na_vehicle_session = AsyncMock(return_value=None)
        conn._session.get = AsyncMock(return_value=_make_mock_response(401))

        result = await conn._fetch_rvs_endpoint(
            url="https://example.com/rvs/v1/vehicle/VIN",
            vin=_TEST_VIN,
            rvs_headers={"Authorization": "Bearer token"},
            label="status",
        )

        assert result is None

    @patch("volkswagencarnet.vw_connection.asyncio.sleep", new_callable=AsyncMock)
    async def test_fetch_rvs_endpoint_5xx_retries_with_backoff(self, _mock_sleep):
        """5xx responses retry up to RVS_MAX_RETRIES times, succeeding on last attempt."""
        conn = _make_na_connection()
        expected = {"lockStatus": "LOCKED"}
        conn._session.get = AsyncMock(side_effect=[
            _make_mock_response(503, text_data="Service Unavailable"),  # attempt 1
            _make_mock_response(503, text_data="Service Unavailable"),  # attempt 2
            _make_mock_response(200, json_data=expected),               # attempt 3 (success)
        ])

        result = await conn._fetch_rvs_endpoint(
            url="https://example.com/rvs/v1/vehicle/VIN",
            vin=_TEST_VIN,
            rvs_headers={"Authorization": "Bearer token"},
            label="status",
        )

        assert result == expected
        assert conn._session.get.call_count == 3

    async def test_fetch_rvs_endpoint_non_5xx_non_200_breaks_immediately(self):
        """403/404 does not retry \u2014 returns None after first attempt."""
        conn = _make_na_connection()
        conn._session.get = AsyncMock(
            return_value=_make_mock_response(403, text_data="Forbidden")
        )

        result = await conn._fetch_rvs_endpoint(
            url="https://example.com/rvs/v1/vehicle/VIN",
            vin=_TEST_VIN,
            rvs_headers={"Authorization": "Bearer token"},
            label="status",
        )

        assert result is None
        assert conn._session.get.call_count == 1

    async def test_fetch_rvs_endpoint_exception_returns_none(self):
        """Network exception is caught and returns None."""
        conn = _make_na_connection()
        conn._session.get = AsyncMock(side_effect=Exception("Connection reset"))

        result = await conn._fetch_rvs_endpoint(
            url="https://example.com/rvs/v1/vehicle/VIN",
            vin=_TEST_VIN,
            rvs_headers={"Authorization": "Bearer token"},
            label="status",
        )

        assert result is None


# ---------------------------------------------------------------------------
# Connection.is_na property tests
# ---------------------------------------------------------------------------


class IsNaPropertyTest(IsolatedAsyncioTestCase):
    """Tests for Connection.is_na property."""

    def test_is_na_true_for_us_country(self):
        """country='US' sets session_region to NA, so is_na returns True."""
        sess = MagicMock()
        conn = Connection(sess, "user@test.com", "password", country="US")
        assert conn.is_na is True

    def test_is_na_false_for_de_country(self):
        """country='DE' defaults to EMEA region, so is_na returns False."""
        sess = MagicMock()
        conn = Connection(sess, "user@test.com", "password", country="DE")
        assert conn.is_na is False


# ---------------------------------------------------------------------------
# Extracted constants tests
# ---------------------------------------------------------------------------


class ConstantsTest(IsolatedAsyncioTestCase):
    """Tests for Phase 22-01 extracted constants."""

    def test_constants_used_in_user_agent(self):
        """USER_AGENT string contains APP_VERSION_SHORT."""
        assert APP_VERSION_SHORT in USER_AGENT
        assert "Volkswagen/" in USER_AGENT

    def test_app_version_format(self):
        """APP_VERSION matches expected format pattern."""
        assert APP_VERSION == "2025.12.10-8414"

    def test_max_redirect_depth_is_positive_int(self):
        """MAX_REDIRECT_DEPTH is a positive integer."""
        assert isinstance(MAX_REDIRECT_DEPTH, int)
        assert MAX_REDIRECT_DEPTH > 0

    def test_country_to_locale_has_expected_keys(self):
        """COUNTRY_TO_LOCALE contains US, CA, GB mappings."""
        assert "US" in COUNTRY_TO_LOCALE
        assert "CA" in COUNTRY_TO_LOCALE
        assert "GB" in COUNTRY_TO_LOCALE
        assert COUNTRY_TO_LOCALE["US"] == "en-US"
