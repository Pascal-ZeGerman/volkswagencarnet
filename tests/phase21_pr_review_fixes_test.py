"""Tests for Phase 21: Fix Critical and High Severity PR Review Issues.

Covers:
  C-1 — Credentials not tracked by git (verified structurally, not runnable in unit test)
  C-2 — SPIN never logged in plaintext
  C-3 — Auth headers logged as key names only (no token values)
  H-1 — Dead _discover_endpoints method removed
  H-2 — doLogin retry loop uses for/else with correct exhaustion handling
  H-3 — response.text bare coroutine bug eliminated
  H-4 — _request() logs only status code and URL (no response body/headers)
  H-5 — docs/ files not tracked by git (verified structurally)
  H-6 — Stale pylint disable=unreachable comment removed
"""
from __future__ import annotations

import ast
import inspect
import logging
import re
import time
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from volkswagencarnet.vw_connection import Connection

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

VW_CONNECTION_SRC = Path(__file__).parent.parent / "volkswagencarnet" / "vw_connection.py"
FAKE_IDK_ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.fake-token-value"
FAKE_IDK_ID_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.fake-id-token"
FAKE_SPIN = "0560"
FAKE_CHALLENGE = "1D02046F451D9ECCA3E4FB6B564958DF0495A069"
USER_ID = "user-sub-12345"
VIN = "WVWZZZ3HZPK002581"
BASE_API = "https://b-h-s.spr.us00.p.con-veh.net"


def _make_na_connection() -> Connection:
    """Create a minimal NA Connection with a mocked aiohttp session."""
    sess = MagicMock()
    sess._cookie_jar = MagicMock()
    sess._cookie_jar._cookies = {}
    conn = Connection(sess, "user@test.com", "password", country="US")
    conn._base_api = BASE_API
    return conn


def _make_na_connection_with_tokens(spin: str | None = None) -> Connection:
    """Create an NA Connection with IDK tokens pre-populated."""
    conn = _make_na_connection()
    if spin:
        conn._spin = spin
    conn._na_tokens = {
        "idk": {
            "id_token": FAKE_IDK_ID_TOKEN,
            "access_token": FAKE_IDK_ACCESS_TOKEN,
        },
        VIN: {
            "tsp_provider": "ATC",
        },
    }
    return conn


def _mock_resp(status: int = 200, json_data=None, text_data: str = ""):
    """Build a lightweight mock aiohttp response."""
    r = MagicMock()
    r.status = status
    r.json = AsyncMock(return_value=json_data if json_data is not None else {})
    r.text = AsyncMock(return_value=text_data)
    return r


def _read_source() -> str:
    """Read vw_connection.py source code."""
    return VW_CONNECTION_SRC.read_text()


# ---------------------------------------------------------------------------
# C-2: SPIN Never Logged in Plaintext
# ---------------------------------------------------------------------------

