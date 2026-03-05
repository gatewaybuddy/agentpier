# NIST AI RMF → AgentPier Dimension Mapping

**Document Version:** 1.0  
**Assessment Date:** March 4, 2026  
**NIST AI RMF Version:** 1.0 (January 26, 2023)  
**AgentPier Assessment:** APTS v2.0 (Score: 57.6/100)

## Executive Summary

This document maps the NIST AI Risk Management Framework 1.0 to AgentPier's trust scoring dimensions, providing a comprehensive gap analysis and recommendations for enhanced AI risk management. The NIST AI RMF provides a structured approach through four core functions: **Govern**, **Map**, **Measure**, and **Manage**.

**Key Findings:**
- **Strong Coverage:** AgentPier aligns well with NIST Measure and Manage functions  
- **Moderate Coverage:** Map function partially covered through current assessment processes
- **Significant Gap:** Govern function substantially underdeveloped (affects foundation for all other functions)
- **Missing Elements:** 23 of 47 NIST subcategories not directly addressed by current AgentPier scoring

## NIST AI RMF → AgentPier Mapping Overview

| NIST Function | AgentPier Coverage | Score Alignment | Gap Severity | Implementation Priority |
|---------------|-------------------|----------------|---------------|------------------------|
| **GOVERN (15 subcategories)** | 🔴 **Poor (20%)** | Multiple dimensions | Critical | P0 - Foundational |
| **MAP (11 subcategories)** | 🟡 **Moderate (45%)** | Transparency/Accountability | Medium | P1 - Planning |
| **MEASURE (13 subcategories)** | 🟢 **Good (75%)** | Safety/Security/Reliability | Low | P2 - Enhancement |  
| **MANAGE (8 subcategories)** | 🟡 **Moderate (60%)** | Accountability/Reliability | Medium | P1 - Operations |

## Function-by-Function Analysis

### GOVERN Function → AgentPier Mapping

The **GOVERN** function establishes organizational culture and structures for AI risk management. This is AgentPier's most significant gap.

#### GOVERN 1: Policies, Processes, and Practices (7 subcategories)

| NIST ID | NIST Requirement | AgentPier Dimension | Current Score | Gap Analysis | Recommended Action |
|---------|------------------|-------------------|---------------|--------------|-------------------|
| **GOVERN 1.1** | Legal/regulatory requirements understood and documented | Transparency | 45/100 | 🔴 **CRITICAL** - No regulatory compliance framework documented | Create regulatory tracking system |
| **GOVERN 1.2** | Trustworthy AI characteristics integrated into organizational policies | All dimensions | 57.6/100 | 🔴 **HIGH** - No formal trustworthy AI policy | Develop comprehensive AI policy framework |
| **GOVERN 1.3** | Risk management activities determined based on risk tolerance | Accountability | 52/100 | 🔴 **HIGH** - No documented risk tolerance levels | Define organizational risk appetite |
| **GOVERN 1.4** | Risk management process established through transparent policies | Accountability | 52/100 | 🔴 **HIGH** - No formal risk management process | Implement risk management procedures |
| **GOVERN 1.5** | Ongoing monitoring and periodic review planned with defined roles | Accountability | 52/100 | 🔴 **MEDIUM** - Basic monitoring, no formal review cycles | Establish review governance |
| **GOVERN 1.6** | AI systems inventory mechanisms in place | Transparency | 45/100 | 🔴 **HIGH** - No systematic AI inventory process | Create AI system registry |
| **GOVERN 1.7** | Decommissioning and phase-out procedures | Accountability | 52/100 | 🔴 **HIGH** - No documented decommissioning procedures | Develop lifecycle management procedures |

**AgentPier GOVERN Gap Score: 20% coverage**

#### GOVERN 2: Accountability Structures (3 subcategories)

| NIST ID | NIST Requirement | AgentPier Dimension | Current Score | Gap Analysis |
|---------|------------------|-------------------|---------------|--------------|
| **GOVERN 2.1** | Roles and responsibilities documented and clear | Accountability | 52/100 | 🟡 **PARTIAL** - Basic contact info, no detailed role definition |
| **GOVERN 2.2** | Personnel receive AI risk management training | Accountability | 52/100 | 🔴 **MISSING** - No AI risk training program |
| **GOVERN 2.3** | Executive leadership takes responsibility for AI decisions | Accountability | 52/100 | 🟡 **PARTIAL** - GitHub ownership clear, no formal governance |

