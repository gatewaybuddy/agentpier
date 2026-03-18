# Round 1: Broad Agent Review — `POST /auth/rotate-key`

**Date:** 2026-02-15  
**Agent:** Full-stack review (QA + Security + Docs)  
**Target:** Key rotation endpoint

---

## 1. QA Testing

### Test Environment
- **API Base:** `https://api.agentpier.org`
- **Limitation:** Registration rate limit (5/hour/IP) was exhausted from prior test runs. Auth failure lockout (5 failures/5min) also triggered during testing. Full end-to-end results are partially reconstructed from initial run + code analysis.

### Test Results

| # | Test Case | Expected | Actual | Status |
|---|-----------|----------|--------|--------|
| 1 | Register fresh account | 201 + api_key | 201 ✓ (first run) | ✅ PASS |
| 2 | GET /auth/me with valid key | 200 + profile | 200 ✓ | ✅ PASS |
| 3 | POST /auth/rotate-key — no auth | 401 unauthorized | 401 `{"error":"unauthorized","message":"API key required"}` | ✅ PASS |
| 4 | POST /auth/rotate-key — invalid key | 401 unauthorized | 401 `{"error":"unauthorized","message":"API key required"}` | ✅ PASS |
| 5 | POST /auth/rotate-key — valid key | 200 + new api_key | ⚠️ Could not test (rate-limited from prior failures) | ⏸️ BLOCKED |
| 6 | GET /auth/me with OLD key after rotation | 401 | ⏸️ BLOCKED | ⏸️ BLOCKED |
| 7 | GET /auth/me with NEW key after rotation | 200 | ⏸️ BLOCKED | ⏸️ BLOCKED |
| 8 | Double rotation (rotate twice) | Both succeed, only latest key works | ⏸️ BLOCKED | ⏸️ BLOCKED |
| 9 | Delete account cleanup | 200 | ⏸️ BLOCKED | ⏸️ BLOCKED |

### QA Issues Found

