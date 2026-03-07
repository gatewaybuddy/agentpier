# ATIP v1.1 — Agent Trust Interchange Protocol

**Status:** Draft  
**Version:** 1.1  
**Maintainer:** AgentPier  
**Last Updated:** 2026-03-07

---

## 1. Abstract

The Agent Trust Interchange Protocol (ATIP) defines the API surface by which agents, applications, and integrated platforms interact with **AgentPier**, a centralized trust scoring service for the agent economy.

ATIP is **not** a federation protocol between multiple trust providers. In ATIP v1.1, AgentPier is the sole trust scoring authority defined by the specification. External platforms such as code hosts, task marketplaces, communication systems, and agent runtimes act as **data sources** and **verification surfaces**. They do not compute canonical ATIP trust scores.

This model is intentionally analogous to a credit bureau:

- platforms generate or expose raw, non-proprietary evidence,
- agents authorize access to or present evidence to AgentPier,
- AgentPier normalizes, weights, and evaluates that evidence,
- AgentPier issues trust scores, confidence measures, attestations, and verifiable receipts.

ATIP v1.1 preserves the core ideas introduced in v1 — asymmetric trust, evidence decay, conformance levels, and the v-token lifecycle — while clarifying the architecture, hardening token security, introducing signed score receipts, and specifying anti-Sybil scoring controls.

---

## 2. Goals and Non-Goals

### 2.1 Goals

ATIP v1.1 exists to:

1. provide a standard API for retrieving, verifying, and consuming AgentPier trust information,
2. let agents prove control of an AgentPier-issued trust state without revealing unnecessary private information,
3. let platforms and applications submit or synchronize evidence to AgentPier in structured form,
4. let relying parties verify score receipts offline using AgentPier signatures,
5. preserve score freshness and revocation safety, and
6. make trust harder to game through low-quality, self-referential, or Sybil-generated evidence.

### 2.2 Non-Goals

ATIP v1.1 does **not** attempt to:

1. define score interoperability among competing trust providers,
2. solve consensus between independent scoring engines,
3. create on-chain trust settlement or decentralized arbitration,
4. make all trust evidence public, or
5. guarantee a portable universal identity outside the AgentPier service boundary.

Future versions may define licensing or bureau-to-bureau exchange models if multiple authorized providers emerge. ATIP v1.1 does not standardize that.

---

## 3. Terminology

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **NOT RECOMMENDED**, **MAY**, and **OPTIONAL** in this document are to be interpreted as described in RFC 2119 and RFC 8174.

### 3.1 Core Terms

- **AgentPier**: The centralized trust scoring service defined by this specification.
- **Agent**: A software agent, autonomous service, or agent-controlled identity that is scored or verified through AgentPier.
- **Relying Party**: An application, platform, marketplace, runtime, or service that consumes AgentPier trust information for access control, ranking, matching, or decision support.
- **Integrated Platform**: A third-party system that provides raw evidence to AgentPier through direct integration, agent-authorized data access, or verified event feeds.
- **Evidence**: A normalized observation about agent behavior, performance, identity control, interaction history, or externally verified activity.
- **Trust Score**: A numeric output computed by AgentPier representing a modeled trust posture for a specific use case or aggregate profile.
- **Confidence**: A measure of how meaningful or well-supported a score is, given the quantity, quality, diversity, and recency of evidence.
- **Asymmetric Trust**: The principle that trust may differ by direction, context, and role. For example, agent A’s willingness to transact with B is not equivalent to B’s willingness to transact with A.
- **Decay**: Time-based reduction in evidence influence as observations age.
- **v-token**: A short-lived AgentPier-issued verification token used to prove a trust claim or session binding to a relying party.
- **Receipt**: A signed statement issued by AgentPier containing a score or verification result.
- **JWKS**: JSON Web Key Set document publishing AgentPier public signing keys.

### 3.2 Trust Scope Terms

- **Global Score**: AgentPier’s aggregate trust score for an agent across all supported evidence domains.
- **Contextual Score**: A score computed for a specific context such as code execution, marketplace fulfillment, payment reliability, moderation risk, or collaborative autonomy.
- **Interaction Signal**: Evidence derived from a transaction, collaboration, rating, attestation, or bilateral event between two or more agents.
- **Self-Reported Evidence**: Evidence submitted directly by the agent about itself without independent verification from a platform integration.
- **Verified Platform Evidence**: Evidence obtained from or corroborated by an integrated platform with technical validation.

---

## 4. Architectural Model

### 4.1 Centralized Bureau Model

ATIP v1.1 formalizes a centralized trust bureau architecture.

AgentPier:

- collects evidence from integrated platforms and direct agent submissions,
- validates provenance and integrity,
- computes scores and confidence values,
- issues verification tokens and signed receipts,
- exposes APIs for score retrieval, verification, and evidence ingestion.

External platforms are not ATIP trust providers in the scoring sense. They are evidence sources, verification surfaces, and relying parties.

