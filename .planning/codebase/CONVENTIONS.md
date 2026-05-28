# Coding Conventions

**Analysis Date:** 2026-03-10

## Naming Patterns

**Files:**
- `snake_case` with `vw_` prefix for all library modules: `vw_connection.py`, `vw_vehicle.py`, `vw_const.py`, `vw_utilities.py`, `vw_dashboard.py`, `vw_exceptions.py`
- Test files use `_test.py` suffix (e.g., `vw_connection_test.py`) or `test_` prefix (e.g., `test_xqmauth.py`) — both patterns are accepted per `pyproject.toml`

**Classes:**
- `PascalCase` for all classes: `Connection`, `Vehicle`, `Dashboard`, `Instrument`
- Test classes use `PascalCase` with descriptive suffix: `NAOAuthLoginTest`, `VehiclePropertyTest`, `TestRegionMapping`, `MarketConfigDiscoveryTest`

**Methods and Functions:**
- `snake_case` for public methods: `do_login()`, `get_openid_config()`, `find_path()`
- Exception: `camelCase` for legacy public API methods that mirror HA integration names: `doLogin()`, `setDepartureTimers()`, `get_selectivestatus()`
- `_single_leading_underscore` for private methods: `_login_na()`, `_classify_endpoint()`, `_refresh_idk_token()`
- Helper factory functions in tests use `_make_` prefix: `_make_na_conn()`, `_make_emea_conn()`, `_make_na_vehicle()`

**Variables and Attributes:**
- `snake_case` for local variables and parameters
- Private instance attributes use `_single_leading_underscore`: `self._session`, `self._base_api`, `self._session_tokens`
- Module-level logger: `_LOGGER = logging.getLogger(__name__)` in every module
- Module-level constants: `SCREAMING_SNAKE_CASE`: `MAX_RETRIES_ON_RATE_LIMIT`, `TIMEOUT`, `JWT_ALGORITHMS`

**Engine type constants:**
- String constants defined at module level in `vw_vehicle.py`:
  ```python
  ENGINE_TYPE_ELECTRIC = "electric"
  ENGINE_TYPE_DIESEL = "diesel"
  ENGINE_TYPE_GASOLINE = "gasoline"
  ENGINE_TYPE_CNG = "cng"
  ```

## Code Style

**Formatting:**
- `ruff format` — configured via `setup.cfg` / pre-commit
- Max line length: 120 characters (`[pycodestyle] max_line_length=120`)
- `E722` (bare except) is ignored (`[pycodestyle] ignore = E722`)
- Trailing whitespace removed by pre-commit hook

**Linting:**
- No dedicated ruff lint config found; mypy is the primary static checker
- mypy enforces `disallow_untyped_defs = True` on `vw_connection.py` and `vw_vehicle.py`
- pyupgrade enforces Python 3.7+ syntax (via pre-commit)
- `detect-secrets` baseline enforced via pre-commit

**Type Annotations:**
- All functions in `vw_connection.py` and `vw_vehicle.py` require full type annotations (enforced by mypy)
- Use `from __future__ import annotations` at top of annotated files
- Use `TYPE_CHECKING` guard for circular import avoidance:
  ```python
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:
      from .vw_connection import Connection
  ```
- Use `|` union syntax (Python 3.10+ style enabled by `from __future__ import annotations`): `str | None`, `dict | list`
- `Any` from `typing` used for aiohttp session and flexible response types

## Import Organization

**Order:**
1. `from __future__ import annotations` (if needed)
2. Standard library modules (alphabetical)
3. Third-party packages (aiohttp, bs4, jwt, freezegun, pytest)
4. Intra-package relative imports (`.vw_const`, `.vw_exceptions`, `.vw_utilities`)

**Example from `vw_connection.py`:**
```python
from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime, timedelta
import hashlib
...

import aiohttp
from aiohttp import ClientTimeout, client_exceptions
from bs4 import BeautifulSoup
import jwt

from .vw_const import (BASE_API, BRAND, ...)
from .vw_exceptions import (AuthenticationError, APIError, ...)
from .vw_utilities import json_loads, redact
```

**No path aliases** — all intra-package imports use relative dot notation.

## Error Handling

**Custom Exception Hierarchy:**
- Base: `VWError(Exception)` in `volkswagencarnet/vw_exceptions.py`
- Subclasses: `AuthenticationError`, `APIError`, `SPINError`, `RedirectError`, `RequestError`
- `TermsAndConditionsError` extends `AuthenticationError` (double inheritance)

