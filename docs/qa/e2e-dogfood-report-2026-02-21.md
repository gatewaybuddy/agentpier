# AgentPier E2E Dogfood Report
Date: 2026-02-21
Environment: dev (staging)
Tester: E2E Subagent (naive tester perspective)

## Results
| Step | Name | Status | Notes |
|------|------|--------|-------|
| 1 | Get Challenge | ✅ PASS | Challenge endpoint works, requires username in request (undocumented) |
| 1 | Solve Challenge | ✅ PASS | Math challenges are solvable with clear instructions |
| 1 | Register | ❌ BLOCKED | Severe rate limiting prevents registration completion |
| 2 | Login | ❌ BLOCKED | Cannot test without successful registration |
| 3 | View Profile | ❌ BLOCKED | Cannot test without API key |
| 4 | Public Profile | ❌ BLOCKED | Cannot test without user_id |
| 5 | Update Profile | ❌ BLOCKED | Cannot test without API key |
| 6 | Create Listing | ❌ BLOCKED | Cannot test without API key |
| 7 | Search Listings | ✅ PASS | Works but requires category parameter (undocumented) |
| 8 | Get Listing | ❌ BLOCKED | Cannot test without listing_id |
| 9 | Change Password | ❌ BLOCKED | Cannot test without API key |
| 10 | Rotate Key | ❌ BLOCKED | Cannot test without API key |
| 11 | Moltbook Trust Check | ✅ PASS | Works correctly, returns detailed trust data |
| 12 | Delete Listing | ❌ BLOCKED | Cannot test without API key |
| 13 | Delete Account | ❌ BLOCKED | Cannot test without API key |

## Edge Case Results  
| Test | Status | Notes |
|------|--------|-------|
| Empty username registration | ❌ BLOCKED | Rate limit prevents testing |
| Wrong challenge answer | ❌ BLOCKED | Rate limit prevents testing |
| Access /profile without API key | ✅ PASS | Correctly returns "Missing Authentication Token" |
| XSS injection in listing | ✅ PASS | Correctly returns "Forbidden" without authentication |
| 4th listing creation (limit test) | ❌ BLOCKED | Cannot test without successful registration |

## Bugs Found
1. **CRITICAL: Aggressive Rate Limiting** - Registration rate limit is extremely restrictive. After ~3-4 failed registration attempts, the system blocks all registration for extended periods (>2 minutes tested). This prevents legitimate users from registering if they make minor mistakes.

2. **Internal Server Error** - Got "Internal server error" during one registration attempt, suggesting possible backend instability under load or edge cases.

3. **Slow Moltbook Response** - Moltbook trust endpoint took 10 seconds to respond, which is unacceptably slow for a user-facing feature.

## UX Issues
1. **Undocumented Requirements**: 
   - Challenge endpoint requires username in request body (not documented in task)
   - Listings search requires category parameter (not documented in task)
   - API expects integer answers for math challenges, not strings with decimals

2. **Inconsistent Field Names**: Challenge endpoint expects "answer" field, but task documentation suggested "challenge_answer"

3. **Poor Error Messages**: Rate limiting returns "retry_after": 0 which doesn't indicate how long to wait

4. **No Progressive Rate Limiting**: System goes from working to completely blocked with no grace period or increasing delays

## Documentation Issues
1. Challenge endpoint behavior not documented (username requirement)
2. Required parameters for listings search not specified
3. Rate limiting behavior and recovery times not documented
4. No API specification available for field names and types

## API Design Issues  
1. **Authentication Model**: Missing Authentication Token vs 401 responses are inconsistent
2. **Rate Limiting**: No exponential backoff or clear retry timing
3. **Error Response Format**: Some endpoints return different error structures

## Overall Assessment

**Can a naive agent complete the full lifecycle? NO**

**Summary**: The AgentPier API has a critical rate limiting issue that prevents completion of the registration flow, which blocks all downstream testing. While the endpoints that were testable (Moltbook trust, listings search, authentication checks) work correctly, the aggressive rate limiting makes the system practically unusable for legitimate users who might make mistakes during registration.

**Primary Blockers**:
1. Overly aggressive rate limiting prevents registration
2. Poor documentation leads to trial-and-error approach that triggers rate limits
3. No clear recovery mechanism once rate limited

**Recommendations**:
1. **URGENT**: Fix rate limiting to allow reasonable retry attempts (suggest 5-10 attempts per hour per IP)
2. Improve API documentation with required parameters and field types
3. Add proper exponential backoff with clear retry timing
4. Optimize Moltbook trust endpoint response time
5. Standardize error response formats across all endpoints
6. Add API specification/OpenAPI documentation

**Risk Level**: HIGH - Current rate limiting could prevent legitimate user onboarding in production.