# Requirements: VW CarNet Make Production Ready

**Defined:** 2026-02-27
**Core Value:** NA users can authenticate with VW CarNet and retrieve real vehicle data for homelab integration without breaking existing EMEA functionality.

## v1.1 Requirements

Requirements for the "make production ready" milestone. Focuses on code quality, robustness, and documentation — NA first, EMEA if easy.

### Error Handling

- [x] **ERR-01**: NA API failures (garage 404, RVS 5xx, vehicle session creation failure) surface descriptive exceptions with context instead of silently returning `None`
- [x] **ERR-02**: Connection exception messages include actionable guidance (e.g., "NA login failed: verify country='US' and credentials are correct")
- [x] **ERR-03**: Transient 5xx errors during NA data fetch retry automatically (up to 2 attempts) before returning `None`, complementing existing 429 retry logic

### Type Hints

- [x] **TYPE-01**: All public `Connection` methods (`doLogin`, `get`, `post`, `put`, `update`, `validate_tokens`) have return type annotations
- [x] **TYPE-02**: NA-specific private methods (`_login_na`, `_create_na_vehicle_session`, `_get_na_vehicle_data`, `_refresh_idk_token`, `_classify_endpoint`) have complete parameter and return type signatures
- [x] **TYPE-03**: Vehicle public properties (`position`, `doors_locked`, `vin`, `na_position`, `na_doors_locked`) have return type annotations matching their actual return types

### Logging

- [ ] **LOG-01**: NA auth flow (code extraction, PKCE challenge, token exchange steps) emits `DEBUG`-level progress logs with enough context to diagnose a failed login
- [ ] **LOG-02**: NA data fetches (vehicle session creation, RVS location call, RVS status call) log at `DEBUG` level with VIN context on each step
- [ ] **LOG-03**: Full token values and passwords are never written to any log level — token strings truncated to first 8 characters in debug output (`eyJa...`)
- [ ] **LOG-04**: Token refresh events (IDK, Brand, MBB) log at `INFO` level identifying which token type was refreshed

### Documentation

- [ ] **DOC-01**: README has a dedicated North America section covering: `country='US'` usage, credential requirements, `VW_TEST_SPIN` env var, and a minimal working example script
- [ ] **DOC-02**: `Connection.__init__()` and `doLogin()` docstrings describe the `country` parameter, NA vs EMEA routing, and the IDK-only auth level for NA Car-Net
- [ ] **DOC-03**: `vehicle.position` and `vehicle.doors_locked` docstrings describe the data source difference between NA (RVS) and EMEA (selectivestatus)
- [ ] **DOC-04**: `_refresh_idk_token()` docstring documents the non-standard `code_verifier` requirement in the refresh body for future maintainers

### Security

- [ ] **SEC-01**: `detect-secrets` scan reports zero new findings against the updated baseline (existing hook already configured; baseline must cover all new credential patterns)
- [ ] **SEC-02**: No full credential values (passwords, bearer tokens, secrets) appear in log output at any log level (enforced by LOG-03 above)
- [ ] **SEC-03**: NA token storage is in-memory only — no disk writes of token values, no credential leakage to filesystem in any code path

### Performance

- [ ] **PERF-01**: RVS vehicle data (GPS + lock status) is cached with a configurable TTL (default 30 seconds) — consecutive `vehicle.update()` calls within the TTL window skip the API roundtrip and return cached values
- [ ] **PERF-02**: NA authentication and initialization code paths are lazy — they do not increase `Connection.__init__()` startup time for EMEA users

### Code Cleanup

- [ ] **CLEAN-01**: All `# TODO` comments in NA code paths (`vw_connection.py`) are either resolved, removed, or replaced with a documented rationale comment
- [ ] **CLEAN-02**: `vw_vehicle.py` energy_flow TODOs (lines ~1651, ~1664, ~1676) are marked as pre-existing EMEA technical debt with `# noqa: T000` and a brief explanation
- [ ] **CLEAN-03**: `x-mobile-session-id` field name is either confirmed from a live session response (and the comment removed) or annotated with "TBD: field name unconfirmed from live traffic" and a unit test placeholder

### Test Coverage

- [ ] **TEST-01**: Unit tests cover NA error paths: token exchange failure, garage endpoint 404, and RVS 5xx all result in graceful `None` returns without uncaught exceptions
- [ ] **TEST-02**: Unit test confirms that IDK token refresh failure (expired refresh token) triggers a full `doLogin()` re-authentication rather than raising an unhandled exception
- [ ] **TEST-03**: All existing E2E tests (21) and unit tests (156+) pass after v1.1 changes — zero regressions

## v2 Requirements

Deferred — promote when API research confirms availability.

### Additional NA Vehicle Properties

- **NA-PROP-01**: `vehicle.battery_level` returns real state of charge (%) for NA vehicles
- **NA-PROP-02**: `vehicle.charging_state` returns real charging status for NA vehicles
- **NA-PROP-03**: Climate/HVAC properties work for NA vehicles

### Vehicle Control

- **CTRL-01**: `vehicle.set_lock()` works for NA vehicles via Car-Net API (if API exposes it)
- **CTRL-02**: `vehicle.set_climatisation()` works for NA vehicles via Car-Net API (if API exposes it)

## Out of Scope

| Feature | Reason |
|---------|--------|
| PyPI publishing | Not requested; v1.1 focuses on code quality |
| Home Assistant integration | Separate repository; not in scope |
| EMEA type hint coverage | NA first; EMEA coverage is v2 |
| Mobile app development | Library for programmatic access only |
| GraphQL API | REST sufficient |
| Real-time push notifications | Polling sufficient for homelab |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ERR-01 | Phase 15 | Complete |
| ERR-02 | Phase 15 | Complete |
| ERR-03 | Phase 15 | Complete |
| TYPE-01 | Phase 16 | Complete |
| TYPE-02 | Phase 16 | Complete |
| TYPE-03 | Phase 16 | Complete |
| LOG-01 | Phase 17 | Pending |
| LOG-02 | Phase 17 | Pending |
| LOG-03 | Phase 17 | Pending |
| LOG-04 | Phase 17 | Pending |
| DOC-01 | Phase 18 | Pending |
| DOC-02 | Phase 18 | Pending |
| DOC-03 | Phase 18 | Pending |
| DOC-04 | Phase 18 | Pending |
| SEC-01 | Phase 19 | Pending |
| SEC-02 | Phase 19 | Pending |
| SEC-03 | Phase 19 | Pending |
| CLEAN-01 | Phase 19 | Pending |
| CLEAN-02 | Phase 19 | Pending |
| CLEAN-03 | Phase 19 | Pending |
| PERF-01 | Phase 20 | Pending |
| PERF-02 | Phase 20 | Pending |
| TEST-01 | Phase 20 | Pending |
| TEST-02 | Phase 20 | Pending |
| TEST-03 | Phase 20 | Pending |

**Coverage:**
- v1.1 requirements: 25 total
- Mapped to phases: 25 (100%)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-27*
*Last updated: 2026-02-27 — v1.1 roadmap created, all requirements mapped*
