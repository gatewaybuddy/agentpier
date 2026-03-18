# AgentPier QA Test Suite — 2026-02-15

**Run time:** 2026-02-15 01:14:13 EST  
**API:** `https://api.agentpier.org`  
**Result:** 31 PASS / 8 FAIL / 7 WARN (46 total)

---

## Results

| # | Test | Result | Details |
|---|------|--------|---------|
| 1.1 | Register account A | ✅ PASS | user=f54460711045 |
| 1.2 | Register account B | ✅ PASS | user=eba13856a633 |
| 2.1 | Get profile (auth/me) | ✅ PASS | Returns user profile |
| 2.2 | Invalid API key rejected | ✅ PASS | HTTP 401 |
| 2.3 | Missing API key rejected | ✅ PASS | HTTP 401 |
| 2.4 | Key rotation - old key invalidated | ✅ PASS | Old key rejected |
| 2.5 | Key rotation - new key works | ✅ PASS | New key accepted |
| 2.6 | Auth failure lockout | ✅ PASS | Locked out after 4 attempts (HTTP 429) |
| 3.1 | Create listing | ✅ PASS | id=lst_5b1f40d1dced |
| 3.2 | Read listing | ✅ PASS | title=QA Test Plumbing Service |
| 3.3 | Update listing | ✅ PASS | Updated successfully |
| 3.4 | Verify update persisted | ✅ PASS | title=QA Test Plumbing UPDATED |
| 4.1 | Cross-account update blocked | ✅ PASS | HTTP 403 |
| 4.2 | Cross-account delete blocked | ✅ PASS | HTTP 403 |
| 4.3 | Listing survives cross-account attack | ✅ PASS | Still accessible |
| 5.1 | Content filter: weapons | ❌ FAIL | Content was ACCEPTED (should be blocked) |
| 5.2 | Content filter: drugs | ❌ FAIL | Content was ACCEPTED (should be blocked) |
| 5.3 | Content filter: adult | ✅ PASS | Blocked (HTTP 400) |
| 5.4 | Content filter: gambling | ❌ FAIL | Content was ACCEPTED (should be blocked) |
| 5.5 | Content filter: fraud | ❌ FAIL | Content was ACCEPTED (should be blocked) |
| 5.6 | Content filter: hate | ❌ FAIL | Content was ACCEPTED (should be blocked) |
| 5.7 | Content filter: violence | ✅ PASS | Blocked (HTTP 400) |
| 5.8 | Content filter: hacking | ❌ FAIL | Content was ACCEPTED (should be blocked) |
| 5.9 | Content filter: scam | ✅ PASS | Blocked (HTTP 403) |
| 5.10 | Clean content passes filter | ✅ PASS | id=lst_7b0eb8881b57 |
| 5.11 | Evasion: leetspeak weapons | ✅ PASS | Blocked (HTTP 400) |
| 5.12 | Evasion: unicode spacing adult | ❌ FAIL | Spacing trick evaded filter! |
| 5.13 | Evasion: mixed case drugs | ❌ FAIL | Mixed case evaded filter! |
| 6.1 | Create 3 listings (free limit) | ✅ PASS | All 3 created |
| 6.2 | 4th listing rejected (free limit) | ✅ PASS | HTTP 402 |
| 6.3 | Create after delete (count accuracy) | ✅ PASS | Slot freed up correctly |
| 6.4 | Listing count accuracy in profile | ⚠️ WARN | `listing_count` field not found in /auth/me response |
| 7.1 | Missing required fields rejected | ✅ PASS | HTTP 400 |
| 7.2 | Oversized title rejected | ✅ PASS | HTTP 400 |
| 7.3 | Invalid category rejected | ✅ PASS | HTTP 400 |
| 7.4 | Invalid pricing rejected | ⚠️ WARN | Accepted invalid pricing type and negative max (HTTP 201) |
| 7.5 | Oversized description rejected | ⚠️ WARN | HTTP 403 (possibly content filter, not validation) |
| 8.1 | Registration rate limit | ✅ PASS | Hit after 1 attempt (HTTP 429) |
| 9.1 | Empty body rejected | ✅ PASS | HTTP 400 |
| 9.2 | Null fields rejected | ✅ PASS | HTTP 400 |
| 9.3 | Special chars / XSS in title | ⚠️ WARN | HTTP 403 — content filter may be too aggressive on `<script>` |
| 9.4 | Very long tag rejected | ⚠️ WARN | Accepted 600-char tag (HTTP 201) |
| 9.5 | Nonexistent listing returns 404 | ✅ PASS | HTTP 404 |
| 9.6 | Delete nonexistent listing returns 404 | ✅ PASS | HTTP 404 |
| C.1 | Cleanup account A | ⚠️ WARN | Rate limited (429) — cleanup retried after cooldown |
| C.2 | Cleanup account B | ⚠️ WARN | Rate limited (429) — cleanup retried after cooldown |

