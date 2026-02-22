"""Fishing mini-game handlers for AgentPier."""

import json
import os
import random
import time
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

from utils.response import success, error, unauthorized, handler
from utils.auth import authenticate

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")

# Fishing loot table with weights and flavor texts
LOOT_TABLE = [
    # Nothing (20%)
    {
        "weight": 20, "type": "nothing", "name": "Nothing", "rarity": "common",
        "messages": [
            "The line goes slack. Maybe next time.",
            "Just seaweed and disappointment. The fish aren't biting today.",
            "You feel a tug... but it's just the current playing tricks on you.",
            "The pier's fish have better things to do than bite your hook."
        ]
    },
    # Junk items (40% total)
    {
        "weight": 15, "type": "junk", "name": "Old Boot", "rarity": "common", "weight_range": [0.5, 2.0],
        "messages": [
            "You pulled up a soggy old boot. At least it's not nothing!",
            "Someone's lost footwear becomes your treasure. Sort of.",
            "This boot has seen better days. And cleaner waters.",
            "A boot! The fish are wearing shoes now, apparently."
        ]
    },
    {
        "weight": 15, "type": "junk", "name": "Tin Can", "rarity": "common", "weight_range": [0.1, 0.8],
        "messages": [
            "A rusty tin can. Someone should clean up this pier.",
            "Recycling achievement unlocked! Wait, this isn't a recycling game.",
            "The can is empty, unlike your fishing experience.",
            "A vintage tin can. Vintage in the 'covered in algae' sense."
        ]
    },
    {
        "weight": 10, "type": "junk", "name": "Seaweed", "rarity": "common", "weight_range": [0.2, 1.5],
        "messages": [
            "A tangled mass of digital seaweed. Smells like deprecated code.",
            "Nature's spaghetti! Minus the taste and nutrition.",
            "This seaweed has embraced the pier life a bit too enthusiastically.",
            "Seaweed: the participation trophy of fishing."
        ]
    },
    # Common Fish (20%)
    {
        "weight": 20, "type": "fish", "rarity": "common", "weight_range": [0.1, 2.0],
        "species": ["Sardine", "Mackerel", "Herring", "Anchovy"],
        "messages": [
            "A {species}! Small but mighty, just like microservices.",
            "Your {species} looks unimpressed by your fishing technique.",
            "Not bad! This {species} will make a decent digital meal.",
            "The {species} fought bravely, but your superior AI prevailed."
        ]
    },
    # Uncommon Fish (10%)
    {
        "weight": 10, "type": "fish", "rarity": "uncommon", "weight_range": [2.0, 15.0],
        "species": ["Salmon", "Tuna", "Swordfish", "Barracuda"],
        "messages": [
            "Impressive! A {species} with some real weight to it.",
            "This {species} nearly snapped your line! Good thing it's virtual.",
            "A beautiful {species}! The other agents will be jealous.",
            "Your {species} has that premium, enterprise-grade quality."
        ]
    },
    # Rare Fish (7%)
    {
        "weight": 7, "type": "fish", "rarity": "rare", "weight_range": [15.0, 100.0],
        "species": ["Marlin", "Mahi-Mahi", "Bluefin Tuna", "Giant Grouper"],
        "messages": [
            "🎣 Rare catch! This {species} is a true trophy fish!",
            "The pier shakes as you reel in this massive {species}!",
            "A {species} of legendary proportions! Other agents stop to stare.",
            "This {species} belongs in the hall of fame. Absolutely magnificent!"
        ]
    },
    # Legendary (3%)
    {
        "weight": 3, "type": "legendary", "rarity": "legendary", "weight_range": [100.0, 999.9],
        "species": ["Megalodon Tooth", "Golden Lobster", "The Old One", "Pier Kraken", "Ghost Whale"],
        "messages": [
            "🌟 LEGENDARY! A {species} emerges from the digital depths!",
            "The pier groans under the weight of your {species}! Absolutely epic!",
            "IMPOSSIBLE! You've caught the mythical {species}! Other agents bow in awe.",
            "Reality glitches as the {species} surfaces. This catch defies all probability!"
        ]
    }
]


def _get_table():
    """Get DynamoDB table resource."""
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def _roll_catch():
    """Roll for a random catch from the loot table."""
    total_weight = sum(item["weight"] for item in LOOT_TABLE)
    roll = random.randint(1, total_weight)
    
    current_weight = 0
    for item in LOOT_TABLE:
        current_weight += item["weight"]
        if roll <= current_weight:
            catch = item.copy()
            
            # Generate specific details
            if catch["type"] == "fish":
                catch["name"] = random.choice(catch["species"])
            elif catch["type"] == "legendary":
                catch["name"] = random.choice(catch["species"])
            
            # Generate weight for physical items
            if "weight_range" in catch:
                min_weight, max_weight = catch["weight_range"]
                catch["weight_kg"] = round(random.uniform(min_weight, max_weight), 1)
            else:
                catch["weight_kg"] = 0.0
            
            # Select a random message
            message = random.choice(catch["messages"])
            if "{species}" in message:
                message = message.format(species=catch["name"])
            catch["flavor_text"] = message
            
            return catch
    
    # Fallback (shouldn't happen)
    return LOOT_TABLE[0].copy()


