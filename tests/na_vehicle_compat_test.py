"""
NA-authenticated Vehicle property compatibility tests.

Proves that the Vehicle property layer is region-agnostic: the same EMEA fixture JSON
produces identical property values and types when accessed via an NA Connection vs an
EMEA Connection.

These tests verify the Python interface only (COMPAT-05). Which HTTP endpoints NA uses
to retrieve vehicle data is out of scope until Phase 7 (live credential validation).

Phase 6 plan 06-02 — COMPAT-05
"""
import json
import os
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock

from volkswagencarnet.vw_connection import Connection
from volkswagencarnet.vw_vehicle import Vehicle


def _make_na_conn() -> Connection:
    """Create a Connection with country='US' and mocked session, simulating post-login NA state."""
    sess = AsyncMock()
    sess._cookie_jar = MagicMock()
    sess._cookie_jar._cookies = {}
    conn = Connection(sess, "user@example.com", "password", country="US")
    conn._na_auth_level = "full"
    conn._na_tokens = {"idk": {"access_token": "idk_at", "refresh_token": "idk_rt", "id_token": "idk_id"}}
    conn._session_tokens = {"identity": {"access_token": "idk_at"}}
    conn._base_api = "https://b-h-s.spr.us00.p.con-veh.net"
    return conn


def _load_fixture(*path_parts) -> dict:
    """Load a fixture JSON file from tests/fixtures/resources/responses/."""
    fixture_path = os.path.join(
        os.path.dirname(__file__),
        "fixtures", "resources", "responses", *path_parts,
    )
    with open(fixture_path) as f:
        return json.load(f)


class NAVehiclePropertyCompatTest(IsolatedAsyncioTestCase):
    """Verify Vehicle properties return correct values under NA auth context.

    Technique: create NA Connection, inject EMEA fixture JSON via vehicle._states.update(),
    assert property values match known fixture content and types match the stable interface.

    The value assertions are annotated with the fixture key path so that future fixture
    changes are easy to trace. Type assertions are the durable interface contract.
    """

    async def test_egolf_battery_properties_via_na_conn(self):
        """Electric vehicle battery properties parse correctly from EMEA fixture under NA auth."""
        conn = _make_na_conn()
        vehicle = Vehicle(conn, "WVWZZZ3CZHE123456")
        vehicle._states.update(_load_fixture("egolf", "selectivestatus_by_app.json"))
        vehicle._discovered = True

        # charging.batteryStatus.value.currentSOC_pct: 71
        assert vehicle.battery_level == 71
        assert isinstance(vehicle.battery_level, int)

        # measurements.rangeStatus.value.electricRange: 116
        assert vehicle.battery_cruising_range == 116
        assert isinstance(vehicle.battery_cruising_range, int)

        assert vehicle.electric_range == 116
        assert isinstance(vehicle.electric_range, int)

    async def test_egolf_charging_properties_via_na_conn(self):
        """Charging state and support flags parse correctly from EMEA fixture under NA auth."""
        conn = _make_na_conn()
        vehicle = Vehicle(conn, "WVWZZZ3CZHE123456")
        vehicle._states.update(_load_fixture("egolf", "selectivestatus_by_app.json"))
        vehicle._discovered = True

        # charging.chargingStatus.value.chargingState
        assert vehicle.charging_state == "Not ready"
        assert isinstance(vehicle.charging_state, str)

        assert vehicle.is_battery_level_supported is True
        assert isinstance(vehicle.is_battery_level_supported, bool)

        assert vehicle.is_charging_supported is True
        assert isinstance(vehicle.is_charging_supported, bool)

        assert vehicle.is_electric_range_supported is True
        assert isinstance(vehicle.is_electric_range_supported, bool)

        # e-Golf is electric — no fuel
        assert vehicle.is_fuel_level_supported is False
        assert isinstance(vehicle.is_fuel_level_supported, bool)

    async def test_egolf_climatisation_properties_via_na_conn(self):
        """Climatisation properties parse correctly from EMEA fixture under NA auth."""
        conn = _make_na_conn()
        vehicle = Vehicle(conn, "WVWZZZ3CZHE123456")
        vehicle._states.update(_load_fixture("egolf", "selectivestatus_by_app.json"))
        vehicle._discovered = True

        # climatisation.climatisationStatus.value.climatisationState
        assert vehicle.climatisation_state == "off"
        assert isinstance(vehicle.climatisation_state, str)

        # climatisation target temperature
        assert vehicle.climatisation_target_temperature == 22.0
        assert isinstance(vehicle.climatisation_target_temperature, float)

        assert vehicle.is_climatisation_state_supported is True
        assert isinstance(vehicle.is_climatisation_state_supported, bool)

    async def test_egolf_door_and_access_properties_via_na_conn(self):
        """Door lock, door closed, trunk, and windows properties parse correctly under NA auth."""
        conn = _make_na_conn()
        vehicle = Vehicle(conn, "WVWZZZ3CZHE123456")
        vehicle._states.update(_load_fixture("egolf", "selectivestatus_by_app.json"))
        vehicle._discovered = True

        # NA region: door_locked reads from na_status["lockStatus"] (not EMEA selectivestatus).
        # Inject na_status fixture so the NA branch returns the expected locked state.
        vehicle._states["na_status"] = _load_fixture("na_vehicle", "rvs_status.json")
        assert vehicle.door_locked is True
        assert isinstance(vehicle.door_locked, bool)

        assert vehicle.door_closed_left_front is True
        assert isinstance(vehicle.door_closed_left_front, bool)

        # trunk
        assert vehicle.trunk_locked is True
        assert isinstance(vehicle.trunk_locked, bool)

        # windows
        assert vehicle.windows_closed is True
        assert isinstance(vehicle.windows_closed, bool)

    async def test_egolf_service_and_distance_properties_via_na_conn(self):
        """Service inspection and odometer properties parse correctly under NA auth."""
        conn = _make_na_conn()
        vehicle = Vehicle(conn, "WVWZZZ3CZHE123456")
        vehicle._states.update(_load_fixture("egolf", "selectivestatus_by_app.json"))
        vehicle._discovered = True

        # vehicleHealthInspection.maintenanceStatus.value.inspectionDue_days: 402
        assert vehicle.service_inspection == 402
        assert isinstance(vehicle.service_inspection, int)

        # vehicleHealthInspection.maintenanceStatus.value.mileage_km: 19795
        assert vehicle.service_inspection_distance == 19795
        assert isinstance(vehicle.service_inspection_distance, int)

        # measurements.odometerStatus.value.odometer: 74777
        assert vehicle.distance == 74777
        assert isinstance(vehicle.distance, int)

    async def test_egolf_vehicle_type_properties_via_na_conn(self):
        """car_type and is_car_type_electric parse correctly under NA auth."""
        conn = _make_na_conn()
        vehicle = Vehicle(conn, "WVWZZZ3CZHE123456")
        vehicle._states.update(_load_fixture("egolf", "selectivestatus_by_app.json"))
        vehicle._discovered = True

        assert vehicle.car_type == "Electric"
        assert isinstance(vehicle.car_type, str)

        assert vehicle.is_car_type_electric is True
        assert isinstance(vehicle.is_car_type_electric, bool)

    async def test_arteon_diesel_fuel_properties_via_na_conn(self):
        """Diesel vehicle fuel properties parse correctly from EMEA fixture under NA auth."""
        conn = _make_na_conn()
        vehicle = Vehicle(conn, "WVWZZZ3HZPK002581")
        vehicle._states.update(_load_fixture("arteon_2023_diesel", "selectivestatus_by_app.json"))
        vehicle._discovered = True

        # fuelStatus.rangeStatus.value.primaryEngine.currentFuelLevel_pct: 19
        assert vehicle.fuel_level == 19
        assert isinstance(vehicle.fuel_level, int)

        assert vehicle.is_fuel_level_supported is True
        assert isinstance(vehicle.is_fuel_level_supported, bool)

        # Arteon diesel has no battery — battery properties not supported
        assert vehicle.is_battery_level_supported is False
        assert isinstance(vehicle.is_battery_level_supported, bool)

        assert vehicle.is_electric_range_supported is False
        assert isinstance(vehicle.is_electric_range_supported, bool)


