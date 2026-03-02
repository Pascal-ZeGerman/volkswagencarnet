"""Unit tests for NA Connection vehicle session and RVS data methods (Phase 11).

Tests cover:
- Connection._create_na_vehicle_session(): tsp_provider lookup, JWT parsing, token caching, 401 retry
- Connection._get_na_vehicle_data(): RVS fetch, partial data return, 401 cache invalidation
"""

import json
import time
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from volkswagencarnet.vw_connection import Connection
from volkswagencarnet.vw_exceptions import AuthenticationError

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "resources" / "responses" / "na_vehicle"

VIN = "WVWZZZ3HZPK002581"
FAKE_IDK_ID_TOKEN = "fake.idk.token"
FAKE_IDK_ACCESS_TOKEN = "fake-idk-access-token"
FAKE_VEHICLE_TOKEN = "fake-vehicle-token"
USER_ID = "user-sub-12345"
BASE_API = "https://b-h-s.spr.us00.p.con-veh.net"


def _load_fixture(name: str) -> dict:
    with open(FIXTURE_DIR / name) as f:
        return json.load(f)


def _mock_resp(status: int = 200, json_data=None, text_data: str = ""):
    """Build a lightweight mock aiohttp response."""
    r = MagicMock()
    r.status = status
    r.json = AsyncMock(return_value=json_data if json_data is not None else {})
    r.text = AsyncMock(return_value=text_data)
    return r


def _make_na_connection() -> Connection:
    """Create a minimal NA Connection with a mocked aiohttp session."""
    sess = MagicMock()
    conn = Connection(sess, "user@test.com", "password", country="US")
    conn._base_api = BASE_API
    conn._na_tokens = {
        "idk": {
            "id_token": FAKE_IDK_ID_TOKEN,
            "access_token": FAKE_IDK_ACCESS_TOKEN,
        },
        VIN: {
            "tsp_provider": "ATC",  # stored during doLogin() garage parse
        },
    }
    return conn


FAKE_CHALLENGE = "1D02046F451D9ECCA3E4FB6B564958DF0495A069"
FAKE_SPIN = "1234"
# PinResponse is flat: {"challenge": "<hex>", "remainingTries": N} — no "data" wrapper
FAKE_CHALLENGE_RESP = {"challenge": FAKE_CHALLENGE, "remainingTries": 6}


