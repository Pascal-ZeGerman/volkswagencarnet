---
phase: 03-three-token-architecture
plan: "03"
subsystem: testing
tags: [pytest, asyncio, mocking, three-token, na-auth, idk, brand, mbb, xclientid]

# Dependency graph
requires:
  - phase: 03-three-token-architecture/03-01
    provides: _register_mbb_client(), xclientId injection, on_xclient_id callback mechanism
  - phase: 03-three-token-architecture/03-02
    provides: _exchange_brand_token(), _exchange_mbb_token(), _refresh_mbb_token(), full _login_na() chain

provides:
  - NAThreeTokenTest class with 8 tests covering full three-token chain regression protection
  - Test coverage for brand failure IDK-only fallback
  - Test coverage for MBB registration/exchange failure fallbacks
  - Test coverage for MBB refresh timing (immediately after initial grant)
  - Test coverage for xclientId injection behavior
  - Test coverage for on_xclient_id callback (fires vs suppressed)
affects:
  - 04-token-refresh (regression anchor for three-token chain changes)
  - any future NA auth changes in vw_connection.py

# Tech tracking
tech-stack:
  added: []
  patterns:
    - IsolatedAsyncioTestCase with _make_na_conn(**kwargs) helper for flexible connection creation
    - _idk_fixtures() helper for shared fixture data reuse across test methods
    - patch.object(conn, method_name) for instance-level mocking (not module-level)
    - Parenthesized with blocks for multiple context managers
    - AsyncMock stored as variable then passed to patch.object for call inspection

key-files:
  created: []
  modified:
    - tests/vw_connection_test.py

key-decisions:
  - "NAThreeTokenTest._make_na_conn(**kwargs) accepts keyword args to support xclient_id and on_xclient_id injection per test"
  - "_idk_fixtures() helper centralizes IDK fixture data to avoid repetition across 8 tests"
  - "mock_refresh stored as AsyncMock variable (not inline) to enable call_count and call_args assertions"

patterns-established:
  - "Pattern: _make_na_conn(**kwargs) helper pattern supports optional constructor params without per-test boilerplate"
  - "Pattern: shared _idk_fixtures() helper avoids OpenID config duplication across all 8 tests"
  - "Pattern: Store mock as variable before patch.object when you need to inspect call_count or call_args"

requirements-completed: [TOKEN-01, TOKEN-02, TOKEN-03, AUTH-03, TOKEN-04, TOKEN-05, COMPAT-04]

# Metrics
duration: 1min
completed: 2026-02-18
---

# Phase 3 Plan 03: Three-Token Architecture Tests Summary

**NAThreeTokenTest class with 8 tests providing full regression coverage for IDK/Brand/MBB chain, fallback paths, xclientId injection, and on_xclient_id callback behavior**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-18T19:57:02Z
- **Completed:** 2026-02-18T19:58:10Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Added NAThreeTokenTest class (8 tests) to tests/vw_connection_test.py
- Total test count increased from 53 to 61 (8 new, zero regressions)
- Full three-token chain covered: success path, all three fallback paths, refresh timing, xclientId injection, callback fired/suppressed

## Task Commits

Each task was committed atomically:

1. **Task 1: Add NAThreeTokenTest class with 8 tests** - `6da1ebf` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `tests/vw_connection_test.py` - Added NAThreeTokenTest class with 8 test methods at end of file

## Decisions Made
- `_make_na_conn(**kwargs)` accepts keyword args to support per-test constructor injection (xclient_id, on_xclient_id) without creating separate helper variants
- `_idk_fixtures()` helper centralizes the OpenID config + idk_tokens dicts shared across all 8 tests to avoid repetition
- For `test_na_mbb_refresh_called_immediately_after_initial_grant`, stored mock as `mock_refresh = AsyncMock(return_value=...)` variable before `patch.object(conn, "_refresh_mbb_token", mock_refresh)` to enable `call_args` inspection after the call

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 3 complete: all three plans done
- Three-token architecture fully implemented and tested
- NAOAuthLoginTest (6 tests) + NAThreeTokenTest (8 tests) = 14 NA-specific tests
- Ready for Phase 4: Token Refresh (independent MBB/IDK refresh using the methods built in Phase 3)

## Self-Check: PASSED

- tests/vw_connection_test.py: FOUND
- 03-03-SUMMARY.md: FOUND
- commit 6da1ebf: FOUND

---
*Phase: 03-three-token-architecture*
*Completed: 2026-02-18*
