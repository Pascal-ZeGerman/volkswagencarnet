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
FAKE_CHALLENGE_RESP = {"data": {"challenge": FAKE_CHALLENGE, "remainingTries": 6}}


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
        """When spin is set, fetches challenge via GET then includes spinHash in session POST."""
        mock_jwt.side_effect = [{"sub": USER_ID}, {"exp": int(time.time()) + 3600}]
        conn = _make_na_connection()
        conn._spin = FAKE_SPIN
        conn._session.get = AsyncMock(return_value=_mock_resp(200, FAKE_CHALLENGE_RESP))
        conn._session.post = AsyncMock(
            return_value=_mock_resp(200, {"carnetVehicleToken": FAKE_VEHICLE_TOKEN})
        )
        result = await conn._create_na_vehicle_session(VIN)
        assert result == FAKE_VEHICLE_TOKEN
        # Challenge GET must have been called with IDK auth header
        assert conn._session.get.call_count == 1
        challenge_call = conn._session.get.call_args
        challenge_url = challenge_call[0][0]
        assert f"/ss/v1/user/{USER_ID}/challenge" in challenge_url
        assert challenge_call.kwargs["headers"]["Authorization"] == f"Bearer {FAKE_IDK_ACCESS_TOKEN}"
        # spinHash must be non-null in session POST body
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
        """Returns None when challenge GET fails (non-200)."""
        conn = _make_na_connection()
        conn._spin = FAKE_SPIN
        conn._session.get = AsyncMock(return_value=_mock_resp(500, text_data="Server Error"))
        result = await conn._create_na_vehicle_session(VIN)
        assert result is None
        # Session POST must NOT be called after challenge failure
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

    @patch("volkswagencarnet.vw_connection.jwt.decode", return_value={"sub": USER_ID})
    async def test_get_na_vehicle_data_returns_partial_on_location_failure(self, _mock_jwt):
        """Returns {'na_location': None, 'na_status': {...}} when location endpoint fails."""
        status_fixture = _load_fixture("rvs_status.json")
        conn = _make_na_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn._create_na_vehicle_session = AsyncMock(return_value=FAKE_VEHICLE_TOKEN)
        conn._session.get = AsyncMock(side_effect=[
            _mock_resp(500, text_data="Internal Server Error"),  # location fails
            _mock_resp(200, json_data=status_fixture),           # status succeeds
        ])
        result = await conn._get_na_vehicle_data(VIN)
        assert result is not None
        assert result["na_location"] is None
        assert result["na_status"] == status_fixture

    @patch("volkswagencarnet.vw_connection.jwt.decode", return_value={"sub": USER_ID})
    async def test_get_na_vehicle_data_returns_partial_on_status_failure(self, _mock_jwt):
        """Returns {'na_location': {...}, 'na_status': None} when status endpoint fails."""
        location_fixture = _load_fixture("rvs_location.json")
        conn = _make_na_connection()
        conn.validate_tokens = AsyncMock(return_value=True)
        conn._create_na_vehicle_session = AsyncMock(return_value=FAKE_VEHICLE_TOKEN)
        conn._session.get = AsyncMock(side_effect=[
            _mock_resp(200, json_data=location_fixture),        # location succeeds
            _mock_resp(500, text_data="Internal Server Error"), # status fails
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
