"""
E2E GPS coordinate assertions for live NA vehicle.

Validates that Phase 11's RVS location endpoint integration returns real GPS telemetry
from the production VW CarNet API — not None or fixture data.

These tests require real VW credentials and a live network connection.
Run with: pytest tests/e2e/test_na_position.py -v
"""
import logging
from datetime import datetime
from datetime import timezone

import pytest
import pytest_asyncio

_log = logging.getLogger(__name__)


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
class TestNAPosition:
    """E2E GPS coordinate assertions for live NA vehicle (TEST-07). Requires VW_TEST_USERNAME/VW_TEST_PASSWORD env vars."""

    pytestmark = pytest.mark.asyncio(loop_scope="module")

    async def test_position_is_not_none(self, first_vehicle):
        """Assert vehicle.position returns non-None lat/lng from a live NA vehicle."""
        pos = first_vehicle.position
        assert pos is not None, "vehicle.position returned None — RVS location endpoint may have failed"
        assert pos.get("lat") is not None, "vehicle.position['lat'] is None"
        assert pos.get("lng") is not None, "vehicle.position['lng'] is None"
        _log.info("vehicle.position: lat=%s, lng=%s, timestamp=%s", pos["lat"], pos["lng"], pos.get("timestamp"))

    async def test_position_coordinate_ranges(self, first_vehicle):
        """Assert GPS coordinates are valid floats within Earth's lat/lng bounds."""
        pos = first_vehicle.position
        if pos is None:
            pytest.skip("vehicle.position is None — surfaced by test_position_is_not_none")
        assert isinstance(pos["lat"], float), f"position['lat'] is not a float: {type(pos['lat']).__name__!r}"
        assert isinstance(pos["lng"], float), f"position['lng'] is not a float: {type(pos['lng']).__name__!r}"
        assert -90.0 <= pos["lat"] <= 90.0, f"latitude {pos['lat']} outside valid range [-90, 90]"
        assert -180.0 <= pos["lng"] <= 180.0, f"longitude {pos['lng']} outside valid range [-180, 180]"
        assert pos["lat"] != 0.0 or pos["lng"] != 0.0, (
            "position is (0.0, 0.0) — likely no-fix indicator, not a real location"
        )
        print(f"\n--- NA Position ---\nlat: {pos['lat']}\nlng: {pos['lng']}\ntimestamp: {pos.get('timestamp')}\n---")

    async def test_position_timestamp_freshness(self, first_vehicle):
        """Assert GPS timestamp is not None and is within 7 days."""
        pos = first_vehicle.position
        if pos is None:
            pytest.skip("vehicle.position is None — surfaced by test_position_is_not_none")
        ts_str = pos.get("timestamp")
        assert ts_str is not None, "vehicle.position['timestamp'] is None — RVS may not include timestamp"
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError as exc:
            pytest.fail(f"Could not parse GPS timestamp {ts_str!r}: {exc}")
        age_days = (datetime.now(timezone.utc) - ts).days
        assert age_days <= 7, f"GPS timestamp {ts_str!r} is older than 7 days"
        _log.info("GPS timestamp: %s (%d days ago)", ts_str, age_days)

    async def test_raw_rvs_position_field_and_freshness(self, first_vehicle):
        """Assert na_location raw RVS state has valid lat/lng and freshness (double coverage)."""
        na_loc = first_vehicle._states.get("na_location")
        if na_loc is None:
            pytest.fail("na_location not in vehicle._states — RVS location endpoint may have failed")
        assert na_loc.get("location") is not None, "na_location has no 'location' sub-dict"
        raw_lat = na_loc["location"].get("latitude")
        raw_lng = na_loc["location"].get("longitude")
        assert raw_lat is not None and raw_lng is not None, (
            "na_location['location'] missing 'latitude' or 'longitude' field"
        )
        assert isinstance(raw_lat, (int, float)), (
            f"raw latitude/longitude must be numeric, got {type(raw_lat).__name__!r}/{type(raw_lng).__name__!r}"
        )
        assert isinstance(raw_lng, (int, float)), (
            f"raw latitude/longitude must be numeric, got {type(raw_lat).__name__!r}/{type(raw_lng).__name__!r}"
        )
        print(
            f"\n--- Raw RVS Location ---\n"
            f"na_location['location']['latitude']: {raw_lat!r}\n"
            f"na_location['location']['longitude']: {raw_lng!r}\n"
            f"vehicle.position lat: {first_vehicle.position.get('lat')}\n"
            f"vehicle.position lng: {first_vehicle.position.get('lng')}\n"
            f"---"
        )
        _log.info("Raw na_location latitude=%r longitude=%r", raw_lat, raw_lng)
        ts_str = na_loc.get("eventTimeStamp")
        if ts_str is not None:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError as exc:
                pytest.fail(f"Could not parse RVS location timestamp {ts_str!r}: {exc}")
            age_days = (datetime.now(timezone.utc) - ts).days
            assert age_days <= 7, f"RVS location timestamp {ts_str!r} is older than 7 days"
        else:
            _log.warning("na_location has no 'eventTimeStamp' field — skipping freshness check")