class NAGolfGteHybridCompatTest(IsolatedAsyncioTestCase):
    """Verify Golf GTE hybrid Vehicle properties under NA auth context.

    The Golf GTE is a plug-in hybrid with both fuel and charging services.
    This test confirms that both fuel and electric properties coexist correctly
    under an NA auth context — neither service type is suppressed.

    Actual values discovered from fixture (golf_gte_hybrid/selectivestatus_by_app.json):
      fuel_level = 37, is_fuel_level_supported = True
      battery_level = 65, is_battery_level_supported = True
      charging_state = 'Not ready', is_charging_supported = True
      climatisation_state = 'off', door_locked = False, car_type = 'Hybrid'
    """

    async def test_golf_gte_hybrid_has_both_fuel_and_charging_services_via_na_conn(self):
        """Hybrid vehicle reports both fuel and charging services as supported under NA auth."""
        conn = _make_na_conn()
        vehicle = Vehicle(conn, "WVWZZZ5KZME100000")
        vehicle._states.update(_load_fixture("golf_gte_hybrid", "selectivestatus_by_app.json"))
        vehicle._discovered = True

        # Golf GTE has charging — both services coexist
        assert vehicle.is_charging_supported is True
        assert isinstance(vehicle.is_charging_supported, bool)

        # Golf GTE has fuel — both services coexist
        assert vehicle.is_fuel_level_supported is True
        assert isinstance(vehicle.is_fuel_level_supported, bool)

        # Golf GTE has a traction battery (PHEV)
        assert vehicle.is_battery_level_supported is True
        assert isinstance(vehicle.is_battery_level_supported, bool)

    async def test_golf_gte_hybrid_charging_state_via_na_conn(self):
        """Hybrid charging state and battery level parse correctly under NA auth."""
        conn = _make_na_conn()
        vehicle = Vehicle(conn, "WVWZZZ5KZME100000")
        vehicle._states.update(_load_fixture("golf_gte_hybrid", "selectivestatus_by_app.json"))
        vehicle._discovered = True

        # charging.chargingStatus.value.chargingState: 'Not ready'
        assert vehicle.charging_state == "Not ready"
        assert isinstance(vehicle.charging_state, str)

        # charging.batteryStatus.value.currentSOC_pct: 65
        assert vehicle.battery_level == 65
        assert isinstance(vehicle.battery_level, int)
        assert 0 <= vehicle.battery_level <= 100

    async def test_golf_gte_hybrid_door_access_via_na_conn(self):
        """Hybrid door/lock access properties parse correctly under NA auth."""
        conn = _make_na_conn()
        vehicle = Vehicle(conn, "WVWZZZ5KZME100000")
        vehicle._states.update(_load_fixture("golf_gte_hybrid", "selectivestatus_by_app.json"))
        vehicle._discovered = True

        # door_locked returns a bool — fixture state: False (unlocked)
        assert vehicle.door_locked is False
        assert isinstance(vehicle.door_locked, bool)
