---
phase: 05-reliability-discovery
plan: "03"
subsystem: testing
tags: [pytest, unit-test, reliability, discovery, rate-limiting, home-region, allowlist, na, retry]

# Dependency graph
requires:
  - phase: 05-01-reliability-discovery
    provides: VW_DOMAIN_ALLOWLIST, _is_allowed_vw_domain(), _discover_market_config(), is_throttled, centralized retry in _request()
  - phase: 05-02-reliability-discovery
    provides: _ensure_home_region(), home_region_url property, _home_region_discovered guard flag
provides:
  - tests/reliability_test.py with MarketConfigDiscoveryTest (8 tests), HomeRegionDiscoveryTest (6 tests), RetryBackoffTest (8 tests)
  - Regression coverage for INT-01, INT-04, INT-05
affects: [future-phases, ci, regression-protection]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "IsolatedAsyncioTestCase for all async test classes — consistent with Phase 4 pattern"
    - "_make_resp_ctx() factory: MagicMock ctx with AsyncMock __aenter__/__aexit__ for async context manager mocking"
    - "_make_request_mock() factory: stateful call_count + ordered status list for multi-call retry simulation"
    - "MagicMock(return_value=ctx) for session.get/request — avoids coroutine-as-context-manager TypeError"
    - "raises_disconnect as plain function (not async) — session.request called synchronously, raises before context manager"
    - "patch('asyncio.sleep') to suppress waits in retry tests; call_args_list inspects actual delay values"

key-files:
  created:
    - tests/reliability_test.py
  modified: []

key-decisions:
  - "All three test classes in a single file (reliability_test.py) to reflect the unified Phase 5 scope"
  - "8 tests per class average: covers happy path, cache guard, EMEA skip, failure fallback, security (allowlist), and property access"
  - "raises_disconnect as sync function — aiohttp session.request() is called synchronously and returns ctx; exception before ctx works for connection-level errors"
  - "assertLogs context manager used for log message verification — avoids brittle mock assertions on logger calls"

patterns-established:
  - "_make_request_mock() helper: call_count list and ordered status list supports any retry sequence test"
  - "subTest() for URL validation tests: one assertion block covers multiple URLs with clear failure identification"

requirements-completed: [INT-01, INT-04, INT-05]

# Metrics
duration: 2min
completed: 2026-02-19
---

# Phase 05 Plan 03: Reliability Discovery Tests Summary

**22-test regression suite (MarketConfigDiscoveryTest, HomeRegionDiscoveryTest, RetryBackoffTest) covering VW domain allowlist validation, lazy NA home region discovery, and centralized exponential-backoff retry**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-19T00:46:27Z
- **Completed:** 2026-02-19T00:49:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Created `tests/reliability_test.py` with 3 test classes and 22 tests total, all passing
- `MarketConfigDiscoveryTest` (8 tests): covers success path, malicious URL rejection, session cache guard, failure fallback, EMEA skip, `VW_DOMAIN_ALLOWLIST` contents, `_is_allowed_vw_domain()` acceptance, and `_is_allowed_vw_domain()` rejection
- `HomeRegionDiscoveryTest` (6 tests): covers first-candidate selection, concurrent re-entry guard, EMEA skip, all-candidates-fail fallback retention, bad-domain candidate skipping, and `home_region_url` property
- `RetryBackoffTest` (8 tests): covers 429 retry count, Retry-After header value, exponential backoff delays (1s/2s/4s), `is_throttled` True after exhaustion, `is_throttled` reset on success, `ServerDisconnectedError` retry, `_no_retry` flag, and `get()` Throttled return
- All 80 pre-existing tests continue to pass (total: 102 passed, 2 skipped)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create tests/reliability_test.py with MarketConfigDiscoveryTest, HomeRegionDiscoveryTest, RetryBackoffTest** - `021de6a` (test)

**Plan metadata:** _(to be committed with SUMMARY.md)_

## Files Created/Modified

- `tests/reliability_test.py` - 22 tests across 3 classes; helper factories _make_na_conn(), _make_emea_conn(), _make_na_vehicle(), _make_resp_ctx(); covers INT-01, INT-04, INT-05

## Decisions Made

- All three test classes in a single file matching the unified Phase 5 scope — avoids test file proliferation for tightly related capabilities
- `raises_disconnect` defined as a plain (non-async) function: `session.request()` is called synchronously and raises before returning a context manager, which is the correct behavior for connection-level errors
- `assertLogs()` context manager used to verify WARNING messages — more robust than patching the logger or inspecting mock call args
- `_make_request_mock()` factory returns both the callable and a `call_count` list — allows exact retry count assertion without patching

## Deviations from Plan

None - plan executed exactly as written. All 22 tests passed on the first run without modification.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 5 complete: all three INT requirements (INT-01, INT-04, INT-05) have regression test coverage
- Phase 6 (EMEA compatibility) can proceed: `VW_DOMAIN_ALLOWLIST`, `_is_allowed_vw_domain()`, `_discover_market_config()`, `_ensure_home_region()`, and `is_throttled` are all tested and stable
- 102 tests provide a solid regression baseline for future changes

---
*Phase: 05-reliability-discovery*
*Completed: 2026-02-19*

## Self-Check: PASSED
