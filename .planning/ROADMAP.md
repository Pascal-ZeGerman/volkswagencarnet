# Roadmap: VW CarNet NA Authentication Fix

## Milestones

- ✅ **v1.0 NA Full API Values** — Phases 1-13 (shipped 2026-02-27)
- ✅ **v1.1 Make Production Ready** — Phases 15-20 (shipped 2026-03-01)
- ✅ **v1.2 PR Review Fixes** — Phases 21-24 (shipped 2026-03-07)
- ✅ **v1.3 NA Endpoint Coverage** — Phases 25-33 (shipped 2026-03-10)
- 🚧 **v1.4 Variable Parity & Enrichment** — Phases 34-36 (in progress)
- 📋 **v1.5 Error Resilience & Code Hardening** — Phases 37-40 (planned)

## Phases

<details>
<summary>✅ v1.0 NA Full API Values (Phases 1-13) — SHIPPED 2026-02-27</summary>

- [x] Phase 1: NA Foundation (1/1 plans) — completed 2026-02-18
- [x] Phase 2: NA OAuth Login Flow (2/2 plans) — completed 2026-02-18
- [x] Phase 3: Three-Token Architecture (3/3 plans) — completed 2026-02-18
- [x] Phase 4: Token Lifecycle Management (2/2 plans) — completed 2026-02-19
- [x] Phase 5: Reliability & Discovery (3/3 plans) — completed 2026-02-19
- [x] Phase 6: Backward Compatibility (2/2 plans) — completed 2026-02-20
- [x] Phase 7: End-to-End Validation (2/2 plans) — completed 2026-02-20
- [x] Phase 8: Fix Stale Unit Tests (1/1 plans) — completed 2026-02-26
- [x] Phase 9: Requirements Wording & Docs Cleanup (1/1 plans) — completed 2026-02-26
- [x] Phase 10: NA Vehicle Data Endpoint Research (1/1 plans) — completed 2026-02-26
- [x] Phase 11: NA Vehicle Data Implementation (2/2 plans) — completed 2026-02-26
- [x] Phase 12: Full API Values E2E Validation (1/1 plans) — completed 2026-02-26
- [x] Phase 12.1: Fix NA Vehicle Session TSP Values (INSERTED) (1/1 plans) — completed 2026-02-27
- [x] Phase 13: Display of Real Values + Manual UAT (1/1 plans) — completed 2026-02-27

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 Make Production Ready (Phases 15-20) — SHIPPED 2026-03-01</summary>

- [x] Phase 15: NA Error Handling (2/2 plans) — completed 2026-02-28
- [x] Phase 16: Type Hints (3/3 plans) — completed 2026-02-28
- [x] Phase 17: Logging (2/2 plans) — completed 2026-03-01
- [x] Phase 18: Documentation (2/2 plans) — completed 2026-03-01
- [x] Phase 19: Security + Code Cleanup (2/2 plans) — completed 2026-03-01
- [x] Phase 20: Performance + Test Coverage (2/2 plans) — completed 2026-03-01

Full details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

<details>
<summary>✅ v1.2 PR Review Fixes (Phases 21-24) — SHIPPED 2026-03-07</summary>

- [x] Phase 21: Fix Critical/High PR Review Issues (2/2 plans) — completed 2026-03-02
- [x] Phase 22: Fix Medium & Nitpick PR Issues (2/2 plans) — completed 2026-03-02
- [x] Phase 23: Create Holistic Test Suite (6/6 plans) — completed 2026-03-03
- [x] Phase 24: Fix PR Review Issues: error handling, comment accuracy, test coverage (2/2 plans) — completed 2026-03-07

Full details: `.planning/milestones/v1.2-ROADMAP.md`

</details>

<details>
<summary>✅ v1.3 NA Endpoint Coverage (Phases 25-33) — SHIPPED 2026-03-10</summary>

- [x] Phase 25: Surface Existing RVS Data as Vehicle Properties (1/1 plans) — completed 2026-03-08
- [x] Phase 26: Implement Optional RVS Vehicle Refresh Trigger (1/1 plans) — completed 2026-03-08
- [x] Phase 27: Implement EV Charge Summary Endpoint (1/1 plans) — completed 2026-03-08
- [x] Phase 28: Implement Pre-Trip Climate Settings (1/1 plans) — completed 2026-03-08
- [x] Phase 29: Implement Trip Statistics Endpoint (1/1 plans) — completed 2026-03-08
- [x] Phase 30: Implement Remote Lock/Unlock (1/1 plans) — completed 2026-03-08
- [x] Phase 31: Implement Honk & Flash (1/1 plans) — completed 2026-03-08
- [x] Phase 32: Implement EV Charging Start/Stop (1/1 plans) — completed 2026-03-08
- [x] Phase 33: Implement Climate Start/Stop (1/1 plans) — completed 2026-03-08

