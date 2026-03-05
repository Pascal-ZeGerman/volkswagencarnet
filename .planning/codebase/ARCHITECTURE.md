# Architecture

**Analysis Date:** 2026-02-10

## Pattern Overview

**Overall:** Async client-server integration library with layered architecture (Connection → Vehicle → Dashboard)

**Key Characteristics:**
- Async-first design using `aiohttp` for all I/O operations
- Multi-region support (EMEA, North America) with region-specific configurations
- Service discovery pattern for vehicle capabilities
- Token-based OAuth2 authentication with automatic refresh
- Home Assistant integration support through Dashboard layer

## Layers

**Connection Layer (`vw_connection.py`):**
- Purpose: OAuth2 authentication, token management, session handling, and high-level API request routing
- Location: `volkswagencarnet/vw_connection.py` (1373 lines)
- Contains: Authentication flow, HTTP methods (get/post/put), token validation, vehicle operations
- Depends on: `aiohttp`, `BeautifulSoup`, `jwt`, region configs (`vw_const.py`)
- Used by: Application code directly; also used internally by Vehicle layer
- Key responsibilities:
  - OAuth2 login flow with region-specific credentials
  - Automatic token refresh before expiry
  - Session state management with cookie jar
  - HTTP request abstraction with automatic retries (max 3 on rate limit 429)
  - Vehicle list discovery and initialization

**Vehicle Layer (`vw_vehicle.py`):**
- Purpose: Represents individual vehicle state and provides control methods
- Location: `volkswagencarnet/vw_vehicle.py` (3760 lines)
- Contains: Vehicle properties, service discovery, control operations (charging, climatisation, locking)
- Depends on: Connection layer, constants (`vw_const.py`), utilities
- Used by: Connection layer (update cycle), Dashboard layer (entity generation)
- Key responsibilities:
  - Lazy discovery of available services per vehicle via `/capabilities` endpoint
  - Caching of vehicle state and request status
  - Vehicle control operations (start/stop charging, set temperature, lock/unlock)
  - Request tracking with timestamp and in-progress detection
  - Service status validation with expiration dates

**Dashboard/Integration Layer (`vw_dashboard.py`):**
- Purpose: Home Assistant integration and entity management
- Location: `volkswagencarnet/vw_dashboard.py` (2874 lines)
- Contains: Instrument base class, sensor implementations, switch implementations, climate controls
- Depends on: Vehicle layer, constants
- Used by: Home Assistant custom integrations
- Key responsibilities:
  - Provide Instrument base class for entity abstraction
  - Dynamically create entities based on vehicle capabilities
  - Handle attribute mapping and state retrieval
  - Support mutable (writable) and immutable (read-only) entities

**Constants & Configuration Layer (`vw_const.py`):**
- Purpose: Centralized configuration, constants, and region-specific settings
- Location: `volkswagencarnet/vw_const.py` (486 lines)
- Contains: API endpoints, OAuth credentials, region configs, service IDs, device classes
- Depends on: None
- Used by: All layers
- Key responsibilities:
  - Region configuration mapping (EMEA, North America)
  - OAuth client IDs and endpoints per region
  - HTTP headers for authentication and requests
  - Service identifier constants
  - Vehicle status parameter definitions

**Utilities Layer (`vw_utilities.py`):**
- Purpose: Shared helper functions for JSON parsing, path navigation, formatting
- Location: `volkswagencarnet/vw_utilities.py` (163 lines)
- Contains: JSON deserialization with datetime parsing, dict/list path navigation, slug formatting
- Depends on: None
- Used by: All layers

**Exception Layer (`vw_exceptions.py`):**
- Purpose: Custom exception hierarchy for error handling
- Location: `volkswagencarnet/vw_exceptions.py` (43 lines)
- Contains: 6 exception types (VWError base, AuthenticationError, APIError, SPINError, RedirectError, RequestError)
- Depends on: None
- Used by: All layers for error handling

## Data Flow

**Login Flow:**

1. Client calls `Connection.doLogin()`
2. Connection discovers endpoints if NA region (tests multiple candidates)
3. Connection retrieves OpenID configuration from identity provider
4. Connection requests authorization page (login form) from OAuth provider
5. Connection extracts state token from HTML response
6. Connection POSTs credentials with state token to authentication endpoint
7. Connection follows redirects and extracts authorization code
8. Connection exchanges authorization code for access/refresh tokens
9. Connection fetches vehicle list from `/vehicle/v2/vehicles`
10. Connection creates Vehicle objects for each VIN
11. Connection calls `update()` to fetch initial vehicle data
12. Returns logged-in status

**Update Cycle Flow:**

1. Connection calls `update()`
2. For each Vehicle, calls `vehicle.update()` in parallel via `asyncio.gather()`
3. Vehicle checks if discovery needed, calls `discover()` if not yet done
4. Vehicle discovery calls Connection.getOperationList() to fetch capabilities
5. Vehicle enables/disables services based on response
6. Vehicle fetches selective status for enabled services
7. Vehicle fetches specific data (parking, trips, etc.) based on enabled services
8. Vehicle caches state in `_states` dict
9. Each state update timestamps recorded in `_requests` dict

