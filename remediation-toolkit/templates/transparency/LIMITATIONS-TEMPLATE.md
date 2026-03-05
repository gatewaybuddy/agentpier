# AI Agent Limitations Disclosure Template

**Compliance Framework**: EU AI Act Article 13 (Transparency obligations for providers and deployers of certain AI systems)

## Agent Information
- **Agent Name**: [Your Agent Name]
- **Version**: [Version Number]
- **Last Updated**: [Date]
- **Provider**: [Company/Organization Name]

---

## Known Limitations

### Accuracy Boundaries
**What this means**: Areas where the agent may provide incorrect or incomplete information.

**Current limitations**:
- Language understanding accuracy: ~XX% for [specific domains]
- Factual accuracy cutoff date: [Knowledge cutoff date]
- Cannot verify real-time information or recent events
- May hallucinate plausible but incorrect information
- Limited accuracy in highly specialized domains: [list specific domains]

**Mitigation**: Always verify critical information from authoritative sources.

### Context Window Constraints
**What this means**: The agent can only process a limited amount of information at once.

**Current limitations**:
- Maximum context length: [X tokens/words]
- Cannot maintain memory across separate conversations
- May lose important details in very long conversations
- Cannot access previous conversation history unless explicitly provided

**Mitigation**: Provide key context in each new conversation or session.

### Language and Cultural Limitations
**What this means**: Reduced performance outside primary training languages and cultures.

**Current limitations**:
- Primary languages: [List languages with confidence levels]
- Limited understanding of: [Cultural contexts, regional dialects, slang]
- May exhibit cultural biases from training data
- Translation accuracy varies by language pair

**Mitigation**: Use primary supported languages for critical tasks.

---

## Edge Cases

### Ambiguous Queries
- **Issue**: Vague or multi-interpretable requests may receive incomplete responses
- **Example**: "Help me with my project" without context
- **Recommendation**: Provide specific, clear instructions with context

### Conflicting Information
- **Issue**: When presented with contradictory data, agent may not identify conflicts
- **Example**: Conflicting dates, numbers, or facts in provided materials
- **Recommendation**: Review outputs for consistency and verify facts independently

### Emotional or Sensitive Content
- **Issue**: May not appropriately handle emotional nuance or sensitive situations
- **Example**: Mental health crises, grief counseling, legal advice
- **Recommendation**: Always involve qualified human professionals for sensitive matters

---

## Not Suitable For

### High-Stakes Decision Making
**Prohibited uses**:
- Medical diagnosis or treatment decisions
- Legal advice for court proceedings
- Financial investment decisions without human oversight
- Safety-critical system control
- Emergency response coordination

**Why**: These require human judgment, liability, and regulatory compliance.

### Real-Time Critical Operations
**Prohibited uses**:
- Live trading algorithms
- Emergency dispatch
- Real-time security monitoring
- Time-sensitive safety systems

**Why**: Response delays and potential errors could cause harm.

### Personal Data Processing (Without Safeguards)
**Prohibited uses**:
- Processing PII without explicit consent
- Healthcare data analysis (HIPAA-covered)
- Financial records processing
- Child data processing

**Why**: Privacy regulations and data protection requirements.

---

## Failure Modes

### Complete Response Failure
**Symptoms**: No response, error messages, system timeouts
**Frequency**: <X% of interactions
**Cause**: Overload, network issues, content filtering
**Recovery**: Retry with simplified request, check system status

### Partial Hallucination
**Symptoms**: Confident but incorrect factual statements
**Frequency**: Estimated X-X% for factual queries
**Cause**: Training data gaps, pattern matching without verification
**Recovery**: Cross-reference claims with authoritative sources

### Context Loss
**Symptoms**: Forgetting earlier conversation parts, repetitive responses
**Frequency**: Increases with conversation length
**Cause**: Context window limits
**Recovery**: Summarize key points, restart conversation if necessary

### Bias Amplification
**Symptoms**: Responses reflecting training data biases
**Frequency**: Varies by topic sensitivity
**Cause**: Biased training data or prompt patterns
**Recovery**: Seek diverse perspectives, review for bias

---

## Performance Boundaries

### Response Time Expectations
- **Typical**: 2-5 seconds for simple queries
- **Complex**: 10-30 seconds for analysis tasks
- **Maximum**: 60 seconds before timeout
- **Peak load**: Response times may increase 2-5x

### Throughput Limitations
- **Rate limit**: [X requests per minute/hour]
- **Concurrent users**: [Maximum supported]
- **Resource constraints**: Performance degrades during high usage

### Quality Degradation Scenarios
- **Fatigue**: Performance may decrease over very long sessions
- **Complexity**: Accuracy decreases with highly complex, multi-step tasks
- **Domain expertise**: Lower quality outside core training domains

---

## Monitoring and Updates

### Limitation Tracking
We continuously monitor:
- Error rates by category
- User-reported limitation incidents
- Performance degradation patterns
- New failure modes

### Update Schedule
- **Limitation documentation**: Quarterly review
- **Performance metrics**: Monthly updates
- **Critical limitations**: Immediate disclosure
- **User notification**: 30 days advance notice for material changes

---

## User Responsibilities

### Pre-Use Assessment
- Review these limitations before deployment
- Assess suitability for your specific use case
- Implement appropriate oversight and verification processes

### Ongoing Monitoring
- Monitor outputs for limitation indicators
- Report new limitations or failure modes
- Maintain human oversight for critical applications

### Escalation
- Know when to involve human experts
- Have backup procedures for limitation scenarios
- Maintain alternative tools/processes for prohibited use cases

---

## Compliance Statement

This disclosure fulfills transparency requirements under EU AI Act Article 13(3)(b)(i), which mandates that deployers inform users about the AI system's capabilities and limitations. This document should be reviewed regularly and updated as the system evolves.

**Last Review Date**: [Date]
**Next Scheduled Review**: [Date]

---

## Contact Information

For limitation-related questions or to report new limitations:
- **Email**: [Contact email]
- **Documentation**: [Link to detailed docs]
- **Support**: [Support channel]

*This template complies with EU AI Act Article 13 transparency requirements. Customize all bracketed placeholders for your specific agent.*