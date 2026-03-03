# Roadmap: VW CarNet NA Authentication Fix

## Milestones

- ✅ **v1.0 NA Full API Values** — Phases 1-13 (shipped 2026-02-27)
- ✅ **v1.1 Make Production Ready** — Phases 15-20 (shipped 2026-03-01)
- **v1.2 PR Review Fixes** — Phases 21-23 (active)

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

</details>

## v1.2 Phases

- [x] **Phase 21: Fix Critical/High PR Review Issues** — Credential scrubbing, security logging, dead code removal (completed 2026-03-02)
- [x] **Phase 22: Fix Medium & Nitpick Issues from PR Review** — Address remaining medium-severity and nitpick PR feedback (completed 2026-03-02)
- [ ] **Phase 23: Create Holistic Test Suite with Comprehensive Code Coverage** — Full test coverage across NA and EMEA paths

### Phase 23: Create Holistic Test Suite with Comprehensive Code Coverage
**Goal:** Achieve comprehensive unit test coverage across all NA and EMEA code paths, ensuring the library is well-tested before merging to main.
**Scope:** Unit tests for connection logic (both regions), vehicle data parsing, token management, error handling, dashboard instruments, and utility functions.
**Plans:** 2/4 plans executed

Plans:
- [ ] 23-01-PLAN.md — Connection tests: aioresponses setup, EMEA OAuth flow, action methods, data fetches, token management
- [ ] 23-02-PLAN.md — Vehicle tests: parametrized property getters, action methods, update flows, discovery
- [ ] 23-03-PLAN.md — Dashboard tests: Instrument hierarchy, Dashboard class, specialized subclasses, edge cases
- [ ] 23-04-PLAN.md — Consolidation: merge phase-specific files, fill coverage gaps, verify 80%+ target

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
| 22. Fix Medium & Nitpick PR Issues | 2/2 | Complete    | 2026-03-02 | - |
| 23. Holistic Test Suite | 2/4 | In Progress|  | - |
