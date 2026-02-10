# Testing Patterns

**Analysis Date:** 2026-02-10

## Test Framework

**Runner:**
- pytest 7.0.0+ (defined in `requirements-test.txt`)
- Config: `pyproject.toml`

**Assertion Library:**
- Python's built-in `assert` statements
- pytest exception checking with `pytest.raises()`

**Run Commands:**
```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=volkswagencarnet --cov-report=html

# Run specific test file
pytest tests/vw_connection_test.py

# Run specific test
pytest tests/vw_vehicle_test.py::TestVehicle::test_init

# Watch mode (not configured, use pytest-watch separately)
```

**Pytest Configuration (pyproject.toml):**
```toml
[tool.pytest.ini_options]
minversion = "6.0"
addopts = "-ra"
asyncio_mode = "strict"
testpaths = ["tests"]
python_files = ["*_test.py"]
```

## Test File Organization

**Location:**
- Tests co-located in separate `tests/` directory (not alongside source)
- Integration tests: `tests/integration_test.py`
- Feature-specific tests: `tests/region_support_test.py`
- Dummy/placeholder tests: `tests/dummy_test.py`

**Naming:**
- Test files: `<module>_test.py` (e.g., `vw_connection_test.py`, `vw_vehicle_test.py`)
- Test classes: `PascalCase` with `Test` prefix: `class TestVehicle:`, `class TwoVehiclesConnection:`
- Test methods: `test_<description>`: `test_init()`, `test_clear_cookies()`, `test_update_deactivated()`

**Structure:**
```
tests/
├── __init__.py
├── conftest.py                          # Pytest configuration and shared fixtures
├── fixtures/
│   ├── __init__.py
│   ├── connection.py                    # Connection fixture
│   ├── mock_server.py                   # Mock HTTP server
│   ├── constants.py                     # Test constants
│   └── resources/                       # Test resource files
├── dummy_test.py                        # Placeholder async test
├── vw_connection_test.py                # Connection tests
├── vw_vehicle_test.py                   # Vehicle tests
├── vw_utilities_test.py                 # Utility function tests
├── integration_test.py                  # Integration tests (require credentials)
└── region_support_test.py               # Region detection tests
```

## Test Structure

**Suite Organization with Classes:**
```python
class TestRegionMapping:
    """Test region detection from country codes."""

    def test_us_maps_to_na(self):
        assert get_region_from_country("US") == "NA"
        assert get_region_from_country("us") == "NA"

class TestConnectionRegionDetection:
    """Test Connection class region detection."""

    @pytest.mark.asyncio
    async def test_connection_defaults_to_emea(self):
        """No country parameter should default to EMEA."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password")
            assert conn._session_region == "EMEA"
```

**Async Test Pattern:**
```python
class VehicleTest(IsolatedAsyncioTestCase):
    """Test Vehicle methods."""

    @freeze_time("2022-02-14 03:04:05")
    async def test_init(self):
        """Test __init__."""
        async with ClientSession() as conn:
            vehicle = Vehicle(conn, url)
            assert conn == vehicle._connection
            assert url == vehicle._url
```

**Setup and Teardown:**
- `IsolatedAsyncioTestCase` for async test class setup
- Context managers for resource cleanup: `async with ClientSession() as session:`
- Fixtures in `tests/fixtures/connection.py` provide pre-configured test resources

**Assertion Patterns:**
```python
# Direct assertions
assert len(connection._session._cookie_jar._cookies) > 0

# Property assertions
assert conn.logged_in is True

# Equality assertions
assert vehicle._requests == expected_requests

# Containment assertions
assert "base_api_candidates" in config

# Type/structure assertions
assert isinstance(exc_info.value, expected)
```

## Fixtures and Factories

**Test Data and Fixtures:**

Pytest fixtures defined in `tests/conftest.py`:
```python
pytest_plugins = ["pytest_cov"]
pytest_plugins.append("tests.fixtures.connection")
```

Connection fixture from `tests/fixtures/connection.py`:
```python
@pytest_asyncio.fixture
async def session():
    """Client session that can be used in tests."""
    jar = CookieJar()
    jar.load(os.path.join(resource_path, "dummy_cookies.pickle"))
    sess = ClientSession(headers={"Connection": "keep-alive"}, cookie_jar=jar)
    yield sess
    await sess.close()

@pytest.fixture
def connection(session):
    """Real connection for integration tests."""
    return Connection(
        session=session,
        username="",
        password="",
        country="DE",
        interval=999,
    )
```

**Test Data Location:**
- Fixtures: `tests/fixtures/connection.py`, `tests/fixtures/constants.py`
- Cookie data: `tests/fixtures/resources/` (loaded by fixture)
- Credentials (optional): `tests/credentials.py` (imported with fallback for missing credentials)

**Factory Pattern in Tests:**
```python
# Mock vehicle factory within test
vehicle1 = vw_connection.Vehicle(None, "vin1")
vehicle2 = vw_connection.Vehicle(None, "vin2")
return [vehicle1, vehicle2]
```

## Mocking

**Framework:** Python's `unittest.mock` (MagicMock, AsyncMock, patch)

**Import Pattern:**
```python
from unittest.mock import MagicMock, patch, AsyncMock
from unittest import IsolatedAsyncioTestCase
```

**Mocking Patterns:**

1. **Mock Objects (MagicMock):**
```python
vehicle = MagicMock(spec=Vehicle, name="MockUpdateVehicle")
vehicle.update = lambda: Vehicle.update(vehicle)
vehicle._discovered = False
await vehicle.update()
vehicle.discover.assert_not_called()
```

