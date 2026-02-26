# VW CarNet NA Authentication Fix

## What This Is

Python library (volkswagencarnet) for VW CarNet API integration. Currently supports EMEA (Europe) region authentication and vehicle data retrieval. This project resurrects North America region authentication to enable homelab monitoring of VW vehicles for NA-based users.

## Core Value

NA users can authenticate with VW CarNet and retrieve vehicle data (battery level, location, status) for homelab integration without breaking existing EMEA functionality.

## Requirements

### Validated

<!-- Existing functionality that already works and must be preserved -->

- ✓ EMEA region authentication — OAuth2 flow working for European users
- ✓ Vehicle data retrieval — battery, location, status, charging, climate data
- ✓ Async API design — aiohttp-based async operations
- ✓ Multi-vehicle support — handles multiple vehicles per account
- ✓ Token management — automatic token refresh and expiry handling

### Active

<!-- Current scope - v1.5 NA vehicle telemetry data -->

- [ ] NA vehicle data endpoints discovered via APK analysis
- [ ] Library fetches real vehicle state (location, lock status) for NA vehicles
- [ ] Vehicle properties return actual values instead of 404/None for NA

### Out of Scope

<!-- Explicit boundaries - read-only monitoring only -->

- Vehicle control features (lock/unlock, climate control, charging control) — read-only sufficient for homelab monitoring
- Mobile app development — library for programmatic access only
- Real-time push notifications — polling-based updates sufficient
- GraphQL API support — REST API sufficient for current needs
- EMEA feature enhancements — focus solely on fixing NA authentication

## Context

**User Situation:**
- VW vehicle owner in North America
- Active CarNet account with credentials ready for testing
- Homelab setup (likely Home Assistant) ready for integration
- Needs read-only vehicle monitoring (battery, location, status)

**Technical Background:**
- Library already has partial NA implementation that fails authentication
- `.VW_NA_Auth_Analysis/` contains Audi Connect implementation analysis (sister brand, shared VW Group infrastructure)
- Analysis reveals required 3-token OAuth flow not fully implemented
- Current implementation uses simplified OAuth vs. actual VW Group multi-layer flow

**Known Issues:**
- NA authentication returns errors (incomplete OAuth implementation)
- Missing X-QMAuth header for token exchange
- Missing MBB OAuth client registration step
- Token hierarchy not properly implemented (single token vs. three-token architecture)

## Constraints

- **Backward Compatibility**: Must not break existing EMEA users — this is a brownfield enhancement
- **Python Version**: Python 3.11+ (externally-managed environment, uses venv)
- **Library Structure**: Must follow existing async patterns and code organization
- **Testing Requirements**: Must test with real NA credentials and vehicle (user has both available)
- **Technical Stack**: Must use existing dependencies (aiohttp, pytest) unless absolutely necessary

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Focus on NA auth only | User only needs data access, existing data retrieval works | — Pending |
| Use Audi analysis as blueprint | Sister brand shares VW Group IT infrastructure | — Pending |
| Maintain backward compatibility | Can't break existing EMEA users | — Pending |

## Current Milestone: v1.5 Full API Values

**Goal:** Discover NA-specific vehicle data endpoints and make real vehicle telemetry (location, lock status) available for NA users

**Target features:**
- APK analysis to identify NA vehicle data API endpoints
- Implement NA data retrieval in Vehicle class (replace 404s with real data)
- Location/GPS and door/lock status as priority properties
- Battery, charging, climate as bonus if the endpoint structure exposes them
- E2E validation confirming real values from live NA vehicle

---
*Last updated: 2026-02-25 after v1.5 milestone start*
