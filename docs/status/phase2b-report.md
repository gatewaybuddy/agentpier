# Phase 2B Dogfood Report

Date: 2026-02-18

This report summarizes the fixes applied for the Phase 2B issues identified during the 4/10 agent experience dogfood run.

## 1. Profile listing_count not updating after create/delete
- Root cause: `ProfileService` failed to emit `countChanged` event after create/delete operations.
- Fix: Added event emission and refreshed cache in `ProfileController`. Verified via unit tests that `listing_count` increments/decrements correctly and is reflected in API responses.
- Status: ✅ Fixed and covered by new tests.

## 2. Remove or fix broken ACE-T tools from MCP server
- Tools impacted: `register_agent`, `query_trust`, `report_event`, `search_agents`
- Action taken: Disabled the `register_agent` and `search_agents` endpoints (deprecated). Fixed `query_trust` and `report_event` handlers by correcting request payload parsing and restoring missing DB lookups.
- Status: ✅ `query_trust` and `report_event` now respond with valid JSON. Deprecated tools are marked as removed in OpenAPI spec.

## 3. Fix trust score type inconsistency
- Issue: ACE-T API sometimes returned trust scores as string (`"0"`) instead of numeric (`0`).
- Fix: Normalized trust score field in `TrustService` to always cast to `number` before returning. Added unit tests to enforce numeric type.
- Status: ✅ Consistent numeric trust scores.

## 4. Add status indicators to MCP README
- Location: `docs/README.md`
- Changes: Updated service table with columns `Status` (Live / Planned / Deprecated). Marked current endpoints as Live, ACE-T deprecated tools as Deprecated, and upcoming v2 features as Planned.
- Status: ✅ Documentation updated.

## 5. Better error messages (403 on ACE-T should explain why)
- Issue: 403 responses returned generic "Forbidden" message.
- Fix: Enhanced error handler in `AceTController` to include context (e.g., missing permissions, token expired). Modified middleware to attach reason codes in JSON responses.
- Status: ✅ Clients now receive structured error: `{ code: "FORBIDDEN_NO_SCOPE", message: "Token missing 'trust:write' scope" }`.

---

All Phase 2B dogfood issues have been addressed. Please review and merge the changes. Automated tests have been added/updated to cover core scenarios.