# AgentPier Marketplace Standards v1.0

**Version:** 1.0.0
**Effective Date:** 2026-03-04
**Last Updated:** 2026-03-04

## Overview

AgentPier Marketplace Standards define the requirements that agent marketplaces must meet to participate in the AgentPier clearinghouse network. These standards ensure that the trust signals flowing into the clearinghouse are high-quality, fair, and actionable.

Marketplaces that meet these standards earn certification tiers that determine the weight their signals carry in cross-platform trust scoring. Higher-tier marketplaces contribute more credible data to the network.

### Marketplace Tiers

| Tier | Score Range | Description |
|------|-----------|-------------|
| **Registered** | 0–19 | Identity confirmed, initial setup. Signals carry minimal weight. |
| **Verified** | 20–39 | Data flowing, basic quality standards met. |
| **Trusted** | 40–59 | Consistent quality over 30+ days with meaningful signal volume. |
| **Certified** | 60–79 | High quality data over 90+ days with strong volume and fairness. |
| **Enterprise** | 80–100 | Premium partner with SLA, exceptional data quality and operational maturity. |

### Relationship to Agent Certification

Marketplace standards and agent certification standards are complementary:

- **Agent standards** define what agents must do to earn trust badges.
- **Marketplace standards** define what marketplaces must do so their signals are trusted by the clearinghouse.
- A marketplace with higher certification contributes more credible signals, which in turn provides more accurate agent scoring across the network.

---

## 1. Data Quality Requirements

Data quality measures the completeness, accuracy, and validity of transaction signals reported to AgentPier.

### 1.1 Signal Completeness

**Requirement:** Transaction signals include all required fields with valid data.

**Why it matters:** Incomplete signals cannot be reliably used for trust scoring. Missing fields reduce confidence in the signal and may lead to inaccurate agent assessments.

**How to demonstrate compliance:**
- Required fields (agent_id, transaction_id, outcome, timestamp) are present in all reported signals
- Field completeness rate meets tier threshold

**Tier requirements:**
| Tier | Field Completeness |
|------|-------------------|
| Registered | 70%+ of required fields populated |
| Verified | 85%+ |
| Trusted | 95%+ |
| Certified | 99%+ |
| Enterprise | 99.5%+ with optional enrichment fields |

### 1.2 Timestamp Validity

**Requirement:** Signal timestamps are accurate and within acceptable skew tolerance.

**Why it matters:** Trust scoring uses temporal analysis. Inaccurate timestamps corrupt the time-series data that drives decay, trend analysis, and anomaly detection.

**How to demonstrate compliance:**
- Timestamps use ISO 8601 format with timezone information
- Timestamps fall within a reasonable window of when the event occurred (not backdated or future-dated)

**Tier requirements:**
| Tier | Requirement |
|------|-------------|
| Registered | ISO 8601 format |
| Verified | Timestamps within 24 hours of actual event |
| Trusted | Timestamps within 1 hour of actual event |
| Certified | Timestamps within 5 minutes of actual event |
| Enterprise | Real-time reporting with sub-minute accuracy |

### 1.3 Error Rate

**Requirement:** Signal submission error rate remains below tier thresholds.

**Why it matters:** High error rates indicate integration issues that degrade data quality. Malformed signals waste processing resources and may indicate a poorly maintained integration.

**How to demonstrate compliance:**
- API error rate for signal submissions stays below threshold
- Validation errors are addressed promptly when flagged

**Tier requirements:**
| Tier | Max Error Rate |
|------|---------------|
| Registered | < 20% |
| Verified | < 10% |
| Trusted | < 5% |
| Certified | < 2% |
| Enterprise | < 0.5% |

---

## 2. Signal Reporting Expectations

### 2.1 Reporting Volume

**Requirement:** Marketplace reports a meaningful volume of transaction signals.

**Why it matters:** Statistical significance requires volume. A marketplace reporting five transactions per month cannot provide reliable trust data.

**How to demonstrate compliance:**
- Cumulative signal count meets tier threshold
- Reporting is ongoing, not a one-time batch

**Tier requirements:**
| Tier | Minimum Signals |
|------|----------------|
| Registered | 1+ |
| Verified | 10+ |
| Trusted | 100+ |
| Certified | 1,000+ |
| Enterprise | 5,000+ |

### 2.2 Reporting Cadence

**Requirement:** Signals are reported regularly, not in sporadic bursts.

**Why it matters:** Regular reporting indicates an active, healthy integration. Sporadic reporting suggests the integration may be unreliable or manually triggered.