class SpinRedactionTest(IsolatedAsyncioTestCase):
    """Tests for C-2: SPIN plaintext never appears in log output."""

    @patch("volkswagencarnet.vw_connection.jwt.decode")
    async def test_spin_hash_length_logged_not_spin_value(self, mock_jwt):
        """During vehicle session challenge, log shows hash length, not SPIN value."""
        mock_jwt.side_effect = [{"sub": USER_ID}, {"exp": int(time.time()) + 3600}]
        conn = _make_na_connection_with_tokens(spin=FAKE_SPIN)

        challenge_resp = _mock_resp(200, {"challenge": FAKE_CHALLENGE, "remainingTries": 6})
        conn._session.get = AsyncMock(return_value=challenge_resp)
        conn._session.post = AsyncMock(
            return_value=_mock_resp(200, {"carnetVehicleToken": "fake-vehicle-token"})
        )

        with self.assertLogs("volkswagencarnet.vw_connection", level="DEBUG") as log:
            await conn._create_na_vehicle_session(VIN)

        all_logs = "\n".join(log.output)
        # SPIN value must NOT appear in any log line
        self.assertNotIn(FAKE_SPIN, all_logs)
        # Hash length must appear (SHA-512 hex = 128 chars)
        self.assertIn("len=128", all_logs)

    def test_no_self_spin_in_logger_calls(self):
        """Source code contains no _LOGGER call that logs self._spin directly."""
        source = _read_source()
        # Match _LOGGER.{level}(...self._spin...) patterns
        matches = re.findall(r'_LOGGER\.\w+\([^)]*self\._spin[^)]*\)', source)
        self.assertEqual(
            len(matches), 0,
            f"Found {len(matches)} _LOGGER call(s) referencing self._spin: {matches}"
        )

    @patch("volkswagencarnet.vw_connection.jwt.decode")
    async def test_spin_redaction_with_no_spin_set(self, mock_jwt):
        """When no SPIN is set, no SPIN-related data appears in logs at all."""
        mock_jwt.side_effect = [{"sub": USER_ID}, {"exp": int(time.time()) + 3600}]
        conn = _make_na_connection_with_tokens(spin=None)  # No SPIN

        conn._session.post = AsyncMock(
            return_value=_mock_resp(200, {"carnetVehicleToken": "fake-vehicle-token"})
        )
        conn._session.get = AsyncMock()  # Should not be called for challenge

        with self.assertLogs("volkswagencarnet.vw_connection", level="DEBUG") as log:
            await conn._create_na_vehicle_session(VIN)

        all_logs = "\n".join(log.output)
        # No spinHash or challenge mentions when SPIN is not set
        self.assertNotIn("spinHash computed", all_logs)
        conn._session.get.assert_not_called()

    @patch("volkswagencarnet.vw_connection.jwt.decode")
    async def test_challenge_response_logs_only_key_names(self, mock_jwt):
        """Challenge response logs only dictionary key names, not values."""
        mock_jwt.side_effect = [{"sub": USER_ID}, {"exp": int(time.time()) + 3600}]
        conn = _make_na_connection_with_tokens(spin=FAKE_SPIN)

        challenge_data = {"challenge": FAKE_CHALLENGE, "remainingTries": 6}
        conn._session.get = AsyncMock(return_value=_mock_resp(200, challenge_data))
        conn._session.post = AsyncMock(
            return_value=_mock_resp(200, {"carnetVehicleToken": "fake-token"})
        )

        with self.assertLogs("volkswagencarnet.vw_connection", level="DEBUG") as log:
            await conn._create_na_vehicle_session(VIN)

        all_logs = "\n".join(log.output)
        # Challenge hex value must NOT appear in logs
        self.assertNotIn(FAKE_CHALLENGE, all_logs)
        # Key names should appear (from list(challenge_resp_data.keys()))
        self.assertIn("challenge", all_logs)  # key name in the list


# ---------------------------------------------------------------------------
# C-3: Auth Headers Logged as Key Names Only
# ---------------------------------------------------------------------------

class AuthHeaderRedactionTest(IsolatedAsyncioTestCase):
    """Tests for C-3: Auth headers logged as key names only."""

    async def test_get_authorization_page_logs_header_keys_only(self):
        """get_authorization_page logs header key names, not header values."""
        conn = _make_na_connection()
        conn._session_auth_headers = {
            "Authorization": f"Bearer {FAKE_IDK_ACCESS_TOKEN}",
            "Accept": "text/html",
            "User-Agent": "okhttp/5.0.0-alpha.2",
        }
        conn._session_region_config = {
            "redirect_uri": "kombi:///login",
            "scope": "openid",
        }
        conn._client_id = "test-client-id"
        conn._session_country = "US"

        # Mock the HTTP response to return a redirect
        mock_resp = MagicMock()
        mock_resp.status = 302
        mock_resp.headers = {"Location": "https://identity.na.vwgroup.io/login"}
        mock_resp.text = AsyncMock(return_value="")
        conn._session.get = AsyncMock(return_value=mock_resp)

        with self.assertLogs("volkswagencarnet.vw_connection", level="DEBUG") as log:
            try:
                await conn.get_authorization_page("https://identity.na.vwgroup.io/authorize")
            except Exception:
                pass  # We only care about the log output

        all_logs = "\n".join(log.output)
        # Token value must NOT appear in logs
        self.assertNotIn(FAKE_IDK_ACCESS_TOKEN, all_logs)
        self.assertNotIn("eyJ0eXA", all_logs)  # JWT prefix
        # Key names SHOULD appear
        self.assertIn("Request header keys", all_logs)

    async def test_auth_header_log_contains_no_bearer_tokens(self):
        """No Bearer token string appears in any log from get_authorization_page."""
        conn = _make_na_connection()
        conn._session_auth_headers = {
            "Authorization": "Bearer super-secret-token-12345",
            "Accept": "text/html",
        }
        conn._session_region_config = {"redirect_uri": "kombi:///login", "scope": "openid"}
        conn._client_id = "test-client-id"
        conn._session_country = "US"

        mock_resp = MagicMock()
        mock_resp.status = 302
        mock_resp.headers = {"Location": "https://identity.na.vwgroup.io/login"}
        mock_resp.text = AsyncMock(return_value="")
        conn._session.get = AsyncMock(return_value=mock_resp)

        with self.assertLogs("volkswagencarnet.vw_connection", level="DEBUG") as log:
            try:
                await conn.get_authorization_page("https://identity.na.vwgroup.io/authorize")
            except Exception:
                pass

        all_logs = "\n".join(log.output)
        self.assertNotIn("super-secret-token-12345", all_logs)
        self.assertNotIn("Bearer ", all_logs)

    async def test_auth_header_keys_logged_as_python_list(self):
        """Header key names are logged as a Python list (e.g., ['Authorization', 'Accept'])."""
        conn = _make_na_connection()
        conn._session_auth_headers = {
            "Authorization": "Bearer secret",
            "Accept": "text/html",
        }
        conn._session_region_config = {"redirect_uri": "kombi:///login", "scope": "openid"}
        conn._client_id = "test-client-id"
        conn._session_country = "US"

        mock_resp = MagicMock()
        mock_resp.status = 302
        mock_resp.headers = {"Location": "https://identity.na.vwgroup.io/login"}
        mock_resp.text = AsyncMock(return_value="")
        conn._session.get = AsyncMock(return_value=mock_resp)

        with self.assertLogs("volkswagencarnet.vw_connection", level="DEBUG") as log:
            try:
                await conn.get_authorization_page("https://identity.na.vwgroup.io/authorize")
            except Exception:
                pass

        all_logs = "\n".join(log.output)
        # Should contain the key names in list format
        self.assertIn("Authorization", all_logs)
        self.assertIn("Accept", all_logs)