**Service Control Flow (e.g., charging):**

1. Application calls `vehicle.set_charger(action)`
2. Vehicle checks `_in_progress()` to prevent concurrent requests
3. Vehicle constructs request payload with action parameter
4. Vehicle calls Connection.setCharging() via POST to API endpoint
5. Connection returns response with request ID
6. Vehicle stores request ID in `_requests[topic]`
7. Vehicle calls `wait_for_request()` to poll for completion
8. Vehicle polls `/requests/{id}` endpoint with exponential backoff
9. Vehicle returns success/failure status

**State Management:**

- **Vehicle State Cache:** `Vehicle._states` dict stores all vehicle properties (battery level, door locks, etc.)
- **Request Tracking:** `Vehicle._requests` dict tracks pending operations with timestamp and status
- **Token Management:** Connection validates tokens before expiry and automatically refreshes
- **Service Status:** Connection tracks per-VIN endpoint health in `_service_status` dict (Up/Down/Unauthorized/Throttled)

## Key Abstractions

**Connection:**
- Purpose: Abstracts HTTP communication, authentication, and OAuth2 flow
- Examples: `vw_connection.py` class
- Pattern: Singleton per session with async lock for login serialization

**Vehicle:**
- Purpose: Abstracts individual vehicle as entity with state and control operations
- Examples: `vw_vehicle.py` class with methods like `set_charger()`, `set_climatisation()`, `set_lock()`
- Pattern: One instance per vehicle VIN, created and cached by Connection

**Instrument:**
- Purpose: Abstracts a single Home Assistant entity (sensor, switch, climate device)
- Examples: All classes in `vw_dashboard.py` (Climatisation, ChargingState, DoorLock, etc.)
- Pattern: Base class with subclasses for different entity types; created dynamically per vehicle capability

**Service:**
- Purpose: Represents API capability available for a vehicle
- Examples: `Services.CHARGING`, `Services.CLIMATISATION`, `Services.ACCESS`
- Pattern: Service IDs tied to specific API endpoints; enabled/disabled per vehicle based on capabilities

## Entry Points

**Connection Initialization:**
- Location: `volkwagencarnet/__init__.py`
- Triggers: Application code instantiating `Connection(session, username, password, country)`
- Responsibilities: Setup session state, region detection, initial configuration

**doLogin():**
- Location: `vw_connection.py` line 166
- Triggers: Application calling login after creating Connection
- Responsibilities: Complete OAuth2 flow, vehicle discovery, initial data fetch

**update():**
- Location: `vw_connection.py` line 737
- Triggers: Periodic refresh (default 5-minute interval), called at end of login
- Responsibilities: Refresh data for all vehicles in parallel

**get_attr():**
- Location: `vw_vehicle.py` line 846
- Triggers: Dashboard/application accessing vehicle properties
- Responsibilities: Return cached state value or None if attribute not supported

## Error Handling

**Strategy:** Exceptions are raised for authentication/API failures; specific error types allow caller to respond appropriately

**Patterns:**

- **Authentication Errors:** `AuthenticationError` raised on login failure, T&C requirement, invalid credentials
- **API Errors:** `APIError` raised for general API failures (4xx/5xx responses)
- **Rate Limiting:** Returns `{"state": "Throttled"}` response state rather than raising; automatic retries (3 attempts with exponential backoff)
- **Security PIN:** `SPINError` raised when SPIN validation fails or attempts exhausted
- **Redirects:** `RedirectError` raised for unexpected OAuth redirect issues
- **Request Errors:** `RequestError` raised for HTTP request execution failures

**Token Expiry:** Caught silently in `validate_tokens()`; triggers `refresh_tokens()` automatically

**Missing Services:** Handled gracefully with 404/502 responses for unsupported endpoints; service marked as inactive

## Cross-Cutting Concerns

**Logging:** Uses `logging` module with module-level logger `_LOGGER`. Debug logs for OAuth flow, Info logs for major events (login success, service discovery), Warning logs for throttling/failures

**Validation:**
- OAuth state token extracted from HTML login page
- Token structure validated using `jwt.decode()` with RS256 algorithm
- SPIN validation required before lock/unlock/honk operations
- Service expiration dates checked before operations

**Authentication:**
- OAuth2 authorization code flow with region-specific client IDs
- Separate identity endpoint for North America (`identity.na.vwgroup.io`)
- PKCE support available but not used by official app (configurable)
- Automatic token refresh when tokens expire within update interval

**Region Detection:** Automatic from `country` parameter (US/CA→NA, others→EMEA)

**Rate Limiting:** HTTP 429 responses trigger exponential backoff retry (max 3 attempts)

---

*Architecture analysis: 2026-02-10*
