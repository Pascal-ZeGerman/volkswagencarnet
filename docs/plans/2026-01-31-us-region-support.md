# US Region Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add North America region support to enable US/Canadian VW vehicles to use the library

**Architecture:** Auto-detect region from existing `country` parameter (US/CA→NA, EU→EMEA). Discovery mechanism tries multiple NA endpoint candidates. Backward compatible—defaults to EMEA when country unspecified.

**Tech Stack:** Python 3.11+, aiohttp, pytest

---

## Task 1: Add Region Configuration (vw_const.py)

**Files:**
- Modify: `volkswagencarnet/vw_const.py` (add after line 36, before TEMP_CELSIUS)

**Step 1: Write failing test for region mapping**

Create: `tests/test_region_support.py`

```python
"""Test region detection and configuration."""
import pytest
from volkswagencarnet.vw_const import (
    get_region_from_country,
    get_region_config,
)


class TestRegionMapping:
    """Test region detection from country codes."""

    def test_us_maps_to_na(self):
        assert get_region_from_country("US") == "NA"
        assert get_region_from_country("us") == "NA"  # Case insensitive

    def test_canada_maps_to_na(self):
        assert get_region_from_country("CA") == "NA"

    def test_germany_maps_to_emea(self):
        assert get_region_from_country("DE") == "EMEA"

    def test_france_maps_to_emea(self):
        assert get_region_from_country("FR") == "EMEA"

    def test_unknown_country_defaults_to_emea(self):
        assert get_region_from_country("XX") == "EMEA"

    def test_emea_config_has_base_api(self):
        config = get_region_config("EMEA")
        assert config["base_api"] == "https://emea.bff.cariad.digital"
        assert config["homeregion"] == "https://msg.volkswagen.de"

    def test_na_config_has_candidates(self):
        config = get_region_config("NA")
        assert "base_api_candidates" in config
        assert len(config["base_api_candidates"]) > 0
        assert config["base_api"] is None  # Not yet discovered
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_region_support.py -v`

Expected: FAIL with "ImportError: cannot import name 'get_region_from_country'"

**Step 3: Add region configuration to vw_const.py**

Add after line 36 (after `HEADERS_AUTH`), before line 37 (`TEMP_CELSIUS`):

```python

# Region configuration
REGION_CONFIGS = {
    "EMEA": {
        "base_api": "https://emea.bff.cariad.digital",
        "homeregion": "https://msg.volkswagen.de",
    },
    "NA": {  # North America
        "base_api": None,  # Discovered during login
        "homeregion": None,  # Discovered during login
        "base_api_candidates": [
            "https://na.bff.cariad.digital",
            "https://us.bff.cariad.digital",
            "https://northamerica.bff.cariad.digital",
            "https://usac.bff.cariad.digital",
            "https://americas.bff.cariad.digital",
        ],
        "homeregion_candidates": [
            "https://msg.vw.com",
            "https://msg.volkswagen.com",
            "https://msg.vw.us",
        ],
    },
}

# Country to region mapping
COUNTRY_TO_REGION = {
    # North America
    "US": "NA",
    "CA": "NA",
    # EMEA
    "DE": "EMEA",
    "FR": "EMEA",
    "UK": "EMEA",
    "GB": "EMEA",
    "IT": "EMEA",
    "ES": "EMEA",
    "NL": "EMEA",
    "BE": "EMEA",
    "AT": "EMEA",
    "CH": "EMEA",
    "SE": "EMEA",
    "NO": "EMEA",
    "DK": "EMEA",
    "FI": "EMEA",
    "PL": "EMEA",
    "CZ": "EMEA",
    "PT": "EMEA",
    "IE": "EMEA",
    "LU": "EMEA",
}

DEFAULT_REGION = "EMEA"


def get_region_from_country(country: str) -> str:
    """Get region identifier from country code.

    Args:
        country: Two-letter country code (e.g., 'US', 'DE')

    Returns:
        Region identifier ('EMEA', 'NA', etc.)
    """
    return COUNTRY_TO_REGION.get(country.upper(), DEFAULT_REGION)


def get_region_config(region: str) -> dict:
    """Get configuration for a specific region.

    Args:
        region: Region identifier ('EMEA', 'NA', etc.)

    Returns:
        Dictionary with region configuration
    """
    return REGION_CONFIGS.get(region, REGION_CONFIGS[DEFAULT_REGION])
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_region_support.py -v`