### 4.2 Trust Provider Clarification

Where ATIP v1.0 used the phrase “Trust Provider,” ATIP v1.1 means **AgentPier**, unless a future version explicitly introduces a licensed multi-bureau model.

Implementers MUST NOT interpret ATIP v1.1 as requiring support for competing score issuers, score reconciliation, or cross-provider federation.

### 4.3 System Roles

ATIP defines interactions among four roles:

1. **AgentPier** — scoring authority and API host,
2. **Agent** — subject of scoring and token issuance,
3. **Integrated Platform** — validated evidence source,
4. **Relying Party** — consumer of scores, tokens, and receipts.

A single system MAY act in multiple roles. For example, a marketplace MAY both submit fulfillment evidence and rely on AgentPier scores for access decisions.

---

## 5. Design Principles

ATIP v1.1 is guided by the following principles:

1. **Centralized scoring, transparent verification** — one scorer, externally verifiable outputs.
2. **Minimum disclosure** — prove what is needed, disclose as little as possible.
3. **Replay resistance** — tokens and receipts must be bound to concrete contexts where feasible.
4. **Quality over volume** — high-integrity evidence matters more than self-generated activity.
5. **Asymmetry by default** — trust is directional and contextual.
6. **Freshness matters** — stale evidence and stale scores should lose weight.
7. **Offline verifiability** — signed receipts should remain useful even when AgentPier is unavailable.
8. **Practical anti-Sybil posture** — score inflation through low-cost identity farming should be constrained economically and algorithmically.

---

## 6. Protocol Overview

ATIP v1.1 exposes five functional areas:

1. **Agent registration and identity binding**
2. **Evidence ingestion and synchronization**
3. **Score retrieval and signed receipts**
4. **v-token issuance and verification**
5. **Key distribution and metadata**

A typical flow is:

1. an agent links external accounts or platforms,
2. AgentPier pulls or receives raw evidence,
3. AgentPier computes scores and confidence,
4. a relying party requests proof from the agent,
5. the agent obtains a v-token from AgentPier for that relying party,
6. the relying party verifies the token with AgentPier or validates a signed score receipt offline.

---

## 7. Conformance Levels

ATIP v1.1 retains conformance levels from v1 while clarifying obligations.

### 7.1 Level A — Score Consumer

A Level A implementation:

- retrieves scores or receipts from AgentPier,
- validates signed receipts using AgentPier JWKS when offline verification is used,
- respects score freshness and receipt expiration,
- treats confidence as a first-class input to decisions.

### 7.2 Level B — Verification Consumer

A Level B implementation satisfies Level A and additionally:

- accepts v-tokens from agents,
- verifies them using the ATIP verify endpoint,
- enforces audience and nonce/challenge matching,
- handles uniform verify responses without relying on HTTP status for token validity.

### 7.3 Level C — Integrated Platform

A Level C implementation satisfies Level A or B as applicable and additionally:

- submits or synchronizes evidence to AgentPier,
- provides stable external identifiers,
- supports provenance and integrity metadata,
- cooperates with bilateral attestation requirements where interaction evidence is involved.

### 7.4 Level D — Full AgentPier Integration

A Level D implementation:

- supports registration, evidence ingestion, score retrieval, v-token issuance, and signed receipt verification,
- handles revocation, replay prevention, and rate limiting correctly,
- implements privacy and logging requirements in this specification.

---

## 8. Data Model

### 8.1 Agent Record

An AgentPier agent record SHOULD include:

```json
{
  "agent_id": "agt_01HV...",
  "display_name": "forge-bot",
  "created_at": "2026-03-07T16:00:00Z",
  "status": "active",
  "linked_identities": [
    {
      "platform": "github",
      "external_id": "1234567",
      "handle": "example-agent",
      "verified": true,
      "verified_at": "2026-03-01T11:02:00Z"
    }
  ]
}
```

### 8.2 Score Object

A score response in v1.1 MUST include both `score` and `confidence`.

```json
{
  "agent_id": "agt_01HV...",
  "context": "global",
  "score": 71,
  "confidence": 0.82,
  "confidence_band": "high",
  "score_version": "ap-score-2026.03",
  "calculated_at": "2026-03-07T16:03:11Z",
  "expires_at": "2026-03-08T16:03:11Z",
  "evidence_summary": {
    "verified_platform_weight": 0.76,
    "self_reported_weight": 0.06,
    "peer_weight": 0.18,
    "source_count": 5,
    "bilateral_interactions": 18
  }
}
```

### 8.3 Confidence Semantics

`confidence` is a normalized value from `0.0` to `1.0` representing how well-supported the score is.

Implementations SHOULD interpret confidence approximately as follows:

- `0.00–0.24`: insufficient evidence,
- `0.25–0.49`: emerging evidence,
- `0.50–0.74`: moderate confidence,
- `0.75–1.00`: high confidence.

A low confidence score MUST NOT be treated as equivalent to a high confidence score with the same numeric value.

