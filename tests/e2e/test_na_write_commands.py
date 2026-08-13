"""
E2E tests for NA remote write commands: lock/unlock, honk & flash, EV charging, climate.

All tests are marked skip by default because they are destructive — they send real commands
to the vehicle. To enable, set the ENABLE_WRITE_TESTS environment variable:

  export ENABLE_WRITE_TESTS=1
  export VW_TEST_USERNAME='...'
  export VW_TEST_PASSWORD='...'
  pytest tests/e2e/test_na_write_commands.py -v
"""

import logging
import os

import pytest

_log = logging.getLogger(__name__)

pytestmark = pytest.mark.asyncio(loop_scope="module")

_skip_write = pytest.mark.skipif(
    not os.environ.get("ENABLE_WRITE_TESTS"),
    reason="Destructive — set ENABLE_WRITE_TESTS=1 to run",
)


class TestNALockUnlock:
    """Remote lock/unlock via /lockunlock/v1/ endpoint."""

    @_skip_write
    async def test_na_lock_returns_true(self, na_connection, first_vehicle):
        """lock_na returns True on success."""
        result = await na_connection.lock_na(first_vehicle.vin, action="lock")
        assert result is True, "lock_na should return True on success"
        _log.info("lock_na result: %s", result)

    @_skip_write
    async def test_na_unlock_returns_true(self, na_connection, first_vehicle):
        """lock_na with action=unlock returns True on success."""
        result = await na_connection.lock_na(first_vehicle.vin, action="unlock")
        assert result is True, "lock_na(unlock) should return True on success"
        _log.info("unlock_na result: %s", result)


class TestNAHonkAndFlash:
    """Remote honk & flash via /honkflash/v1/ endpoint."""

    @_skip_write
    async def test_na_honk_and_flash_returns_true(self, na_connection, first_vehicle):
        """honk_and_flash_na returns True on success."""
        result = await na_connection.honk_and_flash_na(first_vehicle.vin)
        assert result is True, "honk_and_flash_na should return True on success"
        _log.info("honk_and_flash_na result: %s", result)


class TestNAEVCharging:
    """EV charging start/stop via /ev/v1/.../charging/start|stop."""

    @_skip_write
    async def test_na_start_charging_returns_true(self, na_connection, first_vehicle):
        """start_charging_na returns True on success."""
        result = await na_connection.start_charging_na(first_vehicle.vin)
        assert result is True
        _log.info("start_charging_na result: %s", result)

    @_skip_write
    async def test_na_stop_charging_returns_true(self, na_connection, first_vehicle):
        """stop_charging_na returns True on success."""
        result = await na_connection.stop_charging_na(first_vehicle.vin)
        assert result is True
        _log.info("stop_charging_na result: %s", result)


class TestNAClimatisation:
    """Pre-trip climate start/stop via /ev/v1/.../pretripclimate/start|stop."""

    @_skip_write
    async def test_na_start_climatisation_returns_true(
        self, na_connection, first_vehicle
    ):
        """start_climatisation_na returns True on success."""
        result = await na_connection.start_climatisation_na(first_vehicle.vin)
        assert result is True
        _log.info("start_climatisation_na result: %s", result)

    @_skip_write
    async def test_na_stop_climatisation_returns_true(
        self, na_connection, first_vehicle
    ):
        """stop_climatisation_na returns True on success."""
        result = await na_connection.stop_climatisation_na(first_vehicle.vin)
        assert result is True
        _log.info("stop_climatisation_na result: %s", result)
