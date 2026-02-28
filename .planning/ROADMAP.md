# Roadmap: VW CarNet NA Authentication Fix

## Milestones

- ✅ **v1.0 NA Full API Values** — Phases 1-13 (shipped 2026-02-27)
- **v1.1 Make Production Ready** — Phases 15-20 (active)

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

## v1.1 Phases

- [x] **Phase 15: NA Error Handling** — Surface descriptive exceptions for NA API failures; auto-retry transient 5xx errors (completed 2026-02-28)
- [ ] **Phase 16: Type Hints** — Annotate public Connection methods, NA private methods, and Vehicle public properties
- [ ] **Phase 17: Logging** — Structured debug logs for NA auth + data flows; credential redaction; INFO-level token refresh events
- [ ] **Phase 18: Documentation** — README NA section + Connection/Vehicle/refresh docstrings
- [ ] **Phase 19: Security + Code Cleanup** — detect-secrets clean baseline, in-memory token confirmation, TODO resolution
- [ ] **Phase 20: Performance + Test Coverage** — RVS TTL cache, lazy NA init, NA error path unit tests, full regression pass

## Phase Details

### Phase 15: NA Error Handling
**Goal**: NA API failures surface descriptive, actionable exceptions instead of silently returning None
**Depends on**: Phase 13 (v1.0 complete)
**Requirements**: ERR-01, ERR-02, ERR-03
**Success Criteria** (what must be TRUE):
  1. Calling `doLogin()` with wrong NA credentials raises an exception whose message contains actionable guidance such as "verify country='US'" — not a silent False return
  2. A simulated garage endpoint 404 during NA login raises a descriptive exception naming the failed endpoint, not None
  3. A simulated RVS 5xx response triggers a retry (up to 2 attempts) before the method returns; the retry is observable in logs
  4. All existing 21 e2e tests and 156+ unit tests continue to pass after error handling changes
**Plans**: TBD

### Phase 16: Type Hints
**Goal**: All public Connection and Vehicle API surfaces have complete, correct type annotations
**Depends on**: Phase 15
**Requirements**: TYPE-01, TYPE-02, TYPE-03
**Success Criteria** (what must be TRUE):
  1. Running `mypy volkswagencarnet/vw_connection.py` reports no missing return type errors on `doLogin`, `get`, `post`, `put`, `update`, `validate_tokens`
  2. Running `mypy` on `vw_connection.py` reports no missing annotations on `_login_na`, `_create_na_vehicle_session`, `_get_na_vehicle_data`, `_refresh_idk_token`, `_classify_endpoint`
  3. Running `mypy volkswagencarnet/vw_vehicle.py` reports no missing return type errors on `position`, `doors_locked`, `vin`, `na_position`, `na_doors_locked`
  4. Pre-commit mypy hook passes cleanly after all type hint changes
**Plans**: TBD

### Phase 17: Logging
**Goal**: NA auth and data flows emit structured debug logs that diagnose failures without leaking credentials
**Depends on**: Phase 16
**Requirements**: LOG-01, LOG-02, LOG-03, LOG-04
**Success Criteria** (what must be TRUE):
  1. Running a NA login with `DEBUG` logging enabled produces log lines covering each step: code extraction, PKCE challenge, token exchange — enough context to identify which step failed
  2. Each NA vehicle data fetch (vehicle session creation, RVS location, RVS status) emits a DEBUG line that includes the VIN
  3. Grepping all log output at any level for a full token value (>16 chars of a real JWT) finds zero matches — tokens are truncated to 8 chars followed by "..."
  4. A token refresh event (IDK, Brand, or MBB) produces an INFO-level log line that names which token type was refreshed
**Plans**: TBD

### Phase 18: Documentation
**Goal**: README and public API docstrings fully document NA usage and non-obvious implementation decisions
**Depends on**: Phase 17
**Requirements**: DOC-01, DOC-02, DOC-03, DOC-04
**Success Criteria** (what must be TRUE):
  1. README contains a "North America" section with: `country='US'` usage example, credential requirements, `VW_TEST_SPIN` env var explanation, and a minimal working Python script
  2. `Connection.__init__()` and `doLogin()` docstrings describe the `country` parameter, NA vs EMEA routing behavior, and the IDK-only auth level for NA Car-Net
  3. `vehicle.position` and `vehicle.doors_locked` docstrings state that NA data comes from RVS endpoints, EMEA from selectivestatus
  4. `_refresh_idk_token()` docstring documents that the refresh body requires `code_verifier` (non-standard OAuth extension) and why
