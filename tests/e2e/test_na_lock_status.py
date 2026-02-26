"""
E2E lock status assertions for live NA vehicle.

Validates that Phase 11's RVS status endpoint integration returns the correct door lock state
from the production VW CarNet API.

These tests require real VW credentials, a live network connection, and the
VW_TEST_EXPECTED_LOCK environment variable.

Run with:
  export VW_TEST_EXPECTED_LOCK=locked   # if vehicle is locked
  export VW_TEST_EXPECTED_LOCK=unlocked # if vehicle is unlocked
  pytest tests/e2e/test_na_lock_status.py -v
"""
import logging
import os
from datetime import datetime
from datetime import timezone

import pytest
import pytest_asyncio

_log = logging.getLogger(__name__)

_EXPECTED_LOCK_RAW = os.environ.get("VW_TEST_EXPECTED_LOCK")  # "locked" or "unlocked"


# ---------------------------------------------------------------------------
# Module-scoped vehicle fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def first_vehicle(na_connection):
    """Return the first vehicle after calling conn.update(). Fails if no vehicles found."""
    await na_connection.update()
    vehicles = na_connection.vehicles
    if not vehicles:
        pytest.fail("No vehicles returned after conn.update()")
    return vehicles[0]


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="module")
class TestNALockStatus:
    """E2E lock status assertions for live NA vehicle (TEST-08). Requires VW_TEST_EXPECTED_LOCK=locked|unlocked env var."""

    pytestmark = pytest.mark.asyncio(loop_scope="module")

    async def test_expected_lock_env_var_set(self):
        """Assert VW_TEST_EXPECTED_LOCK is set to a valid value before any lock tests run."""
        if _EXPECTED_LOCK_RAW is None:
            pytest.fail(
                "VW_TEST_EXPECTED_LOCK is not set. Set it to 'locked' or 'unlocked' before running this test.\n"
                "  export VW_TEST_EXPECTED_LOCK=locked\n"
                "  export VW_TEST_EXPECTED_LOCK=unlocked"
            )
        assert _EXPECTED_LOCK_RAW.lower() in ("locked", "unlocked"), (
            f"VW_TEST_EXPECTED_LOCK must be 'locked' or 'unlocked', got {_EXPECTED_LOCK_RAW!r}"
        )

    async def test_door_locked_is_bool(self, first_vehicle):
        """Assert vehicle.door_locked returns a bool from a live NA vehicle."""
        if _EXPECTED_LOCK_RAW is None:
            pytest.skip("VW_TEST_EXPECTED_LOCK not set — see test_expected_lock_env_var_set")
        locked = first_vehicle.door_locked
        assert isinstance(locked, bool), (
            f"vehicle.door_locked returned {type(locked).__name__!r}, expected bool"
        )
        print(f"\n--- NA Lock Status ---\nvehicle.door_locked: {locked}\nExpected: {_EXPECTED_LOCK_RAW.lower()}\n---")

    async def test_door_locked_matches_expected(self, first_vehicle):
        """Assert vehicle.door_locked matches VW_TEST_EXPECTED_LOCK."""
        if _EXPECTED_LOCK_RAW is None:
            pytest.skip("VW_TEST_EXPECTED_LOCK not set")
        expected_bool = _EXPECTED_LOCK_RAW.lower() == "locked"
        locked = first_vehicle.door_locked
        assert locked == expected_bool, (
            f"Lock state mismatch: vehicle.door_locked={locked}, "
            f"VW_TEST_EXPECTED_LOCK={_EXPECTED_LOCK_RAW!r} (expected {expected_bool})"
        )

    async def test_raw_rvs_lock_field_and_freshness(self, first_vehicle):
        """Assert na_status raw RVS state has lockStatus field and freshness (double coverage)."""
        na_status = first_vehicle._states.get("na_status")
        if na_status is None:
            pytest.fail("na_status not in vehicle._states — RVS endpoint may have failed")
        raw_lock = na_status.get("lockStatus")
        assert raw_lock is not None, "na_status['lockStatus'] is None or missing"
        print(
            f"\n--- Raw RVS Lock ---\n"
            f"na_status['lockStatus']: {raw_lock!r}\n"
            f"vehicle.door_locked: {first_vehicle.door_locked}\n"
            f"---"
        )
        _log.info("Raw lockStatus=%r -> door_locked=%s", raw_lock, first_vehicle.door_locked)
        # Check freshness: try top-level "timestamp" first, then nested doorStatusTimestamp
        ts_str = na_status.get("timestamp")
        if ts_str is None:
            ts_str = (
                na_status.get("exteriorStatus", {})
                .get("doorStatus", {})
                .get("doorStatusTimestamp")
            )
        if ts_str is not None:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError as exc:
                pytest.fail(f"Could not parse RVS status timestamp {ts_str!r}: {exc}")
            age_days = (datetime.now(timezone.utc) - ts).days
            assert age_days <= 7, f"RVS status timestamp {ts_str!r} is older than 7 days"
        else:
            _log.warning("na_status has no timestamp field — skipping freshness check")