**Patterns:**
- Raise specific custom exceptions with descriptive messages at failure site:
  ```python
  raise AuthenticationError("Wrong username or password")
  raise RedirectError("Too many redirects")
  raise APIError(f"Failed to fetch {url}: {e}")
  ```
- Never use bare `except:` (style guideline, though `E722` is ignored in pycodestyle)
- Catch specific exception types and re-raise or convert:
  ```python
  except client_exceptions.ClientConnectionError as e:
      raise AuthenticationError(f"Connection error: {e}") from e
  ```
- Callers that should not propagate errors return `False` instead:
  ```python
  except Exception as e:
      _LOGGER.error("Login failed: %s", e)
      return False
  ```
- Rate limiting: HTTP 429 is caught and returns `{"state": "Throttled"}` from `Connection.get()`
- Bare `Exception` is used in `Vehicle._handle_response()` intentionally for generic topic errors

## Logging

**Framework:** Python stdlib `logging` module

**Logger instantiation** — every module declares at module level:
```python
_LOGGER = logging.getLogger(__name__)
```

**Log levels used:**
- `_LOGGER.debug()` — flow tracing, token details (redacted), URL decisions
- `_LOGGER.info()` — significant state transitions (login success, vehicle found)
- `_LOGGER.warning()` — non-fatal issues (rate limiting, discovery failure, throttling)
- `_LOGGER.error()` — operation failures (login failed, lock failed)

**Credential redaction — mandatory for any token/secret logging:**
```python
from .vw_utilities import redact
_LOGGER.debug("Token: %s", redact(token_value))
```
`redact()` returns first 8 characters + `"..."` or `"(none)"` for empty/None.

**Log message formatting:**
- Use `%s` formatting (not f-strings) in logger calls: `_LOGGER.debug("URL: %s", url)`
- Do NOT log `response.headers` or `response.text` in `_request()` (enforced by `code_quality_test.py`)
- Only log `response.status` and URL in `_request()` debug calls

## Comments

**When to Comment:**
- Inline comments explain non-obvious decisions, especially API quirks and regional differences
- `# noinspection PyPep8Naming` for intentional camelCase methods
- Section dividers in long test files use `# ---...--- #` style banners

**Docstrings:**
- All public methods and classes have a one-line docstring minimum
- Complex methods use multi-line Google-style docstrings with `Args:`, `Returns:`, `Raises:`, `Example:`:
  ```python
  def redact(value: str | None) -> str:
      """Redact a credential value for safe logging.

      Args:
          value: The credential string to redact.

      Returns:
          Redacted string safe for log output.

      Examples:
          >>> redact("eyJhbGci...")
          'eyJhbGci...'
      """
  ```
- Doctests in `vw_utilities.py` functions serve as both documentation and executable examples

## Function Design

**Size:** Long methods are acceptable in `vw_connection.py` for complex OAuth flows (functions like `_get_authorization_code_na()` are deliberately detailed)

**Parameters:**
- Keyword-only arguments used for Connection constructor: all parameters after `session`, `username`, `password` have defaults
- `**kwargs` used in test helper factories to pass through to `Connection()`

**Return Values:**
- Boolean `True`/`False` for login/operation success/failure
- `None` for operations that have no meaningful return
- `dict` for API responses (typed as `dict[str, Any]`)
- `str | None` for optional string results
- Async methods that fetch data return `dict | None`

## Module Design

**Exports:**
- `volkswagencarnet/__init__.py` exists but is minimal (no explicit `__all__`)
- Public API surfaces are `Connection` (from `vw_connection`) and `Vehicle` (from `vw_vehicle`)

**Constants Module (`vw_const.py`):**
- All API credentials, endpoints, headers, and region configs live in `vw_const.py`
- Region configs use a `REGION_CONFIGS` dict keyed by `"EMEA"` / `"NA"`:
  ```python
  REGION_CONFIGS = {
      "EMEA": {"base_api": "...", "homeregion": "...", "client_id": "..."},
      "NA":   {"base_api": "...", "homeregion": None,  "client_id": "..."},
  }
  ```
- Helper functions `get_region_from_country()` and `get_region_config()` exported from `vw_const`

**Barrel Files:** Not used — each module is imported directly by path.

---

*Convention analysis: 2026-03-10*
