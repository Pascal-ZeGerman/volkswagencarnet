# Roadmap: VW CarNet NA Authentication Fix

## Overview

This roadmap delivers North America region authentication for the volkswagencarnet library, enabling NA users to authenticate with VW CarNet and retrieve vehicle data for homelab integration. The implementation follows the three-token OAuth architecture (IDK, Brand, MBB) discovered through Audi Connect analysis and 2026 traffic capture, building from pure foundation functions through the complete token chain, lifecycle management, and production hardening -- all while preserving existing EMEA functionality.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: NA Foundation** - Region-specific constants, X-QMAuth calculation, endpoint separation (completed 2026-02-18)
- [x] **Phase 2: NA OAuth Login Flow** - IDK token exchange via NA identity provider (completed 2026-02-18)
- [x] **Phase 3: Three-Token Architecture** - Brand and MBB token layers with client registration (completed 2026-02-18)
- [ ] **Phase 4: Token Lifecycle Management** - Per-endpoint token selection and hierarchical refresh
- [x] **Phase 5: Reliability & Discovery** - Market config discovery, home region routing, rate limiting (completed 2026-02-19)
- [ ] **Phase 6: Backward Compatibility** - EMEA regression protection and upgrade path validation
- [x] **Phase 7: End-to-End Validation** - Real credentials, real vehicle, full test suite (completed 2026-02-20)
- [x] **Phase 8: Fix Stale Unit Tests** - Align unit tests with confirmed NA production behavior (completed 2026-02-26)
- [x] **Phase 9: Requirements Wording & Docs Cleanup** - Requirements accuracy and docstring consistency (completed 2026-02-26)
- [x] **Phase 10: NA Vehicle Data Endpoint Research** - APK analysis to document NA vehicle data API endpoints, auth requirements, and response structure (completed 2026-02-26)
- [ ] **Phase 11: NA Vehicle Data Implementation** - Wire NA endpoints into Vehicle class so real telemetry replaces 404/None for NA vehicles
- [ ] **Phase 12: Full API Values E2E Validation** - E2E tests confirming real GPS and lock values from live NA vehicle, plus EMEA regression

## Phase Details

### Phase 1: NA Foundation
**Goal**: Library has all NA-specific configuration and pure utility functions needed to begin OAuth authentication
**Depends on**: Nothing (first phase)
**Requirements**: AUTH-01, AUTH-04, AUTH-05
**Success Criteria** (what must be TRUE):
  1. X-QMAuth header can be calculated for any given timestamp and produces the expected HMAC-SHA256 output
  2. NA region constants (client_id, identity endpoint, base API, scope, redirect_uri) are stored and accessible separately from EMEA constants
  3. Library correctly distinguishes between identity.na.vwgroup.io (OAuth) and b-h-s.spr.us00.p.con-veh.net (vehicle data API) as separate endpoints
  4. Unit tests validate X-QMAuth calculation against known test vectors
**Plans**: 1 plan

Plans:
- [ ] 01-01-PLAN.md -- X-QMAuth constants/calculation, MBB OAuth constants, fix region support tests, add X-QMAuth unit tests

### Phase 2: NA OAuth Login Flow
**Goal**: NA user can complete the OAuth authorization flow and receive an IDK token (first token in the chain)
**Depends on**: Phase 1
**Requirements**: AUTH-02, INT-02, INT-03, COMPAT-03
**Success Criteria** (what must be TRUE):
  1. Library can exchange an NA authorization code for IDK access_token and refresh_token using X-QMAuth header at the NA identity endpoint
  2. NA OAuth flow routes through identity.na.vwgroup.io, not through the base API endpoint
  3. NA redirect URI uses HTTPS callback format (not custom scheme) and matches the registered redirect URI exactly
  4. Passing country="US" or country="CA" automatically routes to the NA authentication flow while omitting country or passing an EMEA country routes to the existing EMEA flow
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md -- follow_redirects() HTTPS stop condition, X-QMAuth injection in token exchange, _login_na() method with IDK-only probe (completed 2026-02-18)
- [x] 02-02-PLAN.md -- NAOAuthLoginTest class (6 tests): success, bad creds, token failure, redirect failure, network error, EMEA routing guard (completed 2026-02-18)