Expected: All 8 tests PASS

**Step 5: Commit**

```bash
git add volkswagencarnet/vw_const.py tests/test_region_support.py
git commit -m "feat: add region configuration and country-to-region mapping"
```

---

## Task 2: Add Region Detection to Connection (vw_connection.py - imports and init)

**Files:**
- Modify: `volkswagencarnet/vw_connection.py:19-31` (imports)
- Modify: `volkswagencarnet/vw_connection.py:60-84` (`__init__`)

**Step 1: Write test for region detection in Connection**

Add to: `tests/test_region_support.py`

```python
import asyncio
from aiohttp import ClientSession
from volkswagencarnet.vw_connection import Connection


class TestConnectionRegionDetection:
    """Test Connection class region detection."""

    @pytest.mark.asyncio
    async def test_connection_defaults_to_emea(self):
        """No country parameter should default to EMEA."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password")
            assert conn._session_region == "EMEA"
            assert conn._session_country == "DE"
            assert conn._base_api == "https://emea.bff.cariad.digital"

    @pytest.mark.asyncio
    async def test_connection_with_de_country(self):
        """DE country should map to EMEA."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password", country="DE")
            assert conn._session_region == "EMEA"
            assert conn._base_api == "https://emea.bff.cariad.digital"

    @pytest.mark.asyncio
    async def test_connection_with_us_country(self):
        """US country should map to NA."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password", country="US")
            assert conn._session_region == "NA"
            assert conn._session_country == "US"
            # base_api should be None (not yet discovered)
            assert conn._base_api is None

    @pytest.mark.asyncio
    async def test_connection_with_ca_country(self):
        """CA country should map to NA."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password", country="CA")
            assert conn._session_region == "NA"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_region_support.py::TestConnectionRegionDetection -v`

Expected: FAIL with "AttributeError: 'Connection' object has no attribute '_session_region'"

**Step 3: Update imports in vw_connection.py**

Modify lines 19-31 to add new imports:

```python
from .vw_const import (
    ANDROID_PACKAGE_NAME,
    APP_URI,
    BASE_API,
    BRAND,
    CLIENT_ID,
    CLIENT_SCOPE,
    CLIENT_TOKEN_TYPES,
    COUNTRY,
    HEADERS_AUTH,
    HEADERS_SESSION,
    USER_AGENT,
    get_region_from_country,
    get_region_config,
)
```

**Step 4: Add region detection to __init__ method**

In `vw_connection.py`, find line 78 (`self._session_country = country.upper()`).

Add immediately after it:

```python

        # Determine region from country
        self._session_region = get_region_from_country(self._session_country)
        self._session_region_config = get_region_config(self._session_region)

        # Set region-specific base API (will be discovered for NA)
        self._base_api = self._session_region_config.get("base_api") or BASE_API
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_region_support.py::TestConnectionRegionDetection -v`

Expected: All 4 tests PASS

**Step 6: Commit**

```bash
git add volkswagencarnet/vw_connection.py tests/test_region_support.py
git commit -m "feat: add region detection to Connection __init__"
```

---

## Task 3: Add Endpoint Discovery Method (vw_connection.py)

**Files:**
- Modify: `volkswagencarnet/vw_connection.py` (add method before `doLogin` at line 90)

**Step 1: Write test for endpoint discovery**

Add to: `tests/test_region_support.py`

