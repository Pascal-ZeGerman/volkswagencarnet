# VW NA Authentication Analysis - Implementation Impact Assessment

**Date**: 2026-02-10
**Source**: Audi Connect HA integration analysis (sister brand, shared VW Group IT infrastructure)
**Target**: volkswagencarnet Python library

---

## ⚠️ Status: Superseded for NA (2026-08-12)

This analysis extrapolated NA requirements from an Audi/EMEA integration and was never confirmed live against VW's NA servers. Live traffic capture and testing since have disproven several of its central "required" conclusions for NA specifically:

| This doc claims (NA) | Confirmed live (2026-08-12) |
|---|---|
| X-QMAuth header is required for token exchange (Gap 2) | X-QMAuth is **EMEA-only**. Sending it on NA causes HTTP 400 "Internal Service validation failure". |
| Three-token architecture: IDK → Brand → MBB (Gap 3) | NA is **IDK-only**. Brand/MBB token endpoints return 404 for NA. |
| MBB OAuth client registration required (Gap 4) | Not applicable to NA — no MBB token to register a client for. |
| Scope `"openid email"` (Testing Strategy, Gap 8) | NA scope is `"openid"`. |
| Redirect URI is an HTTPS callback (Testing Strategy, Gap 8) | NA redirect URI is the custom scheme `kombi:///login`, not HTTPS. |
| NA `client_id` = `b680e751-7e1f-4008-8ec1-3a528183d215@apps_vw-dilab_com` (Gap 8) | Stale. Current value is `59992128-69a9-42c3-8621-7942041ba824_MYVW_ANDROID` (see `volkswagencarnet/vw_const.py`). |

Instead, NA requires a `play_integrity_token` field (Google Play Integrity attestation) on the token exchange/refresh body — a requirement this analysis didn't anticipate. The server checks only that the field is present and non-empty; it doesn't validate the value.

The rest of this document is kept as a historical record of the original (Audi-derived) hypothesis. **Do not implement the X-QMAuth, three-token, or MBB registration recommendations below for NA** — see `CLAUDE.md` and `docs/NA_LIMITATIONS.md` for the current, confirmed-working NA auth flow.

---

## Executive Summary

The Audi Connect authentication analysis reveals a **significantly more complex OAuth2/OIDC flow** than currently implemented in the volkswagencarnet library. The VW Group uses a **3-layer token architecture** with dynamic endpoint discovery, which differs substantially from the current simplified implementation.

### Key Finding

**Current Implementation Gap**: The library uses a simplified OAuth flow, while the actual VW Group API requires:
1. Dynamic market configuration discovery
2. Three distinct token types (IDK → Brand → MBB)
3. Time-based HMAC authentication (X-QMAuth)
4. MBB OAuth client registration
5. Immediate token refresh after initial grant

---

## Critical Differences: Current vs. Required Implementation

### 1. Authentication Flow Complexity

#### Current Implementation
```python
# Simplified OAuth2 flow
1. Get OpenID config
2. Authorize (username/password)
3. Exchange code for tokens
4. Use tokens for API calls
```

#### Required Implementation (from Audi analysis)
```python
# Multi-layered OAuth2/OIDC flow
1. Discovery Phase:
   - Get markets configuration
   - Get market-specific config (extracts client_id)
   - Get OpenID configuration

2. Authorization Phase (with PKCE):
   - Generate PKCE challenge/verifier
   - Initial authorization request
   - Submit email
   - Submit password (may include HMAC)
   - Follow redirects to get authorization code

3. Token Exchange Phase:
   - Exchange code for IDK token (requires X-QMAuth header)
   - Exchange IDK token for Brand token (AZS)
   - Register MBB OAuth client
   - Get initial MBB token
   - Immediately refresh MBB token → final vwToken

4. API Usage:
   - Different tokens for different API levels
   - Token refresh logic for each type
```

---

## Detailed Gap Analysis

### Gap 1: Market Configuration Discovery

**Current**: Hardcoded endpoints and client IDs in `vw_const.py`

**Required**: Dynamic discovery from market configuration endpoints

