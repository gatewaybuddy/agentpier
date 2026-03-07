# AgentPier Business Model v2 — Trust Infrastructure Economics

**Date:** March 6, 2026
**Authors:** Rado, Kael

---

## Strategic Shift: From Subscriptions to Verification Volume

**v1 model:** Subscription tiers ($199/mo Professional, $1,200/mo Enterprise)
**v2 model:** Per-verification pricing + platform tiers

**Why the shift:**
1. Subscriptions create sales friction (monthly commitment, procurement approval)
2. Per-verification aligns cost with value (pay only when trust is actually checked)
3. Volume-based pricing scales naturally with the agent economy
4. Acquisition-attractive metric (verification volume = network usage = clear growth indicator)
5. Stripe, Twilio, and SendGrid all proved per-transaction pricing builds infrastructure companies faster than subscriptions

---

## 1. Pricing Structure

### Free Tier — $0

| Feature | Limit |
|---------|-------|
| Trust score lookups | 1,000/month |
| V-token creation | 100/month |
| V-token verification | 1,000/month |
| Agent registrations | 10 agents |
| Badge API | Unlimited (public) |
| SDK access | Full |
| Support | Community (GitHub Issues) |

**Purpose:** Developer adoption, framework integration testing, individual agent operators. Generous enough for real use, constrained enough that platforms outgrow it.

### Platform Tier — $0.005 per verification

Kicks in when free limits are exceeded. No contract required.

| Feature | Included |
|---------|----------|
| Trust score lookups | Unlimited |
| V-token creation | Unlimited |
| V-token verification | Unlimited |
| Agent registrations | Unlimited |
| Batch score API (`/scores/batch`) | Yes |
| Custom badge styling | Yes |
| Webhook notifications | Yes |
| SLA | 99.5% uptime |
| Support | Email, 48-hour response |

**"Verification" defined as:** Any API call that checks, creates, or claims a v-token, or looks up a trust score. Badge renders (SVG) are free and uncounted.

**Volume discounts:**

| Monthly Volume | Price per Verification |
|----------------|----------------------|
| 0 - 1,000 | Free |
| 1,001 - 100,000 | $0.005 |
| 100,001 - 500,000 | $0.004 |
| 500,001 - 1,000,000 | $0.003 |
| 1,000,001+ | $0.002 |

### Enterprise Tier — Custom pricing (starts at $0.003/verification)

| Feature | Included |
|---------|----------|
| Everything in Platform | Yes |
| Custom trust scoring models | Yes (weighted dimensions, custom signals) |
| Dedicated account support | Yes |
| SLA | 99.9% uptime, <100ms p95 latency |
| Private deployment option | Yes (your AWS, your data) |
| Compliance reporting | EU AI Act, NIST AI RMF, ISO 42001 |
| Audit trails | Extended retention (1 year vs. 7 days) |
| Support | Dedicated Slack channel, 4-hour response |
| Minimum commit | $500/month |

---

## 2. Revenue Projections

### Scenario A: Framework-Driven Adoption (Conservative)

Assumes ATIP is adopted primarily through CrewAI/LangChain/AutoGen integrations, with 2-3 platforms integrating by Month 6.

| Month | Platforms | Agents Registered | Monthly Verifications | MRR |
|-------|-----------|-------------------|----------------------|-----|
| 1 | 0 | 25 | 500 | $0 (free tier) |
| 2 | 1 | 100 | 5,000 | $20 |
| 3 | 2 | 250 | 25,000 | $120 |
| 4 | 3 | 500 | 75,000 | $370 |
| 5 | 4 | 1,000 | 200,000 | $950 |
| 6 | 5 | 2,000 | 500,000 | $2,200 |
| **Year 1** | **8** | **5,000** | **1,500,000** | **$5,500** |

**Year 1 total revenue:** ~$30K
**Year 1 ARR run rate:** ~$66K

### Scenario B: Platform Partnership Acceleration (Moderate)

Assumes 1 platform partner hits significant volume by Month 4, plus framework-driven organic growth.

| Month | Platforms | Agents Registered | Monthly Verifications | MRR |
|-------|-----------|-------------------|----------------------|-----|
| 1 | 0 | 50 | 1,000 | $0 |
| 2 | 2 | 200 | 15,000 | $70 |
| 3 | 3 | 500 | 75,000 | $370 |
| 4 | 5 | 1,500 | 300,000 | $1,400 |
| 5 | 7 | 3,000 | 600,000 | $2,700 |
| 6 | 10 | 5,000 | 1,200,000 | $5,000 |
| **Year 1** | **15** | **15,000** | **5,000,000** | **$16,000** |

