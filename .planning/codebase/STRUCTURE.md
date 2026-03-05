# Codebase Structure

**Analysis Date:** 2026-02-10

## Directory Layout

```
volkswagencarnet/
├── volkswagencarnet/              # Main package source code
│   ├── __init__.py                # Package entry point (minimal, re-exports)
│   ├── vw_connection.py           # Connection class - OAuth2, HTTP, session management
│   ├── vw_vehicle.py              # Vehicle class - vehicle state and control operations
│   ├── vw_dashboard.py            # Home Assistant integration - Instrument classes
│   ├── vw_const.py                # Constants, region configs, service IDs, device classes
│   ├── vw_utilities.py            # Helper functions - JSON, path navigation, formatting
│   ├── vw_exceptions.py           # Custom exception classes
│   └── version.py                 # Auto-generated version from setuptools_scm
├── tests/                         # Test suite
│   ├── __init__.py                # Empty test package marker
│   ├── conftest.py                # pytest configuration, loads connection fixture
│   ├── vw_connection_test.py      # Tests for Connection class
│   ├── vw_vehicle_test.py         # Tests for Vehicle class
│   ├── vw_utilities_test.py       # Tests for utility functions
│   ├── region_support_test.py     # Tests for EMEA/NA region detection
│   ├── integration_test.py        # Integration tests
│   ├── dummy_test.py              # Placeholder test
│   └── fixtures/                  # Test fixtures and mocks
│       ├── __init__.py            # Empty marker
│       ├── connection.py          # Connection fixture for tests
│       ├── constants.py           # Test constants (resource path)
│       ├── mock_server.py         # Mock API server for testing
│       └── resources/             # Test data and fixtures
│           ├── dummy_cookies.pickle  # Pre-authenticated cookies for tests
│           └── responses/         # Sample API responses per vehicle type
│               ├── arteon_2023_diesel/
│               ├── egolf/
│               ├── eup_electric/
│               └── golf_gte_hybrid/
├── docs/                          # Documentation
│   └── plans/                     # Planning documents
├── .planning/                     # GSD planning directory
│   └── codebase/                  # Architecture/structure analysis documents
├── .github/                       # GitHub configuration
│   └── workflows/                 # CI/CD workflows
├── setup.cfg                      # Python package metadata, pytest config
├── pyproject.toml                 # Build system config, version generation
├── requirements.txt               # Runtime dependencies (minimal)
├── requirements-test.txt          # Test dependencies
├── CLAUDE.md                      # Claude Code instructions (this project)
├── README.md                      # Project documentation
└── .pre-commit-config.yaml        # Pre-commit hooks configuration
```

## Directory Purposes

**volkswagencarnet/:**
- Purpose: Main library package
- Contains: Core classes and modules
- Key files: vw_connection.py (1373 lines), vw_vehicle.py (3760 lines), vw_dashboard.py (2874 lines)

**tests/:**
- Purpose: Unit, integration, and property-based tests
- Contains: pytest test cases, fixtures, mock data
- Key files: conftest.py (test configuration), vw_connection_test.py, vw_vehicle_test.py

**tests/fixtures/:**
- Purpose: Shared test infrastructure
- Contains: Pytest fixtures, mock server, pre-recorded API responses
- Key files: connection.py (connection fixture), mock_server.py (mock API)

**tests/fixtures/resources/responses/:**
- Purpose: Sample API responses for different vehicle models
- Contains: JSON response files per vehicle type for testing without live API
- Key files: Directory per vehicle (arteon_2023_diesel, egolf, eup_electric, golf_gte_hybrid)

**docs/:**
- Purpose: Project documentation
- Contains: Planning documents, guides
- Key files: docs/plans/ contains phase planning documents

**.planning/codebase/:**
- Purpose: GSD codebase mapping documents
- Contains: Architecture, structure, conventions, testing patterns analysis
- Key files: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md, STACK.md, INTEGRATIONS.md

## Key File Locations

**Entry Points:**

- `volkswagencarnet/__init__.py`: Package namespace exports (empty/minimal)
- `tests/conftest.py`: pytest configuration and fixture discovery

**Configuration:**

- `setup.cfg`: Package metadata, build config, coverage settings, pytest config
- `pyproject.toml`: Build system requirements, setuptools_scm for versioning
- `.pre-commit-config.yaml`: Pre-commit hook definitions

**Core Logic:**

- `volkwagencarnet/vw_connection.py`: OAuth2 authentication, HTTP requests, token management
- `volkwagencarnet/vw_vehicle.py`: Vehicle state, service discovery, control operations
- `volkwagencarnet/vw_dashboard.py`: Home Assistant integration, entity classes

**Supporting:**

- `volkwagencarnet/vw_const.py`: Region configs, OAuth credentials, service IDs
- `volkwagencarnet/vw_utilities.py`: JSON parsing, path navigation helpers
- `volkwagencarnet/vw_exceptions.py`: Custom exception types