```python
# MISSING: Market discovery
GET https://content.app.my.vw.com/service/mobileapp/configurations/markets
GET https://content.app.my.vw.com/service/mobileapp/configurations/market/us/en?v=4.23.1

# Extract from response:
{
  "idkClientIDAndroidLive": "<dynamic-client-id>",
  "myAudiAuthorizationServerProxyServiceURLProduction": "https://...",
  "mbbOAuthBaseURLLive": "https://mbboauth-1d.prd.ece.vwg-connect.com/mbbcoauth"
}
```

**Impact**:
- Client IDs may change over time
- Current hardcoded values may become outdated
- Regional variations not properly handled

---

### Gap 2: X-QMAuth Header

**Current**: Not implemented

**Required**: Time-based HMAC-SHA256 authentication header for certain endpoints

```python
# MISSING: X-QMAuth calculation
def calculate_X_QMAuth():
    # Time in 100-second intervals since epoch
    gmtime_100sec = int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds() / 100)

    # VW Group secret (hardcoded in apps)
    xqmauth_secret = bytes([
        26, 182, 153, 37, 172, 23, 154, 170, 78, 131,
        171, 230, 113, 169, 71, 109, 23, 100, 24, 184,
        91, 215, 6, 241, 67, 108, 161, 91, 230, 71,
        152, 156
    ])

    xqmauth_val = hmac.new(
        xqmauth_secret,
        str(gmtime_100sec).encode('ascii'),
        digestmod='sha256'
    ).hexdigest()

    return f"v1:01da27b0:{xqmauth_val}"

# Used in token exchange requests:
headers = {
    "X-QMAuth": calculate_X_QMAuth(),
    # ... other headers
}
```

**Impact**:
- Token exchange may fail without this header
- Some NA endpoints may require it
- Current 2026 traffic suggests it's still required

---

### Gap 3: Three-Token Architecture

**Current**: Single token type (`_session_tokens`)

**Required**: Three distinct token types with different purposes

```python
# MISSING: Token hierarchy

# 1. IDK Token (Identity Kit)
_bearer_token_json = {
    "access_token": "...",  # Used for brand token exchange
    "id_token": "...",      # Used for MBB token exchange
    "refresh_token": "...", # Refresh IDK tokens
    "expires_in": 3600
}

# 2. Brand Token (Audi/VW Authorization Server)
audiToken = {  # or vwToken for VW
    "access_token": "...",  # Used for GraphQL API
    "expires_in": 3600
}

# 3. MBB Token (Mobile Backend Bridge)
mbboauthToken = {
    "access_token": "...",  # Used for vehicle control APIs
    "refresh_token": "...", # Long-lived (60 days)
    "expires_in": 3600
}

# Also need:
xclientId = "<registered-mbb-client-id>"
```

**Impact**:
- Different API endpoints require different tokens
- API Level 0 (legacy) uses MBB token
- API Level 1 (modern) uses IDK token
- GraphQL uses Brand token
- Current single-token approach won't work for all endpoints

---

### Gap 4: MBB OAuth Client Registration

**Current**: Not implemented

**Required**: Register as MBB OAuth client during login

```python
# MISSING: MBB registration
POST https://mbboauth-1d.prd.ece.vwg-connect.com/mbbcoauth/mobile/register/v1

Body:
{
  "client_name": "<device-model>",
  "platform": "google",
  "client_brand": "Volkswagen",
  "appName": "myVW",
  "appVersion": "4.31.0",
  "appId": "com.volkswagen.weconnect"
}

Response:
{
  "client_id": "<generated-client-id>"
}

# Store as xclientId and use in all MBB requests:
headers["X-Client-ID"] = xclientId
```

**Impact**:
- MBB OAuth endpoints won't work without client registration
- Each session needs its own client ID
- Should be stored for token refresh

---

### Gap 5: Immediate Token Refresh Pattern

**Current**: Tokens used directly after exchange

**Required**: Immediate refresh after initial MBB token grant

```python
# MISSING: Immediate refresh pattern

# Step 1: Get initial MBB token
POST /mbbcoauth/mobile/oauth2/v1/token
Body: grant_type=id_token&token=<id-token>&scope=sc2:fal
Response: { "access_token": "...", "refresh_token": "..." }

# Step 2: IMMEDIATELY refresh it (app always does this)
POST /mbbcoauth/mobile/oauth2/v1/token
Body: grant_type=refresh_token&token=<refresh-token>&scope=sc2:fal
Response: { "access_token": "...", "token_type": "Bearer", "expires_in": 3600 }

# Use the SECOND token for API calls
```