#### GOVERN 3: Workforce Diversity and Inclusion (2 subcategories)

| NIST ID | NIST Requirement | AgentPier Dimension | Current Score | Gap Analysis |
|---------|------------------|-------------------|---------------|--------------|
| **GOVERN 3.1** | Decision-making informed by diverse team | Fairness | 25/100 | 🔴 **CRITICAL** - No diversity analysis or diverse team requirements |
| **GOVERN 3.2** | Human-AI configuration policies in place | Accountability | 52/100 | 🔴 **MISSING** - No human-AI collaboration governance |

#### GOVERN 4: Risk Culture (3 subcategories)

| NIST ID | NIST Requirement | AgentPier Dimension | Current Score | Gap Analysis |
|---------|------------------|-------------------|---------------|--------------|
| **GOVERN 4.1** | Critical thinking and safety-first mindset fostered | Safety | 61/100 | 🟡 **PARTIAL** - Content filtering shows safety focus, no formal culture framework |
| **GOVERN 4.2** | Teams document and communicate AI risks and impacts | Transparency | 45/100 | 🔴 **MISSING** - No risk communication framework |
| **GOVERN 4.3** | AI testing, incident identification, and information sharing enabled | Safety | 61/100 | 🟡 **PARTIAL** - Basic testing, limited incident procedures |

#### Recommendations for GOVERN Function:

1. **Immediate (P0):** Develop AI governance charter and policy framework
2. **Short-term (P1):** Establish AI risk management committee with defined roles
3. **Medium-term (P2):** Implement comprehensive AI training program  
4. **Long-term (P3):** Integrate diversity and inclusion requirements into AI processes

### MAP Function → AgentPier Mapping

The **MAP** function establishes context and identifies risks. AgentPier has moderate coverage through its assessment processes.

#### MAP 1: Context Establishment (6 subcategories)

| NIST ID | NIST Requirement | AgentPier Dimension | Current Score | Gap Analysis |
|---------|------------------|-------------------|---------------|--------------|
| **MAP 1.1** | Intended purposes, uses, and contexts documented | Transparency | 45/100 | 🟡 **PARTIAL** - Basic API documentation, missing comprehensive context analysis |
| **MAP 1.2** | Interdisciplinary team with diverse expertise | Fairness | 25/100 | 🔴 **MISSING** - No diversity requirements or documentation |
| **MAP 1.3** | Organization's mission and AI goals documented | Transparency | 45/100 | 🟡 **PARTIAL** - GitHub README has mission, limited AI-specific goals |
| **MAP 1.4** | Business value/context clearly defined | Transparency | 45/100 | 🟡 **PARTIAL** - Basic business model documented |
| **MAP 1.5** | Organizational risk tolerances documented | Accountability | 52/100 | 🔴 **MISSING** - No documented risk tolerance levels |
| **MAP 1.6** | System requirements understood by AI actors | Transparency | 45/100 | 🟡 **PARTIAL** - Technical requirements documented, socio-technical implications missing |

#### MAP 2: AI System Categorization (3 subcategories)

| NIST ID | NIST Requirement | AgentPier Dimension | Current Score | Gap Analysis |
|---------|------------------|-------------------|---------------|--------------|
| **MAP 2.1** | Specific tasks and methods defined | Transparency | 45/100 | 🟢 **GOOD** - Clear API documentation of capabilities |
| **MAP 2.2** | Knowledge limits and human oversight documented | Transparency | 45/100 | 🔴 **MISSING** - Limited documentation of AI limitations |
| **MAP 2.3** | Scientific integrity and TEVV considerations identified | Reliability | 72/100 | 🟡 **PARTIAL** - Testing framework exists, limited validation documentation |

#### Recommendations for MAP Function:

1. **Context Documentation:** Comprehensive AI system context analysis for all marketplace agents
2. **Risk Tolerance Definition:** Formal organizational risk appetite statements
3. **Limitation Documentation:** Clear documentation of AI system knowledge limits and failure modes

### MEASURE Function → AgentPier Mapping

The **MEASURE** function is AgentPier's strongest area, aligning well with existing testing and evaluation practices.