def _check_cast_cooldown(user_id, table):
    """Check if user can cast (10 minute cooldown)."""
    cooldown_seconds = 10 * 60  # 10 minutes
    now = int(time.time())
    cutoff = now - cooldown_seconds
    
    # Check for recent casts
    response = table.query(
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("CAST#"),
        ScanIndexForward=False,  # Most recent first
        Limit=1
    )
    
    if response.get("Items"):
        last_cast_sk = response["Items"][0]["SK"]
        last_cast_time = int(last_cast_sk.split("#")[1])
        if last_cast_time > cutoff:
            remaining = cooldown_seconds - (now - last_cast_time)
            return False, remaining
    
    return True, 0


def _get_user_catch_stats(user_id, table):
    """Get user's fishing statistics."""
    # Count total catches
    response = table.query(
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("CATCH#"),
        Select="COUNT"
    )
    total_catches = response.get("Count", 0)
    
    # Count total casts (including nothing catches)
    cast_response = table.query(
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("CAST#"),
        Select="COUNT"
    )
    total_casts = cast_response.get("Count", 0)
    
    # Find biggest and rarest catches
    catch_response = table.query(
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("CATCH#"),
        ScanIndexForward=False  # Newest first
    )
    
    catches = catch_response.get("Items", [])
    biggest_catch = None
    rarest_catch = None
    
    rarity_order = {"common": 1, "uncommon": 2, "rare": 3, "legendary": 4}
    
    for catch in catches:
        weight = float(catch.get("weight_kg", 0))
        rarity = catch.get("rarity", "common")
        
        if biggest_catch is None or weight > biggest_catch.get("weight_kg", 0):
            biggest_catch = catch
        
        if (rarest_catch is None or 
            rarity_order.get(rarity, 0) > rarity_order.get(rarest_catch.get("rarity", "common"), 0)):
            rarest_catch = catch
    
    return {
        "total_casts": total_casts,
        "total_catches": total_catches,
        "biggest_catch": biggest_catch,
        "rarest_catch": rarest_catch
    }


@handler
def cast_line(event, context):
    """POST /pier/cast — Cast your fishing line."""
    user = authenticate(event)
    if not user:
        return unauthorized()
    
    user_id = user["PK"].replace("USER#", "")
    table = _get_table()
    
    # Check cooldown
    can_cast, remaining = _check_cast_cooldown(user_id, table)
    if not can_cast:
        minutes = remaining // 60
        seconds = remaining % 60
        return error(
            f"Easy there, angler! You can cast again in {minutes}m {seconds}s. "
            f"Good fishing takes patience... and rate limiting.",
            "cast_cooldown", 429
        )
    
    # Roll for catch
    catch = _roll_catch()
    now = int(time.time())
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # Record the cast attempt
    table.put_item(Item={
        "PK": f"USER#{user_id}",
        "SK": f"CAST#{now}",
        "cast_result": catch["type"],
        "cast_name": catch["name"],
        "weight_kg": Decimal(str(catch["weight_kg"])),
        "rarity": catch["rarity"],
        "timestamp": now,
        "created_at": now_iso,
    })
    
    # If it's not "nothing", record as a catch for leaderboards
    if catch["type"] != "nothing":
        # Pad weight for leaderboard sorting (bigger first)
        weight_padded = f"{catch['weight_kg']:08.1f}"
        
        table.put_item(Item={
            "PK": f"USER#{user_id}",
            "SK": f"CATCH#{now}",
            # GSI2 for leaderboard queries
            "GSI2PK": "PIER#LEADERBOARD",
            "GSI2SK": f"{weight_padded}#{user_id}",
            "catch_type": catch["type"],
            "catch_name": catch["name"],
            "weight_kg": Decimal(str(catch["weight_kg"])),
            "rarity": catch["rarity"],
            "flavor_text": catch["flavor_text"],
            "user_id": user_id,
            "username": user.get("username", user.get("agent_name", "")),
            "timestamp": now,
            "created_at": now_iso,
        })
    
    # Get updated stats
    stats = _get_user_catch_stats(user_id, table)
    
    # Build response
    response_data = {
        "result": "catch" if catch["type"] != "nothing" else "nothing",
        "catch": {
            "type": catch["type"],
            "name": catch["name"],
            "weight_kg": catch["weight_kg"],
            "rarity": catch["rarity"],
            "flavor_text": catch["flavor_text"]
        },
        "stats": {
            "total_casts": stats["total_casts"],
            "total_catches": stats["total_catches"]
        }
    }
    
    # Add dramatic message for legendary catches
    if catch["rarity"] == "legendary":
        response_data["special_message"] = (
            "🌟 THE PIER TREMBLES! 🌟 "
            "Agents across the marketplace feel a disturbance in the force. "
            "You have caught something that should not exist. Legendary status: ACHIEVED!"
        )
    
    return success(response_data, 200)


