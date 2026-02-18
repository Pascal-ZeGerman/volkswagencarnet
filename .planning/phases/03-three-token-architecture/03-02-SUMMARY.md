---
phase: 03-three-token-architecture
plan: "02"
subsystem: auth
tags: [oauth, jwt, mbb, brand-token, idk, na-region, vw-carnet]

# Dependency graph
requires:
  - phase: 03-01
    provides: NA token registry (_na_tokens dict), _register_mbb_client(), _xclient_id/_xclient_id_callback, MBB_BRAND_CONFIG constant
  - phase: 02-na-oauth-login-flow
    provides: _login_na() IDK token acquisition, _exchange_code_for_tokens(), get_openid_config()
provides:
  - _exchange_brand_token(idk_access_token): IDK access_token -> Brand access_token+refresh_token, /volkswagen/token with /vw/token 404 fallback
  - _exchange_mbb_token(idk_id_token, xclient_id): form-encoded initial MBB grant using IDK id_token
  - _refresh_mbb_token(refresh_token, xclient_id): form-encoded MBB refresh grant, Phase 4 reusable
  - _login_na() extended: full IDK->Brand->register->MBB->refresh_MBB chain with IDK-only fallback
  - _na_tokens populated with 'idk', 'brand', 'mbb' entries on full success
  - _na_auth_level: 'full' or 'idk_only' after NA login
affects: [04-token-lifecycle, phase-4]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "NA three-token chain: IDK -> Brand (JSON POST) -> MBB registration -> MBB initial (form) -> MBB refresh (form)"
    - "IDK-only fallback: Brand/MBB failures do not abort login, na_auth_level='idk_only' signals degraded auth"
    - "MBB token body key convention: 'token' not 'refresh_token'/'id_token' (VW non-standard)"
    - "Callback pattern: on_xclient_id fires only for new registrations, not caller-injected xclientId"
    - "_refresh_mbb_token separate method (not inline) to enable Phase 4 independent token refresh"

key-files:
  created: []
  modified:
    - volkswagencarnet/vw_connection.py

key-decisions:
  - "Brand token exchange uses JSON body (not form-encoded) - confirmed from 2026 traffic analysis"
  - "MBB token exchange uses form-encoded body with key 'token' (not 'id_token') - VW non-standard"
  - "_refresh_mbb_token defined as separate method (not inline in login) for Phase 4 reuse without re-login"
  - "MBB working token is the REFRESHED token, not the initial grant - initial grant is immediately refreshed"
  - "Brand/MBB acquisition wrapped in inner try/except inside outer try block - KeyError/ClientError still caught by outer handlers"

patterns-established:
  - "Token chain: outer try handles IDK failures, inner try handles Brand/MBB failures independently"
  - "na_auth_level property signals auth tier to callers without exposing internal token dict"

requirements-completed: [TOKEN-01, TOKEN-02, TOKEN-03, TOKEN-05]

# Metrics
duration: 2min
completed: 2026-02-18
---

# Phase 3 Plan 02: Three-Token Architecture - Brand and MBB Acquisition Summary

**Full NA three-token auth chain (IDK -> Brand JSON exchange -> MBB form grant -> immediate MBB refresh) with IDK-only graceful fallback on Brand/MBB failure**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-18T19:52:22Z
- **Completed:** 2026-02-18T19:54:11Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Added `_exchange_brand_token()`: JSON POST to `/login/v1/volkswagen/token` with automatic 404 fallback to `/login/v1/vw/token`
- Added `_exchange_mbb_token()`: form-encoded POST using IDK id_token (key `"token"`) with `X-Client-ID` header
- Added `_refresh_mbb_token()`: form-encoded MBB refresh grant, standalone method reusable by Phase 4 token lifecycle
- Extended `_login_na()` to orchestrate full chain: IDK -> Brand -> conditional MBB registration -> MBB initial grant -> immediate MBB refresh
- `_na_tokens` populated with `"idk"`, `"brand"`, `"mbb"` entries; `_na_auth_level = "full"` on success, `"idk_only"` on Brand/MBB failure
- IDK tokens mirrored to `_session_tokens["identity"]` preserving `validate_tokens()` compatibility (COMPAT-04)
- All 53 existing tests pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add _exchange_brand_token, _exchange_mbb_token, _refresh_mbb_token** - `1df9acd` (feat)
2. **Task 2: Extend _login_na() with full three-token chain and IDK-only fallback** - `49ae6cd` (feat)

## Files Created/Modified

- `volkswagencarnet/vw_connection.py` - Three new token exchange methods + extended _login_na() orchestration

## Decisions Made

- Brand token exchange uses JSON body (not form-encoded) per 2026 traffic analysis - same endpoint structure as _register_mbb_client but different content type
- MBB token exchanges use form-encoded body with VW non-standard key `"token"` for both id_token and refresh_token values
- `_refresh_mbb_token` defined as separate named method to enable Phase 4 to call it independently during token lifecycle management
- MBB working token is the refreshed token (not initial grant) - this matches observed app behavior where initial grant is immediately rotated
- Brand/MBB acquisition wrapped in inner try/except inside outer try block so outer KeyError/ClientError handlers still protect IDK-level failures

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 3 Plan 03 (test fixtures for three-token chain) can proceed
- `_na_tokens` dict structure is stable: `{"idk": {...}, "brand": {...}, "mbb": {...}}`
- `_na_auth_level` property available for callers to detect auth tier
- `_refresh_mbb_token` ready for Phase 4 token lifecycle management

---
*Phase: 03-three-token-architecture*
*Completed: 2026-02-18*