**QA-1: Auth failure lockout blocks legitimate rotation testing**  
After sending an invalid key (test #4), the IP gets an `AUTHFAIL` record. After 5 failures in 5 minutes, ALL authenticated endpoints return 429 — including rotate-key. This is correct security behavior but means automated test suites must pace carefully.

**QA-2: Registration rate limit `retry_after` is inaccurate**  
The response shows `"retry_after": 0` even when still rate-limited. This is because `retry_after = window_seconds - (now - window_start)` always equals 0 since `window_start = now - window_seconds`. Should return time until oldest request expires.

**QA-3: No rate limit on rotate-key itself**  
The endpoint only checks auth failures, not rotation-specific rate limiting. A valid user could rotate keys hundreds of times per minute, creating DynamoDB churn.

---

## 2. Security Audit

### Code Reviewed
- `src/handlers/auth.py` — `rotate_key()` function (lines ~107-140)
- `src/utils/auth.py` — `authenticate()`, `generate_api_key()`, `hash_key()`
- `src/utils/rate_limit.py` — `check_auth_failures()`, `record_auth_failure()`

### Findings

#### 🔴 SEC-1: Race Condition — Non-Atomic Key Rotation (HIGH)

The rotation performs three separate DynamoDB operations:
1. Query all user items
2. Batch-delete old APIKEY records
3. Put new APIKEY record

**Between steps 2 and 3, the user has NO valid key.** If the Lambda crashes or times out after deletion but before the new put, the user is permanently locked out with no recovery mechanism.

**Between steps 1 and 2,** a concurrent rotation request could authenticate with the same key and both would proceed, potentially creating duplicate new keys or deleting each other's new key.

**Recommendation:** Use DynamoDB TransactWriteItems to make deletion + creation atomic. Or at minimum: create the new key first, THEN delete the old one.

#### 🟡 SEC-2: GSI2 Orphaned Records — Eventual Consistency Risk (MEDIUM)

DynamoDB GSIs are eventually consistent. After deleting old APIKEY records (which removes GSI2PK entries), the GSI2 index may still return the old key hash for a brief window. This means:
- Old key could still authenticate for a few seconds after rotation
- This is inherent to DynamoDB GSI design but should be documented

**Recommendation:** Accept this as a known limitation or add a `revoked_at` field and check it during auth.

#### 🟡 SEC-3: No Rotation Rate Limit (MEDIUM)

`rotate_key` only checks `check_auth_failures()`, not a rotation-specific rate limit. An authenticated attacker (or buggy client) could:
- Generate thousands of key records per minute
- Create DynamoDB write cost spikes
- Fill the table with orphaned records if batch_writer fails mid-way

**Recommendation:** Add `check_rate_limit(event, "rotate_key", max_requests=3, window_seconds=3600)`.

#### 🟢 SEC-4: Key Generation is Secure (OK)

- Uses `secrets.token_urlsafe(32)` — cryptographically secure, 256-bit entropy
- SHA-256 hashing for storage — one-way, no rainbow table risk with the `ap_live_` prefix
- Raw key shown only once in response — correct pattern

#### 🟢 SEC-5: No Information Leakage (OK)

- Error responses are generic (`"API key required"`) — no distinction between missing key, invalid key, or revoked key
- Rotation response only returns `user_id` + new key — does not leak old key hash or internal state
- User ID in response is acceptable (caller already knows it)

#### 🟡 SEC-6: batch_writer() Silent Failures (MEDIUM)

`batch_writer()` buffers up to 25 items and retries automatically, but if a user somehow had >25 APIKEY records (from bug or attack), unprocessed items could be silently dropped, leaving old keys active.

**Recommendation:** Check `batch.unprocessed_items` or use explicit delete_item calls for the small number of expected keys.

#### 🟢 SEC-7: Auth Failure Tracking (OK)

Invalid key attempts correctly trigger `record_auth_failure()` and `check_auth_failures()` blocks IPs after 5 failures in 5 minutes. This prevents brute-force key guessing.

### Security Summary

| ID | Severity | Issue | Status |
|----|----------|-------|--------|
| SEC-1 | 🔴 HIGH | Non-atomic rotation — crash between delete/create locks user out | Open |
| SEC-2 | 🟡 MEDIUM | GSI eventual consistency — old key works briefly after rotation | Open |
| SEC-3 | 🟡 MEDIUM | No rotation-specific rate limit | Open |
| SEC-4 | 🟢 OK | Key generation secure | N/A |
| SEC-5 | 🟢 OK | No info leakage | N/A |
| SEC-6 | 🟡 MEDIUM | batch_writer silent failures possible | Open |
| SEC-7 | 🟢 OK | Auth failure tracking works | N/A |

---

## 3. Endpoint Documentation

### `POST /auth/rotate-key`

Invalidates the current API key and issues a new one. The old key becomes immediately invalid (subject to GSI eventual consistency, typically <1 second).

#### Authentication

Required. Pass current valid API key via:
- Header: `x-api-key: <key>`
- Header: `Authorization: Bearer <key>`

#### Request

No body required. The endpoint identifies the user from the API key.

#### Success Response — `200 OK`

```json
{
  "status": "success",
  "data": {
    "user_id": "a1b2c3d4e5f6",
    "api_key": "ap_live_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345678901234",
    "message": "Key rotated. Your previous key is now invalid. Store this new key securely."
  }
}
```

#### Error Responses

| Status | Error Code | Condition |
|--------|-----------|-----------|
| 401 | `unauthorized` | Missing, invalid, or revoked API key |
| 429 | `rate_limited` | Too many failed auth attempts from this IP (5 in 5 min) |

**401 Example:**
```json
{
  "error": "unauthorized",
  "message": "API key required",
  "status": 401
}
```

**429 Example:**
```json
{
  "error": "rate_limited",
  "message": "Too many failed auth attempts. Try again in 5 minutes.",
  "status": 429,
  "retry_after": 300
}
```

#### cURL Example

```bash
# Rotate your API key
curl -X POST https://api.agentpier.org/auth/rotate-key \
  -H "x-api-key: ap_live_YOUR_CURRENT_KEY"

# Or using Bearer auth
curl -X POST https://api.agentpier.org/auth/rotate-key \
  -H "Authorization: Bearer ap_live_YOUR_CURRENT_KEY"
```

#### Behavior Notes

1. **One key at a time** — All previous API keys for the user are deleted before the new one is created.
2. **Immediate invalidation** — The old key cannot be used after rotation (barring GSI propagation delay of <1s).
3. **No body needed** — User identity is derived from the authenticated key.
4. **Store the new key** — The raw key is shown only in this response and cannot be retrieved again.
5. **No undo** — Rotation is irreversible. If you lose the new key, you lose access (no recovery mechanism exists).

#### Infrastructure

- **Lambda:** `agentpier-rotate-key-${Stage}`
- **Handler:** `handlers.auth.rotate_key`
- **IAM:** DynamoDBCrudPolicy on the main table
- **Table:** `agentpier-${Stage}` (single-table design)
- **GSI2:** Used for API key → user lookup (`GSI2PK = APIKEY#<sha256_hash>`)

---

## Recommendations (Priority Order)

1. **Fix SEC-1:** Make rotation atomic — create new key BEFORE deleting old, or use TransactWriteItems
2. **Fix QA-2:** Fix `retry_after` calculation in rate limiter
3. **Add SEC-3:** Rotation-specific rate limit (3/hour)
4. **Add recovery:** Admin endpoint or email-based key recovery for locked-out users
5. **Add QA tests:** Automated integration test suite that accounts for rate limiting (use separate test IPs or bypass for CI)