Full details: `.planning/milestones/v1.3-ROADMAP.md`

</details>

### v1.4 Variable Parity & Enrichment (In Progress)

**Milestone Goal:** Surface all remaining NA API response fields as vehicle properties, achieving parity with EMEA where data exists and exposing NA-specific fields.

- [x] **Phase 34: Door & Access Parity** - Wire per-door open/closed and per-door lock status from NA exteriorStatus (completed 2026-03-13)
- [ ] **Phase 35: EV Range, Trip & Metadata Parity** - Map electric range, trip speed, timestamps, parked status, and climate duration from existing NA data
- [ ] **Phase 36: NA-Specific Properties** - Expose aggregate security status and range units indicator unique to NA

### v1.5 Error Resilience & Code Hardening (Planned)

**Milestone Goal:** Fix critical control flow bugs, clean up exception patterns, add data integrity guards, and pass a full code review gate with zero critical findings.

- [ ] **Phase 37: Critical Fixes** - Fix control flow bugs where exceptions always raise, add missing timeouts and JWT guards
- [ ] **Phase 38: Exception Hygiene & Data Integrity** - Replace bare Exception raises with domain types, fix return type inconsistencies, add None guards
- [ ] **Phase 39: Concurrency & Code Quality** - Add update lock, remove dead code, convert recursion to iteration, fix type annotations
- [ ] **Phase 40: Code Review Gate** - Run /review-pr on full codebase, fix all critical findings iteratively until zero remain

## Phase Details

### Phase 34: Door & Access Parity
**Goal**: NA users can see individual door, trunk, and hood open/closed status and per-door lock status
**Depends on**: Phase 33 (v1.3 complete)
**Requirements**: DOOR-01, DOOR-02, DOOR-03, DOOR-04, DOOR-05, DOOR-06, DOOR-07
**Success Criteria** (what must be TRUE):
  1. NA user can check open/closed status of each of the four doors individually (left front, right front, left back, right back)
  2. NA user can check whether trunk and hood are closed
  3. NA user can check per-door lock status (locked/unlocked for each door independently)
  4. All door/lock properties return None gracefully when NA status data is unavailable
  5. Existing EMEA door property behavior is unchanged
**Plans:** 1/1 plans complete
Plans:
- [ ] 34-01-PLAN.md — Extend door helpers with NA branches and add per-door lock properties

### Phase 35: EV Range, Trip & Metadata Parity
**Goal**: NA users see electric range, trip average speed, odometer timestamp, parked status, and climate duration from already-fetched NA data
**Depends on**: Phase 34
**Requirements**: EVRNG-01, EVRNG-02, TRIP-01, META-01, META-02, META-03
**Success Criteria** (what must be TRUE):
  1. NA EV user sees electric_range populated from na_ev.electricRange; non-EV NA user sees None
  2. NA user sees last_trip_average_speed populated from na_trip.averageSpeed
  3. NA user sees odometer update timestamp from na_status.currentMileageTimestamp
  4. NA user sees vehicle_moving correctly derived (inverted) from na_location.parked
  5. NA user sees climatisation duration from na_climate.climatisationDuration
**Plans**: TBD

### Phase 36: NA-Specific Properties
**Goal**: NA users can access properties unique to the NA API that have no EMEA equivalent
**Depends on**: Phase 35
**Requirements**: NASPEC-01, NASPEC-02
**Success Criteria** (what must be TRUE):
  1. NA user can read aggregate security status (secure/locked/unlocked) from exteriorStatus.secure
  2. NA user can read cruise range units indicator (MI/KM) from powerStatus.cruiseRangeUnits
  3. Both properties return None for EMEA vehicles (no NA data source)
**Plans**: TBD

### Phase 37: Critical Fixes
**Goal**: Vehicle action methods behave correctly on success and failure, EMEA token validation cannot crash on malformed tokens, and all session-level HTTP calls have explicit timeouts
**Depends on**: Phase 36 (v1.4 complete)
**Requirements**: CFIX-01, CFIX-02, CFIX-03, CFIX-04
**Success Criteria** (what must be TRUE):
  1. `set_refresh()`, `set_lock()`, and `set_honk_and_flash()` return successfully on happy path without raising exceptions
  2. `_handle_response()` raises `APIError` (not bare `Exception`) when response is falsy
  3. EMEA `validate_tokens()` returns False gracefully when JWT tokens are malformed or have missing exp claims, instead of crashing
  4. EMEA `refresh_tokens()` and `get_openid_config()` complete or timeout within TIMEOUT.seconds, never hang indefinitely
**Plans**: TBD

