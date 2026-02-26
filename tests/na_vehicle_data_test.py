"""Unit tests for NA vehicle data properties (Phase 11)."""

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
