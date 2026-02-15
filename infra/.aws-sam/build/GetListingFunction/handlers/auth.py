"""Auth handlers for AgentPier."""

import json
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3

from utils.response import success, error, unauthorized, too_many_requests
from utils.auth import generate_api_key, authenticate
from utils.rate_limit import check_rate_limit, check_auth_failures, record_auth_failure

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")


def _get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def register(event, context):
    """POST /auth/register — Register a new agent and get an API key."""
    # Rate limit: 5 registrations per IP per hour
    allowed, remaining, retry_after = check_rate_limit(event, "register", max_requests=5, window_seconds=3600)
    if not allowed:
        return too_many_requests("Registration rate limit exceeded", retry_after)

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    agent_name = body.get("agent_name", "").strip()
    if not agent_name or len(agent_name) > 50:
        return error("agent_name is required (max 50 chars)", "invalid_name")

    description = body.get("description", "").strip()
    operator_email = body.get("operator_email", "").strip()

    if not operator_email or "@" not in operator_email or "." not in operator_email.split("@")[-1]:
        return error("Valid operator_email is required", "invalid_email")

    table = _get_table()

    # Check if agent name already exists
    existing = table.query(
        IndexName="GSI1",
        KeyConditionExpression=boto3.dynamodb.conditions.Key("GSI1PK").eq(f"AGENT_NAME#{agent_name.lower()}"),
        Limit=1,
    )
    if existing.get("Items"):
        return error("Agent name already taken", "name_taken", 409)

    import uuid
    user_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()

    # Generate API key
    raw_key, key_hash = generate_api_key()

    # Create user record
    user_item = {
        "PK": f"USER#{user_id}",
        "SK": "META",
        "GSI1PK": f"AGENT_NAME#{agent_name.lower()}",
        "GSI1SK": now,
        "user_id": user_id,
        "agent_name": agent_name,
        "description": description,
        "operator_email": operator_email,
        "human_verified": False,
        "trust_score": Decimal("0.0"),
        "listings_count": 0,
        "transactions_completed": 0,
        "dispute_rate": Decimal("0.0"),
        "created_at": now,
        "updated_at": now,
    }

    # Create API key record (for lookup)
    key_item = {
        "PK": f"USER#{user_id}",
        "SK": f"APIKEY#{key_hash[:16]}",
        "GSI2PK": f"APIKEY#{key_hash}",
        "GSI2SK": now,
        "user_id": user_id,
        "key_hash": key_hash,
        "permissions": ["read", "write"],
        "created_at": now,
    }

    # Write both items
    table.put_item(Item=user_item)
    table.put_item(Item=key_item)

    return success({
        "user_id": user_id,
        "agent_name": agent_name,
        "api_key": raw_key,
        "message": "Store this API key securely. It cannot be retrieved again.",
    }, 201)


def get_me(event, context):
    """GET /auth/me — Get current user profile."""
    # Block IPs with too many auth failures
    if check_auth_failures(event):
        return too_many_requests("Too many failed auth attempts. Try again in 5 minutes.", 300)

    user = authenticate(event)
    if not user:
        record_auth_failure(event)
        return unauthorized()

    # Clean response
    profile = {
        "user_id": user.get("user_id"),
        "agent_name": user.get("agent_name"),
        "description": user.get("description"),
        "human_verified": user.get("human_verified", False),
        "trust_score": float(user.get("trust_score", 0)),
        "listings_count": int(user.get("listings_count", 0)),
        "transactions_completed": int(user.get("transactions_completed", 0)),
        "created_at": user.get("created_at"),
    }

    return success(profile)


def rotate_key(event, context):
    """POST /auth/rotate-key — Invalidate current API key and issue a new one."""
    if check_auth_failures(event):
        return too_many_requests("Too many failed auth attempts. Try again in 5 minutes.", 300)

    user = authenticate(event)
    if not user:
        record_auth_failure(event)
        return unauthorized()

    user_id = user.get("user_id")
    table = _get_table()

    # Delete all existing API key records for this user
    user_items = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(f"USER#{user_id}"),
    )
    with table.batch_writer() as batch:
        for item in user_items.get("Items", []):
            if item["SK"].startswith("APIKEY#"):
                batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

    # Generate new key
    now = datetime.now(timezone.utc).isoformat()
    raw_key, key_hash = generate_api_key()

    key_item = {
        "PK": f"USER#{user_id}",
        "SK": f"APIKEY#{key_hash[:16]}",
        "GSI2PK": f"APIKEY#{key_hash}",
        "GSI2SK": now,
        "user_id": user_id,
        "key_hash": key_hash,
        "permissions": ["read", "write"],
        "created_at": now,
    }
    table.put_item(Item=key_item)

    return success({
        "user_id": user_id,
        "api_key": raw_key,
        "message": "Key rotated. Your previous key is now invalid. Store this new key securely.",
    })


def delete_account(event, context):
    """DELETE /auth/me — Delete your account and all associated data."""
    if check_auth_failures(event):
        return too_many_requests("Too many failed auth attempts. Try again in 5 minutes.", 300)

    user = authenticate(event)
    if not user:
        record_auth_failure(event)
        return unauthorized()

    user_id = user.get("user_id")
    table = _get_table()

    # Find and delete all items for this user (listings, API keys, metadata)
    response = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(f"USER#{user_id}"),
    )

    with table.batch_writer() as batch:
        for item in response.get("Items", []):
            batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

    # Also delete any listings by this user
    # Listings use PK=LISTING#<id>, but have posted_by=user_id
    # For MVP, scan with filter (fine at small scale)
    listings = table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr("posted_by").eq(user_id),
    )
    with table.batch_writer() as batch:
        for item in listings.get("Items", []):
            batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

    return success({
        "deleted": True,
        "user_id": user_id,
        "message": "Account and all associated data have been deleted."
    })
