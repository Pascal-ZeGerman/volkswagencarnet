"""
E2E test configuration for North America live integration tests.

These tests require real VW credentials and a live network connection.
They are excluded from normal pytest runs via norecursedirs in pyproject.toml.

To run: pytest tests/e2e/ -v
"""
import logging
import os

import pytest
import pytest_asyncio
from aiohttp import ClientSession
from aiohttp import CookieJar

from volkswagencarnet.vw_connection import Connection

# ---------------------------------------------------------------------------
# Part A: Credential guard — fails at import time if env vars are missing
# ---------------------------------------------------------------------------
_USERNAME = os.environ.get("VW_TEST_USERNAME")
_PASSWORD = os.environ.get("VW_TEST_PASSWORD")

if not _USERNAME or not _PASSWORD:
    raise EnvironmentError(
        "E2E tests require real VW credentials.\n"
        "Set VW_TEST_USERNAME and VW_TEST_PASSWORD to run live tests.\n"
        "  export VW_TEST_USERNAME='your-email@example.com'\n"
        "  export VW_TEST_PASSWORD='your-password'"
    )

# ---------------------------------------------------------------------------
# Part B: Log file setup
# ---------------------------------------------------------------------------
_LOG_FILE = os.path.join(os.path.dirname(__file__), "e2e_run.log")
_log = logging.getLogger("e2e")


def _truncate_token(t: str) -> str:
    """Truncate token for safe logging — never log full token values."""
    return t[:12] + "..." if t and len(t) > 15 else "(empty)"


@pytest.fixture(scope="session", autouse=True)
def _setup_logging():
    """Install a DEBUG file handler for the e2e log file."""
    handler = logging.FileHandler(_LOG_FILE, mode="a")
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG)

    _log.info("E2E session started — log file: %s", _LOG_FILE)
    yield
    _log.info("E2E session complete")
    root_logger.removeHandler(handler)
    handler.close()


# ---------------------------------------------------------------------------
# Part C: Module-scoped login fixture with full-auth enforcement
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def na_connection():
    """
    Module-scoped async fixture that performs a real NA login and yields
    a fully authenticated Connection instance.

    Raises AssertionError if:
    - doLogin() returns False (authentication failure)
    - na_auth_level != 'full' (only IDK token obtained, not Brand + MBB)

    The full-auth check is intentionally hard-fail — tests that depend on
    Brand/MBB tokens must never silently receive a partially-authenticated
    connection.
    """
    jar = CookieJar()
    async with ClientSession(cookie_jar=jar) as session:
        conn = Connection(session, _USERNAME, _PASSWORD, country="US")
        _log.info("NA doLogin() starting — username: %s", _USERNAME)

        result = await conn.doLogin()

        if not result:
            _log.error("NA doLogin() returned False for username: %s", _USERNAME)
            raise AssertionError(
                f"NA doLogin() returned False.\n"
                f"Username: {_USERNAME!r}\n"
                f"Check credentials and VW API availability."
            )

        assert conn.logged_in, "conn.logged_in is False after successful doLogin()"

        _log.info(
            "NA doLogin() succeeded — na_auth_level=%s, logged_in=%s",
            conn.na_auth_level,
            conn.logged_in,
        )

        if conn.na_auth_level != "full":
            tokens_present = list(conn._na_tokens.keys()) if hasattr(conn, "_na_tokens") else []
            _log.error(
                "Partial auth only — na_auth_level=%s, tokens_present=%s",
                conn.na_auth_level,
                tokens_present,
            )
            raise AssertionError(
                f"NA authentication achieved only '{conn.na_auth_level}' — expected 'full' "
                f"(all three tokens: IDK, Brand, MBB).\n"
                f"Phase 7 goal requires all three token types. "
                f"Check if Brand/MBB token endpoints are reachable.\n"
                f"Tokens present: {tokens_present}"
            )

        _log.info("Full auth confirmed — yielding connection to test module")
        yield conn
