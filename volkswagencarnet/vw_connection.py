#!/usr/bin/env python3
"""Communicate with Volkswagen Connect services."""

from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import logging
from random import random
import re
import secrets
import time
from urllib.parse import parse_qs, urljoin, urlparse
from typing import Any

from aiohttp import ClientTimeout, client_exceptions
from aiohttp.hdrs import METH_GET, METH_POST, METH_PUT
from bs4 import BeautifulSoup
import jwt

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
    MBB_BRAND_CONFIG,
    USER_AGENT,
    XQMAUTH_PREFIX,
    XQMAUTH_SECRET,
    get_region_from_country,
    get_region_config,
)

from .vw_exceptions import (
    AuthenticationError,
    APIError,
    SPINError,
    RedirectError,
    RequestError,
    TermsAndConditionsError,
)

from .vw_utilities import json_loads, redact
from .vw_vehicle import Vehicle

MAX_RETRIES_ON_RATE_LIMIT = 3
RVS_MAX_RETRIES = 2  # Max retry attempts for transient 5xx on RVS endpoints

VW_DOMAIN_ALLOWLIST = (
    ".vwgroup.io",       # identity.na.vwgroup.io, identity.vwgroup.io
    ".con-veh.net",      # b-h-s.spr.us00.p.con-veh.net (confirmed NA base)
    ".cariad.digital",   # emea.bff.cariad.digital, na.bff.cariad.digital candidates
    ".vwg-connect.com",  # mbboauth-1d.prd.ece.vwg-connect.com
    ".volkswagen.de",    # msg.volkswagen.de (EMEA home region)
    ".volkswagen.com",   # msg.volkswagen.com (NA homeregion candidate)
    ".vw.com",           # msg.vw.com (NA homeregion candidate)
    ".vw.us",            # msg.vw.us (NA homeregion candidate)
)

_LOGGER = logging.getLogger(__name__)  # pylint: disable=unreachable

TIMEOUT = timedelta(seconds=30)
JWT_ALGORITHMS = ["RS256"]


