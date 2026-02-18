---
phase: 03-three-token-architecture
plan: "01"
subsystem: auth
tags: [oauth, na, mbb, token-registry, xclientId]

# Dependency graph
requires:
  - phase: 02-na-oauth-login-flow
    provides: _login_na() IDK token flow, NA region config with mbb_oauth_base_url

provides:
  - MBB_BRAND_CONFIG constant in vw_const.py ("myvw")
  - Connection._na_tokens dict initialized on all instances
  - Connection._xclient_id with caller-injection support
  - Connection._xclient_id_callback for persistence hook
  - Connection._na_auth_level state tracker
  - Connection._register_mbb_client() async method
  - Connection.na_auth_level property

affects: [03-02-brand-token-exchange, 03-03-mbb-token-exchange, 04-token-refresh]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "NA token registry: _na_tokens dict with keys 'idk', 'brand', 'mbb'"
    - "xclientId persistence: caller-injected via xclient_id param, new registrations trigger on_xclient_id callback"
    - "na_auth_level: 'full' | 'idk_only' | None to track token completeness"

key-files:
  created: []
  modified:
    - volkswagencarnet/vw_const.py
    - volkswagencarnet/vw_connection.py

key-decisions:
  - "_register_mbb_client() returns xclientId string but does NOT assign self._xclient_id -- caller (_login_na) owns assignment to allow conditional callback invocation"
  - "on_xclient_id callback fires only for NEW registrations, not when xclient_id is caller-injected -- prevents unnecessary persistence writes"
  - "MBB_BRAND_CONFIG imported in vw_connection.py for use in Phase 3 Brand/MBB token exchange methods"

patterns-established:
  - "Token level tracking: _na_auth_level set by _login_na after determining which tokens were obtained"
  - "Caller injection pattern: xclient_id param allows HA integration to persist and re-inject xclientId across sessions"

requirements-completed: [AUTH-03, TOKEN-04, COMPAT-04]

# Metrics
duration: 5min
completed: 2026-02-18
---

# Phase 3 Plan 01: Three-Token Architecture Infrastructure Summary

**NA token registry dict, xclientId caller-injection/callback pattern, MBB client registration async method, and na_auth_level property added to Connection without touching EMEA login flow**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-18T19:47:48Z
- **Completed:** 2026-02-18T19:49:34Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- MBB_BRAND_CONFIG = "myvw" constant added to vw_const.py and importable
- Connection.__init__ extended with xclient_id, on_xclient_id params and four new instance attributes (_na_tokens, _xclient_id, _xclient_id_callback, _na_auth_level)
- _register_mbb_client() async method that POSTs to mbb_oauth_base_url/mobile/register/v1 and returns xclientId string
- na_auth_level property exposing _na_auth_level for external callers
- All 53 existing tests pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add MBB_BRAND_CONFIG to vw_const.py** - `d6288a0` (feat)
2. **Task 2: Extend Connection.__init__ with NA token registry and add _register_mbb_client() and na_auth_level** - `6d4c2b7` (feat)

## Files Created/Modified
- `volkswagencarnet/vw_const.py` - Added MBB_BRAND_CONFIG = "myvw" after ANDROID_PACKAGE_NAME
- `volkswagencarnet/vw_connection.py` - Added MBB_BRAND_CONFIG import, xclient_id/on_xclient_id params, four _na_* attributes, _register_mbb_client() method, na_auth_level property

## Decisions Made
- `_register_mbb_client()` returns the xclientId string but does NOT assign `self._xclient_id`. The caller (`_login_na`) handles assignment to allow conditional invocation of the `on_xclient_id` callback (only fires for new registrations, not caller-injected values). This prevents unnecessary persistence writes in the HA integration.
- `MBB_BRAND_CONFIG` imported in vw_connection.py now (even though Phase 3 Plan 01 doesn't use it directly) to make it available for Brand/MBB token exchange methods being added in subsequent plans.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Infrastructure ready for Phase 3 Plan 02 (Brand token exchange)
- _register_mbb_client() stub is fully implemented and can be called from _login_na() in Plan 02
- na_auth_level will be set to "full" or "idk_only" in Plan 02/03 once token exchange results are known
- EMEA connections unaffected: _na_tokens={}, _xclient_id=None, na_auth_level=None

---
*Phase: 03-three-token-architecture*
*Completed: 2026-02-18*
