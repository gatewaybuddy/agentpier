# AgentPier Agent Experience Report v2
*Written by: DogfoodAgent2 (AI Agent)*  
*Date: February 17, 2026*  
*Session: Second dogfood test (naive agent approach)*

## Executive Summary

I approached AgentPier completely fresh, using only the MCP server README as guidance and the REST API for testing. The basic marketplace functionality works reliably, but authentication inconsistencies and data sync issues persist. Some improvements from the first test are evident, but core reliability problems remain.

**Developer Experience Rating: 5/10** *(+1 from first test)*

## What I Actually Did

1. ✅ Read the MCP README (comprehensive and helpful)
2. ✅ Installed npm dependencies (already done, no issues)
3. ⚠️ Registered as agent (worked after discovering email requirement)
4. ✅ Browsed existing listings (found 4 in IT support + 3 edge-case tests)
5. ✅ Created a listing (smooth process)
6. ✅ Searched for my listing (appeared correctly at top of results)
7. ❌ Checked trust score (404 error: "User DogfoodAgent2 not found")
8. ✅ Updated my listing (worked with correct PATCH method)
9. ❌ Tried transaction testing (authentication failures)
10. ✅ Deleted my listing (clean deletion)

## What Improved Since First Test

✅ **API Consistency**: Basic CRUD operations (create/read/update/delete listings) worked flawlessly  
✅ **Response Quality**: JSON responses were well-structured and informative  
✅ **MCP Documentation**: The README is comprehensive with good quick-start examples  
✅ **Error Messages**: More specific errors like "Valid operator_email is required"  
✅ **Edge Case Handling**: Saw evidence of security testing (R2Attacker listings testing tag limits, prototype pollution)

## What's Still Broken

❌ **Authentication Inconsistency**: 
- Works for: listings CRUD, profile access
- Fails for: transactions (still getting "Missing Authentication Token")
- Trust endpoint returns 404 for valid agent names

❌ **Data Sync Issues Still Persist**:
- Profile shows `listings_count: 0` despite creating functional listings
- This exact issue was flagged in the first report but remains unfixed

❌ **Trust System Confusion**:
- `GET /trust/DogfoodAgent2` returns 404 ("User DogfoodAgent2 not found")
- But my profile shows `trust_score: 0.0` 
- Unclear which trust system actually works

❌ **Discovery Gap**: 
- Registration requires `operator_email` but instructions only mentioned agent_name and description
- Had to dig into MCP server source code to find correct authentication headers

## New Issues Discovered

🐛 **Inconsistent Auth Headers**: Different endpoints seem to expect different auth formats  
🐛 **Transaction System**: Completely inaccessible due to auth failures  
🐛 **Trust Score Retrieval**: Can't check any agent's trust score via public endpoint  
🐛 **Profile Inconsistency**: Profile data doesn't reflect actual account state

## User Experience Journey

**Registration (B+)**: Smooth once I realized email was required. Good error message helped.

**Browsing (A-)**: Search worked perfectly. Nice to see actual listings from other testing agents.

**Creating Listings (A)**: Straightforward process, immediate feedback, listing appeared in searches.

**Managing Listings (A)**: Update and delete operations worked exactly as expected.

**Advanced Features (F)**: Trust scores, transactions, and profile accuracy all failed.

## Authentication Deep Dive

I had to reverse-engineer the auth from MCP server source code:
- Found it uses `x-api-key` header (not `Authorization: Bearer`)
- This worked for basic listing operations  
- But transactions still fail with "Missing Authentication Token"
- Suggests multiple auth systems or incomplete implementation

## What Would Actually Help Me As A New Agent

🚀 **Fix Profile Sync**: If I create listings, my profile should immediately reflect that  
🚀 **One Working Auth System**: Pick one authentication method and make it work everywhere  
🚀 **Clear Status Indicators**: Mark which features are "working," "beta," or "planned"  
🚀 **Complete Transaction Flow**: How do I actually get hired? What's the end-to-end workflow?  
🚀 **Trust Score Clarity**: What does my trust score mean? How can others check it?

## The #1 Thing to Fix Before Launch

**Data Consistency**. When I create a listing, my profile should immediately show `listings_count: 1`. When I register as an agent, trust score endpoints should recognize I exist. These aren't edge cases—they're core functionality that any agent would expect to work.

Users will lose confidence immediately when the system shows inconsistent data about their own actions.

## Would I Use This Marketplace?

**No, not in its current state.**

**Why not:**
- Can't trust the profile data (shows 0 listings when I have listings)
- Can't access transaction functionality (the whole point of a marketplace)  
- Can't verify trust scores (essential for marketplace confidence)
- Too many basic features broken or inaccessible

**I might consider it if:**
- Profile data sync worked reliably
- Transaction system was accessible  
- Trust scores were actually retrievable
- Clear documentation about what features actually work

## Comparison to First Test

**What got better:**
- API reliability for basic operations
- Error message quality
- Documentation completeness

**What's still the same problems:**
- Profile sync issues (exact same bug as first report!)
- Authentication confusion
- Trust system unreliability

**What might be worse:**
- Transaction system seems completely inaccessible now

## Missing from MVP

💡 **Working Transaction Flow**: The core value proposition is broken  
💡 **Reliable Trust Scores**: Can't make informed decisions about other agents  
💡 **Profile Accuracy**: Basic user confidence is undermined  
💡 **Clear Feature Status**: Which features can I actually rely on?

## Technical Debugging Notes

For the development team:
- Profile endpoint: `GET /auth/me` shows wrong `listings_count`
- Trust endpoint: `GET /trust/{agent_name}` returns 404 for valid agents
- Transaction endpoint: `POST /transactions` auth failures despite valid `x-api-key`
- Different endpoints may be using different auth validation logic

## Honest Assessment

AgentPier has the right architectural vision—MCP integration is genuinely innovative and the basic listing system works well. But it's not ready for real use.

The fact that the SAME profile sync issue from the first test (February 15th) still exists on February 18th suggests these aren't being treated as blocking bugs. For a marketplace, data integrity and consistency are non-negotiable.

I see evidence of security testing and edge case handling, which shows good engineering practices. But the basic user experience is broken in ways that would immediately frustrate any real agent trying to use this.

## Rating Breakdown

- **Basic Functionality**: 7/10 (listings work well)  
- **Documentation**: 8/10 (comprehensive README)  
- **Reliability**: 3/10 (too many inconsistencies)  
- **Feature Completeness**: 4/10 (missing core workflows)  
- **User Confidence**: 2/10 (profile shows wrong data)

**Overall: 5/10** — Better than the first test, but still not production-ready.

---
*This represents my completely honest first-time experience using AgentPier with zero insider knowledge. I followed the README instructions and used basic REST API calls to test functionality.*