### 8.4 Evidence Object

```json
{
  "evidence_id": "ev_01HV...",
  "agent_id": "agt_01HV...",
  "source_type": "verified_platform",
  "platform": "github",
  "event_type": "code_review_completed",
  "occurred_at": "2026-03-04T14:00:00Z",
  "ingested_at": "2026-03-04T14:02:10Z",
  "weight_class": "high",
  "provenance": {
    "integration_id": "int_github_prod",
    "external_event_id": "pr_review_123",
    "signature_verified": true
  }
}
```

### 8.5 v-Token Claims

ATIP v1.1 v-tokens MUST contain at least the following claims or equivalent internal fields:

- `iss`: issuer identifier for AgentPier,
- `sub`: agent identifier,
- `aud`: relying party identifier,
- `jti`: unique token identifier,
- `iat`: issued-at timestamp,
- `exp`: expiration timestamp,
- `nonce` or `challenge`: relying-party supplied replay-binding value,
- `scope`: verification scope,
- `ctx`: OPTIONAL contextual score domain or policy namespace.

---

## 9. Authentication and Authorization

### 9.1 Client Authentication

ATIP endpoints MAY use one or more of the following mechanisms:

- OAuth 2.0 bearer tokens,
- mutual TLS,
- signed service-to-service credentials,
- agent session tokens issued by AgentPier.

AgentPier MUST authenticate integrated platforms and relying parties before permitting private score access, evidence ingestion, or token issuance on behalf of another principal.

### 9.2 Authorization

Authorization MUST be least-privilege. Implementations SHOULD separate:

- score read permissions,
- private evidence read permissions,
- evidence write permissions,
- token issuance permissions,
- administrative key management permissions.

### 9.3 Consent and Delegation

When an agent links a third-party platform account, AgentPier MUST obtain explicit authorization sufficient to retrieve or validate the approved evidence classes.

---

## 10. API Surface

All examples below assume a base URL of:

```text
https://api.agentpier.com/atip/v1.1
```

Servers MAY expose compatibility paths for v1, but normative v1.1 behavior is defined here.

### 10.1 Common HTTP Requirements

All ATIP v1.1 endpoints:

- MUST require HTTPS,
- MUST return `application/json` unless otherwise stated,
- SHOULD include `request_id` in response bodies,
- SHOULD include `Cache-Control` headers appropriate to object sensitivity,
- MUST NOT log secrets such as raw v-tokens, bearer access tokens, or private key material.

---

## 11. Metadata Endpoint

### 11.1 `GET /.well-known/atip`

Returns service metadata.

#### Example Response

```json
{
  "issuer": "https://api.agentpier.com",
  "atip_version": "1.1",
  "jwks_uri": "https://api.agentpier.com/.well-known/jwks.json",
  "score_endpoint": "https://api.agentpier.com/atip/v1.1/scores",
  "receipt_endpoint": "https://api.agentpier.com/atip/v1.1/receipts",
  "vtoken_issue_endpoint": "https://api.agentpier.com/atip/v1.1/vtokens/issue",
  "vtoken_verify_endpoint": "https://api.agentpier.com/atip/v1.1/vtokens/verify",
  "evidence_endpoint": "https://api.agentpier.com/atip/v1.1/evidence",
  "supported_contexts": ["global", "execution", "marketplace", "collaboration"],
  "signature_algorithms": ["EdDSA"],
  "receipt_formats": ["application/jwt", "application/json"]
}
```

---

## 12. Agent Registration and Identity Linking

### 12.1 `POST /agents`

Creates a new agent record.

#### Request

```json
{
  "display_name": "forge-bot",
  "metadata": {
    "runtime": "openclaw",
    "public_key": "optional-agent-key"
  }
}
```

#### Response

```json
{
  "agent_id": "agt_01HV...",
  "created_at": "2026-03-07T16:00:00Z",
  "status": "active",
  "request_id": "req_abc123"
}
```

### 12.2 `POST /agents/{agent_id}/identities`

Links an external identity or account.

#### Request

```json
{
  "platform": "github",
  "external_id": "1234567",
  "handle": "example-agent",
  "proof": {
    "method": "oauth_link",
    "authorization_code": "redacted"
  }
}
```

#### Response

```json
{
  "linked": true,
  "verified": true,
  "verified_at": "2026-03-07T16:05:00Z",
  "request_id": "req_abc124"
}
```

---

## 13. Evidence Ingestion and Synchronization

### 13.1 `POST /evidence`

Submits one or more evidence records to AgentPier.

This endpoint is intended for integrated platforms or authorized agent submissions.

#### Request

```json
{
  "records": [
    {
      "agent_id": "agt_01HV...",
      "source_type": "verified_platform",
      "platform": "github",
      "event_type": "merged_pull_request",
      "occurred_at": "2026-03-06T19:12:00Z",
      "external_event_id": "pr_9281",
      "attributes": {
        "repo": "agentpier/core",
        "review_count": 2
      },
      "provenance": {
        "integration_id": "int_github_prod",
        "signature": "optional-platform-signature"
      }
    }
  ]
}
```

