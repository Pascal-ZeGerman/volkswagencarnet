"""
E2E tests for North America vehicle data properties.

Covers TEST-03 (vehicle data property assertions) and TEST-06 (multi-vehicle count logging).
Uses soft-assert pattern so partial endpoint failures produce a summary, not immediate stop.

These tests require real VW credentials and a live network connection.
Run with: pytest tests/e2e/test_na_vehicle_data.py -v
"""

import logging

import pytest
import pytest_asyncio

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Soft-assert helpers — collect failures, raise summary at end
# ---------------------------------------------------------------------------


def _soft_assert(failures: list, condition: bool, msg: str) -> None:
    """Collect assertion failures; caller raises at end with full list."""
    if not condition:
        failures.append(msg)


def _check_int_or_none(failures, val, name, lo=None, hi=None):
    """Soft-assert that val is int (or None for unsupported property) within plausible range."""
    if val is None:
        return  # property not supported — soft skip, not failure
    _soft_assert(
        failures,
        isinstance(val, int),
        f"{name}: expected int, got {type(val).__name__}",
    )
    if lo is not None and val is not None:
        _soft_assert(
            failures,
            lo <= val <= hi,
            f"{name}={val} outside plausible range [{lo}, {hi}]",
        )


def _check_bool_or_none(failures, val, name):
    """Soft-assert that val is bool (or None for unsupported property)."""
    if val is None:
        return
    _soft_assert(
        failures,
        isinstance(val, bool),
        f"{name}: expected bool, got {type(val).__name__}",
    )


def _check_str_or_none(failures, val, name):
    """Soft-assert that val is a non-empty string (or None for unsupported property)."""
    if val is None:
        return
    _soft_assert(
        failures,
        isinstance(val, str),
        f"{name}: expected str, got {type(val).__name__}",
    )
    _soft_assert(failures, len(val) > 0, f"{name}: expected non-empty string")


