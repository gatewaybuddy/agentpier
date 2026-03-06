"""Badge API handlers for AgentPier.

Public endpoints for trust badge lookup, SVG rendering, verification,
and batch badge retrieval for marketplace listing pages.
"""

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone, timedelta

import boto3
from boto3.dynamodb.conditions import Key

from utils.response import success, error, not_found, too_many_requests, handler
from utils.rate_limit import check_rate_limit
from utils.score_query import get_agent_signals_all_sources
from utils.score_response import sanitize_score_response
from utils.ace_scoring import calculate_clearinghouse_score, get_trust_tier
from utils.badge_svg import (
    generate_compact_badge,
    generate_detailed_badge,
    generate_marketplace_badge,
)

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")
BADGE_SECRET = os.environ.get("CURSOR_SECRET", "badge-signing-secret-key-placeholder")
BADGE_VALIDITY_DAYS = 90


def _get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def _get_marketplace_scores_map(table) -> dict:
    """Fetch trust scores for all registered marketplaces."""
    scores = {}
    try:
        from boto3.dynamodb.conditions import Attr

        response = table.scan(
            FilterExpression=Attr("SK").eq("PROFILE")
            & Attr("PK").begins_with("MARKETPLACE#"),
        )
        for item in response.get("Items", []):
            mp_id = item.get("marketplace_id", "")
            score = item.get("trust_score") or item.get("marketplace_score")
            if mp_id and score is not None:
                try:
                    scores[mp_id] = float(score)
                except (ValueError, TypeError):
                    pass
    except Exception:
        pass
    return scores


def _compute_agent_badge(agent_id: str, table) -> dict:
    """Compute badge data for a single agent.

    Returns badge dict or None if agent not found.
    """
    # Look up agent (check both AGENT# and USER# patterns)
    profile = None
    for pk_prefix, sk in [("AGENT#", "PROFILE"), ("USER#", "META")]:
        resp = table.get_item(Key={"PK": f"{pk_prefix}{agent_id}", "SK": sk})
        profile = resp.get("Item")
        if profile:
            break

    if not profile:
        return None

    # Get signals and compute clearinghouse score
    signals = get_agent_signals_all_sources(agent_id)
    marketplace_scores = _get_marketplace_scores_map(table)
    now = datetime.now(timezone.utc)

    score_data = calculate_clearinghouse_score(
        agent_id=agent_id,
        signals=signals,
        marketplace_scores=marketplace_scores,
        now=now,
    )

    # Sanitize
    sanitized = sanitize_score_response(score_data)

    valid_until = (now + timedelta(days=BADGE_VALIDITY_DAYS)).isoformat()

    return {
        "agent_id": agent_id,
        "tier": sanitized.get("trust_tier", "untrusted"),
        "overall_score": int(sanitized.get("trust_score", 0)),
        "dimensions": sanitized.get("dimensions", {}),
        "confidence": sanitized.get("confidence", 0.2),
        "badge_image_url": f"/badges/{agent_id}/image?tier={sanitized.get('trust_tier', 'untrusted')}",
        "verification_url": f"/badges/{agent_id}/verify",
        "valid_until": valid_until,
        "last_updated": sanitized.get("last_updated", now.isoformat()),
    }


def _generate_signature(agent_id: str, tier: str, score: int, timestamp: str) -> str:
    """Generate HMAC-SHA256 signature for badge verification."""
    message = f"{agent_id}:{tier}:{score}:{timestamp}"
    return hmac.new(
        BADGE_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# === GET /badges/{agent_id} ===
@handler
def get_badge(event, context):
    """Public endpoint: badge data for an agent."""
    allowed, remaining, retry_after = check_rate_limit(
        event, "badge_lookup", max_requests=10000, window_seconds=86400
    )
    if not allowed:
        return too_many_requests("Badge lookup rate limit exceeded.", retry_after)

    path_params = event.get("pathParameters") or {}
    agent_id = path_params.get("agent_id", "")
    if not agent_id:
        return error("agent_id is required", "missing_id")

    table = _get_table()
    badge = _compute_agent_badge(agent_id, table)
    if badge is None:
        return not_found(f"Agent {agent_id} not found")

    return success(badge)


# === POST /badges/batch ===
@handler
def get_badges_batch(event, context):
    """Bulk badge lookup for marketplace listing pages."""
    allowed, remaining, retry_after = check_rate_limit(
        event, "badge_batch", max_requests=1000, window_seconds=86400
    )
    if not allowed:
        return too_many_requests("Batch badge rate limit exceeded.", retry_after)

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    agent_ids = body.get("agent_ids", [])
    if not isinstance(agent_ids, list):
        return error("agent_ids must be a list", "validation_error")

    if len(agent_ids) > 50:
        return error("Maximum 50 agent_ids per batch request", "batch_limit_exceeded")

    if not agent_ids:
        return success({"badges": []})

    table = _get_table()
    badges = []
    for agent_id in agent_ids:
        badge = _compute_agent_badge(str(agent_id), table)
        if badge is not None:
            badges.append(badge)

    return success({"badges": badges})


# === GET /badges/{agent_id}/image ===
@handler
def get_badge_image(event, context):
    """SVG badge image endpoint."""
    path_params = event.get("pathParameters") or {}
    agent_id = path_params.get("agent_id", "")
    if not agent_id:
        return error("agent_id is required", "missing_id")

    query_params = event.get("queryStringParameters") or {}
    style = query_params.get("style", "compact")

    table = _get_table()
    badge = _compute_agent_badge(agent_id, table)
    if badge is None:
        return not_found(f"Agent {agent_id} not found")

    tier = badge["tier"]
    score = badge["overall_score"]
    dimensions = badge.get("dimensions", {})

    if style == "detailed" and dimensions:
        svg = generate_detailed_badge(tier, score, dimensions)
    else:
        svg = generate_compact_badge(tier, score)

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "image/svg+xml",
            "Cache-Control": "public, max-age=14400",
            "Access-Control-Allow-Origin": "*",
        },
        "body": svg,
    }


