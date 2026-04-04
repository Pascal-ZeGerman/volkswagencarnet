# Testing Patterns

**Analysis Date:** 2026-03-10

## Test Framework

**Runner:**
- pytest >= 7.0.0
- Config: `pyproject.toml` (`[tool.pytest.ini_options]`)
- `asyncio_mode = "strict"` — all async tests must be explicitly marked

**Assertion Library:**
- pytest `assert` statements (not `unittest.TestCase.assert*` where avoidable)
- `unittest.TestCase` subclasses also used via `IsolatedAsyncioTestCase` for async test classes

**Run Commands:**
```bash
# Activate venv first
source venv/bin/activate

# Run all unit tests (e2e excluded)
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=volkswagencarnet --cov-report=html

# Run specific test file
pytest tests/vw_connection_test.py -v

# Run specific test class
pytest tests/vw_vehicle_test.py::VehiclePropertyTest -v

# Run specific test method
pytest tests/vw_vehicle_test.py::VehicleTest::test_init -v

# Run e2e tests (requires VW_TEST_USERNAME + VW_TEST_PASSWORD)
pytest tests/e2e/ -v

# Skip coverage plugin (faster)
pytest -p no:cov
```

## Test File Organization

**Location:** All unit tests co-located in `tests/` directory. E2E tests separated in `tests/e2e/`.

**Discovery rules (from `pyproject.toml`):**
```toml
testpaths = ["tests"]
python_files = ["*_test.py", "test_*.py"]
norecursedirs = ["tests/e2e"]  # e2e excluded from normal runs
```

**Naming:**
- Unit test files: `vw_connection_test.py`, `vw_vehicle_test.py`, `vw_utilities_test.py`, `vw_dashboard_test.py`
- Feature test files: `region_support_test.py`, `reliability_test.py`, `code_quality_test.py`, `emea_regression_test.py`
- E2E test files: `tests/e2e/test_na_login.py`, `tests/e2e/test_na_vehicle_data.py`, etc.

**Structure:**
```
tests/
├── conftest.py                   # Global fixtures: mock_aiohttp, session, connection
├── fixtures/
│   ├── connection.py             # session + connection fixtures
│   ├── constants.py              # resource_path constant
│   ├── mock_server.py            # Aioresponses-based mock server
│   └── resources/
│       └── responses/
│           ├── egolf/            # E-Golf fixture JSON files
│           ├── na_vehicle/       # NA vehicle fixture JSON files
│           ├── arteon_2023_diesel/
│           ├── eup_electric/
│           └── golf_gte_hybrid/
├── vw_connection_test.py         # Connection auth, rate limiting, NA OAuth
├── vw_vehicle_test.py            # Vehicle properties, state management
├── vw_utilities_test.py          # Utility function unit tests
├── vw_dashboard_test.py          # Dashboard/Instrument hierarchy tests
├── region_support_test.py        # Region detection and routing
├── reliability_test.py           # Retry, discovery, home region routing
├── code_quality_test.py          # AST/regex structural code quality checks
├── emea_regression_test.py       # EMEA API contract regression tests
├── integration_test.py           # Live credential tests (skipped without creds)
└── e2e/
    ├── conftest.py               # Module-scoped na_connection + first_vehicle fixtures
    ├── test_na_login.py          # Live NA login + JWT validation
    ├── test_na_token_refresh.py  # Token refresh lifecycle
    ├── test_na_vehicle_data.py   # Vehicle data retrieval
    └── test_na_write_commands.py # Lock, charge, climate write commands
```

## Test Structure

**Two class styles are used side by side:**

