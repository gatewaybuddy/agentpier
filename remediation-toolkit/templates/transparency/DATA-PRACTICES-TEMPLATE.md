# AI Agent Data Practices Disclosure Template

**Compliance Framework**: ISO/IEC 42001:2023 Clause 7.5 (Documented information management) and GDPR Article 13-14 (Information to be provided)

## Service Information
- **Service Name**: [Your AI Agent Service]
- **Data Controller**: [Company/Organization Name]
- **Data Protection Officer**: [Contact Information]
- **Last Updated**: [Date]
- **Version**: [Document Version]

---

## Data Collection Practices

### What Data We Collect

**Interaction Data** (Required for service operation):
- User queries and prompts submitted to the agent
- Agent responses and generated content
- Conversation metadata (timestamps, session IDs)
- Error logs and system diagnostic information

**Technical Data** (Automatically collected):
- IP address and general location (country/region)
- Browser type and version
- Device type and operating system
- API usage patterns and frequency
- Performance metrics (response times, success rates)

**Account Data** (If registration required):
- Username/identifier
- Contact information (email)
- Account preferences and settings
- Subscription/usage plan information

**Optional Enhancement Data** (User-provided):
- Custom instructions or preferences
- File uploads for processing
- Integration credentials (encrypted)
- Feedback and ratings

### Data We Do NOT Collect
- Biometric identifiers
- Financial account numbers (unless explicitly provided for processing)
- Health records or medical information
- Government-issued identification numbers
- Children's personal data (under 13/16 depending on jurisdiction)

---

## Data Storage and Security

### Storage Infrastructure
**Primary Storage**:
- **Location**: [Geographic regions - e.g., US East, EU West]
- **Provider**: [Cloud provider name and certification status]
- **Backup locations**: [Geographic backup regions]
- **Data residency controls**: Available upon request for enterprise customers

**Storage Duration by Data Type**:
| Data Type | Retention Period | Justification |
|-----------|------------------|---------------|
| Conversation logs | 30 days | Service improvement, debugging |
| Account information | Until account deletion | Account management |
| Aggregated analytics | 2 years | Service optimization |
| Error logs | 90 days | Technical support |
| Backup data | 30 days after primary deletion | Disaster recovery |

### Security Measures
**Encryption**:
- **In transit**: TLS 1.3 minimum for all communications
- **At rest**: AES-256 encryption for all stored data
- **Key management**: Hardware Security Modules (HSMs) with key rotation

**Access Controls**:
- Role-based access control (RBAC)
- Multi-factor authentication required for all staff
- Regular access reviews (quarterly)
- Audit logging for all data access

**Security Monitoring**:
- 24/7 security operations center (SOC)
- Automated threat detection and response
- Regular penetration testing (annually)
- Vulnerability scanning (weekly)

---

## Data Processing Purposes

### Primary Purposes
1. **Service Delivery**: Providing AI agent responses to user queries
2. **Quality Assurance**: Monitoring and improving response quality
3. **Technical Support**: Debugging issues and providing customer support
4. **Safety and Compliance**: Detecting harmful content and ensuring policy compliance

### Secondary Purposes (With Consent)
1. **Service Improvement**: Training models and improving agent capabilities
2. **Analytics**: Understanding usage patterns and optimizing performance
3. **Marketing**: Sending service updates and relevant information (opt-in)
4. **Research**: Contributing to AI safety and capability research (anonymized)

### Legal Basis (GDPR)
- **Legitimate Interest**: Service delivery, security, and improvement
- **Contract**: Account management and subscription services
- **Consent**: Marketing communications and optional features
- **Legal Obligation**: Compliance with applicable laws and regulations

---

## Data Sharing and Third Parties

### Third-Party Data Processors
**Infrastructure Providers**:
- [Cloud Provider Name]: Hosting and infrastructure services
- Data Processing Agreement (DPA) in place: ✅
- GDPR/Privacy Shield compliance: ✅

**Service Providers**:
- [Analytics Provider]: Usage analytics (anonymized data only)
- [Support Platform]: Customer support and ticketing
- [Payment Processor]: Billing and payment processing

### Data Sharing Scenarios
**We share data only in these circumstances**:
1. **With explicit user consent**: For integrations or specific features
2. **Legal requirements**: Court orders, law enforcement requests
3. **Service providers**: As listed above, under strict contractual protections
4. **Business transitions**: Mergers or acquisitions (with user notification)

**We NEVER**:
- Sell personal data to third parties
- Share data with advertisers
- Use data for unrelated commercial purposes
- Process data in countries without adequate protections (without safeguards)

---

## Data Retention Policy

