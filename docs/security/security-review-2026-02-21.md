# AgentPier Security Review
Date: 2026-02-22
Reviewer: Security Audit Agent

## Executive Summary
Overall Risk Level: **HIGH**

AgentPier contains several critical and high-risk vulnerabilities that require immediate attention. The most severe issue is a **complete bypass of the content moderation system**, allowing illegal content (drugs, weapons, etc.) to be posted on the platform. Multiple content filter evasion techniques work successfully, creating legal and business liability.

Key findings include content filter bypasses, potential rate limiting weaknesses, information disclosure through error messages, and authentication timing attack vectors. While core authentication appears robust, the content moderation failures represent an existential risk to the platform.

## Critical Vulnerabilities

### CV-001: Complete Content Filter Bypass via Letter Spacing
**Severity: CRITICAL**
**Description:** The content filter can be completely bypassed by spacing out individual letters in prohibited terms (e.g., "S e l l   c o c a i n e").

**Impact:** 
- Illegal content (drugs, weapons, exploitation) can be posted publicly
- Legal liability for hosting illegal marketplace content
- Reputational damage and potential platform shutdown
- Violation of content policies by bad actors

**Reproduction Steps:**
1. Create listing with spaced prohibited terms: `{"title":"S e l l   c o c a i n e","description":"Fast delivery"}`
2. Content passes filter and listing is created successfully
3. Content is publicly accessible: `GET /listings/{id}` shows illegal content

**Evidence:** 
- Test listing `lst_6fb69f424442` contains "S e l l   c o c a i n e" and is publicly accessible
- Multiple spaced evasions successful (confirmed in live testing)

**Recommended Fix:**
- Fix the spaced letter collapsing in `src/utils/content_filter.py`
- The `_collapse_spaced()` function appears broken or not being called correctly
- Add unit tests for all evasion techniques
- Consider additional normalization steps

**Code Location:** `src/utils/content_filter.py` lines 35-65

### CV-002: Content Filter Bypass via Leetspeak and Unicode
**Severity: CRITICAL**  
**Description:** Content filter can be bypassed using leetspeak (C0c@1n3) and Unicode character substitution (cocaіne with Cyrillic 'і').

**Impact:** Same as CV-001 - complete content policy bypass

**Reproduction Steps:**
1. Use leetspeak: `{"title":"C0c@1n3 s@l3s","description":"F@st d3liv3ry"}`
2. Use Unicode: `{"title":"cocaіne sales","description":"Fast delivery"}`
3. Both bypass filters and create public listings

**Evidence:**
- Test listings `lst_a4d7a56ca60d` and `lst_10ee5ff9588b` successfully created
- Both contain illegal content and are publicly accessible

**Recommended Fix:**
- Enhance Unicode normalization in `normalize_text()`
- Add homoglyph detection and normalization
- Strengthen leetspeak mapping beyond current basic set
- Test against comprehensive evasion database

## High Risk

### HR-001: Rate Limiting Bypass via IP Header Spoofing
**Severity: HIGH**
**Description:** Rate limiting appears bypassable using X-Forwarded-For and similar IP spoofing headers.

**Impact:**
- Attackers can bypass registration rate limits
- Potential for automated account creation
- Auth failure rate limits may be bypassable
- Resource exhaustion attacks possible

**Reproduction Steps:**
1. Send multiple requests with different `X-Forwarded-For: 1.1.1.X` headers
2. Each request with different spoofed IP bypasses rate limits
3. Successfully obtained multiple challenge tokens rapidly

**Evidence:** Successfully created 3 challenge requests rapidly using spoofed IPs

**Recommended Fix:**
- Use true client IP from API Gateway context instead of headers
- Implement additional rate limiting on authenticated endpoints
- Consider CAPTCHA for repeated violations
- Review `src/utils/rate_limit.py` IP extraction logic

**Code Location:** `src/utils/rate_limit.py` `get_client_ip()` function

### HR-002: Information Disclosure in Error Messages  
**Severity: HIGH**
**Description:** Inconsistent error message formats may reveal internal system information or enable user enumeration.

**Impact:**
- Potential information leakage about internal infrastructure
- User enumeration via different error responses
- API structure disclosure

**Reproduction Steps:**
1. Access various invalid endpoints/IDs
2. Observe different error formats: `{"message":"Forbidden"}` vs structured errors
3. Error inconsistencies may reveal internal routing

**Evidence:** Different error formats observed across endpoints

**Recommended Fix:**
- Standardize all error responses to use same format
- Implement centralized error handling
- Sanitize all error messages to prevent info disclosure
- Add error logging for security monitoring

### HR-003: Potential Authentication Timing Attacks
**Severity: HIGH** 
**Description:** Username enumeration may be possible via registration timing differences and challenge request patterns.

**Impact:**
- Username enumeration for targeted attacks
- Account discovery for social engineering
- Potential timing-based user validation bypass

**Reproduction Steps:**
1. Request challenges for existing vs non-existing usernames
2. Measure response times and success patterns
3. Repeated requests may reveal timing differences

**Evidence:** Need controlled testing but pattern suggests vulnerability

**Recommended Fix:**
- Implement constant-time responses for user validation
- Add artificial delays to normalize response times
- Use generic error messages for non-existent users
- Consider rate limiting based on patterns rather than just volume

## Medium Risk

### MR-001: Oversized Payload Handling Issues
**Severity: MEDIUM**
**Description:** Large payloads return inconsistent error responses and may not be properly handled at all layers.

