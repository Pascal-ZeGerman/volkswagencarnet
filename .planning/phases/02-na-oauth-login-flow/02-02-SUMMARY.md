---
phase: 02-na-oauth-login-flow
plan: "02"
subsystem: testing
tags: [na, oauth, unit-tests, pytest, asyncio, mocking, IsolatedAsyncioTestCase]

# Dependency graph
requires:
  - phase: 02-na-oauth-login-flow/02-01
    provides: _login_na() dispatch chain, get_openid_config(), _get_authorization_code(), _exchange_code_for_tokens() in vw_connection.py
provides:
  - NAOAuthLoginTest class with 6 test methods covering NA OAuth login paths
  - Regression protection for _login() dispatch to _login_na() for NA region
  - EMEA routing guard test verifying _login_na is never called for EMEA connections
affects: [03-na-vehicle-data, 04-na-token-refresh]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "patch.object(conn, method_name) to mock Connection instance methods without module-level patching"
    - "IsolatedAsyncioTestCase for async test classes with AsyncMock session"
    - "Test failure-path methods against _login_na() directly; success-path via _login() to validate dispatch"

key-files:
  created: []
  modified:
    - tests/vw_connection_test.py

key-decisions:
  - "Failure-path tests call conn._login_na() directly; only test_na_login_success calls conn._login() to validate dispatch chain"
  - "Mock at Connection instance level with patch.object(conn, ...) not at module level"
  - "test_emea_login_not_routed_to_na asserts _login_na not called by patching it and checking assert_not_called()"

patterns-established:
  - "Use parenthesized with-block (Python 3.10+) for multiple context managers in single async test"
  - "AsyncMock for session; MagicMock for _cookie_jar; dict for _cookie_jar._cookies"

requirements-completed: [AUTH-02, INT-02, INT-03, COMPAT-03]

# Metrics
duration: 6min
completed: 2026-02-18
---

# Phase 2 Plan 02: NA OAuth Login Tests Summary

**NAOAuthLoginTest class with 6 tests validating the full NA OAuth dispatch chain including success, bad credentials, token exchange failure, redirect failure, network error, and EMEA routing guard**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-18T15:41:20Z
- **Completed:** 2026-02-18T15:47:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Added NAOAuthLoginTest class with 6 test methods to tests/vw_connection_test.py
- test_na_login_success validates the actual _login() dispatch chain (not just _login_na() directly)
- test_emea_login_not_routed_to_na confirms _login_na is never called for EMEA region connections
- Total passing tests increased from 47 to 53 (6 new NA tests + 47 existing)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add NAOAuthLoginTest class to tests/vw_connection_test.py** - `ebc3774` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `tests/vw_connection_test.py` - Added AsyncMock/AuthenticationError/RedirectError imports; added NAOAuthLoginTest class with 6 test methods

## Decisions Made
- Failure-path tests call `conn._login_na()` directly to test specific error handling inside that method
- Success-path test calls `conn._login()` to validate the dispatch chain from _login() -> _login_na() for NA region
- Used Python 3.10+ parenthesized `with` block for multiple context managers in single async test

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- NA OAuth login flow fully tested and protected against regressions
- Phase 3 can safely add Brand/MBB token acquisition alongside the IDK token tested here
- The EMEA routing guard test ensures Phase 3 changes to _login_na() won't accidentally affect EMEA users

## Self-Check: PASSED

- FOUND: tests/vw_connection_test.py
- FOUND: .planning/phases/02-na-oauth-login-flow/02-02-SUMMARY.md
- FOUND commit: ebc3774 (feat(02-02): add NAOAuthLoginTest class with 6 NA OAuth login tests)
- NAOAuthLoginTest class present at line 101
- 5 test methods prefixed `test_na` (verified with grep -c)
- test_emea_login_not_routed_to_na present at line 219
- await conn._login() used in test_na_login_success (dispatch chain validated)
- 53 tests pass total (47 baseline + 6 new NA tests)

---
*Phase: 02-na-oauth-login-flow*
*Completed: 2026-02-18*