### Phase 38: Exception Hygiene & Data Integrity
**Goal**: All exceptions raised by the library are domain-specific types, traceback chains are preserved, and data-fetch methods handle None/missing data without crashing
**Depends on**: Phase 37
**Requirements**: EXCP-01, EXCP-02, EXCP-03, DATA-01, DATA-02, DATA-03
**Success Criteria** (what must be TRUE):
  1. No bare `Exception` is raised anywhere in vehicle action methods -- all use `APIError`, `UnsupportedOperationError`, or other domain types
  2. `_request()` final catch preserves the original traceback chain (no `from None`)
  3. Overly broad `except Exception` catches in `update()`, `_discover_market_config()`, and data-fetch methods are narrowed to specific expected exception types
  4. `getVehicleData()` does not crash when API response has no "data" key
  5. Data-fetch methods return `None` (not `False`) on error, and `expired()` compares datetimes consistently (both aware or both naive)
**Plans**: TBD

### Phase 39: Concurrency & Code Quality
**Goal**: Concurrent `update()` calls are safe, recursive wait methods are iterative, and type annotations are correct throughout
**Depends on**: Phase 38
**Requirements**: CONC-01, CONC-02, QUAL-01, QUAL-02, QUAL-03, QUAL-04
**Success Criteria** (what must be TRUE):
  1. Two concurrent `update()` calls do not produce duplicate API requests -- the second waits for the first to complete
  2. Dead `response == 429` check is removed from `_handle_action_result()`
  3. `wait_for_request()` and `wait_for_data_refresh()` use iterative loops instead of recursion
  4. `assert self._connection is not None` replaced with explicit `if ... raise RuntimeError` checks that survive `python -O`
  5. `model_year` type annotation is `int | None` and dead try/except in `_is_allowed_vw_domain()` is removed
**Plans**: TBD

### Phase 40: Code Review Gate
**Goal**: Full codebase passes a comprehensive code review with zero critical findings remaining
**Depends on**: Phase 39
**Requirements**: REVIEW-01
**Success Criteria** (what must be TRUE):
  1. `/review-pr` run against the full codebase produces zero critical-severity recommendations
  2. All critical findings from the review are fixed and verified in subsequent review iterations
  3. All existing tests continue to pass after review-driven fixes (no regressions)
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-13 | v1.0 | 23/23 | Complete | 2026-02-27 |
| 15. NA Error Handling | v1.1 | 2/2 | Complete | 2026-02-28 |
| 16. Type Hints | v1.1 | 3/3 | Complete | 2026-02-28 |
| 17. Logging | v1.1 | 2/2 | Complete | 2026-03-01 |
| 18. Documentation | v1.1 | 2/2 | Complete | 2026-03-01 |
| 19. Security + Code Cleanup | v1.1 | 2/2 | Complete | 2026-03-01 |
| 20. Performance + Test Coverage | v1.1 | 2/2 | Complete | 2026-03-01 |
| 21. Fix Critical/High PR Review Issues | v1.2 | 2/2 | Complete | 2026-03-02 |
| 22. Fix Medium & Nitpick PR Issues | v1.2 | 2/2 | Complete | 2026-03-02 |
| 23. Holistic Test Suite | v1.2 | 6/6 | Complete | 2026-03-03 |
| 24. Fix PR Review Issues (error handling) | v1.2 | 2/2 | Complete | 2026-03-07 |
| 25. Surface RVS Data as Vehicle Properties | v1.3 | 1/1 | Complete | 2026-03-08 |
| 26. Optional RVS Vehicle Refresh Trigger | v1.3 | 1/1 | Complete | 2026-03-08 |
| 27. EV Charge Summary Endpoint | v1.3 | 1/1 | Complete | 2026-03-08 |
| 28. Pre-Trip Climate Settings | v1.3 | 1/1 | Complete | 2026-03-08 |
| 29. Trip Statistics Endpoint | v1.3 | 1/1 | Complete | 2026-03-08 |
| 30. Remote Lock/Unlock | v1.3 | 1/1 | Complete | 2026-03-08 |
| 31. Honk & Flash | v1.3 | 1/1 | Complete | 2026-03-08 |
| 32. EV Charging Start/Stop | v1.3 | 1/1 | Complete | 2026-03-08 |
| 33. Climate Start/Stop | v1.3 | 1/1 | Complete | 2026-03-08 |
| 34. Door & Access Parity | 1/1 | Complete   | 2026-03-13 | - |
| 35. EV Range, Trip & Metadata Parity | v1.4 | 0/? | Not started | - |
| 36. NA-Specific Properties | v1.4 | 0/? | Not started | - |
| 37. Critical Fixes | v1.5 | 0/? | Not started | - |
| 38. Exception Hygiene & Data Integrity | v1.5 | 0/? | Not started | - |
| 39. Concurrency & Code Quality | v1.5 | 0/? | Not started | - |
| 40. Code Review Gate | v1.5 | 0/? | Not started | - |
