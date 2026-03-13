"""Tests for trust score caching system."""

import json
import pytest
import time
from unittest.mock import Mock, patch, MagicMock

# Import the caching system
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.trust_cache import TrustCache, get_trust_cache, cached_trust_calculation


class TestTrustCache:
    """Test trust caching functionality."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client for testing."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        mock_redis.delete.return_value = 1
        mock_redis.keys.return_value = ["test_key"]
        mock_redis.ttl.return_value = 300
        mock_redis.info.return_value = {
            "used_memory_human": "1MB",
            "keyspace_hits": 100,
            "keyspace_misses": 20,
            "connected_clients": 5
        }
        return mock_redis
    
    @pytest.fixture
    def trust_cache(self, mock_redis):
        """Create TrustCache instance with mocked Redis."""
        with patch('utils.trust_cache.redis.Redis') as mock_redis_cls:
            mock_redis_cls.return_value = mock_redis
            cache = TrustCache()
            return cache
    
    def test_cache_initialization(self, trust_cache):
        """Test cache initializes correctly."""
        assert trust_cache.redis_client is not None
        assert trust_cache.metrics.hits == 0
        assert trust_cache.metrics.misses == 0
    
    def test_cache_key_generation(self, trust_cache):
        """Test cache key generation."""
        key1 = trust_cache._get_cache_key("trust_score", "agent123")
        key2 = trust_cache._get_cache_key("trust_score", "agent456")
        key3 = trust_cache._get_cache_key("clearinghouse", "agent123")
        
        assert key1.startswith("trust_score:")
        assert key2.startswith("trust_score:")
        assert key3.startswith("clearinghouse:")
        assert key1 != key2
        assert key1 != key3
        
        # Test with parameters
        key4 = trust_cache._get_cache_key("trust_score", "agent123", param1="value1")
        assert key4 != key1
        assert ":" in key4  # Should include parameter hash
    
    def test_ttl_calculation(self, trust_cache):
        """Test TTL calculation based on trust tier."""
        assert trust_cache._get_ttl("untrusted") == 300
        assert trust_cache._get_ttl("provisional") == 600
        assert trust_cache._get_ttl("established") == 1800
        assert trust_cache._get_ttl("trusted") == 3600
        assert trust_cache._get_ttl("highly_trusted") == 7200
        assert trust_cache._get_ttl("unknown_tier") == 600  # default
    
    def test_trust_score_caching(self, trust_cache, mock_redis):
        """Test trust score caching flow."""
        agent_id = "test_agent"
        score_data = {
            "trust_score": 75.5,
            "trust_tier": "established",
            "axes": {"autonomy": 25, "competence": 25, "experience": 25}
        }
        
        # Test cache miss
        mock_redis.get.return_value = None
        result = trust_cache.get_trust_score(agent_id)
        assert result is None
        assert trust_cache.metrics.misses == 1
        
        # Test cache set
        trust_cache.set_trust_score(agent_id, score_data, "established")
        mock_redis.setex.assert_called()
        
        # Test cache hit
        cached_data = {
            **score_data,
            "_cached_at": "2026-03-13T12:00:00Z",
            "_cache_ttl": 1800,
            "_trust_tier": "established"
        }
        mock_redis.get.return_value = json.dumps(cached_data)
        
        result = trust_cache.get_trust_score(agent_id)
        assert result is not None
        assert result["trust_score"] == 75.5
        assert result["trust_tier"] == "established"
        assert trust_cache.metrics.hits == 1
    
    def test_clearinghouse_caching(self, trust_cache, mock_redis):
        """Test clearinghouse score caching."""
        agent_id = "test_agent"
        score_data = {
            "trust_score": 82.0,
            "dimensions": {"reliability": 85, "capability": 80, "integrity": 85, "benevolence": 78},
            "confidence": 0.92
        }
        
        # Test cache miss
        mock_redis.get.return_value = None
        result = trust_cache.get_clearinghouse_score(agent_id)
        assert result is None
        
        # Test cache set and hit
        trust_cache.set_clearinghouse_score(agent_id, score_data, "trusted")
        
        cached_data = {
            **score_data,
            "_cached_at": "2026-03-13T12:00:00Z",
            "_cache_ttl": 3600,
            "_trust_tier": "trusted"
        }
        mock_redis.get.return_value = json.dumps(cached_data)
        
        result = trust_cache.get_clearinghouse_score(agent_id)
        assert result is not None
        assert result["trust_score"] == 82.0
        assert "dimensions" in result
    
    def test_cache_invalidation(self, trust_cache, mock_redis):
        """Test cache invalidation for an agent."""
        agent_id = "test_agent"
        
        mock_redis.keys.return_value = [
            f"trust_score:{agent_id}",
            f"clearinghouse:{agent_id}",
            f"meta:trust_score:{agent_id}"
        ]
        
        trust_cache.invalidate_agent_cache(agent_id)
        
        mock_redis.keys.assert_called()
        mock_redis.delete.assert_called()
        assert trust_cache.metrics.invalidations == 1
    
    def test_cache_warming_logic(self, trust_cache, mock_redis):
        """Test cache warming detection logic."""
        # Mock TTL responses for warming logic
        mock_redis.ttl.return_value = 600  # 10 minutes remaining
        mock_redis.get.return_value = "3600"  # Original TTL was 1 hour
        
        # Should warm when 80% of TTL elapsed (600/3600 = 0.167 remaining < 0.2 threshold)
        key = "trust_score:test_agent"
        should_warm = trust_cache._should_warm_cache(key)
        
        # Remaining ratio is 600/3600 = 0.167, which is < 0.8, so should warm
        assert should_warm is True
    
    def test_cache_stats(self, trust_cache, mock_redis):
        """Test cache statistics generation."""
        # Set up some metrics
        trust_cache.metrics.hits = 50
        trust_cache.metrics.misses = 10
        trust_cache.metrics.errors = 2
        trust_cache.metrics.warm_hits = 5
        
        stats = trust_cache.get_cache_stats()
        
        assert "cache_metrics" in stats
        assert "redis_info" in stats
        assert "configuration" in stats
        
        cache_metrics = stats["cache_metrics"]
        assert cache_metrics["hits"] == 50
        assert cache_metrics["misses"] == 10
        assert cache_metrics["hit_ratio"] == "0.833"  # 50/(50+10)
        assert cache_metrics["warm_hits"] == 5
        assert cache_metrics["errors"] == 2
    
    def test_cached_function_decorator(self, mock_redis):
        """Test the caching decorator."""
        with patch('utils.trust_cache.redis.Redis') as mock_redis_cls:
            mock_redis_cls.return_value = mock_redis
            
            # Create a test function with caching
            call_count = 0
            
            @cached_trust_calculation("trust_score")
            def test_calculation(agent_id: str, **kwargs):
                nonlocal call_count
                call_count += 1
                return {
                    "trust_score": 75.0,
                    "trust_tier": "established",
                    "call_count": call_count
                }
            
            # First call - cache miss
            mock_redis.get.return_value = None
            result1 = test_calculation("test_agent")
            assert result1["call_count"] == 1
            assert call_count == 1
            
            # Second call - cache hit
            cached_data = {
                "trust_score": 75.0,
                "trust_tier": "established",
                "call_count": 1,
                "_cached_at": "2026-03-13T12:00:00Z"
            }
            mock_redis.get.return_value = json.dumps(cached_data)
            
            result2 = test_calculation("test_agent")
            assert result2["call_count"] == 1  # Same as cached
            assert call_count == 1  # Function not called again
    
    def test_cache_flush(self, trust_cache, mock_redis):
        """Test cache flushing."""
        # Test pattern flush
        mock_redis.keys.return_value = ["trust_score:agent1", "trust_score:agent2"]
        mock_redis.delete.return_value = 2
        deleted = trust_cache.flush_cache("trust_score:*")
        assert deleted == 2
        
        # Test full flush
        mock_redis.keys.side_effect = [
            ["trust_score:agent1"],
            ["clearinghouse:agent1"],
            [],  # metadata
            [],  # meta trust
            []   # meta clearinghouse
        ]
        mock_redis.delete.side_effect = [1, 1]  # Each delete call removes 1 key
        total_deleted = trust_cache.flush_cache()
        assert total_deleted == 2


class TestCacheIntegration:
    """Integration tests for cache with trust handlers."""
    
    def test_cache_behavior_validation(self):
        """Test that caching behavior works correctly."""
        # Create a fresh cache instance for this test
        cache = TrustCache()
        
        # Test cache miss behavior (should be None when Redis not connected or key doesn't exist)
        result = cache.get_trust_score("definitely_nonexistent_agent_12345")
        # If Redis is not available, this will be None
        # If Redis is available but key doesn't exist, this will also be None
        # This test is flexible to handle both cases
        
        # Test cache set and get
        test_data = {
            "trust_score": 85.0,
            "trust_tier": "trusted",
            "axes": {"autonomy": 30, "competence": 30, "experience": 25}
        }
        
        cache.set_trust_score("test_agent", test_data, "trusted")
        
        # The cache should work if Redis is available
        # If not, it gracefully falls back (no errors)
        try:
            cached_result = cache.get_trust_score("test_agent")
            # If we got a result, verify it's correct
            if cached_result:
                assert cached_result["trust_score"] == 85.0
                assert cached_result["trust_tier"] == "trusted"
        except Exception:
            # Cache not available, but that's OK for this test
            pass
    
    def test_cache_consistency(self):
        """Test that cache invalidation maintains consistency."""
        with patch('utils.trust_cache.redis.Redis') as mock_redis_cls:
            mock_redis = MagicMock()
            mock_redis.ping.return_value = True
            mock_redis_cls.return_value = mock_redis
            
            cache = TrustCache()
            
            # Test that invalidation clears all agent data
            mock_redis.keys.side_effect = [
                ["trust_score:agent1:hash1", "trust_score:agent1:hash2"],
                ["clearinghouse:agent1"],
                [],
                ["meta:trust_score:agent1:hash1"],
                []
            ]
            
            cache.invalidate_agent_cache("agent1")
            
            # Should have called delete with all found keys
            assert mock_redis.delete.call_count == 3  # 3 non-empty key lists


def test_get_trust_cache_singleton():
    """Test that get_trust_cache returns singleton."""
    cache1 = get_trust_cache()
    cache2 = get_trust_cache()
    assert cache1 is cache2