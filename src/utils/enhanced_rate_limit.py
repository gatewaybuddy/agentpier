"""Enhanced rate limiting for AgentPier with Redis and user-tier support.

Features:
- Redis-based rate limiting for better performance
- User tier-based rate limits (untrusted, provisional, established, trusted, highly_trusted)
- Configurable limits per endpoint type
- Monitoring integration via CloudWatch metrics
- Graceful fallback to DynamoDB when Redis is unavailable
"""

import json
import os
import time
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timezone

import boto3
import redis

from utils.ace_scoring import get_trust_tier
from utils.response import error, too_many_requests

# Redis configuration
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("REDIS_DB", "0"))
REDIS_TTL = int(os.environ.get("REDIS_TTL", "3600"))  # 1 hour default

# DynamoDB fallback
TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")

# CloudWatch metrics
METRICS_NAMESPACE = os.environ.get("METRICS_NAMESPACE", "AgentPier/RateLimit")

# Rate limit configurations per endpoint type and user tier
# Format: {endpoint_type: {tier: (max_requests, window_seconds)}}
RATE_LIMIT_CONFIG = {
    "vtokens_create": {
        "untrusted": (5, 300),        # 5 per 5 min
        "provisional": (10, 300),     # 10 per 5 min
        "established": (20, 300),     # 20 per 5 min
        "trusted": (50, 300),         # 50 per 5 min
        "highly_trusted": (100, 300), # 100 per 5 min
    },
    "vtokens_verify": {
        "untrusted": (20, 60),        # 20 per min
        "provisional": (50, 60),      # 50 per min
        "established": (100, 60),     # 100 per min
        "trusted": (200, 60),         # 200 per min
        "highly_trusted": (500, 60),  # 500 per min
    },
    "trust_calculation": {
        "untrusted": (10, 300),       # 10 per 5 min
        "provisional": (20, 300),     # 20 per 5 min
        "established": (50, 300),     # 50 per 5 min
        "trusted": (100, 300),        # 100 per 5 min
        "highly_trusted": (200, 300), # 200 per 5 min
    },
    "marketplace_search": {
        "untrusted": (30, 60),        # 30 per min
        "provisional": (60, 60),      # 60 per min
        "established": (120, 60),     # 120 per min
        "trusted": (240, 60),         # 240 per min
        "highly_trusted": (500, 60),  # 500 per min
    },
    "marketplace_create": {
        "untrusted": (2, 3600),       # 2 per hour
        "provisional": (5, 3600),     # 5 per hour
        "established": (10, 3600),    # 10 per hour
        "trusted": (25, 3600),        # 25 per hour
        "highly_trusted": (50, 3600), # 50 per hour
    },
    "auth_challenge": {
        "untrusted": (5, 3600),       # 5 per hour
        "provisional": (10, 3600),    # 10 per hour
        "established": (15, 3600),    # 15 per hour
        "trusted": (20, 3600),        # 20 per hour
        "highly_trusted": (30, 3600), # 30 per hour
    },
    "auth_register": {
        "untrusted": (3, 3600),       # 3 per hour
        "provisional": (5, 3600),     # 5 per hour
        "established": (8, 3600),     # 8 per hour
        "trusted": (10, 3600),        # 10 per hour
        "highly_trusted": (15, 3600), # 15 per hour
    },
    "auth_signin": {
        "untrusted": (10, 300),       # 10 per 5 min
        "provisional": (20, 300),     # 20 per 5 min
        "established": (30, 300),     # 30 per 5 min
        "trusted": (50, 300),         # 50 per 5 min
        "highly_trusted": (100, 300), # 100 per 5 min
    },
}

# Default limits for unknown endpoints
DEFAULT_LIMITS = {
    "untrusted": (10, 300),       # 10 per 5 min
    "provisional": (20, 300),     # 20 per 5 min
    "established": (40, 300),     # 40 per 5 min
    "trusted": (80, 300),         # 80 per 5 min
    "highly_trusted": (160, 300), # 160 per 5 min
}


