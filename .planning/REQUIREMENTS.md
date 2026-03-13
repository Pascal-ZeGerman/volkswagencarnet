# Requirements: VW CarNet Variable Parity & Enrichment

**Defined:** 2026-03-12
**Milestone:** v1.4 Variable Parity & Enrichment
**Core Value:** NA users can authenticate with VW CarNet and retrieve full vehicle data for homelab integration without breaking EMEA functionality.

## v1.4 Requirements

### EV / Range Parity

- [ ] **EVRNG-01**: `electric_range` property returns NA EV electric range from `na_ev.electricRange` when EMEA path is unavailable
- [ ] **EVRNG-02**: `electric_range` returns None gracefully for non-EV NA vehicles

### Door / Access Parity

- [x] **DOOR-01**: `door_closed_left_front` property returns status from `na_status.exteriorStatus.doorStatus.frontLeft`
- [x] **DOOR-02**: `door_closed_right_front` property returns status from `na_status.exteriorStatus.doorStatus.frontRight`
- [x] **DOOR-03**: `door_closed_left_back` property returns status from `na_status.exteriorStatus.doorStatus.rearLeft`
- [x] **DOOR-04**: `door_closed_right_back` property returns status from `na_status.exteriorStatus.doorStatus.rearRight`
- [x] **DOOR-05**: `trunk_closed` property returns status from `na_status.exteriorStatus.doorStatus.trunk`
- [x] **DOOR-06**: `hood_closed` property returns status from `na_status.exteriorStatus.doorStatus.hood`
- [x] **DOOR-07**: Individual door lock properties populated from `na_status.exteriorStatus.doorLockStatus` per-door fields

### Trip Parity

- [ ] **TRIP-01**: `last_trip_average_speed` property returns value from `na_trip.averageSpeed`

### Timestamps / Metadata

- [ ] **META-01**: Odometer update timestamp surfaced from `na_status.currentMileageTimestamp`
- [ ] **META-02**: Vehicle parked status derived from `na_location.parked` (maps to `vehicle_moving` inverted)
- [ ] **META-03**: Climatisation duration surfaced from `na_climate.climatisationDuration`

### NA-Specific Properties

- [ ] **NASPEC-01**: Aggregate security status exposed from `na_status.exteriorStatus.secure`
- [ ] **NASPEC-02**: Cruise range units indicator from `na_status.powerStatus.cruiseRangeUnits`

## v2 Requirements

### NA Alerts (Deferred)

- **NALERT-01**: Library can fetch speed alert thresholds (`GET /alert/v1/vehicle/{id}/speed`)
- **NALERT-02**: Library can fetch geo-fence/boundary alerts (`GET /alert/v1/vehicle/{id}/boundary`)
- **NALERT-03**: Library can fetch curfew time alerts (`GET /alert/v1/vehicle/{id}/curfew`)
- **NALERT-04**: Library can fetch valet mode alerts (`GET /alert/v1/vehicle/{id}/valet`)

### Dashboard NA Support (Deferred)

- **DASH-01**: Dashboard instruments updated to surface new NA properties as HA entities

## Out of Scope

| Feature | Reason |
|---------|--------|
| EMEA-only properties with no NA data | NA API simply doesn't expose these endpoints (74 properties) |
| Refuel/longterm trip data | NA only provides SHORT_TERM trip stats |
| Charging settings (target SOC, AC limits) | NA has no charging settings read endpoint |
| Departure timers | NA has no departure profiles endpoint |
| Service/inspection data | NA has no health inspection endpoint |
| Readiness/connection state | NA has no readiness endpoint |
| Dashboard instrument updates | Deferred to separate milestone or v2 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| EVRNG-01 | Phase 35 | Pending |
| EVRNG-02 | Phase 35 | Pending |
| DOOR-01 | Phase 34 | Complete |
| DOOR-02 | Phase 34 | Complete |
| DOOR-03 | Phase 34 | Complete |
| DOOR-04 | Phase 34 | Complete |
| DOOR-05 | Phase 34 | Complete |
| DOOR-06 | Phase 34 | Complete |
| DOOR-07 | Phase 34 | Complete |
| TRIP-01 | Phase 35 | Pending |
| META-01 | Phase 35 | Pending |
| META-02 | Phase 35 | Pending |
| META-03 | Phase 35 | Pending |
| NASPEC-01 | Phase 36 | Pending |
| NASPEC-02 | Phase 36 | Pending |

**Coverage:**
- v1.4 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0

---
*Requirements defined: 2026-03-12*
*Last updated: 2026-03-12 -- roadmap created, all requirements mapped*
