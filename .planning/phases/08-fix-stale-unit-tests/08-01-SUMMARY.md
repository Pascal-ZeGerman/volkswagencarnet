---
phase: 08-fix-stale-unit-tests
plan: 01
subsystem: testing
tags: [pytest, unit-tests, na-oauth, pkce, discovery, region-config]

# Dependency graph
requires:
  - phase: 05-reliability-discovery
    provides: market config discovery with empty base_api_candidates
  - phase: 04-token-lifecycle-management
    provides: IDK refresh without X-QMAuth header
provides:
  - 0 failing unit tests — CI is trustworthy for Phase 9 advance
  - Fixed assertions for NA empty candidates design
  - Fixed IDK refresh body param assertions (no X-QMAuth)
  - patch.dict pattern for testing discovery with injected candidates
affects:
  - 09-requirements-validation
  - future test authors working with NA discovery

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Use patch.dict(REGION_CONFIGS['NA'], {'base_api_candidates': [...]}) to inject candidates for discovery tests"
    - "NA doLogin uses _request() for garage endpoint, not get() — mock _request not get in integration tests"

key-files:
  created: []
  modified:
    - tests/vw_connection_test.py
    - tests/region_support_test.py
    - tests/reliability_test.py

key-decisions:
  - "NA base_api_candidates == [] is intentional — hardcoded base_api used directly, discovery candidates unused"
  - "IDK refresh body must contain refresh_token, grant_type, code_verifier — X-QMAuth intentionally absent (HTTP 400)"
  - "NA doLogin fetches vehicle list via _request() to garage endpoint, not get() to vehicle/v2/vehicles"

patterns-established:
  - "patch.dict for REGION_CONFIGS: inject fake candidates without modifying production config"
  - "Test against actual production behavior, not outdated behavior that was never shipped"

requirements-completed:
  - MGMT-02
  - INT-01

# Metrics
duration: 2min
completed: 2026-02-26
---

# Phase 8 Plan 1: Fix Stale Unit Tests Summary

**6 stale NA unit tests fixed across 3 files: IDK refresh body params, empty candidates design, and doLogin flow updated to reflect confirmed production behavior**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-26T04:33:21Z
- **Completed:** 2026-02-26T04:35:48Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Fixed 6 failing unit tests with 0 production code changes (test-only fixes)
- Corrected stale X-QMAuth header assertion to body param assertions for IDK refresh retry test
- Updated NA config test to assert empty candidates (intentional design) instead of non-empty
- Rewrote discovery test to verify fallback behavior (returns False, preserves hardcoded base_api)
- Fixed doLogin discovery test to patch `_request` instead of `get` for the NA garage endpoint path
- Added `patch.dict(REGION_CONFIGS["NA"], ...)` pattern for testing discovery with injected candidates
- Full unit suite: 123 passed, 0 failed, 2 skipped (integration, creds not set)

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix IDK refresh test in vw_connection_test.py** - `851e5f1` (fix)
2. **Task 2: Fix NA config and discovery tests in region_support_test.py** - `820eca0` (fix)
3. **Task 3: Fix discovery tests in reliability_test.py via candidate patching** - `9893220` (fix)

## Files Created/Modified

- `tests/vw_connection_test.py` - Renamed and rewrote `test_idk_refresh_uses_fresh_xqmauth_per_attempt` to `test_idk_refresh_retries_up_to_three_times`; replaced X-QMAuth header assertions with body param assertions
- `tests/region_support_test.py` - Fixed `test_na_config_has_candidates` (empty list), `test_discovery_finds_working_endpoint` (fallback behavior), `test_login_calls_discovery_on_every_na_login` (patch `_request` not `get`)
- `tests/reliability_test.py` - Added `REGION_CONFIGS` import; wrapped both discovery tests in `patch.dict` to inject fake candidates

## Decisions Made

- **task_2 deviation from plan spec**: The plan suggested patching `get` for the vehicle list URL in `test_login_calls_discovery_on_every_na_login`. However, the NA `doLogin` path calls `self._request()` for the garage endpoint (`/account/v1/garage`), not `self.get()` for `/vehicle/v2/vehicles` (that's the EMEA path). Patched `_request` instead. This is the correct fix — the plan's suggested approach would not have worked.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] NA doLogin test patched wrong method**
- **Found during:** Task 2 (region_support_test.py)
- **Issue:** Plan suggested patching `get` for the vehicle list URL. NA `doLogin` uses `_request()` for `/account/v1/garage`, not `get()` for `/vehicle/v2/vehicles` (EMEA path). Patching `get` meant the real session was called, resulting in a live 401 response.
- **Fix:** Patched `_request` instead of `get`; mock returns `{"data": {"vehicles": []}}` which matches the NA garage response structure
- **Files modified:** tests/region_support_test.py
- **Verification:** `test_login_calls_discovery_on_every_na_login` PASSED
- **Committed in:** `820eca0` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug: wrong method patched)
**Impact on plan:** Auto-fix essential for correctness. No scope creep — test-only change.

## Issues Encountered

None beyond the one auto-fixed deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Unit test suite at 0 failures — CI trustworthy for Phase 9 advance
- All NA behavior (empty candidates, IDK-only auth, garage endpoint) verified in tests
- No blockers for Phase 9 (requirements validation)

---
*Phase: 08-fix-stale-unit-tests*
*Completed: 2026-02-26*
