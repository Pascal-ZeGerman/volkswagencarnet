# Coding Conventions

**Analysis Date:** 2026-02-10

## Naming Patterns

**Files:**
- Module files use `vw_<component>.py` pattern (e.g., `vw_connection.py`, `vw_vehicle.py`, `vw_utilities.py`, `vw_const.py`, `vw_dashboard.py`, `vw_exceptions.py`)
- Test files follow `<module>_test.py` pattern (e.g., `vw_connection_test.py`, `vw_utilities_test.py`)
- Special integration tests: `integration_test.py`, `region_support_test.py`, `dummy_test.py`

**Functions:**
- Private functions use leading underscore: `_clear_cookies()`, `_discover_endpoints()`, `_request()`
- Async functions explicitly declared with `async def`
- Action methods use verb-first pattern: `doLogin()`, `postForm()`, `handleLoginWithPassword()`, `exchangeCodeForTokens()`
- Query methods use `get*` prefix: `getOpenidConfig()`, `getAuthorizationPage()`, `getVehicleData()`, `getParkingPosition()`
- Method names use mixedCase (camelCase) for all public/private functions

**Variables:**
- Module/class variables use leading underscore: `_session`, `_connection`, `_vehicles`, `_states`, `_requests`, `_services`
- Constants in `vw_const.py` use UPPER_SNAKE_CASE: `BASE_API`, `CLIENT_ID`, `HEADERS_SESSION`, `HEADERS_AUTH`, `MAX_RETRIES_ON_RATE_LIMIT`, `TIMEOUT`
- Engine type constants use UPPER_SNAKE_CASE: `ENGINE_TYPE_ELECTRIC`, `ENGINE_TYPE_DIESEL`, `ENGINE_TYPE_GASOLINE`
- Logger instances use `_LOGGER` (module-level)
- Dictionary keys typically use camelCase for API-related keys: `{"id": ..., "status": ..., "timestamp": ...}`

**Types:**
- Type hints use Union syntax: `Dict[str, str]`, `Optional[str]`, `dict[str, object]` (newer style)
- Union types for parameters: `src: dict | list` (PEP 604 style with `|`)
- Return type hints explicitly declared: `-> bool`, `-> str`, `-> Dict[str, str]`

## Code Style

**Formatting:**
- Max line length: 120 characters (defined in `setup.cfg`)
- Indentation: 4 spaces
- Ignores E722 (do not enforce bare `except`)

**Linting:**
- Runs `pyupgrade` with Python 3.7+ syntax
- Includes `mypy` type checking
- pylint directives used sparingly (e.g., `# pylint: disable=unreachable`)

**Code quality tools:**
- Pre-commit hooks enforce: JSON/YAML/TOML validation, no commits to main/master, trailing whitespace removal, requirements.txt sorting
- Module docstrings at file top: `"""Communicate with Volkswagen Connect services."""`
- Class docstrings: `"""Vehicle contains the state of sensors and methods for interacting with the car."""`
- Function docstrings use imperative form: `"""Initialize the Vehicle with default values."""`, `"""Check if request is already in progress."""`

## Import Organization

**Order:**
1. Shebang and module docstring: `#!/usr/bin/env python3` followed by `"""Module description."""`
2. Future imports: `from __future__ import annotations`
3. Standard library imports (alphabetically)
4. Third-party imports (alphabetically)
5. Local/relative imports (alphabetically)

**Example from `vw_connection.py`:**
```python
#!/usr/bin/env python3
"""Communicate with Volkswagen Connect services."""

from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime, timedelta
import hashlib
import logging
from random import randint, random
import secrets
from urllib.parse import parse_qs, urljoin, urlparse
from typing import Dict, Optional

from aiohttp import ClientTimeout, client_exceptions
from aiohttp.hdrs import METH_GET, METH_POST, METH_PUT
from bs4 import BeautifulSoup
import jwt

from .vw_const import (...)
from .vw_exceptions import (...)
from .vw_utilities import json_loads
from .vw_vehicle import Vehicle
```

**Path Aliases:**
- Relative imports only: `from .vw_const import ...`, `from .vw_exceptions import ...`
- No absolute path aliases configured
- All cross-module imports use relative notation

## Error Handling