### Phase 3: Three-Token Architecture
**Goal**: Library obtains all three token types (IDK, Brand, MBB) from a single NA login, completing the full authentication chain
**Depends on**: Phase 2
**Requirements**: AUTH-03, TOKEN-01, TOKEN-02, TOKEN-03, TOKEN-04, TOKEN-05, COMPAT-04
**Success Criteria** (what must be TRUE):
  1. After successful NA login, library holds three separate token sets: IDK (access + refresh + id_token), Brand (access + refresh), and MBB (access + refresh + xclientId)
  2. Library can register as an MBB OAuth client and receive an xclientId for subsequent MBB operations
  3. MBB token is immediately refreshed after initial grant (second token is the working token, matching official app behavior)
  4. All MBB OAuth requests include X-Client-ID header with the registered xclientId
  5. Token storage structure supports both single-token (EMEA) and three-token (NA) models without breaking existing EMEA token handling
**Plans**: 3 plans

Plans:
- [x] 03-01-PLAN.md -- MBB_BRAND_CONFIG constant, Connection.__init__ NA token registry, _register_mbb_client(), na_auth_level property (completed 2026-02-18)
- [ ] 03-02-PLAN.md -- _exchange_brand_token() with /volkswagen→/vw fallback, _exchange_mbb_token(), _refresh_mbb_token(), extended _login_na() full chain with IDK-only fallback
- [ ] 03-03-PLAN.md -- NAThreeTokenTest class (8 tests): full success, brand fallback, mbb failures, refresh timing, xclientId injection, callback behavior

### Phase 4: Token Lifecycle Management
**Goal**: NA sessions persist beyond initial token expiry through correct token selection per API endpoint and independent refresh of all three token types
**Depends on**: Phase 3
**Requirements**: MGMT-01, MGMT-02, MGMT-03, MGMT-04, MGMT-05, MGMT-06
**Success Criteria** (what must be TRUE):
  1. Library automatically selects the correct token type based on the API endpoint being called (IDK for Cariad BFF, MBB for legacy vehicle APIs, Brand for GraphQL)
  2. IDK via refresh_token + code_verifier (X-QMAuth omitted — server rejects it with HTTP 400); Brand via fresh IDK access_token re-exchange, MBB via refresh_token + X-Client-ID
  3. Refreshing the IDK token automatically triggers Brand token refresh when the Brand token depends on the now-stale IDK access_token
  4. Library tracks expiry timestamps per token type and proactively refreshes before expiry
**Plans**: 2 plans

Plans:
- [ ] 04-01-PLAN.md — Infrastructure plumbing + token refresh methods (_classify_endpoint, _refresh_idk_token, _refresh_brand_token, _refresh_mbb_from_refresh_token, _validate_na_tokens, validate_tokens NA branch, _request 401 retry)
- [ ] 04-02-PLAN.md — NATokenLifecycleTest class (18 tests covering all MGMT requirements)

### Phase 5: Reliability & Discovery
**Goal**: Library handles production edge cases gracefully: discovers configuration dynamically, routes to correct home region per vehicle, and retries on transient failures
**Depends on**: Phase 4
**Requirements**: INT-01, INT-04, INT-05
**Success Criteria** (what must be TRUE):
  1. Library attempts market-specific configuration discovery from VW endpoints and falls back to hardcoded values if discovery fails
  2. Library discovers per-vehicle home region and routes API calls to the correct regional server
  3. Rate-limited responses (HTTP 429) trigger exponential backoff and retry (up to 3 attempts) before returning a throttled state
**Plans**: 3 plans

Plans:
- [ ] 05-01-PLAN.md — VW_DOMAIN_ALLOWLIST, _is_allowed_vw_domain(), _discover_market_config(), discovery_config attr, is_throttled property; centralized retry in _request() with Retry-After + exponential backoff; remove duplicate retry from get/post/put
- [ ] 05-02-PLAN.md — Vehicle._ensure_home_region() lazy discovery, _home_region_discovered guard, home_region_url property, wire into discover()
- [ ] 05-03-PLAN.md — reliability_test.py: MarketConfigDiscoveryTest (7 tests), HomeRegionDiscoveryTest (6 tests), RetryBackoffTest (8 tests)