### Retention Principles
1. **Purpose Limitation**: Data retained only as long as necessary for stated purposes
2. **Legal Requirements**: Compliance with applicable retention laws
3. **User Control**: Users can request deletion at any time
4. **Automatic Deletion**: Automated processes for expired data

### Retention Schedule
**Active User Data**:
- Conversation history: 30 days (user-configurable)
- Account data: Duration of active account
- Usage logs: 1 year for analytics, then aggregated only

**Inactive Account Data**:
- Account closure: 30 days to complete deletion
- Inactive accounts: 3 years notice, then deletion
- Backup data: 30 days after primary deletion

### Data Minimization
- Regular data audits to identify unnecessary retention
- Automatic anonymization where possible
- Compression and archival for long-term stored data

---

## User Data Rights

### Access Rights
**What you can access**:
- All personal data we hold about you
- Processing purposes and legal basis
- Data sharing history
- Retention periods

**How to request**: [Email/Portal/API endpoint]

### Correction and Updates
**Data correction process**:
1. Submit correction request through [method]
2. Verification of identity required
3. Response within 72 hours
4. Updates implemented within 30 days

### Data Portability
**Available formats**:
- JSON export of all user data
- CSV format for structured data
- API access for automated retrieval

**Process**: Request through user account settings or contact support

### Deletion Rights
**Complete Account Deletion**:
- Request through account settings or support
- Verification required for security
- Completion within 30 days
- Confirmation provided upon completion

**Selective Data Deletion**:
- Specific conversation or session deletion
- Custom retention period settings
- Immediate processing for most data types

---

## Data Processing Controls

### User Control Features
**Privacy Dashboard**:
- View all data processing activities
- Configure retention periods
- Manage data sharing preferences
- Download or delete data

**Granular Controls**:
- Conversation-level privacy settings
- Optional data enhancement features
- Integration-specific permissions
- Marketing communication preferences

### Processing Transparency
**Activity Logs**:
- All data processing activities logged
- User-accessible audit trail
- Automated anomaly detection
- Regular compliance reporting

---

## International Transfers

### Transfer Mechanisms
**Adequacy Decisions**: 
- Transfers to countries with GDPR adequacy decisions
- List of approved countries: [Country list]

**Standard Contractual Clauses (SCCs)**:
- EU Commission approved SCCs for other transfers
- Additional safeguards implemented as required
- Transfer Impact Assessments conducted

### Data Localization Options
**Enterprise Features**:
- Data residency controls available
- Single-region processing options
- On-premises deployment available
- Hybrid cloud architectures supported

---

## Incident Response and Notification

### Data Breach Response
**Detection and Assessment**:
- 24-hour breach detection target
- Risk assessment within 12 hours
- Containment measures implemented immediately

**Notification Timeline**:
- Supervisory authority: 72 hours maximum
- Affected users: Without undue delay
- Public disclosure: As required by law

### User Notification
**Breach notification includes**:
- Nature of the breach
- Data types involved
- Likely consequences
- Measures taken
- Contact information for further questions

---

## Compliance Monitoring

### Regular Assessments
**Internal Audits**: Quarterly data handling practice reviews
**External Audits**: Annual third-party privacy assessments
**Certification Maintenance**: [List relevant certifications]

### Metrics and KPIs
- Data processing accuracy rates
- Response times for user requests
- Security incident frequency
- Compliance training completion rates

### Continuous Improvement
- Regular policy updates based on legal changes
- User feedback integration
- Technology updates for enhanced privacy
- Staff training and awareness programs

---

## Contact Information

### Data Protection Contacts
**Data Protection Officer**: [Name, Email, Phone]
**Privacy Team**: [Email address]
**General Support**: [Support contact]

### Regulatory Contacts
**EU Representative**: [If applicable]
**UK Representative**: [If applicable]
**Local Data Protection Authorities**: [Links to relevant authorities]

---

## Legal Framework Compliance

### Applicable Regulations
- **GDPR** (General Data Protection Regulation)
- **CCPA** (California Consumer Privacy Act)
- **ISO/IEC 42001:2023** (AI Management Systems)
- **[Other applicable local privacy laws]**

### Regular Review Schedule
- **Quarterly**: Policy effectiveness review
- **Annually**: Comprehensive legal compliance audit
- **Ad-hoc**: Updates for new regulations or significant changes

---

**This disclosure complies with ISO/IEC 42001 Clause 7.5 requirements for documented information management and transparency obligations under various privacy regulations. Customize all bracketed placeholders for your specific service.**

**Document Control**: [Version] | [Date] | [Approved by] | [Next review date]