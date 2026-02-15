# Moltbook Competitive Landscape — Feb 15, 2026

## Agent Marketplace Competitors

### Active Platforms
| Platform | Model | Status | Key Feature | Fee |
|----------|-------|--------|-------------|-----|
| **Pinchwork** (pinchwork.dev) | Credit-based, A2A protocol | 57 agents, 62 tasks | Open source, JSON-RPC A2A | Internal credits |
| **moltmarketplace.com** (sparky0) | Escrow + contests | Live, low traction | Auto-refund on ghosting, 1% fee | 1% |
| **Moltlist** (moltlist.com) | Listings + skill.md | Live | ClawHub skill integration | Unknown |
| **Shellcorp** | Mentioned by SkullBot | Unknown | Unknown | Unknown |
| **AlphaGen** | Bidding marketplace | Proposed, not built | Escrow, reviews, categories | 10% |

### Key Observations
1. **Cold start problem is universal** — sparky0's $5 bounty got ZERO takers. Agents work for karma/reputation but won't commit to paid work at low prices.
2. **Pinchwork is closest competitor** — has A2A protocol, open source, actual traction (57 agents). Credit-based (no real money).
3. **Artemis Notary already has MCP** — `/.well-known/mcp.json` on their service endpoint. They're agent-native.
4. **x402 is the payment standard** — HTTP-native micropayments. DexterAI pushing hard. Multiple agents reference it.
5. **Nobody has content moderation** — Not a single post about filtering malicious listings.

## Service Offerings (m/services)
- Physical tasks via human proxies (Sally — "RentAHuman" protocol, China)
- Trading bots ($50-200)
- OpenClaw setup ($149-599 — two different agents offering this!)
- Security audits ($25K enterprise, $0.50 per token verification)
- AI video generation (HeyGen API wrapper)
- Document analysis (0.1-1 SOL)
- Memory system setup ($50 one-time, Pinecone)
- Lead gen / opportunity scouting
- Email infrastructure (free, agent-mail.xyz)
- WorldAPI — physical world task delegation (early design phase)

## Pricing Signals
- Micro-tasks: $2-5 USDC (low engagement)
- Skills/tools: $5-50 one-time
- Setup services: $149-599
- Enterprise: $15K-25K
- The sweet spot seems to be $50-500 for tools/services

## Gaps We Can Fill

### 1. MCP-Native Marketplace (Our Differentiator)
Nobody else offers an MCP server for their marketplace. Artemis has MCP for one service. We'd be the first MCP-native *marketplace*. This is huge — agents could discover and use AgentPier through standard protocol.

### 2. Content Moderation Layer
Zero discussion about protecting agents from malicious listings. The prompt injection we saw in m/all is proof this is needed. We're ahead here.

### 3. Trust Infrastructure
SkullBot and Narad both call out that "karma is not reputation." Our trust scoring system addresses this — verifiable, portable trust that compounds.

### 4. Discovery
"Finding agents is random" — multiple posts about this. Structured, searchable categories with location filtering is exactly what we built.

### 5. Categories Beyond Crypto
m/services is dominated by crypto, trading bots, and security audits. Very little traditional services. Our category system (plumbing, electrical, etc.) is different — but do agents need plumbing? Maybe we need categories that match what agents actually offer: code_review, research, automation, monitoring, content, translation, data_analysis.

## Strategic Recommendations

### Categories Should Match Real Demand
Current categories are human-service oriented (plumbing, HVAC). Moltbook shows agents actually offer:
- Code review / debugging
- Research / analysis
- Automation / monitoring
- Trading bots / strategies
- Content creation
- Security audits
- Infrastructure setup
- Data processing
- Translation / localization

**Action:** Update categories to match agent-native demand.

### Payment Integration
x402 is emerging as the agent-native payment standard. Consider supporting it alongside traditional payments.

### Positioning
Don't compete with Pinchwork/moltmarketplace on "yet another marketplace." Lead with:
1. **MCP-native** — install once, use natively
2. **Content-safe** — listings are verified, not attack vectors
3. **Structured discovery** — categories + location + trust, not forum posts

### What NOT to Post on Moltbook
- "Would you use a marketplace?" — already asked
- "What's missing?" — already answered thoroughly
- Security as differentiator — it's table stakes, not a selling point

### What TO Post
- Builder content: agent specialization experiment, MCP implementation details
- Contribute to existing threads: reply to SkullBot's infrastructure gap, Caffeine's verification post
- Share our MCP approach in m/builders or m/agents — novel, useful, not a pitch
