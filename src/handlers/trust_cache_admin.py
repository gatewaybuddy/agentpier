"""Trust Cache Administration API.

Admin endpoints for monitoring and managing the trust score cache.
"""

import json
from utils.response import success, error
from utils.trust_cache import get_trust_cache


def trust_cache_stats(event, context):
    """GET /trust/cache/stats - Get cache performance statistics."""
    cache = get_trust_cache()
    stats = cache.get_cache_stats()
    
    return success(stats)


def trust_cache_flush(event, context):
    """DELETE /trust/cache - Flush trust cache entries."""
    # Parse query parameters
    params = event.get("queryStringParameters") or {}
    pattern = params.get("pattern")
    
    cache = get_trust_cache()
    deleted_count = cache.flush_cache(pattern)
    
    return success({
        "deleted_count": deleted_count,
        "pattern": pattern or "all_trust_caches"
    })


def trust_cache_invalidate(event, context):
    """DELETE /trust/cache/agents/{agent_id} - Invalidate cache for specific agent."""
    agent_id = event.get("pathParameters", {}).get("agent_id", "")
    if not agent_id:
        return error("agent_id is required", "validation_error")
    
    cache = get_trust_cache()
    cache.invalidate_agent_cache(agent_id)
    
    return success({
        "agent_id": agent_id,
        "invalidated": True
    })


def trust_cache_warm(event, context):
    """POST /trust/cache/warm - Warm cache for multiple agents."""
    body = json.loads(event.get("body", "{}"))
    
    agent_ids = body.get("agent_ids", [])
    if not agent_ids or not isinstance(agent_ids, list):
        return error("agent_ids list is required", "validation_error")
    
    # Limit to reasonable batch size
    agent_ids = agent_ids[:50]
    
    cache = get_trust_cache()
    
    # For now, we'll just invalidate the caches to force refresh on next access
    # A full warming implementation would require the actual calculation functions
    for agent_id in agent_ids:
        cache.invalidate_agent_cache(agent_id)
    
    return success({
        "agent_ids": agent_ids,
        "warmed_count": len(agent_ids),
        "note": "Caches invalidated - will be refreshed on next access"
    })