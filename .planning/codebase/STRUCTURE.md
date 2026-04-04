# Codebase Structure

**Analysis Date:** 2026-03-10

## Directory Layout

```
volkswagencarnet/          # repo root
├── volkswagencarnet/      # Python package (importable library)
│   ├── __init__.py        # Namespace init — NullHandler only
│   ├── vw_connection.py   # Connection class (auth, HTTP, commands)
│   ├── vw_vehicle.py      # Vehicle class (state, properties, control)
│   ├── vw_dashboard.py    # Home Assistant integration layer
│   ├── vw_const.py        # Constants, region configs, typed namespaces
│   ├── vw_exceptions.py   # Custom exception hierarchy
│   └── vw_utilities.py    # Shared utility functions
├── tests/                 # All test code
│   ├── conftest.py        # pytest configuration (asyncio mode)
│   ├── fixtures/          # Test infrastructure
│   │   ├── connection.py  # Test connection fixture factory
│   │   ├── constants.py   # Test constants
│   │   ├── mock_server.py # aiohttp mock server for unit tests
│   │   └── resources/     # Response fixtures (JSON files per vehicle/service)
│   │       └── responses/
│   │           ├── arteon_2023_diesel/
│   │           ├── egolf/
│   │           ├── eup_electric/
│   │           ├── golf_gte_hybrid/
│   │           └── na_vehicle/
│   ├── fixtures/responses/ # Additional response fixtures
│   │   ├── capabilities/  # Capabilities endpoint responses
│   │   └── login/         # OAuth flow HTML/response fixtures
│   ├── e2e/               # Live end-to-end tests (requires VW credentials)
│   │   ├── conftest.py    # E2E fixtures (real Connection instance)
│   │   ├── test_na_login.py
│   │   ├── test_na_token_refresh.py
│   │   ├── test_na_vehicle_data.py
│   │   ├── test_na_ev_data.py
│   │   ├── test_na_lock_status.py
│   │   ├── test_na_position.py
│   │   └── test_na_write_commands.py
│   ├── vw_connection_test.py   # Connection unit tests (~3000 lines)
│   ├── vw_vehicle_test.py      # Vehicle unit tests (~4500 lines)
│   ├── vw_dashboard_test.py    # Dashboard unit tests
│   ├── vw_utilities_test.py    # Utility function tests
│   ├── region_support_test.py  # Regional detection and config tests
│   ├── reliability_test.py     # Retry/rate-limit/error-handling tests
│   ├── code_quality_test.py    # Static assertions (naming patterns, etc.)
│   └── emea_regression_test.py # EMEA backward compatibility tests
├── examples/              # Usage example scripts
├── docs/                  # Documentation
│   └── plans/             # Historical design documents
├── .planning/             # GSD workflow planning (not committed)
│   └── codebase/          # Codebase analysis documents
├── .github/
│   └── workflows/         # CI/CD workflow definitions
├── setup.cfg              # Package metadata, test config, mypy settings
├── pyproject.toml         # Build backend config (setuptools_scm)
├── requirements.txt       # Runtime dependencies
├── requirements-test.txt  # Test dependencies
├── .pre-commit-config.yaml
└── CLAUDE.md              # Project-level AI instructions
```

## Directory Purposes

**`volkswagencarnet/` (package):**
- Purpose: The importable Python library — all production code lives here
- Contains: 6 modules, ~11,000 lines total
- Key files: `vw_connection.py` (3,298 lines), `vw_vehicle.py` (4,227 lines), `vw_dashboard.py` (2,874 lines)
- Note: `vw_dashboard.py` is the largest file but has a simple repetitive structure (one class per HA entity type)

**`tests/`:**
- Purpose: All automated tests — unit, integration, and end-to-end
- Contains: Unit test files mirror source module names (`vw_connection_test.py`, `vw_vehicle_test.py`, etc.)
- Important: e2e tests in `tests/e2e/` require `VW_TEST_USERNAME` and `VW_TEST_PASSWORD` env vars and hit live VW servers — never run in CI without credentials

