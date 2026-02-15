# Round 2: Narrow QA Agent — `POST /auth/rotate-key`

**Date:** 2026-02-15  
**Agent:** Hyper-focused QA (rotate-key only)  
**Scope:** End-to-end functional testing of key rotation endpoint

---

## Test Environment
- **API:** `https://brz91cuha4.execute-api.us-east-1.amazonaws.com/dev`
- **Blocker:** Registration rate limit (5/hour/IP) was exhausted by prior round-2 agents. Happy-path tests (1-6, 9-10) could not execute. Error-path tests (7-8) completed.

## Test Results

| # | Test | Expected | Actual | Status |
|---|------|----------|--------|--------|
| 1 | Register fresh account | 201 + apiKey | 429 `rate_limited` — prior agents exhausted 5/hr registration quota | ⏸️ BLOCKED |
| 2 | GET /auth/me with valid key | 200 + profile | Blocked (no key from test 1) | ⏸️ BLOCKED |
| 3 | POST /auth/rotate-key with valid key | 200 + new apiKey | Blocked (no key) | ⏸️ BLOCKED |
| 4 | Old key returns 401 after rotation | 401 | Blocked (no rotation occurred) | ⏸️ BLOCKED |
| 5 | New key works on GET /auth/me | 200 | Blocked | ⏸️ BLOCKED |
| 6 | Double rotation: rotate again, verify chain | 200 + newest key works, old keys fail | Blocked | ⏸️ BLOCKED |
| 7 | Rotate with no auth header | 401 | 401 `{"error":"unauthorized","message":"API key required"}` | ✅ PASS |
| 8 | Rotate with invalid/expired key | 401 | 401 `{"error":"unauthorized","message":"API key required"}` | ✅ PASS |
| 9 | Rotate with key from deleted account | 401 | Blocked (no account to delete) | ⏸️ BLOCKED |
| 10 | Delete test account (cleanup) | 200 | Blocked (nothing to clean up) | ⏸️ BLOCKED |

## Summary

- **Passed:** 2/10
- **Blocked:** 8/10
- **Failed:** 0/10

## Issues Found

### QA-1: Registration rate limit `retry_after` returns 0 while still blocked
**Severity:** Low  
**Details:** Response includes `"retry_after": 0` even when rate limit is still active. Clients following this field would retry immediately and loop forever.  
**Expected:** `retry_after` should return seconds until the oldest request expires from the window.

### QA-2: Auth failure lockout cascades across all endpoints
**Severity:** Medium (for test ergonomics; correct security behavior)  
**Details:** After sending 5 invalid keys (test 8 + implicit retries), all authenticated endpoints return 429 for 5 minutes — including rotate-key. An automated test suite hitting error cases first will lock itself out of happy-path tests.  
**Recommendation:** Test suites should run happy-path first, error-path second, with delays between invalid-key tests.

### QA-3: No distinction between "missing key" and "invalid key" in 401 response
**Severity:** Info (this is good security practice)  
**Details:** Both test 7 (no header) and test 8 (bad key) return identical 401 response. Prevents key enumeration.

## Integration Notes

**This agent was starved by shared rate limits.** The narrow-agent model's weakness is clear: three agents hitting the same API from the same IP share a 5/hr registration budget. The first agent (broad or another narrow) consumed all registrations, leaving this QA agent unable to test the core functionality.

**Mitigation options for future runs:**
1. Stagger agent launches with sufficient cooldown
2. Give each agent its own pre-registered test account
3. Use different source IPs per agent
4. Increase rate limits in dev environment

## Verdict

Cannot assess rotate-key functionality. Error-path responses are correct and well-formatted. The two tests that ran show proper 401 handling with no information leakage. Full test suite needs a fresh rate-limit window or pre-provisioned credentials.