# noinspection PyPep8Naming
class Connection:
    """Connection to VW-Group Connect services."""

    # Init connection class
    def __init__(
        self,
        session: Any,
        username: str,
        password: str,
        country: str = COUNTRY,
        interval: timedelta = timedelta(minutes=5),
        xclient_id: str | None = None,
        on_xclient_id: Any | None = None,
        spin: str | None = None,
    ) -> None:
        """Initialize a Connection to VW Connect services.

        Supports both EMEA (Europe) and North America regions. The region is
        auto-detected from the ``country`` parameter: US and CA route to NA
        endpoints; all other country codes use EMEA (default).

        Args:
            session: An aiohttp ClientSession for HTTP requests.
            username: VW account email address.
            password: VW account password.
            country: ISO 3166-1 alpha-2 country code. Defaults to 'DE'.
                Use 'US' or 'CA' for North America Car-Net.
            interval: Minimum interval between update cycles. Defaults to 5 minutes.
            xclient_id: Optional X-Client-Id header override.
            on_xclient_id: Optional callback invoked when X-Client-Id changes.
            spin: Security PIN for operations that require it (lock/unlock, honk & flash).

        Example:
            >>> async with ClientSession() as session:
            ...     conn = Connection(session, "user@example.com", "pass", country="US")
            ...     await conn.doLogin()
        """
        self._session = session
        self._session_headers = HEADERS_SESSION.copy()
        self._session_auth_headers = HEADERS_AUTH.copy()
        self._session_refresh_interval = interval
        self._session_logged_in = False
        self._session_first_update = False
        self._session_auth_username = username
        self._session_auth_password = password
        self._session_tokens: dict[str, Any] = {}
        self._session_country = country.upper()
        self._spin = spin

        # Determine region from country
        self._session_region = get_region_from_country(self._session_country)
        self._session_region_config = get_region_config(self._session_region)

        # Set region-specific base API (will be discovered for NA)
        self._base_api = self._session_region_config.get("base_api")

        # Set region-specific client ID for OAuth
        self._client_id = self._session_region_config.get("client_id", CLIENT_ID)

        self._vehicles: list[Vehicle] = []

        self._jarCookie = None

        self._service_status: dict[str, Any] = {}
        self._pkce_verifier: str | None = None
        self._pkce_challenge: str | None = None
        self._is_throttled: bool = False
        self.discovery_config: dict = {}

        # NA three-token registry (empty for EMEA, populated during NA login)
        self._na_tokens: dict = {}   # keys: "idk", "brand", "mbb"
        self._xclient_id: str | None = xclient_id  # caller-injected or registered during login
        self._xclient_id_callback = on_xclient_id  # called only when NEW xclientId generated
        self._na_auth_level: str | None = None  # "full", "idk_only", or None (EMEA)
        # Shared lock for login and token refresh (prevents concurrent login+refresh race)
        self._login_lock = asyncio.Lock()
        # NA token endpoint URL (populated during _login_na, needed for IDK refresh)
        self._na_token_endpoint: str | None = None

    def _clear_cookies(self) -> None:
        self._session._cookie_jar._cookies.clear()  # pylint: disable=protected-access

    def _generate_pkce_verifier(self) -> str:
        """Generate PKCE code_verifier.

        Returns:
            Base64URL-encoded random string (43-128 characters)
        """
        # Generate 32 random bytes, base64url encode (43 chars)
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(
            "utf-8"
        )
        # Remove padding
        return code_verifier.rstrip("=")

    def _generate_pkce_challenge(self, code_verifier: str) -> str:
        """Generate PKCE code_challenge from code_verifier.

        Args:
            code_verifier: The code verifier string

        Returns:
            Base64URL-encoded SHA256 hash of the verifier
        """
        # SHA256 hash
        digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        # Base64URL encode
        code_challenge = base64.urlsafe_b64encode(digest).decode("utf-8")
        # Remove padding
        return code_challenge.rstrip("=")

    @staticmethod
    def _calculate_xqmauth(timestamp: float | None = None) -> str:
        """Calculate X-QMAuth header value using HMAC-SHA256.

        The X-QMAuth header is required for IDK token exchange and refresh
        on VW Group platforms. It uses a time-based HMAC with a shared secret.

        Args:
            timestamp: Unix epoch timestamp in seconds. Defaults to current time.
                       Accepts float for deterministic testing with frozen time.

        Returns:
            X-QMAuth header string in format 'v1:01da27b0:<hmac-hex-digest>'
        """
        if timestamp is None:
            timestamp = time.time()
        gmtime_100sec = int(timestamp / 100)
        xqmauth_val = hmac.new(
            XQMAUTH_SECRET,
            str(gmtime_100sec).encode("ascii"),
            digestmod="sha256",
        ).hexdigest()
        return XQMAUTH_PREFIX + xqmauth_val

    def _classify_endpoint(self, url: str) -> str:
        """Classify an API URL to determine which NA token type to use.

        Token routing rules:
        - IDK token: Cariad BFF URLs (self._base_api prefix).
        - MBB token: MBB OAuth service (mbboauth-1d.prd.ece.vwg-connect.com).
        - Brand token: Brand token paths (/login/v1/volkswagen/token or /login/v1/vw/token).

        For EMEA connections, always returns 'idk' (single-token model).

        Args:
            url: The full URL being requested.

        Returns:
            One of: 'idk', 'mbb', 'brand'.

        Raises:
            ValueError: If url does not match any known NA endpoint pattern.
                This is a programmer error — fail loudly.
        """
        if self._session_region != "NA":
            return "idk"  # EMEA always uses the single IDK/access_token

        mbb_host = "mbboauth-1d.prd.ece.vwg-connect.com"
        brand_paths = ("/login/v1/volkswagen/token", "/login/v1/vw/token")

        if mbb_host in url:
            return "mbb"
        if any(path in url for path in brand_paths):
            return "brand"
        if self._base_api and url.startswith(self._base_api):
            return "idk"

        raise ValueError(
            f"Cannot classify NA endpoint — unknown URL pattern: {url!r}. "
            "Add URL to _classify_endpoint() or check base_api configuration."
        )

    def _is_allowed_vw_domain(self, url: str) -> bool:
        """Return True if URL hostname ends with a known VW Group domain suffix."""
        try:
            hostname = urlparse(url).hostname or ""
            return any(hostname.endswith(suffix) for suffix in VW_DOMAIN_ALLOWLIST)
        except Exception:
            return False

    async def _discover_market_config(self) -> bool:
        """Discover and cache market configuration from VW OIDC discovery endpoint.

        Called on every doLogin() for NA region. Uses self.discovery_config as
        session cache guard — if already populated, returns True immediately.
        Validates all URL values against VW_DOMAIN_ALLOWLIST before storing.

        On failure: logs WARNING, leaves self._base_api at hardcoded default,
        sets self._service_status["discovery"] = "Failed". Does NOT block login.

        Returns:
            True if discovery succeeded or was already cached, False on failure.
        """
        if self._session_region != "NA":
            self._service_status["discovery"] = "Skipped"
            return True

        if self.discovery_config:
            # Already discovered this session — use cache
            return True

        candidates = self._session_region_config.get("base_api_candidates", [])
        timeout = ClientTimeout(total=10)

        for candidate in candidates:
            config_url = f"{candidate}/login/v1/idk/openid-configuration"
            try:
                _LOGGER.debug("Attempting market config discovery at %s", config_url)
                async with self._session.get(url=config_url, timeout=timeout) as resp:
                    if resp.status != 200:
                        continue
                    raw_config = await resp.json()

                    # Validate all URL values against allowlist before applying
                    validated = {}
                    for key, value in raw_config.items():
                        if isinstance(value, str) and value.startswith("http"):
                            if not self._is_allowed_vw_domain(value):
                                _LOGGER.warning(
                                    "Discovery: rejected URL %r for key %r (domain not in allowlist)",
                                    value, key,
                                )
                                continue
                        validated[key] = value

                    self.discovery_config = validated
                    self._base_api = candidate
                    self._service_status["discovery"] = "Success"
                    _LOGGER.debug("Market config discovery succeeded via %s", candidate)
                    return True

            except Exception as exc:
                _LOGGER.debug("Config discovery attempt failed for %s: %s", candidate, exc)
                continue

        _LOGGER.warning(
            "Discovery failed, falling back to hardcoded config. "
            "Endpoint %s confirmed working as fallback.",
            self._session_region_config.get("base_api", "unknown"),
        )
        self._service_status["discovery"] = "Failed"
        return False

    async def _discover_endpoints(self) -> bool:
        """Thin alias for _discover_market_config() for backward compatibility.

        Deprecated: Use _discover_market_config() directly.
        """
        return await self._discover_market_config()

    # API Login
    async def doLogin(self, tries: int = 1) -> bool:
        """Authenticate with VW Connect and discover vehicles.

        Performs the full OAuth2 authorization code flow:
        - EMEA: standard flow with IDK + Brand + MBB token exchange.
        - NA (country='US'/'CA'): PKCE-based flow producing a single IDK token.
          NA Car-Net does not support Brand or MBB tokens (auth level: IDK-only).

        After successful authentication, populates ``self.vehicles`` with
        discovered Vehicle objects.

        Args:
            tries: Number of login attempts before giving up. Defaults to 1.

        Returns:
            True if login succeeded and at least one vehicle was discovered,
            False otherwise.

        Raises:
            AuthenticationError: If credentials are invalid or the OAuth flow fails.
            APIError: If the vehicle garage endpoint returns an unexpected error.

        Example:
            >>> if await connection.doLogin():
            ...     print(f"Found {len(connection.vehicles)} vehicles")
        """
        async with self._login_lock:
            _LOGGER.debug("Initiating new login")

            # Discover market config for NA (result cached in self.discovery_config)
            if self._session_region == "NA":
                if not await self._discover_market_config():
                    _LOGGER.warning("Market config discovery failed, using hardcoded values")
                    # Do NOT return False — self._base_api has hardcoded pre-confirmed value

            for i in range(tries):
                self._session_logged_in = await self._login()
                if self._session_logged_in:
                    break
                if i > tries:
                    _LOGGER.error("Login failed after %s tries", tries)
                    return False
                await asyncio.sleep(random() * 5)

            if not self._session_logged_in:
                return False

            _LOGGER.info("Successfully logged in")

            # Get list of vehicles from account
            _LOGGER.debug("Fetching vehicles associated with account")
            self._session_headers.pop("Content-Type", None)

            if self._session_region == "NA":
                # NA uses Car-Net garage endpoint: GET /account/v1/garage?idToken={id_token}
                # Confirmed from APK decompilation: cz.a Retrofit interface @GET("account/v1/garage")
                id_token = self._session_tokens.get("identity", {}).get("id_token", "")
                loaded_vehicles = await self._request(
                    METH_GET,
                    f"{self._base_api}/account/v1/garage",
                    params={"idToken": id_token},
                )
                vehicle_list = loaded_vehicles.get("data", {}).get("vehicles")
            else:
                loaded_vehicles = await self.get(
                    url=f"{self._base_api}/vehicle/v2/vehicles"
                )
                vehicle_list = loaded_vehicles.get("data")

            # Store NA-specific per-VIN metadata for session creation
            if self._session_region == "NA" and vehicle_list:
                for vehicle_data in vehicle_list:
                    vin = vehicle_data.get("vin")
                    if vin:
                        self._na_tokens.setdefault(vin, {})["tsp_provider"] = vehicle_data.get("tspProvider", "ATC")
                        vehicle_id = vehicle_data.get("vehicleId")
                        if vehicle_id:
                            self._na_tokens[vin]["vehicle_id"] = vehicle_id
                        _LOGGER.debug(
                            "NA: stored garage metadata for %s — tspProvider=%r, vehicleId=%r",
                            vin,
                            vehicle_data.get("tspProvider"),
                            vehicle_id,
                        )

            # Add Vehicle class object for all VIN-numbers from account
            if vehicle_list is not None:
                _LOGGER.debug("Found vehicle(s) associated with account")
                self._vehicles = []
                for vehicle in vehicle_list:
                    self._vehicles.append(Vehicle(self, vehicle.get("vin")))
            else:
                if self._session_region == "NA":
                    garage_url = f"{self._base_api}/account/v1/garage"
                    raise APIError(
                        f"NA garage endpoint returned no vehicle list: {garage_url!r}. "
                        "Verify credentials, country='US', and that the account has registered vehicles."
                    )
                _LOGGER.warning("Failed to login to Volkswagen Connect API")
                self._session_logged_in = False
                return False

            # Update all vehicles data before returning
            await self.update()
            return True

    async def get_openid_config(self) -> dict[str, str]:
        """Get OpenID config."""
        # NA: use hardcoded endpoints from region config (app does not fetch well-known)
        auth_ep = self._session_region_config.get("auth_endpoint")
        token_ep = self._session_region_config.get("token_endpoint")
        if auth_ep and token_ep:
            _LOGGER.debug(
                "NA: using hardcoded auth=%s token=%s", auth_ep, token_ep
            )
            return {
                "authorization_endpoint": auth_ep,
                "token_endpoint": token_ep,
            }

        config_url = f"{self._base_api}/login/v1/idk/openid-configuration"
        _LOGGER.debug("Requesting openid config from base API: %s", config_url)
        req = await self._session.get(url=config_url)
        if req.status != 200:
            _LOGGER.error("Failed to get OpenID configuration, status: %s", req.status)
            raise AuthenticationError(
                f"OpenID configuration error: status {req.status}"
            )
        return await req.json()

    async def get_authorization_page(self, authorization_endpoint: str) -> str:
        """Get authorization page (login page)."""
        # https://identity.vwgroup.io/oidc/v1/authorize?nonce={NONCE}&state={STATE}&response_type={TOKEN_TYPES}&scope={SCOPE}&redirect_uri={APP_URI}&client_id={CLIENT_ID}
        # https://identity.vwgroup.io/oidc/v1/authorize?client_id={CLIENT_ID}&scope={SCOPE}&response_type={TOKEN_TYPES}&redirect_uri={APP_URI}
        _LOGGER.debug('Requesting authorization page from "%s"', authorization_endpoint)
        self._session_auth_headers.pop("Referer", None)
        self._session_auth_headers.pop("Origin", None)
        _LOGGER.debug('Request headers: "%s"', self._session_auth_headers)

        try:
            # Build OAuth parameters with region-specific settings
            oauth_params = {
                "redirect_uri": self._session_region_config.get(
                    "redirect_uri", APP_URI
                ),  # Use region-specific redirect URI
                "response_type": CLIENT_TOKEN_TYPES,
                "client_id": self._client_id,  # Use region-specific client ID
                "scope": self._session_region_config.get(
                    "scope", CLIENT_SCOPE
                ),  # Use region-specific scope
            }

            # Add country/locale parameters for region-specific authentication
            # The US API requires these to identify the "legal entity"
            if self._session_country:
                # ui_locales uses language-region format (e.g., "en-US" not "us-US")
                country_to_locale = {
                    "US": "en-US",
                    "CA": "en-CA",
                    "GB": "en-GB",
                }
                oauth_params["ui_locales"] = country_to_locale.get(
                    self._session_country,
                    f"{self._session_country.lower()}-{self._session_country}",
                )
                oauth_params["prompt"] = (
                    "login"  # Force login prompt (observed in 2026 traffic)
                )

            # Add PKCE parameters if generated (required for NA region)
            if hasattr(self, "_pkce_challenge") and self._pkce_challenge:
                oauth_params["code_challenge"] = self._pkce_challenge
                oauth_params["code_challenge_method"] = "S256"
                _LOGGER.debug("Added PKCE challenge to authorization request")

            req = await self._session.get(
                url=authorization_endpoint,
                headers=self._session_auth_headers,
                allow_redirects=False,
                params=oauth_params,
            )

            # Check if the response contains a redirect location
            location = req.headers.get("Location")
            if not location:
                raise AuthenticationError(
                    f"Missing 'Location' header in authorization response. Payload returned: {await req.content.read()}"
                )

            ref = urljoin(authorization_endpoint, location)
            if "error" in ref:
                parsed_query = parse_qs(urlparse(ref).query)
                error_msg = parsed_query.get("error", ["Unknown error"])[0]
                error_description = parsed_query.get(
                    "error_description", ["No description"]
                )[0]
                _LOGGER.info("Authorization error: %s", error_description)
                raise AuthenticationError(f"{error_msg}: {error_description}")

            # If redirected, fetch the new location — follow any further redirects
            # automatically (NA identity server uses a multi-hop chain before
            # landing on the login form).
            req = await self._session.get(
                url=ref, headers=self._session_auth_headers, allow_redirects=True
            )

            if req.status != 200:
                raise AuthenticationError("Failed to fetch authorization endpoint")

            return await req.text()

        except Exception as e:
            _LOGGER.warning("Error during fetching authorization page: %s", str(e))
            raise

    def extract_state_token(self, page_content: str) -> str | None:
        """Extract state token from a page."""
        soup = BeautifulSoup(page_content, "html.parser")
        state_input = soup.select_one('input[name="state"]')
        if not state_input or not state_input.get("value"):
            _LOGGER.debug("State token not found.")
            return None
        return str(state_input["value"])

    def _extract_identitykit_form(self, page_html: str) -> dict:
        """Extract hidden fields from a VW IdentiKit login form.

        Handles two page types:
        - Email step: server-rendered form[id="emailPasswordForm"] with hidden inputs
        - Password step: React SPA — data embedded in window._IDK JavaScript object

        Returns dict with keys: csrf, relay_state, hmac, form_action
        Raises AuthenticationError if neither format is recognised.
        """
        soup = BeautifulSoup(page_html, "html.parser")
        form = soup.select_one('form[id="emailPasswordForm"]')
        if form:
            # Server-rendered email step
            def _val(selector: str) -> str | None:
                el = form.select_one(selector)
                return str(el["value"]) if el and el.get("value") else None

            return {
                "csrf": _val('input[name="_csrf"]'),
                "relay_state": _val('input[name="relayState"]'),
                "hmac": _val('input[name="hmac"]'),
                "form_action": form.get("action"),
            }

        # React-rendered password step — extract from window._IDK object
        # templateModel value is valid JSON; outer object uses unquoted JS keys
        tm_match = re.search(r'templateModel\s*:\s*(\{.*?\}),\s*\n', page_html, re.DOTALL)
        csrf_match = re.search(r"csrf_token\s*:\s*'([^']+)'", page_html)

        if not tm_match or not csrf_match:
            raise AuthenticationError("IdentiKit form not found — login page structure unknown")

        try:
            tm = json.loads(tm_match.group(1))
        except json.JSONDecodeError as exc:
            raise AuthenticationError(
                f"IdentiKit form not found — templateModel JSON parse error: {exc}"
            )

        hmac = tm.get("hmac")
        relay_state = tm.get("relayState")
        post_action = tm.get("postAction")  # e.g. "login/authenticate"
        client_id = tm.get("clientLegalEntityModel", {}).get("clientId") or self._client_id
        csrf = csrf_match.group(1)

        if not all([hmac, relay_state, post_action, csrf]):
            raise AuthenticationError(
                f"IdentiKit form incomplete (JS path) — missing: "
                f"{[k for k, v in {'hmac': hmac, 'relayState': relay_state, 'postAction': post_action, 'csrf': csrf}.items() if not v]}"
            )

        # Reconstruct the full form action path from client_id + postAction
        form_action = f"/signin-service/v1/{client_id}/{post_action}"
        return {
            "csrf": csrf,
            "relay_state": relay_state,
            "hmac": hmac,
            "form_action": form_action,
        }

    async def post_form(
        self, session: Any, url: str, headers: dict[str, str], form_data: dict[str, Any], redirect: bool = True
    ) -> str:
        """Post a form and check for success."""
        req = await session.post(
            url, headers=headers, data=form_data, allow_redirects=redirect
        )

        # Redirect case
        if not redirect and 300 <= req.status < 400:
            return req.headers.get("Location")

        # Handle explicit error 400 (form validation failure)
        if req.status == 400:
            page_content = await req.text()
            soup = BeautifulSoup(page_content, "html.parser")

            # Try both username + password fields in one pass
            for field_id in ("error-element-username", "error-element-password"):
                span = soup.select_one(f'span[id="{field_id}"]')
                if not span:
                    continue

                error_code = span.get("data-error-code")
                if error_code == "wrong-email-credentials":
                    raise AuthenticationError("Wrong username or password")

            # Unknown 400 error — log truncated body for debugging
            _LOGGER.debug(
                "post_form 400 response (first 500 chars): %s",
                page_content[:500],
            )
            raise AuthenticationError(
                "Login form validation failed with unknown 400 error"
            )

        # Any unexpected HTTP code
        if req.status not in (200, 400):
            raise RequestError(
                f"Login form submission failed with HTTP {req.status}. "
                "This might indicate incorrect credentials or a temporary service issue."
            )

        # Normal success path
        return await req.text()

    async def handle_login_with_password(self, session: Any, url: str, auth_headers: dict[str, str], form_data: dict[str, Any]) -> str:
        """Handle login with email and password."""
        return await self.post_form(session, url, auth_headers, form_data, False)

    async def follow_redirects(
        self, session: Any, pw_url: str, redirect_location: str
    ) -> str:
        """Handle redirects."""
        ref = urljoin(pw_url, redirect_location)
        MAX_REDIRECT_DEPTH = 10
        max_depth = MAX_REDIRECT_DEPTH
        stop_uri = self._session_region_config.get("redirect_uri", APP_URI)
        _LOGGER.debug("follow_redirects: stop_uri=%s start_ref=%s", stop_uri, ref)
        while not ref.startswith(stop_uri):
            if max_depth == 0:
                raise RedirectError(
                    f"Too many redirects during login flow (max depth: {MAX_REDIRECT_DEPTH}). "
                    "This might indicate an authentication loop."
                )
            response = await session.get(
                url=ref, headers=self._session_auth_headers, allow_redirects=False
            )
            location = response.headers.get("Location")
            _LOGGER.debug(
                "follow_redirects: GET %s → HTTP %s, Location: %s",
                ref, response.status, location,
            )

            # Check if we hit a terms and conditions page (HTTP 200 with no redirect)
            if response.status == 200 and not location:
                page_content = await response.text()
                if (
                    "termsAndConditions" in page_content
                    or '"page":"termsAndConditions"' in page_content
                ):
                    _LOGGER.error(
                        "Terms and Conditions acceptance required. "
                        "Please log in to https://www.myvolkswagen.net/ and accept the updated terms."
                    )
                    raise TermsAndConditionsError(
                        "Terms and Conditions must be accepted. "
                        "Please visit https://www.myvolkswagen.net/ to accept the updated terms and conditions, "
                        "then try logging in again."
                    )

            if not location:
                _LOGGER.warning("Failed to find next redirect location")
                raise RedirectError("Failed to find next redirect location")
            ref = urljoin(ref, location)
            max_depth -= 1
        return ref

    async def _get_authorization_code(self, openid_config: dict) -> str:
        """Get authorization code from login flow.

        Args:
            openid_config: OpenID configuration dictionary containing
                        authorization_endpoint and issuer

        Returns:
            Authorization code string

        Raises:
            AuthenticationError: If authorization fails
        """
        # Get OpenID configuration
        authorization_endpoint = openid_config["authorization_endpoint"]
        auth_issuer = openid_config["issuer"]

        # Get authorization page
        authorization_page = await self.get_authorization_page(authorization_endpoint)

        # Extract form data
        state_token = self.extract_state_token(authorization_page)

        if not state_token:
            _LOGGER.error(
                "Unable to find valid login page. "
                "Try logging in to the portal: https://www.myvolkswagen.net/"
            )
            raise AuthenticationError("Invalid login page - missing state token")

        # Do login
        login_form = {
            "username": self._session_auth_username,
            "password": self._session_auth_password,
            "state": state_token,
        }
        login_url = f"{auth_issuer}/u/login?state={state_token}"

        redirect_location = await self.post_form(
            self._session,
            login_url,
            self._session_auth_headers,
            login_form,
            False,
        )

        # Handle redirects and extract tokens
        redirect_response = await self.follow_redirects(
            self._session, auth_issuer, redirect_location
        )

        jwt_auth_code = parse_qs(urlparse(redirect_response).query)["code"][0]
        return jwt_auth_code

    async def _get_authorization_code_na(self, openid_config: dict) -> str:
        """NA-specific authorization code flow using VW IdentiKit two-step login."""
        authorization_endpoint = openid_config["authorization_endpoint"]
        _LOGGER.debug(
            "NA auth: fetching authorization page endpoint=%s",
            authorization_endpoint,
        )
        # Login forms are served by the identity server (identity.na.vwgroup.io),
        # not by the base API (b-h-s.spr.us00.p.con-veh.net).
        identity_base = self._session_region_config.get(
            "identity_endpoint", "https://identity.na.vwgroup.io"
        )

        # ── Step 1: get the email identifier page ────────────────────────────
        identifier_page = await self.get_authorization_page(authorization_endpoint)

        # ── Step 2: parse IdentiKit email form ────────────────────────────────
        form_data = self._extract_identitykit_form(identifier_page)
        if not all(form_data.values()):
            raise AuthenticationError(
                f"IdentiKit form incomplete — missing fields: "
                f"{[k for k, v in form_data.items() if not v]}"
            )

        # ── Step 3: POST email ─────────────────────────────────────────────────
        identifier_url = urljoin(identity_base, form_data["form_action"])
        email_payload = {
            "_csrf": form_data["csrf"],
            "relayState": form_data["relay_state"],
            "hmac": form_data["hmac"],
            "email": self._session_auth_username,
        }
        redirect_loc = await self.post_form(
            self._session, identifier_url, self._session_auth_headers, email_payload, redirect=False
        )
        _LOGGER.debug(
            "NA auth: email form submitted redirect=%s",
            (redirect_loc or "")[:60],
        )
        if not redirect_loc:
            raise AuthenticationError("No redirect received after email submission")

        # ── Step 4: GET password page ──────────────────────────────────────────
        password_page_url = urljoin(identity_base, redirect_loc)
        async with self._session.get(
            password_page_url, headers=self._session_auth_headers, allow_redirects=False
        ) as resp:
            if resp.status != 200:
                raise AuthenticationError(
                    f"Password page returned HTTP {resp.status} — check credentials or service availability"
                )
            password_page = await resp.text()
        _LOGGER.debug("NA auth: password page fetched status=%s", resp.status)

        # ── Step 5: parse IdentiKit password form ─────────────────────────────
        form_data2 = self._extract_identitykit_form(password_page)
        if not all(form_data2.values()):
            raise AuthenticationError(
                f"IdentiKit password form incomplete — missing: "
                f"{[k for k, v in form_data2.items() if not v]}"
            )

        # ── Step 6: POST password ──────────────────────────────────────────────
        authenticate_url = urljoin(identity_base, form_data2["form_action"])
        _LOGGER.debug(
            "_get_authorization_code_na Step 6: authenticate_url=%s relayState=%s hmac=%s csrf=%s",
            authenticate_url,
            form_data2.get("relay_state", "?")[:20],
            form_data2.get("hmac", "?")[:20],
            form_data2.get("csrf", "?")[:20],
        )
        password_payload = {
            "_csrf": form_data2["csrf"],
            "relayState": form_data2["relay_state"],
            "hmac": form_data2["hmac"],
            "email": self._session_auth_username,
            "password": self._session_auth_password,
        }
        redirect_loc2 = await self.post_form(
            self._session, authenticate_url, self._session_auth_headers, password_payload, redirect=False
        )
        _LOGGER.debug(
            "NA auth: password form submitted redirect=%s",
            (redirect_loc2 or "")[:60],
        )
        if not redirect_loc2:
            raise AuthenticationError("No redirect received after password submission — check credentials")

        # Detect explicit password rejection before spending hops on follow_redirects
        if "error=login.errors.password_invalid" in redirect_loc2:
            raise AuthenticationError(
                "Password rejected by VW identity server (login.errors.password_invalid). "
                "Verify credentials and account is not locked."
            )

        # Detect throttling — too many failed login attempts
        if "login.error.throttled" in redirect_loc2:
            raise AuthenticationError(
                "VW identity server is throttling login attempts (login.error.throttled). "
                "Too many failed attempts. Wait a few minutes before retrying."
            )

        # ── Step 7: follow redirect chain to callback URL ──────────────────────
        final_url = await self.follow_redirects(self._session, identity_base, redirect_loc2)

        # ── Step 8: extract authorization code ────────────────────────────────
        code = parse_qs(urlparse(final_url).query).get("code", [None])[0]
        if not code:
            raise AuthenticationError(
                f"Authorization code not found in callback URL: {final_url!r}"
            )
        _LOGGER.debug("NA: authorization code obtained")
        return code

    async def _exchange_code_for_tokens(
        self, auth_code: str, token_endpoint: str
    ) -> Any:
        """Exchange an OAuth2 authorization code for access tokens.

        For NA PKCE flow, sends the code_verifier instead of a client_secret.
        For EMEA, sends the standard client_id and redirect_uri.

        Args:
            auth_code: The authorization code obtained from the OAuth redirect.
            token_endpoint: The token endpoint URL for the exchange.

        Returns:
            Parsed JSON response containing access_token, refresh_token,
            id_token, and expiry fields. Returns None if the exchange fails.

        Raises:
            AuthenticationError: If the token endpoint returns an error response.
        """
        token_body = {
            "client_id": self._client_id,  # Use region-specific client ID
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": self._session_region_config.get(
                "redirect_uri", APP_URI
            ),  # Use region-specific redirect URI
        }

        # Add PKCE code_verifier if available (required for NA region)
        if hasattr(self, "_pkce_verifier") and self._pkce_verifier:
            token_body["code_verifier"] = self._pkce_verifier
            _LOGGER.debug("Added PKCE verifier to token exchange")

        # Add X-QMAuth header for NA token exchange (required by identity.na.vwgroup.io)
        if self._session_region == "NA":
            self._session_auth_headers["X-QMAuth"] = self._calculate_xqmauth()

        _LOGGER.debug(
            "Token exchange request: endpoint=%s keys=%s has_verifier=%s",
            token_endpoint,
            list(token_body.keys()),
            bool(token_body.get("code_verifier")),
        )

        # Use direct POST for token exchange to capture error body on failure
        resp = await self._session.post(
            token_endpoint,
            headers=self._session_auth_headers,
            data=token_body,
            allow_redirects=False,
        )
        resp_text = await resp.text()
        if resp.status != 200:
            _LOGGER.debug(
                "Token exchange HTTP %s response body: %s", resp.status, resp_text[:500]
            )
            raise AuthenticationError(
                f"Token exchange failed with HTTP {resp.status}: {resp_text[:200]}"
            )

        tokens_data = json_loads(resp_text)
        _LOGGER.debug(
            "NA token exchange: status=%s has_access_token=%s",
            resp.status,
            "access_token" in tokens_data,
        )
        return tokens_data

    async def _register_mbb_client(self) -> str:
        """Register as MBB OAuth client and return xclientId.

        POSTs to MBB registration endpoint using the VW Car-Net app identity.
        Returns the assigned xclientId (client_id) string.

        Raises:
            AuthenticationError: If registration fails or response is malformed.
        """
        mbb_base = self._session_region_config.get("mbb_oauth_base_url")
        if not mbb_base:
            raise AuthenticationError("NA region config missing mbb_oauth_base_url")

        register_url = f"{mbb_base}/mobile/register/v1"
        register_body = {
            "client_name": "Android Phone",
            "platform": "google",
            "client_brand": "Volkswagen",
            "appName": "myVW",
            "appVersion": "3.51.1",
            "appId": ANDROID_PACKAGE_NAME,
        }
        reg_headers = {**self._session_auth_headers, "Content-Type": "application/json"}

        _LOGGER.debug("Registering as MBB OAuth client at %s", register_url)
        response = await self._session.post(
            url=register_url,
            headers=reg_headers,
            json=register_body,
        )

        if response.status != 200:
            text = await response.text()
            raise AuthenticationError(
                f"MBB client registration failed with HTTP {response.status}: {text}"
            )

        data = await response.json()
        xclient_id = data.get("client_id")
        if not xclient_id:
            raise AuthenticationError(
                f"MBB client registration response missing 'client_id': {data}"
            )

        _LOGGER.info("NA: MBB client registered, xclientId obtained")
        return xclient_id

    async def _exchange_brand_token(self, idk_access_token: str) -> dict:
        """Exchange IDK access_token for Brand token.

        Tries /login/v1/volkswagen/token first, falls back to /login/v1/vw/token on 404.
        Uses JSON body (not form-encoded) per 2026 traffic analysis.

        Args:
            idk_access_token: The IDK access token from the authorization code exchange.

        Returns:
            Dict containing brand access_token and refresh_token.

        Raises:
            AuthenticationError: If brand token exchange fails on both paths.
        """
        brand_body = {
            "token": idk_access_token,
            "grant_type": "id_token",
            "stage": "live",
            "config": MBB_BRAND_CONFIG,
        }
        brand_headers = {**self._session_auth_headers, "Content-Type": "application/json"}

        primary_path = "/login/v1/volkswagen/token"
        fallback_path = "/login/v1/vw/token"

        for path in (primary_path, fallback_path):
            url = f"{self._base_api}{path}"
            _LOGGER.debug("Attempting Brand token exchange at %s", url)
            response = await self._session.post(
                url=url,
                headers=brand_headers,
                json=brand_body,
            )
            if response.status == 404 and path == primary_path:
                _LOGGER.debug("Brand token primary path 404, trying fallback: %s", fallback_path)
                continue
            if response.status == 200:
                data = await response.json()
                _LOGGER.info("NA: Brand token obtained")
                return data
            text = await response.text()
            raise AuthenticationError(
                f"Brand token exchange failed at {path} with HTTP {response.status}: {text}"
            )

        # Should not reach here — loop always returns or raises
        raise AuthenticationError("Brand token exchange failed on all paths")

    async def _exchange_mbb_token(self, idk_id_token: str, xclient_id: str) -> dict:
        """Exchange IDK id_token for initial MBB token (form-encoded).

        NOTE: Uses id_token (not access_token) per MBB OAuth spec.
        NOTE: Body key is 'token' (non-standard) not 'id_token'.
        NOTE: Body is form-encoded (not JSON) — unlike Brand token exchange.

        Args:
            idk_id_token: The IDK id_token from the authorization code exchange.
            xclient_id: The registered MBB client ID (X-Client-ID header).

        Returns:
            Dict containing mbb access_token and refresh_token.

        Raises:
            AuthenticationError: If MBB initial token exchange fails.
        """
        mbb_base = self._session_region_config.get("mbb_oauth_base_url")
        mbb_url = f"{mbb_base}/mobile/oauth2/v1/token"
        mbb_body = {
            "grant_type": "id_token",
            "token": idk_id_token,  # Uses id_token value, key is "token"
            "scope": "sc2:fal",
        }
        mbb_headers = {
            **self._session_auth_headers,
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Client-ID": xclient_id,
        }

        _LOGGER.debug("Requesting initial MBB token at %s", mbb_url)
        response = await self._session.post(
            url=mbb_url,
            headers=mbb_headers,
            data=mbb_body,
        )

        if response.status != 200:
            text = await response.text()
            raise AuthenticationError(
                f"MBB initial token exchange failed with HTTP {response.status}: {text}"
            )

        data = await response.json()
        _LOGGER.info("NA: MBB initial token obtained")
        return data

    async def _refresh_mbb_token(self, refresh_token: str, xclient_id: str) -> dict:
        """Refresh an MBB token using the refresh_token grant.

        Separate method (not embedded in login) so Phase 4 token lifecycle
        management can call it independently without re-login.

        NOTE: Body key for refresh_token value is 'token' (non-standard VW convention).

        Args:
            refresh_token: The MBB refresh_token from a previous MBB grant.
            xclient_id: The registered MBB client ID (X-Client-ID header).

        Returns:
            Dict containing refreshed access_token and refresh_token.

        Raises:
            AuthenticationError: If MBB token refresh fails.
        """
        mbb_base = self._session_region_config.get("mbb_oauth_base_url")
        mbb_url = f"{mbb_base}/mobile/oauth2/v1/token"
        refresh_body = {
            "grant_type": "refresh_token",
            "token": refresh_token,  # Key is "token" not "refresh_token" per VW spec
            "scope": "sc2:fal",
        }
        mbb_headers = {
            **self._session_auth_headers,
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Client-ID": xclient_id,
        }

        _LOGGER.debug("Refreshing MBB token at %s", mbb_url)
        response = await self._session.post(
            url=mbb_url,
            headers=mbb_headers,
            data=refresh_body,
        )

        if response.status != 200:
            text = await response.text()
            raise AuthenticationError(
                f"MBB token refresh failed with HTTP {response.status}: {text}"
            )

        data = await response.json()
        _LOGGER.info("NA: MBB token refreshed")
        return data

    async def _refresh_idk_token(self) -> None:
        """Refresh the IDK access token using the stored refresh token.

        The refresh request includes the original PKCE ``code_verifier`` from
        the initial login. This is a non-standard OAuth extension required by
        the NA AZS server; omitting it causes the server to demand a
        ``client_secret`` that does not exist for this public client.

        The ``X-QMAuth`` header is intentionally NOT sent, as the server
        rejects it with HTTP 400 for this public PKCE client.

        After a successful refresh, updates ``self._na_tokens['idk']``,
        ``self._session_tokens['identity']``, and the Authorization header.

        Returns:
            None.

        Raises:
            AuthenticationError: If no refresh token is stored, the token
                endpoint is not set, or all retry attempts (up to 3) fail.
        """
        idk_entry = self._na_tokens.get("idk", {})
        refresh_token = idk_entry.get("refresh_token")
        if not refresh_token:
            raise AuthenticationError("Cannot refresh IDK token: no refresh_token stored")
        if not self._na_token_endpoint:
            raise AuthenticationError("Cannot refresh IDK token: _na_token_endpoint not set (login not completed?)")

        # NA AZS server requires the same code_verifier from the original PKCE login
        # (non-standard extension — confirmed from APK decompilation of AzsRefreshRequest)
        pkce_verifier = getattr(self, "_pkce_verifier", None) or ""
        refresh_body = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self._client_id,
            "code_verifier": pkce_verifier,
        }
        # Public PKCE client (59992128_MYVW_ANDROID) does NOT use X-QMAuth —
        # that header causes HTTP 400 "Internal Service validation failure" from b-h-s server.
        refresh_headers = {
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
            "x-android-package-name": ANDROID_PACKAGE_NAME,
        }

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._session.post(
                    url=self._na_token_endpoint,
                    headers=refresh_headers,
                    data=refresh_body,
                    timeout=ClientTimeout(total=TIMEOUT.seconds),
                )
                if response.status == 200:
                    tokens = await response.json()
                    now = time.time()
                    # Update NA token registry
                    self._na_tokens["idk"].update({
                        "access_token": tokens["access_token"],
                        "refresh_token": tokens.get("refresh_token", refresh_token),
                        "id_token": tokens.get("id_token", idk_entry.get("id_token")),
                        "expires_at": now + tokens.get("expires_in", 3600),
                        "issued_at": now,
                    })
                    # Mirror to session_tokens for EMEA-compatible validate_tokens()
                    self._session_tokens["identity"].update(self._na_tokens["idk"])
                    self._session_headers["Authorization"] = (
                        "Bearer " + tokens["access_token"]
                    )
                    _LOGGER.info("NA: IDK token refreshed successfully")
                    # Cascade: Brand token derived from IDK access_token; always refresh it
                    if "brand" in self._na_tokens:
                        await self._refresh_brand_token()
                    return
                text = await response.text()
                _LOGGER.warning(
                    "IDK refresh attempt %s/%s failed with HTTP %s: %s",
                    attempt, max_attempts, response.status, text,
                )
            except Exception as exc:
                _LOGGER.warning("IDK refresh attempt %s/%s error: %s", attempt, max_attempts, exc)

            if attempt < max_attempts:
                await asyncio.sleep(2)

        raise AuthenticationError(
            f"IDK token refresh failed after {max_attempts} attempts"
        )

    async def _refresh_brand_token(self) -> None:
        """Refresh the Brand token by re-exchanging the current IDK access_token.

        Brand is derived from IDK, so this re-calls _exchange_brand_token().
        On exchange failure, raises AuthenticationError.

        Raises:
            AuthenticationError: If brand token re-derivation fails.
        """
        idk_access_token = self._na_tokens.get("idk", {}).get("access_token")
        if not idk_access_token:
            raise AuthenticationError("Cannot refresh Brand token: no IDK access_token available")

        try:
            brand_tokens = await self._exchange_brand_token(idk_access_token)
            now = time.time()
            self._na_tokens["brand"] = {
                "access_token": brand_tokens.get("access_token"),
                "refresh_token": brand_tokens.get("refresh_token"),
                "expires_at": now + brand_tokens.get("expires_in", 3600),
                "issued_at": now,
                "scopes": brand_tokens.get("scope", ""),
            }
            _LOGGER.info("NA: Brand token refreshed via IDK re-exchange")
        except AuthenticationError:
            _LOGGER.error("NA: Brand token re-derivation failed")
            raise

    async def _refresh_mbb_from_refresh_token(self) -> None:
        """Refresh the MBB token using the stored MBB refresh_token.

        On failure, falls back to re-exchange from current IDK id_token
        (_exchange_mbb_token + _refresh_mbb_token) before raising.

        Requires self._xclient_id to be set.

        Raises:
            AuthenticationError: If both MBB refresh and re-exchange fallback fail.
        """
        if not self._xclient_id:
            raise AuthenticationError("Cannot refresh MBB token: no xclientId stored")

        mbb_entry = self._na_tokens.get("mbb", {})
        refresh_token = mbb_entry.get("refresh_token")

        # Primary: refresh via stored refresh_token
        if refresh_token:
            try:
                mbb_tokens = await self._refresh_mbb_token(
                    refresh_token=refresh_token,
                    xclient_id=self._xclient_id,
                )
                now = time.time()
                self._na_tokens["mbb"].update({
                    "access_token": mbb_tokens.get("access_token"),
                    "refresh_token": mbb_tokens.get("refresh_token", refresh_token),
                    "expires_at": now + mbb_tokens.get("expires_in", 3600),
                    "issued_at": now,
                })
                _LOGGER.info("NA: MBB token refreshed via refresh_token")
                return
            except AuthenticationError as exc:
                _LOGGER.warning("NA: MBB refresh_token grant failed, trying re-exchange: %s", exc)

        # Fallback: re-exchange from IDK id_token
        idk_id_token = self._na_tokens.get("idk", {}).get("id_token")
        if not idk_id_token:
            raise AuthenticationError(
                "MBB refresh failed and IDK id_token unavailable for re-exchange fallback"
            )
        try:
            mbb_initial = await self._exchange_mbb_token(
                idk_id_token=idk_id_token,
                xclient_id=self._xclient_id,
            )
            mbb_working = await self._refresh_mbb_token(
                refresh_token=mbb_initial["refresh_token"],
                xclient_id=self._xclient_id,
            )
            now = time.time()
            self._na_tokens["mbb"] = {
                "access_token": mbb_working.get("access_token"),
                "refresh_token": mbb_working.get("refresh_token"),
                "expires_at": now + mbb_working.get("expires_in", 3600),
                "issued_at": now,
                "scopes": mbb_working.get("scope", "sc2:fal"),
            }
            _LOGGER.info("NA: MBB token re-exchanged from IDK id_token (fallback)")
        except AuthenticationError:
            _LOGGER.error("NA: MBB re-exchange fallback also failed")
            raise

    async def _create_na_vehicle_session(self, vin: str) -> str | None:
        """Create and cache a carnetVehicleToken for the given VIN.

        Uses ``tsp_provider`` stored in ``self._na_tokens[vin]["tsp_provider"]``
        during the garage parse in ``doLogin()``.  Valid TSP enum values are
        ``"ATC"`` (Aeris Telecommunications Corporation), ``"WCT"``
        (WirelessCar Technologies), and ``"Unknown"``.  ``"VWNA"`` and ``"VW"``
        are NOT valid TSP enum values — both return HTTP 400.  Defaults to
        ``"ATC"`` if no stored tsp_provider is found.

        When SPIN is configured the method performs a two-step flow:

        1. POST vehicle session with ``spinHash=null`` — the server accepts this
           on the first call and returns a ``carnetVehicleToken``.
        2. GET ``ss/v1/user/{userId}/challenge`` with that token as Bearer — the
           challenge endpoint requires the ``carnetVehicleToken``, NOT the IDK
           access_token.  The response is a flat ``{"challenge": "...",
           "remainingTries": N}`` object.
        3. Compute ``spinHash = SHA-512(UTF-8("{challenge}.{spin}"))``.
        4. POST vehicle session again with the computed ``spinHash`` — this
           validates the SPIN and returns the final ``carnetVehicleToken``.

        When SPIN is not configured the method performs a single POST with
        ``spinHash=null``.

        On the first attempt the IDK access_token is sent as a Bearer
        Authorization header; if the server responds 401 the same ``tsp`` is
        retried with NO Authorization header (some NA environments reject the
        header).

        The resulting JWT is cached in
        ``self._na_tokens[vin]["vehicle_session"]`` with ``token``,
        ``expires_at`` (JWT ``exp`` claim), and ``issued_at`` fields.  A 5-minute
        buffer is applied so callers never receive a near-expired token.

        Token values are NEVER logged at any log level.

        Args:
            vin: Vehicle Identification Number.

        Returns:
            The carnetVehicleToken string on success, or ``None`` if the
            session POST fails or the IDK id_token is missing.
        """
        idk_entry = self._na_tokens.get("idk", {})
        idk_id_token = idk_entry.get("id_token", "")
        idk_access_token = idk_entry.get("access_token", "")
        _LOGGER.debug("NA vehicle session: creating session for vin=%s", redact(vin))

        if not idk_id_token:
            _LOGGER.warning("NA: cannot create vehicle session for %s — IDK id_token missing", vin)
            return None

        # Parse userId from IDK id_token JWT sub claim
        try:
            claims = jwt.decode(idk_id_token, options={"verify_signature": False})
            user_id = claims.get("sub", "")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            _LOGGER.warning("NA: failed to decode IDK id_token for userId: %s", exc)
            return None

        if not user_id:
            _LOGGER.warning("NA: IDK id_token has no 'sub' claim, cannot create vehicle session")
            return None

        # Check cache — return cached token if not expiring within 5 minutes
        cached = self._na_tokens.get(vin, {}).get("vehicle_session")
        if cached and cached.get("expires_at", 0) > time.time() + 300:
            _LOGGER.debug("NA vehicle session: cache hit for vin=%s", redact(vin))
            return cached["token"]

        base_api = self._base_api
        # Use the vehicleId (UUID from garage response) for the session URL.
        # The APK uses {vehicleId} (UUID like "7f3e...") NOT the VIN string.
        vehicle_id = self._na_tokens.get(vin, {}).get("vehicle_id", vin)
        session_url = f"{base_api}/ss/v1/user/{user_id}/vehicle/{vehicle_id}/session"
        _LOGGER.debug("NA vehicle session: url=%s", session_url)

        # Use tspProvider from garage response (stored during doLogin)
        # Valid values: "ATC" (Aeris), "WCT" (WirelessCar), "Unknown"
        # "VWNA" and "VW" are NOT valid TSP enum values — both return HTTP 400
        tsp_value = self._na_tokens.get(vin, {}).get("tsp_provider", "ATC")
        _LOGGER.debug("NA vehicle session: using tsp=%r for %s", tsp_value, vin)

        vehicle_token: str | None = None

        def _post_vehicle_session(spin_hash: str | None) -> Any:
            """Helper returning the coroutine for a vehicle session POST."""
            body = {"idToken": idk_id_token, "tsp": tsp_value, "spinHash": spin_hash}
            auth_headers = {
                "Authorization": f"Bearer {idk_access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            return self._session.post(
                url=session_url,
                json=body,
                headers=auth_headers,
                timeout=ClientTimeout(total=TIMEOUT.seconds),
                allow_redirects=False,
            )

        async def _execute_session_post(spin_hash: str | None) -> str | None:
            """POST vehicle session and return vehicle_token or None."""
            nonlocal tsp_value
            try:
                resp = await _post_vehicle_session(spin_hash)
                status = resp.status

                if status == 401:
                    # Retry without Authorization header
                    _LOGGER.debug(
                        "NA vehicle session: 401 with auth header for tsp=%r, retrying without auth",
                        tsp_value,
                    )
                    body = {"idToken": idk_id_token, "tsp": tsp_value, "spinHash": spin_hash}
                    no_auth_headers = {
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    }
                    resp = await self._session.post(
                        url=session_url,
                        json=body,
                        headers=no_auth_headers,
                        timeout=ClientTimeout(total=TIMEOUT.seconds),
                        allow_redirects=False,
                    )
                    status = resp.status

                if status == 200:
                    data = await resp.json()
                    _LOGGER.debug("NA vehicle session 200 response keys: %s", list(data.keys()))
                    # Support both flat {"carnetVehicleToken": "..."} and wrapped {"data": {"carnetVehicleToken": "..."}}
                    payload = data.get("data") if "data" in data else data
                    raw_token = payload.get("carnetVehicleToken") if isinstance(payload, dict) else None
                    if raw_token is None:
                        # Also check top-level as fallback
                        raw_token = data.get("carnetVehicleToken")
                    # Handle both plain string and nested object {"token": "<jwt>"}
                    if isinstance(raw_token, dict):
                        tok = raw_token.get("token") or raw_token.get("f49219a")
                        _LOGGER.debug("NA vehicle session: carnetVehicleToken was a dict, extracted token")
                    else:
                        tok = raw_token
                    if tok:
                        _LOGGER.debug("NA vehicle session: token obtained for vin=%s", redact(vin))
                        _LOGGER.info("NA vehicle session created with tsp='%s'", tsp_value)
                        return tok
                    _LOGGER.warning(
                        "NA vehicle session: tsp=%r got 200 but no carnetVehicleToken in response. "
                        "Response keys: %s, payload keys: %s",
                        tsp_value,
                        list(data.keys()),
                        list(payload.keys()) if isinstance(payload, dict) else payload,
                    )
                    return None
                body_text = await resp.text()
                _LOGGER.warning(
                    "NA vehicle session: tsp=%r returned %d: %s",
                    tsp_value,
                    status,
                    body_text[:300],
                )
                return None
            except Exception as exc:  # pylint: disable=broad-exception-caught
                _LOGGER.warning("NA vehicle session: exception for tsp=%r: %s", tsp_value, exc)
                return None

        if self._spin:
            # SPIN flow (from APK d20/i.java UserSession interceptor analysis):
            #   The AzsSession in the APK is the IDK OIDC session (not a separate carnetVehicleToken).
            #   d20.i adds:
            #     - Authorization: Bearer {idk_access_token}   ← azsSession.token.access_token
            #     - x-user-id: {userId}
            #     - x-mobile-session-id: {sessionId}
            #       ^ TBD: field name from APK analysis, not confirmed from live traffic
            #     - x-app-version: 2025.12.10-8414
            #   The challenge endpoint (ss/v1/user/{userId}/challenge) accepts IDK access_token as
            #   Bearer when the x-user-id header is also present.
            #   PinResponse is flat: {"challenge": "<hex>", "remainingTries": N} — no "data" wrapper.
            #
            #   Flow:
            #   1. GET challenge with IDK access_token Bearer + x-user-id header
            #   2. Compute spinHash = SHA-512(UTF-8("{challenge}.{spin}"))
            #   3. POST vehicle session with computed spinHash → carnetVehicleToken
            challenge_url = f"{base_api}/ss/v1/user/{user_id}/challenge"
            spin_hash: str | None = None
            try:
                challenge_resp = await self._session.get(
                    challenge_url,
                    headers={
                        "Authorization": f"Bearer {idk_access_token}",
                        "x-user-id": user_id,
                        "x-user-agent": "mobile-android",
                        "x-app-version": "2025.12.10-8414",
                        "Accept": "application/json",
                    },
                    timeout=ClientTimeout(total=TIMEOUT.seconds),
                )
                challenge_status = challenge_resp.status
                if challenge_status == 200:
                    # Server wraps PinResponse: {"data": {"challenge": "<hex>", "remainingTries": N}}
                    challenge_resp_data = await challenge_resp.json()
                    _LOGGER.debug(
                        "NA vehicle session: challenge response keys: %s",
                        list(challenge_resp_data.keys()),
                    )
                    # Support both wrapped {"data": {"challenge": ...}} and flat {"challenge": ...}
                    challenge_data = challenge_resp_data.get("data") or challenge_resp_data
                    challenge_hex = challenge_data.get("challenge")
                    if challenge_hex:
                        spin_hash = self.hash_spin(challenge_hex, self._spin)
                        _LOGGER.debug(
                            "NA vehicle session: challenge=%s spin=%s spinHash=%s",
                            challenge_hex,
                            self._spin,
                            spin_hash,
                        )
                    else:
                        _LOGGER.warning(
                            "NA vehicle session: challenge response missing 'challenge' field. "
                            "Top-level keys: %s, data keys: %s",
                            list(challenge_resp_data.keys()),
                            list(challenge_data.keys()) if isinstance(challenge_data, dict) else challenge_data,
                        )
                        return None
                else:
                    body_text = await challenge_resp.text()
                    _LOGGER.warning(
                        "NA vehicle session: challenge GET %d: %s",
                        challenge_status,
                        body_text[:200],
                    )
                    return None
            except Exception as exc:  # pylint: disable=broad-exception-caught
                _LOGGER.warning("NA vehicle session: challenge GET failed: %s", exc)
                return None

            # POST session with computed spinHash → returns carnetVehicleToken
            vehicle_token = await _execute_session_post(spin_hash=spin_hash)
        else:
            # No SPIN configured — single session POST with spinHash=None
            vehicle_token = await _execute_session_post(spin_hash=None)

        if not vehicle_token:
            _LOGGER.warning(
                "NA: vehicle session creation failed for %s (tsp=%r)",
                vin,
                tsp_value,
            )
            return None

        # Parse JWT exp claim for cache TTL
        try:
            token_claims = jwt.decode(vehicle_token, options={"verify_signature": False})
            expires_at = token_claims.get("exp", time.time() + 1800)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            _LOGGER.debug("NA: could not decode vehicle token JWT for exp claim: %s", exc)
            expires_at = time.time() + 1800

        if vin not in self._na_tokens:
            self._na_tokens[vin] = {}
        self._na_tokens[vin]["vehicle_session"] = {
            "token": vehicle_token,
            "expires_at": expires_at,
            "issued_at": time.time(),
        }
        return vehicle_token

    async def _get_na_vehicle_data(self, vin: str) -> dict | None:
        """Fetch NA vehicle telemetry from RVS endpoints.

        Calls ``_create_na_vehicle_session(vin)`` to obtain a
        ``carnetVehicleToken``, then fetches:

        - ``GET {base_api}/rvs/v1/location/vehicle/{vehicle_id}`` — GPS location
        - ``GET {base_api}/rvs/v1/vehicle/{vehicle_id}`` — vehicle status / lock state

        On HTTP 401 from either RVS endpoint, the cached vehicle session is
        invalidated and ``_create_na_vehicle_session`` is called once more
        before a single retry.

        Raw response bodies are logged at DEBUG level for diagnostics.

        Token values (vehicle token, IDK tokens) are NEVER logged.

        Args:
            vin: Vehicle Identification Number.

        Returns:
            A dict with keys ``"na_location"`` and ``"na_status"`` (either may
            be ``None`` if that particular fetch failed).  Returns ``None`` only
            when vehicle session creation itself fails (no data at all possible).
        """
        # Ensure IDK token is valid before proceeding
        if not await self.validate_tokens():
            _LOGGER.warning("NA: validate_tokens() returned False, skipping vehicle data fetch for %s", redact(vin))
            return None

        _LOGGER.debug("NA vehicle data: fetching data for vin=%s", redact(vin))
        vehicle_token = await self._create_na_vehicle_session(vin)
        if vehicle_token is None:
            return None

        # Parse userId from IDK id_token for RVS headers
        idk_id_token = self._na_tokens.get("idk", {}).get("id_token", "")
        try:
            claims = jwt.decode(idk_id_token, options={"verify_signature": False})
            user_id = claims.get("sub", "")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            _LOGGER.warning("NA: failed to decode IDK id_token for x-user-id header: %s", exc)
            user_id = ""

        # Build RVS headers (vehicle_token used in Authorization — NEVER logged)
        rvs_headers: dict = {
            "Authorization": f"Bearer {vehicle_token}",
            "x-user-id": user_id,
            "x-app-version": "2025.12.10-8414",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Add x-mobile-session-id if cached from prior session response
        # TBD: field name "x-mobile-session-id" derived from APK analysis (d20/i.java),
        # not yet confirmed from live HTTP traffic capture. See CLEAN-03.
        session_id = self._na_tokens.get(vin, {}).get("vehicle_session", {}).get("session_id")
        if session_id:
            rvs_headers["x-mobile-session-id"] = session_id

        base_api = self._base_api
        # Use the vehicleId (UUID from garage) for RVS paths — same as vehicle session.
        vehicle_id = self._na_tokens.get(vin, {}).get("vehicle_id", vin)

        # --- Location fetch ---
        location_data: dict | None = None
        location_url = f"{base_api}/rvs/v1/location/vehicle/{vehicle_id}"
        _LOGGER.debug(
            "NA vehicle data: fetching RVS location for vin=%s url=%s",
            redact(vin),
            location_url,
        )
        try:
            for _rvs_attempt in range(RVS_MAX_RETRIES + 1):
                loc_resp = await self._session.get(
                    url=location_url,
                    headers=rvs_headers,
                    timeout=ClientTimeout(total=TIMEOUT.seconds),
                    allow_redirects=False,
                )
                _LOGGER.debug(
                    "NA vehicle data: RVS location status=%s for vin=%s",
                    loc_resp.status,
                    redact(vin),
                )
                if loc_resp.status == 401:
                    _LOGGER.debug("NA RVS location: 401 — refreshing vehicle session and retrying")
                    self._na_tokens.get(vin, {}).pop("vehicle_session", None)
                    vehicle_token = await self._create_na_vehicle_session(vin)
                    if vehicle_token:
                        rvs_headers["Authorization"] = f"Bearer {vehicle_token}"
                        loc_resp = await self._session.get(
                            url=location_url,
                            headers=rvs_headers,
                            timeout=ClientTimeout(total=TIMEOUT.seconds),
                            allow_redirects=False,
                        )
                if loc_resp.status == 200:
                    location_data = await loc_resp.json()
                    # Unwrap {"data": {...}} envelope if present
                    if isinstance(location_data, dict) and "data" in location_data:
                        location_data = location_data["data"]
                    _LOGGER.debug("NA RVS location response: %s", location_data)
                    break  # success — exit retry loop
                elif loc_resp.status >= 500:
                    body_preview = await loc_resp.text()
                    if _rvs_attempt < RVS_MAX_RETRIES:
                        _LOGGER.warning(
                            "NA RVS location: transient %d for %s (attempt %d/%d), retrying",
                            loc_resp.status, redact(vin), _rvs_attempt + 1, RVS_MAX_RETRIES + 1,
                        )
                        await asyncio.sleep(1.0)
                        continue  # retry
                    _LOGGER.warning(
                        "NA RVS location fetch failed for %s: HTTP %d — %s",
                        redact(vin), loc_resp.status, body_preview[:200],
                    )
                else:
                    body_preview = await loc_resp.text()
                    _LOGGER.warning(
                        "NA RVS location fetch failed for %s: HTTP %d — %s",
                        redact(vin), loc_resp.status, body_preview[:200],
                    )
                    break  # non-5xx non-200 — do not retry
        except Exception as exc:  # pylint: disable=broad-exception-caught
            _LOGGER.warning("NA RVS location fetch exception for %s: %s", redact(vin), exc)

        # --- Status fetch ---
        status_data: dict | None = None
        status_url = f"{base_api}/rvs/v1/vehicle/{vehicle_id}"
        _LOGGER.debug(
            "NA vehicle data: fetching RVS status for vin=%s url=%s",
            redact(vin),
            status_url,
        )
        try:
            for _rvs_attempt in range(RVS_MAX_RETRIES + 1):
                st_resp = await self._session.get(
                    url=status_url,
                    headers=rvs_headers,
                    timeout=ClientTimeout(total=TIMEOUT.seconds),
                    allow_redirects=False,
                )
                _LOGGER.debug(
                    "NA vehicle data: RVS status status=%s for vin=%s",
                    st_resp.status,
                    redact(vin),
                )
                if st_resp.status == 401:
                    _LOGGER.debug("NA RVS status: 401 — refreshing vehicle session and retrying")
                    self._na_tokens.get(vin, {}).pop("vehicle_session", None)
                    vehicle_token = await self._create_na_vehicle_session(vin)
                    if vehicle_token:
                        rvs_headers["Authorization"] = f"Bearer {vehicle_token}"
                        st_resp = await self._session.get(
                            url=status_url,
                            headers=rvs_headers,
                            timeout=ClientTimeout(total=TIMEOUT.seconds),
                            allow_redirects=False,
                        )
                if st_resp.status == 200:
                    status_data = await st_resp.json()
                    # Unwrap {"data": {...}} envelope if present
                    if isinstance(status_data, dict) and "data" in status_data:
                        status_data = status_data["data"]
                    _LOGGER.debug("NA RVS status response (unwrapped): %s", status_data)
                    break  # success — exit retry loop
                elif st_resp.status >= 500:
                    body_preview = await st_resp.text()
                    if _rvs_attempt < RVS_MAX_RETRIES:
                        _LOGGER.warning(
                            "NA RVS status: transient %d for %s (attempt %d/%d), retrying",
                            st_resp.status, redact(vin), _rvs_attempt + 1, RVS_MAX_RETRIES + 1,
                        )
                        await asyncio.sleep(1.0)
                        continue  # retry
                    _LOGGER.warning(
                        "NA RVS status fetch failed for %s: HTTP %d — %s",
                        redact(vin), st_resp.status, body_preview[:200],
                    )
                else:
                    body_preview = await st_resp.text()
                    _LOGGER.warning(
                        "NA RVS status fetch failed for %s: HTTP %d — %s",
                        redact(vin), st_resp.status, body_preview[:200],
                    )
                    break  # non-5xx non-200 — do not retry
        except Exception as exc:  # pylint: disable=broad-exception-caught
            _LOGGER.warning("NA RVS status fetch exception for %s: %s", redact(vin), exc)

        # Return partial data even if one endpoint failed
        return {
            "na_location": location_data,
            "na_status": status_data,
        }

    async def _login_na(self) -> bool:
        """Perform the NA-specific OAuth2 + PKCE login flow.

        Uses the b-h-s base API OIDC endpoints with client ID
        59992128_MYVW_ANDROID (public client, no secret). Obtains an IDK
        access token and refresh token via authorization code exchange.

        The flow:
        1. Generate PKCE code_verifier and code_challenge.
        2. GET authorize endpoint to obtain the login form.
        3. POST credentials to the identity provider form action.
        4. Follow redirects to extract the authorization code.
        5. Exchange code for tokens at the base API token endpoint.

        Returns:
            True if login succeeded and tokens were stored, False otherwise.

        Raises:
            AuthenticationError: If credential submission or code extraction fails.
                Wraps ``RequestError`` (network/HTTP failures) and ``KeyError``
                (missing response fields) with actionable guidance —
                e.g. "verify country='US' and credentials are correct".
            RedirectError: If the OAuth redirect chain produces an unexpected URL.
        """
        try:
            # Clear cookies and reset headers (same as _login())
            self._clear_cookies()
            self._session_headers = HEADERS_SESSION.copy()
            self._session_auth_headers = HEADERS_AUTH.copy()

            # NA uses PKCE: code_verifier replaces client_secret at token exchange
            self._pkce_verifier = self._generate_pkce_verifier()
            self._pkce_challenge = self._generate_pkce_challenge(self._pkce_verifier)
            _LOGGER.debug(
                "NA login: PKCE challenge created verifier=%s challenge=%s",
                redact(self._pkce_verifier),
                redact(self._pkce_challenge),
            )

            # Get OpenID config (routes to identity.na.vwgroup.io for NA)
            openid_config = await self.get_openid_config()
            token_endpoint = openid_config["token_endpoint"]
            self._na_token_endpoint = token_endpoint  # persist for Phase 4 IDK refresh
            _LOGGER.debug(
                "NA login: OpenID config fetched token_endpoint=%s",
                openid_config.get("token_endpoint", "?"),
            )

            # Get authorization code via IdentiKit two-step flow
            auth_code = await self._get_authorization_code_na(openid_config)

            # Exchange code for tokens (X-QMAuth header injected inside for NA)
            tokens = await self._exchange_code_for_tokens(auth_code, token_endpoint)
            _LOGGER.debug(
                "NA login: token exchange complete access_token=%s",
                redact(tokens.get("access_token")),
            )

            # Validate token structure
            required_keys = ["access_token", "id_token", "token_type"]
            if not all(key in tokens for key in required_keys):
                _LOGGER.error(
                    "NA token exchange returned invalid response. Missing keys. Got: %s",
                    list(tokens.keys()),
                )
                return False

            # Store IDK token to session_tokens for validate_tokens() compatibility (COMPAT-04)
            self._session_tokens["identity"] = tokens
            self._session_headers["Authorization"] = (
                "Bearer " + self._session_tokens["identity"]["access_token"]
            )

            _LOGGER.info("NA: IDK token obtained and stored")

            # Populate NA token registry with IDK tokens
            self._na_tokens["idk"] = {
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token"),
                "id_token": tokens["id_token"],
                "issued_at": time.time(),
                "expires_at": tokens.get("expires_in", 3600) + time.time(),
                "scopes": tokens.get("scope", ""),
            }

            try:
                # --- Brand token exchange ---
                brand_tokens = await self._exchange_brand_token(tokens["access_token"])
                self._na_tokens["brand"] = {
                    "access_token": brand_tokens.get("access_token"),
                    "refresh_token": brand_tokens.get("refresh_token"),
                    "issued_at": time.time(),
                    "expires_at": brand_tokens.get("expires_in", 3600) + time.time(),
                    "scopes": brand_tokens.get("scope", ""),
                }
                _LOGGER.info("NA: Brand token stored")

                # --- MBB client registration (skip if caller injected xclientId) ---
                if self._xclient_id is None:
                    self._xclient_id = await self._register_mbb_client()
                    # Fire callback only for newly registered xclientId
                    if self._xclient_id_callback is not None:
                        self._xclient_id_callback(self._xclient_id)
                else:
                    _LOGGER.debug("NA: Using caller-provided xclientId, skipping registration")

                # --- MBB initial token grant ---
                mbb_initial = await self._exchange_mbb_token(
                    idk_id_token=tokens["id_token"],
                    xclient_id=self._xclient_id,
                )

                # --- Immediate MBB refresh (working token is the refreshed one) ---
                mbb_working = await self._refresh_mbb_token(
                    refresh_token=mbb_initial["refresh_token"],
                    xclient_id=self._xclient_id,
                )
                self._na_tokens["mbb"] = {
                    "access_token": mbb_working.get("access_token"),
                    "refresh_token": mbb_working.get("refresh_token"),
                    "issued_at": time.time(),
                    "expires_at": mbb_working.get("expires_in", 3600) + time.time(),
                    "scopes": mbb_working.get("scope", "sc2:fal"),
                }
                _LOGGER.info("NA: MBB token obtained and immediately refreshed")

                self._na_auth_level = "full"
                _LOGGER.info("NA: Full three-token authentication complete")

            except (AuthenticationError, RequestError) as brand_mbb_error:
                _LOGGER.warning(
                    "NA: Brand/MBB token acquisition failed, continuing with IDK-only: %s",
                    brand_mbb_error,
                )
                self._na_auth_level = "idk_only"

            self._session_logged_in = True
            return True

        except (AuthenticationError, RedirectError):
            # Authentication failures already carry actionable messages — propagate to caller
            self._session_logged_in = False
            raise
        except RequestError as error:
            self._session_logged_in = False
            raise AuthenticationError(
                f"NA login failed: {error}. Verify country='US' and that credentials are correct."
            ) from error
        except KeyError as error:
            self._session_logged_in = False
            raise AuthenticationError(
                f"NA login failed — unexpected API response structure: {error}. "
                "This may indicate a VW API change."
            ) from error
        except client_exceptions.ClientError as error:
            _LOGGER.error("NA network error during login: %s", error)
            self._session_logged_in = False
            return False
        except Exception as error:
            _LOGGER.error("NA unexpected error during login: %s", error)
            self._session_logged_in = False
            return False

    async def _login(self) -> bool:
        """Login function.

        Returns:
            True if login successful, False otherwise
        """
        # Route NA users to region-specific login flow
        if self._session_region == "NA":
            return await self._login_na()

        try:
            # Clear cookies and reset headers
            self._clear_cookies()
            self._session_headers = HEADERS_SESSION.copy()
            self._session_auth_headers = HEADERS_AUTH.copy()

            # Generate PKCE parameters only if region config specifies it
            use_pkce = self._session_region_config.get("use_pkce", False)
            if use_pkce:
                self._pkce_verifier = self._generate_pkce_verifier()
                self._pkce_challenge = self._generate_pkce_challenge(
                    self._pkce_verifier
                )
                _LOGGER.debug(
                    "Generated PKCE challenge for region %s", self._session_region
                )
            else:
                self._pkce_verifier = None
                self._pkce_challenge = None
                _LOGGER.debug("PKCE disabled for region %s", self._session_region)

            # Get OpenID configuration for token endpoint
            openid_config = await self.get_openid_config()
            token_endpoint = openid_config["token_endpoint"]

            # Get authorization code
            auth_code = await self._get_authorization_code(openid_config)

            # Exchange code for tokens
            tokens = await self._exchange_code_for_tokens(auth_code, token_endpoint)

            # Validate token structure
            required_keys = ["access_token", "id_token", "token_type"]
            if not all(key in tokens for key in required_keys):
                _LOGGER.error(
                    "Invalid token response. Missing required keys. Got: %s",
                    list(tokens.keys()),
                )
                self._session_logged_in = False
                return False

            # Store directly as "identity"
            self._session_tokens["identity"] = tokens

            # Update authorization header
            self._session_headers["Authorization"] = (
                "Bearer " + self._session_tokens["identity"]["access_token"]
            )

            _LOGGER.debug("Successfully stored authentication tokens")

            # Mark session as logged in
            self._session_logged_in = True
            return True

        except (AuthenticationError, RequestError, RedirectError) as error:
            _LOGGER.error("Authentication error during login: %s", error)
            self._session_logged_in = False
            return False
        except client_exceptions.ClientError as error:
            _LOGGER.error("Network error during login: %s", error)
            self._session_logged_in = False
            return False
        except KeyError as error:
            _LOGGER.error("Missing required data during login: %s", error)
            self._session_logged_in = False
            return False
        except Exception as error:
            _LOGGER.error("Unexpected error during login: %s", error)
            self._session_logged_in = False
            return False

    async def _handle_action_result(self, response_raw: Any) -> Any:
        response = await response_raw.json(loads=json_loads)
        if not response:
            raise APIError("Invalid or no response from action endpoint")
        if response == 429:
            return {"id": None, "state": "Throttled"}
        request_id = response.get("data", {}).get("requestID", 0)
        _LOGGER.debug("Request returned with request id: %s", request_id)
        return {"id": str(request_id)}

    async def terminate(self) -> None:
        """Log out from connect services."""
        _LOGGER.info("Initiating logout")
        await self.logout()

    async def logout(self) -> None:
        """Logout, revoke tokens."""
        self._session_headers.pop("Authorization", None)

        if self._session_logged_in:
            if self._session_tokens.get("identity", {}).get("id_token"):
                _LOGGER.info("Revoking Identity Access Token")

            if self._session_tokens.get("identity", {}).get("refresh_token"):
                _LOGGER.info("Revoking Identity Refresh Token")
                params = {"token": self._session_tokens["identity"]["refresh_token"]}
                await self.post(f"{self._base_api}/login/v1/idk/revoke", data=params)

    # HTTP methods to API
    async def _request(self, method: str, url: str, return_raw: bool = False, _retry_401: bool = False,
                       _no_retry: bool = False, **kwargs: Any) -> Any:
        """Perform a query to the VW-Group API with retry on 429 and transient errors."""
        _LOGGER.debug('HTTP %s "%s"', method, url)
        if kwargs.get("json", None):
            _LOGGER.debug("Request payload: %s", kwargs.get("json", None))

        attempt = 0

        while True:
            try:
                async with self._session.request(
                    method,
                    url,
                    headers=self._session_headers,
                    timeout=ClientTimeout(total=TIMEOUT.seconds),
                    cookies=self._jarCookie,
                    raise_for_status=False,
                    **kwargs,
                ) as response:
                    # NA inline 401 retry (Phase 4 — unchanged)
                    if response.status == 401 and self._session_region == "NA" and not _retry_401:
                        _LOGGER.debug("NA: Got 401 on %s, attempting inline token refresh and retry", url)
                        try:
                            token_type = self._classify_endpoint(url)
                            if token_type == "idk":
                                await self._refresh_idk_token()
                            elif token_type == "brand":
                                await self._refresh_brand_token()
                            elif token_type == "mbb":
                                await self._refresh_mbb_from_refresh_token()
                        except (AuthenticationError, ValueError) as refresh_exc:
                            _LOGGER.warning("NA: Inline token refresh failed for 401: %s", refresh_exc)
                        else:
                            return await self._request(method, url, return_raw=return_raw, _retry_401=True, **kwargs)

                    # Phase 5: 429 handling BEFORE raise_for_status
                    if response.status == 429 and not _no_retry and attempt < MAX_RETRIES_ON_RATE_LIMIT:
                        retry_after_raw = response.headers.get("Retry-After")
                        if retry_after_raw:
                            try:
                                delay = max(float(retry_after_raw), 1.0)
                            except (ValueError, TypeError):
                                delay = float(2 ** attempt)
                        else:
                            delay = float(2 ** attempt)  # 1s, 2s, 4s
                        attempt += 1
                        self._is_throttled = True
                        self._service_status["throttled"] = True
                        _LOGGER.warning(
                            "Rate limited, retrying in %.0fs (attempt %d/%d)",
                            delay, attempt, MAX_RETRIES_ON_RATE_LIMIT,
                        )
                        await asyncio.sleep(delay)
                        continue  # retry the while loop

                    # All retries exhausted (or _no_retry): surface the error
                    response.raise_for_status()

                    # Successful response — reset throttle state
                    self._is_throttled = False
                    self._service_status["throttled"] = False

                    # Update cookie jar
                    if self._jarCookie is not None:
                        self._jarCookie.update(response.cookies)
                    else:
                        self._jarCookie = response.cookies

                    # Update service status
                    await self.update_service_status(url, response.status)

                    try:
                        if response.status == 204:
                            if return_raw:
                                res = response
                            else:
                                res = {"status_code": response.status}
                        elif 200 <= response.status < 300:
                            res = await response.json(loads=json_loads)
                        else:
                            res = {}
                            _LOGGER.debug(
                                "Not success status code [%s] response: %s",
                                response.status,
                                response.text,
                            )
                    except Exception:  # pylint: disable=broad-exception-caught
                        res = {}
                        _LOGGER.debug(
                            "Something went wrong [%s] response: %s",
                            response.status,
                            response.text,
                        )
                        if return_raw:
                            return response
                        return res

                    _LOGGER.debug(
                        'Request for "%s" returned with status code [%s], headers: %s, response: %s',
                        url,
                        response.status,
                        response.headers,
                        res,
                    )

                    if return_raw:
                        res = response
                    return res

            except (client_exceptions.ClientConnectionError, client_exceptions.ServerTimeoutError) as net_err:
                if _no_retry or attempt >= MAX_RETRIES_ON_RATE_LIMIT:
                    await self.update_service_status(url, 1000)
                    raise net_err from None
                delay = float(2 ** attempt)
                attempt += 1
                _LOGGER.warning(
                    "Transient network error, retrying in %.0fs (attempt %d/%d): %s",
                    delay, attempt, MAX_RETRIES_ON_RATE_LIMIT, net_err,
                )
                await asyncio.sleep(delay)
                # continue is implicit — while loop wraps the try/except

            except client_exceptions.ClientResponseError as httperror:
                await self.update_service_status(url, httperror.code)
                raise httperror from None

            except Exception as error:
                await self.update_service_status(url, 1000)
                raise error from None

    async def get(self, url: str, vin: str = "", tries: int = 0) -> Any:
        """Perform a get query."""
        try:
            return await self._request(METH_GET, url)
        except client_exceptions.ClientResponseError as error:
            if error.status == 400:
                _LOGGER.error(
                    'Got HTTP 400 "Bad Request" from server, this request might be malformed or not implemented'
                    " correctly for this vehicle"
                )
            elif error.status == 401:
                _LOGGER.warning(
                    'Received "unauthorized" error while fetching data: %s', error
                )
                self._session_logged_in = False
            elif error.status == 429:
                # Retry exhausted in _request() — surface as Throttled state
                return {"state": "Throttled"}
            elif error.status == 500:
                _LOGGER.debug(
                    "Got HTTP 500 from server, service might be temporarily unavailable"
                )
            elif error.status == 502:
                _LOGGER.debug(
                    "Got HTTP 502 from server, this request might not be supported for this vehicle"
                )
            else:
                _LOGGER.error("Got unhandled error from server: %s", error.status)
            return {"status_code": error.status}

    async def post(self, url: str, vin: str = "", tries: int = 0, return_raw: bool = False, **data: Any) -> Any:
        """Perform a post query."""
        if data:
            return await self._request(
                METH_POST, url, return_raw=return_raw, **data
            )
        return await self._request(METH_POST, url, return_raw=return_raw)

    async def put(self, url: str, vin: str = "", tries: int = 0, return_raw: bool = False, **data: Any) -> Any:
        """Perform a put query."""
        if data:
            return await self._request(METH_PUT, url, return_raw=return_raw, **data)
        return await self._request(METH_PUT, url, return_raw=return_raw)

    # Update data for all Vehicles
    async def update(self) -> bool:
        """Update status."""
        if not self.logged_in:
            if not await self._login():
                _LOGGER.warning("Login for %s account failed!", BRAND)
                return False
        try:
            if not await self.validate_tokens():
                _LOGGER.info(
                    "Session expired. Initiating new login for %s account", BRAND
                )
                if not await self.doLogin():
                    _LOGGER.warning("Login for %s account failed!", BRAND)
                    raise AuthenticationError(f"Login for {BRAND} account failed")
            else:
                _LOGGER.debug("Going to call vehicle updates")
                # Get all Vehicle objects and update in parallell
                updatelist = [vehicle.update() for vehicle in self.vehicles]
                # Wait for all data updates to complete
                await asyncio.gather(*updatelist)

                return True
        except (OSError, LookupError, Exception) as error:  # pylint: disable=broad-exception-caught
            _LOGGER.warning("Could not update information: %s", error)
        return False

    async def getPendingRequests(self, vin: str) -> Any:
        """Get status information for pending requests."""
        if not await self.validate_tokens():
            return False
        try:
            response = await self.get(
                f"{self._base_api}/vehicle/v1/vehicles/{vin}/pendingrequests"
            )

            if response:
                response["refreshTimestamp"] = datetime.now(UTC)
                return response

        except Exception as error:  # pylint: disable=broad-exception-caught
            _LOGGER.warning(
                "Could not fetch information for pending requests, error: %s", error
            )
        return False

    async def getOperationList(self, vin: str) -> Any:
        """Collect operationlist for VIN, supported/licensed functions."""
        if not await self.validate_tokens():
            return False
        try:
            response = await self.get(
                f"{self._base_api}/vehicle/v1/vehicles/{vin}/capabilities", ""
            )
            if response.get("capabilities", False):
                data = response
            elif response.get("status_code", {}):
                _LOGGER.warning(
                    "Could not fetch operation list, HTTP status code: %s",
                    response.get("status_code"),
                )
                data = response
            else:
                _LOGGER.info("Could not fetch operation list: %s", response)
                data = {"error": "unknown"}
        except Exception as error:  # pylint: disable=broad-exception-caught
            _LOGGER.warning("Could not fetch operation list, error: %s", error)
            data = {"error": "unknown"}
        return data

    async def getSelectiveStatus(self, vin: str, services: list[str]) -> Any:
        """Get status information for specified services."""
        if not await self.validate_tokens():
            return False
        try:
            response = await self.get(
                f"{self._base_api}/vehicle/v1/vehicles/{vin}/selectivestatus?jobs={','.join(services)}",
                "",
            )

            for service in services:
                if not response.get(service):
                    _LOGGER.debug(
                        "Did not receive return data for requested service %s. (This is expected for several service/car combinations)",
                        service,
                    )

            if response:
                response.update({"refreshTimestamp": datetime.now(UTC)})
                return response

        except Exception as error:  # pylint: disable=broad-exception-caught
            _LOGGER.warning("Could not fetch selectivestatus, error: %s", error)
        return False

    async def getVehicleData(self, vin: str) -> Any:
        """Get car information like VIN, nickname, etc."""
        if not await self.validate_tokens():
            return False
        try:
            response = await self.get(f"{self._base_api}/vehicle/v2/vehicles", "")

            for vehicle in response.get("data"):
                if vehicle.get("vin") == vin:
                    return {"vehicle": vehicle}

            _LOGGER.warning("Could not fetch vehicle data for vin %s", vin)

        except Exception as error:  # pylint: disable=broad-exception-caught
            _LOGGER.warning("Could not fetch vehicle data, error: %s", error)
        return False

    async def getParkingPosition(self, vin: str) -> Any:
        """Get information about the parking position."""
        if not await self.validate_tokens():
            return False
        try:
            response = await self.get(
                f"{self._base_api}/vehicle/v1/vehicles/{vin}/parkingposition", ""
            )

            if "data" in response:
                return {"isMoving": False, "parkingposition": response["data"]}
            if response.get("status_code", {}):
                if response.get("status_code", 0) == 204:
                    _LOGGER.debug(
                        "Seems car is moving, HTTP 204 received from parkingposition"
                    )
                    return {"isMoving": True, "parkingposition": {}}

                _LOGGER.warning(
                    "Could not fetch parkingposition, HTTP status code: %s",
                    response.get("status_code"),
                )
            else:
                _LOGGER.info(
                    "Unhandled error while trying to fetch parkingposition data"
                )
        except Exception as error:  # pylint: disable=broad-exception-caught
            _LOGGER.warning("Could not fetch parkingposition, error: %s", error)
        return False

    async def getTripLast(self, vin: str) -> Any:
        """Get car information like VIN, nickname, etc."""
        if not await self.validate_tokens():
            return False
        try:
            response = await self.get(
                f"{self._base_api}/vehicle/v1/trips/{vin}/shortterm/last", ""
            )
            if "data" in response:
                return {"trip_last": response["data"]}

            if response.get("status_code", 0) in [404, 502]:
                _LOGGER.debug("No last trip data available for this vehicle")
            else:
                _LOGGER.warning(
                    "Could not fetch last trip data, server response: %s", response
                )

        except Exception as error:  # pylint: disable=broad-exception-caught
            _LOGGER.warning("Could not fetch last trip data, error: %s", error)
        return False

    async def getTripRefuel(self, vin: str) -> Any:
        """Get information about the trip since last refuel"""
        if not await self.validate_tokens():
            return False
        try:
            response = await self.get(
                f"{self._base_api}/vehicle/v1/trips/{vin}/cyclic/last", ""
            )
            if "data" in response:
                return {"trip_refuel": response["data"]}

            if response.get("status_code", 0) in [404, 502]:
                _LOGGER.debug("No refuel trip data available for this vehicle")
            else:
                _LOGGER.warning(
                    "Could not fetch refuel trip data, server response: %s", response
                )

        except Exception as error:  # pylint: disable=broad-exception-caught
            _LOGGER.warning("Could not fetch last trip data, error: %s", error)
        return False

    async def getTripLongterm(self, vin: str) -> Any:
        """Get information about the trip last longterm"""
        if not await self.validate_tokens():
            return False
        try:
            response = await self.get(
                f"{self._base_api}/vehicle/v1/trips/{vin}/longterm/last", ""
            )
            if "data" in response:
                return {"trip_longterm": response["data"]}

            if response.get("status_code", 0) in [404, 502]:
                _LOGGER.debug("No longterm trip data available for this vehicle")
            else:
                _LOGGER.warning(
                    "Could not fetch longterm trip data, server response: %s", response
                )

        except Exception as error:  # pylint: disable=broad-exception-caught
            _LOGGER.warning("Could not fetch last trip data, error: %s", error)
        return False

    async def wakeUpVehicle(self, vin: str) -> Any:
        """Wake up vehicle to send updated data to VW Backend."""
        if not await self.validate_tokens():
            return False
        try:
            return await self.post(
                f"{self._base_api}/vehicle/v1/vehicles/{vin}/vehiclewakeuptrigger",
                json={},
                return_raw=True,
            )

        except Exception as error:  # pylint: disable=broad-exception-caught
            _LOGGER.warning("Could not refresh the data, error: %s", error)
        return False

    async def get_request_status(self, vin: str, requestId: str, actionId: str = "") -> Any:
        """Return status of a request ID for a given section ID."""
        if self.logged_in is False:
            if not await self.doLogin():
                _LOGGER.warning("Login for %s account failed!", BRAND)
                raise AuthenticationError(f"Login for {BRAND} account failed")
        try:
            if not await self.validate_tokens():
                _LOGGER.info(
                    "Session expired. Initiating new login for %s account", BRAND
                )
                if not await self.doLogin():
                    _LOGGER.warning("Login for %s account failed!", BRAND)
                    raise AuthenticationError(f"Login for {BRAND} account failed")

            response = await self.getPendingRequests(vin)

            requests = response.get("data", [])
            result = None
            for request in requests:
                if request.get("id", "") == requestId:
                    result = request.get("status")

            # Translate status messages to meaningful info
            if result in ("in_progress", "queued", "fetched"):
                status = "In Progress"
            elif result in ("request_fail", "failed"):
                status = "Failed"
            elif result == "unfetched":
                status = "No response"
            elif result in ("request_successful", "successful"):
                status = "Success"
            elif result == "fail_ignition_on":
                status = "Failed because ignition is on"
            else:
                status = str(result) if result is not None else "Unknown"
        except Exception as error:
            _LOGGER.warning("Failure during get request status: %s", error)
            raise RequestError(f"Failure during get request status: {error}") from error
        else:
            return status

    async def check_spin_state(self) -> bool:
        """Determine SPIN state to prevent lockout due to wrong SPIN."""
        result = await self.get(f"{self._base_api}/vehicle/v1/spin/state")
        remainingTries = result.get("remainingTries", None)
        if remainingTries is None:
            raise SPINError("Couldn't determine S-PIN state")

        if remainingTries < 3:
            raise SPINError(
                "Remaining tries for S-PIN is < 3. Bailing out for security reasons. "
                "To resume operation, please make sure the correct S-PIN has been set in the integration "
                "and then use the correct S-PIN once via the Volkswagen app."
            )

        return True

    async def setClimater(self, vin: str, data: dict[str, Any], action: bool | str) -> Any:
        """Execute climatisation actions."""
        action = "start" if action else "stop"
        try:
            response_raw = await self.post(
                f"{self._base_api}/vehicle/v1/vehicles/{vin}/climatisation/{action}",
                json=data,
                return_raw=True,
            )
            return await self._handle_action_result(response_raw)
        except Exception as e:
            raise APIError(f"Unknown error during setClimater: {str(e)}") from e

    async def setClimaterSettings(self, vin: str, data: dict[str, Any]) -> Any:
        """Execute climatisation settings."""
        try:
            response_raw = await self.put(
                f"{self._base_api}/vehicle/v1/vehicles/{vin}/climatisation/settings",
                json=data,
                return_raw=True,
            )
            return await self._handle_action_result(response_raw)
        except Exception as e:
            raise APIError(f"Unknown error during setClimaterSettings: {str(e)}") from e

    async def setAuxiliary(self, vin: str, data: dict[str, Any], action: bool | str) -> Any:
        """Execute auxiliary climatisation actions."""
        action = "start" if action else "stop"
        try:
            response_raw = await self.post(
                f"{self._base_api}/vehicle/v1/vehicles/{vin}/auxiliaryheating/{action}",
                json=data,
                return_raw=True,
            )
            return await self._handle_action_result(response_raw)
        except Exception as e:
            raise APIError(f"Unknown error during setAuxiliary: {str(e)}") from e

    async def setWindowHeater(self, vin: str, action: bool | str) -> Any:
        """Execute window heating actions."""
        action = "start" if action else "stop"
        try:
            response_raw = await self.post(
                f"{self._base_api}/vehicle/v1/vehicles/{vin}/windowheating/{action}",
                json={},
                return_raw=True,
            )
            return await self._handle_action_result(response_raw)
        except Exception as e:
            raise APIError(f"Unknown error during setWindowHeater: {str(e)}") from e

    async def setCharging(self, vin: str, action: bool | str) -> Any:
        """Execute charging actions."""
        action = "start" if action else "stop"
        try:
            response_raw = await self.post(
                f"{self._base_api}/vehicle/v1/vehicles/{vin}/charging/{action}",
                json={},
                return_raw=True,
            )
            return await self._handle_action_result(response_raw)
        except Exception as e:
            raise APIError(f"Unknown error during setCharging: {str(e)}") from e

    async def setChargingSettings(self, vin: str, data: dict[str, Any]) -> Any:
        """Execute charging actions."""
        try:
            response_raw = await self.put(
                f"{self._base_api}/vehicle/v1/vehicles/{vin}/charging/settings",
                json=data,
                return_raw=True,
            )
            return await self._handle_action_result(response_raw)
        except Exception as e:
            raise APIError(f"Unknown error during setChargingSettings: {str(e)}") from e

    async def setChargingCareModeSettings(self, vin: str, data: dict[str, Any]) -> Any:
        """Execute battery care mode actions."""
        try:
            response_raw = await self.put(
                f"{self._base_api}/vehicle/v1/vehicles/{vin}/charging/care/settings",
                json=data,
                return_raw=True,
            )
            return await self._handle_action_result(response_raw)
        except Exception as e:
            raise APIError(
                f"Unknown error during setChargingCareModeSettings: {str(e)}"
            ) from e

    async def setReadinessBatterySupport(self, vin: str, data: dict[str, Any]) -> Any:
        """Execute readiness battery support actions."""
        try:
            response_raw = await self.put(
                f"{self._base_api}/vehicle/v1/vehicles/{vin}/readiness/batterysupport",
                json=data,
                return_raw=True,
            )
            return await self._handle_action_result(response_raw)
        except Exception as e:
            raise APIError(
                f"Unknown error during setReadinessBatterySupport: {str(e)}"
            ) from e

    async def setDepartureProfiles(self, vin: str, data: dict[str, Any]) -> Any:
        """Execute departure timers actions."""
        try:
            response_raw = await self.put(
                f"{self._base_api}/vehicle/v1/vehicles/{vin}/departure/profiles",
                json=data,
                return_raw=True,
            )
            return await self._handle_action_result(response_raw)
        except Exception as e:
            raise APIError(
                f"Unknown error during setDepartureProfiles: {str(e)}"
            ) from e

    async def setClimatisationTimers(self, vin: str, data: dict[str, Any]) -> Any:
        """Execute climatisation timers actions."""
        try:
            response_raw = await self.put(
                f"{self._base_api}/vehicle/v1/vehicles/{vin}/climatisation/timers",
                json=data,
                return_raw=True,
            )
            return await self._handle_action_result(response_raw)
        except Exception as e:
            raise APIError(
                f"Unknown error during setClimatisationTimers: {str(e)}"
            ) from e

    async def setAuxiliaryHeatingTimers(self, vin: str, data: dict[str, Any]) -> Any:
        """Execute auxiliary heating timers actions."""
        try:
            response_raw = await self.put(
                f"{self._base_api}/vehicle/v1/vehicles/{vin}/auxiliaryheating/timers",
                json=data,
                return_raw=True,
            )
            return await self._handle_action_result(response_raw)
        except Exception as e:
            raise APIError(
                f"Unknown error during setAuxiliaryHeatingTimers: {str(e)}"
            ) from e

    async def setDepartureTimers(self, vin: str, data: dict[str, Any]) -> Any:
        """Execute departure timers actions."""
        try:
            response_raw = await self.put(
                f"{self._base_api}/vehicle/v1/vehicles/{vin}/departure/timers",
                json=data,
                return_raw=True,
            )
            return await self._handle_action_result(response_raw)
        except Exception as e:
            raise APIError(f"Unknown error during setDepartureTimers: {str(e)}") from e

    async def setLock(self, vin: str, lock: bool | str, spin: str) -> Any:
        """Remote lock and unlock actions."""
        await self.check_spin_state()
        action = "lock" if lock else "unlock"
        try:
            response_raw = await self.post(
                f"{self._base_api}/vehicle/v1/vehicles/{vin}/access/{action}",
                json={"spin": spin},
                return_raw=True,
            )
            return await self._handle_action_result(response_raw)
        except Exception as e:
            raise APIError(f"Unknown error during setLock: {str(e)}") from e

    async def setHonkAndFlash(self, vin: str, position: dict[str, Any]) -> Any:
        """Remote Honk and Flash actions."""
        await self.check_spin_state()
        try:
            response_raw = await self.post(
                f"{self._base_api}/vehicle/v1/vehicles/{vin}/honkandflash",
                json={
                    "userPosition": {
                        "longitude": position["lng"],
                        "latitude": position["lat"],
                    },
                    "mode": "flash",
                    "duration_s": 15,
                },
                return_raw=True,
            )
            return await self._handle_action_result(response_raw)
        except Exception as e:
            raise APIError(f"Unknown error during setHonkAndFlash: {str(e)}") from e

    # Token handling #
    def _is_token_expiring(self, entry: dict, now: float, window_seconds: float = 900) -> bool:
        """Return True if token entry expires within window_seconds from now.

        Uses expires_at if present. Falls back to issued_at + assumed lifetime
        (3600s for access tokens) if expires_at is missing.

        Args:
            entry: Token dict with optional 'expires_at' and 'issued_at' keys.
            now: Current Unix timestamp.
            window_seconds: Seconds before expiry to consider token "expiring". Default: 900 (15 min).

        Returns:
            True if token will expire within window_seconds, False otherwise.
        """
        expires_at = entry.get("expires_at")
        if expires_at is None:
            issued_at = entry.get("issued_at", now)
            expires_at = issued_at + 3600  # assumed 1h lifetime if unknown
        return (expires_at - now) <= window_seconds

    async def _validate_na_tokens(self) -> bool:
        """Proactively refresh NA tokens expiring within 15 minutes.

        Checks IDK, Brand, and MBB token expiry. IDK refresh cascades to Brand
        refresh automatically (Brand is derived from IDK access_token).
        MBB is refreshed independently.

        For idk_only auth level: only IDK is checked and refreshed.

        Returns:
            True if all available tokens are valid after any needed refresh.
            False if a critical refresh fails (IDK failure is critical).
        """
        if not self._na_tokens:
            _LOGGER.warning("NA: _validate_na_tokens called but _na_tokens is empty")
            return False

        now = time.time()
        window = 900  # 15-minute proactive refresh window

        # IDK token — critical; failure means session cannot continue
        idk_entry = self._na_tokens.get("idk", {})
        if self._is_token_expiring(idk_entry, now, window):
            _LOGGER.debug("NA: IDK token expiring within %s seconds, refreshing", window)
            try:
                await self._refresh_idk_token()
                # Note: _refresh_idk_token() cascades Brand refresh automatically
            except AuthenticationError as exc:
                _LOGGER.error("NA: IDK token refresh failed: %s", exc)
                return False

        elif "brand" in self._na_tokens and self._na_auth_level == "full":
            # IDK not expiring — check Brand independently (IDK refresh cascade didn't run)
            brand_entry = self._na_tokens.get("brand", {})
            if self._is_token_expiring(brand_entry, now, window):
                _LOGGER.debug("NA: Brand token expiring within %s seconds, refreshing", window)
                try:
                    await self._refresh_brand_token()
                except AuthenticationError as exc:
                    _LOGGER.warning("NA: Brand token refresh failed (non-critical): %s", exc)
                    # Brand failure is non-critical — degrade to idk_only
                    self._na_auth_level = "idk_only"

        # MBB token — independent of IDK refresh path
        if self._na_auth_level == "full" and "mbb" in self._na_tokens:
            mbb_entry = self._na_tokens.get("mbb", {})
            if self._is_token_expiring(mbb_entry, now, window):
                _LOGGER.debug("NA: MBB token expiring within %s seconds, refreshing", window)
                try:
                    await self._refresh_mbb_from_refresh_token()
                except AuthenticationError as exc:
                    _LOGGER.warning("NA: MBB token refresh failed (non-critical): %s", exc)
                    # MBB failure is non-critical for IDK-accessible endpoints

        return True

    async def validate_tokens(self) -> bool:
        """Validate expiry of tokens."""
        # NA region: use dedicated token lifecycle validation
        if self._session_region == "NA":
            return await self._validate_na_tokens()

        try:
            idtoken = self._session_tokens["identity"]["id_token"]
            atoken = self._session_tokens["identity"]["access_token"]
        except KeyError as error:
            _LOGGER.warning("Token validation failed - missing token data: %s", error)
            return False
        id_exp = jwt.decode(
            idtoken,
            options={"verify_signature": False, "verify_aud": False},
            algorithms=JWT_ALGORITHMS,
        ).get("exp", None)
        at_exp = jwt.decode(
            atoken,
            options={"verify_signature": False, "verify_aud": False},
            algorithms=JWT_ALGORITHMS,
        ).get("exp", None)
        id_dt = datetime.fromtimestamp(int(id_exp))
        at_dt = datetime.fromtimestamp(int(at_exp))
        now = datetime.now()
        later = now + self._session_refresh_interval

        # Check if tokens have expired, or expires now
        if now >= id_dt or now >= at_dt:
            _LOGGER.debug("Tokens have expired. Try to fetch new tokens")
            if await self.refresh_tokens():
                _LOGGER.debug("Successfully refreshed tokens")
            else:
                return False
        # Check if tokens expires before next update
        elif later >= id_dt or later >= at_dt:
            _LOGGER.debug("Tokens about to expire. Try to fetch new tokens")
            if await self.refresh_tokens():
                _LOGGER.debug("Successfully refreshed tokens")
            else:
                return False
        return True

    async def refresh_tokens(self) -> bool:
        """Refresh tokens."""
        try:
            tHeaders = {
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": USER_AGENT,
                "x-android-package-name": ANDROID_PACKAGE_NAME,
            }

            body = {
                "grant_type": "refresh_token",
                "refresh_token": self._session_tokens["identity"]["refresh_token"],
                "client_id": self._client_id,  # Use region-specific client ID
            }
            response = await self._session.post(
                url=f"{self._base_api}/login/v1/idk/token",
                headers=tHeaders,
                data=body,
            )
            await self.update_service_status("token", response.status)
            if response.status == 200:
                tokens = await response.json()

                if not tokens or "access_token" not in tokens:
                    _LOGGER.error("Invalid refresh token response: %s", tokens)
                    return False
                for token in tokens:
                    self._session_tokens["identity"][token] = tokens[token]
                self._session_headers["Authorization"] = (
                    "Bearer " + self._session_tokens["identity"]["access_token"]
                )
                _LOGGER.debug("Successfully refreshed and updated tokens")
            else:
                response_text = await response.text()
                _LOGGER.warning(
                    "Token refresh failed with status %s: %s",
                    response.status,
                    response_text,
                )
                return False
        except Exception as error:  # pylint: disable=broad-exception-caught
            _LOGGER.warning("Could not refresh tokens: %s", error)
            return False
        else:
            return True

    async def update_service_status(self, url: str, response_code: int) -> None:
        """Update service status."""
        if response_code in [200, 204, 207]:
            status = "Up"
        elif response_code == 401:
            status = "Unauthorized"
        elif response_code == 403:
            status = "Forbidden"
        elif response_code == 429:
            status = "Rate limited"
        elif response_code == 1000:
            status = "Error"
        else:
            status = "Down"

        if "vehicle/v2/vehicles" in url:
            self._service_status["vehicles"] = status
        elif "parkingposition" in url:
            self._service_status["parkingposition"] = status
        elif "/vehicle/v1/trips/" in url:
            self._service_status["trips"] = status
        elif "capabilities" in url:
            self._service_status["capabilities"] = status
        elif "selectivestatus" in url:
            self._service_status["selectivestatus"] = status
        elif "token" in url:
            self._service_status["token"] = status
        else:
            _LOGGER.debug('Unhandled API URL: "%s"', url)

    async def get_service_status(self) -> dict[str, Any]:
        """Return list of service statuses."""
        _LOGGER.debug("Getting API status updates")
        return self._service_status

    # Class helpers #
    @property
    def vehicles(self) -> list[Vehicle]:
        """Return list of Vehicle objects."""
        return self._vehicles

    @property
    def logged_in(self) -> bool:
        """Return cached logged in state.

        Not actually checking anything.
        """
        return self._session_logged_in

    @property
    def na_auth_level(self) -> str | None:
        """Return the NA authentication level.

        Returns:
            "full" if all three tokens (IDK, Brand, MBB) were obtained.
            "idk_only" if only the IDK token was obtained (Brand/MBB failed).
            None for EMEA connections or before login.
        """
        return self._na_auth_level

    @property
    def is_throttled(self) -> bool:
        """Return True if the last request exhausted all retry attempts due to rate limiting.

        Useful for Home Assistant integrations to skip a poll cycle when throttled.
        Resets to False on the next successful request.
        """
        return self._is_throttled

    def vehicle(self, vin: str) -> Vehicle | None:
        """Return vehicle object for given vin."""
        return next(
            (
                vehicle
                for vehicle in self.vehicles
                if vehicle.unique_id is not None and vehicle.unique_id.lower() == vin.lower()
            ),
            None,
        )

    def hash_spin(self, challenge: str, spin: str) -> str:
        """Compute SPIN hash for NA vehicle session authentication.

        Algorithm confirmed from APK decompilation (f90/y0.java RemoteStartUseCase):
        SHA-512(UTF-8("{challenge}.{spin}"))

        The challenge is the hex string returned by GET ss/v1/user/{userId}/challenge.
        The spin is the 4-digit security PIN as a string (e.g. "0560").
        Both are concatenated with "." separator and hashed as UTF-8 text.
        """
        combined = f"{challenge}.{spin}"
        return hashlib.sha512(combined.encode("utf-8")).hexdigest()

    async def validate_login(self) -> bool:
        """Check that we have a valid access token."""
        try:
            if not await self.validate_tokens():
                return False
        except OSError as error:
            _LOGGER.warning("Could not validate login: %s", error)
            return False
        else:
            return True