class RateLimiter:
    """Enhanced rate limiter with Redis and user-tier support."""
    
    def __init__(self):
        self.redis_client = None
        self.cloudwatch = boto3.client('cloudwatch')
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(TABLE_NAME)
        
        # Try to initialize Redis connection
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection with error handling."""
        try:
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                socket_timeout=1.0,  # 1 second timeout
                socket_connect_timeout=1.0,
                decode_responses=True
            )
            # Test connection
            self.redis_client.ping()
        except Exception:
            # Redis not available, will use DynamoDB fallback
            self.redis_client = None
    
    def get_client_ip(self, event: dict) -> str:
        """Extract client IP from API Gateway event."""
        identity = event.get("requestContext", {}).get("identity", {})
        return identity.get("sourceIp", "unknown")
    
    def get_user_id(self, event: dict) -> Optional[str]:
        """Extract authenticated user ID from event context."""
        # Check for API key authentication
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            return event['requestContext']['authorizer'].get('user_id')
        
        # Check for user ID in event context (set by auth middleware)
        return event.get('user_id')
    
    def get_user_tier(self, user_id: Optional[str]) -> str:
        """Get user's trust tier from database."""
        if not user_id:
            return "untrusted"
        
        try:
            response = self.table.get_item(
                Key={'PK': f'USER#{user_id}', 'SK': 'PROFILE'}
            )
            
            if 'Item' in response:
                trust_score = response['Item'].get('trust_score', 0)
                return get_trust_tier(trust_score)
            
            return "untrusted"
        except Exception:
            # If we can't get user tier, default to untrusted
            return "untrusted"
    
    def get_rate_limits(self, endpoint_type: str, tier: str) -> Tuple[int, int]:
        """Get rate limits for endpoint type and user tier."""
        if endpoint_type in RATE_LIMIT_CONFIG:
            return RATE_LIMIT_CONFIG[endpoint_type].get(tier, DEFAULT_LIMITS[tier])
        
        return DEFAULT_LIMITS[tier]
    
    def _redis_check_rate_limit(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int, int]:
        """Check rate limit using Redis sliding window."""
        try:
            now = int(time.time())
            pipeline = self.redis_client.pipeline()
            
            # Remove expired entries
            pipeline.zremrangebyscore(key, 0, now - window_seconds)
            
            # Count current entries
            pipeline.zcard(key)
            
            # Add current request
            pipeline.zadd(key, {str(now): now})
            
            # Set expiry for the key
            pipeline.expire(key, window_seconds)
            
            results = pipeline.execute()
            current_count = results[1]  # Count after cleanup
            
            # Check if over limit (counting the request we just added)
            if current_count >= max_requests:
                remaining = 0
                retry_after = window_seconds
                allowed = False
            else:
                remaining = max_requests - current_count - 1
                retry_after = 0
                allowed = True
            
            return allowed, remaining, retry_after
            
        except Exception:
            # Redis error, fall back to DynamoDB
            return None
    
    def _dynamodb_check_rate_limit(self, ip: str, user_id: Optional[str], 
                                  action: str, max_requests: int, window_seconds: int) -> Tuple[bool, int, int]:
        """Fallback rate limiting using DynamoDB."""
        now = int(time.time())
        window_start = now - window_seconds
        
        # Use user ID if available, otherwise use IP
        identifier = user_id if user_id else ip
        pk = f"RATELIMIT#{identifier}"
        sk = f"{action}#{now}"
        
        # Write this request
        try:
            self.table.put_item(
                Item={
                    "PK": pk,
                    "SK": sk,
                    "ttl": now + window_seconds,
                    "action": action,
                    "timestamp": now,
                }
            )
        except Exception:
            # Fail closed
            return False, 0, window_seconds
        
        # Count requests in window
        try:
            response = self.table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(pk) & 
                                     boto3.dynamodb.conditions.Key("SK").between(
                                         f"{action}#{window_start}",
                                         f"{action}#{now + 1}"
                                     ),
                Select="COUNT",
            )
        except Exception:
            return False, 0, window_seconds
        
        count = response.get("Count", 0)
        remaining = max(0, max_requests - count)
        
        if count > max_requests:
            retry_after = window_seconds - (now - window_start)
            return False, 0, retry_after
        
        return True, remaining, 0
    
    def check_rate_limit(self, event: dict, endpoint_type: str) -> Tuple[bool, int, int, Dict[str, any]]:
        """
        Check rate limit for an endpoint.
        
        Returns: (allowed, remaining, retry_after, metadata)
        """
        ip = self.get_client_ip(event)
        user_id = self.get_user_id(event)
        tier = self.get_user_tier(user_id)
        max_requests, window_seconds = self.get_rate_limits(endpoint_type, tier)
        
        # Create rate limit key
        identifier = user_id if user_id else ip
        key = f"ratelimit:{endpoint_type}:{identifier}"
        
        # Try Redis first
        if self.redis_client:
            redis_result = self._redis_check_rate_limit(key, max_requests, window_seconds)
            if redis_result is not None:
                allowed, remaining, retry_after = redis_result
                # Record metrics
                self._record_metrics(endpoint_type, tier, allowed, "redis")
                
                metadata = {
                    "tier": tier,
                    "endpoint_type": endpoint_type,
                    "max_requests": max_requests,
                    "window_seconds": window_seconds,
                    "backend": "redis"
                }
                return allowed, remaining, retry_after, metadata
        
        # Fallback to DynamoDB
        allowed, remaining, retry_after = self._dynamodb_check_rate_limit(
            ip, user_id, endpoint_type, max_requests, window_seconds
        )
        
        # Record metrics
        self._record_metrics(endpoint_type, tier, allowed, "dynamodb")
        
        metadata = {
            "tier": tier,
            "endpoint_type": endpoint_type,
            "max_requests": max_requests,
            "window_seconds": window_seconds,
            "backend": "dynamodb"
        }
        
        return allowed, remaining, retry_after, metadata
    
    def _record_metrics(self, endpoint_type: str, tier: str, allowed: bool, backend: str):
        """Record CloudWatch metrics for monitoring."""
        try:
            metrics = [
                {
                    'MetricName': 'RateLimitChecks',
                    'Dimensions': [
                        {'Name': 'EndpointType', 'Value': endpoint_type},
                        {'Name': 'UserTier', 'Value': tier},
                        {'Name': 'Backend', 'Value': backend},
                    ],
                    'Value': 1,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'RateLimitViolations' if not allowed else 'RateLimitAllowed',
                    'Dimensions': [
                        {'Name': 'EndpointType', 'Value': endpoint_type},
                        {'Name': 'UserTier', 'Value': tier},
                    ],
                    'Value': 1,
                    'Unit': 'Count'
                }
            ]
            
            self.cloudwatch.put_metric_data(
                Namespace=METRICS_NAMESPACE,
                MetricData=metrics
            )
        except Exception:
            # Don't fail the request if metrics recording fails
            pass


