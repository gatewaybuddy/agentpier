# Content Filter Fixes — 2026-02-15

**Fixed by:** Automated subagent  
**Deployed:** 2026-02-15 01:21 EST  
**Stack:** agentpier-dev  

---

## Summary

The QA suite (2026-02-15-full-suite.md) found that only 3/9 content filter categories were blocking, plus Unicode spacing evasion bypassed the filter entirely. All issues have been fixed.

## Changes Made (`src/utils/content_filter.py`)

### 1. Added `normalize_text()` function
- **Zero-width Unicode stripping:** Removes `\u200b`, `\u200c`, `\u200d`, `\ufeff`, etc.
- **Spaced letter collapsing:** `"E s c o r t"` → `"Escort"` (3+ single letters separated by spaces)
- **Leetspeak substitution:** `@ → a`, `0 → o`, `1 → i`, `3 → e`, `$ → s`, `5 → s`, `! → i`, `+ → t`, `7 → t`, `4 → a`
- **Unicode normalization:** NFKD decompose → strip combining marks → NFKC recompose
- Applied to all input in `check_content()` before pattern matching

### 2. Broadened existing patterns
- **illegal_drugs:** Added generic `drugs?` with buy/sell/online/for-sale context, `drugs?\s*deal` for "drugs dealer" variant
- **weapons:** Added `guns?`, `weapons?`, `firearms?` plurals; added reverse-order pattern (weapons → for sale/cheap/online)
- **financial_scam:** Added `fake|forged|counterfeit` with plural forms (`ids?`, `passports?`, etc.), added fraud service patterns
- **malware:** Added `hack|crack|breach` + account/password/email context; hacking service/for-hire patterns

### 3. Added new categories
- **gambling:** Online gambling, casino/betting with commercial context, slots/poker with real-money context
- **hate_speech:** Supremacy groups, hate movements, neo-nazi, ethnic cleansing, extremist recruitment

### 4. Updated SEVERITY dict
- Added `gambling: "medium"` and `hate_speech: "high"`

---

## Verification Results (Local Unit Tests)

All 18 tests pass against the filter logic directly:

| # | Test | Input | Result | Category |
|---|------|-------|--------|----------|
| 1 | Weapons (QA phrase) | "Buy guns and weapons cheap" | ✅ Blocked | weapons |
| 2 | Drugs (QA phrase) | "Buy drugs online fast delivery" | ✅ Blocked | illegal_drugs |
| 3 | Gambling (QA phrase) | "Online gambling casino slots" | ✅ Blocked | gambling |
| 4 | Fraud (QA phrase) | "Fake IDs and documents" | ✅ Blocked | financial_scam |
| 5 | Hate (QA phrase) | "White supremacy group meetups" | ✅ Blocked | hate_speech |
| 6 | Hacking (QA phrase) | "Hack any account password" | ✅ Blocked | malware |
| 7 | Unicode spacing evasion | "E s c o r t services" | ✅ Blocked | exploitation |
| 8 | Mixed case drugs | "DRUGS For SALE" | ✅ Blocked | illegal_drugs |
| 9 | Mixed case drugs 2 | "DrUgS dEaLeR" | ✅ Blocked | illegal_drugs |
| 10 | Generic drugs | "Buy drugs online" | ✅ Blocked | illegal_drugs |
| 11 | Generic guns | "Buy guns cheap" | ✅ Blocked | weapons |
| 12 | Weapons for sale | "weapons for sale" | ✅ Blocked | weapons |
| 13 | Adult content | "Escort services available" | ✅ Blocked | exploitation |
| 14 | Violence | "Murder for hire services" | ✅ Blocked | weapons |
| 15 | Scam | "Get rich quick guaranteed profit" | ✅ Blocked | financial_scam |
| 16 | Clean (plumbing) | "Professional plumbing services" | ✅ Passed | — |
| 17 | Clean (tutoring) | "Math tutoring for high school students" | ✅ Passed | — |
| 18 | Clean (web dev) | "Website development and design services" | ✅ Passed | — |

## Live API Verification

Live API tests could not be performed with authenticated requests due to IP-level rate limiting from the earlier QA suite run (registration endpoint returns 403). The rate limit will expire after the cooldown period. The filter logic is verified correct via local tests above, and the deployment succeeded.

**Note:** The IP-level rate limiting issue (bleeds across endpoints) is a separate finding from the QA report (see section "Rate Limit Too Aggressive on Registration").

---

## Status

- ✅ All 6 previously-failing categories now block correctly
- ✅ Unicode spacing evasion defeated
- ✅ Mixed case handled (was already via re.IGNORECASE, patterns were the issue)
- ✅ Generic terms ("drugs", "guns", "weapons") now caught with context
- ✅ New categories (gambling, hate_speech) added
- ✅ Clean content still passes
- ✅ Deployed to agentpier-dev stack
