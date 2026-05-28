# External Integrations

**Analysis Date:** 2026-03-10

## APIs & External Services

**VW Group EMEA API (Cariad BFF):**
- Service: Volkswagen WeConnect EMEA backend
  - Base URL: `https://emea.bff.cariad.digital`
  - Vehicle list: `GET /vehicle/v2/vehicles`
  - Vehicle capabilities: `GET /vehicle/v1/vehicles/{vin}/capabilities`
  - Vehicle status: `GET /vehicle/v1/vehicles/{vin}/selectivestatus` (POST with service list)
  - Parking position: `GET /vehicle/v1/parking/vehicles/{vin}/parkingposition`
  - Trip statistics: `GET /vehicle/v1/trips/vehicles/{vin}/trips`
  - Honk & flash: `POST /vehicle/v1/vehicles/{vin}/honkAndFlash`
  - Lock/unlock: `POST /vehicle/v1/vehicles/{vin}/access/lock`
  - Charging control: `POST /vehicle/v1/vehicles/{vin}/charging/...`
  - Climatisation control: `POST /vehicle/v1/vehicles/{vin}/climatisation/...`
  - Home region: `https://msg.volkswagen.de`
  - SDK/Client: `aiohttp` (direct HTTP, no SDK)
  - Auth: Bearer IDK token in `Authorization` header

**VW Group North America API (Car-Net):**
- Service: Volkswagen Car-Net North America backend
  - Base URL: `https://b-h-s.spr.us00.p.con-veh.net` (hardcoded, confirmed 2026)
  - Vehicle garage: `GET /account/v1/garage?idToken={idk_id_token}`
  - Vehicle data: `GET /vehicle/v1/vehicles/{vin}/selectivestatus` (returns 404 for many services — NA uses different paths)
  - OIDC config: `GET /oidc/v1/.well-known/openid-configuration`
  - JWKS: `GET /oidc/v1/jwks`
  - SDK/Client: `aiohttp` (direct HTTP, no SDK)
  - Auth: IDK token passed as `idToken` query param and Bearer header

**VW Vehicle Media API (EMEA):**
- Service: Vehicle images and media
  - Base URL: `https://emea.bff.cariad.digital/media/v2/`
  - Vehicle images: `GET /vehicle-images/{vin}?resolution=3x`
  - Note: Not yet implemented in code (TODO comment in `volkswagencarnet/vw_vehicle.py` line 22)

## Authentication & Identity

**EMEA Identity Provider:**
- Service: VW Group Identity (OpenID Connect)
  - Endpoint: `https://identity.vwgroup.io`
  - OAuth flow: Authorization Code (standard, no PKCE)
  - Client ID: `a24fba63-34b3-4d43-b181-942111e6bda8@apps_vw-dilab_com` (defined in `volkswagencarnet/vw_const.py`)
  - Scope: `openid profile badge cars dealers vin`
  - Redirect URI: `weconnect://authenticated`
  - Token exchange: IDK token → Brand token → MBB token (3-step chain)
  - MBB OAuth base: `https://mbboauth-1d.prd.ece.vwg-connect.com/mbbcoauth`
  - Implementation: `volkswagencarnet/vw_connection.py` methods `_login_emea()`, `_login()`

**North America Identity Provider:**
- Service: VW Group NA Identity (OpenID Connect with PKCE)
  - Authorization endpoint: `https://b-h-s.spr.us00.p.con-veh.net/oidc/v1/authorize` (proxies to identity.na.vwgroup.io)
  - Token endpoint: `https://b-h-s.spr.us00.p.con-veh.net/oidc/v1/token`
  - Identity/form base: `https://identity.na.vwgroup.io`
  - Client ID: `59992128-69a9-42c3-8621-7942041ba824_MYVW_ANDROID` (confirmed from APK 2026)
  - PKCE: Required — `code_verifier` replaces `client_secret`
  - Scope: `openid`
  - Redirect URI: `kombi:///login` (custom URI scheme)
  - Token refresh requires original `code_verifier` (non-standard NA AZS extension)
  - Implementation: `volkswagencarnet/vw_connection.py` methods `_login_na()`, `_refresh_idk_token()`

