---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Phases
status: unknown
last_updated: "2026-02-28T01:22:06.464Z"
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 2
  completed_plans: 1
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-27)

**Core value:** NA users can authenticate with VW CarNet and retrieve real vehicle data (GPS + lock status) for homelab integration without breaking existing EMEA functionality.
**Current focus:** Milestone v1.1 — Make Production Ready (Phases 15-20)

## Current Position

Phase: 15-na-error-handling (in progress)
Plan: 1 of ? — 15-01 complete
Status: 15-01 complete — NA exception propagation implemented
Last activity: 2026-02-27 - Phase 15 Plan 01 complete (2 tasks, 156 tests pass)

Progress: [#         ] 5%

## Performance Metrics

**Velocity (v1.0 history):**
- Total plans completed: 23
- Average duration: 3.2 min
- Total execution time: ~1.2 hours

**By Phase (v1.0):**

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
| 11-na-vehicle-data-implementation | 2 | 8 min | 8 min |
| 12-full-api-values-e2e-validation | 1 | 2 min | 2 min |
| 12.1-fix-na-vehicle-session-tsp | 1 | 3 min | 3 min |
| 13-display-of-real-values-and-uat | 1 | 14 min | 14 min |

**Recent Trend:**
- Last 5 plans: 2 min, 2 min, 2 min, 3 min, 14 min
- Trend: varies by task complexity

*Updated after each plan completion*
| Phase 15-na-error-handling P01 | 127 | 2 tasks | 2 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 08-fix-stale-unit-tests]: NA base_api_candidates == [] is intentional — hardcoded base_api used directly, discovery candidates unused
- [Phase 09-requirements-wording-cleanup]: _na_tokens writes at login time now include issued_at: time.time() matching refresh method structure
- [Phase 09-requirements-wording-cleanup]: _refresh_idk_token() docstring corrected — X-QMAuth NOT sent (server rejects with HTTP 400), PKCE code_verifier used instead
- [Phase 08-fix-stale-unit-tests]: IDK refresh body must contain refresh_token, grant_type, code_verifier — X-QMAuth intentionally absent (HTTP 400)
- [Phase 08-fix-stale-unit-tests]: NA doLogin fetches vehicle list via _request() to garage endpoint, not get() to vehicle/v2/vehicles
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
- [Phase 11-na-vehicle-data-implementation]: NA branch guard checks _session_region == 'NA' before dispatching to _na_* helpers — safe for Vehicle(None, vin) construction
- [Phase 11-na-vehicle-data-implementation]: compat test updated to inject na_status fixture for NA door_locked test — NA vehicles use na_status, not EMEA selectivestatus, for lock state
- [Phase 12-full-api-values-e2e-validation]: Double-coverage pattern — E2E tests assert both vehicle property (abstraction) AND raw _states[key] (data pipeline) for GPS and lock status
- [Phase 12-full-api-values-e2e-validation]: VW_TEST_EXPECTED_LOCK env var required (hard fail if not set) — prevents silent false-positive pass when env var forgotten
- [Phase 12.1-fix-na-vehicle-session-tsp-values-and-spin-challenge-response-flow]: tspProvider from garage response stored in _na_tokens[vin]['tsp_provider'] during doLogin() — VWNA and VW are NOT valid TSP enum values (return HTTP 400), ATC is default
- [Phase 12.1-fix-na-vehicle-session-tsp-values-and-spin-challenge-response-flow]: vehicleId UUID stored in _na_tokens[vin]['vehicle_id'] for potential future use if session URL needs UUID instead of VIN
- [Phase 13-display-of-real-values-from-api-and-manual-uat]: Demo script VW_SPIN env var documented as required for vehicle data; connection uses proven CookieJar + Connection(country='US', spin=spin) pattern
- [Phase 13-display-of-real-values-from-api-and-manual-uat]: UAT confirmed live values: lat=40.677629, lng=-73.968527, door_locked=True for VIN 3VV4X7B27RM030662 — milestone v1.0 complete
- [Phase 15-na-error-handling]: _login_na() AuthenticationError/RedirectError now re-raise instead of returning False
- [Phase 15-na-error-handling]: doLogin() NA garage 404 path raises APIError with endpoint URL and country='US' guidance

### Roadmap Evolution

- v1.0: Phases 1-13 shipped 2026-02-27
- v1.1: Phases 15-20 planned 2026-02-27 (phase 14 intentionally skipped to avoid confusion with v1.0 phase count of 14)

### Pending Todos

None yet for v1.1.

### Blockers/Concerns

- `x-mobile-session-id` field name TBD — not yet confirmed from live session response; CLEAN-03 addresses this in Phase 19

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 1 | Add a scan for secrets into all github commits to prevent leakage | 2026-02-26 | a62795c | [1-add-a-scan-for-secrets-into-all-github-c](.planning/quick/1-add-a-scan-for-secrets-into-all-github-c/) |

## Session Continuity

Last session: 2026-02-27
Stopped at: v1.1 roadmap created — 6 phases (15-20), 25 requirements mapped, ready for /gsd:plan-phase 15
Resume file: None
