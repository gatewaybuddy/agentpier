"""AgentPier Trust API Handlers.

ACE-T trust scoring for AI agents.
Endpoints: register, report events, query score, search agents.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key, Attr

from utils.response import success, error, not_found
from utils.ace_scoring import calculate_ace_score, calculate_clearinghouse_score, moltbook_weight
from utils.score_query import get_agent_signals_all_sources
from utils.score_response import sanitize_score_response
from utils.audit import log_signal_access
from utils.moltbook import fetch_trust_metrics, calculate_trust_score, MoltbookError

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")
MOLTBOOK_CACHE_TTL_HOURS = 24


def _get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _parse_body(event):
    body = event.get("body", "{}")
    if isinstance(body, str):
        try:
            return json.loads(body)
        except (json.JSONDecodeError, TypeError):
            return {}
    return body or {}


def _get_agent_events(table, agent_id, limit=200):
    """Fetch trust events for an agent, most recent first."""
    response = table.query(
        KeyConditionExpression=Key("PK").eq(f"AGENT#{agent_id}") & Key("SK").begins_with("EVENT#"),
        ScanIndexForward=False,
        Limit=limit,
    )
    return response.get("Items", [])


def _recalculate_and_store(table, agent_id):
    """Recalculate trust score and update agent profile. Returns updated score dict."""
    # Fetch profile
    profile_resp = table.get_item(Key={"PK": f"AGENT#{agent_id}", "SK": "PROFILE"})
    profile = profile_resp.get("Item")
    if not profile:
        return None

    # Fetch events
    events = _get_agent_events(table, agent_id)

    # Calculate
    score_data = calculate_ace_score(profile, events)

    # Update profile with new score
    table.update_item(
        Key={"PK": f"AGENT#{agent_id}", "SK": "PROFILE"},
        UpdateExpression="SET trust_score = :s, trust_tier = :t, last_scored_at = :ts",
        ExpressionAttributeValues={
            ":s": str(score_data["trust_score"]),
            ":t": score_data["trust_tier"],
            ":ts": _now_iso(),
        },
    )

    return score_data


# === POST /trust/agents ===
def trust_register(event, context):
    """Register a new agent identity in the trust system."""
    body = _parse_body(event)

    agent_name = body.get("agent_name", "").strip()
    if not agent_name:
        return error("agent_name is required", "validation_error")

    capabilities = body.get("capabilities", [])
    if not isinstance(capabilities, list):
        return error("capabilities must be a list", "validation_error")

    declared_scope = body.get("declared_scope", "")
    contact_url = body.get("contact_url", "")
    description = body.get("description", "")

    agent_id = str(uuid.uuid4())
    now = _now_iso()

    profile = {
        "PK": f"AGENT#{agent_id}",
        "SK": "PROFILE",
        "agent_id": agent_id,
        "agent_name": agent_name,
        "capabilities": capabilities,
        "declared_scope": declared_scope,
        "contact_url": contact_url,
        "description": description,
        "registered_at": now,
        "trust_score": "0",
        "trust_tier": "untrusted",
        "last_scored_at": now,
    }

    table = _get_table()
    table.put_item(Item=profile)

    # Calculate initial score (cold start)
    score_data = calculate_ace_score(profile, [])
    table.update_item(
        Key={"PK": f"AGENT#{agent_id}", "SK": "PROFILE"},
        UpdateExpression="SET trust_score = :s, trust_tier = :t",
        ExpressionAttributeValues={
            ":s": str(score_data["trust_score"]),
            ":t": score_data["trust_tier"],
        },
    )

    return success({
        "agent_id": agent_id,
        "agent_name": agent_name,
        "trust_score": score_data["trust_score"],
        "trust_tier": score_data["trust_tier"],
        "axes": score_data["axes"],
        "registered_at": now,
    }, status_code=201)


# === POST /trust/agents/{agent_id}/events ===
def trust_report(event, context):
    """Report a trust event (execution outcome) for an agent."""
    agent_id = event.get("pathParameters", {}).get("agent_id", "")
    if not agent_id:
        return error("agent_id is required", "validation_error")

    body = _parse_body(event)

    event_type = body.get("event_type", "")
    valid_types = {"success", "failure", "safety_violation", "timeout"}
    if event_type not in valid_types:
        return error(
            f"event_type must be one of: {', '.join(sorted(valid_types))}",
            "validation_error"
        )

    table = _get_table()

    # Verify agent exists
    profile_resp = table.get_item(Key={"PK": f"AGENT#{agent_id}", "SK": "PROFILE"})
    if not profile_resp.get("Item"):
        return not_found(f"Agent {agent_id} not found")

    # Create event
    event_id = str(uuid.uuid4())
    now = _now_iso()
    trust_event = {
        "PK": f"AGENT#{agent_id}",
        "SK": f"EVENT#{now}#{event_id}",
        "event_id": event_id,
        "agent_id": agent_id,
        "event_type": event_type,
        "timestamp": now,
        "reporter_id": body.get("reporter_id", ""),
        "outcome_details": body.get("outcome_details", ""),
        "reversibility_observed": body.get("reversibility_observed"),
        "blast_radius_observed": body.get("blast_radius_observed"),
    }

    table.put_item(Item=trust_event)

    # Recalculate score
    score_data = _recalculate_and_store(table, agent_id)

    return success({
        "event_id": event_id,
        "agent_id": agent_id,
        "event_type": event_type,
        "trust_score": score_data["trust_score"],
        "trust_tier": score_data["trust_tier"],
        "axes": score_data["axes"],
        "recorded_at": now,
    }, status_code=201)


# === GET /trust/agents/{agent_id} ===
def trust_query(event, context):
    """Query an agent's full trust profile."""
    agent_id = event.get("pathParameters", {}).get("agent_id", "")
    if not agent_id:
        return error("agent_id is required", "validation_error")

    table = _get_table()

    # Get user profile (AgentPier users are stored as USER# not AGENT#)
    profile_resp = table.get_item(Key={"PK": f"USER#{agent_id}", "SK": "META"})
    profile = profile_resp.get("Item")
    if not profile:
        return not_found(f"Agent {agent_id} not found")

    # Get events (trust events for AgentPier users would be stored under USER#, not AGENT#)
    # For now, return default score since trust events system isn't fully integrated with user records
    events = []
    
    # Return default trust score breakdown when no trust events exist
    trust_score = float(profile.get("trust_score", 0.0))
    
    # Build default ACE score breakdown
    default_axes = {
        "autonomy": 0.0,
        "competence": 0.0,  
        "experience": 0.0
    }
    default_weights = {
        "autonomy": 0.4,
        "competence": 0.4,
        "experience": 0.2
    }
    default_history = {
        "total_events": 0,
        "success_events": 0,
        "failure_events": 0,
        "safety_violations": 0
    }

    # Build trust sources
    sources = {
        "agentpier": {
            "trust_score": trust_score,
            "events": 0,
        },
    }

    # Check for linked Moltbook account
    moltbook_name = profile.get("moltbook_name", "")
    combined_score = trust_score

    if moltbook_name:
        # Check if Moltbook data is stale and needs refreshing
        should_refresh = False
        last_refreshed = profile.get("moltbook_last_refreshed")
        
        if last_refreshed:
            try:
                last_refresh_dt = datetime.fromisoformat(last_refreshed.replace("Z", "+00:00"))
                if last_refresh_dt.tzinfo is None:
                    last_refresh_dt = last_refresh_dt.replace(tzinfo=timezone.utc)
                hours_since_refresh = (datetime.now(timezone.utc) - last_refresh_dt).total_seconds() / 3600
                should_refresh = hours_since_refresh >= MOLTBOOK_CACHE_TTL_HOURS
            except (ValueError, TypeError):
                should_refresh = True  # Invalid timestamp, refresh
        else:
            should_refresh = True  # No refresh timestamp, refresh

        moltbook_source = {
            "name": moltbook_name,
            "karma": int(profile.get("moltbook_karma", 0)),
            "age_days": 0,
            "verified": bool(profile.get("moltbook_verified")),
        }

        if should_refresh:
            # Try to refresh metrics from Moltbook
            try:
                moltbook_profile = fetch_trust_metrics(moltbook_name)
                trust_result = calculate_trust_score(moltbook_profile)
                
                # Update cached data in DynamoDB
                now = _now_iso()
                table.update_item(
                    Key={"PK": f"USER#{agent_id}", "SK": "META"},
                    UpdateExpression=(
                        "SET moltbook_karma = :mk, moltbook_last_refreshed = :mlr, "
                        "trust_score = :ts, trust_breakdown = :tb"
                    ),
                    ExpressionAttributeValues={
                        ":mk": trust_result["raw"]["karma"],
                        ":mlr": now,
                        ":ts": trust_result["trust_score"] / 100,  # normalize to 0-1
                        ":tb": {k: Decimal(str(v)) for k, v in trust_result["breakdown"].items()},
                    },
                )
                
                # Update source data
                moltbook_source["karma"] = trust_result["raw"]["karma"]
                moltbook_source["age_days"] = trust_result["raw"]["age_days"]
                moltbook_source["trust_score"] = trust_result["trust_score"]
                
            except MoltbookError:
                # Use cached data if Moltbook is unreachable (don't fail the request)
                moltbook_source["trust_score"] = trust_score * 100
                moltbook_source["cached"] = True
        else:
            # Use cached data
            moltbook_source["trust_score"] = trust_score * 100
            moltbook_source["cached"] = True

        # Calculate combined score with dynamic weighting
        # Count completed transactions for this agent (via GSI2)
        try:
            tx_result = table.query(
                IndexName="GSI2",
                KeyConditionExpression=Key("GSI2PK").eq(f"AGENT#{agent_id}"),
                Select="COUNT",
            )
            transaction_count = tx_result.get("Count", 0)
        except Exception:
            transaction_count = 0
        if moltbook_source.get("trust_score"):
            weight_moltbook = moltbook_weight(transaction_count)
            weight_agentpier = 1.0 - weight_moltbook
            combined_score = round(
                trust_score * 100 * weight_agentpier + moltbook_source["trust_score"] * weight_moltbook,
                2,
            )
            combined_score = min(95.0, combined_score)

        sources["moltbook"] = moltbook_source

    return success({
        "agent_id": agent_id,
        "agent_name": profile.get("username") or profile.get("agent_name", ""),
        "description": profile.get("description", ""),
        "capabilities": profile.get("capabilities", []),
        "declared_scope": profile.get("declared_scope", ""),
        "contact_url": profile.get("contact_method", {}).get("endpoint", ""),
        "registered_at": profile.get("created_at", ""),
        "trust_score": combined_score,
        "trust_tier": "untrusted" if combined_score == 0.0 else "verified",
        "axes": default_axes,
        "weights": default_weights,
        "history": default_history,
        "sources": sources,
    })