```python
from unittest.mock import AsyncMock, Mock, patch


class TestEndpointDiscovery:
    """Test endpoint discovery for NA region."""

    @pytest.mark.asyncio
    async def test_discovery_not_needed_for_emea(self):
        """EMEA region should skip discovery."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password", country="DE")
            result = await conn._discover_endpoints()
            assert result is True  # Should return immediately

    @pytest.mark.asyncio
    async def test_discovery_finds_working_endpoint(self):
        """Should find first working endpoint from candidates."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password", country="US")

            # Mock successful response for second candidate
            mock_response = Mock()
            mock_response.status = 200

            with patch.object(conn._session, 'get', new_callable=AsyncMock) as mock_get:
                # First candidate fails, second succeeds
                mock_get.side_effect = [
                    Exception("Connection refused"),  # First fails
                    mock_response,  # Second succeeds
                ]

                result = await conn._discover_endpoints()

                assert result is True
                # Should have found second candidate
                assert conn._base_api == "https://us.bff.cariad.digital"

    @pytest.mark.asyncio
    async def test_discovery_fails_all_candidates(self):
        """Should return False when all candidates fail."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password", country="US")

            with patch.object(conn._session, 'get', new_callable=AsyncMock) as mock_get:
                # All candidates fail
                mock_get.side_effect = Exception("Connection refused")

                result = await conn._discover_endpoints()

                assert result is False
                assert conn._base_api is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_region_support.py::TestEndpointDiscovery -v`

Expected: FAIL with "AttributeError: 'Connection' object has no attribute '_discover_endpoints'"

**Step 3: Add _discover_endpoints method**

In `vw_connection.py`, add this method before `doLogin` (around line 88-89):

```python
    async def _discover_endpoints(self) -> bool:
        """Discover working endpoints for regions without confirmed URLs.

        Returns:
            True if discovery successful, False otherwise
        """
        if self._session_region != "NA":
            return True  # Only needed for NA region

        _LOGGER.info("Attempting endpoint discovery for North America region")

        base_api_candidates = self._session_region_config.get("base_api_candidates", [])

        for candidate in base_api_candidates:
            try:
                _LOGGER.debug("Testing base API endpoint: %s", candidate)
                req = await self._session.get(
                    url=f"{candidate}/login/v1/idk/openid-configuration",
                    timeout=ClientTimeout(total=5),
                )
                if req.status == 200:
                    _LOGGER.info("Found working base API endpoint: %s", candidate)
                    self._base_api = candidate
                    return True
            except Exception as e:
                _LOGGER.debug("Endpoint %s failed: %s", candidate, str(e))
                continue

        _LOGGER.error(
            "Could not discover working endpoints for NA region. "
            "Please check network traffic or report at: "
            "https://github.com/robinostlund/volkswagencarnet/issues"
        )
        return False

```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_region_support.py::TestEndpointDiscovery -v`

Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add volkswagencarnet/vw_connection.py tests/test_region_support.py
git commit -m "feat: add endpoint discovery method for NA region"
```

---

## Task 4: Integrate Discovery into doLogin (vw_connection.py)

**Files:**
- Modify: `volkswagencarnet/vw_connection.py:90-126` (`doLogin` method)

**Step 1: Write test for discovery integration**

Add to: `tests/test_region_support.py`

```python
class TestLoginWithDiscovery:
    """Test login process with endpoint discovery."""

    @pytest.mark.asyncio
    async def test_login_fails_when_discovery_fails(self):
        """Login should fail if NA endpoint discovery fails."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password", country="US")

            with patch.object(conn, '_discover_endpoints', new_callable=AsyncMock) as mock_discover:
                mock_discover.return_value = False

                result = await conn.doLogin()

                assert result is False
                mock_discover.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_continues_after_successful_discovery(self):
        """Login should proceed after successful NA endpoint discovery."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password", country="US")

            with patch.object(conn, '_discover_endpoints', new_callable=AsyncMock) as mock_discover:
                with patch.object(conn, '_login', new_callable=AsyncMock) as mock_login:
                    mock_discover.return_value = True
                    mock_login.return_value = True

                    # Mock vehicle list response
                    with patch.object(conn, 'get', new_callable=AsyncMock) as mock_get:
                        mock_get.return_value = {"data": []}

                        result = await conn.doLogin()

                        mock_discover.assert_called_once()
                        mock_login.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_region_support.py::TestLoginWithDiscovery -v`