**`tests/fixtures/`:**
- Purpose: Test infrastructure and JSON response fixtures for mock server
- Key files: `tests/fixtures/mock_server.py` provides the aiohttp mock server; `tests/fixtures/connection.py` provides a pre-authenticated `Connection` fixture
- JSON fixtures in `tests/fixtures/resources/responses/{vehicle_type}/` contain full API response payloads for different vehicle configurations (diesel, electric, hybrid, NA)

**`tests/e2e/`:**
- Purpose: Live integration tests validating actual VW API behavior
- Contains: Tests organized by feature area (login, token refresh, vehicle data, write commands)
- Run command: `venv/bin/python -m pytest tests/e2e/ -v`

**`.planning/codebase/`:**
- Purpose: GSD codebase analysis documents
- Generated: Yes (by `/gsd:map-codebase`)
- Committed: No (`.planning/` is in `.gitignore`)

## Key File Locations

**Entry Points:**
- `volkswagencarnet/vw_connection.py:82`: `Connection` class definition
- `volkswagencarnet/vw_connection.py:331`: `Connection.doLogin()` — primary entry point for all usage
- `volkswagencarnet/vw_connection.py:2551`: `Connection.update()` — periodic poll entry point
- `volkswagencarnet/vw_dashboard.py` (bottom): `dashboard()` factory for HA integration

**Configuration:**
- `volkswagencarnet/vw_const.py:85`: `REGION_CONFIGS` dict — all per-region OAuth and API endpoint configuration
- `volkswagencarnet/vw_const.py:122`: `COUNTRY_TO_REGION` mapping — region auto-detection
- `volkswagencarnet/vw_const.py:260`: `Services` class — canonical service name strings
- `volkswagencarnet/vw_const.py:293`: `Paths` class — all dot-notation paths into API response JSON
- `setup.cfg`: package metadata, max line length (120), mypy and coverage config

**Core Logic:**
- `volkswagencarnet/vw_connection.py:2109`: `_login_na()` — NA PKCE OAuth flow
- `volkswagencarnet/vw_connection.py:2272`: `_login()` — EMEA OAuth flow
- `volkswagencarnet/vw_connection.py:1321`: `_create_na_vehicle_session()` — NA vehicle token with optional SPIN
- `volkswagencarnet/vw_connection.py:1683`: `_get_na_vehicle_data()` — NA RVS data fetch
- `volkswagencarnet/vw_connection.py:1951`: `_na_write_request()` — NA command dispatch
- `volkswagencarnet/vw_connection.py:2375`: `_request()` — unified HTTP method with retry/rate-limit
- `volkswagencarnet/vw_vehicle.py:214`: `Vehicle.discover()` — capability discovery
- `volkswagencarnet/vw_vehicle.py:304`: `Vehicle.update()` — per-vehicle refresh dispatcher

**Testing:**
- `tests/fixtures/mock_server.py`: aiohttp mock server responding to fixture JSON
- `tests/fixtures/connection.py`: test `Connection` instance with mock session
- `tests/vw_connection_test.py`: connection and auth unit tests
- `tests/vw_vehicle_test.py`: vehicle property and command unit tests

## Naming Conventions

**Files:**
- Source modules: `vw_{domain}.py` prefix (e.g., `vw_connection.py`, `vw_vehicle.py`)
- Test files: `{module_name}_test.py` or `test_{feature}.py` (mixed — legacy uses `_test` suffix, newer e2e uses `test_` prefix)

**Directories:**
- Lowercase snake_case for all directories
- Test fixture directories named after vehicle type (e.g., `arteon_2023_diesel`, `na_vehicle`)

**Classes:**
- PascalCase: `Connection`, `Vehicle`, `Instrument`, `BinarySensor`, `Services`, `Paths`

**Methods:**
- Public async methods: lowercase snake_case (`doLogin`, `getSelectiveStatus` — some older methods use camelCase preserved from original codebase)
- Private methods: `_underscore_prefix` (`_login_na`, `_request`, `_create_na_vehicle_session`)
- NA-specific methods: suffixed with `_na` (`_login_na`, `lock_na`, `start_charging_na`, `_na_write_request`)

**Properties:**
- Vehicle attributes: `snake_case` property name (e.g., `battery_level`, `outside_temperature`)
- Support guards: `is_{attr}_supported` boolean property for every attribute
- Timestamp accessors: `{attr}_last_updated` returning `datetime`

