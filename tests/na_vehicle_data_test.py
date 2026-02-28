"""Unit tests for NA vehicle data properties (Phase 11) and RVS retry logic (Phase 15)."""

import json
import os
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from volkswagencarnet.vw_vehicle import Vehicle
from volkswagencarnet.vw_connection import Connection


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "resources" / "responses" / "na_vehicle"


def _load_fixture(filename: str) -> dict:
    with open(FIXTURE_DIR / filename) as f:
        return json.load(f)


def _make_na_vehicle(states: dict | None = None) -> Vehicle:
    """Create an NA Vehicle with mocked Connection."""
    conn = MagicMock(spec=Connection)
    conn._session_region = "NA"
    vehicle = Vehicle(conn, "WVWZZZ3HZPK002581")
    if states:
        vehicle._states.update(states)
    return vehicle


def _make_emea_vehicle(states: dict | None = None) -> Vehicle:
    """Create an EMEA Vehicle with mocked Connection."""
    conn = MagicMock(spec=Connection)
    conn._session_region = "EMEA"
    conn._session_region_config = {"homeregion": "https://msg.volkswagen.de"}
    vehicle = Vehicle(conn, "WVWZZZ3HZPK002581")
    if states:
        vehicle._states.update(states)
    return vehicle


class NAVehicleDataTest(IsolatedAsyncioTestCase):
    """Tests for NA vehicle data properties."""

    def test_position_returns_lat_lng_from_na_location(self):
        fixture_data = _load_fixture("rvs_location.json")
        vehicle = _make_na_vehicle(states={"na_location": fixture_data})
        assert vehicle.position == {
            "lat": 37.7749295,
            "lng": -122.4194155,
            "timestamp": "2026-01-15T14:30:00Z",
        }

    def test_position_returns_none_when_na_location_absent(self):
        vehicle = _make_na_vehicle()
        assert vehicle.position == {"lat": None, "lng": None, "timestamp": None}

    def test_position_raises_value_error_on_malformed_na_location(self):
        vehicle = _make_na_vehicle(states={"na_location": {"location": {}}})
        with pytest.raises(ValueError):
            _ = vehicle.position

    def test_door_locked_true_when_lockstatus_locked(self):
        fixture_data = _load_fixture("rvs_status.json")
        vehicle = _make_na_vehicle(states={"na_status": fixture_data})
        assert vehicle.door_locked is True

    def test_door_locked_false_when_lockstatus_unlocked(self):
        fixture_data = _load_fixture("rvs_status_unlocked.json")
        vehicle = _make_na_vehicle(states={"na_status": fixture_data})
        assert vehicle.door_locked is False

    def test_door_locked_false_when_na_status_absent(self):
        vehicle = _make_na_vehicle()
        assert vehicle.door_locked is False

    def test_door_locked_raises_value_error_on_missing_lockstatus(self):
        vehicle = _make_na_vehicle(states={"na_status": {"platform": "VW_NA"}})
        with pytest.raises(ValueError):
            _ = vehicle.door_locked

    def test_is_position_supported_true_when_na_location_present(self):
        vehicle = _make_na_vehicle(
            states={"na_location": {"location": {"latitude": 1.0, "longitude": 2.0}}}
        )
        assert vehicle.is_position_supported is True

    def test_is_position_supported_false_when_na_location_absent(self):
        vehicle = _make_na_vehicle()
        assert vehicle.is_position_supported is False

    def test_is_door_locked_supported_true_when_na_status_present(self):
        vehicle = _make_na_vehicle(states={"na_status": {"lockStatus": "LOCKED"}})
        assert vehicle.is_door_locked_supported is True

    def test_is_door_locked_supported_false_when_na_status_absent(self):
        vehicle = _make_na_vehicle()
        assert vehicle.is_door_locked_supported is False

    def test_emea_position_unaffected_by_na_branch(self):
        vehicle = _make_emea_vehicle()
        # EMEA fallback: no parking data -> exception -> {"lat": "?", "lng": "?"}
        assert vehicle.position == {"lat": "?", "lng": "?"}

    def test_emea_door_locked_unaffected_by_na_branch(self):
        vehicle = _make_emea_vehicle()
        # EMEA path: find_path returns None, None != "locked" -> False
        assert vehicle.door_locked is False

    async def test_update_na_vehicle_calls_get_na_vehicle_data(self):
        vehicle = _make_na_vehicle()
        vehicle._discovered = True
        vehicle._connection._get_na_vehicle_data = AsyncMock(
            return_value={
                "na_location": _load_fixture("rvs_location.json"),
                "na_status": _load_fixture("rvs_status.json"),
            }
        )
        result = await vehicle._update_na_vehicle()
        assert result is True
        assert vehicle._states.get("na_location") is not None
        assert vehicle._states.get("na_status") is not None

    async def test_update_na_vehicle_returns_false_on_none_response(self):
        vehicle = _make_na_vehicle()
        vehicle._discovered = True
        vehicle._connection._get_na_vehicle_data = AsyncMock(return_value=None)
        result = await vehicle._update_na_vehicle()
        assert result is False

    async def test_discover_na_skips_capability_endpoints(self):
        vehicle = _make_na_vehicle()
        vehicle._discovered = False
        vehicle._connection.getOperationList = AsyncMock()

        with patch.object(vehicle, "_ensure_home_region", new_callable=AsyncMock):
            await vehicle.discover()

        assert vehicle._discovered is True
        vehicle._connection.getOperationList.assert_not_called()


