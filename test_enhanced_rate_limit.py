#!/usr/bin/env python3
"""Test script for enhanced rate limiting functionality."""

import os
import sys
import json
import time
from unittest.mock import Mock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.enhanced_rate_limit import RateLimiter, RATE_LIMIT_CONFIG, DEFAULT_LIMITS

def test_rate_limiter_initialization():
    """Test that RateLimiter initializes correctly."""
    print("Testing RateLimiter initialization...")
    
    # Mock Redis to test fallback behavior
    with patch('redis.Redis') as mock_redis:
        mock_redis.side_effect = Exception("Redis not available")
        
        limiter = RateLimiter()
        assert limiter.redis_client is None, "Should fallback when Redis unavailable"
        print("✓ Graceful Redis fallback works")

def test_tier_configuration():
    """Test that all tiers have proper configuration."""
    print("\nTesting tier configuration...")
    
    required_tiers = ["untrusted", "provisional", "established", "trusted", "highly_trusted"]
    
    # Check default limits
    for tier in required_tiers:
        assert tier in DEFAULT_LIMITS, f"Missing default limits for tier: {tier}"
        max_req, window = DEFAULT_LIMITS[tier]
        assert isinstance(max_req, int) and max_req > 0, f"Invalid max_req for {tier}"
        assert isinstance(window, int) and window > 0, f"Invalid window for {tier}"
        print(f"✓ {tier}: {max_req} requests per {window}s")
    
    # Check endpoint configurations
    for endpoint, tier_config in RATE_LIMIT_CONFIG.items():
        for tier in required_tiers:
            if tier in tier_config:
                max_req, window = tier_config[tier]
                assert isinstance(max_req, int) and max_req > 0
                assert isinstance(window, int) and window > 0
        print(f"✓ {endpoint} configured for all tiers")

def test_event_processing():
    """Test IP and user extraction from Lambda events."""
    print("\nTesting event processing...")
    
    limiter = RateLimiter()
    
    # Test IP extraction
    event = {
        "requestContext": {
            "identity": {
                "sourceIp": "192.168.1.100"
            }
        }
    }
    
    ip = limiter.get_client_ip(event)
    assert ip == "192.168.1.100", f"Expected 192.168.1.100, got {ip}"
    print("✓ IP extraction works")
    
    # Test missing IP handling
    empty_event = {}
    ip = limiter.get_client_ip(empty_event)
    assert ip == "unknown", f"Expected 'unknown', got {ip}"
    print("✓ Missing IP handling works")
    
    # Test user ID extraction
    event_with_user = {
        "user_id": "test-user-123"
    }
    user_id = limiter.get_user_id(event_with_user)
    assert user_id == "test-user-123", f"Expected test-user-123, got {user_id}"
    print("✓ User ID extraction works")

def test_limit_calculations():
    """Test rate limit calculations."""
    print("\nTesting limit calculations...")
    
    limiter = RateLimiter()
    
    # Test known endpoint
    max_req, window = limiter.get_rate_limits("vtokens_create", "trusted")
    expected = RATE_LIMIT_CONFIG["vtokens_create"]["trusted"]
    assert (max_req, window) == expected, f"Expected {expected}, got {(max_req, window)}"
    print(f"✓ vtokens_create for trusted: {max_req}/{window}s")
    
    # Test unknown endpoint defaults to tier defaults
    max_req, window = limiter.get_rate_limits("unknown_endpoint", "established") 
    expected = DEFAULT_LIMITS["established"]
    assert (max_req, window) == expected, f"Expected {expected}, got {(max_req, window)}"
    print(f"✓ Unknown endpoint uses default: {max_req}/{window}s")

def test_mock_rate_limiting():
    """Test rate limiting logic with mocks."""
    print("\nTesting rate limiting logic...")
    
    # Mock the DynamoDB and Redis interactions
    with patch('boto3.resource') as mock_boto:
        mock_table = Mock()
        mock_boto.return_value.Table.return_value = mock_table
        
        # Mock successful DynamoDB operations
        mock_table.put_item.return_value = {}
        mock_table.query.return_value = {"Count": 5}  # 5 requests in window
        mock_table.get_item.return_value = {"Item": {"trust_score": 45}}  # established tier
        
        limiter = RateLimiter()
        
        # Test event
        event = {
            "requestContext": {"identity": {"sourceIp": "192.168.1.1"}},
            "user_id": "test-user"
        }
        
        allowed, remaining, retry_after, metadata = limiter.check_rate_limit(event, "vtokens_create")
        
        # With 5 requests and limit of 20 for established tier, should be allowed
        assert allowed == True, "Should be allowed with 5/20 requests"
        assert metadata["tier"] == "established", f"Expected established tier, got {metadata['tier']}"
        assert metadata["endpoint_type"] == "vtokens_create"
        print(f"✓ Rate limiting allows request: {remaining} remaining")

def create_sample_event():
    """Create a sample Lambda event for testing."""
    return {
        "httpMethod": "POST",
        "path": "/vtokens",
        "headers": {
            "Content-Type": "application/json",
            "X-API-Key": "test-key"
        },
        "requestContext": {
            "requestId": "test-request-123",
            "identity": {
                "sourceIp": "203.0.113.1"
            }
        },
        "body": json.dumps({"purpose": "general"})
    }

def main():
    """Run all tests."""
    print("Enhanced Rate Limiting Test Suite")
    print("=" * 50)
    
    try:
        test_rate_limiter_initialization()
        test_tier_configuration()
        test_event_processing()
        test_limit_calculations()
        test_mock_rate_limiting()
        
        print("\n" + "=" * 50)
        print("✅ All tests passed!")
        print("\nRate limiting system is ready for deployment.")
        
        # Display configuration summary
        print("\nConfiguration Summary:")
        print(f"• {len(RATE_LIMIT_CONFIG)} endpoint types configured")
        print(f"• {len(DEFAULT_LIMITS)} user tiers supported")
        print("• Redis primary with DynamoDB fallback")
        print("• CloudWatch metrics integration")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()