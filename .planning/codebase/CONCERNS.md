# Codebase Concerns

**Analysis Date:** 2026-03-10

---

## Tech Debt

**Monolithic vw_vehicle.py (4,227 lines):**
- Issue: Single class handles vehicle state, property accessors, engine-type detection, NA/EMEA branching, write commands, and dashboard data. No separation of concerns.
- Files: `volkswagencarnet/vw_vehicle.py`
- Impact: Hard to navigate, test, and extend. Every new feature adds to an already-huge file.
- Fix approach: Extract NA-specific methods into `vw_vehicle_na.py` mixin or subclass; split write commands into a separate `vw_vehicle_commands.py`.

**Monolithic vw_connection.py (3,298 lines):**
- Issue: Auth flow, token management, NA/EMEA routing, service discovery, HTTP requests, and per-endpoint fetch helpers all live in one class.
- Files: `volkswagencarnet/vw_connection.py`
- Impact: Any change risks breaking orthogonal behavior; unit tests must mock large swathes of the class.
- Fix approach: Extract `NAAuthManager`, `TokenManager`, and `HTTPClient` into separate modules.

**EMEA `energy_flow` parsing is pre-existing tech debt:**
- Issue: Three properties (`energy_flow`, `energy_flow_last_updated`, `is_energy_flow_supported`) use a different API data path structure than all other EMEA properties. Marked with `# noqa: T000` comment acknowledging the debt.
- Files: `volkswagencarnet/vw_vehicle.py` lines 1814–1848
- Impact: May silently return wrong values if charger API response changes.
- Fix approach: Migrate to `Paths`-based lookup like all other properties.

**`refresh_tokens()` (EMEA) has no explicit HTTP timeout:**
- Issue: `self._session.post()` in `refresh_tokens()` does not pass `timeout=ClientTimeout(...)`, relying on session default. This is the same class of bug that caused event-loop failures with aiohttp 3.13+ (documented in project MEMORY).
- Files: `volkswagencarnet/vw_connection.py` line 3159
- Impact: Token refresh could hang indefinitely in aiohttp 3.13+ under certain loop configurations.
- Fix approach: Add `timeout=ClientTimeout(total=TIMEOUT.seconds)` to the `self._session.post()` call at line 3159.

**`lxml` listed as install dependency but not used:**
- Issue: `setup.cfg` lists `lxml` in `install_requires`, but all BeautifulSoup calls use `html.parser` (Python stdlib). `lxml` is never imported.
- Files: `setup.cfg` line 19
- Impact: Unnecessary C-extension dependency installed on user machines.
- Fix approach: Remove `lxml` from `install_requires` in `setup.cfg`.

**Duplicate constant in `Paths`:**
- Issue: `READINESS_INSUFFICIENT_BATTERY_LEVEL_WARNING` and `READINESS_DAILY_POWER_BUDGET_WARNING` resolve to the same path string. `READINESS_DAILY_POWER_BUDGET_WARNING` is incorrectly mapped and will never return "daily power budget" data.
- Files: `volkswagencarnet/vw_const.py` lines 538–539
- Impact: `daily_power_budget_warning` property always reads `insufficientBatteryLevelWarning`, not the correct field.
- Fix approach: Correct `READINESS_DAILY_POWER_BUDGET_WARNING` to point to `connectionWarning.dailyPowerBudgetWarning` (verify actual API field name first).

**`wait_for_request()` and `wait_for_data_refresh()` use tail recursion:**
- Issue: Both methods are recursive with depth `retry_count=18`. At 10s sleep per retry, max wait is 180s. Recursion is avoidable and can exhaust stack on edge cases.
- Files: `volkswagencarnet/vw_vehicle.py` lines 403–445
- Impact: Unusual but theoretically possible `RecursionError` if `retry_count` is caller-set high.
- Fix approach: Refactor to iterative `for` loop with `asyncio.sleep()`.