# ---------------------------------------------------------------------------
# H-4: _request() Logs Only Status Code and URL
# ---------------------------------------------------------------------------

class RequestLoggingTest(IsolatedAsyncioTestCase):
    """Tests for H-4: _request() logs only status code and URL, no response body/headers."""

    def test_no_response_body_in_request_debug_logs(self):
        """_request() method source contains no log of response body or full headers."""
        source = _read_source()
        # Find the _request method body
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "_request":
                request_source = ast.get_source_segment(source, node)
                if request_source:
                    # No response.headers in any _LOGGER call
                    header_log_matches = re.findall(
                        r'_LOGGER\.\w+\([^)]*response\.headers[^)]*\)',
                        request_source
                    )
                    self.assertEqual(
                        len(header_log_matches), 0,
                        f"Found response.headers in _LOGGER calls: {header_log_matches}"
                    )
                    # No response body (response.text or await response.text()) in _LOGGER calls
                    body_log_matches = re.findall(
                        r'_LOGGER\.\w+\([^)]*(?:response\.text|resp_text|response_body)[^)]*\)',
                        request_source
                    )
                    self.assertEqual(
                        len(body_log_matches), 0,
                        f"Found response body in _LOGGER calls: {body_log_matches}"
                    )
                break

    def test_request_debug_logs_contain_status_and_url_only(self):
        """Verify the _request() logging pattern: only status code and URL."""
        source = _read_source()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "_request":
                request_source = ast.get_source_segment(source, node)
                if request_source:
                    # The success log should reference status and URL
                    self.assertIn('response.status', request_source)
                    self.assertIn('url', request_source)
                break

    def test_no_bare_response_text_in_request_method(self):
        """_request() contains no bare response.text (coroutine reference without call)."""
        source = _read_source()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "_request":
                request_source = ast.get_source_segment(source, node)
                if request_source:
                    # Find response.text NOT followed by ( — bare coroutine reference
                    bare_text_refs = re.findall(r'response\.text(?!\s*\()', request_source)
                    self.assertEqual(
                        len(bare_text_refs), 0,
                        f"Found {len(bare_text_refs)} bare response.text reference(s) in _request()"
                    )
                break


# ---------------------------------------------------------------------------
# H-1: Dead _discover_endpoints Method Removed
# ---------------------------------------------------------------------------

class DeadCodeRemovalTest(IsolatedAsyncioTestCase):
    """Tests for H-1: _discover_endpoints dead code is removed."""

    def test_connection_has_no_discover_endpoints_method(self):
        """Connection class does not have a _discover_endpoints method."""
        self.assertFalse(
            hasattr(Connection, "_discover_endpoints"),
            "Connection still has _discover_endpoints method — should be removed"
        )

    def test_no_discover_endpoints_reference_in_source(self):
        """No reference to '_discover_endpoints' exists anywhere in vw_connection.py."""
        source = _read_source()
        matches = re.findall(r'_discover_endpoints', source)
        self.assertEqual(
            len(matches), 0,
            f"Found {len(matches)} reference(s) to _discover_endpoints in source"
        )


