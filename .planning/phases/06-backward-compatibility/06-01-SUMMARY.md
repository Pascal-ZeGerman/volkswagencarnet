---
phase: 06-backward-compatibility
plan: "01"
subsystem: testing
tags: [pytest, inspect, asyncio, emea, regression, contract-testing, patch-object]

# Dependency graph
requires:
  - phase: 05-reliability-discovery
    provides: Retry/backoff infrastructure, home region discovery — regression tests guard against breakage
  - phase: 02-na-oauth-login-flow
    provides: _login_na() dispatch at vw_connection.py line 1140 — the exact insertion point these tests guard
provides:
  - EMEA three-step login sequence regression tests (call_count==1 per step)
  - Public Connection API surface contract locked via inspect.signature()
  - Multi-country routing verification (FR, GB, XX, DE never touch _login_na)
  - NA token isolation proof (_na_tokens empty, _na_auth_level=None after EMEA login)
affects:
  - 06-backward-compatibility (plan 02+ will build on this test file)
  - Any future refactor of Connection.__init__, doLogin(), update(), or vehicles

# Tech tracking
tech-stack:
  added: []
  patterns:
    - inspect.signature() for freezing public API surface without integration tests
    - patch.object(conn, method) at instance level for regression guards
    - pytest.mark.asyncio with connection/session fixtures from conftest.py
    - IsolatedAsyncioTestCase for synchronous contract tests alongside async pytest functions
    - call_count==1 assertion pattern for verifying exactly-once execution of sequential steps

key-files:
  created:
    - tests/emea_regression_test.py
  modified: []

key-decisions:
  - "ConnectionAPIContractTest uses IsolatedAsyncioTestCase (not pytest class) since all 6 methods are synchronous def tests"
  - "EMEA regression tests use module-level @pytest.mark.asyncio async functions with fixture injection — no inline mock factories"
  - "test_non_na_countries_stay_in_emea_path constructs Connection(session, '', '', country=X) inline per-country — real aiohttp session from fixture"
  - "_na_auth_level default confirmed as Python None (not string 'none') — assertion uses 'is None'"

patterns-established:
  - "Contract test pattern: inspect.signature() locks constructor args + method kinds without touching implementation"
  - "Regression test pattern: patch.object + call_count==1 verifies sequential step execution at exact dispatch line"
  - "Isolation proof pattern: assert _na_tokens == {} and _na_auth_level is None after EMEA login"

requirements-completed: [COMPAT-01, COMPAT-02]

# Metrics
duration: 2min
completed: 2026-02-19
---

# Phase 6 Plan 01: EMEA Backward Compatibility Summary

**11-test regression suite locking EMEA auth call sequence (call_count==1 per step) and Connection public API surface via inspect.signature()**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-19T18:17:46Z
- **Completed:** 2026-02-19T18:19:46Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Created `ConnectionAPIContractTest` (6 tests) locking the public API surface: constructor positional args, country default 'DE', doLogin/update async coroutines, vehicles property
- Created 5 module-level `@pytest.mark.asyncio` EMEA regression tests: three-step sequence (get_openid_config -> _get_authorization_code -> _exchange_code_for_tokens) with call_count==1 each, token storage under 'identity' key, multi-country routing (FR/GB/XX/DE never dispatch to _login_na), error handling, and NA token isolation
- Full suite: 120 passed, 2 skipped (integration tests), zero regressions
- `tests/emea_regression_test.py`: 178 lines, 11 test functions

## Task Commits

Each task was committed atomically:

1. **Task 1: ConnectionAPIContractTest — frozen public API surface assertions** - `bfa82f8` (test)
2. **Task 2: EMEA login regression tests — call sequence and multi-country routing** - `460d3cd` (test)

**Plan metadata:** (docs commit follows)

_Note: TDD plan — all tests assert on existing code so RED/GREEN cycle not applicable; tests pass immediately_

## Files Created/Modified

- `tests/emea_regression_test.py` - EMEA regression tests and public API surface contract tests (178 lines, 11 tests)

## Decisions Made

- `ConnectionAPIContractTest` uses `IsolatedAsyncioTestCase` (same as vw_connection_test.py) since its 6 methods are synchronous `def` tests — no async machinery needed
- EMEA regression tests use module-level `@pytest.mark.asyncio` async functions with `connection` and `session` fixtures (auto-registered via conftest.py) — no inline mock factories
- `test_non_na_countries_stay_in_emea_path` constructs `Connection(session, '', '', country=X)` inline per-country using the real aiohttp session fixture
- `_na_auth_level` default confirmed as Python `None` (not string `"none"`) per vw_connection.py line 122: `self._na_auth_level: str | None = None` — assertion uses `is None`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- COMPAT-01 (EMEA auth flow unchanged) verified — three-step sequence with call_count==1 each
- COMPAT-02 (public API surface frozen) verified — inspect.signature() locks constructor, doLogin, update, vehicles
- Ready for Phase 6 Plan 02 (additional backward compatibility requirements if any)

## Self-Check: PASSED

- tests/emea_regression_test.py: FOUND
- .planning/phases/06-backward-compatibility/06-01-SUMMARY.md: FOUND
- Commit bfa82f8: FOUND (ConnectionAPIContractTest)
- Commit 460d3cd: FOUND (EMEA login regression tests)

---
*Phase: 06-backward-compatibility*
*Completed: 2026-02-19*
