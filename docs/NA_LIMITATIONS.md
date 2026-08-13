# North America (Car-Net) Limitations

This document lists known limitations of the North America VW Car-Net integration compared to EMEA (WeConnect).

## Authentication

- NA Car-Net uses IDK-only authentication. Brand and MBB token endpoints return 404.
- Token refresh requires the original PKCE `code_verifier` from the initial login (non-standard OAuth extension specific to VW's NA AZS server).
- If the refresh token expires, a full re-login is triggered automatically.

## Vehicle Data

- The EMEA `capabilities` and `selectivestatus` endpoints return 404 for NA vehicles.
- NA vehicle data (GPS location, lock status) is fetched via RVS (Remote Vehicle Status) endpoints instead.
- Available NA data points: GPS coordinates (lat/lng) and door lock status via RVS, plus EV charging, climate, and trip data fetched separately (see below).
- EV charge/climate/trip data is fetched via `_fetch_na_vehicle_data()`, which calls the `/ev/v1/vehicle/{vehicle_id}/charge/summary`, `/ev/v1/vehicle/{vehicle_id}/pretripclimate/settings`, and `/remotetripstats/v1/vehicle/{vehicle_id}` endpoints.

## Vehicle Control

- Lock/unlock, honk & flash, charging, and climatisation control are implemented for NA via `lock_na()`, `honk_and_flash_na()`, `start_charging_na()`, `stop_charging_na()`, `start_climatisation_na()`, and `stop_climatisation_na()`.
- Some operations require a security PIN configured through the VW Car-Net portal.

## Endpoint Discovery

- NA base API is hardcoded to `b-h-s.spr.us00.p.con-veh.net` (confirmed working as of early 2026).
- Endpoint discovery candidates are intentionally empty for NA to prevent incorrect auto-discovery.
- The NA identity provider (`identity.na.vwgroup.io`) is separate from the base API.

## Contributing

If you have access to a North America VW Car-Net account and can help extend NA support, contributions are welcome. See the main README for development setup.