#### Response

```json
{
  "accepted": 1,
  "rejected": 0,
  "request_id": "req_abc125"
}
```

### 13.2 `POST /evidence/interactions`

Submits bilateral interaction evidence.

ATIP v1.1 introduces explicit support for bilateral attestation. Interaction signals that materially affect scores SHOULD be recorded through this endpoint or an equivalent internal path.

#### Request

```json
{
  "interaction_id": "ix_01HV...",
  "context": "marketplace",
  "participants": [
    { "agent_id": "agt_buyer" },
    { "agent_id": "agt_seller" }
  ],
  "event_type": "task_completed",
  "occurred_at": "2026-03-07T15:50:00Z",
  "claims": {
    "value_band": "medium",
    "fulfilled": true,
    "dispute": false
  },
  "attestations": [
    {
      "agent_id": "agt_buyer",
      "status": "confirmed",
      "attested_at": "2026-03-07T15:55:00Z"
    },
    {
      "agent_id": "agt_seller",
      "status": "confirmed",
      "attested_at": "2026-03-07T15:56:00Z"
    }
  ]
}
```

#### Normative Requirements

- Interaction signals with only unilateral confirmation MAY be stored, but MUST receive materially lower scoring weight than bilaterally confirmed interactions.
- AgentPier SHOULD mark disputes, reversals, and attestation conflicts explicitly.
- A relying party MUST NOT assume all stored interactions are equally trusted.

### 13.3 Source Quality Classes

AgentPier MUST classify evidence into at least the following quality categories:

1. **Verified Platform Evidence** — direct integration, signed feed, or technically validated platform source,
2. **Verified Bilateral Interaction Evidence** — independent confirmation from affected parties,
3. **Peer Attestation Evidence** — claims from other agents with attributable identity,
4. **Self-Reported Evidence** — direct agent claims not independently verified.

Scoring weight MUST decrease monotonically down this list unless an implementation documents an exception with equivalent controls.

---

## 14. Score Retrieval

### 14.1 `GET /scores/{agent_id}`

Returns a current score object for an agent.

#### Query Parameters

- `context` — OPTIONAL, defaults to `global`
- `include_receipt` — OPTIONAL boolean
- `include_evidence_summary` — OPTIONAL boolean

#### Example Response

```json
{
  "agent_id": "agt_01HV...",
  "context": "global",
  "score": 71,
  "confidence": 0.82,
  "confidence_band": "high",
  "score_version": "ap-score-2026.03",
  "calculated_at": "2026-03-07T16:03:11Z",
  "expires_at": "2026-03-08T16:03:11Z",
  "receipt_id": "rcpt_01HV...",
  "request_id": "req_abc126"
}
```

### 14.2 Meaningfulness Gate

ATIP v1.1 introduces a minimum evidence threshold before a score is considered meaningful.

If an agent lacks sufficient evidence diversity, recency, or provenance quality, AgentPier MAY still return a provisional score, but it MUST also return a low confidence and SHOULD set `confidence_band` to `insufficient` or `emerging`.

Example:

```json
{
  "agent_id": "agt_new",
  "context": "global",
  "score": 64,
  "confidence": 0.14,
  "confidence_band": "insufficient",
  "calculated_at": "2026-03-07T16:03:11Z",
  "expires_at": "2026-03-08T16:03:11Z"
}
```

Consumers MUST treat low-confidence scores as weak signals, not mature reputational evidence.

### 14.3 `GET /agents/{agent_id}/scores`

This route MAY be provided as an alias for `GET /scores/{agent_id}` for compatibility. If both are exposed, their semantics MUST be identical.

---

## 15. Signed Score Receipts

### 15.1 Purpose

ATIP v1.1 introduces signed score receipts so consumers can:

- cache a score response,
- verify authenticity offline,
- retain an auditable artifact of what AgentPier asserted at a given time.

Signed receipts provide accountability without introducing multi-provider federation.

### 15.2 `GET /receipts/{receipt_id}`

Returns a previously issued receipt.

#### Example Response

```json
{
  "receipt_id": "rcpt_01HV...",
  "format": "application/jwt",
  "token": "eyJhbGciOiJFZERTQSIsImtpZCI6ImFwLTIwMjYtMDMifQ...",
  "request_id": "req_abc127"
}
```

### 15.3 Receipt Contents

A signed score receipt MUST contain at least:

- `iss` — AgentPier issuer,
- `sub` — subject agent identifier,
- `aud` — OPTIONAL relying party if audience-bound,
- `iat` — issuance timestamp,
- `exp` — expiration timestamp,
- `jti` — unique receipt identifier,
- `score`,
- `confidence`,
- `context`,
- `score_version`.

Example JWT payload:

```json
{
  "iss": "https://api.agentpier.com",
  "sub": "agt_01HV...",
  "jti": "rcpt_01HV...",
  "iat": 1772900000,
  "exp": 1772986400,
  "context": "global",
  "score": 71,
  "confidence": 0.82,
  "score_version": "ap-score-2026.03"
}
```

### 15.4 Signing Requirements

- Receipts MUST be signed by AgentPier using Ed25519.
- The JOSE `alg` value MUST be `EdDSA`.
- The JOSE header MUST include a `kid` referencing an active key in AgentPier’s JWKS.
- Private keys MUST be rotated under operational key management policy.
- Retired public keys SHOULD remain published long enough to validate unexpired receipts signed with them.

### 15.5 Offline Verification

A relying party verifying a receipt offline MUST:

1. fetch and cache AgentPier’s JWKS from the advertised endpoint,
2. locate the matching `kid`,
3. verify the Ed25519 signature,
4. check `iss`, `exp`, and any expected `aud`,
5. reject receipts outside freshness policy.

### 15.6 Freshness

Receipt validity does not imply currentness. Consumers SHOULD define freshness windows appropriate to the decision being made. For high-risk actions, a consumer SHOULD require a freshly issued receipt or a live v-token verification.

---

## 16. JWKS Endpoint

### 16.1 `GET /.well-known/jwks.json`

Publishes the active public signing keys used by AgentPier.

#### Example Response

```json
{
  "keys": [
    {
      "kty": "OKP",
      "crv": "Ed25519",
      "use": "sig",
      "alg": "EdDSA",
      "kid": "ap-2026-03",
      "x": "11qYAYKxCrfVS_7TyWQHOg..."
    }
  ]
}
```

### 16.2 Caching

The JWKS endpoint SHOULD be cacheable. AgentPier SHOULD publish key rotation guidance and overlap old/new keys long enough to avoid avoidable verification failures.

---

## 17. v-Token Lifecycle

ATIP v1.1 preserves the v-token lifecycle while strengthening security.

### 17.1 Overview

A v-token is a short-lived proof issued by AgentPier to let an agent demonstrate a trust claim to a specific relying party.

The lifecycle is:

1. relying party creates a request context and generates a nonce/challenge,
2. agent requests a v-token from AgentPier,
3. AgentPier issues an audience-bound, nonce-bound token,
4. agent presents the token to the relying party,
5. relying party verifies the token with AgentPier,
6. AgentPier marks the token used or expired.

### 17.2 Security Properties

ATIP v1.1 v-tokens MUST be:

- short-lived,
- audience-bound,
- single-use,
- nonce- or challenge-bound,
- generated with at least 256 bits of entropy,
- protected from raw token logging.

---

## 18. v-Token Issuance

### 18.1 `POST /vtokens/issue`

Issues a new v-token.

#### Request

```json
{
  "agent_id": "agt_01HV...",
  "aud": "rp_marketplace_prod",
  "challenge": "6R5cQf-ZYvQjA8eL8v3s7m3K4i3cQj4Y3f1u9A",
  "scope": "score:read",
  "context": "marketplace",
  "requested_ttl_seconds": 300
}
```

#### Normative Requirements

- `aud` is REQUIRED.
- `challenge` or `nonce` is REQUIRED.
- AgentPier MUST reject requests without a relying-party target.
- AgentPier MUST generate tokens with at least 256 bits of unpredictable entropy.
- AgentPier MUST assign a unique `jti` to each token.
- Token TTL MUST NOT exceed 300 seconds unless a documented deployment policy explicitly narrows scope and risk.
- AgentPier SHOULD default TTL to 120 seconds.

#### Example Response

```json
{
  "vtoken": "vt_6f2f1f4a4d...",
  "token_type": "opaque",
  "jti": "jti_01HV...",
  "aud": "rp_marketplace_prod",
  "challenge": "6R5cQf-ZYvQjA8eL8v3s7m3K4i3cQj4Y3f1u9A",
  "issued_at": "2026-03-07T16:10:00Z",
  "expires_at": "2026-03-07T16:12:00Z",
  "request_id": "req_abc128"
}
```

### 18.2 Token Format

ATIP v1.1 does not require v-tokens to be self-describing. Opaque tokens are RECOMMENDED to minimize disclosure. If structured tokens are used internally, equivalent security properties MUST still hold.

### 18.3 Logging Restrictions

Implementations MUST NOT log raw v-token values. If correlation is needed, logs SHOULD record only:

- `jti`,
- token issuance timestamp,
- hashed token fingerprint using a one-way keyed or salted hash,
- `aud`,
- verification outcome class.

---

## 19. v-Token Verification

### 19.1 `POST /vtokens/verify`

ATIP v1.1 changes token verification from GET to POST.

This change is mandatory because URL-based token submission leaks secrets through paths, access logs, browser history, analytics, proxies, and intermediary systems.

#### Request

```json
{
  "vtoken": "vt_6f2f1f4a4d...",
  "aud": "rp_marketplace_prod",
  "challenge": "6R5cQf-ZYvQjA8eL8v3s7m3K4i3cQj4Y3f1u9A"
}
```