# Global instance
_rate_limiter = None

def get_rate_limiter():
    """Get or create global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def check_enhanced_rate_limit(event: dict, endpoint_type: str):
    """
    Enhanced rate limiting check with proper response formatting.
    
    Returns response dict if rate limited, None if allowed.
    """
    limiter = get_rate_limiter()
    allowed, remaining, retry_after, metadata = limiter.check_rate_limit(event, endpoint_type)
    
    if not allowed:
        return too_many_requests(
            f"Rate limit exceeded for {endpoint_type}. "
            f"Tier: {metadata['tier']}, "
            f"Limit: {metadata['max_requests']}/{metadata['window_seconds']}s",
            retry_after,
            {
                "rate_limit": {
                    "tier": metadata["tier"],
                    "endpoint_type": metadata["endpoint_type"],
                    "limit": metadata["max_requests"],
                    "window": metadata["window_seconds"],
                    "backend": metadata["backend"]
                }
            }
        )
    
    return None  # Allowed


def rate_limit_middleware(endpoint_type: str):
    """
    Decorator for easy rate limiting integration.
    
    Usage:
    @rate_limit_middleware("vtokens_create")
    @handler
    def create_vtoken(event, context):
        # Handler implementation
        pass
    """
    def decorator(func):
        def wrapper(event, context):
            # Check rate limit
            rate_limit_response = check_enhanced_rate_limit(event, endpoint_type)
            if rate_limit_response:
                return rate_limit_response
            
            # Rate limit passed, call original function
            return func(event, context)
        
        return wrapper
    return decorator