# ---------------------------------------------------------------------------
# H-2: doLogin Retry Loop Fix (for/else pattern)
# ---------------------------------------------------------------------------

class DoLoginRetryTest(IsolatedAsyncioTestCase):
    """Tests for H-2: doLogin retry loop uses for/else with correct exhaustion."""

    async def test_doLogin_returns_false_on_single_failure(self):
        """doLogin(tries=1) returns False when the single login attempt fails."""
        conn = _make_na_connection()
        conn._login = AsyncMock(return_value=False)
        conn._discover_market_config = AsyncMock(return_value=True)

        result = await conn.doLogin(tries=1)

        self.assertFalse(result)
        self.assertEqual(conn._login.call_count, 1)

    async def test_doLogin_succeeds_on_second_attempt(self):
        """doLogin(tries=3) succeeds when second login attempt returns True."""
        conn = _make_na_connection()
        conn._login = AsyncMock(side_effect=[False, True])
        conn._discover_market_config = AsyncMock(return_value=True)
        conn._session_tokens = {"identity": {"access_token": "test", "id_token": "test-id"}}
        conn._session_headers = {"Authorization": ""}

        # Mock _request (used by NA garage endpoint fetch after login)
        conn._request = AsyncMock(return_value={"data": {"vehicles": []}})
        # Mock update() — called after vehicle list is populated
        conn.update = AsyncMock()

        with patch("volkswagencarnet.vw_connection.asyncio.sleep", new_callable=AsyncMock):
            result = await conn.doLogin(tries=3)

        self.assertTrue(result)
        self.assertEqual(conn._login.call_count, 2)

    @patch("volkswagencarnet.vw_connection.asyncio.sleep", new_callable=AsyncMock)
    async def test_doLogin_returns_false_after_exhausting_all_tries(self, mock_sleep):
        """doLogin(tries=3) returns False after all 3 attempts fail."""
        conn = _make_na_connection()
        conn._login = AsyncMock(return_value=False)
        conn._discover_market_config = AsyncMock(return_value=True)

        result = await conn.doLogin(tries=3)

        self.assertFalse(result)
        self.assertEqual(conn._login.call_count, 3)

    @patch("volkswagencarnet.vw_connection.asyncio.sleep", new_callable=AsyncMock)
    async def test_doLogin_logs_error_on_exhaustion(self, mock_sleep):
        """doLogin logs an error message when all retry attempts are exhausted."""
        conn = _make_na_connection()
        conn._login = AsyncMock(return_value=False)
        conn._discover_market_config = AsyncMock(return_value=True)

        with self.assertLogs("volkswagencarnet.vw_connection", level="ERROR") as log:
            await conn.doLogin(tries=2)

        all_logs = "\n".join(log.output)
        self.assertIn("Login failed after", all_logs)
        self.assertIn("2", all_logs)  # tries count

    @patch("volkswagencarnet.vw_connection.asyncio.sleep", new_callable=AsyncMock)
    async def test_doLogin_sleeps_between_retries_but_not_after_last(self, mock_sleep):
        """Sleep is called between retry attempts but not after the final failure."""
        conn = _make_na_connection()
        conn._login = AsyncMock(return_value=False)
        conn._discover_market_config = AsyncMock(return_value=True)

        await conn.doLogin(tries=3)

        # With 3 tries, sleep should be called 2 times (between attempt 0→1 and 1→2)
        self.assertEqual(mock_sleep.call_count, 2)

    def test_doLogin_uses_for_else_pattern(self):
        """doLogin source code uses for/else pattern (not if i > tries)."""
        source = _read_source()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "doLogin":
                doLogin_source = ast.get_source_segment(source, node)
                if doLogin_source:
                    # Should contain for/else pattern
                    self.assertIn("for i in range(tries)", doLogin_source)
                    # Should NOT contain the old broken pattern
                    self.assertNotIn("if i > tries", doLogin_source)
                    self.assertNotIn("if i >= tries", doLogin_source)
                break


# ---------------------------------------------------------------------------
# H-3: response.text Bare Coroutine Bug Eliminated
# ---------------------------------------------------------------------------