**1. `IsolatedAsyncioTestCase` (unittest-style, preferred for async test classes):**
```python
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

class NAOAuthLoginTest(IsolatedAsyncioTestCase):
    """Test NA OAuth login flow."""

    def _make_na_conn(self):
        """Create a Connection with country='US' and mocked session."""
        mock_session = AsyncMock()
        mock_session._cookie_jar = MagicMock()
        mock_session._cookie_jar._cookies = {}
        conn = Connection(mock_session, "user@example.com", "password", country="US")
        return conn

    async def test_na_login_success(self):
        """Test successful NA login via the _login() dispatch chain."""
        conn = self._make_na_conn()
        with (
            patch.object(conn, "get_openid_config", return_value=openid_config),
            patch.object(conn, "_get_authorization_code_na", return_value="auth_code_123"),
            patch.object(conn, "_exchange_code_for_tokens", return_value=token_response),
        ):
            result = await conn._login()
        assert result is True
```

**2. Plain pytest classes (used for synchronous or `@pytest.mark.asyncio`-decorated tests):**
```python
class TestRegionMapping:
    """Test region detection from country codes."""

    def test_us_maps_to_na(self):
        assert get_region_from_country("US") == "NA"

    @pytest.mark.asyncio
    async def test_connection_defaults_to_emea(self):
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password")
            assert conn._session_region == "EMEA"
```

**Parametrized tests (used in `vw_vehicle_test.py`):**
```python
BATTERY_CHARGING_CASES = [
    ("battery_level", (int, type(None))),
    ("charging_state", str),
    ("charging", bool),
]

@pytest.mark.parametrize("prop,expected_type", BATTERY_CHARGING_CASES)
def test_egolf_battery_charging(self, egolf_vehicle, prop, expected_type):
    """Verify battery/charging property returns expected type."""
    value = getattr(egolf_vehicle, prop)
    assert isinstance(value, expected_type)
```

**Subtest pattern (used in `vw_utilities_test.py` for table-driven tests):**
```python
for key, expected in data.items():
    with self.subTest(msg=key, v=key):
        res = camel2slug(key)
        assert expected == res
```

## Mocking

**Frameworks:** `unittest.mock` (`AsyncMock`, `MagicMock`, `patch`, `patch.object`)

**Standard mock session setup — used across all connection tests:**
```python
mock_session = AsyncMock()
mock_session._cookie_jar = MagicMock()
mock_session._cookie_jar._cookies = {}
conn = Connection(mock_session, "user@example.com", "password", country="US")
```

**Patching methods with `patch.object`:**
```python
with patch.object(conn, "_discover_market_config", new_callable=AsyncMock) as mock_discover:
    mock_discover.return_value = False
    result = await conn.doLogin()
    mock_discover.assert_called_once()
```

**Context manager stacking (Python 3.10+ parenthesized style):**
```python
with (
    patch.object(conn, "get_openid_config", return_value=openid_config),
    patch.object(conn, "_get_authorization_code_na", return_value="auth_code_123"),
    patch.object(conn, "_exchange_code_for_tokens", return_value=token_response),
):
    result = await conn._login()
```

**Mock HTTP response context manager pattern (for `conn._session.get`):**
```python
def _make_resp_ctx(status: int, json_data=None, headers=None):
    resp = MagicMock()
    resp.status = status
    resp.headers = headers or {}
    if json_data is not None:
        resp.json = AsyncMock(return_value=json_data)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx, resp

# Usage:
ctx, resp = _make_resp_ctx(200, json_data={"issuer": "..."})
conn._session.get = MagicMock(return_value=ctx)
```

**`aioresponses` (for higher-level HTTP mocking via `mock_aiohttp` fixture):**
```python
# conftest.py provides:
@pytest.fixture
def mock_aiohttp():
    with aioresponses() as m:
        yield m

# Usage in test:
def test_something(mock_aiohttp):
    mock_aiohttp.get("https://api.example.com/endpoint", payload={"key": "value"})
```

**`MagicMock(spec=Vehicle)` for spec-constrained mocks:**
```python
vehicle = MagicMock(spec=Vehicle, name="MockUpdateVehicle")
vehicle.update = lambda: Vehicle.update(vehicle)
vehicle._discovered = False
await vehicle.update()
vehicle.discover.assert_called_once()
assert len(vehicle.method_calls) == 8
```