**Testing:**

- `tests/fixtures/connection.py`: Async session and connection fixtures
- `tests/fixtures/mock_server.py`: Mock HTTP server for testing
- `tests/fixtures/resources/`: Pre-recorded API responses

## Naming Conventions

**Files:**

- `vw_*.py`: Volkswagen-specific modules (vw_connection, vw_vehicle, vw_const, etc.)
- `*_test.py`: Test files (pytest discovers these automatically)
- `conftest.py`: pytest configuration file (special name)
- `*_fixture.py` or in `fixtures/`: Pytest fixtures

**Directories:**

- `tests/fixtures/resources/responses/{vehicle_type}/`: One directory per test vehicle model
- `.planning/codebase/`: GSD-specific planning documents
- `.github/workflows/`: GitHub Actions CI/CD workflows

**Classes:**

- `PascalCase` for all classes (Connection, Vehicle, Instrument, etc.)
- Base classes use descriptive names (Vehicle, Instrument, VWError)
- Subclasses follow pattern: `{Feature}{ComponentType}` (e.g., Climatisation, ChargingState)

**Functions/Methods:**

- `snake_case` for all functions and methods
- Async methods prefixed with `async def` (no naming convention distinction)
- Private methods start with `_` (e.g., `_login()`, `_discover_endpoints()`)
- Property accessors use `@property` decorator (e.g., `vin`, `unique_id`, `deactivated`)

**Constants:**

- `UPPER_SNAKE_CASE` for module-level constants (BASE_API, CLIENT_ID, etc.)
- Class-level enums like `Services.CHARGING`, `Services.CLIMATISATION`

**Variables:**

- `snake_case` for all variables
- Private instance variables use `_prefix` (e.g., `_session`, `_vehicles`, `_services`)
- Protected variables in inheritance hierarchy use `_prefix`

## Where to Add New Code

**New Feature (e.g., new control operation):**

- Primary code: `volkwagencarnet/vw_vehicle.py` (add method like `set_feature()`)
  - Call existing Connection methods to perform HTTP operations
  - Follow pattern: check `_in_progress()`, construct payload, call Connection, track request, wait for completion
  - Handle response status and timestamps

- Connection layer support: `volkwagencarnet/vw_connection.py` (add HTTP method like `setFeature()`)
  - Wrap HTTP request to vehicle endpoint
  - Handle retries and throttling automatically via `_request()` method
  - Return parsed JSON response

- Constants: `volkwagencarnet/vw_const.py`
  - Add service ID to `Services` class if new API capability
  - Add operation IDs to relevant service definitions

- Tests: `tests/vw_vehicle_test.py` or `tests/vw_connection_test.py`
  - Use fixtures from `tests/fixtures/connection.py`
  - Use pytest async test pattern with `@pytest.mark.asyncio` decorator

**New Component/Module:**

- Implementation: Create new file `volkwagencarnet/vw_{module_name}.py`
- Imports: Follow existing pattern (imports from vw_const, vw_utilities, vw_exceptions)
- Logging: Add module logger: `_LOGGER = logging.getLogger(__name__)`
- Tests: Create corresponding `tests/vw_{module_name}_test.py`

**New Home Assistant Entity Type:**

- Implementation: Add class to `volkwagencarnet/vw_dashboard.py` inheriting from `Instrument`
- Follow pattern: Set `is_mutable`, `icon`, `entity_type`, `device_class` properties
- Implement `configurate()` if setup needed, `state` property for current value
- Add `async def set_state()` method if mutable

**Utilities (shared helpers):**

- Shared helpers: `volkwagencarnet/vw_utilities.py`
- Path navigation: Use existing `find_path()` function
- JSON parsing: Use `json_loads()` for automatic datetime conversion
- Slug formatting: Use `camel2slug()` for converting camelCase to slug

## Special Directories

**tests/fixtures/resources/responses/:**
- Purpose: Pre-recorded API responses for different vehicle models
- Generated: No, manually curated or captured from real API
- Committed: Yes, committed to repository
- Usage: Mock server uses these responses in tests to avoid live API calls
- One subdirectory per vehicle type (arteon_2023_diesel, egolf, eup_electric, golf_gte_hybrid)

**venv/ and .venv/:**
- Purpose: Python virtual environment for development
- Generated: Yes, created with `python3 -m venv venv`
- Committed: No (listed in .gitignore)
- Usage: Activate with `source venv/bin/activate` before running tests/development commands

**.planning/codebase/:**
- Purpose: GSD-generated codebase analysis documents
- Generated: Yes, by `/gsd:map-codebase` command
- Committed: Yes, committed to repository for reference
- Files: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md, STACK.md, INTEGRATIONS.md

---

*Structure analysis: 2026-02-10*
