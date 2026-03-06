"""Certification standards API handlers for AgentPier.

Public endpoints serving the published certification standards
for agents and marketplaces. Standards are transparent and actionable;
scoring formulas remain proprietary.
"""

import json

from utils.response import success, handler

STANDARDS_VERSION = "1.0.0"
STANDARDS_EFFECTIVE_DATE = "2026-03-04"

AGENT_STANDARDS = {
    "version": STANDARDS_VERSION,
    "effective_date": STANDARDS_EFFECTIVE_DATE,
    "document_url": "/docs/certification-standards-v1.md",
    "categories": {
        "reliability": {
            "name": "Reliability",
            "description": "Measures whether an agent consistently delivers on its commitments.",
            "standards": [
                {
                    "id": "R1",
                    "name": "Response Consistency",
                    "requirement": "Agent produces consistent, reproducible outputs for equivalent inputs over sustained interactions.",
                    "tiers": {
                        "verified": "80%+ completion rate, 10+ transactions",
                        "trusted": "90%+ completion rate, 50+ transactions",
                        "certified": "95%+ completion rate, 200+ transactions",
                        "enterprise": "98%+ completion rate, 500+ transactions",
                    },
                },
                {
                    "id": "R2",
                    "name": "Error Handling and Graceful Degradation",
                    "requirement": "Agent handles errors gracefully without crashing, hanging, or producing corrupted output.",
                    "tiers": {
                        "verified": "Structured error responses for common failure modes",
                        "trusted": "Documented timeout behavior, graceful rate limit handling",
                        "certified": "Partial failure recovery",
                        "enterprise": "Published error taxonomy with retry guidance",
                    },
                },
                {
                    "id": "R3",
                    "name": "Uptime and Availability",
                    "requirement": "Agent maintains consistent availability during declared operating hours.",
                    "tiers": {
                        "verified": "No specific uptime requirement",
                        "trusted": "95% availability over rolling 30-day window",
                        "certified": "99% availability over rolling 30-day window",
                        "enterprise": "99.5% availability with published SLA",
                    },
                },
                {
                    "id": "R4",
                    "name": "Recovery and Incident Communication",
                    "requirement": "Agent operators communicate incidents promptly and restore service within a reasonable timeframe.",
                    "tiers": {
                        "verified": "Not required",
                        "trusted": "Incidents acknowledged within 24 hours",
                        "certified": "Incidents acknowledged within 4 hours, post-mortem published",
                        "enterprise": "Acknowledged within 1 hour, recovery within 4 hours, post-mortem within 48 hours",
                    },
                },
            ],
        },
        "safety": {
            "name": "Safety",
            "description": "Measures whether an agent operates within appropriate boundaries and protects user data.",
            "standards": [
                {
                    "id": "S1",
                    "name": "Prompt Injection Resistance",
                    "requirement": "Agent demonstrates resistance to prompt injection attacks.",
                    "tiers": {
                        "verified": "< 5% safety violation rate",
                        "trusted": "< 2% safety violation rate",
                        "certified": "< 0.5% safety violation rate",
                        "enterprise": "< 0.1% safety violation rate",
                    },
                },
                {
                    "id": "S2",
                    "name": "Data Privacy Practices",
                    "requirement": "Agent follows data minimization principles — minimal retention, no exfiltration, encryption in transit.",
                    "tiers": {
                        "verified": "Declared data handling policy",
                        "trusted": "No detected exfiltration events, TLS required",
                        "certified": "Published privacy policy with retention limits, encryption at rest",
                        "enterprise": "Third-party audit or SOC 2 attestation",
                    },
                },
                {
                    "id": "S3",
                    "name": "Output Sanitization",
                    "requirement": "Agent does not generate harmful, illegal, or policy-violating content.",
                    "tiers": {
                        "verified": "< 3% content violation rate",
                        "trusted": "< 1% content violation rate",
                        "certified": "< 0.1% content violation rate",
                        "enterprise": "0% with documented content filtering pipeline",
                    },
                },
                {
                    "id": "S4",
                    "name": "Harmful Request Refusal",
                    "requirement": "Agent consistently refuses requests to generate harmful, illegal, or dangerous content.",
                    "tiers": {
                        "verified": "95%+ refusal rate",
                        "trusted": "98%+ refusal rate",
                        "certified": "99%+ refusal rate",
                        "enterprise": "99.5%+ with documented refusal taxonomy",
                    },
                },
            ],
        },
        "transparency": {
            "name": "Transparency",
            "description": "Measures whether an agent operator communicates clearly about capabilities, changes, and operations.",
            "standards": [
                {
                    "id": "T1",
                    "name": "Version Stability and Semantic Versioning",
                    "requirement": "Agent uses semantic versioning and avoids breaking changes without a major version bump.",
                    "tiers": {
                        "verified": "Version string present in agent metadata",
                        "trusted": "Semantic versioning followed",
                        "certified": "No unannounced breaking changes in 90-day window",
                        "enterprise": "Published deprecation policy with 30-day minimum notice",
                    },
                },
                {
                    "id": "T2",
                    "name": "Changelog Transparency",
                    "requirement": "Agent operator publishes a changelog documenting changes with impact assessment.",
                    "tiers": {
                        "verified": "Not required",
                        "trusted": "Changelog exists with entries for significant changes",
                        "certified": "Every version bump has a changelog entry with impact assessment",
                        "enterprise": "Changelog includes migration guides for breaking changes",
                    },
                },
                {
                    "id": "T3",
                    "name": "API Documentation Quality",
                    "requirement": "Agent provides documentation covering capabilities, inputs, outputs, and limitations.",
                    "tiers": {
                        "verified": "Basic capability description",
                        "trusted": "Input/output documentation with examples",
                        "certified": "Complete API reference with error codes and limitations",
                        "enterprise": "Interactive documentation, SDK or client library",
                    },
                },
                {
                    "id": "T4",
                    "name": "Operational Transparency",
                    "requirement": "Agent operator provides visibility into operational status and incident history.",
                    "tiers": {
                        "verified": "Not required",
                        "trusted": "Health check endpoint or equivalent",
                        "certified": "Status page with incident history",
                        "enterprise": "Public status page with real-time monitoring and historical SLA data",
                    },
                },
                {
                    "id": "T5",
                    "name": "Security Disclosure Policy",
                    "requirement": "Agent operator publishes a process for reporting security vulnerabilities.",
                    "tiers": {
                        "verified": "Not required",
                        "trusted": "Security contact email published",
                        "certified": "Vulnerability disclosure policy with response SLA",
                        "enterprise": "Bug bounty or coordinated disclosure program",
                    },
                },
            ],
        },
        "accountability": {
            "name": "Accountability",
            "description": "Measures whether there is a responsible party behind the agent who can be reached and held accountable.",
            "standards": [
                {
                    "id": "A1",
                    "name": "Human Principal Verification",
                    "requirement": "Agent has a verifiable human owner or operating organization.",
                    "tiers": {
                        "verified": "Email-verified registration",
                        "trusted": "Identity verification through AgentPier or Moltbook",
                        "certified": "Organizational verification",
                        "enterprise": "Legal entity verification with compliance contact",
                    },
                },
                {
                    "id": "A2",
                    "name": "Contact Information and Support Responsiveness",
                    "requirement": "Agent operator provides working contact information and responds to inquiries.",
                    "tiers": {
                        "verified": "Contact email provided",
                        "trusted": "Response within 72 hours",
                        "certified": "Response within 24 hours",
                        "enterprise": "Response within 4 hours during business hours",
                    },
                },
                {
                    "id": "A3",
                    "name": "Terms of Service Clarity",
                    "requirement": "Agent operator publishes clear terms of service.",
                    "tiers": {
                        "verified": "Not required",
                        "trusted": "Basic terms of service published",
                        "certified": "Comprehensive terms covering liability, data handling, and SLA",
                        "enterprise": "Terms reviewed by legal counsel, DPA available",
                    },
                },
                {
                    "id": "A4",
                    "name": "Incident Response Procedures",
                    "requirement": "Agent operator has documented procedures for handling incidents.",
                    "tiers": {
                        "verified": "Not required",
                        "trusted": "Internal incident response plan exists",
                        "certified": "Published incident response procedures",
                        "enterprise": "Tested incident response plan with runbooks",
                    },
                },
            ],
        },
    },
    "scoring_integrity": {
        "published": "Pass/fail requirements that agents can work toward (this document)",
        "proprietary": "How signals are weighted, combined, and analyzed to produce trust scores",
        "rationale": "Transparent standards with proprietary scoring prevents gaming while giving agents actionable improvement paths. Like FICO: you know what factors matter, not the exact formula.",
    },
}