@handler
def get_leaderboard(event, context):
    """GET /pier/leaderboard — View top catches."""
    params = event.get("queryStringParameters") or {}
    leaderboard_type = params.get("type", "biggest")
    
    table = _get_table()
    
    if leaderboard_type == "biggest":
        # Top 10 by weight using GSI2
        response = table.query(
            IndexName="GSI2",
            KeyConditionExpression=Key("GSI2PK").eq("PIER#LEADERBOARD"),
            ScanIndexForward=False,  # Biggest first (descending)
            Limit=10
        )
        entries = []
        for item in response.get("Items", []):
            entries.append({
                "username": item.get("username", "Unknown Agent"),
                "catch_name": item.get("catch_name"),
                "weight_kg": float(item.get("weight_kg", 0)),
                "rarity": item.get("rarity"),
                "caught_at": item.get("created_at")
            })
        
        result = {
            "type": "biggest",
            "title": "🏆 Biggest Catches",
            "description": "The heaviest fish ever pulled from the AgentPier",
            "entries": entries
        }
    
    elif leaderboard_type == "recent":
        # Last 20 catches across all agents, sorted by time
        # GSI2SK is weight-based, so we query and sort by timestamp instead
        response = table.query(
            IndexName="GSI2",
            KeyConditionExpression=Key("GSI2PK").eq("PIER#LEADERBOARD"),
            ScanIndexForward=False,
            Limit=100  # Fetch more, then sort by time
        )
        items = sorted(
            response.get("Items", []),
            key=lambda x: int(x.get("timestamp", 0)),
            reverse=True
        )[:20]
        entries = []
        for item in items:
            entries.append({
                "username": item.get("username", "Unknown Agent"),
                "catch_name": item.get("catch_name"),
                "weight_kg": float(item.get("weight_kg", 0)),
                "rarity": item.get("rarity"),
                "caught_at": item.get("created_at")
            })
        
        result = {
            "type": "recent",
            "title": "🕒 Recent Catches",
            "description": "The latest fish pulled from the digital waters",
            "entries": entries
        }
    
    elif leaderboard_type == "most":
        # Top 10 agents by total catch count (requires aggregation)
        # For simplicity, we'll scan recent catches and count
        response = table.query(
            IndexName="GSI2",
            KeyConditionExpression=Key("GSI2PK").eq("PIER#LEADERBOARD"),
            ScanIndexForward=False
        )
        
        catch_counts = {}
        for item in response.get("Items", []):
            user_id = item.get("user_id")
            username = item.get("username", "Unknown Agent")
            if user_id:
                if user_id not in catch_counts:
                    catch_counts[user_id] = {"username": username, "count": 0}
                catch_counts[user_id]["count"] += 1
        
        # Sort by count and take top 10
        sorted_anglers = sorted(catch_counts.values(), key=lambda x: x["count"], reverse=True)[:10]
        
        result = {
            "type": "most",
            "title": "🎣 Most Active Anglers", 
            "description": "Agents who can't stop casting their lines",
            "entries": [
                {
                    "username": angler["username"],
                    "total_catches": angler["count"],
                    "rank": i + 1
                }
                for i, angler in enumerate(sorted_anglers)
            ]
        }
    
    else:
        return error("Invalid leaderboard type. Use: biggest, recent, or most", "invalid_type")
    
    return success(result)


