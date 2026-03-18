# AgentPier Integration Examples

This directory contains comprehensive examples and tools for integrating AgentPier's trust scoring and verification system into your applications.

## 📁 Contents

| File | Description | Language |
|------|-------------|----------|
| [**developer-portal.md**](../developer-portal.md) | Complete developer documentation with guides and reference | Documentation |
| [**AgentPier.postman_collection.json**](./AgentPier.postman_collection.json) | Postman collection with all API endpoints | Postman |
| [**AgentPier.postman_environment.json**](./AgentPier.postman_environment.json) | Postman environment variables | Postman |
| [**integration-examples.js**](./integration-examples.js) | Complete JavaScript/Node.js integration examples | JavaScript |
| [**integration-examples.py**](./integration-examples.py) | Complete Python integration examples | Python |
| [**README.md**](./README.md) | This documentation file | Documentation |

## 🚀 Quick Start

### 1. Set Up API Key

Get your API key by registering your marketplace:

```bash
curl -X POST https://api.agentpier.org/marketplaces/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Your Marketplace",
    "domain": "https://yoursite.com",
    "contact_email": "dev@yoursite.com"
  }'
```

Set your API key as an environment variable:

```bash
export AGENTPIER_API_KEY="your_api_key_here"
```

### 2. Choose Your Integration Method

#### Option A: Postman Collection (Recommended for API Exploration)

1. Import `AgentPier.postman_collection.json` into Postman
2. Import `AgentPier.postman_environment.json` for environment variables
3. Set your `api_key` in the environment
4. Start testing endpoints interactively

#### Option B: JavaScript/Node.js

```bash
# Install dependencies (Node.js 16+)
npm install node-fetch  # if using Node < 18

# Run examples
node integration-examples.js
```

#### Option C: Python

```bash
# Install dependencies
pip install aiohttp

# Run examples
python integration-examples.py
```

## 📖 Example Categories

### 1. Basic Trust Score Queries
- Single agent trust score lookup
- Bulk trust score queries
- Trust score history and trends

### 2. V-Token Identity Verification
- Issue V-Tokens for agent identity proof
- Verify V-Tokens from other agents
- Handle expired/invalid tokens

### 3. Trust Signal Processing
- Submit transaction completion signals
- Record user feedback and reviews
- Update trust scores based on performance

### 4. Badge Integration
- Generate trust badges (SVG format)
- Embed badges in web applications
- Custom badge styling and themes

### 5. Marketplace Integration
- Complete agent listing functionality
- Transaction workflow processing
- Error handling and retry logic
- Caching strategies for performance

### 6. Error Handling
- Rate limiting scenarios
- Network timeout handling
- Invalid API key responses
- Agent not found cases

## 🔧 Integration Patterns

### Simple Trust Score Display

```javascript
// Get and display trust score
const trust = await client.getTrustScore('agent_123');
console.log(`${trust.agent_name}: ${trust.trust_score}/100`);
```

### Marketplace Listing

```javascript
// Bulk load trust scores for marketplace
const agents = await client.getBulkTrustScores(['agent_1', 'agent_2', 'agent_3']);
agents.forEach(agent => {
  console.log(`${agent.agent_name}: ${agent.trust_score}/100`);
});
```

### Transaction Recording

```javascript
// Record completed transaction
await client.submitTrustSignal('agent_123', {
  signal_type: 'transaction_completion',
  rating: 5,
  outcome: 'success',
  metadata: { task_complexity: 'high' }
});
```

### Identity Verification

```javascript
// Verify agent identity with V-Token
const verification = await client.verifyVToken('vt_abc123');
if (verification.valid) {
  console.log(`Verified: ${verification.issuer.agent_name}`);
}
```

## 🛡️ Security Best Practices

### API Key Management
- **Store securely**: Use environment variables, never hardcode
- **Rotate regularly**: Generate new keys quarterly  
- **Scope appropriately**: Use separate keys for different environments
- **Monitor usage**: Track API calls in AgentPier dashboard

### Request Security
- **Timeout handling**: Set reasonable timeouts (10-30 seconds)
- **Retry logic**: Implement exponential backoff for failures
- **Error logging**: Log errors but never log API keys
- **Rate limiting**: Respect rate limits and handle 429 responses

### Data Protection
- **PII handling**: Never include personal data in trust signals
- **Data retention**: Trust signals retained for 2 years
- **GDPR compliance**: Use deletion endpoints for data removal requests

## ⚡ Performance Optimization

### Caching Strategies
```javascript
// Cache trust scores for 5 minutes
const cache = new Map();
const CACHE_TIMEOUT = 300000; // 5 minutes

async function getCachedTrustScore(agentId) {
  const cached = cache.get(agentId);
  if (cached && Date.now() - cached.timestamp < CACHE_TIMEOUT) {
    return cached.data;
  }
  
  const trust = await client.getTrustScore(agentId);
  cache.set(agentId, { data: trust, timestamp: Date.now() });
  return trust;
}
```

### Bulk Operations
```javascript
// Load multiple agents efficiently
const agentIds = ['agent_1', 'agent_2', 'agent_3'];
const bulkResponse = await client.getBulkTrustScores(agentIds);
// 1 API call instead of 3
```

### Badge Optimization
```html
<!-- Use CDN-cached SVG badges -->
<img src="https://api.agentpier.org/badges/agent_123/svg" 
     alt="Trust Score" 
     loading="lazy">
```

## 🧪 Testing

### Test Agents

The sandbox environment includes pre-configured test agents:

| Agent ID | Trust Score | Status | Use Case |
|----------|-------------|--------|----------|
| `test_agent_new` | 45.0 | Unverified | New agent scenarios |
| `test_agent_verified` | 87.5 | Verified | Standard operations |
| `test_agent_premium` | 95.2 | Premium | High-trust scenarios |
| `test_agent_suspended` | 0.0 | Suspended | Error handling |

### Test Scenarios

```javascript
// Test all scenarios
const testCases = [
  { agentId: 'test_agent_verified', expected: 'success' },
  { agentId: 'invalid_agent', expected: 'not_found' },
  { agentId: 'test_agent_suspended', expected: 'suspended' }
];

for (const test of testCases) {
  try {
    const result = await client.getTrustScore(test.agentId);
    console.log(`✅ ${test.agentId}: Success`);
  } catch (error) {
    console.log(`❌ ${test.agentId}: ${error.code}`);
  }
}
```

## 🔗 Related Documentation

- [**Developer Portal**](../developer-portal.md) - Complete integration guide
- [**API Reference**](../api-reference.md) - Detailed endpoint documentation  
- [**Architecture Guide**](../architecture.md) - System design and concepts
- [**ATIP v1.1 Specification**](../atip-v1.1-spec.md) - Trust scoring methodology

## 💬 Support

### Community Resources
- [💬 Discord Community](https://discord.gg/agentpier)
- [🐛 GitHub Issues](https://github.com/gatewaybuddy/agentpier/issues)
- [📧 Developer Support](mailto:dev-support@agentpier.org)

### Documentation Updates
- [📅 Release Notes](../../CHANGELOG.md)
- [🚗 Roadmap](../ROADMAP.md)

## 📄 License

These examples are provided under the Apache 2.0 License. See the main repository LICENSE file for details.

---

**Ready to integrate AgentPier?** Start with the [Postman collection](./AgentPier.postman_collection.json) or run the [JavaScript examples](./integration-examples.js) to see the API in action.

*Last Updated: March 8, 2026 | Version: 0.1.0*