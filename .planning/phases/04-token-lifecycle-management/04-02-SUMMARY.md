---
phase: 04-token-lifecycle-management
plan: "02"
subsystem: testing
tags: [oauth, jwt, token-refresh, lifecycle, na-region, pytest, tdd, mocking]

# Dependency graph
requires:
  - phase: 04-token-lifecycle-management
    plan: "01"
    provides: "_classify_endpoint(), _refresh_idk_token(), _refresh_brand_token(), _refresh_mbb_from_refresh_token(), _validate_na_tokens(), validate_tokens() NA branch, _request() 401 inline retry"
provides:
  - "NATokenLifecycleTest class with 18 test methods covering all Phase 4 lifecycle behaviors"
  - "Regression protection for endpoint classification, per-token refresh, IDK->Brand cascade, proactive expiry, 401 retry, and idk_only non-regression"
affects: [05-vehicle-data-na, 06-emea-compat, all phases modifying token lifecycle methods]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Session mirror pre-population: _session_tokens['identity'] must be pre-populated before calling _refresh_idk_token() in tests (mirror update requires existing dict entry)"
    - "MagicMock for session.request: async context manager mocking requires MagicMock(return_value=cm) not AsyncMock - avoids coroutine-as-context-manager error"
    - "AsyncMock for session.post: must pass mock directly to patch.object (not return_value= kwarg) to ensure await compatibility"

key-files:
  created: []
  modified:
    - tests/vw_connection_test.py

key-decisions:
  - "Pre-populate _session_tokens['identity'] in IDK refresh tests — _refresh_idk_token() mirrors new tokens to existing identity entry, causing KeyError if entry missing"
  - "Use MagicMock (not AsyncMock) for session.request replacement — async with requires synchronous callable returning context manager; AsyncMock returns coroutine"
  - "EMEA 401 non-regression test uses call_count==1 assertion — cleaner than hasattr sentinel, directly verifies no retry occurred"

patterns-established:
  - "AsyncMock post pattern: patch.object(conn._session, 'post', AsyncMock(return_value=mock_response)) — explicit AsyncMock needed when session is AsyncMock"
  - "Context manager mock pattern: MagicMock with __aenter__=AsyncMock and __aexit__=AsyncMock for async with session.request() patterns"

requirements-completed: [MGMT-01, MGMT-02, MGMT-03, MGMT-04, MGMT-05, MGMT-06]

# Metrics
duration: 5min
completed: 2026-02-18
---

# Phase 4 Plan 02: Token Lifecycle Management Tests Summary

**NATokenLifecycleTest class with 18 regression tests covering endpoint classification, per-token independent refresh (IDK/Brand/MBB), IDK->Brand cascade, proactive 15-min expiry validation, 401 inline retry, and EMEA non-regression**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-18T21:20:27Z
- **Completed:** 2026-02-18T21:28:29Z
- **Tasks:** 1 (single TDD task)
- **Files modified:** 1

## Accomplishments
- Added `NATokenLifecycleTest` class with 18 test methods to `tests/vw_connection_test.py`
- All 18 new tests pass; all 61 existing tests continue to pass (total: 79 passed)
- Full coverage of all 6 MGMT requirements with at least one test each
- Discovered and resolved 3 test-level setup issues (session mirror, MagicMock vs AsyncMock, context manager mocking)

## Task Commits

Each task was committed atomically:

1. **Task 1: NATokenLifecycleTest class with 18 tests** - `03a84ac` (feat)

## Files Created/Modified
- `tests/vw_connection_test.py` - Added `import time`, added `NATokenLifecycleTest` class (18 tests, 2 helpers)

## Decisions Made
- Pre-populate `_session_tokens["identity"]` in IDK refresh tests — `_refresh_idk_token()` calls `self._session_tokens["identity"].update(...)` which requires the key to exist
- Use `MagicMock(return_value=cm)` directly for `session.request` patching — `async with session.request(...)` requires synchronous callable returning context manager; using `AsyncMock` causes coroutine-as-context-manager `TypeError`
- EMEA non-regression test asserts `mock_session_request.call_count == 1` rather than negative assertion — directly verifies EMEA 401 path uses no retry

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed _session_tokens["identity"] KeyError in IDK refresh tests**
- **Found during:** TDD GREEN phase (tests 6 and 8 failing with `KeyError: 'identity'`)
- **Issue:** `_refresh_idk_token()` mirrors new IDK token into `self._session_tokens["identity"]` via `.update()`, but test fixtures didn't initialize `_session_tokens["identity"]`; `.update()` on missing key raises KeyError
- **Fix:** Added `conn._session_tokens["identity"] = {"access_token": "old_at"}` to tests 6 and 8 before calling `_refresh_idk_token()`
- **Files modified:** `tests/vw_connection_test.py`
- **Committed in:** `03a84ac` (Task 1 commit)

**2. [Rule 1 - Bug] Fixed AsyncMock vs MagicMock for session.post patching**
- **Found during:** TDD GREEN phase (tests 6 and 7 failing with AuthenticationError from retry exhaustion)
- **Issue:** `patch.object(conn._session, "post", return_value=mock_response)` creates a MagicMock with return_value, but since `conn._session` is `AsyncMock`, `conn._session.post` is `AsyncMock`; patching with `return_value=` kwarg creates a synchronous mock that doesn't work with `await session.post(...)`
- **Fix:** Changed to `patch.object(conn._session, "post", AsyncMock(return_value=mock_response))` — passing the mock object directly ensures it is awaitable
- **Files modified:** `tests/vw_connection_test.py`
- **Committed in:** `03a84ac` (Task 1 commit)

**3. [Rule 1 - Bug] Fixed EMEA session.request context manager TypeError**
- **Found during:** TDD GREEN phase (test 18 failing with `TypeError: 'coroutine' object does not support the asynchronous context manager protocol`)
- **Issue:** `patch.object(conn._session, "request", return_value=cm_401)` on an `AsyncMock` session created an `AsyncMock` that returned a coroutine when called; `async with session.request(...)` requires a synchronous callable returning a context manager, not a coroutine
- **Fix:** Changed to `mock_session_request = MagicMock(return_value=cm_401)` + `patch.object(conn._session, "request", mock_session_request)` — `MagicMock` returns `cm_401` directly (not as coroutine)
- **Files modified:** `tests/vw_connection_test.py`
- **Committed in:** `03a84ac` (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (3 Rule 1 bugs — all test-level setup issues)
**Impact on plan:** All fixes were necessary for test correctness. No scope creep. Implementation code (Plan 01) required zero changes.

## Issues Encountered

None — the implementation from Plan 01 was correct. All 3 issues were test setup problems related to Python mock library behavior differences between `MagicMock` and `AsyncMock` when patching attributes of `AsyncMock` instances.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All 6 MGMT requirements have regression tests; Phase 4 is fully complete
- `NATokenLifecycleTest` provides safety net for Phase 5 vehicle data retrieval changes
- The mock patterns established (MagicMock for session.request, AsyncMock for session.post, pre-populating _session_tokens) are documented for future test phases

---
*Phase: 04-token-lifecycle-management*
*Completed: 2026-02-18*
