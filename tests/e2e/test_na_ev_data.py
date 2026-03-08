"""
E2E tests for NA EV charge summary, climate settings, and trip statistics endpoints.

For non-EV vehicles (e.g. Taos), the EV and climate endpoints return 404.
Tests skip gracefully in that case (not a failure).

Requires real VW credentials:
  export VW_TEST_USERNAME='...'
  export VW_TEST_PASSWORD='...'
Run with: pytest tests/e2e/test_na_ev_data.py -v
"""
import logging

import pytest

_log = logging.getLogger(__name__)

pytestmark = pytest.mark.asyncio(loop_scope="module")


class TestNAEVData:
    """EV charge summary endpoint tests."""

    async def test_na_ev_data_fetch(self, connection, vehicle):
        """_get_na_vehicle_data includes na_ev key (None for non-EV is acceptable)."""
        data = await connection._get_na_vehicle_data(vehicle.vin)
        assert data is not None
        assert "na_ev" in data
        _log.info("na_ev data: %s", data.get("na_ev"))

    async def test_na_battery_level(self, connection, vehicle):
        """battery_level is int 0-100 for EV, None for non-EV."""
        await connection._get_na_vehicle_data(vehicle.vin)
        # Populate vehicle states
        import asyncio
        data = await connection._get_na_vehicle_data(vehicle.vin)
        if data and data.get("na_ev") is None:
            pytest.skip("Vehicle is not electric — EV endpoint returned 404")
        level = vehicle.battery_level
        assert isinstance(level, int), f"battery_level expected int, got {type(level).__name__}"
        assert 0 <= level <= 100, f"battery_level={level} outside [0, 100]"

    async def test_na_charging_state(self, connection, vehicle):
        """charging is bool for EV vehicles."""
        data = await connection._get_na_vehicle_data(vehicle.vin)
        if data and data.get("na_ev") is None:
            pytest.skip("Vehicle is not electric — EV endpoint returned 404")
        assert isinstance(vehicle.charging, bool)

    async def test_na_charging_cable_connected(self, connection, vehicle):
        """charging_cable_connected is bool for EV vehicles."""
        data = await connection._get_na_vehicle_data(vehicle.vin)
        if data and data.get("na_ev") is None:
            pytest.skip("Vehicle is not electric — EV endpoint returned 404")
        assert isinstance(vehicle.charging_cable_connected, bool)

    async def test_na_charging_time_left(self, connection, vehicle):
        """charging_time_left is int >= 0 for EV vehicles."""
        data = await connection._get_na_vehicle_data(vehicle.vin)
        if data and data.get("na_ev") is None:
            pytest.skip("Vehicle is not electric — EV endpoint returned 404")
        assert isinstance(vehicle.charging_time_left, int)
        assert vehicle.charging_time_left >= 0


class TestNAClimateData:
    """Pre-trip climate settings endpoint tests."""

    async def test_na_climate_data_fetch(self, connection, vehicle):
        """_get_na_vehicle_data includes na_climate key (None for non-EV is acceptable)."""
        data = await connection._get_na_vehicle_data(vehicle.vin)
        assert data is not None
        assert "na_climate" in data
        _log.info("na_climate data: %s", data.get("na_climate"))

    async def test_na_climatisation_state(self, connection, vehicle):
        """climatisation_state is str for climate-capable vehicles."""
        data = await connection._get_na_vehicle_data(vehicle.vin)
        if data and data.get("na_climate") is None:
            pytest.skip("Climate endpoint not available for this vehicle")
        assert isinstance(vehicle.climatisation_state, str)

    async def test_na_climatisation_target_temperature(self, connection, vehicle):
        """climatisation_target_temperature is float for climate-capable vehicles."""
        data = await connection._get_na_vehicle_data(vehicle.vin)
        if data and data.get("na_climate") is None:
            pytest.skip("Climate endpoint not available for this vehicle")
        temp = vehicle.climatisation_target_temperature
        assert isinstance(temp, float), f"expected float, got {type(temp).__name__}"
        assert -30 <= temp <= 50, f"target temp={temp} outside plausible range"


class TestNATripData:
    """Remote trip statistics endpoint tests."""

    async def test_na_trip_data_fetch(self, connection, vehicle):
        """_get_na_vehicle_data includes na_trip key."""
        data = await connection._get_na_vehicle_data(vehicle.vin)
        assert data is not None
        assert "na_trip" in data
        _log.info("na_trip data: %s", data.get("na_trip"))

    async def test_na_last_trip_length(self, connection, vehicle):
        """last_trip_length is int >= 0 when trip data is available."""
        data = await connection._get_na_vehicle_data(vehicle.vin)
        if data and data.get("na_trip") is None:
            pytest.skip("Trip stats endpoint not available for this vehicle")
        length = vehicle.last_trip_length
        assert isinstance(length, (int, float)), f"expected numeric, got {type(length).__name__}"
        assert length >= 0

    async def test_na_last_trip_duration(self, connection, vehicle):
        """last_trip_duration is int >= 0 when trip data is available."""
        data = await connection._get_na_vehicle_data(vehicle.vin)
        if data and data.get("na_trip") is None:
            pytest.skip("Trip stats endpoint not available for this vehicle")
        duration = vehicle.last_trip_duration
        assert isinstance(duration, (int, float)), f"expected numeric, got {type(duration).__name__}"
        assert duration >= 0