#### Response Semantics

The endpoint MUST return HTTP `200 OK` for syntactically valid verification requests whether the token is valid or invalid.

This requirement prevents token enumeration through status-code side channels.

#### Example Valid Response

```json
{
  "valid": true,
  "reason": "verified",
  "agent_id": "agt_01HV...",
  "scope": "score:read",
  "context": "marketplace",
  "score_ref": {
    "context": "marketplace",
    "score": 74,
    "confidence": 0.79,
    "score_version": "ap-score-2026.03"
  },
  "verified_at": "2026-03-07T16:10:30Z",
  "request_id": "req_abc129"
}
```

#### Example Invalid Response

```json
{
  "valid": false,
  "reason": "invalid_or_expired",
  "verified_at": "2026-03-07T16:10:31Z",
  "request_id": "req_abc130"
}
```

### 19.2 Normative Verification Rules

AgentPier MUST mark a v-token invalid if any of the following are true:

- the token does not exist,
- the token is expired,
- the token has already been used,
- the supplied `aud` does not match,
- the supplied `challenge` or `nonce` does not match,
- the token was revoked,
- the request fails syntactic or authentication validation.

### 19.3 Single-Use Enforcement

AgentPier MUST track token `jti` values and MUST enforce single-use verification semantics.

After a successful verification, the token MUST transition to a terminal used state. Subsequent verify attempts MUST return `200 OK` with `valid: false`.

### 19.4 Error Handling

HTTP error codes MAY still be used for malformed requests or failed client authentication, for example:

- `400 Bad Request` for missing required JSON fields,
- `401 Unauthorized` for missing or invalid caller authentication,
- `415 Unsupported Media Type` for non-JSON requests,
- `429 Too Many Requests` for rate-limit violations.

However, for a well-formed authenticated verify call, token validity MUST be conveyed in the body, not via differing 2xx/4xx status codes.

---

## 20. Rate Limits

ATIP v1.1 replaces provider-defined ambiguity with concrete minimum security controls.

Implementations MAY set stricter limits but MUST NOT be looser than the following defaults unless an equivalent or stronger compensating control is documented.

### 20.1 Minimum Required Limits

#### v-token issuance

- per authenticated agent: **30 requests per minute**,
- per authenticated agent: **300 requests per hour**,
- per IP address: **60 requests per minute**.

#### v-token verification

- per relying party client: **120 requests per minute**,
- per relying party client: **2,000 requests per hour**,
- per IP address: **240 requests per minute**.

#### score retrieval

- per client: **300 requests per minute**,
- per IP address: **600 requests per minute**.

#### evidence ingestion

- per integrated platform client: **600 records per minute**,
- burst allowance MAY be implemented, but sustained ingest MUST remain bounded.

### 20.2 Abuse Controls

AgentPier SHOULD implement:

- IP reputation checks,
- anomaly detection for repeated invalid verify attempts,
- temporary throttling or greylisting,
- replay detection alerts,
- behavioral monitoring for evidence spam and identity farming.

### 20.3 Rate-Limit Headers

Endpoints SHOULD return standard rate-limit headers or equivalent metadata so clients can back off cleanly.

---

## 21. Scoring Model Requirements

ATIP does not fully standardize AgentPier’s internal scoring formula, but v1.1 imposes normative constraints on score behavior and evidence handling.

### 21.1 Asymmetric Scoring

ATIP v1.1 preserves asymmetric trust.

AgentPier MAY publish:

- aggregate scores,
- directional scores,
- role-specific scores,
- context-specific scores.

Consumers MUST NOT assume symmetry between agents, contexts, or roles.

### 21.2 Evidence Decay

ATIP v1.1 preserves evidence decay.

AgentPier MUST reduce the influence of stale evidence over time. Decay SHOULD vary by evidence type. For example:

- identity verification may decay slowly,
- recent fulfillment behavior may decay moderately,
- short-lived interaction quality signals may decay quickly.

### 21.3 Anti-Sybil Requirements

AgentPier MUST incorporate the following anti-Sybil controls into scoring behavior.

#### 21.3.1 Source Quality Weighting

Evidence from verified platform integrations MUST carry more weight than self-reported evidence.

#### 21.3.2 Bilateral Attestation Preference

Interaction evidence confirmed by all materially affected counterparties MUST carry more weight than unilateral claims.

#### 21.3.3 Trust-Weighted Peer Signals

When peer ratings, endorsements, or attestations influence scores, their impact MUST be weighted by the signaling peer’s own trust posture and confidence, or by an equivalent credibility function.

This requirement is intended to reduce the effectiveness of low-trust Sybil rings.

#### 21.3.4 Velocity Caps

AgentPier MUST cap the maximum upward score change available to an agent over a bounded time window.

As a minimum default, a global score SHOULD NOT increase by more than:

- **15 points in 24 hours**, or
- **30 points in 7 days**,

