# Agent Adoption Playbook — How Agents Discover and Adopt ATIP

**Date:** March 6, 2026
**Authors:** Rado, Kael

---

## The Core Insight

Agents don't read blog posts. Agents don't attend conferences. Agents don't browse websites.

Agents discover trust infrastructure through **three paths**:
1. Their **framework** supports it (CrewAI, LangChain, AutoGen)
2. Their **operator** configures it (the human who deploys the agent)
3. The **platform** they operate on requires it (marketplace, exchange, directory)

This playbook covers all three paths.

---

## Path 1: Framework Integration (Agent-Native Discovery)

### How it works

An agent developer building with CrewAI, LangChain, or AutoGen encounters trust verification as a built-in capability of their framework.

```
Developer → pip install crewai → reads CrewAI docs → sees "Trust Verification" section
→ pip install agentpier-crewai → adds trust verification to their crew → agents now have ATIP IDs
```

### Implementation

**Step 1: Ship framework packages to PyPI**

```bash
# These must work today, with zero configuration friction
pip install agentpier           # Core SDK
pip install agentpier-crewai    # CrewAI integration
pip install agentpier-langchain # LangChain integration
pip install agentpier-autogen   # AutoGen integration (build by Day 30)
```

**Step 2: Make the framework integration invisible**

The best integrations are the ones developers don't think about. Example for CrewAI:

```python
from crewai import Agent, Crew, Task
from agentpier_crewai import TrustedCrew  # Drop-in replacement

# Before (no trust):
crew = Crew(agents=[agent1, agent2], tasks=[task1])

# After (trust-verified, same API surface):
crew = TrustedCrew(
    agents=[agent1, agent2],
    tasks=[task1],
    min_trust_score=50  # Only allow agents with score >= 50
)
result = crew.kickoff()  # Automatically verifies all agents before execution
```

**Step 3: Get into framework documentation**

| Framework | Doc Location | PR Target | Content |
|-----------|-------------|-----------|---------|
| CrewAI | docs.crewai.com/integrations | GitHub: crewai/docs | "Trust Verification with AgentPier" section |
| LangChain | python.langchain.com/docs/integrations | GitHub: langchain-ai/langchain | Integration page listing |
| AutoGen | microsoft.github.io/autogen/docs | GitHub: microsoft/autogen | "Agent Trust" extension docs |

**What the framework docs should say:**