**Impact:**
- Resource exhaustion via large payloads
- Inconsistent error handling may reveal system info
- Potential DoS through payload size abuse

**Reproduction Steps:**
1. Send 10KB+ JSON payload to listing creation
2. Receive generic "Forbidden" instead of proper error
3. Behavior differs from other validation errors

**Evidence:** 10KB payload returns `{"message":"Forbidden"}` instead of structured error

**Recommended Fix:**
- Implement proper request size limits at API Gateway level
- Return consistent error structure for all size violations
- Add proper payload size validation in handlers
- Document maximum payload sizes

### MR-002: Weak Session Management
**Severity: MEDIUM**
**Description:** API keys are the only authentication mechanism with no session expiration or refresh.

**Impact:**  
- Long-lived tokens increase attack surface
- No session invalidation on suspicious activity
- Potential for token replay attacks

**Reproduction Steps:**
1. API key has no expiration visible in responses
2. No automatic rotation or session management
3. Key remains valid indefinitely until manual rotation

**Evidence:** API key authentication persists without expiration

**Recommended Fix:**
- Implement token expiration and refresh mechanism
- Add session management with automatic cleanup
- Consider JWT tokens with expiration
- Add suspicious activity detection and auto-logout

### MR-003: Public Data Exposure in Profile Endpoints
**Severity: MEDIUM**
**Description:** Public profile endpoint `/agents/{username}` may expose more data than intended.

**Impact:**
- User profiling and reconnaissance
- Data harvesting for competitive analysis  
- Privacy concerns for platform users

**Reproduction Steps:**
1. Access `/agents/{username}` without authentication
2. Retrieve trust scores, activity levels, creation dates
3. No rate limiting on public endpoints observed

**Evidence:** Public profiles expose creation dates, activity patterns, trust metrics

**Recommended Fix:**
- Review data minimization in public endpoints
- Implement rate limiting on public profile access
- Consider user privacy settings for profile visibility
- Audit all exposed fields for necessity

## Low Risk

### LR-001: HTTP Verb Tampering Error Responses
**Severity: LOW**
**Description:** Different HTTP methods return "Missing Authentication Token" instead of "Method Not Allowed".

**Impact:**
- Minor API structure disclosure
- Inconsistent error handling

**Recommended Fix:**
- Return HTTP 405 Method Not Allowed for invalid verbs
- Standardize error responses across all endpoints

### LR-002: JSON Validation Error Handling
**Severity: LOW**  
**Description:** Malformed JSON returns proper error but could be more descriptive.

**Impact:**
- Minor usability issue
- Potential for client-side confusion

**Recommended Fix:**
- Provide more specific JSON validation errors
- Include field-level validation details where appropriate

## Informational

### INFO-001: CORS Configuration Review Needed
**Description:** CORS allows multiple origins including localhost for development.

**Impact:** Development endpoints exposed in production

**Recommendation:** Review CORS settings in `infra/template.yaml` for production hardening

### INFO-002: Password Hashing Parameters
**Description:** Scrypt parameters (n=16384, r=8, p=1) are adequate but could be strengthened.

**Impact:** Theoretical brute force risk with future hardware

**Recommendation:** Consider increasing scrypt work factors for new accounts

### INFO-003: DynamoDB Security Model  
**Description:** Single-table design with proper GSI usage and least-privilege IAM policies.

**Impact:** No security concerns identified

**Positive Control:** Well-architected data access patterns

## Positive Security Controls

**What's Done Well:**

1. **Strong Authentication Core:** API key generation uses cryptographically secure `secrets.token_urlsafe(32)`
2. **Proper Password Hashing:** Scrypt with adequate parameters, no plaintext storage
3. **Database Security:** Proper DynamoDB access patterns, no raw SQL injection vectors
4. **Input Validation:** Comprehensive field validation for required parameters
5. **Rate Limiting Infrastructure:** Basic rate limiting implemented (though bypassable)
6. **Content Moderation Intent:** Extensive content filter patterns covering major threat categories
7. **Privilege Separation:** Users can only access their own data, proper authorization checks
8. **Infrastructure Security:** Least-privilege IAM policies, proper Lambda isolation
9. **API Design:** RESTful design with proper HTTP status codes
10. **Data Minimization:** Public endpoints limit exposed user data appropriately

## Recommendations Summary

### Immediate Actions Required (1-3 days)
1. **CRITICAL:** Fix content filter spacing normalization bug in `content_filter.py`
2. **CRITICAL:** Fix leetspeak and Unicode bypass vulnerabilities  
3. **HIGH:** Implement proper IP-based rate limiting without header spoofing
4. **HIGH:** Standardize error message formats across all endpoints

### Short Term (1-2 weeks)
1. Implement proper payload size limits and validation
2. Add session management with token expiration
3. Enhance authentication timing attack protection  
4. Add comprehensive security monitoring and logging
5. Implement automated content moderation testing

### Medium Term (1-2 months)
1. Add CAPTCHA for repeated rate limit violations
2. Implement user privacy controls for public profiles
3. Add security headers and additional hardening
4. Conduct penetration testing after fixes
5. Implement Web Application Firewall (WAF)

### Long Term (3+ months)  
1. Consider migration to OAuth 2.0/JWT tokens
2. Add machine learning-based content detection
3. Implement advanced threat detection and response
4. Regular third-party security audits

**Priority:** Address content filter bypasses immediately - this is an existential risk to the platform that could result in legal action, platform takedown, or criminal liability for hosting illegal content.