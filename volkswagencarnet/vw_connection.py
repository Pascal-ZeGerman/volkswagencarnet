#!/usr/bin/env python3
"""Communicate with Volkswagen Connect services."""

from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import logging
from random import randint, random
import secrets
import time
from urllib.parse import parse_qs, urljoin, urlparse
from typing import Dict, Optional

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

from .vw_utilities import json_loads
from .vw_vehicle import Vehicle

MAX_RETRIES_ON_RATE_LIMIT = 3

_LOGGER = logging.getLogger(__name__)  # pylint: disable=unreachable

TIMEOUT = timedelta(seconds=30)
JWT_ALGORITHMS = ["RS256"]


# noinspection PyPep8Naming
class Connection:
    """Connection to VW-Group Connect services."""

    _login_lock = asyncio.Lock()

    # Init connection class
    def __init__(
        self,
        session,
        username,
        password,
        country=COUNTRY,
        interval=timedelta(minutes=5),
        xclient_id: str | None = None,
        on_xclient_id=None,
    ) -> None:
        """Initialize."""
        self._session = session
        self._session_headers = HEADERS_SESSION.copy()
        self._session_auth_headers = HEADERS_AUTH.copy()
        self._session_refresh_interval = interval
        self._session_logged_in = False
        self._session_first_update = False
        self._session_auth_username = username
        self._session_auth_password = password
        self._session_tokens = {}
        self._session_country = country.upper()

        # Determine region from country
        self._session_region = get_region_from_country(self._session_country)
        self._session_region_config = get_region_config(self._session_region)

        # Set region-specific base API (will be discovered for NA)
        self._base_api = self._session_region_config.get("base_api")

        # Set region-specific client ID for OAuth
        self._client_id = self._session_region_config.get("client_id", CLIENT_ID)

        self._vehicles = []

        self._jarCookie = None

        self._service_status = {}

        # NA three-token registry (empty for EMEA, populated during NA login)
        self._na_tokens: dict = {}   # keys: "idk", "brand", "mbb"
        self._xclient_id: str | None = xclient_id  # caller-injected or registered during login
        self._xclient_id_callback = on_xclient_id  # called only when NEW xclientId generated
        self._na_auth_level: str | None = None  # "full", "idk_only", or None (EMEA)

    def _clear_cookies(self):
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
                async with self._session.get(
                    url=f"{candidate}/login/v1/idk/openid-configuration",
                    timeout=ClientTimeout(total=5),
                ) as req:
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

    # API Login
    async def doLogin(self, tries: int = 1):
        """Login method, clean login."""
        async with self._login_lock:
            _LOGGER.debug("Initiating new login")

            # Discover endpoints if needed
            if self._session_region == "NA" and not self._base_api:
                if not await self._discover_endpoints():
                    _LOGGER.error("Endpoint discovery failed for NA region")
                    return False

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
            loaded_vehicles = await self.get(
                url=f"{self._base_api}/vehicle/v2/vehicles"
            )
            # Add Vehicle class object for all VIN-numbers from account
            if loaded_vehicles.get("data") is not None:
                _LOGGER.debug("Found vehicle(s) associated with account")
                self._vehicles = []
                for vehicle in loaded_vehicles.get("data"):
                    self._vehicles.append(Vehicle(self, vehicle.get("vin")))
            else:
                _LOGGER.warning("Failed to login to Volkswagen Connect API")
                self._session_logged_in = False
                return False

            # Update all vehicles data before returning
            await self.update()
            return True

    async def get_openid_config(self) -> Dict[str, str]:
        """Get OpenID config."""
        # Use identity_endpoint for NA region, otherwise use base_api
        identity_endpoint = self._session_region_config.get("identity_endpoint")
        if identity_endpoint:
            config_url = f"{identity_endpoint}/.well-known/openid-configuration"
            _LOGGER.debug(
                "Requesting openid config from identity endpoint: %s", config_url
            )
        else:
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

            # If redirected, fetch the new location
            req = await self._session.get(
                url=ref, headers=self._session_auth_headers, allow_redirects=False
            )

            if req.status != 200:
                raise AuthenticationError("Failed to fetch authorization endpoint")

            return await req.text()

        except Exception as e:
            _LOGGER.warning("Error during fetching authorization page: %s", str(e))
            raise

    def extract_state_token(self, page_content: str) -> Optional[str]:
        """Extract state token from a page."""
        soup = BeautifulSoup(page_content, "html.parser")
        state_input = soup.select_one('input[name="state"]')
        if not state_input or not state_input.get("value"):
            _LOGGER.debug("State token not found.")
            return None
        return state_input["value"]

    async def post_form(
        self, session, url: str, headers: dict, form_data: dict, redirect: bool = True
    ) -> str:
        """Post a form and check for success."""
        req = await session.post(
            url, headers=headers, data=form_data, allow_redirects=redirect
        )

        # Redirect case
        if not redirect and req.status == 302:
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

            # Unknown 400 error
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

    async def handle_login_with_password(self, session, url, auth_headers, form_data):
        """Handle login with email and password."""
        return await self.post_form(session, url, auth_headers, form_data, False)

    async def follow_redirects(
        self, session, pw_url: str, redirect_location: str
    ) -> str:
        """Handle redirects."""
        ref = urljoin(pw_url, redirect_location)
        MAX_REDIRECT_DEPTH = 10
        max_depth = MAX_REDIRECT_DEPTH
        stop_uri = self._session_region_config.get("redirect_uri", APP_URI)
        while not ref.startswith(stop_uri):
            if max_depth == 0:
                raise RedirectError(
                    f"Too many redirects during login flow (max depth: {MAX_REDIRECT_DEPTH}). "
                    "This might indicate an authentication loop."
                )
            response = await session.get(
                url=ref, headers=self._session_auth_headers, allow_redirects=False
            )

            # Check if we hit a terms and conditions page (HTTP 200 with no redirect)
            if response.status == 200 and "Location" not in response.headers:
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

            if "Location" not in response.headers:
                _LOGGER.warning("Failed to find next redirect location")
                raise RedirectError("Failed to find next redirect location")
            ref = urljoin(ref, response.headers["Location"])
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

    async def _exchange_code_for_tokens(
        self, auth_code: str, token_endpoint: str
    ) -> dict:
        """Exchange authorization code for access tokens.

        Args:
            auth_code: Authorization code from login flow
            token_endpoint: Token endpoint URL

        Returns:
            Dictionary containing tokens

        Raises:
            AuthenticationError: If token exchange fails
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

        # Token endpoint
        token_response = await self.post_form(
            self._session, token_endpoint, self._session_auth_headers, token_body
        )

        return json_loads(token_response)

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

    async def _login_na(self) -> bool:
        """NA-specific login flow using identity.na.vwgroup.io.

        Obtains IDK access_token and refresh_token via OAuth authorization
        code flow with X-QMAuth header on token exchange.

        NOTE: IDK-only BFF access hypothesis (whether the IDK token alone is
        sufficient for /vehicle/v1/vehicles without a Brand token) is validated
        in Phase 3 via test fixture scenarios, not via a live probe here.

        Returns:
            True if login successful, False otherwise
        """
        try:
            # Clear cookies and reset headers (same as _login())
            self._clear_cookies()
            self._session_headers = HEADERS_SESSION.copy()
            self._session_auth_headers = HEADERS_AUTH.copy()

            # NA does not use PKCE (app does not send code_challenge)
            self._pkce_verifier = None
            self._pkce_challenge = None

            # Get OpenID config (routes to identity.na.vwgroup.io for NA)
            openid_config = await self.get_openid_config()
            token_endpoint = openid_config["token_endpoint"]

            # Get authorization code via standard OAuth form flow
            auth_code = await self._get_authorization_code(openid_config)

            # Exchange code for tokens (X-QMAuth header injected inside for NA)
            tokens = await self._exchange_code_for_tokens(auth_code, token_endpoint)

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
                "expires_at": tokens.get("expires_in", 3600) + time.time(),
                "scopes": tokens.get("scope", ""),
            }

            try:
                # --- Brand token exchange ---
                brand_tokens = await self._exchange_brand_token(tokens["access_token"])
                self._na_tokens["brand"] = {
                    "access_token": brand_tokens.get("access_token"),
                    "refresh_token": brand_tokens.get("refresh_token"),
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

        except (AuthenticationError, RequestError, RedirectError) as error:
            _LOGGER.error("NA authentication error during login: %s", error)
            self._session_logged_in = False
            return False
        except client_exceptions.ClientError as error:
            _LOGGER.error("NA network error during login: %s", error)
            self._session_logged_in = False
            return False
        except KeyError as error:
            _LOGGER.error("NA missing required data during login: %s", error)
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

    async def _handle_action_result(self, response_raw):
        response = await response_raw.json(loads=json_loads)
        if not response:
            raise APIError("Invalid or no response from action endpoint")
        if response == 429:
            return {"id": None, "state": "Throttled"}
        request_id = response.get("data", {}).get("requestID", 0)
        _LOGGER.debug("Request returned with request id: %s", request_id)
        return {"id": str(request_id)}

    async def terminate(self):
        """Log out from connect services."""
        _LOGGER.info("Initiating logout")
        await self.logout()

    async def logout(self):
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
    async def _request(self, method, url, return_raw=False, **kwargs):
        """Perform a query to the VW-Group API."""
        _LOGGER.debug('HTTP %s "%s"', method, url)
        if kwargs.get("json", None):
            _LOGGER.debug("Request payload: %s", kwargs.get("json", None))
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
                response.raise_for_status()

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
        except client_exceptions.ClientResponseError as httperror:
            # Update service status
            await self.update_service_status(url, httperror.code)
            raise httperror from None
        except Exception as error:
            # Update service status
            await self.update_service_status(url, 1000)
            raise error from None

    async def get(self, url, vin="", tries=0):
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
            elif error.status == 429 and tries < MAX_RETRIES_ON_RATE_LIMIT:
                delay = randint(1, 3 + tries * 2)
                _LOGGER.debug(
                    "Server side throttled. Waiting %s, try %s", delay, tries + 1
                )
                await asyncio.sleep(delay)
                return await self.get(url, vin, tries + 1)
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

    async def post(self, url, vin="", tries=0, return_raw=False, **data):
        """Perform a post query."""
        try:
            if data:
                return await self._request(
                    METH_POST, url, return_raw=return_raw, **data
                )
            return await self._request(METH_POST, url, return_raw=return_raw)
        except client_exceptions.ClientResponseError as error:
            if error.status == 429 and tries < MAX_RETRIES_ON_RATE_LIMIT:
                delay = randint(1, 3 + tries * 2)
                _LOGGER.debug(
                    "Server side throttled. Waiting %s, try %s", delay, tries + 1
                )
                await asyncio.sleep(delay)
                return await self.post(
                    url, vin, tries + 1, return_raw=return_raw, **data
                )
            raise

    async def put(self, url, vin="", tries=0, return_raw=False, **data):
        """Perform a put query."""
        try:
            if data:
                return await self._request(METH_PUT, url, return_raw=return_raw, **data)
            return await self._request(METH_PUT, url, return_raw=return_raw)
        except client_exceptions.ClientResponseError as error:
            if error.status == 429 and tries < MAX_RETRIES_ON_RATE_LIMIT:
                delay = randint(1, 3 + tries * 2)
                _LOGGER.debug(
                    "Server side throttled. Waiting %s, try %s", delay, tries + 1
                )
                await asyncio.sleep(delay)
                return await self.put(
                    url, vin, tries + 1, return_raw=return_raw, **data
                )
            raise

    # Update data for all Vehicles
    async def update(self):
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

    async def getPendingRequests(self, vin):
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

    async def getOperationList(self, vin):
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

    async def getSelectiveStatus(self, vin, services):
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

    async def getVehicleData(self, vin):
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

    async def getParkingPosition(self, vin):
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

    async def getTripLast(self, vin):
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

    async def getTripRefuel(self, vin):
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

    async def getTripLongterm(self, vin):
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

    async def wakeUpVehicle(self, vin):
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

    async def get_request_status(self, vin, requestId, actionId=""):
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
                status = result
        except Exception as error:
            _LOGGER.warning("Failure during get request status: %s", error)
            raise RequestError(f"Failure during get request status: {error}") from error
        else:
            return status

    async def check_spin_state(self):
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

    async def setClimater(self, vin, data, action):
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

    async def setClimaterSettings(self, vin, data):
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

    async def setAuxiliary(self, vin, data, action):
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

    async def setWindowHeater(self, vin, action):
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

    async def setCharging(self, vin, action):
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

    async def setChargingSettings(self, vin, data):
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

    async def setChargingCareModeSettings(self, vin, data):
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

    async def setReadinessBatterySupport(self, vin, data):
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

    async def setDepartureProfiles(self, vin, data):
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

    async def setClimatisationTimers(self, vin, data):
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

    async def setAuxiliaryHeatingTimers(self, vin, data):
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

    async def setDepartureTimers(self, vin, data):
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

    async def setLock(self, vin, lock, spin):
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

    async def setHonkAndFlash(self, vin, position):
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
    async def validate_tokens(self) -> bool:
        """Validate expiry of tokens."""
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

    async def refresh_tokens(self):
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

    async def update_service_status(self, url, response_code):
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

    async def get_service_status(self):
        """Return list of service statuses."""
        _LOGGER.debug("Getting API status updates")
        return self._service_status

    # Class helpers #
    @property
    def vehicles(self):
        """Return list of Vehicle objects."""
        return self._vehicles

    @property
    def logged_in(self):
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

    def vehicle(self, vin):
        """Return vehicle object for given vin."""
        return next(
            (
                vehicle
                for vehicle in self.vehicles
                if vehicle.unique_id.lower() == vin.lower()
            ),
            None,
        )

    def hash_spin(self, challenge, spin):
        """Convert SPIN and challenge to hash."""
        spinArray = bytearray.fromhex(spin)
        byteChallenge = bytearray.fromhex(challenge)
        spinArray.extend(byteChallenge)
        return hashlib.sha512(spinArray).hexdigest()

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