Expected: FAIL (discovery not called during login)

**Step 3: Modify doLogin method**

In `vw_connection.py`, find the `doLogin` method (around line 90). Add endpoint discovery after acquiring the lock and before the login retry loop.

Find line 93 (`_LOGGER.debug("Initiating new login")`).

Add after it:

```python

            # Discover endpoints if needed
            if self._session_region == "NA" and not self._base_api:
                if not await self._discover_endpoints():
                    _LOGGER.error("Endpoint discovery failed for NA region")
                    return False
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_region_support.py::TestLoginWithDiscovery -v`

Expected: All 2 tests PASS

**Step 5: Run all region tests**

Run: `pytest tests/test_region_support.py -v`

Expected: All tests PASS

**Step 6: Commit**

```bash
git add volkswagencarnet/vw_connection.py tests/test_region_support.py
git commit -m "feat: integrate endpoint discovery into doLogin flow"
```

---

## Task 5: Replace BASE_API with self._base_api (vw_connection.py)

**Files:**
- Modify: `volkswagencarnet/vw_connection.py` (multiple locations)

**Step 1: Find all BASE_API references**

Run: `grep -n "BASE_API" volkswagencarnet/vw_connection.py | grep -v "from .vw_const import"`

Expected: List of ~30 line numbers where BASE_API is used

**Step 2: Replace all BASE_API with self._base_api**

Use find/replace:
- Pattern: `f"{BASE_API}/`
- Replace with: `f"{self._base_api}/`

Locations (approximate):
- Line 112: `url=f"{BASE_API}/vehicle/v2/vehicles"`
- Line 132: `url=f"{BASE_API}/login/v1/idk/openid-configuration"`
- Line 461: `await self.post(f"{BASE_API}/login/v1/idk/revoke", data=params)`
- Line 641: `f"{BASE_API}/vehicle/v1/vehicles/{vin}/pendingrequests"`
- Line 660: `f"{BASE_API}/vehicle/v1/vehicles/{vin}/capabilities"`
- Line 684: `f"{BASE_API}/vehicle/v1/vehicles/{vin}/selectivestatus"`
- Line 708: `response = await self.get(f"{BASE_API}/vehicle/v2/vehicles", "")`
- Line 726: `f"{BASE_API}/vehicle/v1/vehicles/{vin}/parkingposition"`
- Line 756: `f"{BASE_API}/vehicle/v1/trips/{vin}/shortterm/last"`
- Line 778: `f"{BASE_API}/vehicle/v1/trips/{vin}/cyclic/last"`
- Line 800: `f"{BASE_API}/vehicle/v1/trips/{vin}/longterm/last"`
- Line 822: `f"{BASE_API}/vehicle/v1/vehicles/{vin}/vehiclewakeuptrigger"`
- Line 875: `result = await self.get(f"{BASE_API}/vehicle/v1/spin/state")`
- Line 894: `f"{BASE_API}/vehicle/v1/vehicles/{vin}/climatisation/{action}"`
- Line 906: `f"{BASE_API}/vehicle/v1/vehicles/{vin}/climatisation/settings"`
- Line 919: `f"{BASE_API}/vehicle/v1/vehicles/{vin}/auxiliaryheating/{action}"`
- Line 932: `f"{BASE_API}/vehicle/v1/vehicles/{vin}/windowheating/{action}"`
- Line 945: `f"{BASE_API}/vehicle/v1/vehicles/{vin}/charging/{action}"`
- Line 957: `f"{BASE_API}/vehicle/v1/vehicles/{vin}/charging/settings"`
- Line 969: `f"{BASE_API}/vehicle/v1/vehicles/{vin}/charging/care/settings"`
- Line 983: `f"{BASE_API}/vehicle/v1/vehicles/{vin}/readiness/batterysupport"`
- Line 997: `f"{BASE_API}/vehicle/v1/vehicles/{vin}/departure/profiles"`
- Line 1011: `f"{BASE_API}/vehicle/v1/vehicles/{vin}/climatisation/timers"`
- Line 1025: `f"{BASE_API}/vehicle/v1/vehicles/{vin}/auxiliaryheating/timers"`
- Line 1039: `f"{BASE_API}/vehicle/v1/vehicles/{vin}/departure/timers"`
- Line 1053: `f"{BASE_API}/vehicle/v1/vehicles/{vin}/access/{action}"`
- Line 1066: `f"{BASE_API}/vehicle/v1/vehicles/{vin}/honkandflash"`
- Line 1138: `url=f"{BASE_API}/login/v1/idk/token"`

