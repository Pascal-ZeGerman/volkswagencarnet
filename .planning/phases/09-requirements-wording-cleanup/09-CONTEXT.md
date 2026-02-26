# Phase 9: Requirements Wording & Docs Cleanup - Context

**Gathered:** 2026-02-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Update REQUIREMENTS.md wording for MGMT-02, TEST-02, TEST-04 to accurately describe NA Car-Net behavior. Fix `_refresh_idk_token()` docstring. Add missing `issued_at` key to `_login_na()` token writes. No new functionality.

</domain>

<decisions>
## Implementation Decisions

### Requirement rewrite tone
- State what the library does AND explain the server limitation — helps future maintainers distinguish "not implemented" from "server doesn't support it"
- MGMT-02: "Library can refresh IDK token using refresh_token and code_verifier (X-QMAuth omitted — server rejects it with HTTP 400)"
- TEST-02: "IDK token obtained and validated; Brand/MBB tokens not available on NA Car-Net (endpoints return 404)"
- TEST-04: "IDK token refresh working; Brand/MBB refresh not applicable (NA Car-Net does not expose these endpoints)"

### Claude's Discretion
- Exact sentence structure for requirement updates (above wording is the direction, minor phrasing fine)
- `issued_at` format: match existing pattern from `_refresh_idk_token()` (use `time.time()`)
- Docstring fix: simply remove "Requires X-QMAuth header", replace with "Does NOT send X-QMAuth header (server rejects it with HTTP 400)"

</decisions>

<specifics>
## Specific Ideas

- "State + explain server limit" style — not just removing wrong text, but documenting the WHY for future contributors

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 09-requirements-wording-cleanup*
*Context gathered: 2026-02-26*
