# Requirements: VW CarNet NA Full API Values

**Defined:** 2026-02-25
**Core Value:** NA users can retrieve real vehicle telemetry (location, lock status) from VW CarNet for homelab integration without breaking existing EMEA functionality.

## v1.5 Requirements

Requirements for NA vehicle data retrieval. Each maps to roadmap phases.
Phases 8-9 in ROADMAP.md close v1.0 tech debt; phases 10+ deliver v1.5 features.

### Endpoint Discovery

- [ ] **DISC-01**: Library automatically uses correct NA-specific vehicle data endpoints (not EMEA paths that return 404 for NA)
- [ ] **DISC-02**: NA endpoint authentication requirements confirmed — which token type and headers are needed for vehicle data calls

### Vehicle Data Integration

- [ ] **DATA-01**: Library fetches vehicle state data from NA endpoints with a non-404 response
- [ ] **DATA-02**: NA API response correctly parsed and stored in `Vehicle._states`
- [ ] **DATA-03**: `Vehicle.discover()` completes for NA vehicles with populated service data (not empty capabilities)

### Vehicle Properties

- [ ] **PROP-01**: `vehicle.position` (or NA equivalent) returns real GPS coordinates (latitude/longitude) for NA vehicles
- [ ] **PROP-02**: `vehicle.doors_locked` (or NA equivalent) returns real lock/unlock state for NA vehicles

### Testing & Validation

- [ ] **TEST-07**: E2E test confirms position returns non-None GPS coordinates for real NA vehicle
- [ ] **TEST-08**: E2E test confirms lock status returns real boolean for real NA vehicle
- [ ] **TEST-09**: All v1.0 NA e2e tests continue passing (login, vehicle discovery, IDK token refresh)
- [ ] **TEST-10**: EMEA regression suite passes with 0 failures after NA data changes

## v2 Requirements

Deferred — promote to v1.5 after APK research if the NA API exposes these.

### Additional Vehicle Properties

- **PROP-03**: `vehicle.battery_level` returns real state of charge (%) for NA vehicles
- **PROP-04**: `vehicle.charging_state` returns real charging status for NA vehicles
- **PROP-05**: Climate/HVAC properties (`climatisation_target_temperature`, etc.) work for NA vehicles

## Out of Scope

Explicitly excluded to maintain focus on core goal.

| Feature | Reason |
|---------|--------|
| Vehicle control (lock, climate start/stop) | Read-only monitoring sufficient for homelab use case |
| GraphQL API | REST sufficient for vehicle data |
| MBB/Brand token data endpoints | IDK token sufficient for NA data calls |
| EMEA feature enhancements | Focus solely on NA data gap |
| Multi-region simultaneous session | Single region per Connection instance |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DISC-01 | Phase 10 | Pending |
| DISC-02 | Phase 10 | Pending |
| DATA-01 | Phase 11 | Pending |
| DATA-02 | Phase 11 | Pending |
| DATA-03 | Phase 11 | Pending |
| PROP-01 | Phase 11 | Pending |
| PROP-02 | Phase 11 | Pending |
| TEST-07 | Phase 12 | Pending |
| TEST-08 | Phase 12 | Pending |
| TEST-09 | Phase 12 | Pending |
| TEST-10 | Phase 12 | Pending |

**Coverage:**
- v1.5 requirements: 11 total
- Mapped to phases: 11 (100%)
- Unmapped: 0

---
*Requirements defined: 2026-02-25*
*Last updated: 2026-02-25 after v1.5 roadmap creation (Phases 10-12)*
