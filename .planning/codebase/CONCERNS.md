# Codebase Concerns

**Analysis Date:** 2026-02-10

## Tech Debt

**Untouched Energy Flow Properties:**
- Issue: Three properties marked with `# TODO untouched` in vehicle state handling
- Files: `volkswagencarnet/vw_vehicle.py` (lines 1541, 1554, 1566)
- Impact: `energy_flow`, `energy_flow_last_updated`, and `is_energy_flow_supported` properties lack validation and may return incomplete/unprocessed data structures
- Fix approach: Validate data extraction patterns, ensure proper timestamp handling, add unit tests for these properties

**Incomplete API Image Support:**
- Issue: TODO comment indicates vehicle image endpoint exists but implementation incomplete
- Files: `volkswagencarnet/vw_vehicle.py` (lines 16-20)
- Impact: Image retrieval functionality not implemented despite API availability
- Fix approach: Implement vehicle image fetching from `/media/v2/vehicle-images/{vin}` endpoint if needed, or remove TODO

**Missing Model Year Data:**
- Issue: Model year appears unavailable via standard API, only through web API with separate authentication
- Files: `volkswagencarnet/vw_vehicle.py` (line 20)
- Impact: Cannot provide complete vehicle specifications
- Fix approach: Document as limitation or implement separate web scraping if critical

## Error Handling & Resilience

**Overly Broad Exception Handling:**
- Issue: 20+ instances of `except Exception` without specific exception type catching
- Files: `volkswagencarnet/vw_connection.py` (lines 154, 302, 558, 633, 659, 776, 801, 827, 844, 874, 896, 918, 940, 955, 995, 1027, 1039, 1052, 1065, 1078)
- Impact: Masks specific errors (network timeouts, authentication failures, malformed responses), makes debugging difficult
- Fix approach: Catch specific exceptions (aiohttp.ClientError, json.JSONDecodeError, KeyError, etc.) with targeted handling for each error type

**Generic Error Response Masking:**
- Issue: Operations that fail return opaque `{"error": "unknown"}` dictionary
- Files: `volkswagencarnet/vw_connection.py` (line 803 in `getOperationList`)
- Impact: Callers cannot distinguish between API failures, missing endpoints, and validation errors
- Fix approach: Extend error objects to include HTTP status codes and original exception details

**Protected Access to Cookie Jar:**
- Issue: Direct access to `_session._cookie_jar._cookies` (protected member)
- Files: `volkswagencarnet/vw_connection.py` (line 101)
- Impact: Breaks encapsulation; breaks if aiohttp changes internal structure (upgrade risk)
- Fix approach: Use aiohttp public API or store cookie state separately

## Security Considerations

**Credentials in Memory:**
- Risk: Username and password stored as plaintext instance variables for duration of session
- Files: `volkswagencarnet/vw_connection.py` (lines 79-80)
- Current mitigation: Session typically short-lived; credentials not logged
- Recommendations:
  - Consider clearing credentials after login once tokens obtained
  - Document that users should use unique passwords or app-specific credentials
  - Add explicit warnings in docstrings about credential handling

**Region-Specific Client ID & Hardcoded Credentials:**
- Risk: OAuth client IDs are hardcoded and tied to specific regions, enabling potential tracking or manipulation
- Files: `volkswagencarnet/vw_const.py` (lines 8-9, 42, 47)
- Current mitigation: Client IDs are public (extracted from app traffic)
- Recommendations:
  - Document that client IDs are app-derived, not sensitive secrets
  - Monitor for changes in official app client IDs (requires periodic network traffic analysis)
  - Consider adding version detection for credential freshness

**OAuth Flow Dependency on External Discovery:**
- Risk: North America region requires endpoint discovery; misconfiguration could route authentication to wrong server
- Files: `volkswagencarnet/vw_connection.py` (lines 130-163), `vw_const.py` (lines 52-65)
- Current mitigation: Multiple candidate endpoints tested; error messages guide users
- Recommendations:
  - Implement certificate pinning for OAuth identity endpoint
  - Log all tested endpoints and their results for debugging
  - Document expected endpoints in configuration comments

