---
phase: 05-reliability-discovery
plan: "01"
subsystem: auth
tags: [oauth, retry, rate-limiting, discovery, allowlist, security]

# Dependency graph
requires:
  - phase: 04-token-lifecycle-management
    provides: _classify_endpoint, _refresh_idk_token, _refresh_brand_token, _refresh_mbb_from_refresh_token, inline 401 retry in _request()
provides:
  - VW_DOMAIN_ALLOWLIST: 8-entry tuple of known VW Group domain suffixes
  - _is_allowed_vw_domain(): URL hostname validation against allowlist
  - _discover_market_config(): full OIDC discovery with URL validation, caching, non-blocking failure
  - _discover_endpoints(): backward-compatible alias for _discover_market_config()
  - discovery_config: cached validated OIDC discovery dict on Connection instance
  - is_throttled property: observable rate-limit state on Connection instance
  - centralized retry in _request(): exponential backoff for 429 and transient network errors
affects: [05-02-PLAN.md, 05-03-PLAN.md, any code relying on get/post/put retry behavior]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Allowlist validation: all externally-sourced URLs validated against VW_DOMAIN_ALLOWLIST before storing"
    - "Session cache guard: discovery_config checked first; network call skipped if already populated"
    - "Centralized retry: while loop in _request() owns all 429 and transient error retry; get/post/put are thin wrappers"
    - "Non-blocking discovery: _discover_market_config() failure logs WARNING and continues with hardcoded fallback"

key-files:
  created: []
  modified:
    - volkswagencarnet/vw_connection.py
    - tests/region_support_test.py
    - tests/vw_connection_test.py

key-decisions:
  - "Discovery failure does NOT block NA login — self._base_api has pre-confirmed hardcoded value as fallback"
  - "Retry-After header respected when present; exponential 2^attempt (1s/2s/4s) when absent"
  - "_discover_endpoints() kept as thin alias to _discover_market_config() for backward compatibility"
  - "get() returns {state: Throttled} (not {status_code: 429}) after retry exhaustion in _request()"
  - "Transient network errors (ClientConnectionError, ServerTimeoutError) retry with same MAX_RETRIES_ON_RATE_LIMIT limit"

patterns-established:
  - "URL allowlist validation pattern: use _is_allowed_vw_domain() for any externally-sourced URL before storing"
  - "is_throttled observable: check connection.is_throttled before poll cycles to avoid wasted requests"

requirements-completed: [INT-01, INT-05]

# Metrics
duration: 5min
completed: 2026-02-19
---

# Phase 05 Plan 01: Reliability Discovery Summary

**VW domain allowlist with URL validation, full OIDC market config discovery with session caching, and centralized exponential-backoff retry (429 + transient errors) replacing three duplicate retry blocks in get/post/put**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-19T00:33:02Z
- **Completed:** 2026-02-19T00:38:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `VW_DOMAIN_ALLOWLIST` (8 VW Group domain suffixes) and `_is_allowed_vw_domain()` for security validation of all externally-sourced OIDC config URLs
- Replaced probe-only `_discover_endpoints()` with full `_discover_market_config()` that fetches, validates, and caches the entire OIDC discovery document; failure is non-blocking
- Centralized all retry logic into `_request()` with while loop, Retry-After header support, exponential backoff, and transient network error retry; removed three duplicate retry blocks from `get/post/put`
- Added `is_throttled` property and `discovery_config` attribute to Connection for observability

## Task Commits

Each task was committed atomically (combined in one commit since both tasks modified the same file):

1. **Task 1: VW_DOMAIN_ALLOWLIST, _is_allowed_vw_domain(), discovery_config, _discover_market_config()** - `5828ff0` (feat)
2. **Task 2: Centralized retry in _request(), remove duplicates from get/post/put** - `5828ff0` (feat)

## Files Created/Modified

- `volkswagencarnet/vw_connection.py` - Added VW_DOMAIN_ALLOWLIST, _is_allowed_vw_domain(), _discover_market_config(), _discover_endpoints() alias, is_throttled property, centralized retry in _request(), simplified get/post/put
- `tests/region_support_test.py` - Updated TestEndpointDiscovery tests to use new _discover_market_config() interface; added cache test; updated TestLoginWithDiscovery to reflect non-blocking discovery
- `tests/vw_connection_test.py` - Updated RateLimitTest to reflect centralized retry design (get() returns {"state": "Throttled"})

## Decisions Made

- Discovery failure does NOT block NA login — `self._base_api` has the pre-confirmed hardcoded value `https://b-h-s.spr.us00.p.con-veh.net` as fallback
- `_discover_endpoints()` kept as thin alias calling `_discover_market_config()` for backward compatibility with any external callers
- `get()` returns `{"state": "Throttled"}` (not `{"status_code": 429}`) after retry exhaustion — clearer semantics for callers
- Retry-After header parsed as float; exponential `2^attempt` seconds (1s, 2s, 4s) used when header absent or unparseable
- Transient network errors (`ClientConnectionError`, `ServerTimeoutError`) share the same `MAX_RETRIES_ON_RATE_LIMIT` = 3 retry budget

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test assertions for changed return values and API design**
- **Found during:** Task 2 (centralized retry in _request())
- **Issue:** `test_rate_limit` in `vw_connection_test.py` expected `{"status_code": 429}` (old behavior) and invocation count from old get() retry loop; `region_support_test.py` patched `_discover_endpoints` which doLogin() no longer calls
- **Fix:** Updated `test_rate_limit` to expect `{"state": "Throttled"}`; updated region_support_test.py discovery tests to call `_discover_market_config()` directly and patch the new method name in doLogin() tests
- **Files modified:** `tests/vw_connection_test.py`, `tests/region_support_test.py`
- **Verification:** `80 passed, 2 skipped` — all existing tests pass
- **Committed in:** `5828ff0`

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in tests after API change)
**Impact on plan:** Test updates required by the intentional API changes in the plan. No scope creep.

## Issues Encountered

None - plan executed cleanly. One additional test (`test_discovery_uses_cache_on_second_call`) was added to cover the new cache guard behavior in `_discover_market_config()`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `_discover_market_config()` and `is_throttled` are ready for Phase 5 Plan 2 integration tests
- `discovery_config` can be used by future plans to extract validated OIDC endpoints (token_endpoint, authorization_endpoint)
- Centralized retry in `_request()` means all API calls (get/post/put) now have consistent retry behavior

---
*Phase: 05-reliability-discovery*
*Completed: 2026-02-19*