**Bare `raise Exception(...)` in action methods:**
- Issue: `set_charger()`, `set_climatisation()`, `set_lock()`, etc. raise `Exception` directly instead of a typed exception (e.g., `APIError` or `ValueError`).
- Files: `volkswagencarnet/vw_vehicle.py` lines 455, 458, 480, 490, 502, 514, 557, 564, 577, 584, 595, 671, 673, 680, 692, 700, 703, 744, 756
- Impact: Callers cannot distinguish between an API failure and a programming error without inspecting the message string.
- Fix approach: Replace with `raise APIError(...)` or `raise ValueError(...)` from `vw_exceptions.py`.

**Broad `except Exception` blocks throughout Connection:**
- Issue: Over 15 `except Exception` handlers in `vw_connection.py` suppress unexpected errors with just a log line. Many are marked `# pylint: disable=broad-exception-caught`.
- Files: `volkswagencarnet/vw_connection.py` lines 264, 319, 538, 2267, 2344, 2464, 2502, 2573, 2590, 2615, 2641, 2658, 2688, 2710, 2732, 2754, 2769, 3185
- Impact: Silent swallowing of programming errors; makes debugging difficult.
- Fix approach: Progressively narrow exception types; at minimum, re-raise `SystemExit` and `KeyboardInterrupt`.

**`_clear_cookies()` accesses private aiohttp internals:**
- Issue: `self._session._cookie_jar._cookies.clear()` directly manipulates `_cookie_jar._cookies`, a private attribute of aiohttp's `CookieJar`.
- Files: `volkswagencarnet/vw_connection.py` line 166
- Impact: Will break silently on any aiohttp internal refactor; `# pylint: disable=protected-access` suppresses the warning.
- Fix approach: Use `self._session.cookie_jar.clear()` (public API available since aiohttp 3.x).

**Debug/diagnostic scripts committed to repository:**
- Issue: `tests/debug_na_login.py` and `test_us_endpoints.py` (in project root) are development artifacts, not part of the test suite.
- Files: `tests/debug_na_login.py`, `test_us_endpoints.py`
- Impact: Confusing project structure; `test_us_endpoints.py` is not picked up by pytest (`norecursedirs` in `pyproject.toml` excludes `tests/e2e` but not root-level files).
- Fix approach: Move to `examples/` or remove.

---

## Security Considerations

**XQMAUTH shared secret hardcoded in source:**
- Risk: The HMAC-SHA256 shared secret for X-QMAuth header is stored as a plain byte array in `vw_const.py` lines 16–51.
- Files: `volkswagencarnet/vw_const.py`
- Current mitigation: Secret is from VW's own app, so it was already public; library does not store user credentials this way.
- Recommendations: This is an inherent consequence of reverse-engineering VW's app protocol — no practical alternative. Document this explicitly.

**Credentials stored in memory as plain strings:**
- Risk: `self._session_auth_password` holds the plaintext VW account password for the lifetime of the `Connection` object.
- Files: `volkswagencarnet/vw_connection.py` line 128
- Current mitigation: Memory-only; no disk persistence.
- Recommendations: Consider clearing `_session_auth_password` after successful login (only needed for re-login after session expiry).

**JWT decoded without signature verification:**
- Risk: `jwt.decode(..., options={"verify_signature": False})` used in multiple places to extract claims (user_id, expiry) from tokens the library itself receives from VW servers.
- Files: `volkswagencarnet/vw_connection.py` lines 1375, 1582, 1735, 1737, 1923, 3112–3121
- Current mitigation: Tokens are received over HTTPS from VW's own servers; verification without signature is acceptable for extracting expiry from trusted tokens.
- Recommendations: Add a comment clarifying this is intentional; consider verifying IDK tokens against the JWKS endpoint (`b-h-s.spr.us00.p.con-veh.net/oidc/v1/jwks`) for the NA flow.

**Redirect URL domain allowlist validation is present but incomplete:**
- Risk: `VW_DOMAIN_ALLOWLIST` allows all of `.vw.com`, `.vw.us`, `.vwgroup.io`, etc. An attacker who controls a subdomain (e.g., via subdomain takeover) could pass the allowlist check.
- Files: `volkswagencarnet/vw_connection.py` lines 64–73
- Current mitigation: Allowlist is in place; OAuth redirect URI is hardcoded to `kombi:///login`.
- Recommendations: Use strict hostname matching for known endpoints rather than suffix matching where possible.

