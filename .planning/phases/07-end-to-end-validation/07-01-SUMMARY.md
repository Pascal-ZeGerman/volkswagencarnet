---
phase: 07-end-to-end-validation
plan: "01"
subsystem: testing
tags: [e2e, pytest, aiohttp, jwt, cryptography, vw-connect, north-america]

# Dependency graph
requires:
  - phase: 06-backward-compatibility
    provides: Full EMEA regression suite and NA vehicle property compat tests
provides:
  - "tests/e2e/ package with credential guard that fails loudly at import time"
  - "na_connection module-scoped async fixture with full-auth enforcement (na_auth_level == 'full')"
  - "norecursedirs exclusion preventing accidental e2e test collection in normal pytest runs"
  - "cryptography package for PyJWT RS256 JWT verification backend"
  - "gitignore pattern for e2e log files"
affects: [07-02-na-live-vehicle-data]

# Tech tracking
tech-stack:
  added: [cryptography]
  patterns:
    - "EnvironmentError guard at module import time (not pytest.skip) for missing credentials"
    - "Module-scoped async fixture with hard AssertionError for partial-auth scenarios"
    - "norecursedirs in pyproject.toml to exclude opt-in test directories from default collection"

key-files:
  created:
    - tests/e2e/__init__.py
    - tests/e2e/conftest.py
  modified:
    - pyproject.toml
    - requirements-test.txt
    - .gitignore

key-decisions:
  - "EnvironmentError at import (not pytest.skip) for missing credentials — ensures loud, immediate failure naming both required env vars"
  - "na_auth_level == 'full' check uses AssertionError (not pytest.skip) — tests requiring Brand/MBB tokens must never silently receive partial auth"
  - "module-scoped fixture with loop_scope='module' required by pytest-asyncio strict mode for single login per test file"
  - "_truncate_token helper exported from conftest for safe token value logging without leaking full secrets"
  - "tests/e2e/*.log gitignored (not committed) — log files contain truncated tokens, kept local only"

patterns-established:
  - "E2E fixture pattern: CookieJar-backed ClientSession + Connection(country='US') + full-auth assertion"
  - "Credential guard: os.environ.get() + EnvironmentError at module scope (not inside fixture)"
  - "Logging setup: session-scoped autouse fixture installs DEBUG FileHandler at tests/e2e/e2e_run.log"

requirements-completed: [TEST-05]

# Metrics
duration: 5min
completed: 2026-02-20
---

# Phase 7 Plan 01: E2E Infrastructure Setup Summary

**opt-in e2e test infrastructure with credential guard, na_connection module-scoped fixture enforcing full 3-token auth, and cryptography backend for RS256 JWT verification**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-02-20T02:37:00Z
- **Completed:** 2026-02-20T02:42:34Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- E2e tests excluded from normal `pytest` runs via `norecursedirs = ["tests/e2e"]` in pyproject.toml
- `tests/e2e/conftest.py` credential guard fires EnvironmentError at import time naming both `VW_TEST_USERNAME` and `VW_TEST_PASSWORD`
- `na_connection` module-scoped async fixture calls `Connection(country="US").doLogin()` then raises AssertionError (not skips) if `na_auth_level != "full"`
- `cryptography` package installed — PyJWT RS256 backend operational (`from jwt.algorithms import RSAAlgorithm` works)
- EMEA test suite: 123 passed, 2 skipped, 0 failures (TEST-05 satisfied, zero regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Config changes — norecursedirs, cryptography, gitignore** - `e6c253e` (chore)
2. **Task 2: tests/e2e/ package and conftest.py with credential guard and login fixture** - `4dc0de1` (feat)
3. **Task 3: Install cryptography and verify EMEA suite passes** - no commit needed (pip install + test run only, no file changes)

**Plan metadata:** (docs commit — pending)

## Files Created/Modified
- `pyproject.toml` - Added `norecursedirs = ["tests/e2e"]` to pytest ini_options
- `requirements-test.txt` - Added `cryptography` for PyJWT RS256 backend
- `.gitignore` - Added `tests/e2e/*.log` pattern to exclude live test logs
- `tests/e2e/__init__.py` - Empty package marker
- `tests/e2e/conftest.py` - EnvironmentError guard + _setup_logging fixture + na_connection fixture with full-auth enforcement

## Decisions Made
- EnvironmentError at import (not pytest.skip) for missing credentials — immediate, loud failure naming both required env vars
- na_auth_level == 'full' check uses AssertionError (not pytest.skip) — ensures tests requiring Brand/MBB tokens always receive fully-authenticated connection or never run
- module-scoped fixture with `loop_scope="module"` required by pytest-asyncio strict mode — single real login per test module
- `_truncate_token` helper exported from conftest for safe truncated logging of token prefixes without committing full token values

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required for this infrastructure plan. Live credentials are only needed when running `pytest tests/e2e/ -v`.

## Next Phase Readiness
- E2e infrastructure is complete — Phase 7 Plan 02 (NA live vehicle data tests) can use the `na_connection` fixture directly
- The `na_connection` fixture enforces `na_auth_level == "full"` — Plan 02 tests are guaranteed to receive all three tokens (IDK, Brand, MBB) or fail loudly at fixture setup time
- `cryptography` backend installed — RS256 JWT verification available for token inspection tests

---
*Phase: 07-end-to-end-validation*
*Completed: 2026-02-20*