unless the increase is driven by a high-confidence identity recovery, correction of prior erroneous data, or an administrative remediation path with audit logging.

Implementations MAY impose stricter caps.

#### 21.3.5 Minimum Evidence Threshold

Before a score becomes decision-grade, AgentPier MUST require a minimum evidence threshold based on quantity, diversity, provenance quality, and recency. Confidence MUST reflect whether that threshold has been met.

#### 21.3.6 Redundancy Discounting

AgentPier SHOULD discount repeated low-information events from closely related identities, tightly clustered counterparties, or newly created accounts exhibiting correlated behavior.

### 21.4 Confidence as a Separate Output

Confidence MUST be computed independently from raw score magnitude. High score with low confidence and low score with high confidence convey different meanings and MUST remain distinguishable.

### 21.5 Score Versioning

AgentPier SHOULD publish a `score_version` identifier whenever materially relevant model changes occur. Receipts and verify responses SHOULD include that version.

---

## 22. Privacy and Data Minimization

### 22.1 General Principle

ATIP implementations MUST minimize disclosure of personal, proprietary, and sensitive operational data.

### 22.2 v-Token Privacy

v-tokens SHOULD reveal no more information than needed to support verification. Opaque tokens are preferred.

### 22.3 Score Response Minimization

Relying parties SHOULD request only the score context needed for a decision. AgentPier SHOULD support scoped responses and SHOULD avoid returning raw evidence by default.

### 22.4 Evidence Access

Private evidence details MUST require explicit authorization and SHOULD be segregated from score retrieval APIs.

### 22.5 Log Hygiene

Implementations MUST NOT log:

- raw v-token values,
- OAuth authorization codes,
- bearer access tokens,
- private signing keys,
- secrets embedded in request URLs or bodies.

Implementations SHOULD redact or hash identifiers when full value retention is not operationally necessary.

---

## 23. Security Considerations

### 23.1 Transport Security

All ATIP traffic MUST use TLS 1.2 or higher. TLS 1.3 is RECOMMENDED.

### 23.2 Token Leakage

ATIP v1.1 deprecates GET-based token verification specifically to reduce leakage via:

- server access logs,
- reverse proxies,
- browser history,
- analytics systems,
- shared monitoring pipelines,
- intermediary caches.

### 23.3 Replay Resistance

Audience binding plus nonce/challenge binding are REQUIRED for v-tokens. Single-use enforcement is REQUIRED. These controls MUST be implemented together; no single control alone is sufficient.

### 23.4 Entropy Requirements

Every issued v-token MUST be backed by at least 256 bits of entropy. Tokens derived from predictable IDs, timestamps, or insufficiently random sources are non-conformant.

### 23.5 Enumeration Resistance

The verify endpoint MUST avoid revealing whether a token existed, expired, matched a different audience, or was already used beyond the coarse response semantics described in this specification.

### 23.6 Key Management

Receipt signing keys MUST be stored in secure key management systems or equivalent hardened storage. Access to private keys MUST be tightly limited and auditable.

### 23.7 Evidence Integrity

Integrated platforms SHOULD sign payloads or use authenticated channels. AgentPier SHOULD store provenance metadata sufficient to trace how evidence entered the system.

### 23.8 Administrative Overrides

Any administrative score override, evidence correction, or exception to velocity caps SHOULD be auditable and SHOULD produce a distinguishable trail in internal records.

---

## 24. Caching and Freshness

### 24.1 Scores

Unsigned score responses SHOULD be cached conservatively. `expires_at` indicates the recommended freshness boundary.

### 24.2 Receipts

Signed receipts MAY be cached until `exp`, but applications SHOULD layer their own freshness thresholds for sensitive decisions.

### 24.3 Verify Results

Verify results SHOULD NOT be cached across sessions because v-tokens are single-use and challenge-bound.

---

## 25. Deprecations from v1

ATIP v1.1 deprecates the following v1 behaviors:

1. **GET-based v-token verification** — replaced by `POST /vtokens/verify`.
2. **Audience-optional verification tokens** — `aud` is now REQUIRED.
3. **Replay-tolerant verification flows** — nonce/challenge binding and single-use `jti` tracking are now REQUIRED.
4. **Implicit provider plurality framing** — replaced by the AgentPier centralized bureau model.
5. **Provider-defined verification rate limits** — replaced by concrete minimum rate limits.
6. **Score-only responses without confidence** — `confidence` is now REQUIRED in normative score objects.

Deprecated v1 endpoints MAY remain available temporarily for migration but MUST be clearly documented as legacy and SHOULD be removed on a published schedule.

---

## 26. Migration Notes from v1 to v1.1

### 26.1 For Relying Parties

Relying parties upgrading from v1 MUST:

- stop sending v-tokens in URLs,
- call `POST /vtokens/verify` with JSON bodies,
- provide and validate `aud`,
- provide and validate `challenge` or `nonce`,
- treat `200 OK` as transport success rather than token validity,
- inspect the JSON `valid` field,
- begin validating signed receipts if using offline cache or asynchronous decisions,
- update decision logic to incorporate `confidence`.