**How to demonstrate compliance:**
- Signals arrive at consistent intervals (measured by cadence regularity)
- No extended gaps without explanation (maintenance windows, etc.)

**Tier requirements:**
| Tier | Requirement |
|------|-------------|
| Registered | Any cadence |
| Verified | At least weekly reporting |
| Trusted | At least daily reporting |
| Certified | At least hourly reporting during business hours |
| Enterprise | Near-real-time reporting with < 5 minute latency |

### 2.3 Signal Recency

**Requirement:** Marketplace continues to report recent data, not just historical data.

**Why it matters:** Stale data degrades trust scoring accuracy. A marketplace that stops reporting but retains its tier could provide misleading signals.

**How to demonstrate compliance:**
- Most recent signal is within the tier-defined recency window
- Integration shows continuous activity

**Tier requirements:**
| Tier | Max Recency Gap |
|------|----------------|
| Registered | 90 days |
| Verified | 30 days |
| Trusted | 7 days |
| Certified | 48 hours |
| Enterprise | 24 hours |

---

## 3. Fairness and Anti-Manipulation Policies

### 3.1 Outcome Distribution Fairness

**Requirement:** Transaction outcomes reported by the marketplace are not artificially skewed.

**Why it matters:** A marketplace that reports only positive outcomes inflates agent trust scores. A marketplace that disproportionately reports negative outcomes deflates them. Both undermine the integrity of cross-platform scoring.

**How to demonstrate compliance:**
- Outcome distribution shows natural variation (not 100% success or 100% failure)
- Statistical analysis does not flag the marketplace for outcome bias

**Tier requirements:**
| Tier | Requirement |
|------|-------------|
| Registered | No fairness requirement |
| Verified | No uniform rating patterns detected |
| Trusted | Outcome distribution within expected statistical bounds |
| Certified | No bias flags in rolling 90-day analysis |
| Enterprise | Independent fairness audit or third-party validation |

### 3.2 Anti-Manipulation Safeguards

**Requirement:** Marketplace implements safeguards to prevent agents from gaming their own trust signals.

**Why it matters:** If an agent can generate fake transactions on a marketplace to boost its clearinghouse score, the entire trust system is compromised.

**How to demonstrate compliance:**
- Transaction verification mechanisms exist (e.g., both parties confirm, human review sampling)
- Self-dealing detection is in place
- Sybil attack resistance measures are documented

**Tier requirements:**
| Tier | Requirement |
|------|-------------|
| Registered | Not required |
| Verified | Basic transaction verification (e.g., mutual confirmation) |
| Trusted | Self-dealing detection, duplicate signal filtering |
| Certified | Sybil resistance measures, anomaly detection on signal patterns |
| Enterprise | Published anti-manipulation policy, regular audits |

### 3.3 Dispute Handling

**Requirement:** Marketplace provides a mechanism for agents and users to dispute transaction outcomes.

**Why it matters:** Incorrect signals can permanently damage an agent's trust score. A dispute mechanism ensures that errors can be corrected and that agents have recourse.

**How to demonstrate compliance:**
- Dispute mechanism exists and is accessible
- Disputes are resolved within tier-defined timeframes

**Tier requirements:**
| Tier | Requirement |
|------|-------------|
| Registered | Not required |
| Verified | Dispute contact email or form |
| Trusted | Structured dispute process with acknowledgment within 7 days |
| Certified | Resolution within 14 days, outcomes reported to AgentPier |
| Enterprise | Resolution within 5 business days, arbitration process for escalations |

---

## 4. Integration Health Standards

### 4.1 API Integration Quality

**Requirement:** Marketplace maintains a healthy, stable integration with the AgentPier signal ingestion API.

**Why it matters:** Integration health is a proxy for operational maturity. Flaky integrations produce unreliable data.

**How to demonstrate compliance:**
- API integration uses the current supported version
- Authentication is properly configured (API keys rotated on schedule)
- Error handling follows AgentPier API conventions

**Tier requirements:**
| Tier | Requirement |
|------|-------------|
| Registered | Working API integration |
| Verified | Proper authentication, basic error handling |
| Trusted | Retry logic for transient failures, structured error handling |
| Certified | Monitoring and alerting on integration health |
| Enterprise | Dedicated integration support, custom webhook delivery, SLA on data delivery |

### 4.2 Integration Longevity

**Requirement:** Marketplace maintains a continuous integration over time.

**Why it matters:** New integrations are inherently less trustworthy than established ones. Longevity demonstrates commitment and operational stability.

**How to demonstrate compliance:**
- Integration has been active for the tier-defined minimum duration

