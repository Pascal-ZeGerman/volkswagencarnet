# Requirements: VW CarNet NA Authentication Fix

**Defined:** 2026-02-10
**Core Value:** NA users can authenticate with VW CarNet and retrieve vehicle data (battery level, location, status) for homelab integration without breaking existing EMEA functionality.

## v1 Requirements

Requirements for NA authentication fix. Each maps to roadmap phases.

### Authentication Core (F1-F3: Foundation)

- [ ] **AUTH-01**: Library can calculate X-QMAuth header using time-based HMAC-SHA256
- [x] **AUTH-02**: Library can exchange authorization code for IDK token with X-QMAuth header
- [x] **AUTH-03**: Library can register as MBB OAuth client and receive xclientId
- [ ] **AUTH-04**: Library stores NA region-specific constants (client_id, endpoints, scope, redirect_uri)
- [ ] **AUTH-05**: Library can distinguish between identity endpoint and base API endpoint for NA

### Token Exchange (F1-F2-F4: Three-Token Architecture)

- [x] **TOKEN-01**: Library can exchange IDK access_token for Brand token at `/login/v1/volkswagen/token`
- [x] **TOKEN-02**: Library can exchange IDK id_token for initial MBB token via MBB OAuth endpoint
- [x] **TOKEN-03**: Library immediately refreshes MBB token after initial grant (uses second token, not first)
- [x] **TOKEN-04**: Library stores all three token types separately (IDK, Brand, MBB) with metadata
- [x] **TOKEN-05**: Library includes X-Client-ID header in all MBB OAuth requests

### Token Management (F5-F6: Selection and Refresh)

- [ ] **MGMT-01**: Library selects correct token type per API endpoint (IDK for Cariad BFF, MBB for legacy, Brand for GraphQL)
- [ ] **MGMT-02**: Library can refresh IDK token independently using IDK refresh_token and X-QMAuth header
- [ ] **MGMT-03**: Library can refresh Brand token independently by re-exchanging current IDK access_token
- [ ] **MGMT-04**: Library can refresh MBB token independently using MBB refresh_token and X-Client-ID header
- [ ] **MGMT-05**: Library respects token hierarchy when refreshing (IDK refresh triggers Brand refresh if needed)
- [ ] **MGMT-06**: Library tracks token expiry per token type and refreshes proactively

### Integration & Reliability (F7-F10: Important Features)

- [ ] **INT-01**: Library can discover market-specific configuration from VW endpoints with fallback to hardcoded values
- [x] **INT-02**: Library routes NA authentication through identity.na.vwgroup.io (not base API)
- [x] **INT-03**: Library handles NA redirect URI format (HTTPS callback, not custom scheme)
- [ ] **INT-04**: Library discovers per-vehicle home region for API calls
- [ ] **INT-05**: Library handles rate limiting with exponential backoff and retry logic

### Backward Compatibility (Cross-Cutting)

- [ ] **COMPAT-01**: EMEA authentication flow remains unchanged (no breaking changes to existing API)
- [ ] **COMPAT-02**: Existing EMEA users can upgrade library without code changes
- [x] **COMPAT-03**: Region detection automatically routes to correct flow (EMEA vs NA) based on country parameter
- [x] **COMPAT-04**: Token storage structure supports both single-token (EMEA) and three-token (NA) models
- [ ] **COMPAT-05**: All existing vehicle data APIs work with NA authentication

### Testing & Validation

- [ ] **TEST-01**: NA authentication tested end-to-end with real CarNet credentials
- [ ] **TEST-02**: All three token types successfully obtained and validated
- [ ] **TEST-03**: Vehicle data retrieval (battery, location, status) working with NA tokens
- [ ] **TEST-04**: Token refresh working for all three token types
- [ ] **TEST-05**: EMEA authentication regression tests pass (no backward compatibility breaks)
- [ ] **TEST-06**: Multi-vehicle support working with NA authentication

## v2 Requirements

Deferred enhancements. Not in current roadmap.

### Advanced Features

