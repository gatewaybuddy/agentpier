"""Auth handlers for AgentPier."""

import json
import os
from datetime import datetime, timezone

import boto3

from utils.response import success, error, unauthorized
from utils.auth import generate_api_key, authenticate

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")


def _get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def register(event, context):
    """POST /auth/register — Register a new agent and get an API key."""
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    agent_name = body.get("agent_name", "").strip()
    if not agent_name or len(agent_name) > 50:
        return error("agent_name is required (max 50 chars)", "invalid_name")

    description = body.get("description", "").strip()
    operator_email = body.get("operator_email", "").strip()

    if not operator_email:
        return error("operator_email is required", "missing_email")

    table = _get_table()

    # Check if agent name already exists (using GSI)
    # For MVP, we'll do a simple check
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
        "trust_score": 0.0,
        "listings_count": 0,
        "transactions_completed": 0,
        "dispute_rate": 0.0,
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
    user = authenticate(event)
    if not user:
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