### Phase 6: Backward Compatibility
**Goal**: Existing EMEA users experience zero breaking changes after the NA authentication code is merged
**Depends on**: Phase 5
**Requirements**: COMPAT-01, COMPAT-02, COMPAT-05
**Success Criteria** (what must be TRUE):
  1. EMEA authentication flow produces identical results before and after NA code is merged (same API calls, same token handling, same behavior)
  2. Existing EMEA users can upgrade the library version without modifying any of their code (no constructor signature changes, no new required parameters, no behavior changes for default configuration)
  3. All existing vehicle data APIs (battery, location, status, charging, climate) work correctly when authenticated via NA tokens
**Plans**: 2 plans

Plans:
- [ ] 06-01-PLAN.md — EMEA login sequence regression + Connection API surface contract (inspect.signature)
- [ ] 06-02-PLAN.md — NA-authenticated Vehicle property compat against EMEA fixture data

### Phase 7: End-to-End Validation
**Goal**: NA authentication is validated against real VW CarNet infrastructure with real credentials and a real vehicle
**Depends on**: Phase 6
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04, TEST-05, TEST-06
**Success Criteria** (what must be TRUE):
  1. Full NA login flow completes successfully with real CarNet credentials against the live VW API (not mocked)
  2. IDK token is successfully obtained and contains valid JWT claims; Brand/MBB tokens not available on NA Car-Net (endpoints return 404)
  3. Vehicle data (battery level, location, lock status) is successfully retrieved for at least one real NA vehicle
  4. IDK token refresh works without requiring re-login; Brand/MBB token refresh not applicable (NA Car-Net does not expose these endpoints)
  5. Full existing EMEA test suite passes with zero regressions
  6. Multiple vehicles are discoverable and accessible if the account has more than one vehicle
**Plans**: 2 plans

Plans:
- [ ] 07-01-PLAN.md — E2E infrastructure: norecursedirs config, cryptography dep, gitignore, conftest.py credential guard + login fixture; EMEA regression verification
- [ ] 07-02-PLAN.md — Live test files: test_na_login.py (TEST-01, TEST-02), test_na_vehicle_data.py (TEST-03, TEST-06), test_na_token_refresh.py (TEST-04)

### Phase 8: Fix Stale Unit Tests
**Goal**: All unit tests accurately reflect current production behavior after NA implementation evolved (empty base_api_candidates by design; IDK refresh omits X-QMAuth by design)
**Depends on**: Phase 7
**Requirements**: MGMT-02, INT-01
**Gap Closure**: Closes Tier 1 tech debt from v1.0 audit — 6 failing tests across 3 files

Plans:
- [ ] 08-01-PLAN.md — Fix test_idk_refresh_uses_fresh_xqmauth_per_attempt (vw_connection_test.py); update 5 discovery/region tests in region_support_test.py and reliability_test.py to reflect intentional empty base_api_candidates design

### Phase 9: Requirements Wording & Docs Cleanup
**Goal**: Requirements accurately describe implemented behavior; code docstrings match implementation; token structure is consistent at login time and post-refresh
**Depends on**: Phase 8
**Requirements**: MGMT-02, TEST-02, TEST-04
**Gap Closure**: Closes Tier 2 + Tier 3 code tech debt from v1.0 audit

Plans:
- [x] 09-01-PLAN.md — Update REQUIREMENTS.md wording for MGMT-02/TEST-02/TEST-04; fix _refresh_idk_token() docstring (remove "Requires X-QMAuth header"); add issued_at key to _login_na() token writes for consistency (completed 2026-02-26)

### Phase 10: NA Vehicle Data Endpoint Research
**Goal**: NA vehicle data API endpoints are fully documented — URLs, required auth tokens, request format, and response structure — so implementation can proceed without guesswork
**Depends on**: Phase 9
**Requirements**: DISC-01, DISC-02
**Success Criteria** (what must be TRUE):
  1. At least one NA vehicle data endpoint URL is identified from APK source (jadx-decompiled Java/Kotlin) that returns vehicle state (location, lock status, or similar)
  2. The token type required for NA vehicle data calls is confirmed (IDK id_token, access_token, or other) and the required Authorization header format is documented
  3. The response JSON structure for at least the location and lock-status endpoints is documented with field names and types
  4. A written endpoint spec exists in .planning/ that plan-phase can reference during Phase 11 implementation
