# Architecture

**Analysis Date:** 2026-03-10

## Pattern Overview

**Overall:** Layered async library with regional bifurcation

**Key Characteristics:**
- All I/O is async via `aiohttp` — no synchronous blocking calls in the core library
- Regional code paths (EMEA vs. NA) diverge at `Connection._login()` and `Vehicle.update()`, not at individual method level
- Vehicle state is held entirely in-memory in `Vehicle._states` dict and refreshed by polling — no local persistence
- Token management is dual-track: EMEA uses a single IDK access_token; NA uses a three-token registry (`idk`, `brand`, `mbb`) plus per-VIN vehicle session tokens
- Home Assistant integration layer (`vw_dashboard.py`) is strictly read-only over the Vehicle abstraction — it never calls the API directly

## Layers

**Configuration / Constants Layer:**
- Purpose: Provides all static configuration: API endpoints, OAuth credentials, HTTP headers, service names, status parameter hex codes, and path helpers
- Location: `volkswagencarnet/vw_const.py`
- Contains: `REGION_CONFIGS`, `Services`, `Paths`, `VehicleStatusParameter`, `VWDeviceClass`, `VWStateClass`, enum-like classes, `get_region_from_country()`, `get_region_config()`
- Depends on: nothing (pure constants)
- Used by: `Connection`, `Vehicle`, `Dashboard`

**Connection / Transport Layer:**
- Purpose: OAuth2 authentication (EMEA + NA PKCE flows), token lifecycle management, HTTP request routing with retry/rate-limit logic, vehicle list fetching, command dispatch to API
- Location: `volkswagencarnet/vw_connection.py`
- Contains: `Connection` class (3,298 lines) — auth flows, `_request()`, `get()`/`post()`/`put()` wrappers, all `set*` and NA write command methods (`lock_na`, `start_charging_na`, etc.), token refresh methods
- Depends on: `vw_const`, `vw_exceptions`, `vw_utilities`, `vw_vehicle`, `aiohttp`, `bs4`, `jwt`
- Used by: consumer applications, `Vehicle` (via `self._connection` back-reference), Home Assistant integration

**Vehicle State Layer:**
- Purpose: Represents a single vehicle's state; discovers available services; fetches and caches telemetry; exposes Python properties for every vehicle attribute; dispatches control commands via `Connection`
- Location: `volkswagencarnet/vw_vehicle.py`
- Contains: `Vehicle` class (4,227 lines) — `discover()`, `update()`, `_update_na_vehicle()`, ~200 `@property` definitions, `set_charger()`, `set_climatisation()`, etc.
- Depends on: `vw_const`, `vw_utilities`, `aiohttp.ClientTimeout`; `Connection` via `TYPE_CHECKING` import only
- Used by: `Connection` (creates instances, populates `self._vehicles`), `Dashboard`

**Integration / Presentation Layer:**
- Purpose: Home Assistant entity adapter — maps Vehicle properties to HA-compatible entity objects (sensors, binary sensors, switches, climate, tracker, lock)
- Location: `volkswagencarnet/vw_dashboard.py`
- Contains: `Instrument` base class + ~25 concrete subclasses (`BinarySensor`, `Sensor`, `Switch`, `Climate`, `Tracker`, `Lock`), `dashboard()` factory function
- Depends on: `vw_const`, `vw_utilities`, `vw_vehicle`
- Used by: Home Assistant custom integration consuming this library

**Utilities Layer:**
- Purpose: Shared low-level helpers
- Location: `volkswagencarnet/vw_utilities.py`
- Contains: `find_path()` (dot-notation dict/list traversal), `is_valid_path()`, `json_loads()` with datetime parsing, `camel2slug()`, `make_url()`, `redact()` (safe credential logging)
- Depends on: nothing (stdlib only)
- Used by: `Connection`, `Vehicle`, `Dashboard`

**Exceptions Layer:**
- Purpose: Typed error hierarchy so callers can handle specific failure modes
- Location: `volkswagencarnet/vw_exceptions.py`
- Contains: `VWError` (base), `AuthenticationError`, `APIError`, `SPINError`, `RedirectError`, `RequestError`, `TermsAndConditionsError`
- Depends on: nothing
- Used by: `Connection`, `Vehicle`

## Data Flow

**EMEA Login Flow:**

1. Caller invokes `Connection.doLogin()`
2. `_login()` routes to EMEA path: fetch OpenID config → `get_authorization_page()` → `extract_state_token()` → `post_form()` with credentials → `follow_redirects()` → extract auth code
3. `_exchange_code_for_tokens()` POSTs to token endpoint; access/id tokens stored in `self._session_tokens["identity"]`
4. `Connection._session_headers["Authorization"]` set to `Bearer {access_token}`
5. `doLogin()` fetches `GET /vehicle/v2/vehicles` → creates `Vehicle` instances for each VIN
6. `update()` called: triggers `Vehicle.update()` for each vehicle in parallel via `asyncio.gather()`

