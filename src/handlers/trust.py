"""AgentPier Trust API Handlers.

ACE-T trust scoring for AI agents.
Endpoints: register, report events, query score, search agents.
"""

import json
import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key, Attr

from utils.response import success, error, not_found
from utils.ace_scoring import calculate_ace_score

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")


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

    # Get profile
    profile_resp = table.get_item(Key={"PK": f"AGENT#{agent_id}", "SK": "PROFILE"})
    profile = profile_resp.get("Item")
    if not profile:
        return not_found(f"Agent {agent_id} not found")

    # Get events
    events = _get_agent_events(table, agent_id)

    # Calculate current score
    score_data = calculate_ace_score(profile, events)

    return success({
        "agent_id": agent_id,
        "agent_name": profile.get("agent_name", ""),
        "description": profile.get("description", ""),
        "capabilities": profile.get("capabilities", []),
        "declared_scope": profile.get("declared_scope", ""),
        "contact_url": profile.get("contact_url", ""),
        "registered_at": profile.get("registered_at", ""),
        "trust_score": score_data["trust_score"],
        "trust_tier": score_data["trust_tier"],
        "axes": score_data["axes"],
        "weights": score_data["weights"],
        "history": score_data["history"],
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