class ResponseTextCoroutineBugTest(IsolatedAsyncioTestCase):
    """Tests for H-3: No bare response.text (without parentheses) in log calls."""

    def test_no_bare_response_text_in_logger_calls(self):
        """No _LOGGER call references response.text without () — would be a coroutine object."""
        source = _read_source()
        # Pattern: _LOGGER.{level}(...response.text...) where .text is NOT followed by (
        # This catches the bug where response.text was logged as a coroutine object
        matches = re.findall(r'_LOGGER\.\w+\([^)]*response\.text(?!\s*\()[^)]*\)', source)
        self.assertEqual(
            len(matches), 0,
            f"Found {len(matches)} _LOGGER call(s) with bare response.text: {matches}"
        )

    def test_all_response_text_calls_have_parentheses(self):
        """Every response.text in the source is followed by () (properly called)."""
        source = _read_source()
        # Find all response.text occurrences
        all_response_text = list(re.finditer(r'response\.text', source))
        for match in all_response_text:
            after = source[match.end():match.end() + 5].strip()
            self.assertTrue(
                after.startswith("("),
                f"Found bare response.text at position {match.start()}: "
                f"...{source[max(0, match.start()-20):match.end()+20]}..."
            )


# ---------------------------------------------------------------------------
# H-6: Stale pylint disable=unreachable Comment Removed
# ---------------------------------------------------------------------------

class StalePylintCommentTest(IsolatedAsyncioTestCase):
    """Tests for H-6: No stale pylint disable=unreachable comment."""

    def test_no_pylint_disable_unreachable_in_source(self):
        """vw_connection.py contains no 'pylint: disable=unreachable' comment."""
        source = _read_source()
        matches = re.findall(r'pylint:\s*disable=unreachable', source)
        self.assertEqual(
            len(matches), 0,
            f"Found {len(matches)} stale 'pylint: disable=unreachable' comment(s)"
        )


# ---------------------------------------------------------------------------
# C-1 / H-5: Git Tracking (Structural Tests)
# ---------------------------------------------------------------------------

class GitIgnoreStructureTest(IsolatedAsyncioTestCase):
    """Tests for C-1/H-5: .gitignore contains proper credential and docs rules."""

    def test_gitignore_has_explicit_testing_creds_entry(self):
        """'.gitignore' explicitly lists 'testing_creds.env' (not just *.env glob)."""
        gitignore = (Path(__file__).parent.parent / ".gitignore").read_text()
        self.assertIn("testing_creds.env", gitignore)

    def test_gitignore_has_docs_directory_rule(self):
        """'.gitignore' contains a docs/ directory exclusion rule."""
        gitignore = (Path(__file__).parent.parent / ".gitignore").read_text()
        self.assertIn("docs/", gitignore)

    def test_gitignore_has_env_glob_rule(self):
        """'.gitignore' contains *.env glob pattern for general credential files."""
        gitignore = (Path(__file__).parent.parent / ".gitignore").read_text()
        self.assertIn("*.env", gitignore)


# ---------------------------------------------------------------------------
# Integration: Verify All Phase 21 Fixes Coexist
# ---------------------------------------------------------------------------

class Phase21IntegrationTest(IsolatedAsyncioTestCase):
    """Integration tests verifying Phase 21 fixes don't regress each other."""

    def test_connection_class_is_importable(self):
        """Connection class imports without error after all Phase 21 changes."""
        from volkswagencarnet.vw_connection import Connection as Conn
        self.assertTrue(callable(Conn))

    def test_connection_has_expected_login_method(self):
        """Connection.doLogin still exists and is async after retry loop fix."""
        self.assertTrue(hasattr(Connection, "doLogin"))
        self.assertTrue(inspect.iscoroutinefunction(Connection.doLogin))

    def test_connection_has_request_method(self):
        """Connection._request still exists after response body log removal."""
        self.assertTrue(hasattr(Connection, "_request"))
        self.assertTrue(inspect.iscoroutinefunction(Connection._request))

    def test_connection_has_get_authorization_page(self):
        """Connection.get_authorization_page still exists after header log fix."""
        self.assertTrue(hasattr(Connection, "get_authorization_page"))
        self.assertTrue(inspect.iscoroutinefunction(Connection.get_authorization_page))

    def test_connection_still_has_discover_market_config(self):
        """_discover_market_config (live discovery) still exists — only dead _discover_endpoints removed."""
        self.assertTrue(hasattr(Connection, "_discover_market_config"))

    async def test_na_connection_initialization_after_dead_code_removal(self):
        """NA Connection can be instantiated after _discover_endpoints removal."""
        conn = _make_na_connection()
        self.assertEqual(conn._session_region, "NA")
        self.assertFalse(hasattr(conn, "_discover_endpoints"))
