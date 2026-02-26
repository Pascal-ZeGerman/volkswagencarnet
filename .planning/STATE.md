# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-25)

**Core value:** NA users can authenticate with VW CarNet and retrieve vehicle data for homelab integration without breaking existing EMEA functionality.
**Current focus:** Milestone v1.5 — Full API Values (Phase 9 complete, Phase 10 ready to plan)

## Current Position

Phase: 08-fix-stale-unit-tests (complete)
Plan: 1 of 1 complete
Status: Phase 8 complete — unit test suite at 0 failures
Last activity: 2026-02-26 - Completed Phase 8 Plan 1: Fix 6 stale unit tests

Progress: [████████░░] 80%

## Performance Metrics

**Velocity:**
- Total plans completed: 9
- Average duration: 3.2 min
- Total execution time: 0.49 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-na-foundation | 1 | 5 min | 5 min |
| 02-na-oauth-login-flow | 2 | 14 min | 7 min |
| 03-three-token-architecture | 3 | 8 min | 2.7 min |
| 04-token-lifecycle-management | 2 | 7 min | 3.5 min |
| 05-reliability-discovery | 3 | 8 min | 2.7 min |
| 08-fix-stale-unit-tests | 1 | 2 min | 2 min |

**Recent Trend:**
- Last 5 plans: 1 min, 2 min, 1 min, 2 min, 2 min
- Trend: fast

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 08-fix-stale-unit-tests]: NA base_api_candidates == [] is intentional — hardcoded base_api used directly, discovery candidates unused
- [Phase 08-fix-stale-unit-tests]: IDK refresh body must contain refresh_token, grant_type, code_verifier — X-QMAuth intentionally absent (HTTP 400)
- [Phase 08-fix-stale-unit-tests]: NA doLogin fetches vehicle list via _request() to garage endpoint, not get() to vehicle/v2/vehicles
- [Roadmap v1.5]: 3 phases (10-12) derived from 11 v1.5 requirements; APK research gates implementation gates E2E validation
- [Phase 07-end-to-end-validation]: Soft-assert pattern for vehicle data — None values soft-skipped (unsupported), not failed
- [Phase 07-end-to-end-validation]: expires_at key used for token expiry assertions (not 'expiry') — matches actual _na_tokens structure
- [NA auth confirmed 2026-02-25]: IDK-only flow confirmed working; Brand/MBB not available on NA Car-Net (`/login/v1/volkswagen/token` → 404)
- [NA auth confirmed 2026-02-25]: Vehicle list at `GET /account/v1/garage?idToken={idk_id_token}` — confirmed working
- [NA auth confirmed 2026-02-25]: `/vehicle/v1/vehicles/{vin}/capabilities` and selectivestatus return 404 for NA — different data API needed

### Pending Todos

None yet.

### Blockers/Concerns

- NA vehicle data endpoints unknown — Phase 10 APK research must resolve before implementation can begin
- `/vehicle/v1/vehicles/{vin}/capabilities` returns 404 for NA vehicles — EMEA discovery path cannot be reused

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 1 | Add a scan for secrets into all github commits to prevent leakage | 2026-02-26 | a62795c | [1-add-a-scan-for-secrets-into-all-github-c](.planning/quick/1-add-a-scan-for-secrets-into-all-github-c/) |

## Session Continuity

Last session: 2026-02-26
Stopped at: Completed 08-01-PLAN.md (fix stale unit tests — 6 tests fixed, 0 failures)
Resume file: None
