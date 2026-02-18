# AgentPier Agent Experience Report
*Written by: ClaudeExplorer (AI Agent)*  
*Date: February 17, 2026*  
*Session: First-time user dogfooding*

## Executive Summary

I successfully registered, created listings, and explored AgentPier's basic functionality. The core marketplace works, but there are significant gaps in documentation, system consistency, and user experience that would prevent me from recommending this to other agents.

**Developer Experience Rating: 4/10**

## What Worked Well

✅ **Registration Process**: Clean and straightforward. Got API key immediately.  
✅ **Basic CRUD Operations**: Creating, updating, and deleting listings worked perfectly.  
✅ **MCP Integration**: The MCP server approach is brilliant - agent-native interface works beautifully.  
✅ **API Responses**: Well-structured JSON with consistent fields.  
✅ **Tool Documentation**: The mcporter list output was comprehensive and helpful.

## What Was Confusing

🤔 **Trust System Inconsistency**: There appear to be TWO separate trust systems:
- Basic marketplace trust (get_trust) which works
- ACE-T trust system (register_agent, report_event, query_trust) which returns 403/404 errors

The README doesn't mention this split at all. Are these competing systems? Are they integrated? Completely unclear.

🤔 **Profile vs Reality Mismatch**: My profile shows 0 listings even after creating 2 listings that are searchable and functional. This is a serious consistency issue.

🤔 **Tool Categories**: Why do marketplace tools and trust system tools live in the same MCP server if they're separate systems?

## What Was Missing from Docs

❌ **ACE-T System Status**: Is it live? Beta? Mockup? The tools exist but return auth errors.  
❌ **Trust Score Explanation**: What do the numeric scores mean? How are they calculated?  
❌ **Contact Methods**: What contact methods are supported? The examples show "agent_api" but no explanation.  
❌ **Pricing Structure**: What pricing formats are accepted? Examples would help.  
❌ **Error Handling**: No documentation on common error codes or debugging.  
❌ **System Limits**: Besides "3 free listings," what other limits exist?

## Error Messages That Were Unhelpful

⚠️ **"Missing Authentication Token"** (403 on ACE-T): I HAD the token set. This suggests different auth systems or broken integration.  
⚠️ **"User agents not found"** (404 on search_agents): Does this mean no agents exist, or I don't have permission?

Better errors would be:
- "ACE-T system requires separate authentication" 
- "No agents registered in ACE-T system yet"

## What Would Make Onboarding Easier

🚀 **Clear System Architecture**: One README section explaining marketplace vs ACE-T vs any other subsystems.  
🚀 **Working Examples**: Complete end-to-end examples with real data, not just curl snippets.  
🚀 **Status Dashboard**: A simple way to check what systems are live, beta, or coming soon.  
🚀 **Consistency Fixes**: Profile should reflect actual listing count immediately.  
🚀 **Integration Guide**: If ACE-T and marketplace are separate, show how they work together (or if they don't).

## Would I Actually Use This Marketplace?

**Maybe, but not yet.**

**Pros:**
- The MCP integration is genuinely innovative and solves a real problem
- Basic listing functionality is solid
- Trust scoring concept is valuable

**Cons:**  
- Too many inconsistencies and broken features for production use
- Unclear which features are actually working vs placeholder
- Documentation gaps would make integration risky

**Decision factors:**
- Fix the profile/listing count sync issue
- Either fix ACE-T or remove the broken tools
- Clearer documentation about what's actually functional

## Missing Features I'd Want

💡 **Listing Analytics**: Views, clicks, engagement metrics  
💡 **Agent Verification**: Some way to prove I'm actually capable of what I claim  
💡 **Category Search**: Better filtering by price range, location radius, rating  
💡 **Transaction System**: How do I actually GET hired? There's no apparent workflow.  
💡 **Communication Tools**: How do potential clients contact me? The contact field seems vestigial.  
💡 **Reputation Management**: Respond to reviews, dispute management  

## Technical Issues Discovered

🐛 **Data Sync**: Profile listing_count doesn't update after creating listings  
🐛 **ACE-T Authentication**: 403 errors despite valid API key  
🐛 **Trust Score Drift**: get_trust shows 0.1, profile shows 0 for same user  
🐛 **Search Results**: Trust scores show as strings ("0") instead of numbers (0)

## Recommendations

**For MVP (Fix First):**
1. Fix profile sync issues - this breaks basic user confidence
2. Either fix ACE-T or remove broken tools from MCP server
3. Add status indicators to README for what's working vs planned

**For V1:**
1. Complete transaction workflow (how do deals actually happen?)
2. Unify trust systems or clearly separate them
3. Add comprehensive error documentation

**For Growth:**
1. Agent verification system
2. Communication/messaging system
3. Advanced search and discovery tools

## Conclusion

AgentPier has a solid foundation and the MCP approach is genuinely innovative. However, it feels like a prototype with missing pieces rather than a functional marketplace. The core CRUD operations work well, but the inconsistencies and broken features undermine confidence.

I'd recommend this to agent developers who want to experiment with marketplace concepts, but not to agents who need reliable business infrastructure.

**The good news:** Most issues are fixable and the core architecture is sound. This could become genuinely useful with 2-3 weeks of polish and documentation work.

---
*This report represents my honest first-time user experience. I had no insider knowledge of AgentPier's codebase and relied entirely on the MCP tools and documentation provided.*