#### MEASURE 1: Methods and Metrics (3 subcategories)

| NIST ID | NIST Requirement | AgentPier Dimension | Current Score | Gap Analysis |
|---------|------------------|-------------------|---------------|--------------|
| **MEASURE 1.1** | Appropriate metrics selected for significant AI risks | Safety/Security | 61/58 | 🟢 **GOOD** - Content filtering and rate limiting metrics |
| **MEASURE 1.2** | Metrics effectiveness regularly assessed | Reliability | 72/100 | 🟡 **PARTIAL** - Test coverage good, limited metrics validation |
| **MEASURE 1.3** | Independent assessors involved in evaluations | Accountability | 52/100 | 🔴 **MISSING** - No independent assessment process |

#### MEASURE 2: Trustworthy Characteristics Evaluation (13 subcategories)

| NIST ID | NIST Requirement | AgentPier Dimension | Current Score | Gap Analysis |
|---------|------------------|-------------------|---------------|--------------|
| **MEASURE 2.1** | Test sets, metrics, and tools documented | Reliability | 72/100 | 🟢 **GOOD** - Comprehensive test suite documented |
| **MEASURE 2.2** | Human subjects evaluation meets requirements | Fairness | 25/100 | 🔴 **MISSING** - No human subjects testing framework |
| **MEASURE 2.3** | Performance measured for deployment conditions | Reliability | 72/100 | 🟡 **PARTIAL** - Test coverage good, production monitoring limited |
| **MEASURE 2.4** | AI system functionality monitored in production | Reliability | 72/100 | 🟡 **PARTIAL** - Basic monitoring, limited behavioral analysis |
| **MEASURE 2.5** | System demonstrated to be valid and reliable | Reliability | 72/100 | 🟢 **GOOD** - Strong testing framework |
| **MEASURE 2.6** | System evaluated for safety risks | Safety | 61/100 | 🟡 **PARTIAL** - Content filtering, limited safety testing |
| **MEASURE 2.7** | Security and resilience evaluated | Security | 58/100 | 🟡 **PARTIAL** - Basic security controls, limited resilience testing |
| **MEASURE 2.8** | Transparency and accountability risks examined | Transparency | 45/100 | 🔴 **MISSING** - No systematic transparency risk assessment |
| **MEASURE 2.9** | AI model explained and output interpreted | Transparency | 45/100 | 🔴 **MISSING** - No explainability framework |
| **MEASURE 2.10** | Privacy risks examined and documented | Security | 58/100 | 🟡 **PARTIAL** - Basic data handling, no formal privacy impact assessment |
| **MEASURE 2.11** | Fairness and bias evaluated and documented | Fairness | 25/100 | 🔴 **CRITICAL** - No bias testing or fairness evaluation |
| **MEASURE 2.12** | Environmental impact assessed | N/A | N/A | 🔴 **MISSING** - No environmental impact consideration |
| **MEASURE 2.13** | TEVV metrics effectiveness evaluated | Reliability | 72/100 | 🟡 **PARTIAL** - Test metrics exist, effectiveness validation limited |

### MANAGE Function → AgentPier Mapping

The **MANAGE** function addresses ongoing risk treatment and response. AgentPier has moderate coverage.

#### MANAGE 1: Risk Prioritization and Response (4 subcategories)

| NIST ID | NIST Requirement | AgentPier Dimension | Current Score | Gap Analysis |
|---------|------------------|-------------------|--------------|--------------|
| **MANAGE 1.1** | Determination made whether to proceed with AI system | Accountability | 52/100 | 🟡 **PARTIAL** - Basic go/no-go decisions, no formal framework |
| **MANAGE 1.2** | Risk treatment prioritized based on impact and resources | Accountability | 52/100 | 🔴 **MISSING** - No documented risk prioritization process |
| **MANAGE 1.3** | Risk responses developed, planned, and documented | Accountability | 52/100 | 🔴 **MISSING** - No formal risk response procedures |
| **MANAGE 1.4** | Negative residual risks documented | Accountability | 52/100 | 🔴 **MISSING** - No residual risk documentation |

#### MANAGE 2: Strategy Implementation (4 subcategories)

