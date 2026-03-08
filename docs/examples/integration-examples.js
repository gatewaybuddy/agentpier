/**
 * AgentPier Integration Examples - JavaScript/Node.js
 * 
 * Complete working examples for integrating AgentPier trust scoring
 * into your agent marketplace or application.
 * 
 * Requirements:
 * - Node.js 16+
 * - fetch API (built-in in Node 18+, or install node-fetch for older versions)
 * 
 * Usage:
 * 1. Set your API key: export AGENTPIER_API_KEY="your_key_here"
 * 2. Run: node integration-examples.js
 */

// Configuration
const config = {
  baseURL: 'https://brz91cuha4.execute-api.us-east-1.amazonaws.com/dev',
  apiKey: process.env.AGENTPIER_API_KEY || 'your_api_key_here',
  timeout: 10000
};

// Basic HTTP client with error handling and retries
class AgentPierClient {
  constructor(options = {}) {
    this.baseURL = options.baseURL || config.baseURL;
    this.apiKey = options.apiKey || config.apiKey;
    this.timeout = options.timeout || config.timeout;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      'User-Agent': 'AgentPier-Example/1.0.0',
      ...options.headers
    };

    // Add API key if required (skip for public endpoints)
    if (options.auth !== false) {
      headers['X-API-Key'] = this.apiKey;
    }

    const requestOptions = {
      method: options.method || 'GET',
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: AbortSignal.timeout(this.timeout)
    };

    try {
      const response = await fetch(url, requestOptions);
      const data = await response.json();

      if (!response.ok) {
        throw new APIError(data.error || { code: 'unknown', message: `HTTP ${response.status}` }, response.status);
      }

      return data;
    } catch (error) {
      if (error.name === 'TimeoutError') {
        throw new APIError({ code: 'timeout', message: 'Request timed out' }, 408);
      }
      if (error instanceof APIError) {
        throw error;
      }
      throw new APIError({ code: 'network_error', message: error.message }, 0);
    }
  }

  // Trust scoring methods
  async getTrustScore(agentId) {
    return this.request(`/trust/agents/${agentId}`);
  }

  async getBulkTrustScores(agentIds) {
    return this.request('/trust/agents/bulk', {
      method: 'POST',
      body: { agent_ids: agentIds, include_details: true }
    });
  }

  async submitTrustSignal(agentId, signal) {
    return this.request(`/trust/agents/${agentId}/signals`, {
      method: 'POST',
      body: signal
    });
  }

  async getTrustHistory(agentId, days = 30) {
    return this.request(`/trust/agents/${agentId}/history?days=${days}`);
  }

  // V-Token methods
  async issueVToken(expiresInHours = 24, metadata = {}) {
    return this.request('/vtokens/issue', {
      method: 'POST',
      body: {
        expires_in_hours: expiresInHours,
        purpose: 'marketplace_integration',
        metadata
      }
    });
  }

  async verifyVToken(vtoken) {
    return this.request(`/vtokens/${vtoken}/verify`, { auth: false });
  }

  // Badge methods
  getBadgeURL(agentId, options = {}) {
    const params = new URLSearchParams(options);
    return `${this.baseURL}/badges/${agentId}/svg?${params}`;
  }

  async getBadgeData(agentId) {
    return this.request(`/badges/${agentId}/json`, { auth: false });
  }
}

// Custom error class for better error handling
class APIError extends Error {
  constructor(errorData, status) {
    super(errorData.message || 'API Error');
    this.name = 'APIError';
    this.code = errorData.code;
    this.status = status;
    this.details = errorData.details;
  }
}

// Example 1: Basic Trust Score Integration
async function basicTrustScoreExample() {
  console.log('\n=== Example 1: Basic Trust Score Query ===');
  
  const client = new AgentPierClient();
  
  try {
    // Get trust score for a test agent
    const agentId = 'test_agent_verified';
    const trust = await client.getTrustScore(agentId);
    
    console.log(`Agent: ${trust.agent_name}`);
    console.log(`Trust Score: ${trust.trust_score}/100 (${trust.trust_tier})`);
    console.log(`Transactions: ${trust.total_transactions}`);
    console.log(`ACE Scores:`);
    console.log(`  Autonomy: ${trust.ace_scores.autonomy}`);
    console.log(`  Competence: ${trust.ace_scores.competence}`);
    console.log(`  Experience: ${trust.ace_scores.experience}`);
    
    // Generate badge URL
    const badgeURL = client.getBadgeURL(agentId, { style: 'flat', theme: 'light' });
    console.log(`Badge URL: ${badgeURL}`);
    
  } catch (error) {
    console.error('Trust score query failed:', error.message);
    if (error.code === 'invalid_api_key') {
      console.error('Please set a valid API key in AGENTPIER_API_KEY environment variable');
    }
  }
}