**Header Mutation During Auth:**
- Risk: Headers are mutated (`.pop()`) during authentication flow; could cause side effects if headers reused
- Files: `volkswagencarnet/vw_connection.py` (lines 193, 234-235, 580)
- Current mitigation: Headers copied at connection init
- Recommendations: Use `.get()` with defaults instead of `.pop()` to avoid mutation

## Performance Bottlenecks

**Synchronous Vehicle Discovery:**
- Problem: Vehicles discovered sequentially during login before parallel updates can begin
- Files: `volkswagencarnet/vw_vehicle.py` (lines 137-198)
- Cause: Each vehicle calls `discover()` in first `update()` call, blocking other vehicle updates
- Improvement path: Batch discovery across all vehicles or parallelize discovery during login phase

**N+1 API Calls During Update:**
- Problem: Each vehicle must call `/vehicle/v1/vehicles/{vin}/capabilities` before requesting status
- Files: `volkswagencarnet/vw_vehicle.py` (line 142), `vw_connection.py` (lines 784-804)
- Cause: Capabilities cached only per vehicle, rediscovered if cache expires
- Improvement path: Cache capabilities at connection level with longer TTL (24+ hours), implement cache invalidation on service changes

**No Request De-duplication:**
- Problem: Multiple concurrent calls to same endpoint not deduplicated
- Files: `volkswagencarnet/vw_vehicle.py` (line 205-242)
- Cause: Each service status call is independent request
- Improvement path: Implement request-level caching or batch endpoint support

**Large Dashboard File:**
- Problem: `vw_dashboard.py` is 2,874 lines with 436 class/function definitions
- Files: `volkswagencarnet/vw_dashboard.py`
- Cause: Single file contains all Home Assistant integration code
- Improvement path: Split into service modules (climatisation.py, charging.py, access.py, etc.)

## Fragile Areas

**Request Status Tracking Without Atomic Updates:**
- Files: `volkswagencarnet/vw_vehicle.py` (lines 55-63, 85-97, 119-132)
- Why fragile: `_requests` dictionary updated in multiple places without locks; race conditions possible if multiple coroutines update same topic simultaneously
- Safe modification: Add asyncio locks per topic or refactor to use immutable request state
- Test coverage: No tests for concurrent request updates on same vehicle

**State Mutation in Discover Process:**
- Files: `volkswagencarnet/vw_vehicle.py` (lines 158-196)
- Why fragile: Services dictionary updated item-by-item in loop; if exception occurs mid-loop, vehicle left in partial state
- Safe modification: Build new service state dictionary, apply atomically, or wrap entire loop in try-except
- Test coverage: Tests don't verify partial failure scenarios

**Token Validation Race Condition:**
- Files: `volkswagencarnet/vw_connection.py` (lines 744-756)
- Why fragile: Token validated, then multiple vehicles updated in parallel; token could expire between validation and update calls
- Safe modification: Implement token refresh retry within each vehicle update, not just at connection level
- Test coverage: No tests for concurrent updates with token expiry

**Header State Mutations:**
- Files: `volkswagencarnet/vw_connection.py` (lines 193, 234-235)
- Why fragile: Shared `_session_headers` and `_session_auth_headers` popped during requests; if concurrent requests access same header, one will see modified state
- Safe modification: Create header copies per request instead of mutating shared state
- Test coverage: No concurrency tests for multiple simultaneous requests

## Dependencies at Risk

**Pinned Dependencies Missing:**
- Risk: No version constraints on core dependencies (aiohttp, BeautifulSoup4, PyJWT)
- Files: `requirements.txt`, `setup.cfg`
- Impact: Breaking changes in minor/patch versions could break library silently
- Migration plan:
  - Add minimum version constraints: `aiohttp>=3.8.0`, `beautifulsoup4>=4.9.0`, `pyjwt>=2.0.0`
  - Lock to major versions: `aiohttp<4.0`, `beautifulsoup4<5.0`
  - Test against new versions before releases

**BeautifulSoup4 HTML Parsing Fragility:**
- Risk: Relies on parsing HTML from OAuth provider; layout changes break login
- Files: `volkswagencarnet/vw_connection.py` (lines 308-313, 329-345)
- Impact: Login fails if VW identity provider redesigns login form HTML
- Mitigation: Implement fallback parsing strategies, add integration tests against real OAuth endpoint (if possible), monitor for HTML structure changes

