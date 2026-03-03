---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Phases
status: unknown
last_updated: "2026-03-03T04:36:10.907Z"
progress:
  total_phases: 17
  completed_phases: 12
  total_plans: 30
  completed_plans: 35
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-27)

**Core value:** NA users can authenticate with VW CarNet and retrieve real vehicle data (GPS + lock status) for homelab integration without breaking existing EMEA functionality.
**Current focus:** Milestone v1.1 — Make Production Ready (Phases 15-20)

## Current Position

Phase: 23-create-holistic-test-suite-with-comprehensive-code-coverage
Plan: 6 of 6 complete (23-01, 23-02, 23-03, 23-04, 23-05, 23-06 complete)
Status: Phase 23 complete -- 973 tests, 82% vw_connection.py coverage (target 80%+ met)
Last activity: 2026-03-03 - Completed 23-05 (connection coverage gap closure: 51 new tests, 61% to 82%)

Progress: [###       ] 15%

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
| Phase 15-na-error-handling P02 | 177 | 2 tasks | 3 files |
| Phase 16-type-hints P01 | 12 | 2 tasks | 3 files |
| Phase 16-type-hints P02 | 12 | 2 tasks | 2 files |
| Phase 16-type-hints P03 | 25 | 2 tasks | 2 files |
| Phase 17-logging P01 | 2 | 2 tasks | 3 files |
| Phase 17-logging P02 | 3 | 2 tasks | 1 file |
| Phase 22-fix-medium-nitpick P01 | 2 | 2 tasks | 2 files |
| Phase 22-fix-medium-nitpick P02 | 3 | 2 tasks | 3 files |
| Phase 23-connection-tests P01 | 4 | 2 tasks | 8 files |
| Phase 23 P04 | 5 | 2 tasks | 5 files |
| Phase 23 P06 | 7 | 2 tasks | 1 file |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 21-01]: User chose Option A: full git history rewrite with filter-repo to scrub testing_creds.env from all commits
- [Phase 21-01]: Force-push required to propagate rewritten history to remote; PR #1 must be recreated
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
- [Phase 15-na-error-handling]: RVS_MAX_RETRIES = 2: 1 initial + 2 retries = 3 total attempts for 5xx transient errors
- [Phase 15-na-error-handling]: Non-5xx non-200 RVS responses break immediately without retry (403/404 not transient)
- [Phase 16-type-hints]: vw_connection.py typed with X|None syntax and Any for aiohttp types; disallow_untyped_defs scoped per-file in setup.cfg
- [Phase 16-type-hints P02]: vin property asserts self._url is not None and returns str — all action methods rely on non-None VIN
- [Phase 16-type-hints P02]: Connection action methods (setCharging/setClimater/setAuxiliary/setWindowHeater/setLock) accept bool | str for action param — code uses bool expressions (action == "start")
- [Phase 16-type-hints P02]: assert self._connection is not None pattern in action methods rather than if/return guards
- [Phase 16-type-hints]: windows_closed returns bool|None; departure_timer_enabled/ac_departure_timer_enabled use None guard returning False; vehicle() unique_id None guard added
- [Phase 17-logging P01]: redact() uses value[:8]+"..." — first 8 chars identifies token prefix while hiding the secret; handles None/"" with single `if not value` guard returning "(none)"
- [Phase 17-logging P01]: NullHandler added to root package logger 'volkswagencarnet' in __init__.py per Python logging best practices for library authors
- [Phase 17-logging P02]: _exchange_code_for_tokens refactored — bare return json_loads(resp_text) replaced with tokens_data variable + DEBUG log + return, avoiding double parse
- [Phase 17-logging P02]: redact(vin) used for VINs in all new log calls — VINs are 17 chars, first 8 shown is sufficient for correlation without exposing full VIN
- [Phase 17-logging P02]: RVS URL logs outside retry loop; per-attempt HTTP status logs inside loop — best coverage without duplication
- [Phase 22-01]: APP_VERSION/APP_VERSION_SHORT constants in vw_const.py; USER_AGENT uses f-string with APP_VERSION_SHORT
- [Phase 22-01]: COUNTRY_TO_LOCALE kept minimal (US, CA, GB) matching original local dict; MAX_REDIRECT_DEPTH promoted to module-level
- [Phase 22-02]: _fetch_rvs_endpoint returns None on 401 session recreation failure — no further retries
- [Phase 22-02]: Test mocks set is_na explicitly — MagicMock(spec=Connection) returns truthy MagicMock for unset property attributes
- [Phase 23-01]: AsyncMock-based method mocking preferred over aioresponses for Connection tests (mock session doesn't integrate with aioresponses ClientSession patching)
- [Phase 23-01]: Action method tests mock post/put at Connection level for cleaner URL assertions; _make_connection() factory pattern established
- [Phase 23]: vw_connection.py (61%) and vw_vehicle.py (64%) remain below 80% -- large files with OAuth/action method gaps; dashboard 80%, utilities 86% met targets
- [Phase 23-05]: test_set_schedule repurposed to test setDepartureTimers — no setSchedule method exists in codebase
- [Phase 23-05]: vw_connection.py coverage raised from 61% to 82% — 51 new tests covering OAuth helpers, NA auth code flow, MBB tokens, action exceptions

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

Last session: 2026-03-03
Stopped at: Completed 23-05-PLAN.md — Connection coverage gap closure (973 tests, 82% vw_connection.py)
Resume file: None