# === GET /trust/agents ===
def trust_search(event, context):
    """Search/list agents by score range, tier, or capability."""
    params = event.get("queryStringParameters") or {}

    min_score = params.get("min_score")
    max_score = params.get("max_score")
    tier = params.get("tier", "")
    capability = params.get("capability", "")
    limit = min(int(params.get("limit", "20")), 100)

    table = _get_table()

    # For MVP: scan with filters (replace with GSI for scale)
    scan_kwargs = {
        "FilterExpression": Attr("SK").eq("PROFILE"),
        "Limit": limit * 5,  # overscan to account for filtering
    }

    response = table.scan(**scan_kwargs)
    items = response.get("Items", [])

    results = []
    for item in items:
        score = float(item.get("trust_score", "0"))
        item_tier = item.get("trust_tier", "untrusted")
        item_caps = item.get("capabilities", [])

        # Apply filters
        if min_score and score < float(min_score):
            continue
        if max_score and score > float(max_score):
            continue
        if tier and item_tier != tier:
            continue
        if capability and capability not in item_caps:
            continue

        results.append({
            "agent_id": item.get("agent_id", ""),
            "agent_name": item.get("agent_name", ""),
            "trust_score": score,
            "trust_tier": item_tier,
            "declared_scope": item.get("declared_scope", ""),
            "registered_at": item.get("registered_at", ""),
        })

        if len(results) >= limit:
            break

    return success({
        "agents": results,
        "count": len(results),
        "limit": limit,
    })


