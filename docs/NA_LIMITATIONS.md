# North America (Car-Net) Limitations

This document lists known limitations of the North America VW Car-Net integration compared to EMEA (WeConnect).

## Authentication

- NA Car-Net uses IDK-only authentication. Brand and MBB token endpoints return 404.
- Token refresh requires the original PKCE `code_verifier` from the initial login (non-standard OAuth extension specific to VW's NA AZS server).
- If the refresh token expires, a full re-login is triggered automatically.

## Vehicle Data

- The EMEA `capabilities` and `selectivestatus` endpoints return 404 for NA vehicles.
- NA vehicle data (GPS location, lock status) is fetched via RVS (Remote Vehicle Status) endpoints instead.
- Available NA data points: GPS coordinates (lat/lng) and door lock status.
- Additional EMEA properties (battery level, charging state, climate control, trip data) are not yet available for NA.

## Vehicle Control

- Lock/unlock, climatisation, and other vehicle control commands are not yet implemented for NA.
- Some operations require a security PIN configured through the VW Car-Net portal.

## Endpoint Discovery

- NA base API is hardcoded to `b-h-s.spr.us00.p.con-veh.net` (confirmed working as of early 2026).
- Endpoint discovery candidates are intentionally empty for NA to prevent incorrect auto-discovery.
- The NA identity provider (`identity.na.vwgroup.io`) is separate from the base API.

## Contributing

If you have access to a North America VW Car-Net account and can help extend NA support, contributions are welcome. See the main README for development setup.