**Step 3: Verify replacements**

Run: `grep -n '"BASE_API"' volkswagencarnet/vw_connection.py`

Expected: Only the import line should remain

Run: `grep -n 'self._base_api' volkswagencarnet/vw_connection.py | wc -l`

Expected: ~30 occurrences

**Step 4: Run all existing tests**

Run: `pytest tests/ -v`

Expected: All tests PASS (backward compatibility maintained)

**Step 5: Commit**

```bash
git add volkswagencarnet/vw_connection.py
git commit -m "refactor: replace hardcoded BASE_API with self._base_api throughout Connection"
```

---

## Task 6: Make Vehicle Homeregion Configurable (vw_vehicle.py)

**Files:**
- Modify: `volkswagencarnet/vw_vehicle.py:43-48` (`__init__`)

**Step 1: Write test for configurable homeregion**

Add to: `tests/test_region_support.py`

```python
from volkswagencarnet.vw_vehicle import Vehicle


class TestVehicleRegionConfig:
    """Test Vehicle class uses region config."""

    @pytest.mark.asyncio
    async def test_vehicle_uses_emea_homeregion(self):
        """Vehicle should use EMEA homeregion from connection."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password", country="DE")
            vehicle = Vehicle(conn, "WVWZZZ3CZHE123456")

            assert vehicle._homeregion == "https://msg.volkswagen.de"

    @pytest.mark.asyncio
    async def test_vehicle_uses_na_homeregion_when_discovered(self):
        """Vehicle should use NA homeregion from connection config."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password", country="US")

            # Simulate discovered NA homeregion
            conn._session_region_config["homeregion"] = "https://msg.vw.com"

            vehicle = Vehicle(conn, "1VWSA7A3XLC123456")

            assert vehicle._homeregion == "https://msg.vw.com"

    @pytest.mark.asyncio
    async def test_vehicle_falls_back_to_default_homeregion(self):
        """Vehicle should fall back to DE if homeregion is None."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password", country="US")

            # NA config has homeregion=None initially
            assert conn._session_region_config.get("homeregion") is None

            vehicle = Vehicle(conn, "1VWSA7A3XLC123456")

            # Should fall back to default
            assert vehicle._homeregion == "https://msg.volkswagen.de"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_region_support.py::TestVehicleRegionConfig -v`

Expected: Tests fail (homeregion still hardcoded)

**Step 3: Modify Vehicle.__init__ to use region config**

In `volkswagencarnet/vw_vehicle.py`, find line 47:

```python
        self._homeregion = "https://msg.volkswagen.de"
```

Replace with:

```python
        # Get homeregion from connection's region config
        region_config = conn._session_region_config
        self._homeregion = region_config.get("homeregion", "https://msg.volkswagen.de")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_region_support.py::TestVehicleRegionConfig -v`

Expected: All 3 tests PASS

**Step 5: Run all tests**

Run: `pytest tests/ -v`

Expected: All tests PASS

**Step 6: Commit**

```bash
git add volkswagencarnet/vw_vehicle.py tests/test_region_support.py
git commit -m "feat: make Vehicle homeregion configurable from connection region"
```

---

## Task 7: Update CLAUDE.md Documentation

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update Overview section**

Find the "Regional Limitation" paragraph in CLAUDE.md and replace it with:

```markdown
**Regional Support**: This library supports both **EMEA** (Europe, Middle East, Africa) and **North America** regions. The region is auto-detected from the `country` parameter:
- `country='US'` or `country='CA'` → North America
- `country='DE'` or other EU countries → EMEA (default)
- No country parameter → EMEA (backward compatible)

For North America, the library will automatically discover the correct API endpoints during the first login.
```