**What to Mock:**
- `conn._session.get/post` when testing HTTP interaction without running a server
- Specific connection methods (`get_openid_config`, `_login_na`, `_discover_market_config`) to isolate the method under test
- `conn.put`, `conn.get` when testing higher-level methods like `setDepartureTimers`

**What NOT to Mock:**
- `Connection.__init__` — always instantiate real Connection with mock session
- `Vehicle.__init__` — always instantiate real Vehicle; set `_discovered = True` and inject `_states` directly
- Standard library functions (unless testing time-dependent behavior with `freeze_time`)

## Fixtures and Factories

**Global fixtures (`tests/conftest.py`):**
```python
@pytest_asyncio.fixture
async def session():
    """Client session with pre-loaded cookie jar."""
    jar = CookieJar()
    jar.load(os.path.join(resource_path, "dummy_cookies.pickle"))
    sess = ClientSession(headers={"Connection": "keep-alive"}, cookie_jar=jar)
    yield sess
    await sess.close()

@pytest.fixture
def connection(session):
    """Real connection for integration tests (country='DE', EMEA)."""
    return Connection(session=session, username="", password="", country="DE", interval=999)

@pytest.fixture
def mock_aiohttp():
    """aioresponses context manager for mocking aiohttp requests."""
    with aioresponses() as m:
        yield m
```

**Fixture loading helper (used in `vw_vehicle_test.py` and `vw_dashboard_test.py`):**
```python
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "resources" / "responses"

def load_fixture(*parts):
    """Load a JSON fixture file."""
    with open(FIXTURE_DIR.joinpath(*parts)) as f:
        return json.load(f)
```

**Vehicle fixture pattern (pytest fixtures with injected JSON state):**
```python
@pytest.fixture
def egolf_vehicle():
    """E-Golf with full selectivestatus data and parking position."""
    vehicle = Vehicle(conn=None, url="WVWZZZ3CZHE123456")
    vehicle._discovered = True
    data = load_fixture("egolf", "selectivestatus_by_app.json")
    vehicle._states.update(data)
    parking = load_fixture("egolf", "parkingposition.json")
    vehicle._states["parkingposition"] = parking.get("data", {})
    trip = load_fixture("egolf", "last_trip.json")
    vehicle._states[Services.TRIP_LAST] = trip.get("data", {})
    return vehicle
```

**NA vehicle fixture pattern (uses MagicMock connection to set `is_na = True`):**
```python
@pytest.fixture
def na_vehicle():
    """NA vehicle with RVS data."""
    conn = MagicMock()
    conn.is_na = True
    conn._session_region = "NA"
    conn._session_region_config = {"homeregion": "https://msg.volkswagen.de"}
    vehicle = Vehicle(conn=conn, url="3VV4X7B27RM030662")
    vehicle._discovered = True
    vehicle._states["na_status"] = load_fixture("na_vehicle", "rvs_status.json")
    vehicle._states["na_location"] = load_fixture("na_vehicle", "rvs_location.json")
    return vehicle
```

**Test helper factory functions (module-level, not pytest fixtures, for `IsolatedAsyncioTestCase`):**
```python
def _make_na_conn(**kwargs) -> Connection:
    mock_session = AsyncMock()
    mock_session._cookie_jar = MagicMock()
    mock_session._cookie_jar._cookies = {}
    conn = Connection(mock_session, "user@example.com", "password", country="US", **kwargs)
    conn._session_tokens = {"identity": {"access_token": "test_token"}}
    conn._base_api = "https://b-h-s.spr.us00.p.con-veh.net"
    return conn
```