def _get_marketplace_scores(table) -> dict:
    """Fetch trust scores for all registered marketplaces.

    Returns dict of {marketplace_id: trust_score (0-100)}.
    """
    scores = {}
    scan_kwargs = {
        "FilterExpression": Attr("SK").eq("PROFILE") & Attr("PK").begins_with("MARKETPLACE#"),
    }
    response = table.scan(**scan_kwargs)
    for item in response.get("Items", []):
        mp_id = item.get("marketplace_id", "")
        score = item.get("trust_score")
        if mp_id and score is not None:
            try:
                scores[mp_id] = float(score)
            except (ValueError, TypeError):
                pass
    return scores


# === GET /trust/agents/{agent_id}/clearinghouse-score ===
def trust_clearinghouse_score(event, context):
    """Public endpoint: cross-platform clearinghouse trust score.

    Aggregates signals from all marketplaces, calculates four-dimension
    score, and returns sanitized result (no marketplace source info).
    """
    agent_id = event.get("pathParameters", {}).get("agent_id", "")
    if not agent_id:
        return error("agent_id is required", "validation_error")

    table = _get_table()

    # Verify agent exists (check both AGENT# and USER# patterns)
    profile_resp = table.get_item(Key={"PK": f"AGENT#{agent_id}", "SK": "PROFILE"})
    profile = profile_resp.get("Item")
    if not profile:
        profile_resp = table.get_item(Key={"PK": f"USER#{agent_id}", "SK": "META"})
        profile = profile_resp.get("Item")
    if not profile:
        return not_found(f"Agent {agent_id} not found")

    # Fetch all signals across marketplaces (internal only)
    signals = get_agent_signals_all_sources(agent_id)

    # Fetch marketplace trust scores for source weighting
    marketplace_scores = _get_marketplace_scores(table)

    # Calculate clearinghouse score
    score_data = calculate_clearinghouse_score(
        agent_id=agent_id,
        signals=signals,
        marketplace_scores=marketplace_scores,
    )

    # Add agent_id to response
    score_data["agent_id"] = agent_id

    # Sanitize — strip any marketplace-identifying fields
    sanitized = sanitize_score_response(score_data)

    # Audit log
    ip = event.get("requestContext", {}).get("identity", {}).get("sourceIp", "")
    log_signal_access(
        accessor_id="public",
        accessor_type="system",
        agent_id=agent_id,
        action="clearinghouse_score_query",
        ip_address=ip,
    )

    return success(sanitized)


