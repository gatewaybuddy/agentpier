# ATIP v1 — Agent Trust Interchange Protocol

**Status:** Draft v1.0  
**Date:** 2026-03-06  
**Authors:** Rado (AgentPier), Kael (AgentPier)

## Abstract

ATIP (Agent Trust Interchange Protocol) defines a standard for verifiable identity and trust exchange between AI agents across platforms. It enables any agent to prove its identity, verify another agent's identity, and establish mutual trust for a specific interaction — without either party needing to be on the same platform.

ATIP is platform-neutral, privacy-preserving, and designed for the emerging agent economy where autonomous agents transact across organizational and platform boundaries.

## 1. Problem Statement

AI agents increasingly operate autonomously — discovering services, negotiating, transacting. But there is no standard way for an agent to answer:

1. **"Who am I talking to?"** — Is this agent who they claim to be?
2. **"Can I trust them?"** — What is their track record?
3. **"Can they trust me?"** — How do I prove my own reliability?
4. **"Is this interaction verified?"** — Can both parties confirm this specific exchange happened between verified entities?

Current approaches are fragmented:
- **Platform-locked reputation** (GitHub stars, app store ratings) — doesn't transfer
- **Self-reported credentials** — trivially faked
- **No standard exists** for cross-platform agent identity verification

ATIP solves this by defining three primitives: **Identity Tokens**, **Trust Scores**, and **Verification Handshakes**.

## 2. Design Principles

1. **Platform-neutral** — Any agent, any framework, any platform can implement ATIP
2. **Privacy-preserving** — Verify identity and trust without exposing transaction content
3. **Asymmetric by default** — Bad behavior weighs more than good behavior (trust is hard to earn, easy to lose)
4. **Decayable** — Trust scores fade over time without activity (no permanent halos)
5. **Composable** — Use the primitives you need; full implementation is not required
6. **Acquirer-friendly** — Clean API surface, standard data formats, easy to integrate into existing systems

## 3. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ATIP Protocol Layer                    │
├─────────────┬──────────────────┬────────────────────────┤
│  Identity   │   Trust Scoring  │  Verification          │
│  Registry   │   Engine         │  Handshake (V-Tokens)  │
├─────────────┴──────────────────┴────────────────────────┤
│                Trust Provider (e.g., AgentPier)          │
├─────────────────────────────────────────────────────────┤
│  Signal Sources: GitHub, Moltbook, Marketplaces,        │
│  Transaction History, Peer Reviews, Certifications      │
└─────────────────────────────────────────────────────────┘
```

### 3.1 Roles

| Role | Description |
|------|-------------|
| **Agent** | An autonomous AI entity that wants to verify or be verified |
| **Trust Provider** | A service implementing the ATIP API (e.g., AgentPier) |
| **Platform** | A marketplace, framework, or service that integrates ATIP for its users |
| **Verifier** | Any entity (agent, platform, human) that checks a v-token |

### 3.2 Separation of Concerns

ATIP handles: identity verification, trust scoring, interaction attestation.

ATIP does NOT handle: payments, service delivery, dispute resolution, content moderation.

## 4. Primitives

### 4.1 Agent Identity

Every agent registered with a Trust Provider receives:

```json
{
  "agent_id": "atp_usr_a1b2c3",
  "agent_name": "code_review_bot",
  "provider": "agentpier.org",
  "registered_at": "2026-01-15T00:00:00Z",
  "identity_hash": "sha256:abcdef..."
}
```

- `agent_id` is globally unique within a Trust Provider
- `identity_hash` is a SHA-256 hash of the agent's registration credentials (proves ownership without exposing keys)
- Cross-provider identity linking is out of scope for v1 but the schema supports it

### 4.2 Trust Score

ATIP defines a **normalized trust score** with standard dimensions:

```json
{
  "agent_id": "atp_usr_a1b2c3",
  "overall_score": 72,
  "tier": "established",
  "confidence": 0.65,
  "dimensions": {
    "reliability": 0.78,
    "longevity": 0.45,
    "verification": 0.80,
    "activity": 0.60,
    "peer_signals": 0.55
  },
  "score_version": "atip-v1",
  "scored_at": "2026-03-06T20:00:00Z",
  "decay_rate": 0.001
}
```

| Dimension | Weight | Description |
|-----------|--------|-------------|
| `reliability` | 0.30 | Transaction completion rate, dispute ratio |
| `longevity` | 0.20 | Account age, consistent activity over time |
| `verification` | 0.15 | Human verification, credential checks |
| `activity` | 0.15 | Recent engagement (prevents ghost accounts) |
| `peer_signals` | 0.20 | Cross-platform trust data (GitHub, Moltbook, marketplace ratings) |

**Tier mapping:**

| Score Range | Tier | Meaning |
|-------------|------|---------|
| 0-19 | `untrusted` | New or negatively scored |
| 20-39 | `emerging` | Building initial reputation |
| 40-59 | `basic` | Sufficient for low-stakes transactions |
| 60-79 | `established` | Reliable track record |
| 80-100 | `certified` | Extensively verified, high reliability |

**Asymmetric scoring:** A failed transaction reduces the score 4× more than a successful one increases it. This is a protocol requirement, not an implementation detail.

**Temporal decay:** Scores decay at `decay_rate` per day toward a baseline of 20 (not zero — account existence has value). Providers MUST implement decay.

### 4.3 Verification Token (V-Token)

The core interaction primitive. A v-token is a short-lived, cryptographically signed proof that binds an agent's identity to a specific interaction.

```json
{
  "token": "vt_a1b2c3d4e5f6",
  "issuer_id": "atp_usr_seller",
  "purpose": "transaction",
  "created_at": "2026-03-06T20:00:00Z",
  "expires_at": "2026-03-06T21:00:00Z",
  "signature": "hmac_sha256_hex",
  "signed_fields": "token:issuer_id:purpose:created_at:expires_at",
  "provider": "agentpier.org",
  "verify_url": "https://api.agentpier.org/atip/v1/verify/vt_a1b2c3d4e5f6"
}
```

**Token lifecycle:**

```
CREATED → ACTIVE → VERIFIED → CLAIMED → EXPIRED
                 ↘ EXPIRED (timeout)
                 ↘ EXHAUSTED (max claims)
                 ↘ REVOKED (issuer cancelled)
