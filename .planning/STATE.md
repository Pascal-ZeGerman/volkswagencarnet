# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-10)

**Core value:** NA users can authenticate with VW CarNet and retrieve vehicle data for homelab integration without breaking existing EMEA functionality.
**Current focus:** Phase 5 - Reliability Discovery (complete) / Phase 6 next

## Current Position

Phase: 6 of 7 (Backward Compatibility) - IN PROGRESS
Plan: 1 of 1 in current phase (06-01 complete)
Status: Phase 6 Plan 1 complete — EMEA regression tests and API surface contract tests
Last activity: 2026-02-19 -- Phase 6 Plan 1 completed (emea_regression_test.py: ConnectionAPIContractTest, 5 EMEA regression tests)

Progress: [█████████░] 95%

## Performance Metrics

**Velocity:**
- Total plans completed: 8
- Average duration: 3.4 min
- Total execution time: 0.46 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-na-foundation | 1 | 5 min | 5 min |
| 02-na-oauth-login-flow | 2 | 14 min | 7 min |
| 03-three-token-architecture | 3 | 8 min | 2.7 min |
| 04-token-lifecycle-management | 2 | 7 min | 3.5 min |
| 05-reliability-discovery | 3 | 8 min | 2.7 min |

**Recent Trend:**
- Last 5 plans: 5 min, 2 min, 1 min, 2 min, 1 min
- Trend: fast

*Updated after each plan completion*
| Phase 06-backward-compatibility P01 | 2 | 2 tasks | 1 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: 7 phases derived from 32 requirements following authentication dependency chain
- [Roadmap]: COMPAT requirements distributed across relevant phases (COMPAT-03 -> Phase 2, COMPAT-04 -> Phase 3) with EMEA-focused ones in Phase 6
- [Research]: Simplified IDK-only flow may work for modern vehicles -- validate early in Phase 2 before investing in full three-token complexity (Phase 3)
- [Phase 01-na-foundation]: Use time.time() for X-QMAuth (not datetime.utcnow() deprecated in Python 3.12+)
- [Phase 01-na-foundation]: X-QMAuth divides by 100 seconds (not 100000ms) for 100-second HMAC windows
- [Phase 01-na-foundation]: NA base_api is pre-confirmed (b-h-s.spr.us00.p.con-veh.net), discovery only needed as fallback
- [Phase 02-na-oauth-login-flow plan 01]: NA dispatch placed BEFORE try block in _login() to avoid shadowing NA exception handlers
- [Phase 02-na-oauth-login-flow plan 01]: X-QMAuth header NOT removed after post_form -- retained for Phase 4 token refresh
- [Phase 02-na-oauth-login-flow plan 01]: No live IDK-only probe in _login_na() -- hypothesis validated via Phase 3 test fixtures
- [Phase 02-na-oauth-login-flow plan 01]: PKCE explicitly None in _login_na() per 2026 traffic analysis (app does not use PKCE)
- [Phase 02-na-oauth-login-flow plan 02]: Failure-path tests call conn._login_na() directly; only test_na_login_success calls conn._login() to validate dispatch chain
- [Phase 02-na-oauth-login-flow plan 02]: Mock at Connection instance level with patch.object(conn, ...) not at module level
- [Phase 03-three-token-architecture plan 01]: _register_mbb_client() returns xclientId string but does NOT assign self._xclient_id -- caller (_login_na) owns assignment to allow conditional callback invocation
- [Phase 03-three-token-architecture plan 01]: on_xclient_id callback fires only for NEW registrations, not when xclient_id is caller-injected -- prevents unnecessary persistence writes
- [Phase 03-two]: Brand token exchange uses JSON body (not form-encoded); MBB uses form-encoded body with key 'token'
- [Phase 03-two]: _refresh_mbb_token defined as separate method for Phase 4 independent token refresh reuse
- [Phase 03-two]: MBB working token is the immediately refreshed token (initial grant rotated on first use)
- [Phase 03-three]: _make_na_conn(**kwargs) helper pattern supports optional constructor params without per-test boilerplate
- [Phase 03-three]: Store AsyncMock as variable before patch.object when call_count/call_args inspection needed post-call
- [Phase 04-01]: _retry_401 as explicit method parameter (not kwargs key) avoids leaking unknown kwargs to aiohttp session.request()
- [Phase 04-01]: Brand/MBB token refresh failures non-critical -- degrade to idk_only rather than failing validation
- [Phase 04-01]: IDK refresh failure is critical -- returns False from _validate_na_tokens() triggering full re-login
- [Phase 04-01]: _classify_endpoint raises ValueError for unknown NA URLs -- programmer error should fail loudly
- [Phase 04-02]: Pre-populate _session_tokens['identity'] before calling _refresh_idk_token() in tests -- mirror update requires existing dict entry
- [Phase 04-02]: Use MagicMock (not AsyncMock) for session.request patching -- async with requires synchronous callable returning context manager
- [Phase 04-02]: AsyncMock must be passed directly to patch.object (not as return_value= kwarg) to preserve await compatibility for session.post
- [Phase 05-01]: Discovery failure does NOT block NA login — self._base_api has pre-confirmed hardcoded value as fallback
- [Phase 05-01]: get() returns {state: Throttled} (not {status_code: 429}) after retry exhaustion in _request()
- [Phase 05-01]: _discover_endpoints() kept as thin alias to _discover_market_config() for backward compatibility
- [Phase 05-01]: Transient network errors (ClientConnectionError, ServerTimeoutError) retry with same MAX_RETRIES_ON_RATE_LIMIT limit as 429
- [Phase 05-02]: Guard flag set at entry (not exit) of _ensure_home_region() — optimistic lock prevents concurrent probe storms
- [Phase 05-02]: EMEA returns immediately without network calls — home region is statically configured, no probe needed
- [Phase 05-02]: Domain allowlist validation before probing each candidate — guards against config injection or malformed entries
- [Phase 05-02]: HTTP 200/400/401/403/404 all count as "reachable" — auth errors prove routing works; 5xx or connection errors mean unreachable
- [Phase 05-03]: All three test classes in single reliability_test.py — unified scope for tightly related Phase 5 capabilities
- [Phase 05-03]: raises_disconnect as plain (non-async) function for ServerDisconnectedError tests — session.request() called synchronously before context manager
- [Phase 05-03]: assertLogs() context manager for WARNING verification — more robust than patching logger or inspecting mock calls
- [Phase 06-backward-compatibility]: ConnectionAPIContractTest uses IsolatedAsyncioTestCase (not pytest class) since all 6 methods are synchronous def tests — no async machinery needed
- [Phase 06-backward-compatibility]: EMEA regression tests use module-level @pytest.mark.asyncio async functions with connection/session fixtures (auto-registered via conftest.py) — no inline mock factories
- [Phase 06-backward-compatibility]: _na_auth_level default confirmed as Python None (not string 'none') per vw_connection.py line 122 — assertion uses 'is None'

### Pending Todos

None yet.

### Blockers/Concerns

- ~~X-QMAuth secret from Audi analysis may differ for VW NA~~ RESOLVED: test vector confirmed working
- ~~Brand token path unknown~~ DEFERRED: Both /login/v1/volkswagen/token and /login/v1/vw/token fallback implemented, live validation in Phase 5+
- IDK-only flow might suffice for Cariad BFF endpoints, potentially allowing Phase 3 scope reduction

## Session Continuity

Last session: 2026-02-19
Stopped at: Completed 05-03-PLAN.md (Phase 5 complete)
Resume file: .planning/phases/06-emea-compat/ (next phase)
