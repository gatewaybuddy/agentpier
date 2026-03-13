"""Trust Score Caching for AgentPier.

Optimizes trust calculations through intelligent Redis-based caching with:
- Tiered TTL based on trust stability
- Cache warming strategies 
- Smart invalidation on trust events
- Performance monitoring and metrics
- Graceful fallback to direct calculation
"""

import json
import os
import time
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

import boto3
import redis

# Cache configuration
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("REDIS_DB", "0"))

# CloudWatch metrics
METRICS_NAMESPACE = os.environ.get("METRICS_NAMESPACE", "AgentPier/TrustCache")

# Cache TTL configuration (seconds)
# Higher trust agents have longer cache TTL since they're more stable
TRUST_CACHE_TTL = {
    "untrusted": 300,      # 5 minutes - low trust changes frequently
    "provisional": 600,    # 10 minutes 
    "established": 1800,   # 30 minutes
    "trusted": 3600,       # 1 hour
    "highly_trusted": 7200, # 2 hours - high trust is very stable
}

# Default TTL for unknown tiers
DEFAULT_TTL = 600  # 10 minutes

# Cache key prefixes
TRUST_SCORE_KEY = "trust_score:"
CLEARINGHOUSE_KEY = "clearinghouse:"
METADATA_KEY = "trust_meta:"

# Cache warming configuration
WARM_CACHE_THRESHOLD = 0.8  # Warm cache when 80% of TTL elapsed
MAX_CACHE_WARM_BATCH = 50   # Maximum agents to warm at once


