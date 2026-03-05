---
phase: 05-reliability-discovery
plan: "02"
subsystem: api
tags: [vehicle, home-region, discovery, aiohttp, na, routing]

# Dependency graph
requires:
  - phase: 05-01-reliability-discovery
    provides: VW_DOMAIN_ALLOWLIST, _discover_market_config(), centralized retry, _is_allowed_vw_domain()
provides:
  - Vehicle._home_region_discovered flag (session cache guard)
  - Vehicle._ensure_home_region() async method (lazy NA home region discovery)
  - Vehicle.home_region_url property (HA debugging)
  - discover() wired to call _ensure_home_region() at entry
affects: [06-emea-compat, home-assistant-integration, vehicle-api-calls]

# Tech tracking
tech-stack:
  added: [aiohttp.ClientTimeout (module-level import)]
  patterns:
    - "Optimistic lock: set guard flag BEFORE async work to prevent concurrent re-entry"
    - "Any HTTP response (200/400/401/403/404) = server reachable (probe pattern)"
    - "Lazy discovery: expensive network probe deferred until first actual use"
    - "Fallback retention: failed discovery silently keeps initialized value, logs WARNING"

key-files:
  created: []
  modified:
    - volkswagencarnet/vw_vehicle.py

key-decisions:
  - "Guard flag set at entry (not exit) of _ensure_home_region() — optimistic lock prevents concurrent probe storms"
  - "EMEA returns immediately without network calls — static config, no probe needed"
  - "Domain allowlist validation before probing each candidate — security guard against config injection"
  - "HTTP 200/400/401/403/404 all count as reachable — auth errors prove routing works, not auth state"

patterns-established:
  - "Optimistic guard pattern: bool flag set True at start of async work before any await"
  - "Lazy vehicle-level discovery: _ensure_home_region() called in discover(), cached for session"

requirements-completed: [INT-04]

# Metrics
duration: 1min
completed: 2026-02-19
---

# Phase 5 Plan 02: Reliability Discovery Summary

**Lazy per-vehicle NA home region discovery via candidate URL probing with domain allowlist validation, wired into Vehicle.discover()**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-19T00:42:48Z
- **Completed:** 2026-02-19T00:44:22Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Added `_home_region_discovered: bool = False` guard flag in `Vehicle.__init__()` to cache discovery state
- Implemented `_ensure_home_region()` async method: probes NA homeregion_candidates, validates each via `_is_allowed_vw_domain()`, assigns first responding server to `self._homeregion`, falls back silently with WARNING log
- Added `home_region_url` property exposing `self._homeregion` for Home Assistant debugging and logging
- Wired `await self._ensure_home_region()` at the very start of `discover()` so discovery is always complete before capability fetching
- EMEA vehicles return immediately without any network calls — static regional config is used as-is

## Task Commits

Each task was committed atomically:

1. **Task 1: _home_region_discovered flag, _ensure_home_region(), home_region_url property, wire into discover()** - `03a7a4d` (feat)

**Plan metadata:** _(to be committed with SUMMARY.md)_

## Files Created/Modified
- `volkswagencarnet/vw_vehicle.py` - Added ClientTimeout import, _home_region_discovered flag, _ensure_home_region() method, home_region_url property, and discover() hook

## Decisions Made
- Guard flag set at entry (not exit) of `_ensure_home_region()` — optimistic lock prevents concurrent probe storms on the same vehicle across multiple asyncio tasks
- EMEA returns immediately without network calls — home region is statically configured, no probe needed
- Domain allowlist validation before probing each candidate — guards against config injection or malformed entries in homeregion_candidates
- HTTP 200/400/401/403/404 all count as "reachable" — auth errors prove routing works; 5xx or connection errors mean the server is not serving this vehicle

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- INT-04 fulfilled: NA vehicles now discover their correct home region server on first API call
- `home_region_url` property available for Home Assistant entity attributes and logging
- 05-03 can proceed: both VW_DOMAIN_ALLOWLIST (05-01) and home region discovery (05-02) are in place

---
*Phase: 05-reliability-discovery*
*Completed: 2026-02-19*
