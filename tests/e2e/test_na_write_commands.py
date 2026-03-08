"""
E2E tests for NA remote write commands: lock/unlock, honk & flash, EV charging, climate.

All tests are marked skip because they are destructive — they send real commands
to the vehicle. Run manually by setting ENABLE_WRITE_TESTS=1 and unsetting the skip.

Requires real VW credentials:
  export VW_TEST_USERNAME='...'
  export VW_TEST_PASSWORD='...'
Run with: pytest tests/e2e/test_na_write_commands.py -v
"""

import logging

import pytest

_log = logging.getLogger(__name__)

pytestmark = pytest.mark.asyncio(loop_scope="module")


class TestNALockUnlock:
    """Remote lock/unlock via /lockunlock/v1/ endpoint."""

    @pytest.mark.skip(reason="Destructive — sends real lock command to vehicle")
    async def test_na_lock_returns_true(self, connection, vehicle):
        """lock_na returns True on success."""
        result = await connection.lock_na(vehicle.vin, action="lock")
        assert result is True, "lock_na should return True on success"
        _log.info("lock_na result: %s", result)

    @pytest.mark.skip(reason="Destructive — sends real unlock command to vehicle")
    async def test_na_unlock_returns_true(self, connection, vehicle):
        """lock_na with action=unlock returns True on success."""
        result = await connection.lock_na(vehicle.vin, action="unlock")
        assert result is True, "lock_na(unlock) should return True on success"
        _log.info("unlock_na result: %s", result)


class TestNAHonkAndFlash:
    """Remote honk & flash via /honkflash/v1/ endpoint."""

    @pytest.mark.skip(reason="Destructive — sends real honk+flash command to vehicle")
    async def test_na_honk_and_flash_returns_true(self, connection, vehicle):
        """honk_and_flash_na returns True on success."""
        result = await connection.honk_and_flash_na(vehicle.vin)
        assert result is True, "honk_and_flash_na should return True on success"
        _log.info("honk_and_flash_na result: %s", result)


class TestNAEVCharging:
    """EV charging start/stop via /ev/v1/.../charging/start|stop."""

    @pytest.mark.skip(reason="Destructive — sends real charging start command")
    async def test_na_start_charging_returns_true(self, connection, vehicle):
        """start_charging_na returns True on success."""
        result = await connection.start_charging_na(vehicle.vin)
        assert result is True
        _log.info("start_charging_na result: %s", result)

    @pytest.mark.skip(reason="Destructive — sends real charging stop command")
    async def test_na_stop_charging_returns_true(self, connection, vehicle):
        """stop_charging_na returns True on success."""
        result = await connection.stop_charging_na(vehicle.vin)
        assert result is True
        _log.info("stop_charging_na result: %s", result)


class TestNAClimatisation:
    """Pre-trip climate start/stop via /ev/v1/.../pretripclimate/start|stop."""

    @pytest.mark.skip(reason="Destructive — sends real climate start command")
    async def test_na_start_climatisation_returns_true(self, connection, vehicle):
        """start_climatisation_na returns True on success."""
        result = await connection.start_climatisation_na(vehicle.vin)
        assert result is True
        _log.info("start_climatisation_na result: %s", result)

    @pytest.mark.skip(reason="Destructive — sends real climate stop command")
    async def test_na_stop_climatisation_returns_true(self, connection, vehicle):
        """stop_climatisation_na returns True on success."""
        result = await connection.stop_climatisation_na(vehicle.vin)
        assert result is True
        _log.info("stop_climatisation_na result: %s", result)