class NAVehicleSessionTest(IsolatedAsyncioTestCase):
    """Tests for Connection._create_na_vehicle_session()."""

    @patch("volkswagencarnet.vw_connection.jwt.decode")
    async def test_create_session_stores_spin_from_constructor(self, _mock_jwt):
        """Connection stores spin parameter passed at construction time."""
        sess = MagicMock()
        conn = Connection(sess, "user@test.com", "password", country="US", spin=FAKE_SPIN)
        assert conn._spin == FAKE_SPIN

    @patch("volkswagencarnet.vw_connection.jwt.decode")
    async def test_create_session_spin_defaults_to_none(self, _mock_jwt):
        """Connection._spin defaults to None when spin not passed."""
        sess = MagicMock()
        conn = Connection(sess, "user@test.com", "password", country="US")
        assert conn._spin is None

    @patch("volkswagencarnet.vw_connection.jwt.decode")
    async def test_create_session_fetches_challenge_and_includes_spinhash(self, mock_jwt):
        """When spin is set: GET challenge with IDK Bearer + x-user-id, then POST with spinHash.

        APK d20/i.java UserSession interceptor uses AzsSession (= IDK OIDC session) as Bearer
        and adds x-user-id: {userId}. Challenge endpoint accepts IDK access_token + x-user-id.
        """
        mock_jwt.side_effect = [{"sub": USER_ID}, {"exp": int(time.time()) + 3600}]
        conn = _make_na_connection()
        conn._spin = FAKE_SPIN
        # Challenge GET returns flat PinResponse: {"challenge": "<hex>", "remainingTries": N}
        conn._session.get = AsyncMock(return_value=_mock_resp(200, FAKE_CHALLENGE_RESP))
        # Single POST returns a vehicle token
        conn._session.post = AsyncMock(
            return_value=_mock_resp(200, {"carnetVehicleToken": FAKE_VEHICLE_TOKEN})
        )
        result = await conn._create_na_vehicle_session(VIN)
        assert result == FAKE_VEHICLE_TOKEN
        # Challenge GET called once with IDK Bearer + x-user-id header
        assert conn._session.get.call_count == 1
        challenge_call = conn._session.get.call_args_list[0]
        challenge_url = challenge_call[0][0]
        assert f"/ss/v1/user/{USER_ID}/challenge" in challenge_url
        # Bearer is IDK access_token, x-user-id is userId
        challenge_headers = challenge_call.kwargs.get("headers", {})
        assert challenge_headers.get("Authorization") == f"Bearer {FAKE_IDK_ACCESS_TOKEN}"
        assert challenge_headers.get("x-user-id") == USER_ID
        # Single POST called with the computed spinHash (SHA-512 hex = 128 chars)
        assert conn._session.post.call_count == 1
        post_body = conn._session.post.call_args.kwargs["json"]
        assert post_body["spinHash"] is not None
        assert isinstance(post_body["spinHash"], str)
        assert len(post_body["spinHash"]) == 128  # SHA-512 hex = 128 chars

    @patch("volkswagencarnet.vw_connection.jwt.decode")
    async def test_create_session_skips_challenge_and_sends_null_spinhash_when_no_spin(self, mock_jwt):
        """When no spin set, skips challenge GET and sends spinHash=None (server will reject, but cleanly)."""
        mock_jwt.side_effect = [{"sub": USER_ID}, {"exp": int(time.time()) + 3600}]
        conn = _make_na_connection()
        # No spin set (default)
        conn._session.post = AsyncMock(
            return_value=_mock_resp(200, {"carnetVehicleToken": FAKE_VEHICLE_TOKEN})
        )
        # GET should NOT be called for challenge
        conn._session.get = AsyncMock()
        await conn._create_na_vehicle_session(VIN)
        conn._session.get.assert_not_called()
        post_body = conn._session.post.call_args.kwargs["json"]
        assert post_body["spinHash"] is None

    @patch("volkswagencarnet.vw_connection.jwt.decode", return_value={"sub": USER_ID})
    async def test_create_session_returns_none_when_challenge_fetch_fails(self, _mock_jwt):
        """Returns None when challenge GET fails (non-200).

        Flow: GET challenge (IDK Bearer + x-user-id) → fails → None. Session POST not called.
        """
        conn = _make_na_connection()
        conn._spin = FAKE_SPIN
        # Challenge GET fails (401)
        conn._session.get = AsyncMock(return_value=_mock_resp(401, text_data="Unauthorized"))
        conn._session.post = AsyncMock()
        result = await conn._create_na_vehicle_session(VIN)
        assert result is None
        # Challenge GET must have been attempted exactly once
        assert conn._session.get.call_count == 1
        # Session POST must NOT have been called (no spinHash available)
        conn._session.post.assert_not_called()

    @patch("volkswagencarnet.vw_connection.jwt.decode")
    async def test_create_session_returns_none_when_idk_missing(self, mock_jwt):
        """Returns None immediately when no IDK id_token is present."""
        conn = _make_na_connection()
        conn._na_tokens = {}  # no idk key
        result = await conn._create_na_vehicle_session(VIN)
        assert result is None
        mock_jwt.assert_not_called()

    @patch("volkswagencarnet.vw_connection.jwt.decode", side_effect=Exception("bad jwt"))
    async def test_create_session_returns_none_on_invalid_jwt(self, _mock_jwt):
        """Returns None when IDK id_token fails JWT decode (sub claim unavailable)."""
        conn = _make_na_connection()
        result = await conn._create_na_vehicle_session(VIN)
        assert result is None

    @patch("volkswagencarnet.vw_connection.jwt.decode", return_value={"sub": USER_ID})
    async def test_create_session_returns_cached_token(self, _mock_jwt):
        """Returns the cached vehicle token without any HTTP call when cache is fresh."""
        conn = _make_na_connection()
        conn._na_tokens[VIN] = {
            "vehicle_session": {
                "token": "cached-vehicle-token",
                "expires_at": time.time() + 3600,  # 1 hour in the future
                "issued_at": time.time(),
            }
        }
        result = await conn._create_na_vehicle_session(VIN)
        assert result == "cached-vehicle-token"
        conn._session.post.assert_not_called()

    @patch("volkswagencarnet.vw_connection.jwt.decode")
    async def test_create_session_uses_tsp_provider_from_na_tokens(self, mock_jwt):
        """Session POST uses tsp value from _na_tokens[vin]['tsp_provider']."""
        mock_jwt.side_effect = [{"sub": USER_ID}, {"exp": int(time.time()) + 3600}]
        conn = _make_na_connection()
        conn._na_tokens[VIN]["tsp_provider"] = "ATC"
        conn._session.post = AsyncMock(
            return_value=_mock_resp(200, {"carnetVehicleToken": FAKE_VEHICLE_TOKEN})
        )
        result = await conn._create_na_vehicle_session(VIN)
        assert result == FAKE_VEHICLE_TOKEN
        assert conn._session.post.call_count == 1  # single attempt, no probe loop
        call = conn._session.post.call_args_list[0]
        assert call.kwargs["json"]["tsp"] == "ATC"

    @patch("volkswagencarnet.vw_connection.jwt.decode")
    async def test_create_session_defaults_to_atc_when_no_tsp_provider(self, mock_jwt):
        """Falls back to tsp='ATC' when no tsp_provider is stored for the VIN."""
        mock_jwt.side_effect = [{"sub": USER_ID}, {"exp": int(time.time()) + 3600}]
        conn = _make_na_connection()
        # Remove tsp_provider to test default fallback
        conn._na_tokens.pop(VIN, None)
        conn._session.post = AsyncMock(
            return_value=_mock_resp(200, {"carnetVehicleToken": FAKE_VEHICLE_TOKEN})
        )
        result = await conn._create_na_vehicle_session(VIN)
        assert result == FAKE_VEHICLE_TOKEN
        call = conn._session.post.call_args_list[0]
        assert call.kwargs["json"]["tsp"] == "ATC"

    @patch("volkswagencarnet.vw_connection.jwt.decode")
    async def test_create_session_retries_without_auth_on_401(self, mock_jwt):
        """On 401 response, retries the same tsp value without Authorization header."""
        mock_jwt.side_effect = [{"sub": USER_ID}, {"exp": int(time.time()) + 3600}]
        conn = _make_na_connection()
        conn._session.post = AsyncMock(side_effect=[
            _mock_resp(401),                                                 # with auth → rejected
            _mock_resp(200, {"carnetVehicleToken": FAKE_VEHICLE_TOKEN}),    # without auth → success
        ])
        result = await conn._create_na_vehicle_session(VIN)
        assert result == FAKE_VEHICLE_TOKEN
        assert conn._session.post.call_count == 2
        no_auth_call = conn._session.post.call_args_list[1]
        assert "Authorization" not in no_auth_call.kwargs["headers"]

    @patch("volkswagencarnet.vw_connection.jwt.decode")
    async def test_create_session_caches_token_with_exp(self, mock_jwt):
        """Stores token in _na_tokens[vin]['vehicle_session'] with JWT exp as expires_at."""
        future_exp = int(time.time()) + 3600
        mock_jwt.side_effect = [{"sub": USER_ID}, {"exp": future_exp}]
        conn = _make_na_connection()
        conn._session.post = AsyncMock(
            return_value=_mock_resp(200, {"carnetVehicleToken": FAKE_VEHICLE_TOKEN})
        )
        result = await conn._create_na_vehicle_session(VIN)
        assert result == FAKE_VEHICLE_TOKEN
        cached = conn._na_tokens[VIN]["vehicle_session"]
        assert cached["token"] == FAKE_VEHICLE_TOKEN
        assert cached["expires_at"] == future_exp
        assert "issued_at" in cached

    @patch("volkswagencarnet.vw_connection.jwt.decode", return_value={"sub": USER_ID})
    async def test_create_session_returns_none_when_tsp_fails(self, _mock_jwt):
        """Returns None when session POST returns 400 (wrong tsp or invalid request)."""
        conn = _make_na_connection()
        conn._session.post = AsyncMock(return_value=_mock_resp(400, text_data="Bad Request"))
        result = await conn._create_na_vehicle_session(VIN)
        assert result is None
        assert conn._session.post.call_count == 1  # single attempt only