**Impact**:
- Using the first token may not work
- This is the pattern the official app follows
- Unknown why this is required (possibly server-side flag setting)

---

### Gap 6: PKCE Implementation Details

**Current**: PKCE methods exist but may not be used correctly

**Required**: PKCE is supported by server but **NOT used by official VW NA app**

```python
# From 2026 traffic analysis:
# - Server supports PKCE (code_challenge_methods_supported: ["S256"])
# - Official app does NOT include code_challenge in auth request
# - Official app does NOT include code_verifier in token exchange
# - PKCE is optional for VW Group APIs

# Current implementation has PKCE methods:
def _generate_pkce_verifier(self) -> str: ...
def _generate_pkce_challenge(self, code_verifier: str) -> str: ...

# But analysis shows:
REGION_CONFIGS["NA"]["use_pkce"] = False  # App doesn't use it
```

**Impact**:
- Current PKCE implementation may be unnecessary for NA
- Should be configurable per region
- EMEA behavior may differ

---

### Gap 7: Token Refresh Complexity

**Current**: Simple token refresh

**Required**: Hierarchical token refresh with multiple refresh endpoints

```python
# MISSING: Multi-token refresh logic

# Refresh MBB Token (for vehicle APIs):
POST https://mbboauth-1d.prd.ece.vwg-connect.com/mbbcoauth/mobile/oauth2/v1/token
Headers: X-Client-ID: <xclientId>
Body: grant_type=refresh_token&token=<mbb-refresh-token>&scope=sc2:fal

# Refresh IDK Token (for Cariad APIs):
POST https://{region}.bff.cariad.digital/login/v1/idk/token
Headers: X-QMAuth: <calculated>
Body: client_id=<client-id>&grant_type=refresh_token&refresh_token=<idk-refresh-token>&response_type=token id_token

# Refresh Brand Token (for GraphQL):
POST https://{region}.bff.cariad.digital/login/v1/vw/token
Body: {"token": "<new-idk-access-token>", "grant_type": "id_token", "stage": "live", "config": "myvw"}

# Need to track expiry for each token type separately
```

**Impact**:
- Current refresh logic won't work for all token types
- Need separate refresh timers
- If IDK refresh fails, need to refresh MBB too
- Complex dependency chain

---

### Gap 8: Regional OAuth Endpoint Differences

**Current**: Basic region detection, hardcoded endpoints

**Required**: Different OAuth flows per region

```python
# Current vw_const.py (simplified):
REGION_CONFIGS = {
    "EMEA": {
        "base_api": "https://emea.bff.cariad.digital",
        "client_id": "a24fba63-34b3-4d43-b181-942111e6bda8@apps_vw-dilab_com",
    },
    "NA": {
        "base_api": "https://b-h-s.spr.us00.p.con-veh.net",
        "client_id": "b680e751-7e1f-4008-8ec1-3a528183d215@apps_vw-dilab_com",  # stale — see superseded-status note above; current value is 59992128-69a9-42c3-8621-7942041ba824_MYVW_ANDROID
    }
}

# MISSING from current implementation:
REGION_CONFIGS["NA"].update({
    "identity_endpoint": "https://identity.na.vwgroup.io",  # Separate from base_api
    "scope": "openid email",  # Different from EMEA
    "redirect_uri": "https://b-h-s.spr.us00.p.con-veh.net/oidc/v1/oauth/callback",  # HTTPS, not custom scheme
    "mbb_oauth_base": "https://mbboauth-1d.prd.ece.vwg-connect.com/mbbcoauth",
    "brand_path": "/login/v1/volkswagen",  # or /vw
})
```

**Impact**:
- NA region has separate identity provider
- Redirect URIs are different (HTTPS callback vs custom scheme)
- Scopes are minimal for NA
- Current implementation may not authenticate correctly for NA

---

## Impact on Test Files

### Current Test Structure

Tests focus on:
- Basic connection/authentication
- Region detection
- Endpoint discovery
- PKCE generation
- Cookie management

### Required Test Additions

#### 1. Market Configuration Discovery Tests
```python
async def test_market_config_discovery():
    """Test dynamic market configuration retrieval."""
    # Mock GET /configurations/markets
    # Mock GET /configurations/market/us/en
    # Verify client_id extracted
    # Verify endpoints populated
    pass

async def test_market_config_fallback():
    """Test fallback when market config unavailable."""
    # Use hardcoded values when discovery fails
    pass
```