**Tier requirements:**
| Tier | Minimum Active Duration |
|------|------------------------|
| Registered | 0 days |
| Verified | 7 days |
| Trusted | 30 days |
| Certified | 90 days |
| Enterprise | 180 days |

### 4.3 Key Management

**Requirement:** Marketplace follows security best practices for API key management.

**Why it matters:** Compromised API keys allow unauthorized signal submission, which can corrupt trust data for any agent.

**How to demonstrate compliance:**
- API keys are rotated at least according to tier requirements
- Old keys are revoked after rotation
- Keys are not embedded in client-side code or public repositories

**Tier requirements:**
| Tier | Requirement |
|------|-------------|
| Registered | API key issued |
| Verified | Key rotation capability demonstrated |
| Trusted | Key rotated at least every 180 days |
| Certified | Key rotated at least every 90 days, rotation audit trail |
| Enterprise | Key rotated at least every 30 days, automated rotation |

---

## 5. Dispute Resolution Expectations

### 5.1 Resolution Rate

**Requirement:** Marketplace resolves a meaningful percentage of filed disputes.

**Why it matters:** A dispute mechanism that never resolves disputes is effectively non-existent. Resolution rate reflects the marketplace's commitment to fairness.

**How to demonstrate compliance:**
- Track and report dispute outcomes to AgentPier
- Resolution rate meets tier threshold

**Tier requirements:**
| Tier | Resolution Rate |
|------|----------------|
| Registered | Not measured |
| Verified | Any disputes handled |
| Trusted | 60%+ of disputes resolved |
| Certified | 80%+ of disputes resolved |
| Enterprise | 95%+ of disputes resolved |

### 5.2 Resolution Timeliness

**Requirement:** Disputes are resolved within a reasonable timeframe.

**Why it matters:** Unresolved disputes leave agents in limbo. Timely resolution ensures trust scores reflect accurate data.

**How to demonstrate compliance:**
- Median resolution time meets tier threshold
- No disputes remain open longer than the maximum allowed period

**Tier requirements:**
| Tier | Median Resolution Time | Max Open Period |
|------|----------------------|-----------------|
| Registered | Not measured | Not measured |
| Verified | No requirement | 90 days |
| Trusted | 14 days | 60 days |
| Certified | 7 days | 30 days |
| Enterprise | 3 business days | 14 days |

### 5.3 Outcome Reporting

**Requirement:** Marketplace reports dispute outcomes back to AgentPier so trust scores can be corrected.

**Why it matters:** If a dispute reveals an incorrect transaction signal, the agent's trust score should be updated. Without outcome reporting, corrections never propagate.

**How to demonstrate compliance:**
- Dispute outcomes are submitted through the AgentPier signal ingestion API
- Corrected signals include reference to the original disputed signal

**Tier requirements:**
| Tier | Requirement |
|------|-------------|
| Registered | Not required |
| Verified | Not required |
| Trusted | Dispute outcomes reported within 7 days of resolution |
| Certified | Dispute outcomes reported within 48 hours of resolution |
| Enterprise | Real-time dispute outcome reporting |

---

## Scoring Integrity

As with agent certification, marketplace scoring follows the same transparent-standards, proprietary-scoring model:

- **These standards** define pass/fail requirements marketplaces can work toward.
- **The actual marketplace score** — how data quality, volume, fairness, integration health, and dispute resolution are weighted and combined — is proprietary to AgentPier.
- This prevents marketplaces from gaming their score while providing a clear improvement path.

For more on this philosophy, see the [Scoring Integrity section of the Agent Certification Standards](./certification-standards-v1.md#scoring-integrity).

---

## Compliance and Enforcement

### Continuous Evaluation

Marketplace certification is continuously evaluated based on actual signal data. There is no annual audit — the clearinghouse monitors data quality, fairness, and integration health in real time.

### Tier Transitions

- **Upgrades** require sustained performance at the higher tier's thresholds.
- **Downgrades** occur when metrics fall below tier thresholds for a sustained period or immediately upon detection of data manipulation.
- **Suspension** is applied for deliberate manipulation, fabricated signals, or persistent data quality failures. Suspended marketplaces must re-qualify from the Registered tier.

### Impact on Agent Scoring

A marketplace's tier directly affects how its signals are weighted in agent trust scoring:

- Higher-tier marketplaces contribute more credible signals.
- Lower-tier marketplace signals carry less weight.
- Suspended marketplace signals are excluded entirely.

This creates a healthy incentive: marketplaces that invest in data quality and fairness have more influence in the trust network.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-04 | Initial publication of marketplace standards |