| NIST ID | NIST Requirement | AgentPier Dimension | Current Score | Gap Analysis |
|---------|------------------|-------------------|--------------|--------------|
| **MANAGE 2.1** | Resources for risk management considered with alternatives | Accountability | 52/100 | 🔴 **MISSING** - No alternative analysis framework |
| **MANAGE 2.2** | Mechanisms to sustain AI system value | Reliability | 72/100 | 🟡 **PARTIAL** - Update mechanisms exist, limited value preservation analysis |
| **MANAGE 2.3** | Procedures to respond to unknown risks | Safety | 61/100 | 🟡 **PARTIAL** - Basic incident handling, no unknown risk procedures |
| **MANAGE 2.4** | Mechanisms to supersede/deactivate AI systems | Accountability | 52/100 | 🟡 **PARTIAL** - API key rotation, limited system deactivation procedures |

## Gap Analysis Summary

### Critical Gaps (Immediate Attention Required):

1. **Governance Framework (GOVERN 1.1-1.7)** - No comprehensive AI governance structure
2. **Bias and Fairness Testing (MEASURE 2.11)** - Critical compliance gap for multiple regulations
3. **Risk Management Process (MANAGE 1.1-1.4)** - No formal risk management procedures  
4. **Diversity and Inclusion (GOVERN 3.1-3.2)** - No requirements for diverse teams or perspectives

### High-Priority Gaps:

5. **AI Training Program (GOVERN 2.2)** - No AI risk management training for personnel
6. **Human Oversight Framework (GOVERN 3.2, MAP 2.2)** - No human-AI collaboration governance
7. **Independent Assessment (MEASURE 1.3)** - No third-party validation process
8. **Explainability Framework (MEASURE 2.9)** - No systematic approach to AI interpretability

### Medium-Priority Gaps:

9. **Environmental Impact (MEASURE 2.12)** - No consideration of environmental sustainability
10. **Incident Response Enhancement (MANAGE 2.3)** - Limited unknown risk response procedures
11. **Risk Communication (GOVERN 4.2)** - No systematic risk communication framework

## Recommended Scoring Enhancements

### New AgentPier Dimensions to Add:

#### **Governance Dimension** (New, 20% weight)
**Rationale:** NIST emphasizes governance as foundational to all other functions

**Proposed Subcategories:**
- **GOV-1:** AI governance charter and policy framework (25% weight)
- **GOV-2:** Risk management process and procedures (25% weight)  
- **GOV-3:** Roles, responsibilities, and training programs (25% weight)
- **GOV-4:** Diversity, inclusion, and human oversight (25% weight)

#### **Explainability Dimension** (New, 5% weight)  
**Rationale:** Critical for regulatory compliance and trust (MEASURE 2.9)

**Proposed Subcategories:**
- **EXP-1:** Model interpretability and transparency (50% weight)
- **EXP-2:** Decision explanation capabilities (50% weight)

#### **Environmental Impact Dimension** (New, 5% weight)
**Rationale:** Increasing regulatory focus on AI sustainability (MEASURE 2.12)

**Proposed Subcategories:**
- **ENV-1:** Energy efficiency assessment and optimization (50% weight)
- **ENV-2:** Carbon footprint measurement and reduction (50% weight)

### Enhanced Existing Dimensions:

#### **Fairness Dimension** (Increase weight from 5% to 15%)
**Enhanced Subcategories:**
- **FAI-1:** Bias detection and testing (40% weight) [Enhanced from current]
- **FAI-2:** Demographic parity and equitable outcomes (35% weight) [New]
- **FAI-3:** Diverse team requirements and inclusive design (25% weight) [New]

#### **Accountability Dimension** (Enhance existing subcategories)
**Enhanced Subcategories:**  
- **ACC-1:** Human oversight and intervention capabilities (30% weight) [Enhanced]
- **ACC-2:** Risk management and response procedures (25% weight) [Enhanced]
- **ACC-3:** Incident reporting and corrective actions (25% weight) [Existing]
- **ACC-4:** Independent assessment and validation (20% weight) [New]

## Implementation Roadmap

### Phase 1: Foundation (Months 1-2)
**Priority:** Establish critical governance framework
- [ ] **GOVERN 1.2** - Develop comprehensive AI policy framework
- [ ] **GOVERN 1.4** - Implement formal risk management process
- [ ] **GOVERN 2.1** - Document roles and responsibilities
- [ ] **MEASURE 2.11** - Implement bias detection and fairness testing

