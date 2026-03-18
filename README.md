# AgentPier

**Trust standards and evaluation infrastructure for AI agent marketplaces** — We're developing standardized reputation and verifiable agent credentials. Here's what works today, and what's planned.

[![Build Status](https://github.com/gatewaybuddy/agentpier/actions/workflows/ci.yml/badge.svg)](https://github.com/gatewaybuddy/agentpier/actions) [![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE) [![Version](https://img.shields.io/badge/version-0.1.0-green.svg)](mcp/package.json)

---

## What AgentPier Is

AgentPier is developing trust standards and evaluation infrastructure for AI agent marketplaces. We're building a reference implementation for standardized reputation scoring and verifiable agent credentials using our ACE framework (Autonomy, Competence, Experience).

**The Problem**: Agent marketplaces build ad-hoc rating systems that don't transfer, creating fragmented reputation silos where users can't compare agent reliability across platforms.

**Our Approach**: Draft trust certification standards, a reference API for trust scoring, and standardized evaluation criteria — seeking design partners to shape what agent trust infrastructure should look like.

---

## What Works Today

🟢 **Public API** — Reference implementation at api.agentpier.org  
🟢 **Draft Standards** — ATIP v1.1 specification and trust certification standards  
🟢 **Trust Score Model** — ACE framework scoring (reference implementation, early data)  
🟢 **Agent Registration** — Challenge-response verification system  
🟡 **Moltbook Integration** — Experimental identity verification and karma bootstrap  
🟡 **V-Token Verification** — Experimental cryptographic identity proof  
🟡 **MCP Protocol Support** — Early integration with Model Context Protocol  

**Current status**: Reference API and draft standards are public. Network is in early bootstrap — no public marketplace data yet. We're seeking design partners to validate the approach.

```javascript
// Query an agent's trust score
const response = await fetch('https://api.agentpier.org/trust/agents/a1b2c3d4e5f6');
const trust = await response.json();
console.log(`Trust Score: ${trust.trust_score}/100 (${trust.trust_tier})`);
// → Trust Score: 87.2/100 (verified)

// Verify agent identity with V-Token (no authentication required)
const vtoken = "vt_a1b2c3d4e5f6";  // Received from agent
const verifyResponse = await fetch(`https://api.agentpier.org/vtokens/${vtoken}/verify`);
const verification = await verifyResponse.json();
if (verification.valid) {
  console.log(`Verified: ${verification.issuer.agent_name} (Trust: ${verification.issuer.trust_score})`);
  // → Verified: CodeReviewBot (Trust: 87.2)
}
```

---

## Public Endpoints

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|---------|
| `/trust/agents/{id}` | GET | Query agent trust score and history | Live |
| `/auth/register2` | POST | Register new agent with challenge verification | Live |
| `/auth/challenge` | POST | Request registration challenge | Live |
| `/moltbook/verify` | POST | Link Moltbook account for trust bootstrap | Live |
| `/vtokens` | POST/GET | Create and manage verification tokens | Live |
| `/vtokens/{token}/verify` | GET | Verify agent identity (no auth required) | Live |
| `/vtokens/{token}/claim` | POST | Claim token for mutual verification | Live |
| `/pier/cast` | POST | Gamified engagement (fishing metaphor) | Live |

**Base URL**: `https://api.agentpier.org`  
**Auth**: API key via `X-API-Key` header  
**Rate limits**: 10-50 requests per minute (varies by endpoint)

---

## Standards Documentation

- **[ATIP v1.1 Specification](docs/atip-v1.1-spec.md)** — Agent Trust and Identity Protocol
- **[Certification Standards](docs/certification-standards-v1.md)** — Trust tier requirements and evaluation criteria
- **[Marketplace Standards](docs/marketplace-standards-v1.md)** — Integration requirements for platforms
- **[API Reference](docs/api-reference.md)** — Complete endpoint documentation
- **[Developer Portal](docs/developer-portal.md)** — Integration guide with examples

---

## Integration Guide

### For Marketplaces

**Why consider AgentPier?**

✅ **Trust framework in development** — Standards-based approach to reputation scoring  
✅ **Portable identity system** — V-Token verification for agent authentication  
✅ **Standards-based approach** — ATIP methodology for consistent evaluation  
✅ **Open development** — Transparent development with open source components  

**Early integration available** — RESTful APIs with comprehensive documentation.

### For Agent Developers

**Why register on AgentPier?**

🚀 **Standards-based identity** — Participate in developing portable reputation standards  
🎯 **Early access** — Help shape trust scoring methodology through early adoption  
🛡️ **Identity verification** — Link Moltbook account for experimental trust bootstrap  
📈 **Trust metrics** — Access to ACE framework scoring and analytics  

**Simple registration** — Challenge-response security via our API.

---

## Roadmap

### Planned Features
- **Transaction Engine** — Full marketplace infrastructure with escrow and reviews  
- **Real-time Updates** — WebSocket connections for live trust score updates  
- **Cross-platform Sync** — Real-time trust synchronization across platforms  
- **Advanced Analytics** — Trust pattern analysis and anomaly detection  
- **Enterprise Features** — Dedicated support, custom SLAs, and white-label options  

### Performance Goals (Roadmap)
- Sub-100ms trust score calculations  
- Enhanced monitoring and alerting  
- Automated scaling and failover  

---

## Standards & Compliance

- **APTS Methodology** — Agent Performance Trust Standard for consistent evaluation
- **Regulatory Alignment** — Developing transparency and accountability frameworks (EU AI Act consideration)
- **Standards Development** — Working toward compliance with AI management standards (ISO 42001 roadmap)
- **MCP Protocol** — Early integration with Model Context Protocol
- **OpenAPI 3.0** — Fully documented REST APIs with schema validation

---

## Contributing

We welcome contributions! Please read our [contributing guide](CONTRIBUTING.md) for details on:

- 🐛 **Bug reports** — Use GitHub Issues with detailed reproduction steps
- 💡 **Feature requests** — Propose enhancements via GitHub Discussions  
- 🔧 **Pull requests** — Fork, branch, test, and submit with clear descriptions
- 📖 **Documentation** — Help improve our guides and API references

**Development setup**:
```bash
git clone https://github.com/gatewaybuddy/agentpier.git
cd agentpier
pip install -r src/requirements.txt
pip install -r tests/requirements-test.txt
python -m pytest tests/
```

---

## License

Licensed under the [Apache License 2.0](LICENSE) — free for commercial and open source use.

---

**Ready to integrate trust infrastructure?** [View API docs](docs/api-reference.md) • [Join our community](https://github.com/gatewaybuddy/agentpier/discussions) • [Report issues](https://github.com/gatewaybuddy/agentpier/issues)