**NA Login Flow:**

1. Caller invokes `Connection.doLogin(country="US")`
2. `_login()` routes to `_login_na()`: generates PKCE verifier/challenge → fetches OpenID config (hardcoded endpoints) → `_get_authorization_code_na()` — two-step IdentiKit form POST (email then password)
3. Auth code exchanged at `b-h-s.spr.us00.p.con-veh.net/oidc/v1/token` with `code_verifier` (PKCE, no secret)
4. IDK tokens stored in `self._na_tokens["idk"]` and mirrored to `self._session_tokens["identity"]`
5. Attempts Brand and MBB token acquisition (falls back to `idk_only` auth level if these fail)
6. Garage endpoint `GET /account/v1/garage?idToken={id_token}` fetches VINs + vehicle metadata (tspProvider, vehicleId)
7. `Vehicle` instances created; `update()` → `_update_na_vehicle()` per vehicle

**EMEA Vehicle Data Refresh:**

1. `Vehicle.update()` → `discover()` once (fetches `/vehicle/v1/vehicles/{vin}/capabilities`)
2. `asyncio.gather()` fires `get_selectivestatus()`, `get_vehicle()`, `get_parkingposition()`, trip stats in parallel
3. `Connection.getSelectiveStatus()` calls `GET /vehicle/v1/vehicles/{vin}/selectivestatus?services=...`
4. Response JSON merged into `Vehicle._states` dict
5. Vehicle properties read from `_states` via `find_path()` using `Paths.*` dot-notation strings

**NA Vehicle Data Refresh:**

1. `Vehicle._update_na_vehicle()` calls `Connection._get_na_vehicle_data(vin)`
2. `_create_na_vehicle_session(vin)` obtains/caches a `carnetVehicleToken` (JWT) — SPIN challenge/response if configured
3. Five parallel RVS/EV endpoints fetched: `rvs/v1/location/vehicle/{id}`, `rvs/v1/vehicle/{id}`, `ev/v1/vehicle/{id}/charge/summary`, `ev/v1/vehicle/{id}/pretripclimate/settings`, `remotetripstats/v1/vehicle/{id}`
4. Results stored as `Vehicle._states["na_location"]`, `["na_status"]`, `["na_ev"]`, `["na_climate"]`, `["na_trip"]`
5. RVS data cached in `Connection._na_rvs_cache[vin]` with TTL (`rvs_cache_ttl`, default 30s)

**Command Dispatch (e.g., lock):**

1. Caller invokes `Vehicle.set_lock(action)` (e.g., via HA)
2. EMEA: checks SPIN state → `Connection.setLock(vin, action)` → `POST /vehicle/v1/vehicles/{vin}/access/{action}` → returns request ID
3. `Vehicle._handle_response()` stores request ID in `self._requests["lock"]`
4. `wait_for_request()` polls `GET /vehicle/v1/vehicles/{vin}/pendingrequests` until state != "In Progress"
5. NA: `Connection.lock_na(vin, action)` → `_na_write_request()` → `PUT /lockunlock/v1/vehicle/{vehicleId}` — returns bool directly (no polling)

**State Management:**

- `Vehicle._states`: flat dict keyed by service name (EMEA) or `"na_*"` keys (NA). All properties read from this dict via `find_path(self.attrs, Paths.SOME_PATH)` dot-notation traversal
- `Vehicle._requests`: tracks in-flight command status per topic (`lock`, `charging`, `climatisation`, `departuretimer`, `batterycharge`, `refresh`)
- `Vehicle._services`: capability registry — `{"service_name": {"active": bool, ...}}` — populated by `discover()`
- `Connection._na_tokens`: NA token registry — `{"idk": {...}, "brand": {...}, "mbb": {...}, "{vin}": {"vehicle_session": {...}, "tsp_provider": "ATC", "vehicle_id": "uuid"}}`
- `Connection._service_status`: endpoint health map `{"discovery": "Success", "throttled": False, ...}`

## Key Abstractions

**`Connection`:**
- Purpose: Session management, auth, all API communication
- Examples: `volkswagencarnet/vw_connection.py` — `Connection.doLogin()`, `Connection.update()`, `Connection._request()`
- Pattern: All public API-fetching methods (`get*`, `set*`) call internal `get()`/`post()`/`put()` which call `_request()` — single HTTP chokepoint with unified retry logic

**`Vehicle`:**
- Purpose: Per-vehicle state container with property-per-attribute interface
- Examples: `volkswagencarnet/vw_vehicle.py` — every attribute has a `@property`, an `is_{attr}_supported` guard, and often a `{attr}_last_updated` timestamp property
- Pattern: Properties first check for NA-specific state keys (`self._states.get("na_ev")`), fall back to EMEA path (dot-notation via `find_path`). This dual-check pattern is used throughout for regional compatibility

