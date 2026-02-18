# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-10)

**Core value:** NA users can authenticate with VW CarNet and retrieve vehicle data for homelab integration without breaking existing EMEA functionality.
**Current focus:** Phase 2 - NA OAuth Login Flow (COMPLETE)

## Current Position

Phase: 2 of 7 (NA OAuth Login Flow)
Plan: 2 of 2 in current phase (02-02 complete -- phase complete)
Status: Phase 2 complete, ready for Phase 3
Last activity: 2026-02-18 -- Phase 2 Plan 2 completed (NAOAuthLoginTest: 6 tests, 53 total passing)

Progress: [███░░░░░░░] 30%

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: 6 min
- Total execution time: 0.32 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-na-foundation | 1 | 5 min | 5 min |
| 02-na-oauth-login-flow | 2 | 14 min | 7 min |

**Recent Trend:**
- Last 5 plans: 5 min, 8 min, 6 min
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

### Pending Todos

None yet.

### Blockers/Concerns

- ~~X-QMAuth secret from Audi analysis may differ for VW NA~~ RESOLVED: test vector confirmed working
- Brand token path unknown (/login/v1/volkswagen/token vs /login/v1/vw/token) -- test against live API in Phase 3
- IDK-only flow might suffice for Cariad BFF endpoints, potentially allowing Phase 3 scope reduction

## Session Continuity

Last session: 2026-02-18
Stopped at: Completed 02-na-oauth-login-flow/02-02-PLAN.md
Resume file: .planning/phases/03-na-vehicle-data/ (next phase)