class NAVehicleDataFetchTest(IsolatedAsyncioTestCase):
    """Tests for Connection._get_na_vehicle_data()."""

    async def test_get_na_vehicle_data_returns_none_when_session_fails(self):
        """Returns None when vehicle session creation fails (no token obtainable)."""
        conn = _make_na_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn._create_na_vehicle_session = AsyncMock(return_value=None)
        result = await conn._get_na_vehicle_data(VIN)
        assert result is None

    @patch("volkswagencarnet.vw_connection.asyncio.sleep", new_callable=AsyncMock)
    @patch("volkswagencarnet.vw_connection.jwt.decode", return_value={"sub": USER_ID})
    async def test_get_na_vehicle_data_returns_partial_on_location_failure(self, _mock_jwt, _mock_sleep):
        """Returns {'na_location': None, 'na_status': {...}} when location endpoint always 500s.

        With RVS_MAX_RETRIES=2, the location fetch makes 3 total attempts (1 initial + 2 retries)
        before giving up. The status fetch then succeeds on first try.
        """
        status_fixture = _load_fixture("rvs_status.json")
        conn = _make_na_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn._create_na_vehicle_session = AsyncMock(return_value=FAKE_VEHICLE_TOKEN)
        conn._session.get = AsyncMock(side_effect=[
            _mock_resp(500, text_data="Internal Server Error"),  # location attempt 1 → retry
            _mock_resp(500, text_data="Internal Server Error"),  # location attempt 2 → retry
            _mock_resp(500, text_data="Internal Server Error"),  # location attempt 3 → give up
            _mock_resp(200, json_data=status_fixture),           # status succeeds
        ])
        result = await conn._get_na_vehicle_data(VIN)
        assert result is not None
        assert result["na_location"] is None
        assert result["na_status"] == status_fixture

    @patch("volkswagencarnet.vw_connection.asyncio.sleep", new_callable=AsyncMock)
    @patch("volkswagencarnet.vw_connection.jwt.decode", return_value={"sub": USER_ID})
    async def test_get_na_vehicle_data_returns_partial_on_status_failure(self, _mock_jwt, _mock_sleep):
        """Returns {'na_location': {...}, 'na_status': None} when status endpoint always 500s.

        With RVS_MAX_RETRIES=2, the status fetch makes 3 total attempts (1 initial + 2 retries)
        before giving up.
        """
        location_fixture = _load_fixture("rvs_location.json")
        conn = _make_na_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn._create_na_vehicle_session = AsyncMock(return_value=FAKE_VEHICLE_TOKEN)
        conn._session.get = AsyncMock(side_effect=[
            _mock_resp(200, json_data=location_fixture),        # location succeeds
            _mock_resp(500, text_data="Internal Server Error"), # status attempt 1 → retry
            _mock_resp(500, text_data="Internal Server Error"), # status attempt 2 → retry
            _mock_resp(500, text_data="Internal Server Error"), # status attempt 3 → give up
        ])
        result = await conn._get_na_vehicle_data(VIN)
        assert result is not None
        assert result["na_location"] == location_fixture
        assert result["na_status"] is None

    @patch("volkswagencarnet.vw_connection.jwt.decode", return_value={"sub": USER_ID})
    async def test_get_na_vehicle_data_invalidates_cache_on_401(self, _mock_jwt):
        """On 401 from RVS: clears vehicle_session cache and retries with fresh token."""
        location_fixture = _load_fixture("rvs_location.json")
        status_fixture = _load_fixture("rvs_status.json")
        conn = _make_na_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        # _create_na_vehicle_session is called twice: initial + post-401 refresh
        conn._create_na_vehicle_session = AsyncMock(return_value=FAKE_VEHICLE_TOKEN)
        conn._session.get = AsyncMock(side_effect=[
            _mock_resp(401),                              # location first attempt → 401
            _mock_resp(200, json_data=location_fixture),  # location retry → success
            _mock_resp(200, json_data=status_fixture),    # status → success
        ])
        result = await conn._get_na_vehicle_data(VIN)
        assert result is not None
        assert result["na_location"] == location_fixture
        assert result["na_status"] == status_fixture
        # Session was refreshed: _create_na_vehicle_session called twice
        assert conn._create_na_vehicle_session.call_count == 2