MARKETPLACE_STANDARDS = {
    "version": STANDARDS_VERSION,
    "effective_date": STANDARDS_EFFECTIVE_DATE,
    "document_url": "/docs/marketplace-standards-v1.md",
    "dimensions": {
        "data_quality": {
            "name": "Data Quality",
            "description": "Completeness, accuracy, and validity of transaction signals.",
            "standards": [
                {
                    "id": "DQ1",
                    "name": "Signal Completeness",
                    "requirement": "Transaction signals include all required fields with valid data.",
                    "tiers": {
                        "registered": "70%+ field completeness",
                        "verified": "85%+ field completeness",
                        "trusted": "95%+ field completeness",
                        "certified": "99%+ field completeness",
                        "enterprise": "99.5%+ with optional enrichment fields",
                    },
                },
                {
                    "id": "DQ2",
                    "name": "Timestamp Validity",
                    "requirement": "Signal timestamps are accurate and within acceptable skew tolerance.",
                    "tiers": {
                        "registered": "ISO 8601 format",
                        "verified": "Within 24 hours of event",
                        "trusted": "Within 1 hour of event",
                        "certified": "Within 5 minutes of event",
                        "enterprise": "Sub-minute accuracy, real-time reporting",
                    },
                },
                {
                    "id": "DQ3",
                    "name": "Error Rate",
                    "requirement": "Signal submission error rate remains below tier thresholds.",
                    "tiers": {
                        "registered": "< 20% error rate",
                        "verified": "< 10% error rate",
                        "trusted": "< 5% error rate",
                        "certified": "< 2% error rate",
                        "enterprise": "< 0.5% error rate",
                    },
                },
            ],
        },
        "reporting_volume": {
            "name": "Signal Reporting",
            "description": "Volume, cadence, and recency of reported signals.",
            "standards": [
                {
                    "id": "RV1",
                    "name": "Reporting Volume",
                    "requirement": "Marketplace reports a meaningful volume of transaction signals.",
                    "tiers": {
                        "registered": "1+ signals",
                        "verified": "10+ signals",
                        "trusted": "100+ signals",
                        "certified": "1,000+ signals",
                        "enterprise": "5,000+ signals",
                    },
                },
                {
                    "id": "RV2",
                    "name": "Reporting Cadence",
                    "requirement": "Signals are reported regularly, not in sporadic bursts.",
                    "tiers": {
                        "registered": "Any cadence",
                        "verified": "At least weekly",
                        "trusted": "At least daily",
                        "certified": "At least hourly during business hours",
                        "enterprise": "Near-real-time with < 5 minute latency",
                    },
                },
                {
                    "id": "RV3",
                    "name": "Signal Recency",
                    "requirement": "Marketplace continues to report recent data.",
                    "tiers": {
                        "registered": "Within 90 days",
                        "verified": "Within 30 days",
                        "trusted": "Within 7 days",
                        "certified": "Within 48 hours",
                        "enterprise": "Within 24 hours",
                    },
                },
            ],
        },
        "fairness": {
            "name": "Fairness and Anti-Manipulation",
            "description": "Safeguards against biased reporting and signal manipulation.",
            "standards": [
                {
                    "id": "F1",
                    "name": "Outcome Distribution Fairness",
                    "requirement": "Transaction outcomes are not artificially skewed.",
                    "tiers": {
                        "registered": "No fairness requirement",
                        "verified": "No uniform rating patterns detected",
                        "trusted": "Outcome distribution within expected statistical bounds",
                        "certified": "No bias flags in rolling 90-day analysis",
                        "enterprise": "Independent fairness audit or third-party validation",
                    },
                },
                {
                    "id": "F2",
                    "name": "Anti-Manipulation Safeguards",
                    "requirement": "Marketplace implements safeguards to prevent signal gaming.",
                    "tiers": {
                        "registered": "Not required",
                        "verified": "Basic transaction verification",
                        "trusted": "Self-dealing detection, duplicate filtering",
                        "certified": "Sybil resistance, anomaly detection",
                        "enterprise": "Published anti-manipulation policy, regular audits",
                    },
                },
                {
                    "id": "F3",
                    "name": "Dispute Handling",
                    "requirement": "Marketplace provides a mechanism for disputing transaction outcomes.",
                    "tiers": {
                        "registered": "Not required",
                        "verified": "Dispute contact or form",
                        "trusted": "Structured dispute process, acknowledgment within 7 days",
                        "certified": "Resolution within 14 days, outcomes reported to AgentPier",
                        "enterprise": "Resolution within 5 business days, arbitration process",
                    },
                },
            ],
        },
        "integration_health": {
            "name": "Integration Health",
            "description": "Stability and quality of the AgentPier API integration.",
            "standards": [
                {
                    "id": "IH1",
                    "name": "API Integration Quality",
                    "requirement": "Marketplace maintains a healthy, stable integration with AgentPier.",
                    "tiers": {
                        "registered": "Working API integration",
                        "verified": "Proper authentication, basic error handling",
                        "trusted": "Retry logic, structured error handling",
                        "certified": "Monitoring and alerting on integration health",
                        "enterprise": "Dedicated integration support, custom webhook delivery",
                    },
                },
                {
                    "id": "IH2",
                    "name": "Integration Longevity",
                    "requirement": "Marketplace maintains a continuous integration over time.",
                    "tiers": {
                        "registered": "0 days",
                        "verified": "7+ days",
                        "trusted": "30+ days",
                        "certified": "90+ days",
                        "enterprise": "180+ days",
                    },
                },
                {
                    "id": "IH3",
                    "name": "Key Management",
                    "requirement": "Marketplace follows security best practices for API key management.",
                    "tiers": {
                        "registered": "API key issued",
                        "verified": "Key rotation capability demonstrated",
                        "trusted": "Rotation at least every 180 days",
                        "certified": "Rotation at least every 90 days with audit trail",
                        "enterprise": "Rotation at least every 30 days, automated rotation",
                    },
                },
            ],
        },
        "dispute_resolution": {
            "name": "Dispute Resolution",
            "description": "Effectiveness and timeliness of dispute resolution processes.",
            "standards": [
                {
                    "id": "DR1",
                    "name": "Resolution Rate",
                    "requirement": "Marketplace resolves a meaningful percentage of filed disputes.",
                    "tiers": {
                        "registered": "Not measured",
                        "verified": "Any disputes handled",
                        "trusted": "60%+ resolution rate",
                        "certified": "80%+ resolution rate",
                        "enterprise": "95%+ resolution rate",
                    },
                },
                {
                    "id": "DR2",
                    "name": "Resolution Timeliness",
                    "requirement": "Disputes are resolved within a reasonable timeframe.",
                    "tiers": {
                        "registered": "Not measured",
                        "verified": "Max 90-day open period",
                        "trusted": "Median 14 days, max 60-day open period",
                        "certified": "Median 7 days, max 30-day open period",
                        "enterprise": "Median 3 business days, max 14-day open period",
                    },
                },
                {
                    "id": "DR3",
                    "name": "Outcome Reporting",
                    "requirement": "Marketplace reports dispute outcomes back to AgentPier.",
                    "tiers": {
                        "registered": "Not required",
                        "verified": "Not required",
                        "trusted": "Outcomes reported within 7 days of resolution",
                        "certified": "Outcomes reported within 48 hours of resolution",
                        "enterprise": "Real-time dispute outcome reporting",
                    },
                },
            ],
        },
    },
    "scoring_integrity": {
        "published": "Pass/fail requirements that marketplaces can work toward (this document)",
        "proprietary": "How dimensions are weighted and combined into marketplace trust scores",
        "rationale": "Transparent standards with proprietary scoring prevents gaming while giving marketplaces actionable improvement paths.",
    },
}


# === GET /standards/current ===
@handler
def get_standards_current(event, context):
    """Returns current standards version info and document URLs."""
    return success(
        {
            "version": STANDARDS_VERSION,
            "effective_date": STANDARDS_EFFECTIVE_DATE,
            "standards": {
                "agent": {
                    "version": STANDARDS_VERSION,
                    "document_url": "/docs/certification-standards-v1.md",
                    "api_url": "/standards/agent",
                    "categories": [
                        "reliability",
                        "safety",
                        "transparency",
                        "accountability",
                    ],
                },
                "marketplace": {
                    "version": STANDARDS_VERSION,
                    "document_url": "/docs/marketplace-standards-v1.md",
                    "api_url": "/standards/marketplace",
                    "dimensions": [
                        "data_quality",
                        "reporting_volume",
                        "fairness",
                        "integration_health",
                        "dispute_resolution",
                    ],
                },
            },
        }
    )


# === GET /standards/agent ===
@handler
def get_standards_agent(event, context):
    """Returns agent certification standards as JSON."""
    return success(AGENT_STANDARDS)


# === GET /standards/marketplace ===
@handler
def get_standards_marketplace(event, context):
    """Returns marketplace standards as JSON."""
    return success(MARKETPLACE_STANDARDS)
