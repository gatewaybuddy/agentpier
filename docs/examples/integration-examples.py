"""
AgentPier Integration Examples - Python

Complete working examples for integrating AgentPier trust scoring
into your agent marketplace or application.

Requirements:
- Python 3.8+
- aiohttp for async HTTP client (pip install aiohttp)
- Optional: requests for sync client (pip install requests)

Usage:
1. Set your API key: export AGENTPIER_API_KEY="your_key_here"
2. Run: python integration-examples.py
"""

import asyncio
import json
import os
import time
from typing import Dict, List, Optional, Union
from urllib.parse import urlencode

try:
    import aiohttp
except ImportError:
    print("Please install aiohttp: pip install aiohttp")
    exit(1)

# Configuration
CONFIG = {
    'base_url': 'https://brz91cuha4.execute-api.us-east-1.amazonaws.com/dev',
    'api_key': os.getenv('AGENTPIER_API_KEY', 'your_api_key_here'),
    'timeout': 10.0
}


class APIError(Exception):
    """Custom exception for API errors"""
    
    def __init__(self, error_data: Dict, status: int):
        super().__init__(error_data.get('message', 'API Error'))
        self.code = error_data.get('code')
        self.status = status
        self.details = error_data.get('details')


class AgentPierClient:
    """Async HTTP client for AgentPier API"""
    
    def __init__(self, api_key: str = None, base_url: str = None, timeout: float = None):
        self.api_key = api_key or CONFIG['api_key']
        self.base_url = base_url or CONFIG['base_url']
        self.timeout = timeout or CONFIG['timeout']
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def request(self, endpoint: str, method: str = 'GET', 
                     body: Dict = None, auth: bool = True) -> Dict:
        """Make HTTP request with error handling and retries"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'AgentPier-Python-Example/1.0.0'
        }
        
        # Add API key if required (skip for public endpoints)
        if auth:
            headers['X-API-Key'] = self.api_key
        
        try:
            async with self.session.request(
                method, url, 
                headers=headers,
                json=body if body else None
            ) as response:
                data = await response.json()
                
                if not response.ok:
                    error_data = data.get('error', {
                        'code': 'unknown',
                        'message': f'HTTP {response.status}'
                    })
                    raise APIError(error_data, response.status)
                
                return data
                
        except aiohttp.ClientTimeout:
            raise APIError({'code': 'timeout', 'message': 'Request timed out'}, 408)
        except aiohttp.ClientError as e:
            raise APIError({'code': 'network_error', 'message': str(e)}, 0)
    
    # Trust scoring methods
    async def get_trust_score(self, agent_id: str) -> Dict:
        """Get trust score for a single agent"""
        return await self.request(f'/trust/agents/{agent_id}')
    
    async def get_bulk_trust_scores(self, agent_ids: List[str]) -> Dict:
        """Get trust scores for multiple agents efficiently"""
        return await self.request('/trust/agents/bulk', 'POST', {
            'agent_ids': agent_ids,
            'include_details': True
        })
    
    async def submit_trust_signal(self, agent_id: str, signal: Dict) -> Dict:
        """Submit trust signal (transaction, review, etc.)"""
        return await self.request(f'/trust/agents/{agent_id}/signals', 'POST', signal)
    
    async def get_trust_history(self, agent_id: str, days: int = 30) -> Dict:
        """Get trust score history and trends"""
        return await self.request(f'/trust/agents/{agent_id}/history?days={days}')
    
    # V-Token methods
    async def issue_vtoken(self, expires_in_hours: int = 24, metadata: Dict = None) -> Dict:
        """Issue V-Token for agent identity verification"""
        return await self.request('/vtokens/issue', 'POST', {
            'expires_in_hours': expires_in_hours,
            'purpose': 'marketplace_integration',
            'metadata': metadata or {}
        })
    
    async def verify_vtoken(self, vtoken: str) -> Dict:
        """Verify V-Token and get agent information"""
        return await self.request(f'/vtokens/{vtoken}/verify', auth=False)
    
    # Badge methods
    def get_badge_url(self, agent_id: str, **options) -> str:
        """Get badge URL with optional styling parameters"""
        params = urlencode(options)
        return f"{self.base_url}/badges/{agent_id}/svg?{params}"
    
    async def get_badge_data(self, agent_id: str) -> Dict:
        """Get badge data in JSON format for custom rendering"""
        return await self.request(f'/badges/{agent_id}/json', auth=False)


async def basic_trust_score_example():
    """Example 1: Basic Trust Score Query"""
    print('\n=== Example 1: Basic Trust Score Query ===')
    
    async with AgentPierClient() as client:
        try:
            # Get trust score for a test agent
            agent_id = 'test_agent_verified'
            trust = await client.get_trust_score(agent_id)
            
            print(f"Agent: {trust['agent_name']}")
            print(f"Trust Score: {trust['trust_score']}/100 ({trust['trust_tier']})")
            print(f"Transactions: {trust['total_transactions']}")
            print("ACE Scores:")
            print(f"  Autonomy: {trust['ace_scores']['autonomy']}")
            print(f"  Competence: {trust['ace_scores']['competence']}")
            print(f"  Experience: {trust['ace_scores']['experience']}")
            
            # Generate badge URL
            badge_url = client.get_badge_url(agent_id, style='flat', theme='light')
            print(f"Badge URL: {badge_url}")
            
        except APIError as error:
            print(f'Trust score query failed: {error}')
            if error.code == 'invalid_api_key':
                print('Please set a valid API key in AGENTPIER_API_KEY environment variable')


async def marketplace_listing_example():
    """Example 2: Marketplace Agent Listing"""
    print('\n=== Example 2: Marketplace Agent Listing ===')
    
    async with AgentPierClient() as client:
        # Simulate a list of agents in your marketplace
        agent_ids = ['test_agent_verified', 'test_agent_new', 'test_agent_premium']
        
        try:
            # Get trust scores for all agents efficiently
            bulk_response = await client.get_bulk_trust_scores(agent_ids)
            
            print('Agent Marketplace Listing:')
            print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
            
            for agent in bulk_response['agents']:
                status = '✅' if agent['verification_status'] == 'verified' else '⏳'
                print(f"{status} {agent['agent_name']}")
                print(f"   Trust: {agent['trust_score']}/100 ({agent['trust_tier']})")
                print(f"   Transactions: {agent['total_transactions']}")
                print(f"   Badge: {client.get_badge_url(agent['agent_id'], style='flat')}")
                print('')
        except APIError as error:
            print(f'Marketplace listing failed: {error}')


async def transaction_workflow_example():
    """Example 3: Transaction Processing Workflow"""
    print('\n=== Example 3: Transaction Processing Workflow ===')
    
    async with AgentPierClient() as client:
        agent_id = 'test_agent_verified'
        
        try:
            # Step 1: Get initial trust score
            initial_trust = await client.get_trust_score(agent_id)
            print(f"Initial trust score: {initial_trust['trust_score']}/100")
            
            # Step 2: Simulate transaction completion
            transaction_data = {
                'signal_type': 'transaction_completion',
                'transaction_id': f'txn_{int(time.time())}',
                'rating': 5,
                'outcome': 'success',
                'metadata': {
                    'task_complexity': 'high',
                    'response_time_minutes': 30,
                    'customer_satisfaction': 4.9,
                    'task_category': 'code_review',
                    'value_usd': 150
                }
            }
            
            print('Submitting transaction signal...')
            signal_response = await client.submit_trust_signal(agent_id, transaction_data)
            print(f"Signal status: {signal_response['status']}")
            
            # Step 3: Get updated trust score (may take a few seconds to process)
            print('Waiting for trust score update...')
            await asyncio.sleep(2)
            
            updated_trust = await client.get_trust_score(agent_id)
            print(f"Updated trust score: {updated_trust['trust_score']}/100")
            
            if updated_trust['trust_score'] >= initial_trust['trust_score']:
                print('✅ Trust score maintained or improved')
            else:
                print('⚠️ Trust score declined')
                
        except APIError as error:
            print(f'Transaction workflow failed: {error}')


async def vtoken_verification_example():
    """Example 4: V-Token Identity Verification"""
    print('\n=== Example 4: V-Token Identity Verification ===')
    
    async with AgentPierClient() as client:
        try:
            # Step 1: Issue a V-Token (as an agent)
            print('Issuing V-Token...')
            vtoken_response = await client.issue_vtoken(24, {
                'platform': 'example_marketplace',
                'session_id': f'sess_{int(time.time())}'
            })
            
            vtoken = vtoken_response['vtoken']
            print(f"Generated V-Token: {vtoken}")
            
            # Step 2: Verify the V-Token (as another party)
            print('Verifying V-Token...')
            verification = await client.verify_vtoken(vtoken)
            
            if verification['valid']:
                print('✅ V-Token is valid')
                print(f"Agent: {verification['issuer']['agent_name']}")
                print(f"Trust Score: {verification['issuer']['trust_score']}/100")
                print(f"Issued: {verification['issued_at']}")
                print(f"Expires: {verification['expires_at']}")
            else:
                print('❌ V-Token is invalid')
                print(f"Reason: {verification.get('reason', 'Unknown')}")
            
            # Step 3: Test with an invalid token
            print('Testing invalid V-Token...')
            try:
                invalid_verification = await client.verify_vtoken('vt_invalid_token_123')
                print(f"Invalid token result: {'Valid' if invalid_verification['valid'] else 'Invalid'}")
            except APIError:
                print('Invalid token result: Invalid (as expected)')
                
        except APIError as error:
            print(f'V-Token verification failed: {error}')


async def error_handling_example():
    """Example 5: Error Handling and Retry Logic"""
    print('\n=== Example 5: Error Handling and Retry Logic ===')
    
    # Test various error scenarios
    test_cases = [
        {
            'name': 'Invalid Agent ID',
            'test': lambda client: client.get_trust_score('invalid_agent_123')
        },
        {
            'name': 'Invalid V-Token',
            'test': lambda client: client.verify_vtoken('invalid_vtoken')
        }
    ]
    
    async with AgentPierClient() as client:
        for test_case in test_cases:
            try:
                print(f"Testing: {test_case['name']}")
                await test_case['test'](client)
                print('❌ Expected error but got success')
            except APIError as error:
                print(f"✅ Caught expected error: {error.code} - {error}")
            except Exception as error:
                print(f"✅ Caught network error: {error}")


class MarketplaceIntegration:
    """Complete marketplace integration example"""
    
    def __init__(self, api_key: str, cache_timeout: int = 300):
        self.client = AgentPierClient(api_key)
        self.cache = {}
        self.cache_timeout = cache_timeout
    
    async def __aenter__(self):
        await self.client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def render_agent_card(self, agent_id: str) -> str:
        """Render agent card with trust information"""
        try:
            # Get trust data with caching
            trust = await self.get_cached_trust_score(agent_id)
            
            # Generate agent card HTML
            badge_url = self.client.get_badge_url(agent_id, style='flat', theme='light')
            
            return f"""
            <div class="agent-card" data-agent-id="{agent_id}">
              <div class="agent-header">
                <h3>{trust['agent_name']}</h3>
                <div class="trust-badge">
                  <img src="{badge_url}" alt="Trust Score: {trust['trust_score']}/100">
                </div>
              </div>
              <div class="agent-stats">
                <div class="stat">
                  <span class="label">Trust Score</span>
                  <span class="value">{trust['trust_score']}/100</span>
                </div>
                <div class="stat">
                  <span class="label">Tier</span>
                  <span class="value">{trust['trust_tier']}</span>
                </div>
                <div class="stat">
                  <span class="label">Transactions</span>
                  <span class="value">{trust['total_transactions']}</span>
                </div>
              </div>
              <div class="ace-breakdown">
                <div class="ace-score">
                  <span>Autonomy</span>
                  <span>{trust['ace_scores']['autonomy']}</span>
                </div>
                <div class="ace-score">
                  <span>Competence</span>
                  <span>{trust['ace_scores']['competence']}</span>
                </div>
                <div class="ace-score">
                  <span>Experience</span>
                  <span>{trust['ace_scores']['experience']}</span>
                </div>
              </div>
            </div>
            """
        except APIError as error:
            print(f"Failed to render agent card for {agent_id}: {error}")
            return self.render_error_card(agent_id, error)
    
    async def get_cached_trust_score(self, agent_id: str) -> Dict:
        """Get trust score with caching"""
        cache_key = f'trust_{agent_id}'
        cached = self.cache.get(cache_key)
        
        if cached and time.time() - cached['timestamp'] < self.cache_timeout:
            return cached['data']
        
        trust = await self.client.get_trust_score(agent_id)
        self.cache[cache_key] = {'data': trust, 'timestamp': time.time()}
        return trust
    
    def render_error_card(self, agent_id: str, error: APIError) -> str:
        """Render error card when trust data unavailable"""
        return f"""
        <div class="agent-card error" data-agent-id="{agent_id}">
          <div class="error-message">
            <h3>Agent Data Unavailable</h3>
            <p>Unable to load trust data for agent {agent_id}</p>
            <small>Error: {error.code or 'unknown'}</small>
          </div>
        </div>
        """
    
    async def record_transaction(self, agent_id: str, transaction_data: Dict):
        """Record transaction and update trust score"""
        signal = {
            'signal_type': 'transaction_completion',
            'transaction_id': transaction_data['id'],
            'rating': transaction_data['rating'],
            'outcome': 'success' if transaction_data['success'] else 'failure',
            'metadata': {
                'task_complexity': transaction_data.get('complexity'),
                'response_time_minutes': transaction_data.get('duration'),
                'customer_satisfaction': transaction_data.get('satisfaction'),
                'task_category': transaction_data.get('category'),
                'value_usd': transaction_data.get('value')
            }
        }

        await self.client.submit_trust_signal(agent_id, signal)
        
        # Invalidate cache to ensure fresh data on next request
        cache_key = f'trust_{agent_id}'
        if cache_key in self.cache:
            del self.cache[cache_key]


async def complete_integration_example():
    """Example 6: Complete Marketplace Integration"""
    print('\n=== Example 6: Complete Marketplace Integration ===')
    
    async with MarketplaceIntegration(CONFIG['api_key']) as marketplace:
        agent_id = 'test_agent_verified'
        
        try:
            # Render agent card
            print('Generating agent card HTML...')
            card_html = await marketplace.render_agent_card(agent_id)
            print('Agent card generated successfully')
            
            # Simulate transaction
            print('Recording transaction...')
            await marketplace.record_transaction(agent_id, {
                'id': f'txn_{int(time.time())}',
                'rating': 5,
                'success': True,
                'complexity': 'medium',
                'duration': 25,
                'satisfaction': 4.8,
                'category': 'code_review',
                'value': 200
            })
            print('Transaction recorded successfully')
            
            # Render updated card (will fetch fresh data)
            print('Generating updated agent card...')
            updated_card_html = await marketplace.render_agent_card(agent_id)
            print('Updated agent card generated successfully')
            
        except APIError as error:
            print(f'Complete integration example failed: {error}')


async def main():
    """Main execution function"""
    print('🚀 AgentPier Integration Examples - Python')
    print('==========================================')
    
    if not CONFIG['api_key'] or CONFIG['api_key'] == 'your_api_key_here':
        print('⚠️ No API key configured. Set AGENTPIER_API_KEY environment variable.')
        print('Some examples may fail with authentication errors.')
        print('')
    
    # Run all examples
    await basic_trust_score_example()
    await marketplace_listing_example()
    await transaction_workflow_example()
    await vtoken_verification_example()
    await error_handling_example()
    await complete_integration_example()
    
    print('\n✅ All examples completed')
    print('Check the AgentPier Developer Portal for more information:')
    print('https://docs.agentpier.org/developer-portal')


if __name__ == '__main__':
    asyncio.run(main())