2. **Async Mocking (AsyncMock):**
```python
sess = AsyncMock()
conn = vw_connection.Connection(sess, "", "")
```

3. **Patching Functions/Classes:**
```python
@patch("volkswagencarnet.vw_connection.Connection",
       spec_set=vw_connection.Connection,
       new=TwoVehiclesConnection)
@patch("volkswagencarnet.vw_connection.MAX_RETRIES_ON_RATE_LIMIT", 1)
async def test_rate_limit(self):
    # Test using patched class/constant
    pass
```

4. **Patching Object Methods:**
```python
with patch.object(conn, "_request", self.rateLimitedFunction):
    res = await conn.get("foo")
    assert res == {"status_code": 429}
```

**What to Mock:**
- HTTP requests (via aiohttp session mocks)
- External API responses
- Time-dependent behavior (using `freezegun`)
- Constants that should be different in test (patch module constants)

**What NOT to Mock:**
- Internal methods unless necessary for isolation
- Data structures (dict, list) - test with actual data
- Exception classes
- Module imports (prefer fixtures instead)

**Time Mocking with freezegun:**
```python
from freezegun import freeze_time

@freeze_time("2022-02-14 03:04:05")
async def test_init(self):
    """Test with frozen time."""
    target_date = datetime.fromisoformat("2022-02-14 03:04:05").replace(
        tzinfo=UTC
    )
    # Assertions use target_date
```

## Coverage

**Requirements:** Not enforced by CI; optional local measurement

**Coverage Configuration (setup.cfg):**
```
[coverage:run]
branch = True
omit = tests/*,volkswagencarnet/version.py
```

**View Coverage:**
```bash
pytest --cov=volkswagencarnet --cov-report=html
# Opens coverage HTML report in htmlcov/index.html
```

## Test Types

**Unit Tests:**
- Scope: Individual functions/methods in isolation
- Location: `tests/vw_utilities_test.py` (utility function tests), parts of `vw_vehicle_test.py`
- Approach: Direct assertions on function output, no async required unless testing async code
- Example: `test_camel_to_slug()`, `test_is_valid_path()`, `test_json_loads()`

**Integration Tests:**
- Scope: Multiple components working together or with real API
- Location: `tests/integration_test.py`
- Approach: Use actual Connection with real or mocked sessions; skipped if credentials not available
- Example: `test_successful_login()` - requires username/password in `credentials.py`
- Marked with: `@pytest.mark.skipif(username is None or password is None, reason="...") ` and `@pytest.mark.asyncio`

**Feature/Behavior Tests:**
- Scope: Specific feature verification (region support, error handling)
- Location: `tests/region_support_test.py`
- Approach: Test classes organized by feature
- Example: `TestRegionMapping`, `TestConnectionRegionDetection`, `TestConnectionLoginFlow`

## Common Patterns

**Async Testing:**
```python
# Using IsolatedAsyncioTestCase
class VehicleTest(IsolatedAsyncioTestCase):
    async def test_init(self):
        async with ClientSession() as conn:
            # Test async code
            vehicle = Vehicle(conn, url)
            assert vehicle._connection == conn

# Using pytest.mark.asyncio
@pytest.mark.asyncio
async def test_connection_defaults_to_emea(self):
    async with ClientSession() as session:
        conn = Connection(session, "test@example.com", "password")
        assert conn._session_region == "EMEA"
```

**Error Testing:**
```python
# Test that exception is raised
with pytest.raises(AuthenticationError) as exc_info:
    # Code that should raise
    pass
assert isinstance(exc_info.value, AuthenticationError)

# Test with mock raising exception
ri = MagicMock(aiohttp.RequestInfo)
e = client_exceptions.ClientResponseError(request_info=ri, history=tuple([]))
e.status = 429
raise e
```

**Subtest Pattern (for parametrized data):**
```python
def test_camel_to_slug(self):
    """Test camel_to_slug conversion."""
    data = {
        "foo": "foo",
        "fooBar": "foo_bar",
        "XYZ": "x_y_z",
    }

    for key, expected in data.items():
        with self.subTest(msg=key, v=key):
            res = camel2slug(key)
            assert expected == res
```

**Mock Server Pattern:**
```python
# From tests/fixtures/mock_server.py
class MockServerRequestHandler(BaseHTTPRequestHandler):
    mock_responses = {"/ok": {"content": json.dumps([]), "code": 200}}

    def do_GET(self):
        """Respond with something."""
        if self.path in self.mock_responses:
            self.send_response(self.mock_responses.get(self.path).get("code"))
        # ...

def get_free_port():
    """Find a free port on localhost."""
    s = socket.socket(socket.AF_INET, type=socket.SOCK_STREAM)
    s.bind(("localhost", 0))
    address, port = s.getsockname()
    s.close()
    return port

def start_mock_server(port):
    """Start the server."""
    mock_server = HTTPServer(("localhost", port), MockServerRequestHandler)
    mock_server_thread = Thread(target=mock_server.serve_forever)
    mock_server_thread.setDaemon(True)
    mock_server_thread.start()
```

**Skip and Mark Patterns:**
```python
# Skip test if Python version too old
@pytest.mark.skipif(
    condition=sys.version_info < (3, 11),
    reason="Test incompatible with Python < 3.11"
)
def test_clear_cookies(connection) -> None:
    pass

# Skip test if credentials missing
@pytest.mark.skipif(
    username is None or password is None,
    reason="Username or password is not set. Check credentials.py.sample"
)
@pytest.mark.asyncio
async def test_successful_login() -> None:
    pass

# Mark test as not yet implemented
@pytest.mark.skip("Not yet implemented")
async def test_spin_action() -> None:
    pass
```

---

*Testing analysis: 2026-02-10*