**Custom Exception Hierarchy (from `vw_exceptions.py`):**
```python
class VWError(Exception):
    """Base exception for VW CarNet errors."""
    pass

class AuthenticationError(VWError):
    """Authentication failed."""
    pass

class APIError(VWError):
    """API request failed."""
    pass

class SPINError(VWError):
    """S-PIN related error."""
    pass

class RedirectError(VWError):
    """Redirect handling failed."""
    pass

class RequestError(VWError):
    """Request execution failed."""
    pass

class TermsAndConditionsError(AuthenticationError):
    """Terms and Conditions need to be accepted."""
    pass
```

**Error Handling Patterns:**
- Exceptions raised with descriptive messages: `raise AuthenticationError("Wrong username or password")`
- Errors logged at appropriate levels before raising: `_LOGGER.error(...); raise APIError(...)`
- Warnings for recoverable errors: `_LOGGER.warning("Failed to login...")`
- Debug logs for detailed flow: `_LOGGER.debug("Requesting openid config from...")`
- Try-except blocks catch broad exceptions then log: `except Exception as e: _LOGGER.warning(...)`
- Some methods re-raise with context: `except ValueError as valerr: raise KeyError(...) from valerr`

## Logging

**Framework:** Python's built-in `logging` module with module-level logger

**Pattern:**
```python
import logging
_LOGGER = logging.getLogger(__name__)
```

**Usage Levels:**
- `_LOGGER.debug()`: Low-level detail (endpoint discovery, request parameters, state details)
- `_LOGGER.info()`: Important events (login success, endpoint found, vehicle discovered)
- `_LOGGER.warning()`: Recoverable errors (failed login attempt, authorization error)
- `_LOGGER.error()`: Critical failures (authentication error, endpoint discovery failed)

**Examples from codebase:**
```python
_LOGGER.debug("Initiating new login")
_LOGGER.info("Found working base API endpoint: %s", candidate)
_LOGGER.warning("Error during fetching authorization page: %s", str(e))
_LOGGER.error("Failed to get OpenID configuration, status: %s", req.status)
```

## Comments

**When to Comment:**
- Class-level summary docstring at class definition (never inline)
- Method docstrings explaining purpose, not repeating code
- Inline comments for complex logic or non-obvious decisions
- `# TODO` comments for future work (seen in `vw_vehicle.py` line 16-20 for image endpoints)
- pylint directives for necessary violations: `# pylint: disable=protected-access`
- `# noinspection` comments for IDE hints: `# noinspection PyMissingConstructor`

**JSDoc/TSDoc:**
- Not used (Python codebase)
- Standard Python docstring format with triple quotes
- Docstrings follow imperative form
- Method docstring example:
```python
def extract_state_token(self, page_content: str) -> Optional[str]:
    """Extract state token from response."""
```

## Function Design

**Size:** Functions range from 5-100+ lines. Longer functions handle complex logic like OAuth flow or HTTP request retries.

**Parameters:**
- Use type hints on all parameters: `url: str`, `vin="", tries=0`
- Default parameters in function signature: `async def doLogin(self, tries: int = 1)`
- Keyword-only arguments for optional parameters
- Consistent parameter ordering: `self`, required params, optional params with defaults

**Return Values:**
- Type hints on all return values: `-> bool`, `-> str`, `-> Dict[str, str]`, `-> Optional[str]`
- Boolean methods (status checks) return bool: `_in_progress() -> bool`, `_discover_endpoints() -> bool`
- Data retrieval methods return data or None: `extract_state_token() -> Optional[str]`, `find_path() -> Any`

## Module Design

**Exports:**
- Classes: `Connection`, `Vehicle`, custom exceptions
- Functions: Utility functions like `find_path()`, `is_valid_path()`, `json_loads()`
- Constants: Configuration in `vw_const.py` (endpoints, headers, client IDs)

**Barrel Files:**
- Not used; imports are explicit from specific modules
- Each module imports what it needs from others

**Module Structure Pattern:**
```python
# File: vw_<name>.py
#!/usr/bin/env python3
"""Module description."""

from __future__ import annotations

[imports]

_LOGGER = logging.getLogger(__name__)
[module constants]

class ClassName:
    """Class docstring."""

    def __init__(...):
        """Initialize."""

    async def _private_async_method(...):
        """Private async method."""

    def public_method(...):
        """Public method."""
```

---

*Convention analysis: 2026-02-10*