---

## Performance Bottlenecks

**NA vehicle data requires a new vehicle session token per update cycle:**
- Problem: `_create_na_vehicle_session()` is called on every `update()` for NA vehicles unless the RVS cache is fresh. Session creation is an extra HTTP round-trip.
- Files: `volkswagencarnet/vw_connection.py` — `_get_na_vehicle_data()`, `_create_na_vehicle_session()`
- Cause: Vehicle session tokens expire and must be re-issued; no session token TTL tracking.
- Improvement path: Cache vehicle session token with an expiry timestamp (vehicle session tokens likely have a TTL similar to access tokens).

**EMEA update fires 6 concurrent requests per vehicle per cycle:**
- Problem: `Vehicle.update()` uses `asyncio.gather()` to fire `getSelectiveStatus`, `getVehicleData`, `getParkingPosition`, `getTripLast`, `getTripRefuel`, `getTripLongterm` simultaneously.
- Files: `volkswagencarnet/vw_vehicle.py` lines 313–338
- Cause: Design decision for parallelism; could trigger API rate limiting.
- Improvement path: Group calls into fewer `selectivestatus` requests where possible.

---

## Fragile Areas

**NA authentication flow depends on HTML scraping of VW's login page:**
- Files: `volkswagencarnet/vw_connection.py` lines 542–614, `_extract_identitykit_form()` lines 551–614
- Why fragile: Uses regex on JavaScript `window._IDK` object and BeautifulSoup for form extraction. VW can break this by changing the login page template, renaming JS keys, or switching from server-rendered to full SPA.
- Safe modification: Any change to auth flow must be tested against live VW identity server. Add new parsing paths alongside old ones; don't remove working fallback patterns.
- Test coverage: Unit tests mock the HTML; no automated test detects real login page changes.

**NA PKCE `code_verifier` must survive token refresh:**
- Files: `volkswagencarnet/vw_connection.py` — `_refresh_idk_token()` line 1167
- Why fragile: `getattr(self, "_pkce_verifier", None) or ""` — if `_pkce_verifier` is `None` (e.g., after a re-login triggered by a different code path), the refresh request will fail silently with an incorrect `code_verifier=""`.
- Safe modification: Ensure `_pkce_verifier` is always set before any token refresh is attempted.
- Test coverage: `test_idk_refresh_updates_na_tokens_and_session_mirror` covers the happy path but not the `_pkce_verifier=None` case.

**`_na_tokens` dict uses mixed key types (VIN strings and string literals):**
- Files: `volkswagencarnet/vw_connection.py` — `_na_tokens`
- Why fragile: `_na_tokens["idk"]` holds IDK tokens, `_na_tokens["brand"]` holds brand tokens, and `_na_tokens[vin]` holds per-vehicle data. Using VINs as top-level keys alongside string keys makes the structure opaque and error-prone if a VIN happened to equal a reserved string.
- Safe modification: When adding new per-VIN data, always use `self._na_tokens.setdefault(vin, {})["new_key"]`. Do not add new top-level string keys without documenting the schema.
- Fix approach: Separate into `_na_token_store: dict` (for `idk`/`brand`/`mbb`) and `_na_vehicle_sessions: dict[str, dict]` (keyed by VIN).

**`doLogin()` `tries` parameter loop logic:**
- Files: `volkswagencarnet/vw_connection.py` lines 366–374
- Why fragile: Uses `for i in range(tries)` with `else:` clause. If `tries=1`, the loop body executes once; if login succeeds, it `break`s. If it fails and `tries=1`, the `else` fires ("Login failed after 1 tries"). But there is no sleep between the single attempt. Callers who pass `tries=0` get `_LOGGER.error` without attempting login.
- Safe modification: Validate `tries >= 1` at entry or document the behavior for `tries=0`.

---

## Test Coverage Gaps