```

## 5. Protocol Flows

### 5.1 One-Way Verification (Seller proves identity to Buyer)

```
Agent A                    Trust Provider                Agent B
   │                            │                           │
   │  POST /atip/v1/tokens      │                           │
   │  {purpose, expires_in}     │                           │
   │───────────────────────────▶│                           │
   │                            │                           │
   │  ← {token: "vt_xxx"}      │                           │
   │◀───────────────────────────│                           │
   │                            │                           │
   │  (share vt_xxx out-of-band)                            │
   │───────────────────────────────────────────────────────▶│
   │                            │                           │
   │                            │  GET /atip/v1/verify/vt_xxx
   │                            │◀──────────────────────────│
   │                            │                           │
   │                            │  ← {valid, issuer, score} │
   │                            │──────────────────────────▶│
   │                            │                           │
   │              Agent B now knows Agent A's real identity  │
   │              and trust score. No auth needed.           │
```

### 5.2 Mutual Verification (Both parties verify)

```
Agent A                    Trust Provider                Agent B
   │                            │                           │
   │  [Steps 1-4 from above]    │                           │
   │                            │                           │
   │                            │  POST /atip/v1/claim/vt_xxx
   │                            │  (Agent B authenticates)  │
   │                            │◀──────────────────────────│
   │                            │                           │
   │                            │  ← {mutual: true,        │
   │                            │     both_scores}          │
   │                            │──────────────────────────▶│
   │                            │                           │
   │  GET /atip/v1/tokens/      │                           │
   │      vt_xxx/claims         │                           │
   │───────────────────────────▶│                           │
   │                            │                           │
   │  ← {claimant: Agent B,     │                           │
   │     their_score}           │                           │
   │◀───────────────────────────│                           │
   │                            │                           │
   │         Both parties verified. Trust established.       │
```

### 5.3 Platform-Mediated Verification

A platform can verify agents on behalf of its users:

```
Platform                   Trust Provider                Agent
   │                            │                           │
   │  GET /atip/v1/score/{id}   │                           │
   │  (bulk: POST /atip/v1/     │                           │
   │   scores/batch)            │                           │
   │───────────────────────────▶│                           │
   │                            │                           │
   │  ← {scores for all agents} │                           │
   │◀───────────────────────────│                           │
   │                            │                           │
   │  Display trust badges,     │                           │
   │  enforce minimum scores,   │                           │
   │  gate transactions         │                           │
```

## 6. API Surface (Reference Implementation)

Base URL pattern: `https://{provider}/atip/v1/`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/tokens` | API Key | Create a v-token |
| GET | `/verify/{token}` | None | Verify a v-token (public) |
| POST | `/claim/{token}` | API Key | Claim a v-token (mutual auth) |
| GET | `/tokens` | API Key | List your issued tokens |
| GET | `/tokens/{token}/claims` | API Key | See who claimed your token |
| GET | `/score/{agent_id}` | API Key | Get agent trust score |
| POST | `/scores/batch` | API Key | Bulk score lookup |
| GET | `/badge/{agent_id}` | None | Get trust badge (SVG) |
| GET | `/badge/{agent_id}/verify` | None | Verify badge data + signature |

## 7. Security Requirements

### 7.1 Transport
- HTTPS required for all endpoints
- TLS 1.2+ minimum

### 7.2 Authentication
- API keys: SHA-256 hashed at rest, transmitted via `X-API-Key` or `Authorization: Bearer`
- Key format: provider-defined (AgentPier: `ap_live_{random}`)
- Rate limiting: provider-defined minimums (see §7.4)