class NARVSCacheTest(IsolatedAsyncioTestCase):
    """Tests for RVS TTL cache behavior in Connection._get_na_vehicle_data()."""

    @patch("volkswagencarnet.vw_connection.jwt.decode", return_value={"sub": USER_ID})
    async def test_rvs_cache_prevents_second_api_call(self, _mock_jwt):
        """Two consecutive calls within TTL: second returns cached data with zero extra HTTP calls."""
        location_fixture = _load_fixture("rvs_location.json")
        status_fixture = _load_fixture("rvs_status.json")
        conn = _make_na_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn._create_na_vehicle_session = AsyncMock(return_value=FAKE_VEHICLE_TOKEN)
        conn._session.get = AsyncMock(side_effect=[
            _mock_resp(200, json_data=location_fixture),
            _mock_resp(200, json_data=status_fixture),
        ])
        result1 = await conn._get_na_vehicle_data(VIN)
        call_count_after_first = conn._session.get.call_count
        result2 = await conn._get_na_vehicle_data(VIN)
        # Second call should NOT have made additional HTTP requests
        assert conn._session.get.call_count == call_count_after_first
        # Both results must be identical
        assert result1 == result2
        assert result1 is not None

    @patch("volkswagencarnet.vw_connection.jwt.decode", return_value={"sub": USER_ID})
    async def test_rvs_cache_expires_after_ttl(self, _mock_jwt):
        """Cache entry past TTL triggers new HTTP requests on second call."""
        location_fixture = _load_fixture("rvs_location.json")
        status_fixture = _load_fixture("rvs_status.json")
        conn = _make_na_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn._create_na_vehicle_session = AsyncMock(return_value=FAKE_VEHICLE_TOKEN)
        conn._session.get = AsyncMock(side_effect=[
            _mock_resp(200, json_data=location_fixture),
            _mock_resp(200, json_data=status_fixture),
            _mock_resp(200, json_data=location_fixture),
            _mock_resp(200, json_data=status_fixture),
        ])
        await conn._get_na_vehicle_data(VIN)
        call_count_after_first = conn._session.get.call_count
        # Age the cache entry past the TTL (default 30s)
        conn._na_rvs_cache[VIN]["fetched_at"] = time.time() - 31
        await conn._get_na_vehicle_data(VIN)
        # New HTTP calls should have been made
        assert conn._session.get.call_count > call_count_after_first

    @patch("volkswagencarnet.vw_connection.jwt.decode", return_value={"sub": USER_ID})
    async def test_rvs_cache_cleared_on_401(self, _mock_jwt):
        """401 on location fetch clears the RVS cache."""
        location_fixture = _load_fixture("rvs_location.json")
        status_fixture = _load_fixture("rvs_status.json")
        conn = _make_na_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn._create_na_vehicle_session = AsyncMock(return_value=FAKE_VEHICLE_TOKEN)
        # Pre-populate cache
        conn._na_rvs_cache[VIN] = {
            "data": {"na_location": location_fixture, "na_status": status_fixture},
            "fetched_at": time.time() - 31,  # expired so it won't short-circuit
        }
        conn._session.get = AsyncMock(side_effect=[
            _mock_resp(401),                              # location → 401, clears cache
            _mock_resp(200, json_data=location_fixture),  # location retry → success
            _mock_resp(200, json_data=status_fixture),    # status → success
        ])
        result = await conn._get_na_vehicle_data(VIN)
        assert result is not None
        # During 401 handling, cache was cleared; then re-populated with fresh data
        assert conn._na_rvs_cache.get(VIN) is not None
        assert conn._na_rvs_cache[VIN]["data"]["na_location"] == location_fixture

    @patch("volkswagencarnet.vw_connection.jwt.decode", return_value={"sub": USER_ID})
    async def test_rvs_cache_respects_custom_ttl(self, _mock_jwt):
        """Custom TTL of 5s: cache aged 6s triggers new fetch."""
        location_fixture = _load_fixture("rvs_location.json")
        status_fixture = _load_fixture("rvs_status.json")
        conn = _make_na_connection()
        conn._rvs_cache_ttl = 5
        conn.validate_tokens = AsyncMock(return_value=True)
        conn._create_na_vehicle_session = AsyncMock(return_value=FAKE_VEHICLE_TOKEN)
        # Pre-populate cache with expired entry (6s > 5s TTL)
        conn._na_rvs_cache[VIN] = {
            "data": {"na_location": location_fixture, "na_status": status_fixture},
            "fetched_at": time.time() - 6,
        }
        conn._session.get = AsyncMock(side_effect=[
            _mock_resp(200, json_data=location_fixture),
            _mock_resp(200, json_data=status_fixture),
        ])
        result = await conn._get_na_vehicle_data(VIN)
        assert result is not None
        # New HTTP calls were made (cache was stale)
        assert conn._session.get.call_count == 2