# === POST /trust/agents/{agent_id}/recalculate ===
def trust_recalculate(event, context):
    """Admin/system endpoint: force full recalculation from all signals.

    Recalculates the clearinghouse score and updates the agent profile.
    """
    agent_id = event.get("pathParameters", {}).get("agent_id", "")
    if not agent_id:
        return error("agent_id is required", "validation_error")

    table = _get_table()

    # Verify agent exists
    profile_resp = table.get_item(Key={"PK": f"AGENT#{agent_id}", "SK": "PROFILE"})
    profile = profile_resp.get("Item")
    if not profile:
        profile_resp = table.get_item(Key={"PK": f"USER#{agent_id}", "SK": "META"})
        profile = profile_resp.get("Item")
    if not profile:
        return not_found(f"Agent {agent_id} not found")

    # Fetch all signals across marketplaces
    signals = get_agent_signals_all_sources(agent_id)

    # Fetch marketplace trust scores
    marketplace_scores = _get_marketplace_scores(table)

    # Calculate clearinghouse score
    score_data = calculate_clearinghouse_score(
        agent_id=agent_id,
        signals=signals,
        marketplace_scores=marketplace_scores,
    )

    # Update stored score on agent profile
    pk = profile.get("PK", f"AGENT#{agent_id}")
    sk = profile.get("SK", "PROFILE")
    now = _now_iso()

    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression=(
            "SET trust_score = :s, trust_tier = :t, last_scored_at = :ts, "
            "clearinghouse_dimensions = :dims, clearinghouse_confidence = :conf"
        ),
        ExpressionAttributeValues={
            ":s": str(score_data["trust_score"]),
            ":t": score_data["trust_tier"],
            ":ts": now,
            ":dims": {k: Decimal(str(v)) for k, v in score_data["dimensions"].items()},
            ":conf": str(score_data["confidence"]),
        },
    )

    # Add agent_id to response
    score_data["agent_id"] = agent_id

    # Sanitize
    sanitized = sanitize_score_response(score_data)

    # Audit log
    ip = event.get("requestContext", {}).get("identity", {}).get("sourceIp", "")
    log_signal_access(
        accessor_id="system",
        accessor_type="admin",
        agent_id=agent_id,
        action="recalculate",
        ip_address=ip,
    )

    return success(sanitized)