**JSON fixture files location:** `tests/fixtures/resources/responses/`
- `egolf/` — E-Golf EV: `selectivestatus_by_app.json`, `parkingposition.json`, `last_trip.json`
- `na_vehicle/` — NA vehicle: `rvs_status.json`, `rvs_location.json`, `ev_charge.json`, `ev_charge_active.json`, `climate_settings.json`, `trip_stats.json`
- `arteon_2023_diesel/`, `eup_electric/`, `golf_gte_hybrid/` — additional vehicle type fixtures

## Coverage

**Requirements:** Branch coverage enabled (`branch = True` in `setup.cfg`). No minimum percentage enforced.

**Exclusions:**
```ini
[coverage:run]
omit = tests/*,volkswagencarnet/version.py
```

**View Coverage:**
```bash
pytest --cov=volkswagencarnet --cov-report=html
# Open htmlcov/index.html in browser
```

## Test Types

**Unit Tests (majority):**
- Test individual methods in isolation
- Mock external dependencies (HTTP session, other Connection methods)
- Direct state injection into `Vehicle._states` and `Vehicle._services`
- Located in `tests/vw_*_test.py` and `tests/*_test.py`

**Code Quality Tests (`tests/code_quality_test.py`):**
- Unique structural pattern: AST parsing + regex applied to `vw_connection.py` source
- Enforces: no bare `response.text` (coroutine reference bug), no dead methods, no stale lint suppression comments
- Tests read source directly via `Path(__file__).parent.parent / "volkswagencarnet" / "vw_connection.py"`

**Integration Tests (`tests/integration_test.py`):**
- Require real credentials in `tests/credentials.py` (not committed; `credentials.py.sample` is provided)
- Skipped automatically via `@pytest.mark.skipif` when credentials module is missing
- Run in same pytest session but gated by import-time try/except

**E2E Tests (`tests/e2e/`):**
- Excluded from `pytest` normal runs via `norecursedirs = ["tests/e2e"]` in `pyproject.toml`
- Require env vars: `VW_TEST_USERNAME`, `VW_TEST_PASSWORD`, optionally `VW_TEST_SPIN`
- Fail loudly at import time if env vars are missing (credential guard in `tests/e2e/conftest.py`)
- Use module-scoped `na_connection` fixture for shared live authentication
- `loop_scope="module"` required on all e2e test classes to share event loop with module-scoped fixture:
  ```python
  pytestmark = pytest.mark.asyncio(loop_scope="module")
  ```

## Common Patterns

**Time freezing for datetime-dependent tests:**
```python
from freezegun import freeze_time

@freeze_time("2022-02-14 03:04:05")
async def test_init(self):
    target_date = datetime.fromisoformat("2022-02-14 03:04:05").replace(tzinfo=UTC)
    vehicle = Vehicle(conn, url)
    assert vehicle._requests["departuretimer"]["timestamp"] == target_date
```

**Exception testing:**
```python
with pytest.raises(AuthenticationError, match="Wrong username or password"):
    await conn._login_na()

# Inspect exception message:
with pytest.raises(Exception) as exc_info:
    await vehicle.set_lock("any", "")
assert str(exc_info.value) == "Invalid lock action: any"
```

**Strict call-count verification:**
```python
vehicle = MagicMock(spec=Vehicle, name="MockUpdateVehicle")
vehicle.update = lambda: Vehicle.update(vehicle)
await vehicle.update()
vehicle.discover.assert_called_once()
assert len(vehicle.method_calls) == 8, (
    f"Wrong number of methods called. Expected 8, got {len(vehicle.method_calls)}"
)
```

**Async session timeout rule:**
Any `self._session.post/get()` call outside of `_request()` MUST pass an explicit timeout parameter:
```python
await self._session.post(
    url,
    data=body,
    headers=headers,
    timeout=ClientTimeout(total=TIMEOUT.seconds),  # REQUIRED
)
```
This prevents "Timeout context manager should be used inside a task" errors in aiohttp 3.13 + pytest-asyncio with mismatched loop scopes.

---

*Testing analysis: 2026-03-10*