**EMEA `refresh_tokens()` has no dedicated unit test:**
- What's not tested: The EMEA token refresh path (`refresh_tokens()`) is not explicitly tested in isolation. Only end-to-end-style flows cover it.
- Files: `volkswagencarnet/vw_connection.py` lines 3143–3189
- Risk: The missing timeout bug (no `ClientTimeout` on the `self._session.post()` call) and the EMEA token refresh error handling could regress undetected.
- Priority: High

**`_extract_identitykit_form()` JavaScript path has no negative-case tests:**
- What's not tested: The regex-based `templateModel` / `csrf_token` extraction in `_extract_identitykit_form()` is tested for the happy path but not for malformed JS, partial matches, or JSON parse failure.
- Files: `volkswagencarnet/vw_connection.py` lines 576–614
- Risk: A VW login page change could cause silent `AuthenticationError` with no clear error message.
- Priority: High

**NA write commands (lock, charger, climate, honk/flash) are not tested against real NA endpoint responses:**
- What's not tested: `tests/vw_vehicle_test.py` mocks the `_connection` object for NA write tests; there are no response-fixture tests covering NA-specific HTTP response bodies (202, 204, error JSON).
- Files: `tests/vw_vehicle_test.py` lines 1103–1284
- Risk: NA write commands may misparse actual server responses (e.g., treating a 202 body as success when the server changes the response schema).
- Priority: Medium

**`_in_progress()` guard uses `dict.pop()` with side effects inside `.get()` chain:**
- What's not tested: Line 99 — `self._requests.get(topic, {}).pop("id")` — mutates the default empty dict `{}` from `.get()`, which has no effect (the default is not the stored dict). This means the `"id"` key is never actually removed when `topic` doesn't exist in `_requests`, and the guard may not fire correctly for unrecognized topics.
- Files: `volkswagencarnet/vw_vehicle.py` line 99
- Risk: Commands for unregistered topics bypass the in-progress guard.
- Priority: Medium

**Dashboard `Climate` base class has `pass`-body methods that are never tested:**
- What's not tested: `Climate.hvac_mode`, `Climate.target_temperature`, `Climate.set_temperature`, `Climate.set_hvac_mode` all have `pass` bodies at lines 311–321. These are intended as abstract methods but don't raise `NotImplementedError`.
- Files: `volkswagencarnet/vw_dashboard.py` lines 305–321
- Risk: Subclass forgetting to override gets silent `None` returns instead of an error.
- Priority: Low

---

## Missing Critical Features

**NA vehicle data endpoints (capabilities, selectivestatus) return 404:**
- Problem: `/vehicle/v1/vehicles/{vin}/capabilities` and `/vehicle/v1/vehicles/{vin}/selectivestatus` return 404 for NA vehicles. The NA vehicle update path (`_update_na_vehicle`) uses RVS endpoints instead, but those only cover location, status, EV, climate, and trip — not EMEA-style service discovery.
- Files: `volkswagencarnet/vw_vehicle.py` lines 287–312, `volkswagencarnet/vw_connection.py` — `_get_na_vehicle_data()`
- Blocks: Full parity between EMEA and NA feature sets; NA vehicles cannot use EMEA-only services (departure timers, service inspection, etc.).

**NA vehicle session token TTL is not tracked:**
- Problem: No expiry tracking for vehicle session tokens (`_na_tokens[vin]["vehicle_session"]["token"]`). Tokens are reused until they expire server-side, causing a 401 on the next RVS call. The inline 401-retry in `_request()` partially mitigates this but is not the right long-term fix.
- Files: `volkswagencarnet/vw_connection.py` — `_create_na_vehicle_session()`, `_na_tokens` dict
- Blocks: Proactive token refresh before expiry; currently the library is reactive (retry on 401).

**Vehicle image URL retrieval (EMEA) is unimplemented:**
- Problem: `vw_vehicle.py` line 21 has a `# TODO` comment with a full example API response for vehicle image URLs from the EMEA media endpoint. No method exists to expose this data.
- Files: `volkswagencarnet/vw_vehicle.py` lines 21–25
- Blocks: Home Assistant integration cannot display vehicle images.

---

*Concerns audit: 2026-03-10*