@dataclass
class CacheMetrics:
    """Cache performance metrics."""
    hits: int = 0
    misses: int = 0
    errors: int = 0
    warm_hits: int = 0
    invalidations: int = 0
    
    @property
    def hit_ratio(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class TrustCache:
    """Redis-based trust score cache with intelligent TTL and warming."""
    
    def __init__(self):
        self.redis_client = None
        self.cloudwatch = boto3.client('cloudwatch')
        self.metrics = CacheMetrics()
        
        # Initialize Redis connection
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection with error handling."""
        try:
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
                decode_responses=True
            )
            # Test connection
            self.redis_client.ping()
        except Exception:
            # Redis not available, will skip caching
            self.redis_client = None
    
    def _get_cache_key(self, cache_type: str, agent_id: str, **params) -> str:
        """Generate cache key with parameter hash for consistency."""
        if cache_type == "trust_score":
            prefix = TRUST_SCORE_KEY
        elif cache_type == "clearinghouse":
            prefix = CLEARINGHOUSE_KEY
        else:
            prefix = "trust_generic:"
        
        # Include relevant parameters in cache key
        if params:
            param_str = json.dumps(params, sort_keys=True)
            param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
            return f"{prefix}{agent_id}:{param_hash}"
        
        return f"{prefix}{agent_id}"
    
    def _get_ttl(self, trust_tier: str) -> int:
        """Get cache TTL based on trust tier."""
        return TRUST_CACHE_TTL.get(trust_tier, DEFAULT_TTL)
    
    def _should_warm_cache(self, key: str) -> bool:
        """Check if cache entry should be warmed (refreshed proactively)."""
        if not self.redis_client:
            return False
        
        try:
            ttl = self.redis_client.ttl(key)
            if ttl <= 0:  # Key expired or doesn't exist
                return False
            
            # Get original TTL from metadata
            meta_key = f"meta:{key}"
            original_ttl = self.redis_client.get(meta_key)
            if not original_ttl:
                return False
            
            original_ttl = int(original_ttl)
            remaining_ratio = ttl / original_ttl
            
            return remaining_ratio <= WARM_CACHE_THRESHOLD
        except Exception:
            return False
    
    def _record_metrics(self, operation: str, hit: bool = False, warm: bool = False):
        """Record cache metrics for monitoring."""
        if hit:
            self.metrics.hits += 1
            if warm:
                self.metrics.warm_hits += 1
        else:
            self.metrics.misses += 1
        
        # Record CloudWatch metrics
        try:
            metric_data = [
                {
                    'MetricName': f'Cache{operation}',
                    'Value': 1,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'CacheHitRatio',
                    'Value': self.metrics.hit_ratio * 100,
                    'Unit': 'Percent'
                }
            ]
            
            self.cloudwatch.put_metric_data(
                Namespace=METRICS_NAMESPACE,
                MetricData=metric_data
            )
        except Exception:
            # Don't fail on metrics errors
            pass
    
    def get_trust_score(self, agent_id: str, **params) -> Optional[Dict[str, Any]]:
        """Get cached trust score if available."""
        if not self.redis_client:
            return None
        
        cache_key = self._get_cache_key("trust_score", agent_id, **params)
        
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                result = json.loads(cached_data)
                
                # Check if cache should be warmed
                should_warm = self._should_warm_cache(cache_key)
                
                self._record_metrics("Hit", hit=True, warm=should_warm)
                
                # Mark for warming if needed
                if should_warm:
                    result["_cache_warm_needed"] = True
                
                return result
            
            self._record_metrics("Miss", hit=False)
            return None
            
        except Exception:
            self.metrics.errors += 1
            return None
    
    def set_trust_score(self, agent_id: str, score_data: Dict[str, Any], 
                       trust_tier: str = "untrusted", **params):
        """Cache trust score with appropriate TTL."""
        if not self.redis_client:
            return
        
        cache_key = self._get_cache_key("trust_score", agent_id, **params)
        ttl = self._get_ttl(trust_tier)
        
        try:
            # Add caching metadata
            cached_data = {
                **score_data,
                "_cached_at": datetime.now(timezone.utc).isoformat(),
                "_cache_ttl": ttl,
                "_trust_tier": trust_tier
            }
            
            # Set cache entry
            self.redis_client.setex(
                cache_key, 
                ttl, 
                json.dumps(cached_data)
            )
            
            # Store metadata for cache warming logic
            meta_key = f"meta:{cache_key}"
            self.redis_client.setex(meta_key, ttl, str(ttl))
            
        except Exception:
            self.metrics.errors += 1
    
    def get_clearinghouse_score(self, agent_id: str, **params) -> Optional[Dict[str, Any]]:
        """Get cached clearinghouse score if available."""
        if not self.redis_client:
            return None
        
        cache_key = self._get_cache_key("clearinghouse", agent_id, **params)
        
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                result = json.loads(cached_data)
                
                should_warm = self._should_warm_cache(cache_key)
                self._record_metrics("ClearinghouseHit", hit=True, warm=should_warm)
                
                if should_warm:
                    result["_cache_warm_needed"] = True
                
                return result
            
            self._record_metrics("ClearinghouseMiss", hit=False)
            return None
            
        except Exception:
            self.metrics.errors += 1
            return None
    
    def set_clearinghouse_score(self, agent_id: str, score_data: Dict[str, Any],
                              trust_tier: str = "untrusted", **params):
        """Cache clearinghouse score with appropriate TTL."""
        if not self.redis_client:
            return
        
        cache_key = self._get_cache_key("clearinghouse", agent_id, **params)
        ttl = self._get_ttl(trust_tier)
        
        try:
            cached_data = {
                **score_data,
                "_cached_at": datetime.now(timezone.utc).isoformat(),
                "_cache_ttl": ttl,
                "_trust_tier": trust_tier
            }
            
            self.redis_client.setex(cache_key, ttl, json.dumps(cached_data))
            
            meta_key = f"meta:{cache_key}"
            self.redis_client.setex(meta_key, ttl, str(ttl))
            
        except Exception:
            self.metrics.errors += 1
    
    def invalidate_agent_cache(self, agent_id: str):
        """Invalidate all cached data for an agent."""
        if not self.redis_client:
            return
        
        try:
            # Find all keys for this agent
            patterns = [
                f"{TRUST_SCORE_KEY}{agent_id}*",
                f"{CLEARINGHOUSE_KEY}{agent_id}*",
                f"{METADATA_KEY}{agent_id}*",
                f"meta:{TRUST_SCORE_KEY}{agent_id}*",
                f"meta:{CLEARINGHOUSE_KEY}{agent_id}*"
            ]
            
            for pattern in patterns:
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            
            self.metrics.invalidations += 1
            self._record_metrics("Invalidation")
            
        except Exception:
            self.metrics.errors += 1
    
    def warm_cache_batch(self, agent_ids: List[str], 
                        calculate_fn, calculation_params: Dict[str, Any] = None):
        """Warm cache for multiple agents in batch."""
        if not self.redis_client or not agent_ids:
            return
        
        calculation_params = calculation_params or {}
        warmed_count = 0
        
        for agent_id in agent_ids[:MAX_CACHE_WARM_BATCH]:
            try:
                # Check if any cache entries need warming
                trust_key = self._get_cache_key("trust_score", agent_id)
                clearing_key = self._get_cache_key("clearinghouse", agent_id)
                
                needs_warming = (
                    self._should_warm_cache(trust_key) or 
                    self._should_warm_cache(clearing_key)
                )
                
                if needs_warming:
                    # Calculate fresh scores
                    fresh_data = calculate_fn(agent_id, **calculation_params)
                    if fresh_data:
                        trust_tier = fresh_data.get("trust_tier", "untrusted")
                        
                        # Update cache
                        if "trust_score" in fresh_data:
                            self.set_trust_score(agent_id, fresh_data, trust_tier)
                        
                        warmed_count += 1
                        
            except Exception:
                continue
        
        if warmed_count > 0:
            self._record_metrics("BatchWarm")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        redis_info = {}
        
        if self.redis_client:
            try:
                info = self.redis_client.info()
                redis_info = {
                    "connected": True,
                    "used_memory": info.get("used_memory_human", "0B"),
                    "keyspace_hits": info.get("keyspace_hits", 0),
                    "keyspace_misses": info.get("keyspace_misses", 0),
                    "connected_clients": info.get("connected_clients", 0)
                }
                
                # Get trust cache specific stats
                trust_keys = len(self.redis_client.keys(f"{TRUST_SCORE_KEY}*"))
                clearing_keys = len(self.redis_client.keys(f"{CLEARINGHOUSE_KEY}*"))
                
                redis_info.update({
                    "trust_cache_keys": trust_keys,
                    "clearinghouse_cache_keys": clearing_keys
                })
                
            except Exception:
                redis_info = {"connected": False, "error": "Connection failed"}
        else:
            redis_info = {"connected": False, "error": "Not initialized"}
        
        return {
            "cache_metrics": {
                "hits": self.metrics.hits,
                "misses": self.metrics.misses,
                "hit_ratio": f"{self.metrics.hit_ratio:.3f}",
                "warm_hits": self.metrics.warm_hits,
                "errors": self.metrics.errors,
                "invalidations": self.metrics.invalidations
            },
            "redis_info": redis_info,
            "configuration": {
                "ttl_config": TRUST_CACHE_TTL,
                "warm_threshold": WARM_CACHE_THRESHOLD,
                "max_batch_size": MAX_CACHE_WARM_BATCH
            }
        }
    
    def flush_cache(self, pattern: str = None):
        """Flush cache entries matching pattern (admin operation)."""
        if not self.redis_client:
            return 0
        
        try:
            if pattern:
                keys = self.redis_client.keys(pattern)
                if keys:
                    return self.redis_client.delete(*keys)
                return 0
            else:
                # Flush only trust-related caches
                patterns = [
                    f"{TRUST_SCORE_KEY}*",
                    f"{CLEARINGHOUSE_KEY}*",
                    f"{METADATA_KEY}*",
                    f"meta:{TRUST_SCORE_KEY}*",
                    f"meta:{CLEARINGHOUSE_KEY}*"
                ]
                
                total_deleted = 0
                for p in patterns:
                    keys = self.redis_client.keys(p)
                    if keys:
                        total_deleted += self.redis_client.delete(*keys)
                
                return total_deleted
                
        except Exception:
            return 0


# Global cache instance
_trust_cache = None

def get_trust_cache() -> TrustCache:
    """Get or create global trust cache instance."""
    global _trust_cache
    if _trust_cache is None:
        _trust_cache = TrustCache()
    return _trust_cache


def cached_trust_calculation(cache_key_type: str = "trust_score"):
    """
    Decorator for trust calculation functions to add caching.
    
    Usage:
    @cached_trust_calculation("trust_score")
    def calculate_trust_for_agent(agent_id, **kwargs):
        # Expensive trust calculation
        return trust_data
    """
    def decorator(func):
        def wrapper(agent_id: str, **kwargs):
            cache = get_trust_cache()
            
            # Try cache first
            if cache_key_type == "trust_score":
                cached_result = cache.get_trust_score(agent_id, **kwargs)
            elif cache_key_type == "clearinghouse":
                cached_result = cache.get_clearinghouse_score(agent_id, **kwargs)
            else:
                cached_result = None
            
            # Check if we need to warm cache
            warm_needed = cached_result and cached_result.get("_cache_warm_needed")
            
            if cached_result and not warm_needed:
                # Remove cache metadata before returning
                result = {k: v for k, v in cached_result.items() 
                         if not k.startswith("_cache")}
                return result
            
            # Calculate fresh result
            fresh_result = func(agent_id, **kwargs)
            
            if fresh_result:
                # Cache the result
                trust_tier = fresh_result.get("trust_tier", "untrusted")
                
                if cache_key_type == "trust_score":
                    cache.set_trust_score(agent_id, fresh_result, trust_tier, **kwargs)
                elif cache_key_type == "clearinghouse":
                    cache.set_clearinghouse_score(agent_id, fresh_result, trust_tier, **kwargs)
            
            return fresh_result
        
        return wrapper
    return decorator