# VW CarNet NA Authentication Fix

## Current Milestone: v2.0 Feature Parity to App

**Goal:** Match the VW Car-Net mobile app's feature set for NA users — remote commands, alerts, navigation, and full Home Assistant dashboard support.

**Target features:**
- Remote engine start (for ICE/PHEV users; library-wide, BEV excluded at runtime)
- NA Alerts — read active alerts, configure all 4 types (speed/boundary/curfew/valet), acknowledge/dismiss
- AC control — read climatisation state + set target temperature (start/stop already done in v1.3)
- Navigation destination — send (lat/lon, address string, POI name+coords) + confirm delivery
- Dashboard (vw_dashboard.py) — wire all NA-specific properties for Home Assistant integration

## What This Is

Python library (volkswagencarnet) for VW CarNet API integration supporting both EMEA (Europe) and North America regions. Provides async API for vehicle monitoring (location, lock status, battery) with full OAuth2 + PKCE authentication, type-annotated API, structured logging, and comprehensive test coverage.

## Core Value

NA users can authenticate with VW CarNet and retrieve vehicle data (location, lock status) for homelab integration without breaking existing EMEA functionality.

## Requirements

### Validated

- ✓ EMEA region authentication — OAuth2 flow working for European users
- ✓ Vehicle data retrieval — battery, location, status, charging, climate data
- ✓ Async API design — aiohttp-based async operations
- ✓ Multi-vehicle support — handles multiple vehicles per account
- ✓ Token management — automatic token refresh and expiry handling
- ✓ NA OAuth2 + PKCE login flow — IDK token exchange via identity.na.vwgroup.io — v1.0
- ✓ Three-token architecture (IDK → Brand → MBB) with IDK-only fallback for Car-Net — v1.0
- ✓ NA vehicle data — GPS + lock status via RVS endpoint, real values confirmed via UAT — v1.0
- ✓ Descriptive error handling — NA failures raise AuthenticationError/APIError with actionable guidance — v1.1
- ✓ Full type annotations — all public/private Connection and Vehicle methods annotated — v1.1
- ✓ Structured logging — DEBUG logs across auth and data flows, credential redaction via redact() — v1.1
- ✓ Documentation — README NA section, NA limitations doc, Google-style docstrings — v1.1
- ✓ Security hardening — detect-secrets clean, in-memory token storage, VIN redaction in logs — v1.1
- ✓ Performance — per-VIN RVS TTL cache (30s), lazy NA init for EMEA users — v1.1
- ✓ Credential scrubbing — testing_creds.env removed from git history, .gitignore hardened — v1.2
- ✓ Code quality — dead code removed, constants extracted, is_na property, no magic strings — v1.2
- ✓ Comprehensive tests — 990 tests, 82% overall coverage, regression tests for all fixes — v1.2
- ✓ Exception narrowing — JWT catches narrowed, exc_info=True, 401 retry loops fixed — v1.2

### Active

- [ ] PR merge to main — feat/na-endpoint-coverage open as PR #2, pending review

### Validated (v1.5)

- ✓ NA-EU variable parity — 15 EMEA properties wired from NA endpoints (doors, EV range, trips, metadata) — v1.5
- ✓ NA-specific properties — security_status, cruise_range_units with no EMEA equivalent — v1.5
- ✓ Error resilience — 4 critical control flow bugs fixed, domain exceptions, data integrity guards — v1.5
- ✓ Code review gate — 23 findings cataloged, 8 actionable fixed, zero remain — v1.5

### Validated (v1.3)

- ✓ RVS data as properties — odometer, fuel_level, range, door/window/lock status — v1.3
- ✓ Optional RVS refresh trigger — POST /rvs/v1/vehicle/{id}/refresh, non-fatal — v1.3
- ✓ EV charge summary — battery_level, charging state, plug status, charging_time — v1.3
- ✓ Pre-trip climate settings — climatisation_state, climatisation_target_temp — v1.3
- ✓ Trip statistics — trip_last_km, trip_last_duration from SHORT_TERM endpoint — v1.3
- ✓ Remote lock/unlock — PUT /lockunlock/v1/ wired into set_lock() — v1.3
- ✓ Remote honk & flash — PUT /honkflash/v1/ wired into set_honk_and_flash() — v1.3
- ✓ EV charging start/stop — POST /ev/v1/.../charging/start|stop, wired into set_charger() — v1.3
- ✓ Climate start/stop — POST /ev/v1/.../pretripclimate/start|stop, wired into set_climatisation() — v1.3
- ✓ 401-retry on all NA write commands — invalidate session, refresh once, retry — v1.3