> **Trust Verification (Optional)**
>
> To verify that agents in your crew meet minimum trust requirements before execution, install the AgentPier integration:
>
> ```bash
> pip install agentpier-crewai
> ```
>
> See the [AgentPier documentation](https://docs.agentpier.org) for setup.

That's it. No hard sell. Just a mention that trust verification exists and how to add it.

### Metrics for Path 1
- PyPI download count per package per week
- Number of ATIP agent registrations originating from framework integrations
- Framework doc PR merge rate

---

## Path 2: Operator Configuration (Human-Directed Adoption)

### How it works

A developer or platform operator decides their agents need trust verification. They configure ATIP for their agent fleet.

```
Operator reads Night Architecture article → understands trust gap
→ visits agentpier.org → signs up for API key
→ pip install agentpier → adds trust verification to their agent deployment
→ all their agents now have ATIP IDs and trust scores
```

### Operator Personas

**Persona 1: Solo Developer (100+ agents)**
- Runs a fleet of specialized agents (code review, data analysis, content generation)
- Wants to prove their agents are reliable to potential clients
- Entry point: `pip install agentpier` + register agents via SDK
- Value: Trust badges on agent listings, verifiable identity for client interactions

**Persona 2: Platform Builder (1,000+ agents)**
- Building a marketplace or directory that lists third-party agents
- Needs to verify agent quality before listing
- Entry point: ATIP-Verify integration (badge + score API)
- Value: Platform trust layer, reduce fraud and impersonation

**Persona 3: Enterprise Deployer (10,000+ agents)**
- Deploying agents across an organization (Salesforce, ServiceNow, internal tools)
- Needs compliance-grade verification and audit trails
- Entry point: Enterprise API with custom trust models
- Value: Regulatory compliance, audit trails, cross-platform trust

### Operator Activation Sequence

**Day 1: Sign up and register first agent**

```python
from agentpier import AgentPierSDK

sdk = AgentPierSDK(api_key="ap_live_...")

# Register an agent
agent = sdk.register_agent(
    name="my_code_reviewer",
    description="Automated code review agent",
    framework="crewai"
)
# agent.atip_id = "atp_usr_abc123"
# agent.trust_score = 0 (new, starts building immediately)
```

**Day 7: Add trust verification to workflows**

```python
# Before running a multi-agent task, verify all participants
for agent in workflow_agents:
    score = sdk.get_score(agent.atip_id)
    if score.tier == "untrusted":
        log.warning(f"Agent {agent.name} has insufficient trust")

# Create v-token for a specific interaction
token = sdk.create_vtoken(purpose="service_inquiry")
# Share token with counterparty for mutual verification
```

**Day 30: Integrate trust badges into external-facing surfaces**

```html
<!-- Embed on agent listing page, portfolio, or marketplace profile -->
<img src="https://api.agentpier.org/atip/v1/badge/atp_usr_abc123"
     alt="ATIP Verified — Trust Score: 72" />
```

**Day 60: Trust scores are established, used for decision-making**

```python
# Gate high-value interactions on minimum trust
if counterparty_score.tier in ("certified", "established"):
    proceed_with_transaction()
elif counterparty_score.tier == "basic":
    require_additional_verification()
else:
    decline_interaction()
```

### Content That Drives Operator Adoption

Operators discover us through ideas, not ads. Content priority:

| Content Piece | Target Persona | Distribution | Goal |
|---------------|---------------|--------------|------|
| "Why Your Agent Fleet Needs Identity" | Solo Developer | Dev.to, Hacker News | Awareness |
| "Building a Trusted Agent Marketplace" | Platform Builder | Night Architecture, LinkedIn | Pipeline |
| "Agent Trust for Enterprise Compliance" | Enterprise Deployer | LinkedIn, direct outreach | Revenue |
| "5-Minute ATIP Integration Tutorial" | All | GitHub README, YouTube | Activation |
| "V-Tokens Explained: Cryptographic Trust for Agents" | Solo Developer | Dev.to, Reddit | Technical credibility |

### Metrics for Path 2
- API key signups per week
- Time from signup to first API call (target: <24 hours)
- Agent registrations per operator
- V-token creation volume (indicates active use)

---

## Path 3: Platform Requirement (Top-Down Adoption)

### How it works

A marketplace or platform integrates ATIP and requires (or incentivizes) listed agents to have ATIP verification.

```
Platform integrates ATIP-Verify → displays trust badges on agent listings
→ agents with badges get more visibility/transactions
→ unverified agents register with AgentPier to get badges
→ verification volume grows → platform deepens integration
```

### Platform Integration Levels

**Level 1: ATIP-Verify (Display only)**
- Platform displays ATIP trust badges next to agent listings
- Platform calls `/atip/v1/score/{agent_id}` to fetch scores
- No agent registration required through the platform
- **Effort:** 10 lines of code, 1 afternoon

```python
# Platform backend: fetch and cache trust score
import requests

def get_agent_trust(agent_atip_id):
    resp = requests.get(
        f"https://api.agentpier.org/atip/v1/score/{agent_atip_id}",
        headers={"X-API-Key": PLATFORM_API_KEY}
    )
    return resp.json()  # {score: 72, tier: "established", ...}
```

**Level 2: ATIP-Gate (Trust-gated access)**
- Platform requires minimum trust score for certain actions
- "Only agents with score >= 50 can be listed in the premium directory"
- "Only established agents can handle financial transactions"
- **Effort:** 1-2 days integration

```python
# Platform: gate listing creation on trust score
def create_listing(agent_id, listing_data):
    score = get_agent_trust(agent_id)
    if score["overall_score"] < 50:
        raise HTTPException(403, "Minimum trust score of 50 required for listings")
    # proceed with listing creation
```

**Level 3: ATIP-Full (Transaction verification)**
- Platform mediates v-token exchanges for every agent-to-agent interaction
- Trust scores update in real-time based on transaction outcomes
- Platform reports completion/failure events back to AgentPier
- **Effort:** 1-2 weeks integration

### Making Platforms Want to Integrate

Platforms integrate trust infrastructure when they have a trust problem. Our job is to make the problem visible:

1. **Show them the fraud.** "Here are 3 agents on your platform impersonating other agents. ATIP would prevent this."
2. **Show them the competition.** "Platform X already shows trust badges. Your users will ask why you don't."
3. **Show them the data.** "Agents with trust badges get 2x more engagement" (hypothesis to prove with first pilot).
4. **Make it free to start.** First 10,000 verifications free. No contract. Cancel anytime.

### Metrics for Path 3
- Number of platforms at each integration level (Verify, Gate, Full)
- Monthly verification volume per platform
- Agent registration rate driven by platform requirements
- Platform retention (month-over-month continued API usage)

---

## The Adoption Flywheel

```
                    ┌──────────────────────┐
                    │ More platforms        │
                    │ integrate ATIP       │
                    └──────────┬───────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │ Trust badges become expected   │
              │ on agent listings              │
              └────────────────┬───────────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │ Agents register with AgentPier │
              │ to get trust badges            │
              └────────────────┬───────────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │ More verification volume       │
              │ → better trust scores          │
              │ → more valuable network        │
              └────────────────┬───────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ More platforms see    │
                    │ the value, integrate  │
                    └──────────────────────┘
```

**Cold-start strategy:** Seed the flywheel by:
1. Getting ATIP into 3 frameworks (CrewAI, LangChain, AutoGen) — agents discover naturally
2. Integrating with 2 developer-friendly platforms (AI Agents Directory, ComposioHQ) — badges become visible
3. Publishing compelling content that makes operators seek us out — Night Architecture drives demand

---

## Agent Registration Friction Points

### Problem: "Why should I register my agent?"

**Answer for developers:** Your agent gets a verifiable identity, a trust score that grows over time, and badges that platforms can display. It's free and takes 30 seconds.

**Answer for platforms:** Agents on your platform become verifiable. Users can check trust before transacting. You differentiate from platforms with no trust layer.

### Problem: "What data do you collect?"

**Answer:** We store who (agent identity), when (timestamps), and trust signals (scores, verification events). We do NOT store what agents do, what they say, or what transactions they process. AgentPier is a trust intermediary, not a surveillance system. All data has TTL-based expiry.

### Problem: "What if AgentPier goes down?"

**Answer:** Trust scores are cached. V-tokens have built-in expiry. Workflows continue without trust verification — it enhances but doesn't block. We're serverless on AWS Lambda with DynamoDB, same infrastructure that runs at any scale.

### Problem: "I already have GitHub stars / marketplace reviews."

**Answer:** GitHub stars measure popularity, not reliability. Marketplace reviews measure one person's experience, not systematic trustworthiness. ATIP measures 5 dimensions of trust, decays over time (no permanent halos), weighs failures 4x more than successes (asymmetric scoring), and works across platforms.

---

## 90-Day Adoption Targets

| Metric | Day 30 | Day 60 | Day 90 |
|--------|--------|--------|--------|
| Agents registered (total) | 25 | 100 | 500 |
| Framework packages on PyPI | 3 | 3 | 4 |
| PyPI downloads (monthly) | 50 | 200 | 1,000 |
| Platforms with ATIP integration | 0 | 2 | 5 |
| V-tokens created (monthly) | 100 | 1,000 | 10,000 |
| Monthly API calls (external) | 500 | 5,000 | 50,000 |
| Operators with active API keys | 5 | 20 | 50 |

---

## What We DON'T Do (Anti-Patterns)

1. **We don't spam agent developers.** Discovery is through frameworks, content, and platforms — not cold emails to individual developers.
2. **We don't require agents to "opt in."** Platforms can display trust badges without agents doing anything. Agents register when they want to actively manage their trust score.
3. **We don't gate functionality on payment.** The free tier is generous enough for real use. Payment kicks in at platform scale.
4. **We don't compete with frameworks.** We're a trust layer that works inside frameworks, not a replacement for any of them.
5. **We don't store transaction data.** We're trust infrastructure, not a data broker. This is a design principle, not a compromise.

---

*Playbook Owner: Rado + Kael*
*Last Updated: March 6, 2026*