**Constants:**
- Module-level string constants: `UPPER_CASE` (e.g., `BASE_API`, `CLIENT_ID`, `USER_AGENT`)
- Enum-like class attributes: `UPPER_CASE` within class (`Services.CHARGING`, `Paths.BATTERY_SOC`)
- Token registry keys: lowercase with underscores (`"access_token"`, `"expires_at"`, `"vehicle_session"`)

## Where to Add New Code

**New EMEA API endpoint (read-only data):**
- Add `Paths.NEW_PATH = "service.subpath.value.field"` constant to `volkswagencarnet/vw_const.py`
- Add `Services.NEW_SERVICE = "serviceName"` if it's a new service
- Add `Vehicle._services[Services.NEW_SERVICE] = {"active": False}` in `Vehicle.__init__()`
- Add fetching call in `Vehicle.update()` inside the `asyncio.gather()` block
- Add `Vehicle.new_attr` property (read from `find_path(self.attrs, Paths.NEW_PATH)`)
- Add `Vehicle.is_new_attr_supported` property (check `is_valid_path(self.attrs, Paths.NEW_PATH)`)
- Add `Vehicle.new_attr_last_updated` property returning timestamp
- Add `Sensor` or `BinarySensor` in `volkswagencarnet/vw_dashboard.py`

**New NA API endpoint (read-only data):**
- Add fetch call in `Connection._get_na_vehicle_data()` using `_fetch_na_optional_endpoint()` or `_fetch_rvs_endpoint()`
- Store result in returned dict with key `"na_{feature}"`
- Update `Vehicle._update_na_vehicle()` to merge new key into `self._states`
- Add property to `Vehicle` with NA guard: `na_data = self._states.get("na_{feature}"); if na_data: return na_data.get("field")`

**New NA write command:**
- Add method on `Connection` following pattern of `lock_na()` / `honk_and_flash_na()`:
  ```python
  async def new_command_na(self, vin: str) -> bool:
      vehicle_id = self._na_tokens.get(vin, {}).get("vehicle_id", vin)
      url = f"{self._base_api}/endpoint/v1/vehicle/{vehicle_id}/action"
      return await self._na_write_request(vin, url, method="put", body={})
  ```
- Add corresponding `set_new_command()` on `Vehicle` with NA/EMEA dispatch pattern
- Add `Switch` or similar in `vw_dashboard.py`

**New EMEA write command:**
- Add method on `Connection` following `setClimater()` / `setCharging()` pattern (POST to API, parse response ID)
- Add `Vehicle.set_new_command()` calling `Connection.setNewCommand()` then `_handle_response()`

**New utility function:**
- Add to `volkswagencarnet/vw_utilities.py` with docstring and `Examples:` in docstring

**New test for existing feature:**
- Unit tests: add to `tests/vw_vehicle_test.py` or `tests/vw_connection_test.py`
- Uses `tests/fixtures/connection.py` for the `Connection` fixture and `tests/fixtures/mock_server.py` for mocked HTTP

**New test fixture (vehicle model):**
- Add directory under `tests/fixtures/resources/responses/{vehicle_type}/`
- Add JSON files matching the API endpoint response structures

## Special Directories

**`.planning/`:**
- Purpose: GSD workflow files (project state, roadmap, phase plans, analysis)
- Generated: Yes (by GSD commands)
- Committed: No (in `.gitignore`)

**`App-APK/`:**
- Purpose: Holds the myVW Android APK used for traffic analysis and API reverse-engineering
- Generated: No (manually added reference artifact)
- Committed: Yes (binary XAPK file)

**`.trafficanalysis/`:**
- Purpose: Captured HTTP traffic from mitmproxy sessions used for NA API research
- Generated: No (manually captured)
- Committed: Yes

**`.VW_NA_Auth_Analysis/`:**
- Purpose: NA authentication research notes and APK decompilation findings
- Generated: No
- Committed: Yes

**`venv/` and `.venv/`:**
- Purpose: Python virtual environments (two exist — `venv/` is the active one per CLAUDE.md)
- Generated: Yes
- Committed: No (in `.gitignore`)

---

*Structure analysis: 2026-03-10*