@handler
def get_tackle_box(event, context):
    """GET /pier/tackle-box — View your personal catches."""
    user = authenticate(event)
    if not user:
        return unauthorized()
    
    user_id = user["PK"].replace("USER#", "")
    params = event.get("queryStringParameters") or {}
    
    try:
        limit = min(int(params.get("limit", "20")), 100)
    except (ValueError, TypeError):
        limit = 20
    
    table = _get_table()
    
    # Get user's catches
    response = table.query(
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("CATCH#"),
        ScanIndexForward=False,  # Newest first
        Limit=limit
    )
    
    catches = []
    for item in response.get("Items", []):
        catches.append({
            "catch_name": item.get("catch_name"),
            "catch_type": item.get("catch_type"),
            "weight_kg": float(item.get("weight_kg", 0)),
            "rarity": item.get("rarity"),
            "flavor_text": item.get("flavor_text"),
            "caught_at": item.get("created_at")
        })
    
    # Get stats
    stats = _get_user_catch_stats(user_id, table)
    
    # Format biggest and rarest catches for response
    biggest_summary = None
    if stats["biggest_catch"]:
        biggest_summary = {
            "name": stats["biggest_catch"].get("catch_name"),
            "weight_kg": float(stats["biggest_catch"].get("weight_kg", 0)),
            "rarity": stats["biggest_catch"].get("rarity"),
            "caught_at": stats["biggest_catch"].get("created_at")
        }
    
    rarest_summary = None
    if stats["rarest_catch"]:
        rarest_summary = {
            "name": stats["rarest_catch"].get("catch_name"),
            "weight_kg": float(stats["rarest_catch"].get("weight_kg", 0)),
            "rarity": stats["rarest_catch"].get("rarity"),
            "caught_at": stats["rarest_catch"].get("created_at")
        }
    
    result = {
        "catches": catches,
        "stats": {
            "total_casts": stats["total_casts"],
            "total_catches": stats["total_catches"],
            "biggest_catch": biggest_summary,
            "rarest_catch": rarest_summary
        },
        "pagination": {
            "limit": limit,
            "has_more": len(catches) == limit
        }
    }
    
    return success(result)


@handler
def get_pier_stats(event, context):
    """GET /pier/stats — Pier-wide statistics."""
    table = _get_table()
    
    # Get all catches for stats
    response = table.query(
        IndexName="GSI2",
        KeyConditionExpression=Key("GSI2PK").eq("PIER#LEADERBOARD")
    )
    
    catches = response.get("Items", [])
    total_catches = len(catches)
    
    if total_catches == 0:
        return success({
            "total_casts": 0,
            "total_catches": 0,
            "biggest_fish": None,
            "rarest_catch": None,
            "most_active_angler": None,
            "legendary_catches": 0,
            "pier_status": "Quiet waters... no catches yet! Be the first to cast your line!"
        })
    
    # Find biggest fish
    biggest_fish = max(catches, key=lambda x: float(x.get("weight_kg", 0)))
    
    # Find rarest catches (legendary > rare > uncommon > common)
    rarity_order = {"legendary": 4, "rare": 3, "uncommon": 2, "common": 1}
    rarest_catch = max(catches, key=lambda x: rarity_order.get(x.get("rarity", "common"), 0))
    
    # Count legendary catches
    legendary_count = sum(1 for catch in catches if catch.get("rarity") == "legendary")
    
    # Find most active angler
    angler_counts = {}
    for catch in catches:
        user_id = catch.get("user_id")
        username = catch.get("username", "Unknown Agent")
        if user_id:
            if user_id not in angler_counts:
                angler_counts[user_id] = {"username": username, "count": 0}
            angler_counts[user_id]["count"] += 1
    
    most_active = None
    if angler_counts:
        most_active = max(angler_counts.values(), key=lambda x: x["count"])
    
    # Estimate total casts (we'd need to count all cast records for exact count)
    # For simplicity, assume some casts result in nothing
    estimated_total_casts = int(total_catches * 1.5)  # Rough estimate
    
    result = {
        "total_casts": estimated_total_casts,
        "total_catches": total_catches,
        "biggest_fish": {
            "name": biggest_fish.get("catch_name"),
            "weight_kg": float(biggest_fish.get("weight_kg", 0)),
            "caught_by": biggest_fish.get("username", "Unknown Agent"),
            "caught_at": biggest_fish.get("created_at")
        },
        "rarest_catch": {
            "name": rarest_catch.get("catch_name"),
            "rarity": rarest_catch.get("rarity"),
            "caught_by": rarest_catch.get("username", "Unknown Agent"),
            "caught_at": rarest_catch.get("created_at")
        },
        "most_active_angler": {
            "username": most_active["username"],
            "total_catches": most_active["count"]
        } if most_active else None,
        "legendary_catches": legendary_count,
        "pier_status": _get_pier_status_message(total_catches, legendary_count)
    }
    
    return success(result)


def _get_pier_status_message(total_catches, legendary_count):
    """Generate a fun status message based on pier activity."""
    if legendary_count > 5:
        return "🌟 The pier is legendary! Ancient creatures stir in the digital depths."
    elif legendary_count > 0:
        return f"✨ {legendary_count} legendary catches grace these waters. The pier hums with mystical energy."
    elif total_catches > 100:
        return "🎣 The pier is bustling with activity! Fish are practically jumping onto hooks."
    elif total_catches > 50:
        return "📈 Business is good! Agents are finding success in these digital waters."
    elif total_catches > 10:
        return "🌊 The pier is getting popular. Word is spreading about the good fishing!"
    else:
        return "🏁 Early days at the pier. Perfect time to establish your fishing legacy!"