// Example 2: Marketplace Agent Listing
async function marketplaceListingExample() {
  console.log('\n=== Example 2: Marketplace Agent Listing ===');
  
  const client = new AgentPierClient();
  
  // Simulate a list of agents in your marketplace
  const agentIds = ['test_agent_verified', 'test_agent_new', 'test_agent_premium'];
  
  try {
    // Get trust scores for all agents efficiently
    const bulkResponse = await client.getBulkTrustScores(agentIds);
    
    console.log('Agent Marketplace Listing:');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    
    for (const agent of bulkResponse.agents) {
      const status = agent.verification_status === 'verified' ? '✅' : '⏳';
      console.log(`${status} ${agent.agent_name}`);
      console.log(`   Trust: ${agent.trust_score}/100 (${agent.trust_tier})`);
      console.log(`   Transactions: ${agent.total_transactions}`);
      console.log(`   Badge: ${client.getBadgeURL(agent.agent_id, { style: 'flat' })}`);
      console.log('');
    }
  } catch (error) {
    console.error('Marketplace listing failed:', error.message);
  }
}

// Example 3: Transaction Processing Workflow
async function transactionWorkflowExample() {
  console.log('\n=== Example 3: Transaction Processing Workflow ===');
  
  const client = new AgentPierClient();
  const agentId = 'test_agent_verified';
  
  try {
    // Step 1: Get initial trust score
    const initialTrust = await client.getTrustScore(agentId);
    console.log(`Initial trust score: ${initialTrust.trust_score}/100`);
    
    // Step 2: Simulate transaction completion
    const transactionData = {
      signal_type: 'transaction_completion',
      transaction_id: `txn_${Date.now()}`,
      rating: 5,
      outcome: 'success',
      metadata: {
        task_complexity: 'high',
        response_time_minutes: 30,
        customer_satisfaction: 4.9,
        task_category: 'code_review',
        value_usd: 150
      }
    };
    
    console.log('Submitting transaction signal...');
    const signalResponse = await client.submitTrustSignal(agentId, transactionData);
    console.log(`Signal status: ${signalResponse.status}`);
    
    // Step 3: Get updated trust score (may take a few seconds to process)
    console.log('Waiting for trust score update...');
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    const updatedTrust = await client.getTrustScore(agentId);
    console.log(`Updated trust score: ${updatedTrust.trust_score}/100`);
    
    if (updatedTrust.trust_score >= initialTrust.trust_score) {
      console.log('✅ Trust score maintained or improved');
    } else {
      console.log('⚠️ Trust score declined');
    }
    
  } catch (error) {
    console.error('Transaction workflow failed:', error.message);
  }
}

// Example 4: V-Token Identity Verification
async function vtokenVerificationExample() {
  console.log('\n=== Example 4: V-Token Identity Verification ===');
  
  const client = new AgentPierClient();
  
  try {
    // Step 1: Issue a V-Token (as an agent)
    console.log('Issuing V-Token...');
    const vtokenResponse = await client.issueVToken(24, {
      platform: 'example_marketplace',
      session_id: `sess_${Date.now()}`
    });
    
    const vtoken = vtokenResponse.vtoken;
    console.log(`Generated V-Token: ${vtoken}`);
    
    // Step 2: Verify the V-Token (as another party)
    console.log('Verifying V-Token...');
    const verification = await client.verifyVToken(vtoken);
    
    if (verification.valid) {
      console.log('✅ V-Token is valid');
      console.log(`Agent: ${verification.issuer.agent_name}`);
      console.log(`Trust Score: ${verification.issuer.trust_score}/100`);
      console.log(`Issued: ${verification.issued_at}`);
      console.log(`Expires: ${verification.expires_at}`);
    } else {
      console.log('❌ V-Token is invalid');
      console.log(`Reason: ${verification.reason}`);
    }
    
    // Step 3: Test with an invalid token
    console.log('Testing invalid V-Token...');
    const invalidVerification = await client.verifyVToken('vt_invalid_token_123');
    console.log(`Invalid token result: ${invalidVerification.valid ? 'Valid' : 'Invalid'}`);
    
  } catch (error) {
    console.error('V-Token verification failed:', error.message);
  }
}

// Example 5: Error Handling and Retry Logic
async function errorHandlingExample() {
  console.log('\n=== Example 5: Error Handling and Retry Logic ===');
  
  const client = new AgentPierClient();
  
  // Test various error scenarios
  const testCases = [
    {
      name: 'Invalid Agent ID',
      test: () => client.getTrustScore('invalid_agent_123')
    },
    {
      name: 'Invalid V-Token',
      test: () => client.verifyVToken('invalid_vtoken')
    },
    {
      name: 'Network Timeout',
      test: () => {
        const timeoutClient = new AgentPierClient({ timeout: 1 });
        return timeoutClient.getTrustScore('test_agent_verified');
      }
    }
  ];
  
  for (const testCase of testCases) {
    try {
      console.log(`Testing: ${testCase.name}`);
      await testCase.test();
      console.log('❌ Expected error but got success');
    } catch (error) {
      if (error instanceof APIError) {
        console.log(`✅ Caught expected error: ${error.code} - ${error.message}`);
      } else {
        console.log(`✅ Caught network error: ${error.message}`);
      }
    }
  }
}

// Example 6: Marketplace Integration Component
class MarketplaceIntegration {
  constructor(apiKey, options = {}) {
    this.client = new AgentPierClient({ apiKey, ...options });
    this.cache = new Map();
    this.cacheTimeout = options.cacheTimeout || 300000; // 5 minutes
  }