### Deferred (v2 candidates)

- NA alerts endpoints (/alert/v1/ speed/boundary/curfew/valet) — no EMEA equivalent, low priority
- EV charging settings read endpoint — target SOC, charge mode — low demand
- VHS health refresh trigger — low priority
- Per-trip analytics endpoint — low priority
- Send navigation destination (/poi/v1/) — no user demand

### Out of Scope

- Mobile app development — library for programmatic access only
- Real-time push notifications — polling-based updates sufficient
- GraphQL API support — REST sufficient
- EMEA feature enhancements — focus on NA authentication fix
- PyPI publishing — not yet requested

## Context

**Current state (2026-03-17):**
- Six milestones shipped (v1.0 through v1.5)
- PR #2 open: feat/na-endpoint-coverage → main, pending review
- 1,152 unit tests passing, 0 failures
- Tech stack: Python 3.11+, aiohttp, pytest, aioresponses, jwt, detect-secrets
- 11,406 Python LOC (library), ~16,800 total with tests
- All domain exceptions use UnsupportedOperationError/APIError hierarchy
- asyncio.Lock on update() for concurrency safety

**Known tech debt:**
- Dashboard (vw_dashboard.py) not updated with NA-specific properties (DASH-01 deferred to v2)
- No VALIDATION.md files for v1.1/v1.2/v1.3 phases (Nyquist MISSING — not a blocker)

**User situation:**
- VW vehicle owner in North America with active CarNet account
- Homelab setup ready for integration (likely Home Assistant)

## Constraints

- **Backward Compatibility**: Must not break existing EMEA users
- **Python Version**: Python 3.11+ (uses venv due to externally-managed environment)
- **Library Structure**: Must follow existing async patterns and code organization
- **Technical Stack**: Must use existing dependencies (aiohttp, pytest) unless necessary

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| IDK-only auth for NA Car-Net | Brand/MBB token paths return 404 for Car-Net tier | ✓ Good — works in production |
| PKCE required, no client_secret | NA AZS is a public client; client_secret not available | ✓ Good — confirmed from APK |
| code_verifier in refresh body | NA AZS non-standard extension (AzsRefreshRequest.java) | ✓ Good — required for token refresh |
| Hardcoded NA base API (no discovery) | discovery wrongly resolves to na.bff.cariad.digital (wrong) | ✓ Good — b-h-s.spr.us00.p.con-veh.net |
| Per-VIN RVS TTL cache (30s) | Prevent redundant API roundtrips on consecutive update() calls | ✓ Good — configurable via rvs_cache_ttl |
| is_na property over string comparisons | Eliminate magic strings, single source of truth | ✓ Good — used at 8 call sites |
| git-filter-repo to scrub creds | testing_creds.env accidentally committed | ✓ Good — history clean locally |
| aioresponses for HTTP mocking | Standard approach for aiohttp unit testing | ✓ Good — 1,152 tests passing |
| NA branch at top of property helpers | EMEA code paths untouched; NA returns early | ✓ Good — zero EMEA regressions |
| UnsupportedOperationError for unsupported ops | Domain-specific exception replaces 33 bare Exception raises | ✓ Good — clear error semantics |
| asyncio.Lock on update() | Prevent duplicate API requests from concurrent callers | ✓ Good — same pattern as _login_lock |
| Iterative wait loops (not recursive) | Prevent stack overflow on long polling | ✓ Good — bounded by range() |
| Narrowed except clauses throughout | Catch only expected exception types per call site | ✓ Good — no masking of unexpected errors |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-02 after v2.0 milestone start*
