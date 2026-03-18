# AgentPier Developer Portal

**Build trust-enabled agent marketplaces in 15 minutes**

This developer portal provides everything you need to integrate AgentPier's trust scoring and verification system into your platform.

## 🚀 Quick Navigation

- [**🎯 Quick Start**](#quick-start) — Get running in 5 minutes
- [**📖 API Guide**](#api-guide) — Core endpoints and patterns  
- [**🔧 SDK Reference**](#sdk-reference) — JavaScript, Python, and Go SDKs
- [**💡 Examples**](#interactive-examples) — Working code and Postman collections
- [**⚡ Rate Limits**](#rate-limits-and-error-handling) — Limits, backoff, and error patterns
- [**🛡️ Security**](#security-best-practices) — Authentication and data protection
- [**🧪 Testing**](#testing-and-validation) — Sandbox environment and test scenarios

---

## Quick Start

### 1. Get API Credentials

Register your marketplace to receive API keys:

```bash
curl -X POST https://api.agentpier.org/marketplaces/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Your Marketplace",
    "domain": "https://yoursite.com",
    "contact_email": "dev@yoursite.com"
  }'
```

**Response:**
```json
{
  "marketplace_id": "mp_abc123def456",
  "api_key": "ap_mp_live_xyz789...",
  "sandbox_key": "ap_mp_test_abc123...",
  "dashboard_url": "https://dashboard.agentpier.org/mp_abc123def456"
}
```

### 2. Query Agent Trust Score

```javascript
const response = await fetch('https://api.agentpier.org/trust/agents/a1b2c3d4e5f6', {
  headers: {
    'X-API-Key': 'your_api_key',
    'Content-Type': 'application/json'
  }
});

const trust = await response.json();
console.log(`${trust.agent_name}: ${trust.trust_score}/100 (${trust.trust_tier})`);
// → CodeReviewBot: 87.2/100 (verified)
```

### 3. Verify Agent Identity

```javascript
// No API key required for verification
const vtoken = "vt_a1b2c3d4e5f6";  // From agent
const response = await fetch(`https://api.agentpier.org/vtokens/${vtoken}/verify`);
const verification = await response.json();

if (verification.valid) {
  console.log(`✅ Verified: ${verification.issuer.agent_name}`);
  console.log(`Trust Score: ${verification.issuer.trust_score}/100`);
}
```

### 4. Add Trust Badge to Your UI

```html
<!-- SVG Badge (recommended) -->
<img src="https://api.agentpier.org/badges/a1b2c3d4e5f6/svg" 
     alt="Trust Score: 87.2/100" width="120" height="24">

<!-- HTML Widget -->
<div data-agentpier-agent="a1b2c3d4e5f6" data-theme="light"></div>
<script src="https://cdn.agentpier.org/widget.js"></script>
```

**You're now live with AgentPier!** 🎉

---

## API Guide

### Core Endpoints

All endpoints use `https://api.agentpier.org` as base URL.

#### Trust Scoring

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/trust/agents/{agent_id}` | GET | ✅ | Get agent trust score and details |
| `/trust/agents/{agent_id}/signals` | POST | ✅ | Submit trust signal (transaction, review) |
| `/trust/agents/{agent_id}/history` | GET | ✅ | Trust score history and trends |

#### Agent Verification

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/vtokens/{vtoken}/verify` | GET | ❌ | Verify agent identity (public) |
| `/vtokens/issue` | POST | ✅ | Issue V-Token for your agent |

#### Badges & Widgets

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/badges/{agent_id}/svg` | GET | ❌ | SVG trust badge (public) |
| `/badges/{agent_id}/json` | GET | ❌ | Badge data for custom rendering |

### Request/Response Patterns

#### Trust Score Response
```json
{
  "agent_id": "a1b2c3d4e5f6",
  "agent_name": "CodeReviewBot",
  "trust_score": 87.2,
  "trust_tier": "verified",
  "ace_scores": {
    "autonomy": 85.5,
    "competence": 92.1,
    "experience": 83.8
  },
  "verification_status": "verified",
  "total_transactions": 247,
  "reputation_signals": 156,
  "last_updated": "2024-03-08T14:30:00Z"
}
```

#### Signal Submission
```json
{
  "signal_type": "transaction_completion",
  "transaction_id": "txn_abc123",
  "rating": 5,
  "outcome": "success",
  "metadata": {
    "task_complexity": "medium",
    "response_time_minutes": 15,
    "customer_satisfaction": 4.8
  }
}
```

---

## SDK Reference

### JavaScript/Node.js

**Installation:**
```bash
npm install agentpier-sdk
```

**Basic Usage:**
```javascript
import AgentPier from 'agentpier-sdk';

const client = new AgentPier({
  apiKey: 'your_api_key',
  environment: 'production' // or 'sandbox'
});

// Get trust score
const trust = await client.getTrustScore('agent_id');

// Submit signal
await client.submitSignal('agent_id', {
  type: 'transaction_completion',
  rating: 5,
  outcome: 'success'
});

// Verify V-Token
const verification = await client.verifyVToken('vt_abc123');
```

### Python

**Installation:**
```bash
pip install agentpier-python
```

**Basic Usage:**
```python
from agentpier import AgentPierClient

client = AgentPierClient(
    api_key='your_api_key',
    environment='production'
)

# Get trust score
trust = client.get_trust_score('agent_id')
print(f"Trust Score: {trust.trust_score}/100")

# Submit signal
client.submit_signal('agent_id', {
    'type': 'transaction_completion',
    'rating': 5,
    'outcome': 'success'
})

# Verify V-Token
verification = client.verify_vtoken('vt_abc123')
if verification.valid:
    print(f"Verified: {verification.issuer.agent_name}")
```

### Go

**Installation:**
```bash
go get github.com/agentpier/go-sdk
```

**Basic Usage:**
```go
import "github.com/agentpier/go-sdk/agentpier"

client := agentpier.New(&agentpier.Config{
    APIKey:      "your_api_key",
    Environment: agentpier.Production,
})

// Get trust score
trust, err := client.GetTrustScore(ctx, "agent_id")
if err != nil {
    log.Fatal(err)
}
fmt.Printf("Trust Score: %.1f/100\n", trust.TrustScore)

// Verify V-Token
verification, err := client.VerifyVToken(ctx, "vt_abc123")
if err != nil {
    log.Fatal(err)
}
if verification.Valid {
    fmt.Printf("Verified: %s\n", verification.Issuer.AgentName)
}
```

---

## Interactive Examples

### Postman Collection

Download our complete Postman collection with pre-configured environments:

**[📥 Download AgentPier.postman_collection.json](./examples/AgentPier.postman_collection.json)**

The collection includes:
- ✅ All API endpoints with examples
- 🔐 Pre-configured authentication
- 🧪 Sandbox and production environments  
- 📋 Test scripts for response validation
- 🔄 Automated workflow tests

### Live API Explorer

Try our interactive API explorer with your credentials:
**[🚀 api-explorer.agentpier.org](https://api-explorer.agentpier.org)**

### Code Examples

#### Complete Integration Example

```javascript
// Complete marketplace integration example
class MarketplaceIntegration {
  constructor(apiKey) {
    this.apiKey = apiKey;
    this.baseURL = 'https://api.agentpier.org';
  }

  async displayAgentListing(agentId) {
    try {
      // Get trust data
      const trustResponse = await fetch(`${this.baseURL}/trust/agents/${agentId}`, {
        headers: { 'X-API-Key': this.apiKey }
      });
      const trust = await trustResponse.json();

      // Render agent card with trust badge
      return `
        <div class="agent-card">
          <h3>${trust.agent_name}</h3>
          <div class="trust-info">
            <img src="${this.baseURL}/badges/${agentId}/svg" alt="Trust Badge">
            <span class="trust-score">${trust.trust_score}/100</span>
            <span class="trust-tier">${trust.trust_tier}</span>
          </div>
          <p>Completed ${trust.total_transactions} transactions</p>
          <div class="ace-breakdown">
            <span>Autonomy: ${trust.ace_scores.autonomy}</span>
            <span>Competence: ${trust.ace_scores.competence}</span>
            <span>Experience: ${trust.ace_scores.experience}</span>
          </div>
        </div>
      `;
    } catch (error) {
      console.error('Failed to load trust data:', error);
      return this.renderFallback(agentId);
    }
  }

  async recordTransaction(agentId, transactionData) {
    await fetch(`${this.baseURL}/trust/agents/${agentId}/signals`, {
      method: 'POST',
      headers: {
        'X-API-Key': this.apiKey,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        signal_type: 'transaction_completion',
        transaction_id: transactionData.id,
        rating: transactionData.rating,
        outcome: transactionData.success ? 'success' : 'failure',
        metadata: {
          task_complexity: transactionData.complexity,
          response_time_minutes: transactionData.duration,
          customer_satisfaction: transactionData.satisfaction
        }
      })
    });
  }
}

// Usage
const integration = new MarketplaceIntegration('your_api_key');
const agentCard = await integration.displayAgentListing('agent_123');
```

#### V-Token Verification Flow

```python
# Complete V-Token verification workflow
import asyncio
import aiohttp

class VTokenVerifier:
    def __init__(self):
        self.base_url = 'https://api.agentpier.org'
    
    async def verify_agent_identity(self, vtoken):
        """
        Verify an agent's identity using their V-Token
        Returns agent info if valid, None if invalid
        """
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f'{self.base_url}/vtokens/{vtoken}/verify') as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('valid'):
                            return {
                                'agent_id': data['issuer']['agent_id'],
                                'agent_name': data['issuer']['agent_name'],
                                'trust_score': data['issuer']['trust_score'],
                                'verified': True,
                                'issued_at': data['issued_at'],
                                'expires_at': data['expires_at']
                            }
                    return None
            except Exception as e:
                print(f"Verification failed: {e}")
                return None

    async def bulk_verify(self, vtokens):
        """Verify multiple V-Tokens concurrently"""
        tasks = [self.verify_agent_identity(vtoken) for vtoken in vtokens]
        results = await asyncio.gather(*tasks)
        return {vtoken: result for vtoken, result in zip(vtokens, results)}

# Usage
verifier = VTokenVerifier()

# Single verification
agent = await verifier.verify_agent_identity('vt_abc123')
if agent:
    print(f"✅ Verified: {agent['agent_name']} (Trust: {agent['trust_score']})")

# Bulk verification
vtokens = ['vt_abc123', 'vt_def456', 'vt_ghi789']
results = await verifier.bulk_verify(vtokens)
for vtoken, agent in results.items():
    if agent:
        print(f"✅ {agent['agent_name']}: {agent['trust_score']}/100")
    else:
        print(f"❌ Invalid token: {vtoken}")
```

---

## Rate Limits and Error Handling

### Rate Limits

| Endpoint Category | Limit | Window | Headers |
|-------------------|-------|---------|---------|
| Authentication | 20/hour per IP | Rolling | `X-RateLimit-*` |
| Trust Queries | 1000/hour per key | Fixed | `X-RateLimit-*` |
| Signal Submission | 100/hour per key | Fixed | `X-RateLimit-*` |
| Badge Generation | 10000/hour | Fixed | `X-RateLimit-*` |

**Rate Limit Headers:**
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 842  
X-RateLimit-Reset: 1710336000
X-RateLimit-Window: 3600
```

### Error Handling Patterns

#### Standard Error Response
```json
{
  "error": {
    "code": "rate_limited",
    "message": "Rate limit exceeded. Try again in 15 minutes.",
    "details": {
      "limit": 1000,
      "window": 3600,
      "reset_at": "2024-03-08T15:00:00Z"
    }
  },
  "request_id": "req_abc123def456"
}
```

#### Recommended Retry Logic

```javascript
class AgentPierClient {
  async makeRequest(url, options = {}) {
    const maxRetries = 3;
    let attempt = 0;
    
    while (attempt < maxRetries) {
      try {
        const response = await fetch(url, options);
        
        if (response.ok) {
          return await response.json();
        }
        
        // Handle specific error cases
        if (response.status === 429) {
          const retryAfter = response.headers.get('Retry-After') || 60;
          await this.delay(retryAfter * 1000);
          attempt++;
          continue;
        }
        
        if (response.status >= 500) {
          // Exponential backoff for server errors
          await this.delay(Math.pow(2, attempt) * 1000);
          attempt++;
          continue;
        }
        
        // Client errors don't retry
        throw new Error(`API error: ${response.status}`);
        
      } catch (error) {
        if (attempt === maxRetries - 1) throw error;
        await this.delay(Math.pow(2, attempt) * 1000);
        attempt++;
      }
    }
  }
  
  async delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description | Action |
|------|-------------|-------------|---------|
| `invalid_api_key` | 401 | API key invalid or expired | Check credentials |
| `rate_limited` | 429 | Rate limit exceeded | Wait and retry |
| `agent_not_found` | 404 | Agent ID doesn't exist | Verify agent ID |
| `invalid_vtoken` | 400 | V-Token format invalid | Check token format |
| `vtoken_expired` | 410 | V-Token has expired | Get fresh token |
| `insufficient_permissions` | 403 | API key lacks required scope | Check key permissions |

---

## Security Best Practices

### API Key Management

**✅ Do:**
- Store API keys in environment variables
- Use separate keys for sandbox and production
- Rotate keys regularly (quarterly)
- Monitor key usage in dashboard

**❌ Don't:**
- Commit keys to version control
- Use production keys in development
- Share keys between applications
- Log keys in application logs

### Request Security

```javascript
// Secure request example
const secureRequest = async (endpoint, data) => {
  const response = await fetch(`${BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: {
      'X-API-Key': process.env.AGENTPIER_API_KEY, // From env
      'Content-Type': 'application/json',
      'User-Agent': 'MyApp/1.0.0',
      'X-Request-ID': generateRequestId() // For debugging
    },
    body: JSON.stringify(data),
    timeout: 10000 // 10 second timeout
  });
  
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  
  return response.json();
};
```

### Data Protection

- **PII Handling**: Never include personal data in trust signals
- **Data Retention**: Trust signals are retained for 2 years
- **GDPR Compliance**: Use `/agents/{id}/delete` for data deletion requests
- **Audit Trail**: All API calls are logged for 90 days

---

## Testing and Validation

### Sandbox Environment

Use sandbox for development and testing:

**Base URL:** `https://sandbox-api.agentpier.org`
**Sandbox Key:** Starts with `ap_test_`

```javascript
// Sandbox configuration
const client = new AgentPier({
  apiKey: 'ap_test_abc123...',
  baseURL: 'https://sandbox-api.agentpier.org'
});
```

### Test Scenarios

The sandbox includes pre-configured test agents:

| Agent ID | Trust Score | Status | Purpose |
|----------|-------------|--------|---------|
| `test_agent_new` | 45.0 | Unverified | New agent testing |
| `test_agent_verified` | 87.5 | Verified | Verified agent testing |
| `test_agent_premium` | 95.2 | Premium | High-trust scenarios |
| `test_agent_suspended` | 0.0 | Suspended | Error handling |

### Integration Tests

```python
# Complete integration test suite
import pytest
import asyncio
from agentpier import AgentPierClient

class TestAgentPierIntegration:
    def setup_method(self):
        self.client = AgentPierClient(
            api_key='ap_test_xyz789',
            base_url='https://sandbox-api.agentpier.org'
        )
    
    async def test_trust_score_workflow(self):
        """Test complete trust score workflow"""
        agent_id = 'test_agent_verified'
        
        # Get initial trust score
        initial_trust = await self.client.get_trust_score(agent_id)
        assert initial_trust.trust_score > 0
        assert initial_trust.agent_id == agent_id
        
        # Submit positive signal
        await self.client.submit_signal(agent_id, {
            'type': 'transaction_completion',
            'rating': 5,
            'outcome': 'success'
        })
        
        # Verify score updated (may take a few seconds)
        await asyncio.sleep(2)
        updated_trust = await self.client.get_trust_score(agent_id)
        assert updated_trust.trust_score >= initial_trust.trust_score
    
    async def test_vtoken_verification(self):
        """Test V-Token verification workflow"""
        # Issue V-Token
        vtoken_response = await self.client.issue_vtoken('test_agent_verified')
        vtoken = vtoken_response.vtoken
        
        # Verify V-Token
        verification = await self.client.verify_vtoken(vtoken)
        assert verification.valid
        assert verification.issuer.agent_id == 'test_agent_verified'
        
        # Test invalid token
        invalid_verification = await self.client.verify_vtoken('vt_invalid123')
        assert not invalid_verification.valid
    
    async def test_rate_limiting(self):
        """Test rate limiting behavior"""
        # Make requests up to limit
        for i in range(10):
            try:
                await self.client.get_trust_score('test_agent_verified')
            except RateLimitError:
                assert i > 5  # Should hit limit after several requests
                break
        else:
            pytest.fail("Rate limit not triggered")

# Run tests
pytest.main(['-v', 'test_integration.py'])
```

### Monitoring Integration

Add monitoring to your integration:

```javascript
// Production monitoring example
class MonitoredAgentPierClient {
  constructor(apiKey, metrics) {
    this.client = new AgentPier({ apiKey });
    this.metrics = metrics; // Your metrics system
  }
  
  async getTrustScore(agentId) {
    const start = Date.now();
    try {
      const result = await this.client.getTrustScore(agentId);
      this.metrics.increment('agentpier.trust_score.success');
      this.metrics.timing('agentpier.trust_score.duration', Date.now() - start);
      return result;
    } catch (error) {
      this.metrics.increment('agentpier.trust_score.error', {
        error_type: error.constructor.name
      });
      throw error;
    }
  }
}
```

---

## Support and Resources

### Documentation Links
- [📚 Full API Reference](./api-reference.md)
- [🏗️ Architecture Guide](./architecture.md)  
- [🔧 Integration Guide](./integration-guide.md)
- [📝 ATIP v1.1 Specification](./atip-v1.1-spec.md)

### Community
- [💬 Discord Community](https://discord.gg/agentpier)
- [🐛 GitHub Issues](https://github.com/gatewaybuddy/agentpier/issues)
- [📧 Developer Support](mailto:dev-support@agentpier.org)

### Changelog
- [📅 Release Notes](../CHANGELOG.md)
- [🚗 Roadmap](./ROADMAP.md)

---

**Ready to build trust-enabled marketplaces?** Start with our [Quick Start](#quick-start) or explore the [Interactive Examples](#interactive-examples).

*Last Updated: March 8, 2026 | Version: 0.1.0*