**lxml Dependency Indirect:**
- Risk: Only needed as BeautifulSoup parser; explicit dependency but could be replaced
- Files: `setup.cfg` line 19
- Impact: Additional system dependency (C compiler for installation)
- Recommendation: Document that lxml can be replaced with html.parser if needed

## Test Coverage Gaps

**No Async Concurrency Tests:**
- What's not tested: Multiple vehicles updating simultaneously, concurrent token refreshes, race conditions in request tracking
- Files: `tests/vw_connection_test.py`, `tests/vw_vehicle_test.py`
- Risk: Concurrency bugs in production not detected
- Priority: High - affects main update loop

**No OAuth Redirect Flow Tests:**
- What's not tested: Full authorization code flow, state token extraction, error handling in login redirects
- Files: No comprehensive OAuth tests
- Risk: Authentication failures not caught until user attempts login
- Priority: High - authentication is critical path

**No Region-Specific Endpoint Tests:**
- What's not tested: NA region endpoint discovery, region-specific OAuth parameters, client ID selection
- Files: `tests/region_support_test.py` (239 lines, basic coverage only)
- Risk: North America authentication could fail silently
- Priority: High - essential for NA users

**Dashboard Instrument Tests Missing:**
- What's not tested: Individual instrument state transformations, data binding, error handling for missing data
- Files: `volkswagencarnet/vw_dashboard.py` (2,874 lines) with minimal test coverage
- Risk: Home Assistant integration breaks with API changes undetected
- Priority: Medium

**Rate Limiting Retry Logic Undertested:**
- What's not tested: Multiple retries with backoff, MAX_RETRIES_ON_RATE_LIMIT boundary conditions
- Files: `tests/vw_connection_test.py` (lines 59-97, single test case)
- Risk: Throttling behavior could cause cascading failures
- Priority: Medium

## Scaling Limits

**No Connection Pooling for Multiple Accounts:**
- Current capacity: Single aiohttp.ClientSession per Connection instance
- Limit: Using library in multi-account scenarios requires separate session per account
- Scaling path: Implement optional shared session pool with per-account credential isolation, respect rate limiting across accounts

**Vehicle Update Parallelism Unbounded:**
- Current capacity: All vehicle updates triggered simultaneously via `asyncio.gather()`
- Limit: Large account (50+ vehicles) could cause connection pool exhaustion or rate limiting
- Scaling path: Implement semaphore-based concurrency limit (e.g., max 5 concurrent vehicle updates), progressive backoff per vehicle

**Service Discovery Cache No Expiration:**
- Current capacity: Capabilities cached for lifetime of Vehicle object
- Limit: Service changes (new subscriptions, feature updates) not reflected until restart
- Scaling path: Implement TTL-based cache with configurable expiration (default 24 hours), manual cache invalidation method

**API Response Buffering:**
- Current capacity: Full response bodies read into memory
- Limit: Very large responses (error logs, diagnostic data) could consume significant memory
- Scaling path: Implement streaming responses for large endpoints, set max response size limits

## Missing Critical Features

**PKCE Implementation Incomplete:**
- Problem: PKCE code generation implemented but not used (per CLAUDE.md, official app doesn't use it)
- Impact: Code prepared for future OAuth security improvements but disabled
- Blocks: Standards-compliant OAuth implementations that require PKCE
- Recommendation: Document PKCE support status, consider enforcing PKCE for security-conscious deployments

**No Offline Mode/Local Cache:**
- Problem: All vehicle data fetched fresh on each update; no local caching mechanism
- Impact: Frequent updates cause excessive API calls; no access if connectivity lost
- Blocks: Building responsive UI without API dependency
- Recommendation: Implement optional local cache with timestamp tracking, staleness indicators

**Limited Error Recovery:**
- Problem: Most API failures trigger full re-login rather than granular retry
- Impact: Transient network errors cause unnecessary authentication overhead
- Blocks: Building resilient integrations
- Recommendation: Implement granular retry strategies (exponential backoff, circuit breakers) per endpoint

**No Support for Multiple Authentication Methods:**
- Problem: Only password-based OAuth authentication supported
- Impact: Cannot use biometric/multi-factor authentication if enabled on account
- Blocks: Using library with accounts requiring MFA
- Recommendation: Document MFA limitations, implement token import/export for pre-authenticated sessions

---

*Concerns audit: 2026-02-10*