**`Instrument` / `Dashboard`:**
- Purpose: HA entity factory — maps Vehicle attributes to typed HA entities
- Examples: `volkswagencarnet/vw_dashboard.py` — `Sensor`, `BinarySensor`, `Switch`, `Climate`, `Lock`, `Tracker` subclasses
- Pattern: Each `Instrument` subclass implements `is_supported` (delegates to `vehicle.is_{attr}_supported`) and `state` property (delegates to `vehicle.{attr}`)

**`Services` / `Paths` / `VehicleStatusParameter`:**
- Purpose: Typed string namespaces that eliminate magic strings throughout the codebase
- Examples: `volkswagencarnet/vw_const.py` — `Services.CHARGING = "charging"`, `Paths.CHARGING_STATE = "charging.chargingStatus.value.chargingState"`
- Pattern: All `find_path()` calls use `Paths.*` constants; all service capability lookups use `Services.*` constants

## Entry Points

**`Connection.__init__()`:**
- Location: `volkswagencarnet/vw_connection.py:85`
- Triggers: Direct instantiation by caller or Home Assistant integration
- Responsibilities: Detects region from country code, loads region config, initializes token registries and session state, creates `asyncio.Lock` for login serialization

**`Connection.doLogin()`:**
- Location: `volkswagencarnet/vw_connection.py:331`
- Triggers: Caller invokes after instantiation
- Responsibilities: Runs full OAuth2 flow, fetches vehicle list, triggers initial `update()`

**`Connection.update()`:**
- Location: `volkswagencarnet/vw_connection.py:2551`
- Triggers: Periodic polling by HA or consumer app
- Responsibilities: Validates/refreshes tokens, then calls `Vehicle.update()` for all vehicles in parallel

**`Vehicle.update()`:**
- Location: `volkswagencarnet/vw_vehicle.py:304`
- Triggers: `Connection.update()` via `asyncio.gather()`
- Responsibilities: Calls `discover()` on first run, then routes to EMEA or NA data fetching

**`dashboard()` factory:**
- Location: `volkswagencarnet/vw_dashboard.py` (bottom of file)
- Triggers: Home Assistant integration on platform setup
- Responsibilities: Returns all `Instrument` instances that are supported for a given vehicle

## Error Handling

**Strategy:** Exception-based with typed errors. The `_request()` method is the primary error boundary. Higher-level `get()`/`post()`/`put()` wrap `ClientResponseError` and return structured dicts (`{"status_code": N}`) rather than re-raising for expected API errors (4xx/5xx from service unavailability). Auth failures propagate as `AuthenticationError`.

**Patterns:**
- `Connection._request()`: handles 401 (inline token refresh + retry), 429 (exponential backoff up to `MAX_RETRIES_ON_RATE_LIMIT=3`), raises `ClientResponseError` for other status codes
- `Connection.get()/post()/put()`: translate HTTP errors to log messages + structured dict returns; 401 sets `self._session_logged_in = False`
- `Vehicle._handle_response()`: for command responses — logs error, raises `Exception` on falsy response; stores request state on success
- NA write commands (`_na_write_request()`): 401 → invalidate vehicle session + retry once; 429 → exponential backoff; other non-2xx → log and return `False`
- Broad `except Exception` used in most data-fetch methods to ensure one vehicle failure doesn't break others — logs warning and returns `False`/`None`

## Cross-Cutting Concerns

**Logging:** `logging.getLogger(__name__)` in every module. Token/credential values always pass through `redact()` before logging. NA endpoints log VINs as `redact(vin)`. Log levels: DEBUG for flow tracing, INFO for significant state changes (login success, token refresh), WARNING for degraded-but-recoverable conditions, ERROR for unrecoverable failures.

**Validation:** Domain allowlist (`VW_DOMAIN_ALLOWLIST`) applied to all discovery-sourced URLs before use. SPIN has a minimum 3 remaining-tries check before any SPIN-protected operation.

**Authentication:** All API calls require `Authorization: Bearer {token}` header, set in `Connection._session_headers`. NA write commands use vehicle-scoped tokens (`carnetVehicleToken`) rather than the IDK access token. Token validity checked via `validate_tokens()` before every update cycle and before write commands.

**Concurrency:** `Connection._login_lock` (asyncio.Lock) prevents concurrent login + token-refresh races. `asyncio.gather()` used for parallel vehicle updates and parallel multi-service fetches. The `_home_region_discovered` bool on `Vehicle` acts as an optimistic lock for home region discovery.

---

*Architecture analysis: 2026-03-10*
