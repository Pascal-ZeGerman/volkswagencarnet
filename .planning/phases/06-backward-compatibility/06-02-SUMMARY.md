---
phase: 06-backward-compatibility
plan: "02"
subsystem: testing
tags: [python, pytest, vehicle, compatibility, na-auth, tdd, fixture]

# Dependency graph
requires:
  - phase: 06-01-backward-compatibility
    provides: Phase 6 Plan 01 EMEA compat test foundation
  - phase: 05-reliability-discovery
    provides: NA Connection with _na_auth_level, _na_tokens, _base_api attributes
  - phase: 03-three-token-architecture
    provides: Connection with _session_tokens structure
provides:
  - tests/na_vehicle_compat_test.py with NAVehiclePropertyCompatTest (7 tests, e-Golf + Arteon)
  - tests/na_vehicle_compat_test.py with NAGolfGteHybridCompatTest (3 tests, Golf GTE PHEV)
  - COMPAT-05 verified: Vehicle property layer confirmed region-agnostic
  - Fixture-injection pattern for NA auth context testing
affects: [07-live-validation, future-na-vehicle-tests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_make_na_conn() factory sets _na_auth_level='full', _na_tokens, _session_tokens, _base_api for NA post-login simulation"
    - "_load_fixture(*path_parts) for loading JSON from tests/fixtures/resources/responses/"
    - "vehicle._states.update(data) + vehicle._discovered = True for state injection without network calls"
    - "Value assertions annotated with fixture key path for traceability; type assertions as durable interface contract"
    - "Hybrid vehicle discovered-value pattern: run probe script first, then write exact assertions"

key-files:
  created:
    - tests/na_vehicle_compat_test.py
  modified: []

key-decisions:
  - "Golf GTE hybrid values discovered at runtime before writing assertions: fuel_level=37, battery_level=65, charging_state='Not ready', door_locked=False, car_type='Hybrid'"
  - "vw_vehicle.py has zero property-layer region-branching — 4 region references are in home region endpoint discovery only, not in data-reading properties"
  - "NAGolfGteHybridCompatTest uses exact charging_state assertion ('Not ready') not just type check — fixture values are stable"

patterns-established:
  - "NA compat test pattern: _make_na_conn() + vehicle._states.update(fixture) + vehicle._discovered = True"
  - "Hybrid fixture probe script (Step 1) before writing assertions for less-documented vehicles"

requirements-completed: [COMPAT-05]

# Metrics
duration: 2min
completed: 2026-02-19
---

# Phase 6 Plan 02: NA Vehicle Property Compatibility Tests Summary

**10 pytest tests across 2 classes confirming Vehicle property layer is region-agnostic: e-Golf, Arteon diesel, and Golf GTE hybrid all return correct typed values when state injected via NA-authenticated Connection**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-19T18:17:38Z
- **Completed:** 2026-02-19T18:19:51Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Created `tests/na_vehicle_compat_test.py` with `NAVehiclePropertyCompatTest` (7 tests: e-Golf battery/charging/climatisation/door-access/service-distance/vehicle-type + Arteon diesel fuel) and `NAGolfGteHybridCompatTest` (3 tests: PHEV dual-service coexistence/charging state+SOC/door access)
- Verified COMPAT-05: EMEA fixture JSON produces identical property values and types when accessed via NA Connection — confirmed by all tests passing without any code changes to vw_vehicle.py
- Confirmed vw_vehicle.py has zero property-layer region branching (4 region-related lines are in home region endpoint discovery methods only, not in any data-reading properties)
- Full suite: 123 passed, 2 skipped (expected integration tests), zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: NAVehiclePropertyCompatTest for e-Golf and Arteon** - `037212c` (test)
2. **Task 2: NAGolfGteHybridCompatTest and full suite verification** - `eee57f0` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `tests/na_vehicle_compat_test.py` - 10 NA-auth Vehicle property compatibility tests across 3 vehicle types (e-Golf electric, Arteon diesel, Golf GTE PHEV); 249 lines

## Verified Property Values

**e-Golf electric (egolf/selectivestatus_by_app.json):**
- battery_level = 71 (int), battery_cruising_range = 116 (int), electric_range = 116 (int)
- charging_state = 'Not ready' (str), climatisation_state = 'off' (str)
- climatisation_target_temperature = 22.0 (float), door_locked = True (bool)
- service_inspection = 402 (int), service_inspection_distance = 19795 (int), distance = 74777 (int)
- car_type = 'Electric' (str), is_car_type_electric = True (bool)
- is_battery_level_supported = True, is_charging_supported = True, is_fuel_level_supported = False

**Arteon diesel (arteon_2023_diesel/selectivestatus_by_app.json):**
- fuel_level = 19 (int), is_fuel_level_supported = True
- is_battery_level_supported = False, is_electric_range_supported = False

**Golf GTE hybrid (golf_gte_hybrid/selectivestatus_by_app.json) — discovered at runtime:**
- fuel_level = 37 (int), is_fuel_level_supported = True
- battery_level = 65 (int), is_battery_level_supported = True
- charging_state = 'Not ready' (str), is_charging_supported = True
- climatisation_state = 'off' (str), door_locked = False (bool), car_type = 'Hybrid' (str)

## Region-Branching Confirmation

```
grep -c "session_region\|_na_auth" volkswagencarnet/vw_vehicle.py
4
```

All 4 matches are in `_homeregion` property and `_ensure_home_region()` — home region endpoint discovery, not property value reading. Zero region-branching in any data property.

## Decisions Made

- Golf GTE hybrid values discovered at runtime before writing assertions: fixture probe script in Task 2 Step 1 confirmed exact values for durable assertions
- Used exact `charging_state == "Not ready"` assertion (not just type check) — fixture values are stable and exact assertions catch regressions

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all 7 e-Golf and Arteon assertions passed on first run. Hybrid values matched runtime probe exactly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 6 both plans complete: EMEA compat test foundation (06-01) + NA Vehicle property compat tests (06-02)
- COMPAT-05 verified: Vehicle property layer confirmed region-agnostic
- Phase 7 (live validation) can proceed — Vehicle data properties need no changes for NA support
- The fixture injection pattern (`_make_na_conn()` + `vehicle._states.update()`) is reusable for any future NA vehicle tests

---
*Phase: 06-backward-compatibility*
*Completed: 2026-02-19*
