# Round 2: Narrow Security Audit — Key Rotation

**Date:** 2025-02-15  
**Scope:** `src/handlers/auth.py::rotate_key` + `src/utils/auth.py`  
**Auditor:** Automated security subagent

---

## Finding 1: Orphaned GSI2 Entries After Key Deletion

**Severity: HIGH**

The `rotate_key` function deletes old API key items by their primary key (`PK`/`SK`), but DynamoDB GSI entries are projections — they are eventually consistent and derived from the base table. Deletion of the base item *does* propagate to the GSI, so the GSI2 entry will be removed. **This is actually fine mechanically.**

However, there is a timing gap. GSI updates are **eventually consistent**. Between deleting the old key item and the GSI2 propagation completing, the old key hash still resolves in GSI2. Combined with the `authenticate()` function querying GSI2 without `ConsistentRead` (GSIs don't support it), there's a window where the **old key remains valid** after rotation.

**Impact:** Old key continues to authenticate for a brief window (typically <1s, but no guarantee).

**Recommendation:** Accept as inherent DynamoDB limitation, or add a `revoked_at` field and check it during auth.

---

## Finding 2: Race Condition on Concurrent Rotation

**Severity: HIGH**

If two `rotate_key` requests arrive simultaneously with the same valid key:

1. Both calls `authenticate()` successfully (old key still valid)
2. Both query for existing APIKEY# items
3. Both delete the same old key items
4. Both generate new keys and write new APIKEY# records
5. **Result:** Two valid API keys exist for the same user

There is no locking, conditional write, or version check. An attacker who intercepts a key could race the legitimate owner's rotation to maintain access.

**Impact:** Attacker retains valid credentials after rotation intended to revoke them.

**Recommendation:** Use a DynamoDB conditional expression (e.g., optimistic locking with a `key_version` counter on the USER#META record) to ensure only one rotation succeeds.

---

## Finding 3: Delete-Then-Create Non-Atomicity

**Severity: MEDIUM**

The rotation performs three separate DynamoDB operations:
1. Query existing keys
2. Batch-delete old keys
3. Put new key

These are not wrapped in a DynamoDB transaction (`transact_write_items`). If the Lambda crashes or times out between step 2 and step 3, the user is left with **zero valid keys** and no recovery path (no key to call rotate again, no password reset flow).

**Impact:** User permanently locked out on partial failure.

**Recommendation:** Use `transact_write_items` to atomically delete old + create new, or at minimum create the new key before deleting the old one.

---

## Finding 4: Hardcoded Permissions — New Key Doesn't Inherit

**Severity: MEDIUM**

The new key is always created with `"permissions": ["read", "write"]` hardcoded. The old key's actual permissions are never read. If permissions were ever customized (e.g., read-only key), rotation silently **escalates to full permissions**.

**Impact:** Privilege escalation if custom permissions are ever implemented.

**Recommendation:** Read the old key's permissions before deletion and copy them to the new key item, or derive permissions from the user record.

---

## Finding 5: No Authorization Boundary Issues

**Severity: INFORMATIONAL**

Rotation requires a valid API key via `authenticate()`. An attacker cannot rotate another user's key without possessing that user's key. The `user_id` is derived from the authenticated key record, not from user input. **This is correctly implemented.**

---

## Finding 6: Response Information Leakage

**Severity: LOW**

The rotation response includes `user_id`. This is the same `user_id` the caller already knows (they're authenticated), so no *new* information leaks. The raw API key must be returned (it's the only chance to see it). The `message` field is benign.

**No issue found.** Response is clean.

---

## Finding 7: Cryptographic Strength of New Key

**Severity: INFORMATIONAL**

- `secrets.token_urlsafe(32)` → 32 bytes of OS entropy → 256 bits → excellent
- SHA-256 hash for storage → industry standard, no reversibility
- Prefix `ap_live_` aids identification without weakening entropy

**No issue found.** Key generation is cryptographically sound.

---

## Finding 8: GSI Eventual Consistency in Authentication

**Severity: MEDIUM**

`authenticate()` queries GSI2 which only supports eventually consistent reads. After rotation:
- New key may not appear in GSI2 immediately → brief auth failure window
- Old key may linger in GSI2 → brief window where old key still works

This is the same issue as Finding 1 but from the new-key perspective. The user may get a 401 immediately after rotation if they try to use the new key before GSI2 propagates.

**Impact:** Brief authentication failures with valid new key; brief continued validity of old key.

**Recommendation:** Document this behavior. For stronger guarantees, auth could fall back to a direct `query` on the base table (`PK=USER#{id}`, `SK begins_with APIKEY#`) using consistent reads when GSI2 lookup fails.

---

## Summary

| # | Finding | Severity |
|---|---------|----------|
| 1 | Old key valid briefly after rotation (GSI eventual consistency) | HIGH |
| 2 | Race condition: concurrent rotation → duplicate valid keys | HIGH |
| 3 | Non-atomic delete+create → possible lockout on partial failure | MEDIUM |
| 4 | Permissions hardcoded, not inherited from old key | MEDIUM |
| 5 | No cross-user rotation possible (correct) | INFORMATIONAL |
| 6 | Response reveals no sensitive data beyond necessity | LOW |
| 7 | Key generation cryptographically sound | INFORMATIONAL |
| 8 | New key may not work immediately (GSI propagation delay) | MEDIUM |

**Top priority fix:** Finding 2 (race condition) — use `transact_write_items` with a version counter to make rotation atomic and prevent duplicate keys.
