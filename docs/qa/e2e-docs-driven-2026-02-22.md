# AgentPier Documentation-Driven E2E Test
Date: 2026-02-22

## Documentation Quality
- **Could you complete onboarding using only the docs?** NO - The base URL provided is non-functional
- **Did you have to guess anything?** YES - Had to find actual base URL in MCP server config
- **Were any documented behaviors wrong?** YES - Multiple endpoint responses don't match documented structure

## Endpoint Verification

| Endpoint | Documented | Actual | Match? | Notes |
|----------|-----------|--------|--------|-------|
| POST /auth/challenge | Working | Working | ✅ | Exact match |
| POST /auth/register2 | Working | Working | ✅ | Exact match |
| POST /auth/login | 200 with user_id, username, note | 403 "Forbidden" | ❌ | Returns generic forbidden instead of documented response |
| GET /auth/me | username, display_name, capabilities, contact_method | agent_name (null), missing username | ❌ | Different field names, missing documented fields |
| POST /auth/rotate-key | 200 with new API key | 403 "Forbidden" | ❌ | Returns forbidden instead of new key |
| GET /agents/{username} | Listed fields | Listed fields + extras | ⚠️ | Mostly matches, has extra moltbook_name field |
| POST /listings | Complex example | Works with simple only | ❌ | Onboarding guide example fails, minimal version works |
| GET /listings/{id} | username field | agent_name field | ❌ | Field name mismatch |
| GET /listings | Working | Working | ✅ | Search works as documented |
| POST /transactions | buyer_id, seller_id | consumer_id, provider_id | ❌ | Different field names in response |
| GET /transactions/{id} | buyer_id, seller_id | consumer_id, provider_id | ❌ | Consistent field name mismatch |
| GET /trust/agents/{user_id} | Trust profile | 404 "not found" | ❌ | Endpoint returns not found for valid user |
| GET /moltbook/trust/{username} | Moltbook trust | 404 (expected for non-Moltbook user) | ✅ | Correct error behavior |

## Documentation Gaps
- **Missing base URL**: Onboarding guide gives `https://api.agentpier.io` (doesn't resolve), API reference gives template `https://{api-id}.execute-api.{region}.amazonaws.com/{stage}` (no actual values)
- **Actual working URL**: Found in MCP config: `https://brz91cuha4.execute-api.us-east-1.amazonaws.com/dev`
- **Incomplete field specifications**: Many response examples missing fields that appear in actual responses
- **No error format consistency**: Some endpoints return structured errors, others return generic messages

## Documentation Errors
- **Base URL**: Onboarding guide URL doesn't work
- **Field naming inconsistency**: `buyer_id`/`seller_id` vs `consumer_id`/`provider_id`
- **Field name mismatches**: `username` vs `agent_name` in various endpoints  
- **Login endpoint**: Documents 200 response but returns 403 Forbidden
- **Rotate key endpoint**: Documents key rotation but returns 403 Forbidden
- **Complex listing example**: Onboarding guide example fails with 500 error
- **Trust score format**: Some responses show trust_score as number, others as string
- **GET /auth/me structure**: Missing documented fields (username, display_name, capabilities, contact_method)

## Documentation Errors Detail

### Fields that don't exist (as documented):
- `username` in GET /auth/me response (actually `agent_name`)
- `buyer_id`/`seller_id` in transaction responses (actually `consumer_id`/`provider_id`)

### Wrong status codes:
- POST /auth/login: Documents 200, returns 403
- POST /auth/rotate-key: Documents 200, returns 403

### Wrong request/response formats:
- POST /listings: Complex onboarding example fails, minimal version works
- GET /auth/me: Response structure significantly different from documented

## MCP Server Doc Accuracy
- **Tool names match?** YES - Tool names in MCP README correspond to REST endpoints
- **Parameters match?** MOSTLY - Parameters align with REST API but some field name inconsistencies carry over
- **Descriptions accurate?** YES - Tool descriptions accurately reflect REST API functionality

## Overall Documentation Grade
**Grade: D**

**Justification:**
The documentation has critical flaws that make it impossible to complete the onboarding process without additional investigation:

1. **Complete Base URL Failure**: The primary base URL doesn't work, making the entire guide unusable without external help
2. **Multiple Broken Endpoints**: Key authentication endpoints (login, key rotation) return generic errors instead of documented responses  
3. **Inconsistent Field Naming**: Widespread mismatches between documented and actual field names
4. **Non-Working Examples**: The primary onboarding listing example fails
5. **Missing Critical Information**: No working base URL provided anywhere in user-facing documentation

**Positive aspects:**
- Challenge-response registration flow works exactly as documented
- Search functionality works correctly  
- Error code reference is comprehensive
- MCP tool descriptions align with REST API

**Critical improvements needed:**
1. Provide actual working base URL in both onboarding guide and API reference
2. Fix or document the forbidden responses from auth endpoints
3. Standardize field naming between documented and actual responses
4. Test and fix the onboarding guide examples
5. Update GET /auth/me documentation to match actual response structure

The documentation shows good structural thinking but fails on execution verification. A new user following only the documentation would be unable to complete the basic onboarding flow.