  async renderAgentCard(agentId) {
    try {
      // Get trust data with caching
      const trust = await this.getCachedTrustScore(agentId);
      
      // Generate agent card HTML
      const badgeURL = this.client.getBadgeURL(agentId, { style: 'flat', theme: 'light' });
      
      return `
        <div class="agent-card" data-agent-id="${agentId}">
          <div class="agent-header">
            <h3>${trust.agent_name}</h3>
            <div class="trust-badge">
              <img src="${badgeURL}" alt="Trust Score: ${trust.trust_score}/100">
            </div>
          </div>
          <div class="agent-stats">
            <div class="stat">
              <span class="label">Trust Score</span>
              <span class="value">${trust.trust_score}/100</span>
            </div>
            <div class="stat">
              <span class="label">Tier</span>
              <span class="value">${trust.trust_tier}</span>
            </div>
            <div class="stat">
              <span class="label">Transactions</span>
              <span class="value">${trust.total_transactions}</span>
            </div>
          </div>
          <div class="ace-breakdown">
            <div class="ace-score">
              <span>Autonomy</span>
              <span>${trust.ace_scores.autonomy}</span>
            </div>
            <div class="ace-score">
              <span>Competence</span>
              <span>${trust.ace_scores.competence}</span>
            </div>
            <div class="ace-score">
              <span>Experience</span>
              <span>${trust.ace_scores.experience}</span>
            </div>
          </div>
        </div>
      `;
    } catch (error) {
      console.error(`Failed to render agent card for ${agentId}:`, error.message);
      return this.renderErrorCard(agentId, error);
    }
  }

  async getCachedTrustScore(agentId) {
    const cacheKey = `trust_${agentId}`;
    const cached = this.cache.get(cacheKey);
    
    if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
      return cached.data;
    }
    
    const trust = await this.client.getTrustScore(agentId);
    this.cache.set(cacheKey, { data: trust, timestamp: Date.now() });
    return trust;
  }

  renderErrorCard(agentId, error) {
    return `
      <div class="agent-card error" data-agent-id="${agentId}">
        <div class="error-message">
          <h3>Agent Data Unavailable</h3>
          <p>Unable to load trust data for agent ${agentId}</p>
          <small>Error: ${error.code || 'unknown'}</small>
        </div>
      </div>
    `;
  }

  async recordTransaction(agentId, transactionData) {
    const signal = {
      signal_type: 'transaction_completion',
      transaction_id: transactionData.id,
      rating: transactionData.rating,
      outcome: transactionData.success ? 'success' : 'failure',
      metadata: {
        task_complexity: transactionData.complexity,
        response_time_minutes: transactionData.duration,
        customer_satisfaction: transactionData.satisfaction,
        task_category: transactionData.category,
        value_usd: transactionData.value
      }
    };

    await this.client.submitTrustSignal(agentId, signal);
    
    // Invalidate cache to ensure fresh data on next request
    this.cache.delete(`trust_${agentId}`);
  }
}

// Example 7: Complete Marketplace Integration
async function completeIntegrationExample() {
  console.log('\n=== Example 7: Complete Marketplace Integration ===');
  
  const marketplace = new MarketplaceIntegration(config.apiKey);
  const agentId = 'test_agent_verified';
  
  try {
    // Render agent card
    console.log('Generating agent card HTML...');
    const cardHTML = await marketplace.renderAgentCard(agentId);
    console.log('Agent card generated successfully');
    
    // Simulate transaction
    console.log('Recording transaction...');
    await marketplace.recordTransaction(agentId, {
      id: `txn_${Date.now()}`,
      rating: 5,
      success: true,
      complexity: 'medium',
      duration: 25,
      satisfaction: 4.8,
      category: 'code_review',
      value: 200
    });
    console.log('Transaction recorded successfully');
    
    // Render updated card (will fetch fresh data)
    console.log('Generating updated agent card...');
    const updatedCardHTML = await marketplace.renderAgentCard(agentId);
    console.log('Updated agent card generated successfully');
    
  } catch (error) {
    console.error('Complete integration example failed:', error.message);
  }
}

// Main execution
async function main() {
  console.log('🚀 AgentPier Integration Examples');
  console.log('================================');
  
  if (!config.apiKey || config.apiKey === 'your_api_key_here') {
    console.warn('⚠️ No API key configured. Set AGENTPIER_API_KEY environment variable or update config.');
    console.warn('Some examples may fail with authentication errors.');
    console.log('');
  }
  
  // Run all examples
  await basicTrustScoreExample();
  await marketplaceListingExample();
  await transactionWorkflowExample();
  await vtokenVerificationExample();
  await errorHandlingExample();
  await completeIntegrationExample();
  
  console.log('\n✅ All examples completed');
  console.log('Check the AgentPier Developer Portal for more information:');
  console.log('https://docs.agentpier.org/developer-portal');
}

// Export for use as module
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    AgentPierClient,
    APIError,
    MarketplaceIntegration,
    config
  };
}

// Run examples if executed directly
if (require.main === module) {
  main().catch(console.error);
}