**Plans**: TBD

### Phase 19: Security + Code Cleanup
**Goal**: Codebase passes secrets scan clean, token storage is confirmed in-memory only, and all NA TODO comments are resolved
**Depends on**: Phase 17
**Requirements**: SEC-01, SEC-02, SEC-03, CLEAN-01, CLEAN-02, CLEAN-03
**Success Criteria** (what must be TRUE):
  1. `detect-secrets scan` against the updated baseline reports zero new findings in any file changed during v1.1
  2. A code review of all disk-write operations confirms no file paths handle token or credential values — tokens live in memory only
  3. All `# TODO` comments in NA code paths of `vw_connection.py` are either replaced with resolved code or a documented rationale comment (no bare TODOs remain)
  4. `vw_vehicle.py` energy_flow TODO lines (~1651, ~1664, ~1676) carry a `# noqa: T000` annotation with a brief EMEA debt explanation
  5. `x-mobile-session-id` is either confirmed from live traffic (comment removed) or annotated "TBD: field name unconfirmed from live traffic" with a placeholder unit test
**Plans**: TBD

### Phase 20: Performance + Test Coverage
**Goal**: RVS data is cached to reduce API calls, NA init is lazy for EMEA users, and error paths are covered by unit tests
**Depends on**: Phase 19
**Requirements**: PERF-01, PERF-02, TEST-01, TEST-02, TEST-03
**Success Criteria** (what must be TRUE):
  1. Two consecutive `vehicle.update()` calls within 30 seconds on a NA vehicle result in only one RVS API roundtrip — the second call returns cached data (verifiable via mock call count)
  2. Constructing `Connection(session, username, password)` (no `country` parameter) imports no NA-specific code at init time — EMEA startup time is unaffected
  3. Unit tests exist for: token exchange failure returns graceful None, garage 404 returns graceful None, RVS 5xx returns graceful None — all without uncaught exceptions
  4. A unit test confirms that IDK token refresh failure triggers `doLogin()` re-authentication rather than propagating an unhandled exception
  5. Full test suite passes: all existing 21 e2e tests + 156+ unit tests + new v1.1 unit tests — zero regressions
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. NA Foundation | v1.0 | 1/1 | Complete | 2026-02-18 |
| 2. NA OAuth Login Flow | v1.0 | 2/2 | Complete | 2026-02-18 |
| 3. Three-Token Architecture | v1.0 | 3/3 | Complete | 2026-02-18 |
| 4. Token Lifecycle Management | v1.0 | 2/2 | Complete | 2026-02-19 |
| 5. Reliability & Discovery | v1.0 | 3/3 | Complete | 2026-02-19 |
| 6. Backward Compatibility | v1.0 | 2/2 | Complete | 2026-02-20 |
| 7. End-to-End Validation | v1.0 | 2/2 | Complete | 2026-02-20 |
| 8. Fix Stale Unit Tests | v1.0 | 1/1 | Complete | 2026-02-26 |
| 9. Requirements Wording & Docs Cleanup | v1.0 | 1/1 | Complete | 2026-02-26 |
| 10. NA Vehicle Data Endpoint Research | v1.0 | 1/1 | Complete | 2026-02-26 |
| 11. NA Vehicle Data Implementation | v1.0 | 2/2 | Complete | 2026-02-26 |
| 12. Full API Values E2E Validation | v1.0 | 1/1 | Complete | 2026-02-26 |
| 12.1. Fix NA Vehicle Session TSP (INSERTED) | v1.0 | 1/1 | Complete | 2026-02-27 |
| 13. Display of Real Values + Manual UAT | v1.0 | 1/1 | Complete | 2026-02-27 |
| 15. NA Error Handling | 2/2 | Complete    | 2026-02-28 | - |
| 16. Type Hints | 1/3 | In Progress|  | - |
| 17. Logging | v1.1 | 0/? | Not started | - |
| 18. Documentation | v1.1 | 0/? | Not started | - |
| 19. Security + Code Cleanup | v1.1 | 0/? | Not started | - |
| 20. Performance + Test Coverage | v1.1 | 0/? | Not started | - |