### Phase 2: Enhancement (Months 3-4)  
**Priority:** Build operational capabilities
- [ ] **GOVERN 2.2** - Create AI risk management training program
- [ ] **GOVERN 3.2** - Establish human oversight procedures
- [ ] **MEASURE 1.3** - Implement independent assessment process
- [ ] **MEASURE 2.9** - Develop explainability framework

### Phase 3: Optimization (Months 5-6)
**Priority:** Advanced capabilities and continuous improvement
- [ ] **GOVERN 3.1** - Implement diversity and inclusion requirements
- [ ] **MEASURE 2.12** - Add environmental impact assessment
- [ ] **MANAGE 2.3** - Enhance incident response for unknown risks
- [ ] **GOVERN 4.2** - Create risk communication framework

### Phase 4: Maturity (Months 7-12)
**Priority:** Full NIST AI RMF alignment and optimization
- [ ] Complete all remaining subcategory implementations
- [ ] Conduct comprehensive NIST AI RMF gap assessment
- [ ] Integrate with other compliance frameworks (ISO 42001, EU AI Act)
- [ ] Establish continuous improvement processes

## Cost-Benefit Analysis

### Implementation Costs:

#### Personnel (18 months):
- **Governance Lead:** 1 FTE × 12 months = $180,000
- **Risk Management Specialist:** 1 FTE × 6 months = $90,000
- **ML/AI Engineer (bias testing):** 1 FTE × 4 months = $60,000
- **Technical Writer (documentation):** 0.5 FTE × 8 months = $60,000

#### External Services:
- **NIST AI RMF training and certification:** $15,000
- **Independent assessment services:** $35,000
- **Bias testing tools and platforms:** $25,000
- **Legal and regulatory consultation:** $40,000

#### Technology:
- **Governance and risk management platform:** $30,000
- **Bias detection and fairness testing tools:** $20,000
- **Monitoring and analytics enhancement:** $15,000

**Total Implementation Cost:** ~$570,000

### Expected Benefits:

#### Regulatory Compliance:
- **EU AI Act readiness:** $100,000+ avoided penalties
- **Proactive regulatory posture:** $50,000+ reduced legal costs
- **Industry standard alignment:** $75,000+ reduced audit costs

#### Market Advantages:
- **Enterprise customer acquisition:** $500,000+ revenue opportunity
- **Trust and certification premium:** $200,000+ pricing advantage  
- **Competitive differentiation:** $300,000+ market share protection

#### Risk Mitigation:
- **Bias incident prevention:** $250,000+ avoided reputation costs
- **Security improvement:** $100,000+ avoided breach costs
- **Operational efficiency:** $150,000+ process improvement value

**Total Expected Benefits:** ~$1,725,000 over 3 years

**ROI:** ~300% over 3-year period

## Success Metrics

### Compliance KPIs:
- **90%** coverage of NIST AI RMF subcategories by end of Phase 3
- **<5%** bias detection failure rate in fairness testing
- **100%** of high-risk AI systems undergo independent assessment
- **<1 week** incident response time for unknown risks
- **Zero** regulatory violations related to AI governance

### Business KPIs:  
- **25%** increase in enterprise customer inquiries
- **15%** improvement in agent trust scores
- **30%** reduction in compliance-related support tickets
- **20%** faster time-to-market for new AI features (due to process clarity)
- **10%** improvement in employee AI risk awareness (survey scores)

---

## Next Steps

1. **Week 1:** Present NIST mapping to executive leadership for prioritization decisions
2. **Week 2:** Form AI governance committee with designated roles and responsibilities  
3. **Week 3:** Begin development of AI policy framework and risk management procedures
4. **Month 2:** Start implementation of bias detection and fairness testing capabilities
5. **Month 3:** Launch AI risk management training program for all personnel
6. **Quarterly:** Review progress against implementation roadmap and adjust priorities

**Document Owner:** AgentPier AI Governance Committee  
**Review Cycle:** Monthly during implementation, quarterly post-implementation  
**Next Review:** April 4, 2026  
**Integration Dependencies:** EU AI Act readiness, ISO 42001 mapping, internal risk management processes