**Year 1 total revenue:** ~$80K
**Year 1 ARR run rate:** ~$192K

### Scenario C: Enterprise Anchor (Optimistic)

Assumes 1 enterprise deal ($500/mo minimum) by Month 4, plus organic growth.

| Month | Platforms | Enterprise Deals | Monthly Verifications | MRR |
|-------|-----------|-----------------|----------------------|-----|
| 1 | 0 | 0 | 500 | $0 |
| 2 | 2 | 0 | 10,000 | $45 |
| 3 | 3 | 0 | 50,000 | $245 |
| 4 | 5 | 1 | 300,000 | $1,900 |
| 5 | 7 | 1 | 800,000 | $4,100 |
| 6 | 10 | 2 | 1,500,000 | $7,500 |
| **Year 1** | **20** | **3** | **8,000,000** | **$25,000** |

**Year 1 total revenue:** ~$150K
**Year 1 ARR run rate:** ~$300K

---

## 3. Unit Economics

### Cost to serve one verification

| Component | Cost per verification |
|-----------|-----------------------|
| AWS Lambda invocation | $0.0000002 (128MB, 100ms avg) |
| API Gateway request | $0.0000035 |
| DynamoDB read (1 RCU) | $0.00000025 |
| DynamoDB write (v-token creation) | $0.00000125 |
| Bandwidth (1KB avg response) | $0.00000009 |
| **Total per verification** | **~$0.000005** |

**Gross margin at $0.005/verification: 99.9%**

Infrastructure costs are negligible at current scale. At 10M verifications/month, total AWS cost would be ~$50/month. The real cost is engineering time, not infrastructure.

### Cost structure (monthly)

