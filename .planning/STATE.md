# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-10)

**Core value:** NA users can authenticate with VW CarNet and retrieve vehicle data for homelab integration without breaking existing EMEA functionality.
**Current focus:** Phase 3 - Three-Token Architecture (in progress)

## Current Position

Phase: 3 of 7 (Three-Token Architecture)
Plan: 1 of 3 in current phase (03-01 complete)
Status: Phase 3 in progress, Plan 1 complete
Last activity: 2026-02-18 -- Phase 3 Plan 1 completed (NA token registry infrastructure, MBB client registration)

Progress: [████░░░░░░] 40%

## Performance Metrics

**Velocity:**
- Total plans completed: 4
- Average duration: 6 min
- Total execution time: 0.37 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-na-foundation | 1 | 5 min | 5 min |
| 02-na-oauth-login-flow | 2 | 14 min | 7 min |
| 03-three-token-architecture | 1 | 5 min | 5 min |

**Recent Trend:**
- Last 5 plans: 5 min, 8 min, 6 min, 5 min
- Trend: stable

*Updated after each plan completion*

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

### Pending Todos

None yet.

### Blockers/Concerns

- ~~X-QMAuth secret from Audi analysis may differ for VW NA~~ RESOLVED: test vector confirmed working
- Brand token path unknown (/login/v1/volkswagen/token vs /login/v1/vw/token) -- test against live API in Phase 3
- IDK-only flow might suffice for Cariad BFF endpoints, potentially allowing Phase 3 scope reduction

## Session Continuity

Last session: 2026-02-18
Stopped at: Completed 03-three-token-architecture/03-01-PLAN.md
Resume file: .planning/phases/03-three-token-architecture/03-02-PLAN.md (next plan)