#### 2. X-QMAuth Header Tests
```python
def test_xqmauth_calculation():
    """Test X-QMAuth header calculation."""
    # Verify HMAC-SHA256 calculation
    # Verify time-based component
    # Verify header format: v1:01da27b0:<hmac>
    pass

def test_xqmauth_time_window():
    """Test X-QMAuth changes every 100 seconds."""
    # Verify different times produce different values
    # Verify same 100-sec window produces same value
    pass
```

#### 3. Multi-Token Architecture Tests
```python
async def test_three_token_exchange():
    """Test complete 3-token exchange flow."""
    # Mock authorization code exchange → IDK token
    # Mock IDK token → Brand token
    # Mock ID token → MBB token (initial)
    # Mock MBB refresh → final vwToken
    # Verify all tokens stored separately
    pass

async def test_token_type_selection():
    """Test correct token used for each API type."""
    # API Level 0 endpoints use MBB token
    # API Level 1 endpoints use IDK token
    # GraphQL uses Brand token
    pass

async def test_hierarchical_token_refresh():
    """Test token refresh dependencies."""
    # Refresh MBB token
    # Refresh IDK token (requires X-QMAuth)
    # Refresh Brand token (requires new IDK token)
    pass
```

#### 4. MBB Client Registration Tests
```python
async def test_mbb_client_registration():
    """Test MBB OAuth client registration."""
    # Mock POST /mbbcoauth/mobile/register/v1
    # Verify request body format
    # Verify xclientId stored
    # Verify xclientId used in subsequent requests
    pass

async def test_mbb_client_reuse():
    """Test MBB client ID reused across sessions."""
    # Register once, store xclientId
    # Reuse in future sessions
    # Re-register only if invalid
    pass
```

#### 5. Immediate Refresh Pattern Tests
```python
async def test_immediate_mbb_refresh():
    """Test immediate refresh after MBB token grant."""
    # Mock initial MBB token grant
    # Verify immediate refresh call
    # Verify second token used for APIs
    pass
```

#### 6. PKCE Conditional Tests
```python
def test_pkce_disabled_for_na():
    """Test PKCE not used for NA region per 2026 traffic."""
    # NA region: no code_challenge/code_verifier
    # EMEA region: PKCE may be used
    pass
```

#### 7. Regional OAuth Flow Tests
```python
async def test_na_identity_endpoint():
    """Test NA uses separate identity endpoint."""
    # Verify identity.na.vwgroup.io for auth
    # Verify base API for token exchange
    pass

async def test_na_redirect_uri():
    """Test NA uses HTTPS callback redirect."""
    # Verify HTTPS callback URI (not custom scheme)
    pass

async def test_na_minimal_scope():
    """Test NA uses minimal scope."""
    # Verify scope is "openid email" (not full profile)
    pass
```

---

## Implementation Recommendations

### Phase 1: Foundation (Essential)
1. **Add X-QMAuth calculation** - Critical for token exchange
2. **Implement 3-token architecture** - Required for API compatibility
3. **Add MBB client registration** - Required for MBB OAuth
4. **Implement immediate refresh pattern** - Match official app behavior

### Phase 2: Discovery (Important)
5. **Add market configuration discovery** - Future-proof client IDs
6. **Dynamic endpoint detection** - Handle API changes
7. **Proper regional OAuth config** - NA/EMEA differences

### Phase 3: Refinement (Nice to have)
8. **Hierarchical token refresh** - Better session management
9. **PKCE conditional logic** - Region-specific security
10. **Comprehensive error handling** - Token hierarchy failures

---

## Backward Compatibility Considerations

### Breaking Changes Required

The new authentication flow is **fundamentally incompatible** with the current implementation:

1. **Token storage format changes** - Need 3 token types + xclientId
2. **API call patterns change** - Different tokens for different endpoints
3. **Login flow changes** - Multi-step exchange instead of single exchange
4. **Refresh logic changes** - Hierarchical refresh instead of simple refresh

### Migration Strategy

**Option A: Clean Break (Recommended)**
- Implement new auth flow in parallel
- Deprecate old flow with clear migration guide
- Major version bump (e.g., 2.0.0 → 3.0.0)

