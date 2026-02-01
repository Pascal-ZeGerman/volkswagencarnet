# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Python library for communicating with Volkswagen Connect (WeConnect) services. It provides an async API for retrieving vehicle data and controlling vehicle features like climatisation, charging, and locking.

**Regional Support**: This library supports both **EMEA** (Europe, Middle East, Africa) and **North America** regions. The region is auto-detected from the `country` parameter:
- `country='US'` or `country='CA'` → North America
- `country='DE'` or other EU countries → EMEA (default)
- No country parameter → EMEA (backward compatible)

For North America, the library will automatically discover the correct API endpoints during the first login.

## Development Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-test.txt

# Install pre-commit hooks (recommended)
pre-commit install
```

### Testing
```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=volkswagencarnet --cov-report=html

# Run specific test file
pytest tests/vw_connection_test.py

# Run specific test
pytest tests/vw_vehicle_test.py::TestVehicle::test_specific_method
```

### Code Quality
```bash
# Format code with ruff
ruff format .

# Check formatting without changes
ruff format --diff

# Run pre-commit checks manually
pre-commit run --all-files
```

### Building
```bash
# Build package
python -m build --outdir dist/

# Validate package
python -m twine check dist/*

# Check version from setuptools_scm
python -m setuptools_scm --strip-dev
```

## Usage Examples

### EMEA Region (Default)
```python
from volkswagencarnet.vw_connection import Connection
from aiohttp import ClientSession

async with ClientSession() as session:
    # Defaults to EMEA
    connection = Connection(session, username, password)
    # Or explicitly:
    connection = Connection(session, username, password, country="DE")

    if await connection.doLogin():
        for vehicle in connection.vehicles:
            print(f"VIN: {vehicle.vin}")
```

### North America Region
```python
from volkswagencarnet.vw_connection import Connection
from aiohttp import ClientSession

async with ClientSession() as session:
    # Auto-detects NA region and discovers endpoints
    connection = Connection(session, username, password, country="US")

    if await connection.doLogin():
        print(f"Discovered endpoint: {connection._base_api}")
        for vehicle in connection.vehicles:
            print(f"VIN: {vehicle.vin}")
```

## Architecture

### Core Components

**Connection (`vw_connection.py`)**
- Main entry point for interacting with VW API
- Handles OAuth2 authentication flow with VW Identity service
- Manages session state, token refresh, and API requests
- Implements rate limiting and retry logic
- Key methods:
  - `doLogin()`: Performs full OAuth2 login flow
  - `update()`: Updates all vehicles in parallel
  - `get()`, `post()`, `put()`: HTTP methods with automatic token validation
  - `validate_tokens()`: Checks token expiry and refreshes if needed

**Vehicle (`vw_vehicle.py`)**
- Represents a single vehicle and its state
- Lazy discovery of available API endpoints per vehicle
- Caches vehicle data and request states
- Services are discovered dynamically based on vehicle capabilities
- Methods for controlling vehicle features (charging, climatisation, locking)

**Dashboard (`vw_dashboard.py`)**
- Integration layer for Home Assistant
- Provides `Instrument` base class for entities (sensors, switches, etc.)
- Each instrument represents a specific vehicle attribute
- Instruments are dynamically created based on vehicle capabilities

**Constants (`vw_const.py`)**
- API endpoints and configuration
- OAuth2 client credentials
- HTTP headers for authentication and API requests
- Vehicle status parameter hex codes
- Service identifiers

### Authentication Flow

The library uses OAuth2 with authorization code flow:
1. Get OpenID configuration from VW API
2. Request authorization page (login form)
3. Extract state token from login page HTML
4. POST credentials with state token
5. Follow redirects to extract authorization code
6. Exchange authorization code for access/refresh tokens
7. Tokens are validated and refreshed automatically before expiry

**Regional OAuth Differences:**
- **EMEA (EU)**: Standard OAuth2 authorization code flow
- **North America (US/CA)**: OAuth2 + PKCE (Proof Key for Code Exchange, RFC 7636)
  - Generates `code_verifier` (random 43-char string)
  - Generates `code_challenge` (SHA256 hash of verifier, base64url encoded)
  - Includes `code_challenge` and `code_challenge_method=S256` in authorization request
  - Sends `code_verifier` in token exchange to prove request origin

### API Structure

- **EMEA**: `https://emea.bff.cariad.digital`
- **North America**: Auto-discovered (tries multiple endpoint candidates)
- Home region configured per region (DE: `https://msg.volkswagen.de`)
- Default country: `DE` (Germany), configurable via `country` parameter
- Authentication uses Identity service with JWT tokens
- All API calls require Bearer token in Authorization header
- Vehicle capabilities are discovered per VIN
- Services are enabled/disabled based on vehicle hardware and subscription

**Region Detection**: The library automatically detects the region from the `country` parameter. US and Canadian users should pass `country='US'` or `country='CA'` to enable North America region support.

**Region-Specific Configuration** (`vw_const.py`):
- Each region has its own `client_id` for OAuth authentication
- EMEA Client ID: `a24fba63-34b3-4d43-b181-942111e6bda8@apps_vw-dilab_com`
- NA Client ID: `2dae49f6-830b-4180-9af9-59dd0d060916@apps_vw-dilab_com` (from 2021 iOS app)
- NA endpoint discovery tries 6 candidates in priority order (legacy first, then modern CARIAD endpoints)
- `"legal entity is missing or invalid"` error = missing PKCE or wrong/outdated client_id

### Service Discovery

Each vehicle has different capabilities based on its model and subscription. The library:
1. Calls `/vehicle/v1/vehicles/{vin}/capabilities` to get available services
2. Stores enabled services in `Vehicle._services`
3. Only requests data from enabled endpoints
4. Handles gracefully when services return 404/502 for unsupported features

### Async Design

- All I/O operations are async using `aiohttp`
- Multiple vehicles updated in parallel using `asyncio.gather()`
- Connection uses a shared `ClientSession` passed at initialization
- Login has a lock to prevent concurrent authentication

## Testing

### Test Structure
- Unit tests use fixtures in `tests/fixtures/`
- Mock server in `tests/fixtures/mock_server.py` for integration tests
- Connection fixture in `tests/fixtures/connection.py` provides test connection
- Response fixtures in `tests/fixtures/resources/responses/` contain sample API responses

### Running Single Tests
```bash
# Test specific vehicle functionality
pytest tests/vw_vehicle_test.py -v

# Test connection/authentication
pytest tests/vw_connection_test.py -v

# Test region support (US/NA functionality)
pytest tests/region_support_test.py -v

# Test utilities
pytest tests/vw_utilities_test.py -v
```

## Configuration

### Setup.cfg
- Python 3.11+ required
- Code style: max line length 120, ignores E722
- Coverage configured to omit tests and version.py

### Pre-commit Hooks
The project uses pre-commit hooks that run automatically before commits:
- JSON/YAML/TOML validation
- No direct commits to main/master branches
- Trailing whitespace removal
- pyupgrade for Python 3.7+ syntax
- mypy type checking

### Versioning
Uses `setuptools_scm` for automatic versioning from git tags. Version written to `volkswagencarnet/version.py`.

## Important Notes

### Updating US Credentials
If US authentication fails with current credentials:
- OAuth credentials may be outdated (last confirmed: 2021)
- Use network traffic analysis to capture current credentials from official VW Car-Net app
- See `docs/US_NETWORK_TRAFFIC_ANALYSIS.md` for detailed capture guide using mitmproxy/Charles Proxy
- Extract current `client_id`, endpoints, and OAuth parameters from captured traffic

### Rate Limiting
The VW API implements rate limiting (HTTP 429). The library:
- Retries up to 3 times with exponential backoff
- Returns `{"state": "Throttled"}` when rate limited
- Logs warnings about throttling

### Token Management
- Tokens are validated before each update cycle
- Refresh occurs if tokens expire within the next update interval
- Failed token refresh triggers full re-login
- Identity tokens have different expiry than access tokens

### Error Handling
Custom exceptions in `vw_exceptions.py`:
- `AuthenticationError`: Login/token issues
- `APIError`: General API failures
- `SPINError`: Security PIN validation failures
- `RedirectError`: OAuth redirect flow issues
- `TermsAndConditionsError`: User must accept T&C on VW portal
- `RequestError`: HTTP request failures

### Security PIN (SPIN)
Some operations (lock/unlock, honk & flash) require a security PIN:
- SPIN state is checked before operations to prevent lockout
- Minimum 3 remaining attempts required
- SPIN is hashed with challenge using SHA-512

### Service Status Tracking
Connection tracks API endpoint health in `_service_status`:
- Up (200, 204, 207)
- Unauthorized (401)
- Forbidden (403)
- Rate limited (429)
- Down (other errors)
