---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-02-26T17:47:40Z"
progress:
  total_phases: 12
  completed_phases: 11
  total_plans: 19
  completed_plans: 19
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-25)

**Core value:** NA users can authenticate with VW CarNet and retrieve vehicle data for homelab integration without breaking existing EMEA functionality.
**Current focus:** Milestone v1.5 — Full API Values (Phase 11 complete — NA vehicle session + RVS data fetch implemented; Phase 12 E2E validation ready)

## Current Position

Phase: 11-na-vehicle-data-implementation (complete)
Plan: 1 of 1 complete
Status: Phase 11 complete — carnetVehicleToken session creation + RVS telemetry fetch wired into Connection and Vehicle; EMEA paths unchanged; 123 tests pass
Last activity: 2026-02-26 - Completed Phase 11 Plan 1: NA vehicle session + RVS data fetch (vw_connection.py + vw_vehicle.py)

Progress: [█████████░] 96%

## Performance Metrics

**Velocity:**
- Total plans completed: 10
- Average duration: 3.2 min
- Total execution time: 0.49 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-na-foundation | 1 | 5 min | 5 min |
| 02-na-oauth-login-flow | 2 | 14 min | 7 min |
| 03-three-token-architecture | 3 | 8 min | 2.7 min |
| 04-token-lifecycle-management | 2 | 7 min | 3.5 min |
| 05-reliability-discovery | 3 | 8 min | 2.7 min |
| 08-fix-stale-unit-tests | 1 | 2 min | 2 min |
| 09-requirements-wording-cleanup | 1 | 2 min | 2 min |
| 10-na-vehicle-data-endpoint-research | 1 | 2 min | 2 min |
| 11-na-vehicle-data-implementation | 1 | 8 min | 8 min |

**Recent Trend:**
- Last 5 plans: 2 min, 2 min, 2 min, 2 min, 8 min
- Trend: fast

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 08-fix-stale-unit-tests]: NA base_api_candidates == [] is intentional — hardcoded base_api used directly, discovery candidates unused
- [Phase 09-requirements-wording-cleanup]: _na_tokens writes at login time now include issued_at: time.time() matching refresh method structure
- [Phase 09-requirements-wording-cleanup]: _refresh_idk_token() docstring corrected — X-QMAuth NOT sent (server rejects with HTTP 400), PKCE code_verifier used instead
- [Phase 08-fix-stale-unit-tests]: IDK refresh body must contain refresh_token, grant_type, code_verifier — X-QMAuth intentionally absent (HTTP 400)
- [Phase 08-fix-stale-unit-tests]: NA doLogin fetches vehicle list via _request() to garage endpoint, not get() to vehicle/v2/vehicles
- [Roadmap v1.5]: 3 phases (10-12) derived from 11 v1.5 requirements; APK research gates implementation gates E2E validation
- [Phase 07-end-to-end-validation]: Soft-assert pattern for vehicle data — None values soft-skipped (unsupported), not failed
- [Phase 07-end-to-end-validation]: expires_at key used for token expiry assertions (not 'expiry') — matches actual _na_tokens structure
- [NA auth confirmed 2026-02-25]: IDK-only flow confirmed working; Brand/MBB not available on NA Car-Net (`/login/v1/volkswagen/token` → 404)
- [NA auth confirmed 2026-02-25]: Vehicle list at `GET /account/v1/garage?idToken={idk_id_token}` — confirmed working
- [NA auth confirmed 2026-02-25]: `/vehicle/v1/vehicles/{vin}/capabilities` and selectivestatus return 404 for NA — different data API needed
- [Phase 10-na-vehicle-data-endpoint-research]: NA vehicle data requires carnetVehicleToken from POST ss/v1/user/{userId}/vehicle/{vehicleId}/session — separate from IDK auth
- [Phase 10-na-vehicle-data-endpoint-research]: RVS endpoints: /rvs/v1/vehicle/{vid} (status/lock) and /rvs/v1/location/vehicle/{vid} (GPS) are the NA equivalents of EMEA selectivestatus and location
- [Phase 11-na-vehicle-data-implementation]: tsp probe sequence ["VWNA", "VW"] — first 200 wins, logs which tsp succeeded for Phase 12 hard-coding
- [Phase 11-na-vehicle-data-implementation]: carnetVehicleToken cached in _na_tokens[vin]["vehicle_session"] with JWT exp-based TTL + 5min buffer
- [Phase 11-na-vehicle-data-implementation]: Vehicle.update() NA branch calls _update_na_vehicle() and returns immediately — EMEA asyncio.gather never reached for NA
- [Phase 11-na-vehicle-data-implementation]: RVS partial data returned even if one endpoint fails — None only when vehicle session creation fails entirely

### Pending Todos

None yet.

### Blockers/Concerns

- `tsp` enum value and auth header behavior for POST ss/v1/.../session unconfirmed until Phase 12 E2E runs live — probe logic in place
- `x-mobile-session-id` field name TBD — Phase 12 DEBUG logs will reveal correct field from live session response

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 1 | Add a scan for secrets into all github commits to prevent leakage | 2026-02-26 | a62795c | [1-add-a-scan-for-secrets-into-all-github-c](.planning/quick/1-add-a-scan-for-secrets-into-all-github-c/) |

## Session Continuity

Last session: 2026-02-26
Stopped at: Completed 11-01-PLAN.md (NA vehicle session + RVS data fetch — _create_na_vehicle_session + _get_na_vehicle_data on Connection, NA dispatch in Vehicle.update())
Resume file: None