**Option B: Gradual Migration**
- Auto-detect old vs new token format
- Try new flow, fallback to old if it fails
- Log warnings when using old flow
- Remove old flow in future version

---

## Testing Strategy

### Unit Tests
- ✅ X-QMAuth calculation
- ✅ PKCE generation (conditional)
- ✅ Token type selection
- ✅ MBB client registration
- ✅ Multi-token storage

### Integration Tests
- ✅ Complete 3-token exchange flow (mocked)
- ✅ Token refresh sequence (mocked)
- ✅ Market configuration discovery (mocked)
- ✅ Regional endpoint differences (mocked)

### Manual/Live Tests
- ⚠️ Real NA credentials against real endpoints
- ⚠️ Token expiry and refresh
- ⚠️ Error handling (expired tokens, invalid credentials)
- ⚠️ Rate limiting behavior

---

## Security Implications

### Current Implementation
- Simple OAuth2 flow
- Basic token management
- PKCE supported but may not be required

### New Implementation
- **X-QMAuth secret hardcoded** - Same across all VW Group apps (security by obscurity)
- **Three token types** - Larger attack surface if any token leaks
- **MBB client registration** - Each session has unique client ID (good)
- **PKCE optional** - NA doesn't use it (less secure but matches official app)
- **Long-lived refresh tokens** - 60-day validity (convenience vs security tradeoff)

### Recommendations
- Store all tokens securely (encrypted at rest if persisted)
- Clear tokens on logout
- Implement token rotation
- Monitor for token theft/replay attacks
- Consider PKCE for EMEA even if NA doesn't use it

---

## Estimated Effort

### Code Changes
- **New files**: 2-3 (token manager, MBB client, market discovery)
- **Modified files**: 5-7 (vw_connection.py, vw_const.py, exceptions, utilities)
- **Lines of code**: ~800-1000 new, ~300-500 modified

### Testing
- **New unit tests**: 15-20
- **Modified unit tests**: 10-15
- **Integration tests**: 5-10
- **Manual testing**: 2-3 days with real credentials

### Documentation
- **API documentation updates**: 3-4 files
- **Migration guide**: 1 comprehensive document
- **Examples**: 2-3 updated examples

### Timeline Estimate
- **Phase 1 (Foundation)**: 1-2 weeks
- **Phase 2 (Discovery)**: 1 week
- **Phase 3 (Refinement)**: 1 week
- **Testing & Documentation**: 1 week
- **Total**: 4-5 weeks for complete implementation

---

## Open Questions

1. **Does EMEA also use the 3-token architecture?**
   - Analysis is from Audi (EMEA brand)
   - Likely yes, but needs confirmation for VW brand

2. **Are hardcoded endpoints still correct for 2026?**
   - Analysis shows `b-h-s.spr.us00.p.con-veh.net` working in 2026
   - May change in future

3. **Is X-QMAuth required for all regions?**
   - Analysis shows it for token exchange
   - May be optional in some cases

4. **What happens if market config discovery fails?**
   - Fallback to hardcoded values?
   - Fail authentication?
   - Needs decision

5. **Should we implement GraphQL API support?**
   - Analysis shows Brand token used for GraphQL
   - Different from current REST API approach
   - Future enhancement?

---

## Conclusion

The Audi Connect analysis reveals that the **current volkswagencarnet implementation is significantly simplified** compared to the actual VW Group authentication architecture. To properly support North America region (and potentially improve EMEA support), the library needs:

### Must Implement
1. ✅ Three-token architecture (IDK → Brand → MBB)
2. ✅ X-QMAuth header calculation
3. ✅ MBB OAuth client registration
4. ✅ Immediate token refresh pattern

### Should Implement
5. ✅ Market configuration discovery
6. ✅ Hierarchical token refresh
7. ✅ Regional OAuth flow differences

### Nice to Have
8. ⚠️ GraphQL API support
9. ⚠️ Advanced error recovery
10. ⚠️ Token rotation strategies

**Risk**: Without these changes, the NA region implementation may:
- Fail to authenticate
- Have limited API functionality
- Break when VW updates endpoints/credentials
- Not match official app behavior

**Recommendation**: Prioritize Phase 1 (Foundation) changes for NA support, then gradually implement Phase 2 and 3 enhancements.