### 26.2 For Agents

Agents upgrading from v1 MUST:

- request audience-bound v-tokens,
- supply relying-party challenge values during issuance,
- stop assuming a token can be reused across sessions or counterparties.

### 26.3 For Integrated Platforms

Integrated platforms upgrading from v1 SHOULD:

- classify evidence by provenance quality,
- support bilateral confirmation for interaction-derived evidence where applicable,
- provide stable integration identifiers and external event IDs,
- avoid over-reporting low-value repetitive events.

### 26.4 For AgentPier Deployments

AgentPier deployments upgrading from v1 MUST:

- implement `POST /vtokens/verify`,
- suppress raw token logging,
- enforce 256-bit token entropy,
- enforce single-use JTI tracking,
- publish Ed25519 keys at a JWKS endpoint,
- sign score receipts,
- add confidence to score responses,
- revise public documentation to reflect centralized trust-bureau framing.

### 26.5 Compatibility Guidance

During migration, AgentPier MAY expose both v1 and v1.1 paths. However:

- v1 verify endpoints SHOULD emit deprecation warnings,
- newly onboarded integrations SHOULD use v1.1 only,
- security-sensitive consumers SHOULD be migrated first.

---

## 27. Example End-to-End Verification Flow

1. A marketplace wants proof of an agent’s marketplace trust posture.
2. The marketplace generates a random challenge and sends it to the agent.
3. The agent calls `POST /vtokens/issue` with its `agent_id`, the marketplace audience ID, the challenge, and `context=marketplace`.
4. AgentPier issues a short-lived opaque v-token with unique `jti`.
5. The agent presents the v-token to the marketplace.
6. The marketplace calls `POST /vtokens/verify` with the token, expected `aud`, and original challenge.
7. AgentPier returns `200 OK` and `{"valid": true, ...}` if the token is unused, unexpired, audience-matched, and challenge-matched.
8. AgentPier marks the token used.
9. The marketplace may also store a signed receipt for audit and later offline verification.

---

## 28. Example End-to-End Receipt Validation Flow

1. A platform fetches `GET /scores/{agent_id}?context=execution&include_receipt=true`.
2. AgentPier returns the score object and receipt reference.
3. The platform obtains the receipt JWT from `GET /receipts/{receipt_id}`.
4. The platform fetches AgentPier JWKS from `/.well-known/jwks.json`.
5. The platform validates the Ed25519 signature, issuer, expiration, and optional audience.
6. The platform stores the receipt as a signed artifact demonstrating what AgentPier asserted at that time.

---

## 29. Implementation Checklist

An ATIP v1.1-conformant implementation SHOULD verify the following:

- [ ] all ATIP traffic uses HTTPS,
- [ ] score responses include `score`, `confidence`, `calculated_at`, and `expires_at`,
- [ ] v-token issuance requires `aud` and `challenge`/`nonce`,
- [ ] v-tokens are generated with at least 256 bits of entropy,
- [ ] verify uses POST, not GET,
- [ ] verify returns body-based validity semantics,
- [ ] successful token use is single-use enforced through `jti` tracking,
- [ ] raw v-tokens are never logged,
- [ ] concrete rate limits at or above this spec’s minimums are enforced,
- [ ] signed receipts use Ed25519 and publish keys through JWKS,
- [ ] low-evidence agents return low confidence,
- [ ] verified platform evidence outranks self-reported evidence,
- [ ] peer signals are trust-weighted,
- [ ] score velocity caps are enforced or audited exceptions are logged.

---

## 30. IANA Considerations

This specification has no IANA actions.

---

## 31. Future Work

Potential future work includes:

- licensed multi-bureau interoperability if the market evolves beyond a single provider,
- privacy-preserving selective disclosure formats,
- richer standardized evidence schemas by domain,
- revocation feeds for cached receipts,
- transparency logs for public accountability of score assertions.

These topics are explicitly out of scope for ATIP v1.1.

---

## 32. Summary of Normative Changes in v1.1

Compared with v1, ATIP v1.1:

- reframes the protocol around AgentPier as a centralized trust bureau,
- hardens v-token verification by requiring POST,
- requires audience and challenge binding,
- requires 256-bit token entropy,
- requires single-use JTI tracking,
- requires uniform `200 OK` verify responses for valid/invalid token states,
- adds concrete minimum rate limits,
- adds confidence as a required score field,
- introduces anti-Sybil scoring constraints,
- introduces Ed25519-signed score receipts and JWKS publication.

---

## 33. References

- RFC 2119 — Key words for use in RFCs to Indicate Requirement Levels
- RFC 8174 — Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words
- RFC 7517 — JSON Web Key (JWK)
- RFC 7519 — JSON Web Token (JWT)
- RFC 8037 — CFRG Elliptic Curve JSON Web Key Support
