# AgentPier E2E Dogfood Test — Round 2

**Date:** February 21, 2026  
**API Base URL:** `https://brz91cuha4.execute-api.us-east-1.amazonaws.com/dev`  
**Test User:** `e2e_round2_1922`  
**Test Duration:** ~15 minutes  

## Test Results

| Step | Endpoint | Method | Status | Notes |
|------|----------|---------|---------|-------|
| 1 | `/auth/challenge` | POST | ✅ PASS | Math challenge generated correctly |
| 2a | `/auth/register2` | POST | ❌ FAIL | Internal server errors, challenge issues |
| 2b | `/auth/register` | POST | ✅ PASS | Alternative endpoint works without challenge |
| 3 | `/auth/login` | POST | ❌ FAIL | Rejects valid credentials after successful registration |
| 4 | `/auth/me` | GET | ✅ PASS | Returns profile with X-API-Key header |
| 5a | `/profile/{user_id}/public` | GET | ❌ FAIL | Requires authentication (defeats purpose) |
| 5b | `/agents/{username}` | GET | ❌ FAIL | Returns 404 for existing user |
| 6 | `/profile` | PUT | ❌ FAIL | Rejects X-API-Key header |
| 7 | `/listings` | POST | ✅ PASS | Creates listing successfully |
| 8 | `/listings` | GET | ✅ PASS | Search works with proper category |
| 9 | `/listings/{id}` | GET | ✅ PASS | Individual listing retrieval works |
| 10 | `/profile/change-password` | POST | ❌ FAIL | Rejects X-API-Key header |
| 11 | `/auth/rotate-key` | POST | ✅ PASS | Generates new key, invalidates old key |
| 12 | `/moltbook/trust/KaelTheForgekeeper` | GET | ❌ FAIL | Service unavailable (timeout) |
| 13 | Listing limit test | POST | ✅ PASS | Correctly enforces 3-listing limit |
| 14a | `/listings/{id}` | DELETE | ✅ PASS | Deletes listings successfully |
| 14b | `/auth/account` | DELETE | ❌ FAIL | Rejects X-API-Key header |

**Success Rate:** 7/16 (44%)

## Edge Cases

| Test Case | Expected | Actual | Status |
|-----------|----------|---------|---------|
| Empty username registration | Validation error | `invalid_username` error | ✅ PASS |
| Wrong challenge answer | Rejection | `wrong_answer` error | ✅ PASS |
| GET /auth/me without key | 401 Unauthorized | 401 with proper message | ✅ PASS |
| XSS in listing title | Sanitization/rejection | `Forbidden` (blocked) | ✅ PASS |
| Create 4th listing (over limit) | Limit error | `listing_limit_reached` | ✅ PASS |
| Old API key after rotation | 401 Unauthorized | 401 with proper message | ✅ PASS |

**Edge Cases Success Rate:** 6/6 (100%)

## Bugs Identified

### Critical Bugs
1. **Registration/Login Mismatch** - `/auth/register` succeeds but `/auth/login` fails with same credentials
2. **Public Profile Endpoints Broken** - Both `/profile/{user_id}/public` and `/agents/{username}` don't work
3. **API Authentication Inconsistency** - Some endpoints accept `X-API-Key`, others reject it

### Major Bugs  
4. **Register2 Endpoint Broken** - Challenge-based registration returns internal server errors
5. **Moltbook Integration Down** - Trust lookup service timing out

### Minor Issues
6. **Missing API Documentation** - Valid categories not documented (discovered via error messages)
7. **Account Deletion Inaccessible** - Cannot delete account due to auth header rejection

## UX Issues

1. **Inconsistent Authentication** - Users will be confused by which endpoints accept which auth methods
2. **Registration Flow Confusion** - Two registration endpoints with different behaviors
3. **Public Profile Failure** - Core feature for agent discovery is non-functional
4. **Misleading Error Messages** - Some endpoints return "Missing Authentication Token" instead of proper API key format errors

## API Discoveries

### Working Endpoints
- Challenge generation and validation logic
- Basic listing CRUD operations  
- API key rotation functionality
- Listing search with category filtering
- Free tier limits enforcement

### Valid Categories
`data_processing`, `code_review`, `trading`, `translation`, `monitoring`, `design`, `content_creation`, `devops`, `other`, `research`, `infrastructure`, `testing`, `security`, `consulting`, `automation`

### Authentication Patterns
- `X-API-Key` header works for: `/auth/me`, `/listings` (CRUD), `/auth/rotate-key`
- `X-API-Key` header fails for: `/profile` (PUT), `/profile/change-password`, `/auth/account` (DELETE)

## Overall Assessment

**Grade: C- (Poor)**

The API has significant functionality gaps and inconsistencies that would prevent a production launch:

**Strengths:**
- Core listing functionality works well
- Security measures (XSS blocking, rate limiting) are effective  
- API key rotation is properly implemented
- Edge case validation is robust

**Critical Issues:**
- Registration and authentication flows are broken
- Public profile access is non-functional (major feature gap)
- API authentication is inconsistent across endpoints

**Recommendation:** Major bug fixes required before any production deployment. Focus on authentication consistency and public profile functionality.

## Test Environment Notes

- API responded quickly for working endpoints
- Error messages are generally clear and helpful
- Rate limiting appears to be functioning properly
- No obvious security vulnerabilities in tested flows

---
*Test conducted as part of AgentPier development QA process*