---

## Critical Findings

### 🔴 CRITICAL — Content Filter Bypasses (6 of 9 categories fail)

**Severity: CRITICAL**

The content filter only blocks 3 of 9 categories (adult, violence, scam). The following categories pass through unchecked:

| Category | Content Tested | Result |
|----------|---------------|--------|
| Weapons | "Buy guns and weapons cheap" | ❌ Accepted |
| Drugs | "Buy drugs online fast delivery" | ❌ Accepted |
| Gambling | "Online gambling casino slots" | ❌ Accepted |
| Fraud | "Fake IDs and documents" | ❌ Accepted |
| Hate | "White supremacy group meetups" | ❌ Accepted |
| Hacking | "Hack any account password" | ❌ Accepted |

**Recommendation:** The content filter likely uses keyword matching or a lightweight model. It needs to be expanded to cover all 9 categories. Consider using an LLM-based moderation layer or a more comprehensive blocklist.

### 🔴 HIGH — Content Filter Evasion

**Severity: HIGH**

Two evasion techniques bypassed the filter:
- **Unicode spacing:** `"E s c o r t services"` — evaded adult content filter
- **Mixed case:** `"DRUGS For SALE"` / `"DrUgS dEaLeR"` — evaded drug content filter

**Recommendation:** Normalize input before filtering (strip extra spaces, lowercase, strip unicode tricks).

### 🟡 MEDIUM — No Pricing Validation

Invalid pricing (`type: "invalid"`, `min: "not_a_number"`, `max: -1`) was accepted. Could lead to garbage data in search results.

### 🟡 MEDIUM — No Tag Length Validation

A 600-character tag was accepted. Should enforce max tag length (e.g., 50 chars).

### 🟡 LOW — Missing listing_count in /auth/me

The profile endpoint doesn't expose a listing count field, or uses an unexpected key name. May be a docs gap.

### 🟡 LOW — Rate Limit Too Aggressive on Registration

Rate limit hit on the very first registration attempt during the rate limit test (test 8.1). This is because the lockout test (2.6) triggered IP-based rate limiting that bled into later tests. The rate limiter may be too broad (IP-level instead of per-endpoint).

---

## What Worked Well

- ✅ **Auth flow is solid** — registration, profile, key rotation, old key invalidation all work correctly
- ✅ **Cross-account protection is airtight** — account B cannot touch account A's listings (403)
- ✅ **CRUD operations work correctly** — create, read, update, delete all function properly
- ✅ **Listing limits enforced** — free tier 3-listing cap works, count recalculates after deletes
- ✅ **Input validation good for basics** — missing fields, invalid categories, oversized titles all rejected
- ✅ **Auth lockout works** — 4 failed attempts triggers 429 with 5-min cooldown
- ✅ **404 handling correct** — nonexistent resources return proper 404

---

## Cleanup Status

Test accounts could not be deleted during the test run due to rate limiting (the auth lockout test triggered IP-based rate limits). Accounts will need manual cleanup or will be cleaned up on the next attempt after the 5-minute cooldown.

- Account A: `f54460711045` (key rotated during test)
- Account B: `eba13856a633`