# ---------------------------------------------------------------------------
# Phase 15-02: RVS 5xx retry tests
# ---------------------------------------------------------------------------

_RETRY_VIN = "TESTVIN123"
# JWT payload {"sub": "test-user-id"} (no signature verification needed)
_FAKE_IDK_ID_TOKEN = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ0ZXN0LXVzZXItaWQifQ.sig"


def _make_mock_response(status, json_data=None, text_data=""):
    """Build a lightweight mock aiohttp response for retry tests."""
    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.text = AsyncMock(return_value=text_data)
    mock_resp.json = AsyncMock(return_value=json_data if json_data is not None else {})
    return mock_resp


def _make_retry_connection() -> Connection:
    """Create a minimal NA Connection pre-loaded with tokens for retry testing."""
    sess = MagicMock()
    conn = Connection(sess, "user@test.com", "password", country="US")
    conn._base_api = "https://b-h-s.spr.us00.p.con-veh.net"
    conn._na_tokens = {
        "idk": {
            "id_token": _FAKE_IDK_ID_TOKEN,
            "access_token": "fake-access-token",
        },
        _RETRY_VIN: {
            "vehicle_id": "test-vehicle-uuid",
            "vehicle_session": {
                "token": "fake.vehicle.token",
                "expires_at": 9999999999,
                "issued_at": 0,
            },
        },
    }
    conn.validate_tokens = AsyncMock(return_value=True)
    conn._create_na_vehicle_session = AsyncMock(return_value="fake.vehicle.token")
    return conn


class RVSRetryTest(IsolatedAsyncioTestCase):
    """Tests for RVS 5xx retry behavior in _get_na_vehicle_data() (Phase 15-02)."""

    @patch("volkswagencarnet.vw_connection.asyncio.sleep", new_callable=AsyncMock)
    async def test_rvs_5xx_retry_location(self, _mock_sleep):
        """On 5xx from RVS location: retries up to RVS_MAX_RETRIES times and succeeds on 3rd attempt.

        With RVS_MAX_RETRIES=2: 1 initial + 2 retries = 3 total attempts.
        The mock returns 503, 503, 200 (success on 3rd attempt).
        The session.get mock must be called at least 3 times total (location retries alone).
        """
        conn = _make_retry_connection()
        location_success = {"latitude": 40.0, "longitude": -74.0}
        status_success = {"lockStatus": "LOCKED"}

        # 3 calls for location (2x 503 + 1x 200), then 1 for status
        conn._session.get = AsyncMock(side_effect=[
            _make_mock_response(503, text_data="Service Unavailable"),   # location attempt 1
            _make_mock_response(503, text_data="Service Unavailable"),   # location attempt 2
            _make_mock_response(200, json_data=location_success),        # location attempt 3 — success
            _make_mock_response(200, json_data=status_success),          # status succeeds
        ])

        result = await conn._get_na_vehicle_data(_RETRY_VIN)

        # Retry is observable: mock called >= 3 times (two 503s + one 200 for location)
        assert conn._session.get.call_count >= 3
        # Location data is returned (success on 3rd attempt)
        assert result is not None
        assert result["na_location"] is not None
        assert result["na_location"] == location_success

    @patch("volkswagencarnet.vw_connection.asyncio.sleep", new_callable=AsyncMock)
    async def test_rvs_5xx_retry_exhausted(self, _mock_sleep):
        """When all RVS retry attempts return 5xx, the method returns a dict with None values.

        With RVS_MAX_RETRIES=2: 3 total attempts for each endpoint.
        All 6 calls (3 location + 3 status) return 503.
        Method must NOT raise — returns {"na_location": None, "na_status": None}.
        """
        conn = _make_retry_connection()

        # All 6 attempts return 503 (3 for location, 3 for status)
        conn._session.get = AsyncMock(side_effect=[
            _make_mock_response(503, text_data="Service Unavailable"),  # location attempt 1
            _make_mock_response(503, text_data="Service Unavailable"),  # location attempt 2
            _make_mock_response(503, text_data="Service Unavailable"),  # location attempt 3 → give up
            _make_mock_response(503, text_data="Service Unavailable"),  # status attempt 1
            _make_mock_response(503, text_data="Service Unavailable"),  # status attempt 2
            _make_mock_response(503, text_data="Service Unavailable"),  # status attempt 3 → give up
        ])

        result = await conn._get_na_vehicle_data(_RETRY_VIN)

        # Must return a dict, not raise an exception
        assert result is not None
        assert isinstance(result, dict)
        # Both values are None (all retries exhausted)
        assert result.get("na_location") is None
        assert result.get("na_status") is None