# === GET /badges/{agent_id}/verify ===
@handler
def verify_badge(event, context):
    """Public verification page data with cryptographic signature."""
    path_params = event.get("pathParameters") or {}
    agent_id = path_params.get("agent_id", "")
    if not agent_id:
        return error("agent_id is required", "missing_id")

    table = _get_table()
    badge = _compute_agent_badge(agent_id, table)
    if badge is None:
        return not_found(f"Agent {agent_id} not found")

    # Look up agent name
    agent_name = ""
    for pk_prefix, sk in [("AGENT#", "PROFILE"), ("USER#", "META")]:
        resp = table.get_item(Key={"PK": f"{pk_prefix}{agent_id}", "SK": sk})
        profile = resp.get("Item")
        if profile:
            agent_name = profile.get("agent_name") or profile.get("username", "")
            break

    tier = badge["tier"]
    score = badge["overall_score"]
    timestamp = badge["last_updated"]
    signature = _generate_signature(agent_id, tier, score, timestamp)

    return success(
        {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "tier": tier,
            "overall_score": score,
            "dimensions": badge.get("dimensions", {}),
            "confidence": badge.get("confidence", 0.2),
            "last_updated": timestamp,
            "valid_until": badge.get("valid_until", ""),
            "signature": signature,
            "signature_algorithm": "HMAC-SHA256",
            "signed_fields": "agent_id:tier:overall_score:last_updated",
        }
    )


# === GET /badges/marketplace/{marketplace_id} ===
@handler
def get_marketplace_badge(event, context):
    """Marketplace badge endpoint."""
    allowed, remaining, retry_after = check_rate_limit(
        event, "badge_lookup", max_requests=10000, window_seconds=86400
    )
    if not allowed:
        return too_many_requests("Badge lookup rate limit exceeded.", retry_after)

    path_params = event.get("pathParameters") or {}
    marketplace_id = path_params.get("marketplace_id", "")
    if not marketplace_id:
        return error("marketplace_id is required", "missing_id")

    table = _get_table()
    resp = table.get_item(Key={"PK": f"MARKETPLACE#{marketplace_id}", "SK": "PROFILE"})
    item = resp.get("Item")
    if not item:
        return not_found("Marketplace not found")

    now = datetime.now(timezone.utc)
    score = int(float(item.get("marketplace_score", 0)))
    tier = item.get("tier", "registered")
    valid_until = (now + timedelta(days=BADGE_VALIDITY_DAYS)).isoformat()

    dimensions_raw = item.get("marketplace_dimensions")
    dimensions = {}
    if dimensions_raw:
        try:
            dimensions = (
                json.loads(dimensions_raw)
                if isinstance(dimensions_raw, str)
                else dimensions_raw
            )
        except (json.JSONDecodeError, TypeError):
            pass

    return success(
        {
            "marketplace_id": marketplace_id,
            "name": item.get("name", ""),
            "tier": tier,
            "overall_score": score,
            "dimensions": dimensions,
            "badge_image_url": f"/badges/marketplace/{marketplace_id}/image?tier={tier}",
            "verification_url": f"/badges/marketplace/{marketplace_id}/verify",
            "valid_until": valid_until,
            "last_updated": item.get("last_scored_at", now.isoformat()),
        }
    )
