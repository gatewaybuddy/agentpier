"""Rate limiting information endpoints for AgentPier API monitoring."""

import json
import os
from datetime import datetime, timezone

from utils.response import success, error, handler
from utils.auth import authenticate
from utils.enhanced_rate_limit import get_rate_limiter, RATE_LIMIT_CONFIG, DEFAULT_LIMITS


@handler
def get_rate_limit_info(event, context):
    """GET /rate-limits - Get rate limiting configuration and current status."""
    # This endpoint is for monitoring/debugging - require authentication
    user = authenticate(event)
    if not user:
        return error("Authentication required", "unauthorized", 401)
    
    limiter = get_rate_limiter()
    user_tier = limiter.get_user_tier(user.get("user_id"))
    
    # Get all endpoint configurations for the user's tier
    endpoint_limits = {}
    for endpoint_type, tier_configs in RATE_LIMIT_CONFIG.items():
        max_requests, window_seconds = tier_configs.get(user_tier, DEFAULT_LIMITS[user_tier])
        endpoint_limits[endpoint_type] = {
            "max_requests": max_requests,
            "window_seconds": window_seconds,
            "tier": user_tier
        }
    
    return success({
        "user_tier": user_tier,
        "backend_available": {
            "redis": limiter.redis_client is not None,
            "dynamodb": True  # Always available in Lambda
        },
        "endpoint_limits": endpoint_limits,
        "default_limits": {
            "max_requests": DEFAULT_LIMITS[user_tier][0],
            "window_seconds": DEFAULT_LIMITS[user_tier][1]
        },
        "tier_definitions": {
            "untrusted": "New users, score 0-19",
            "provisional": "Basic verification, score 20-39", 
            "established": "Proven reliability, score 40-59",
            "trusted": "High confidence, score 60-79",
            "highly_trusted": "Maximum trust, score 80-95"
        }
    })


@handler
def get_rate_limit_status(event, context):
    """GET /rate-limits/status - Get current rate limit usage for authenticated user."""
    user = authenticate(event)
    if not user:
        return error("Authentication required", "unauthorized", 401)
    
    # Get query parameters for endpoint type
    query_params = event.get("queryStringParameters") or {}
    endpoint_type = query_params.get("endpoint_type")
    
    if not endpoint_type:
        return error("endpoint_type query parameter required", "missing_parameter", 400)
    
    if endpoint_type not in RATE_LIMIT_CONFIG and endpoint_type != "default":
        return error(f"Unknown endpoint_type: {endpoint_type}", "invalid_parameter", 400)
    
    limiter = get_rate_limiter()
    
    # Perform a dry-run rate limit check to get current usage
    # This doesn't count against the limit but shows current status
    allowed, remaining, retry_after, metadata = limiter.check_rate_limit(event, endpoint_type)
    
    return success({
        "endpoint_type": endpoint_type,
        "user_tier": metadata["tier"],
        "current_status": {
            "allowed": allowed,
            "remaining": remaining,
            "retry_after": retry_after
        },
        "limits": {
            "max_requests": metadata["max_requests"],
            "window_seconds": metadata["window_seconds"]
        },
        "backend": metadata["backend"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@handler  
def get_rate_limit_config(event, context):
    """GET /rate-limits/config - Get complete rate limiting configuration (admin only)."""
    # Check for admin API key
    headers = event.get("headers") or {}
    admin_key = headers.get("X-Admin-Key") or headers.get("x-admin-key")
    expected_admin_key = os.environ.get("ADMIN_API_KEY")
    
    if not admin_key or admin_key != expected_admin_key or expected_admin_key == "none":
        return error("Admin authentication required", "unauthorized", 401)
    
    return success({
        "rate_limit_configuration": RATE_LIMIT_CONFIG,
        "default_limits": DEFAULT_LIMITS,
        "backend_config": {
            "redis_host": os.environ.get("REDIS_HOST", "localhost"),
            "redis_port": os.environ.get("REDIS_PORT", "6379"),
            "redis_db": os.environ.get("REDIS_DB", "0"),
            "metrics_namespace": os.environ.get("METRICS_NAMESPACE", "AgentPier/RateLimit")
        },
        "features": [
            "Redis-based sliding window rate limiting",
            "DynamoDB fallback for high availability", 
            "User tier-based limits (5 tiers)",
            "Per-endpoint type configuration",
            "CloudWatch metrics integration",
            "Automatic failover to DynamoDB"
        ]
    })