class NAErrorPathTest(IsolatedAsyncioTestCase):
    """Tests for NA error paths: token exchange failure, garage 404, RVS 5xx."""

    async def test_token_exchange_failure_raises_auth_error(self):
        """_exchange_code_for_tokens raises AuthenticationError on HTTP 400."""
        conn = _make_na_connection()
        conn._pkce_verifier = "test-verifier"
        conn._session_auth_headers = {}
        conn._session_region_config = {"redirect_uri": "kombi:///login"}
        conn._session.post = AsyncMock(
            return_value=_mock_resp(400, text_data='{"error":"invalid_grant"}')
        )
        with self.assertRaises(AuthenticationError) as ctx:
            await conn._exchange_code_for_tokens("bad-code", "https://example.com/token")
        assert "400" in str(ctx.exception)

    async def test_validate_tokens_false_causes_get_na_vehicle_data_to_return_none(self):
        """When validate_tokens() returns False, _get_na_vehicle_data exits early with None."""
        conn = _make_na_connection()
        conn.validate_tokens = AsyncMock(return_value=False)
        conn._create_na_vehicle_session = AsyncMock()
        result = await conn._get_na_vehicle_data(VIN)
        assert result is None
        # _create_na_vehicle_session should NOT be called (early exit)
        conn._create_na_vehicle_session.assert_not_called()

    @patch("volkswagencarnet.vw_connection.asyncio.sleep", new_callable=AsyncMock)
    @patch("volkswagencarnet.vw_connection.jwt.decode", return_value={"sub": USER_ID})
    async def test_rvs_5xx_on_both_endpoints_returns_none_values(self, _mock_jwt, _mock_sleep):
        """RVS 5xx on both location and status returns dict with None values, no exception.

        With RVS_MAX_RETRIES=2: 3 attempts per endpoint = 6 total GET calls.
        """
        conn = _make_na_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn._create_na_vehicle_session = AsyncMock(return_value=FAKE_VEHICLE_TOKEN)
        conn._session.get = AsyncMock(side_effect=[
            _mock_resp(500, text_data="Internal Server Error"),  # location attempt 1
            _mock_resp(500, text_data="Internal Server Error"),  # location attempt 2
            _mock_resp(500, text_data="Internal Server Error"),  # location attempt 3
            _mock_resp(500, text_data="Internal Server Error"),  # status attempt 1
            _mock_resp(500, text_data="Internal Server Error"),  # status attempt 2
            _mock_resp(500, text_data="Internal Server Error"),  # status attempt 3
        ])
        result = await conn._get_na_vehicle_data(VIN)
        assert result is not None
        assert result == {"na_location": None, "na_status": None}
        # 6 total GET calls (3 location retries + 3 status retries)
        assert conn._session.get.call_count == 6


class NATokenValidationTest(IsolatedAsyncioTestCase):
    """Tests for NA token validation and IDK refresh failure paths."""

    async def test_idk_refresh_failure_triggers_relogin_via_validate_tokens(self):
        """Expired IDK + _refresh_idk_token raising AuthenticationError -> _validate_na_tokens returns False."""
        conn = _make_na_connection()
        # Set IDK token as expired
        conn._na_tokens["idk"]["expires_at"] = time.time() - 100
        conn._na_tokens["idk"]["issued_at"] = time.time() - 3700
        conn._refresh_idk_token = AsyncMock(side_effect=AuthenticationError("refresh failed"))
        result = await conn._validate_na_tokens()
        assert result is False
        conn._refresh_idk_token.assert_called_once()

    async def test_validate_na_tokens_returns_false_on_empty_na_tokens(self):
        """_validate_na_tokens() returns False when _na_tokens is empty."""
        conn = _make_na_connection()
        conn._na_tokens = {}
        result = await conn._validate_na_tokens()
        assert result is False