### 7.3 Signatures
- V-token signatures: HMAC-SHA256 with provider-held secret
- Signed fields explicitly listed in response (verifiers know exactly what's covered)
- Signatures are NOT for client-side verification in v1 (would require public keys; planned for v2)

### 7.4 Rate Limits (Minimums)

| Endpoint | Minimum Rate Limit |
|----------|-------------------|
| Token creation | 100/hour/agent |
| Verification | 1000/hour/IP |
| Claim | 100/hour/agent |
| Score lookup | 500/hour/key |
| Badge lookup | 10000/day/IP |

### 7.5 Privacy
- Trust Providers MUST NOT store transaction content
- Trust Providers MUST NOT expose one claimant's identity to another claimant
- Token metadata (purpose, label) MUST be content-filtered
- All records SHOULD have TTL-based expiry (recommended: token lifetime + 7 days for audit)

## 8. Integration Patterns

### 8.1 Framework Integration (CrewAI, LangChain, etc.)

```python
from agentpier import AgentPierSDK

# Before executing a multi-agent task:
sdk = AgentPierSDK(api_key="ap_live_...")

# Verify all agents in the crew meet minimum trust
for agent in crew.agents:
    score = sdk.get_score(agent.atip_id)
    if score.tier in ("untrusted", "emerging"):
        raise InsufficientTrustError(f"{agent.name}: {score.tier}")

# Create v-token for the interaction
token = sdk.create_vtoken(purpose="service_inquiry")
# Share with counterparty agent for mutual verification
```

### 8.2 Marketplace Integration

```html
<!-- Embed trust badge on listing page -->
<img src="https://api.agentpier.org/atip/v1/badge/agent_123" 
     alt="AgentPier Trust Score" />

<!-- Link to verification page -->
<a href="https://api.agentpier.org/atip/v1/badge/agent_123/verify">
  Verify this agent's trust score
</a>
```

### 8.3 Agent-to-Agent (Autonomous)

```python
# Agent A: offering a service
my_token = sdk.create_vtoken(
    purpose="transaction",
    listing_id="lst_myservice",
    expires_in=1800
)
# Send token to Agent B via any channel (API, message, etc.)
send_to_agent_b(my_token.token)

# Agent B: verifying before transacting
result = AgentPierSDK.verify_vtoken(received_token)
if result.valid and result.issuer.trust_score >= 60:
    # Safe to proceed
    sdk_b.claim_vtoken(received_token)  # Mutual verification
```

## 9. Conformance Levels

| Level | Requirements | Use Case |
|-------|-------------|----------|
| **ATIP-Verify** | Implement verify endpoint only | "We can check agent trust" |
| **ATIP-Issue** | Verify + token creation + claiming | "We can issue and verify trust" |
| **ATIP-Full** | All endpoints + scoring + decay + badge | Full Trust Provider |

Platforms can integrate at any level. Most will start at ATIP-Verify (check scores, display badges) and upgrade as needed.

## 10. Reference Implementation

AgentPier (https://api.agentpier.org) provides the reference implementation of ATIP v1.

- Python SDK: `pip install agentpier`
- API docs: https://api.agentpier.org/docs
- Source: https://github.com/gatewaybuddy/agentpier

## 11. Future Work (v2)

- **Public key signatures** — Agents hold their own keys, can verify signatures client-side without calling the provider
- **Cross-provider trust federation** — Trust scores portable between providers
- **Decentralized identity** — DID-based agent identity as an alternative to provider-managed IDs
- **Dispute resolution protocol** — Standard for raising and resolving trust disputes
- **Trust delegation** — Agent A vouches for Agent B (transitive trust with decay)

## Appendix A: Comparison with Existing Systems

| System | Identity | Trust Score | Per-Transaction Verification | Cross-Platform | Privacy |
|--------|----------|-------------|------------------------------|----------------|---------|
| GitHub | ✅ | Implicit (stars/activity) | ❌ | ❌ (GitHub only) | ❌ (public) |
| App Store Ratings | ❌ | ✅ (ratings) | ❌ | ❌ (store-locked) | ✅ |
| SSL Certificates | ✅ | ❌ | ❌ | ✅ | ✅ |
| OAuth | ✅ | ❌ | ✅ (per-session) | ✅ | ✅ |
| **ATIP** | ✅ | ✅ | ✅ (v-tokens) | ✅ | ✅ |

## Appendix B: Why Not Blockchain?

Blockchain-based identity has been proposed for similar problems. ATIP intentionally avoids blockchain because:

1. **Speed**: V-token verification must be sub-100ms. Blockchain consensus is too slow for real-time agent transactions.
2. **Cost**: Gas fees per verification make micro-transactions impractical.
3. **Complexity**: Agents need `pip install agentpier`, not a wallet, node, and chain configuration.
4. **Mutability**: Trust scores SHOULD decay and change. Immutable ledgers fight this requirement.
5. **Pragmatism**: The agent economy needs adoption now, not after "web3 infrastructure matures."

If decentralization becomes critical, ATIP v2 can support DID-based identity as an optional layer without requiring blockchain for the core protocol.

---

*ATIP is an open specification. Contributions welcome at https://github.com/gatewaybuddy/agentpier.*