# ---------------------------------------------------------------------------
# Module-scoped vehicle fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def first_vehicle(na_connection):
    """Return the first vehicle after calling conn.update(). Fails if no vehicles found."""
    await na_connection.update()
    vehicles = na_connection.vehicles
    if not vehicles:
        pytest.fail(
            "No vehicles returned after conn.update() — cannot test vehicle data"
        )
    v = vehicles[0]
    _log.info("Testing vehicle: VIN=%s, car_type=%s", v.vin, v.car_type)
    return v


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="module")
class TestNAVehicleData:
    """Vehicle data property assertions (TEST-03, TEST-06)."""

    pytestmark = pytest.mark.asyncio(loop_scope="module")

    async def test_vehicle_count_logged(self, na_connection):
        """TEST-06: Vehicle count is logged after conn.update()."""
        await na_connection.update()
        count = len(na_connection.vehicles)
        assert count >= 1, f"Expected at least 1 vehicle, got {count}"
        _log.info("Account has %d vehicle(s)", count)

    async def test_vehicle_basic_properties(self, first_vehicle):
        """TEST-03: VIN is 17 characters; car_type is a non-empty string if present."""
        failures = []
        _check_str_or_none(failures, first_vehicle.vin, "vin")
        _soft_assert(
            failures,
            first_vehicle.vin and len(first_vehicle.vin) == 17,
            f"VIN length should be 17: {first_vehicle.vin!r}",
        )
        _check_str_or_none(failures, first_vehicle.car_type, "car_type")
        if failures:
            raise AssertionError(
                "Vehicle basic property failures:\n"
                + "\n".join(f"  - {f}" for f in failures)
            )

    async def test_vehicle_electric_properties(self, first_vehicle):
        """TEST-03: Electric/hybrid properties have correct types and plausible ranges."""
        failures = []
        if not hasattr(first_vehicle, "is_electric") or not hasattr(
            first_vehicle, "is_hybrid"
        ):
            pytest.skip(
                "Vehicle does not expose is_electric/is_hybrid (NA vehicle data not loaded)"
            )
        if first_vehicle.is_electric or first_vehicle.is_hybrid:
            _check_int_or_none(
                failures, first_vehicle.battery_level, "battery_level", 0, 100
            )
            _check_int_or_none(
                failures, first_vehicle.electric_range, "electric_range", 0, 1000
            )
            _check_str_or_none(failures, first_vehicle.charging_state, "charging_state")
            _log.info(
                "Electric properties tested: battery_level=%s, electric_range=%s, charging_state=%s",
                first_vehicle.battery_level,
                first_vehicle.electric_range,
                first_vehicle.charging_state,
            )
        else:
            _log.info("Vehicle is not electric/hybrid — electric properties skipped")
        if failures:
            raise AssertionError(
                "Electric property failures:\n"
                + "\n".join(f"  - {f}" for f in failures)
            )

    async def test_vehicle_climate_properties(self, first_vehicle):
        """TEST-03: Climatisation properties have correct types if climatisation is supported."""
        failures = []
        if first_vehicle.is_climatisation_supported:
            _check_str_or_none(
                failures, first_vehicle.climatisation_state, "climatisation_state"
            )
            target_temp = first_vehicle.climatisation_target_temperature
            if target_temp is not None:
                _check_int_or_none(
                    failures,
                    int(target_temp),
                    "climatisation_target_temperature",
                    16,
                    30,
                )
            _log.info(
                "Climate properties tested: state=%s, target_temp=%s",
                first_vehicle.climatisation_state,
                target_temp,
            )
        else:
            _log.info(
                "Climatisation not supported on this vehicle — climate properties skipped"
            )
        if failures:
            raise AssertionError(
                "Climate property failures:\n" + "\n".join(f"  - {f}" for f in failures)
            )

    async def test_vehicle_door_lock_properties(self, first_vehicle):
        """TEST-03: Door/lock properties are bool type if present."""
        failures = []
        _check_bool_or_none(failures, first_vehicle.door_locked, "door_locked")
        _check_bool_or_none(
            failures, first_vehicle.door_closed_left_front, "door_closed_left_front"
        )
        _check_bool_or_none(failures, first_vehicle.trunk_locked, "trunk_locked")
        _check_bool_or_none(failures, first_vehicle.windows_closed, "windows_closed")
        if failures:
            raise AssertionError(
                "Door/lock property failures:\n"
                + "\n".join(f"  - {f}" for f in failures)
            )

    async def test_vehicle_service_properties(self, first_vehicle):
        """TEST-03: Service inspection and distance properties have correct types/ranges."""
        failures = []
        service_insp = first_vehicle.service_inspection
        service_insp_dist = first_vehicle.service_inspection_distance
        distance = first_vehicle.distance
        _check_str_or_none(failures, service_insp, "service_inspection")
        _check_int_or_none(
            failures, service_insp_dist, "service_inspection_distance", -100000, 100000
        )
        _check_int_or_none(failures, distance, "distance", 0, 10_000_000)
        # Log which properties returned values vs None
        _log.info(
            "Service properties: inspection=%s (got value: %s), inspection_dist=%s (got value: %s), distance=%s (got value: %s)",
            service_insp,
            service_insp is not None,
            service_insp_dist,
            service_insp_dist is not None,
            distance,
            distance is not None,
        )
        if failures:
            raise AssertionError(
                "Service property failures:\n" + "\n".join(f"  - {f}" for f in failures)
            )

    async def test_vehicle_support_flags_are_bool(self, first_vehicle):
        """TEST-03: Vehicle support flags are all bool type."""
        if not hasattr(first_vehicle, "is_electric"):
            pytest.skip(
                "Vehicle does not expose support flags (NA vehicle data not loaded)"
            )
        failures = []
        support_flags = [
            ("is_electric", first_vehicle.is_electric),
            ("is_hybrid", first_vehicle.is_hybrid),
            ("is_charging_supported", first_vehicle.is_charging_supported),
            ("is_climatisation_supported", first_vehicle.is_climatisation_supported),
        ]
        for name, val in support_flags:
            _soft_assert(
                failures,
                isinstance(val, bool),
                f"{name}: expected bool, got {type(val).__name__} ({val!r})",
            )
        if failures:
            raise AssertionError(
                "Support flag type failures:\n"
                + "\n".join(f"  - {f}" for f in failures)
            )