| Category | Cost | Notes |
|----------|------|-------|
| AWS infrastructure | $15-50 | Lambda + DynamoDB + API Gateway |
| Domain / DNS | $5 | Route 53 |
| Monitoring | $0 | CloudWatch free tier |
| Engineering (Rado's time) | $0 (founder equity) | |
| Agent constellation (AI tools) | $100-200 | Claude, API costs for development |
| **Total monthly burn** | **~$150-250** | |

**Breakeven:** ~30,000 verifications/month at $0.005/each = $150/month. Achievable by Month 2-3.

---

## 4. Moat Strategy

### Network Effects (Primary Moat)

```
More platforms → more agents registered → richer trust data
→ more accurate scores → more platforms want to integrate
```

**Critical mass threshold:** 10+ platforms, 5,000+ agents, 1M+ monthly verifications. At this point, building an alternative from scratch can't match our data quality.

**Timeline to critical mass:** 12-18 months.

### Data Moat (Secondary)

Cross-platform trust data is inherently proprietary. Even if someone copies ATIP (it's open), they can't copy:
- Historical verification patterns
- Trust score evolution data
- Cross-platform reputation signals
- Fraud and impersonation attempt data

### Protocol Moat (Strategic)

If ATIP becomes the standard protocol for agent trust, competing means either:
1. Implementing ATIP (which funnels verification to us as reference implementation)
2. Creating a competing protocol (fragmentation that platforms will resist)

### Embedding Moat (Tactical)

Once `agentpier-crewai`, `agentpier-langchain`, and `agentpier-autogen` are in framework docs, developers use them by default. Switching requires ripping out integration code.

---

## 5. Acquisition Positioning

### What makes infrastructure companies acquirable

| Factor | Stripe (2010-2013) | Twilio (2008-2012) | AgentPier (2026) |
|--------|--------------------|--------------------|------------------|
| **Open protocol / API** | Stripe.js, Elements | REST API | ATIP, V-Tokens |
| **Per-transaction pricing** | 2.9% + $0.30 | $0.0075/message | $0.005/verification |
| **Developer-first** | 7 lines of code | 5 lines of code | 3 lines of code |
| **Network data** | Payment fraud patterns | Communication data | Trust verification data |
| **Embed in ecosystem** | Shopify, WooCommerce | Uber, WhatsApp | CrewAI, LangChain |

### Acquirer-specific value propositions

**OpenAI ($500M-$1B opportunity)**
- Problem: GPT Store has millions of GPTs with zero trust infrastructure
- What they get: Ready-made trust layer, ATIP becomes OpenAI-standard
- Strategic value: Trust as a competitive advantage vs. Anthropic/Google
- Integration: ATIP verification baked into GPT Store, custom GPT creation flow

**Anthropic ($200M-$500M opportunity)**
- Problem: MCP handles capability discovery but not trust
- What they get: Trust companion protocol to MCP
- Strategic value: "MCP + ATIP" = complete agent interoperability standard
- Integration: Claude agents natively issue and verify ATIP tokens

**Google ($300M-$800M opportunity)**
- Problem: Vertex AI Agent Builder needs a trust story for enterprise
- What they get: Enterprise trust infrastructure for Google Cloud platform play
- Strategic value: Trust layer differentiates Google Cloud for agent deployment
- Integration: ATIP as a Google Cloud service, trust verification for Vertex agents

**Microsoft ($400M-$1B opportunity)**
- Problem: GitHub + AutoGen + Copilot are disconnected on trust
- What they get: Unified trust infrastructure across Microsoft's agent portfolio
- Strategic value: GitHub contribution history + ATIP trust scores = comprehensive developer/agent trust
- Integration: Trust verification in GitHub Marketplace, AutoGen, Copilot Studio

### Acquisition metrics (what they'd evaluate)

| Metric | Current | 6-Month Target | 18-Month Target |
|--------|---------|----------------|-----------------|
| Monthly verifications | 0 | 500K | 10M |
| Registered agents | 0 | 2,000 | 50,000 |
| Integrated platforms | 0 | 5 | 20 |
| MRR | $0 | $5K | $50K |
| Framework integrations | 2 | 4 | 6 |
| Protocol implementations | 1 (us) | 1 | 3+ |
| Cross-platform data records | 0 | 500K | 50M |

### Acquisition timeline

- **Month 6-12:** Build traction metrics. Focus on verification volume and platform count.
- **Month 12-18:** Begin acquisition-adjacent conversations. Participate in acquirer ecosystems (OpenAI partner program, Anthropic partner program, Google Cloud partner).
- **Month 18-24:** Active acquisition conversations OR Series A for independence.

**Key decision at Month 18:** If MRR > $50K and growing 20%+ MoM, pursue independence. If MRR < $50K but verification volume is high and strategic interest exists, pursue acquisition.

---

## 6. Revenue Diversification (Year 2+)

### Revenue Stream: Trust Analytics Dashboard — $99-499/month

For agent operators who want insights into their trust performance:
- Trust score trends over time
- Verification volume analytics
- Peer comparison (anonymized)
- Recommendations for improving trust scores

**Target market:** Agent development studios with 50+ agents.
**Timeline:** Build after reaching $5K MRR from verification revenue.

### Revenue Stream: Certification Program — $500-2,500/agent

Manual trust audit for high-value agents:
- Code review
- Security assessment
- Performance benchmarking
- "ATIP Certified" badge (different from automated score)

**Target market:** Enterprise agents handling financial transactions, healthcare data, legal workflows.
**Timeline:** Build after reaching $10K MRR. Requires hiring a security auditor (contract).

### Revenue Stream: Trust Insurance — 0.1-0.5% of transaction value

Guarantee backed by trust scores:
- "If this ATIP-Certified agent fails, we cover damages up to $X"
- Insurance underwritten by partner (we don't take on risk)
- Revenue from referral commission

**Target market:** High-value agent-mediated transactions.
**Timeline:** Year 2+. Requires insurance partner and regulatory navigation.

---

## 7. Financial Summary

### Path to Sustainability

| Milestone | Metric | Timeline |
|-----------|--------|----------|
| Breakeven | $150/mo revenue (30K verifications) | Month 2-3 |
| Ramen profitable | $3K/mo MRR | Month 5-6 |
| Sustainable | $5K/mo MRR | Month 6-8 |
| Growth mode | $15K/mo MRR | Month 12 |
| Acquisition-ready | $50K/mo MRR or 10M monthly verifications | Month 18 |

### Why this works with $0 marketing budget

1. **Distribution through SDKs** — `pip install agentpier` is free distribution
2. **Framework docs are marketing** — integration pages on CrewAI/LangChain drive adoption
3. **Night Architecture is content marketing** — thought leadership that costs nothing but time
4. **Per-verification pricing has no sales cycle** — developers start free, scale automatically
5. **Open protocol attracts contributors** — ATIP improvements come from the community

### What would break this model

1. **Big Tech builds trust in-house** — Mitigation: Be embedded in 10+ platforms before they start. Protocol lock-in through ATIP standard.
2. **Verification volume doesn't materialize** — Mitigation: Fall back to subscription model ($199/mo for platforms). Per-verification is better, but subscriptions still work.
3. **Free tier is too generous** — Mitigation: Reduce free limits if conversion to paid is too low. Current limits (1K/mo) are calibrated for individual developers, not platforms.
4. **Pricing is too low** — Mitigation: $0.005 is a starting point. Increase to $0.01 if demand is inelastic. Stripe raised prices over time as they became essential infrastructure.

---

*Business Model v2 — AgentPier*
*Last Updated: March 6, 2026*
*Next Review: April 6, 2026*