**Step 2: Update API Structure section**

Find the API Structure section and update it:

```markdown
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
```

**Step 3: Add usage examples**

Add a new section after "Development Commands":

```markdown
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
```

**Step 4: Review changes**

Run: `cat CLAUDE.md | grep -A 5 "Regional"`

Expected: See updated regional support information

**Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with NA region support info"
```

---

## Task 8: Final Verification

**Files:**
- All modified files

**Step 1: Run complete test suite**

Run: `pytest tests/ -v --cov=volkswagencarnet --cov-report=term-missing`

Expected: All tests PASS with good coverage

**Step 2: Test EMEA backward compatibility**

Create temporary test script: `test_emea_compat.py`

```python
import asyncio
from aiohttp import ClientSession
from volkswagencarnet.vw_connection import Connection


async def test_emea_compat():
    """Verify EMEA backward compatibility."""
    async with ClientSession() as session:
        # Test 1: No country parameter
        conn1 = Connection(session, "test@example.com", "pass")
        assert conn1._session_region == "EMEA"
        assert conn1._base_api == "https://emea.bff.cariad.digital"
        print("✓ No country parameter → EMEA")

        # Test 2: Explicit DE
        conn2 = Connection(session, "test@example.com", "pass", country="DE")
        assert conn2._session_region == "EMEA"
        assert conn2._base_api == "https://emea.bff.cariad.digital"
        print("✓ country='DE' → EMEA")

        # Test 3: US country
        conn3 = Connection(session, "test@example.com", "pass", country="US")
        assert conn3._session_region == "NA"
        assert conn3._base_api is None  # Not discovered yet
        print("✓ country='US' → NA (discovery pending)")

        print("\n✓ All backward compatibility checks passed!")


if __name__ == "__main__":
    asyncio.run(test_emea_compat())
```

Run: `python test_emea_compat.py`

Expected: All checks pass

Remove: `rm test_emea_compat.py`

**Step 3: Check code formatting**

Run: `ruff format --diff .`

Expected: No formatting changes needed (or apply them)

**Step 4: Review all commits**

Run: `git log --oneline -8`

Expected: See all 8 feature commits

**Step 5: Create summary commit**

```bash
git add -A
git commit -m "feat: add US/NA region support with auto-detection

- Add region configuration and country-to-region mapping
- Implement endpoint discovery for NA region
- Auto-detect region from country parameter (US/CA→NA, EU→EMEA)
- Maintain backward compatibility (defaults to EMEA)
- Update documentation with usage examples
- Add comprehensive test coverage

Closes #XXX" --allow-empty
```

---

## Testing Checklist

After implementation, verify:

- [ ] `pytest tests/test_region_support.py -v` - All region tests pass
- [ ] `pytest tests/ -v` - All existing tests pass (backward compat)
- [ ] EMEA users: `Connection(session, user, pass)` → EMEA region
- [ ] EMEA users: `Connection(session, user, pass, country="DE")` → EMEA region
- [ ] US users: `Connection(session, user, pass, country="US")` → NA region
- [ ] CA users: `Connection(session, user, pass, country="CA")` → NA region
- [ ] Unknown country defaults to EMEA
- [ ] Code formatting: `ruff format --diff` shows no changes
- [ ] Documentation updated in CLAUDE.md

## Expected Outcome

**For EMEA users (backward compatible):**
- Existing code works without any changes
- Library defaults to EMEA endpoints
- No breaking changes

**For US/CA users:**
```python
connection = Connection(session, username, password, country="US")
await connection.doLogin()
# Library discovers NA endpoints automatically
```

## Notes for Implementation

- Use TDD: Write test first, verify it fails, implement, verify it passes, commit
- Keep commits small and focused (one feature per commit)
- Run tests after each step to catch issues early
- The endpoint discovery will likely fail initially (unknown endpoints) - this is expected
- If discovery fails, log clear error messages for debugging
- Future: Update endpoint candidates based on real-world testing