**Plans**: 1 plan

Plans:
- [ ] 10-01-PLAN.md — Write NA-VEHICLE-API-SPEC.md from pre-extracted APK findings: RVS endpoints, carnetVehicleToken auth flow, VehicleLocation/DoorLockStatus response structures, Phase 11 priority order

### Phase 11: NA Vehicle Data Implementation
**Goal**: NA vehicles return real telemetry (GPS coordinates and lock status) from live VW CarNet API instead of 404 errors or None values
**Depends on**: Phase 10
**Requirements**: DATA-01, DATA-02, DATA-03, PROP-01, PROP-02
**Success Criteria** (what must be TRUE):
  1. `Vehicle.discover()` completes for NA vehicles and populates service data without hitting 404 on every capability endpoint
  2. Calling `vehicle.update()` for a NA vehicle returns a non-404 response and stores parsed data in `Vehicle._states`
  3. `vehicle.position` returns a dict with real latitude and longitude values (not None) for a NA vehicle with location sharing enabled
  4. `vehicle.doors_locked` returns a real boolean (True or False, not None) reflecting the actual lock state of the NA vehicle
  5. All NA data calls use the correct token type identified in Phase 10 research (no auth errors on data retrieval)
**Plans**: TBD

Plans:
- [ ] 11-01-PLAN.md — Vehicle.discover() NA branch: skip/replace EMEA capability endpoints, call NA vehicle list endpoint, store service data in _states
- [ ] 11-02-PLAN.md — Vehicle NA property implementation: position and doors_locked properties reading from NA _states structure; unit tests with fixture data

### Phase 12: Full API Values E2E Validation
**Goal**: Real GPS coordinates and lock status are confirmed from a live NA vehicle, and all v1.0 NA tests plus the full EMEA unit suite remain green
**Depends on**: Phase 11
**Requirements**: TEST-07, TEST-08, TEST-09, TEST-10
**Success Criteria** (what must be TRUE):
  1. E2E test `test_na_vehicle_data` asserts `vehicle.position` returns non-None latitude and longitude from the real NA vehicle (not a fixture)
  2. E2E test `test_na_lock_status` asserts `vehicle.doors_locked` returns a real boolean from the real NA vehicle
  3. All six v1.0 NA e2e tests (login, vehicle discovery, IDK token refresh) continue passing without modification
  4. Running `pytest tests/` (unit suite, no credentials required) exits with 0 failures after Phase 11 changes are merged
**Plans**: TBD

Plans:
- [ ] 12-01-PLAN.md — New e2e tests: test_na_position.py (TEST-07) and test_na_lock_status.py (TEST-08); EMEA regression run confirming 0 failures (TEST-09, TEST-10)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10 -> 11 -> 12

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. NA Foundation | 1/1 | Complete   | 2026-02-18 |
| 2. NA OAuth Login Flow | 2/2 | Complete    | 2026-02-18 |
| 3. Three-Token Architecture | 3/3 | Complete   | 2026-02-18 |
| 4. Token Lifecycle Management | 1/2 | In Progress|  |
| 5. Reliability & Discovery | 3/3 | Complete   | 2026-02-19 |
| 6. Backward Compatibility | 1/2 | In Progress|  |
| 7. End-to-End Validation | 2/2 | Complete   | 2026-02-20 |
| 8. Fix Stale Unit Tests | 1/1 | Complete | 2026-02-26 |
| 9. Requirements Wording & Docs Cleanup | 1/1 | Complete | 2026-02-26 |
| 10. NA Vehicle Data Endpoint Research | 1/1 | Complete    | 2026-02-26 |
| 11. NA Vehicle Data Implementation | 1/2 | In Progress|  |
| 12. Full API Values E2E Validation | 0/1 | Pending | |