**Token Management:**
- JWT validation: `pyjwt` library with `RS256` algorithm
- JWKS fetched from identity provider for signature verification
- Token types: IDK (identity), Brand, MBB (Mobile Backend Bus)
- Stored in-memory: `Connection._session_tokens` dict
- Refresh threshold: tokens refreshed before expiry based on `interval` setting
- Implementation: `volkswagencarnet/vw_connection.py` `validate_tokens()`, `_refresh_idk_token()`

**X-QMAuth HMAC Authentication:**
- Some EMEA endpoints require `X-QMAuth` header
- HMAC-SHA256 with shared secret (`XQMAUTH_SECRET` in `volkswagencarnet/vw_const.py`)
- Prefix: `v1:01da27b0:`
- NA endpoints: do NOT use X-QMAuth (causes HTTP 400 on NA token refresh)

## Data Storage

**Databases:**
- None — this is a stateless client library

**File Storage:**
- None — all state is in-memory

**Caching:**
- In-memory only:
  - `Connection._service_status` dict tracks per-endpoint health (up/down/throttled)
  - `Connection._na_rvs_cache` dict for per-VIN RVS data (TTL configurable via `rvs_cache_ttl`, default 30s)
  - `Vehicle._states` dict holds latest polled vehicle data
  - `Vehicle._requests` dict tracks in-progress operations

## Monitoring & Observability

**Error Tracking:**
- None — no external error tracking service

**Logs:**
- Python standard `logging` module throughout
- Logger: `logging.getLogger(__name__)` in each module
- Credentials redacted in logs via `volkswagencarnet/vw_utilities.py` `redact()` function
- Log levels: DEBUG for API calls/responses, INFO for login success, WARNING for throttling/discovery failures, ERROR for login failures

## CI/CD & Deployment

**Hosting:**
- PyPI — distributed as `volkswagencarnet` Python package

**CI Pipeline:**
- Not detected (no GitHub Actions workflows, no `.circleci/`, no `Jenkinsfile`)
- Pre-commit hooks enforce code quality locally

## Environment Configuration

**Required environment variables:**
- None — library uses constructor parameters only
- Credentials: `username`, `password` passed to `Connection()` at instantiation
- Optional `country` parameter selects region (`US`/`CA` → NA, others → EMEA)
- Optional `spin` parameter for security PIN operations

**Secrets location:**
- `testing_creds.env` at project root (manual testing only, not used by library)
- `tests/credentials.py.sample` — sample test credentials template
- `.secrets.baseline` — detect-secrets baseline for pre-commit hook

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- `on_xclient_id` callback: optional callable passed to `Connection()`, invoked when a new `X-Client-Id` is registered during EMEA login
  - Allows callers (e.g., Home Assistant) to persist the generated client ID across restarts

## Rate Limiting

**VW API rate limiting:**
- HTTP 429 responses handled with retry logic (up to `MAX_RETRIES_ON_RATE_LIMIT = 3` retries)
- Exponential backoff between retries
- `Connection._is_throttled` flag set during throttle period
- Returns `{"state": "Throttled"}` response when rate limited
- Implementation: `volkswagencarnet/vw_connection.py` `_request()` method

## Domain Allowlist

All redirect and discovery URLs are validated against `VW_DOMAIN_ALLOWLIST` in `vw_connection.py`:
- `.vwgroup.io` — identity providers
- `.con-veh.net` — NA base API
- `.cariad.digital` — EMEA/NA BFF APIs
- `.vwg-connect.com` — MBB OAuth
- `.volkswagen.de` — EMEA home region
- `.volkswagen.com`, `.vw.com`, `.vw.us` — NA home region candidates

---

*Integration audit: 2026-03-10*