- **GRAPH-01**: GraphQL API support using Brand token
- **PERSIST-01**: Persistent storage of MBB xclientId across sessions
- **PERSIST-02**: Token serialization/deserialization for session resume
- **REFRESH-01**: Pre-emptive token refresh before expiry (all three types in parallel)

### Nice-to-Have Reliability

- **DISC-01**: Dynamic client_id discovery from market config (instead of hardcoded fallback)
- **DISC-02**: Automatic API Level detection per vehicle (Level 0 vs Level 1)
- **ERROR-01**: Detailed error messages mapping HTTP errors to user-actionable guidance
- **RETRY-01**: Intelligent retry logic distinguishing transient vs permanent failures

## Out of Scope

Explicitly excluded to maintain focus on core goal.

| Feature | Reason |
|---------|--------|
| Vehicle control (lock, climate, charging) | Read-only monitoring sufficient for homelab use case |
| Mobile app development | Library is for programmatic access only |
| Real-time push notifications | Polling-based updates sufficient |
| 2FA/MFA handling | Not required for basic authentication flow |
| PKCE for NA region | Official app doesn't use it despite server support |
| API Level 0 + Level 1 simultaneous support | Modern vehicles use Level 1; implement Level 0 only if needed |
| APK decompilation for credentials | 2026 traffic capture provides current working credentials |
| GraphQL in v1 | REST API sufficient for vehicle monitoring |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 1: NA Foundation | Pending |
| AUTH-02 | Phase 2: NA OAuth Login Flow | Complete |
| AUTH-03 | Phase 3: Three-Token Architecture | Complete |
| AUTH-04 | Phase 1: NA Foundation | Pending |
| AUTH-05 | Phase 1: NA Foundation | Pending |
| TOKEN-01 | Phase 3: Three-Token Architecture | Complete |
| TOKEN-02 | Phase 3: Three-Token Architecture | Complete |
| TOKEN-03 | Phase 3: Three-Token Architecture | Complete |
| TOKEN-04 | Phase 3: Three-Token Architecture | Complete |
| TOKEN-05 | Phase 3: Three-Token Architecture | Complete |
| MGMT-01 | Phase 4: Token Lifecycle Management | Pending |
| MGMT-02 | Phase 4: Token Lifecycle Management | Pending |
| MGMT-03 | Phase 4: Token Lifecycle Management | Pending |
| MGMT-04 | Phase 4: Token Lifecycle Management | Pending |
| MGMT-05 | Phase 4: Token Lifecycle Management | Pending |
| MGMT-06 | Phase 4: Token Lifecycle Management | Pending |
| INT-01 | Phase 5: Reliability & Discovery | Pending |
| INT-02 | Phase 2: NA OAuth Login Flow | Complete |
| INT-03 | Phase 2: NA OAuth Login Flow | Complete |
| INT-04 | Phase 5: Reliability & Discovery | Pending |
| INT-05 | Phase 5: Reliability & Discovery | Pending |
| COMPAT-01 | Phase 6: Backward Compatibility | Pending |
| COMPAT-02 | Phase 6: Backward Compatibility | Pending |
| COMPAT-03 | Phase 2: NA OAuth Login Flow | Complete |
| COMPAT-04 | Phase 3: Three-Token Architecture | Complete |
| COMPAT-05 | Phase 6: Backward Compatibility | Pending |
| TEST-01 | Phase 7: End-to-End Validation | Pending |
| TEST-02 | Phase 7: End-to-End Validation | Pending |
| TEST-03 | Phase 7: End-to-End Validation | Pending |
| TEST-04 | Phase 7: End-to-End Validation | Pending |
| TEST-05 | Phase 7: End-to-End Validation | Pending |
| TEST-06 | Phase 7: End-to-End Validation | Pending |

**Coverage:**
- v1 requirements: 32 total
- Mapped to phases: 32
- Unmapped: 0

---
*Requirements defined: 2026-02-10*
*Last updated: 2026-02-18 after Phase 2 Plan 01 completion (AUTH-02, INT-02, INT-03, COMPAT-03)*
