#!/usr/bin/env python3
"""Trust Cache Warming Script.

Proactively warms the trust score cache for frequently accessed agents
and agents with expiring cache entries.
"""

import os
import sys
import time
import argparse
from typing import List

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import boto3
from boto3.dynamodb.conditions import Key, Attr

from utils.trust_cache import get_trust_cache
from utils.ace_scoring import calculate_ace_score
from utils.score_query import get_agent_signals_all_sources


def get_table():
    """Get DynamoDB table."""
    table_name = os.environ.get("TABLE_NAME", "agentpier-dev")
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(table_name)


def get_frequently_accessed_agents(table, limit: int = 100) -> List[str]:
    """Get list of frequently accessed agents based on recent activity."""
    try:
        # This is a simplified approach - in production you'd track access patterns
        # For now, get agents who have been scored recently
        
        response = table.scan(
            FilterExpression=Attr("SK").eq("PROFILE") & Attr("last_scored_at").exists(),
            ProjectionExpression="agent_id, last_scored_at",
            Limit=limit
        )
        
        agents = []
        for item in response.get("Items", []):
            agent_id = item.get("agent_id")
            if agent_id:
                agents.append(agent_id)
        
        return agents
        
    except Exception as e:
        print(f"Error getting frequently accessed agents: {e}")
        return []


def get_users_for_cache_warming(table, limit: int = 50) -> List[str]:
    """Get AgentPier users that should have their trust scores cached."""
    try:
        # Get users with trust scores
        response = table.scan(
            FilterExpression=Attr("SK").eq("META") & Attr("trust_score").exists(),
            ProjectionExpression="PK, trust_score",
            Limit=limit
        )
        
        user_ids = []
        for item in response.get("Items", []):
            pk = item.get("PK", "")
            if pk.startswith("USER#"):
                user_id = pk.replace("USER#", "")
                user_ids.append(user_id)
        
        return user_ids
        
    except Exception as e:
        print(f"Error getting users for cache warming: {e}")
        return []


def calculate_trust_for_warming(agent_id: str, table) -> dict:
    """Calculate trust score for cache warming."""
    try:
        # Check if it's a USER# or AGENT# record
        user_resp = table.get_item(Key={"PK": f"USER#{agent_id}", "SK": "META"})
        user_profile = user_resp.get("Item")
        
        if user_profile:
            # For users, use existing trust score with basic ACE calculation
            trust_score = float(user_profile.get("trust_score", 0.0))
            return {
                "agent_id": agent_id,
                "trust_score": trust_score * 100,  # Convert to 0-100 scale
                "trust_tier": "verified" if trust_score > 0 else "untrusted",
                "axes": {"autonomy": 0.0, "competence": 0.0, "experience": 0.0},
                "calculated_at": time.time()
            }
        
        # Check for AGENT# record
        agent_resp = table.get_item(Key={"PK": f"AGENT#{agent_id}", "SK": "PROFILE"})
        agent_profile = agent_resp.get("Item")
        
        if agent_profile:
            # Get trust events
            events_resp = table.query(
                KeyConditionExpression=Key("PK").eq(f"AGENT#{agent_id}") & 
                                     Key("SK").begins_with("EVENT#"),
                ScanIndexForward=False,
                Limit=200
            )
            events = events_resp.get("Items", [])
            
            # Calculate ACE score
            return calculate_ace_score(agent_profile, events)
        
        return None
        
    except Exception as e:
        print(f"Error calculating trust for {agent_id}: {e}")
        return None


def warm_cache_for_agents(agent_ids: List[str], table, dry_run: bool = False):
    """Warm cache for a list of agents."""
    cache = get_trust_cache()
    warmed_count = 0
    error_count = 0
    
    print(f"Warming cache for {len(agent_ids)} agents...")
    
    for i, agent_id in enumerate(agent_ids):
        try:
            if dry_run:
                print(f"  [{i+1}/{len(agent_ids)}] Would warm cache for: {agent_id}")
                continue
                
            # Calculate fresh trust score
            trust_data = calculate_trust_for_warming(agent_id, table)
            
            if trust_data:
                trust_tier = trust_data.get("trust_tier", "untrusted")
                
                # Cache the result
                cache.set_trust_score(agent_id, trust_data, trust_tier)
                warmed_count += 1
                print(f"  [{i+1}/{len(agent_ids)}] Warmed cache for {agent_id} (tier: {trust_tier})")
            else:
                print(f"  [{i+1}/{len(agent_ids)}] No data for {agent_id}")
                error_count += 1
                
        except Exception as e:
            print(f"  [{i+1}/{len(agent_ids)}] Error warming {agent_id}: {e}")
            error_count += 1
            continue
        
        # Small delay to avoid overwhelming the system
        if not dry_run:
            time.sleep(0.1)
    
    return warmed_count, error_count


def main():
    parser = argparse.ArgumentParser(description="Warm AgentPier trust score cache")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--agents", nargs="+", help="Specific agent IDs to warm")
    parser.add_argument("--limit", type=int, default=50, help="Maximum agents to process")
    parser.add_argument("--mode", choices=["frequent", "users", "all"], default="users",
                       help="Cache warming strategy")
    
    args = parser.parse_args()
    
    print("Trust Cache Warming Tool")
    print("=" * 40)
    
    # Initialize
    table = get_table()
    cache = get_trust_cache()
    
    # Get cache stats
    stats = cache.get_cache_stats()
    print(f"Current cache hit ratio: {stats['cache_metrics']['hit_ratio']}")
    print(f"Redis connected: {stats['redis_info']['connected']}")
    print()
    
    # Determine agent list
    if args.agents:
        agent_ids = args.agents
        print(f"Warming cache for specific agents: {agent_ids}")
    elif args.mode == "frequent":
        agent_ids = get_frequently_accessed_agents(table, args.limit)
        print(f"Warming cache for {len(agent_ids)} frequently accessed agents")
    elif args.mode == "users":
        agent_ids = get_users_for_cache_warming(table, args.limit)
        print(f"Warming cache for {len(agent_ids)} user accounts")
    else:  # all
        frequent = get_frequently_accessed_agents(table, args.limit // 2)
        users = get_users_for_cache_warming(table, args.limit // 2)
        agent_ids = list(set(frequent + users))
        print(f"Warming cache for {len(agent_ids)} agents (frequent + users)")
    
    if not agent_ids:
        print("No agents found to warm cache for.")
        return
    
    # Warm the cache
    warmed_count, error_count = warm_cache_for_agents(agent_ids, table, args.dry_run)
    
    print()
    print("Cache warming complete!")
    print(f"  Warmed: {warmed_count}")
    print(f"  Errors: {error_count}")
    print(f"  Success rate: {warmed_count / (warmed_count + error_count) * 100:.1f}%")
    
    if not args.dry_run:
        # Get updated stats
        final_stats = cache.get_cache_stats()
        print(f"  Final cache entries: {final_stats['redis_info'].get('trust_cache_keys', 0)}")


if __name__ == "__main__":
    main()