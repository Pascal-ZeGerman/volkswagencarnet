---
phase: 02-na-oauth-login-flow
plan: "01"
subsystem: auth
tags: [oauth, na, identity, x-qmauth, redirect, pkce]

# Dependency graph
requires:
  - phase: 01-na-foundation
    provides: _calculate_xqmauth() method, X-QMAuth constants, NA region config with redirect_uri
provides:
  - follow_redirects() with region-aware stop condition (stop_uri from region config)
  - _login_na() private method for NA OAuth flow via identity.na.vwgroup.io
  - X-QMAuth header injection in _exchange_code_for_tokens() for NA
  - _login() dispatches to _login_na() before try block when region == "NA"
affects:
  - 02-02 (NA login test suite -- tests these methods)
  - 02-na-oauth-login-flow (phase 2 plans depend on this wiring)
  - 03-na-brand-token (Phase 3 adds brand/mbb tokens alongside identity token)
  - 04-na-token-refresh (Phase 4 refresh flow needs X-QMAuth in same place)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Region-aware configuration: self._session_region_config.get(key, fallback) for all region-specific values"
    - "NA login delegation: _login() dispatches BEFORE try block to _login_na() to avoid shadowing NA exception handling"
    - "X-QMAuth injection point: inside _exchange_code_for_tokens() keyed on self._session_region == 'NA'"

key-files:
  created: []
  modified:
    - volkswagencarnet/vw_connection.py

key-decisions:
  - "NA dispatch placed BEFORE the try block in _login() so _login_na() exception handlers are not shadowed"
  - "X-QMAuth header is NOT removed after post_form -- retained for Phase 4 token refresh reuse"
  - "No live IDK-only probe HTTP call in _login_na() -- hypothesis validated in Phase 3 via test fixtures"
  - "PKCE explicitly set to None in _login_na() (use_pkce: False per 2026 traffic analysis)"

patterns-established:
  - "stop_uri pattern: always derive redirect stop condition from region config, not hardcoded constants"

requirements-completed: [AUTH-02, INT-02, INT-03, COMPAT-03]

# Metrics
duration: 8min
completed: 2026-02-18
---

# Phase 2 Plan 01: NA OAuth Login Branching Summary

**NA OAuth branching wired into Connection class: region-aware redirect stop condition, X-QMAuth injection in token exchange, and _login_na() delegation method routed from _login() before try block**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-18T15:36:31Z
- **Completed:** 2026-02-18T15:38:00Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- `follow_redirects()` now uses `stop_uri = self._session_region_config.get("redirect_uri", APP_URI)` so NA stops at HTTPS callback URI while EMEA continues to stop at `weconnect://authenticated`
- `_login_na()` implements the full NA OAuth authorization code flow via `identity.na.vwgroup.io` without PKCE, storing IDK token in `self._session_tokens["identity"]`
- `_exchange_code_for_tokens()` injects `X-QMAuth` header when `self._session_region == "NA"`, satisfying the identity.na.vwgroup.io requirement
- `_login()` dispatches to `_login_na()` BEFORE the try block so NA exception handling is not shadowed by EMEA handlers
- All 47 existing tests pass (EMEA regression gate verified)

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix follow_redirects() stop condition for NA HTTPS callback URI** - `2e15181` (fix)
2. **Task 2: Inject X-QMAuth and add _login_na() method** - `3ecf717` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `volkswagencarnet/vw_connection.py` - Added region-aware stop_uri in follow_redirects(), added _login_na() private method, added X-QMAuth injection in _exchange_code_for_tokens(), added NA dispatch before try block in _login()

## Decisions Made

- NA dispatch is placed BEFORE the `try` block in `_login()` so that `_login_na()`'s own exception handlers are not shadowed by `_login()`'s EMEA handlers. This preserves the complete EMEA try/except structure untouched.
- `X-QMAuth` header is NOT removed after `post_form()` -- it will be reused for token refresh in Phase 4. Auth headers are reset at the start of each `_login()` call anyway.
- No live HTTP probe inside `_login_na()` for the IDK-only BFF access hypothesis -- this is validated in Phase 3 via test fixture scenarios, not production code.
- PKCE is explicitly set to `None` in `_login_na()` because 2026 traffic analysis confirmed the VW Car-Net app does NOT send `code_challenge` despite server support.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- NA OAuth branching is wired and ready for test coverage in Phase 2 Plan 02
- `_login_na()` method is in place for Phase 3 to extend with brand/mbb token acquisition alongside the IDK token
- X-QMAuth injection point is established for Phase 4 token refresh to use the same approach

## Self-Check: PASSED

- `volkswagencarnet/vw_connection.py` - FOUND
- `.planning/phases/02-na-oauth-login-flow/02-01-SUMMARY.md` - FOUND
- Commit `2e15181` - FOUND
- Commit `3ecf717` - FOUND

---
*Phase: 02-na-oauth-login-flow*
*Completed: 2026-02-18*
