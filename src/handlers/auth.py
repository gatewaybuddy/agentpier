"""Auth handlers for AgentPier."""

import json
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3

from utils.response import success, error, unauthorized, too_many_requests
from utils.auth import generate_api_key, authenticate
from utils.rate_limit import check_rate_limit, check_auth_failures, record_auth_failure
from utils.moltbook import (
    verify_moltbook_key, fetch_trust_metrics, calculate_trust_score,
    MoltbookAuthError, MoltbookAPIError,
)

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

    # Include Moltbook data when linked
    if user.get("moltbook_verified"):
        profile["moltbook_linked"] = True
        profile["moltbook_name"] = user.get("moltbook_name", "")
        profile["moltbook_karma"] = int(user.get("moltbook_karma", 0))
        profile["moltbook_verified_at"] = user.get("moltbook_verified_at", "")
        trust_breakdown = user.get("trust_breakdown")
        if trust_breakdown:
            profile["trust_breakdown"] = {
                k: float(v) for k, v in trust_breakdown.items()
            }
    else:
        profile["moltbook_linked"] = False

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

    # Delete all records for this user with pagination
    items_to_delete = []
    
    # 1. Delete USER# records (API keys, metadata)
    last_key = None
    while True:
        query_kwargs = {
            "KeyConditionExpression": boto3.dynamodb.conditions.Key("PK").eq(f"USER#{user_id}")
        }
        if last_key:
            query_kwargs["ExclusiveStartKey"] = last_key
            
        response = table.query(**query_kwargs)
        items_to_delete.extend(response.get("Items", []))
        
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
    
    # 2. Delete TRUST# records
    last_key = None
    while True:
        query_kwargs = {
            "KeyConditionExpression": boto3.dynamodb.conditions.Key("PK").eq(f"TRUST#{user_id}")
        }
        if last_key:
            query_kwargs["ExclusiveStartKey"] = last_key
            
        response = table.query(**query_kwargs)
        items_to_delete.extend(response.get("Items", []))
        
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
    
    # 3. Delete ABUSE# records 
    last_key = None
    while True:
        query_kwargs = {
            "KeyConditionExpression": boto3.dynamodb.conditions.Key("PK").eq(f"ABUSE#{user_id}")
        }
        if last_key:
            query_kwargs["ExclusiveStartKey"] = last_key
            
        response = table.query(**query_kwargs)
        items_to_delete.extend(response.get("Items", []))
        
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
    
    # 4. Delete listings using GSI2 (more efficient than table scan)
    last_key = None
    while True:
        query_kwargs = {
            "IndexName": "GSI2",
            "KeyConditionExpression": boto3.dynamodb.conditions.Key("GSI2PK").eq(f"AGENT#{user_id}")
        }
        if last_key:
            query_kwargs["ExclusiveStartKey"] = last_key
            
        response = table.query(**query_kwargs)
        items_to_delete.extend(response.get("Items", []))
        
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
    
    # Batch delete all items (DynamoDB batch_writer handles the 25-item limit automatically)
    with table.batch_writer() as batch:
        for item in items_to_delete:
            batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

    return success({
        "deleted": True,
        "user_id": user_id,
        "message": "Account and all associated data have been deleted."
    })


def link_moltbook(event, context):
    """POST /auth/link-moltbook — Link a Moltbook account to your AgentPier profile."""
    if check_auth_failures(event):
        return too_many_requests("Too many failed auth attempts. Try again in 5 minutes.", 300)

    user = authenticate(event)
    if not user:
        record_auth_failure(event)
        return unauthorized()

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    moltbook_api_key = body.get("moltbook_api_key", "").strip()
    if not moltbook_api_key:
        return error("moltbook_api_key is required", "missing_field")

    # Check if already linked
    if user.get("moltbook_verified"):
        return error(
            f"Already linked to Moltbook account '{user.get('moltbook_name')}'. Unlink first.",
            "already_linked", 409,
        )

    # Verify the Moltbook key
    try:
        moltbook_profile = verify_moltbook_key(moltbook_api_key)
    except MoltbookAuthError:
        return error("Invalid Moltbook API key", "invalid_moltbook_key", 401)
    except MoltbookAPIError as e:
        return error(f"Could not reach Moltbook: {e}", "moltbook_unavailable", 502)

    agent_data = moltbook_profile.get("agent", {})
    moltbook_name = agent_data.get("name", "")

    # Calculate trust score from Moltbook metrics
    trust_result = calculate_trust_score(moltbook_profile)

    now = datetime.now(timezone.utc).isoformat()
    user_id = user.get("user_id")
    table = _get_table()

    # Update user record with Moltbook data (never store the API key)
    table.update_item(
        Key={"PK": f"USER#{user_id}", "SK": "META"},
        UpdateExpression=(
            "SET moltbook_name = :mn, moltbook_verified = :mv, "
            "moltbook_verified_at = :mvat, moltbook_karma = :mk, "
            "moltbook_account_age = :maa, moltbook_has_owner = :mho, "
            "trust_score = :ts, trust_breakdown = :tb, updated_at = :now"
        ),
        ExpressionAttributeValues={
            ":mn": moltbook_name,
            ":mv": True,
            ":mvat": now,
            ":mk": agent_data.get("karma", 0),
            ":maa": agent_data.get("created_at", ""),
            ":mho": bool(agent_data.get("owner")),
            ":ts": Decimal(str(trust_result["trust_score"])),
            ":tb": trust_result["breakdown"],
            ":now": now,
        },
    )

    return success({
        "linked": True,
        "moltbook_name": moltbook_name,
        "trust_score": trust_result["trust_score"],
        "trust_breakdown": trust_result["breakdown"],
    })


def unlink_moltbook(event, context):
    """POST /auth/unlink-moltbook — Remove Moltbook link from your profile."""
    if check_auth_failures(event):
        return too_many_requests("Too many failed auth attempts. Try again in 5 minutes.", 300)

    user = authenticate(event)
    if not user:
        record_auth_failure(event)
        return unauthorized()

    if not user.get("moltbook_verified"):
        return error("No Moltbook account linked", "not_linked")

    user_id = user.get("user_id")
    now = datetime.now(timezone.utc).isoformat()
    table = _get_table()

    # Remove all Moltbook fields and reset trust score
    table.update_item(
        Key={"PK": f"USER#{user_id}", "SK": "META"},
        UpdateExpression=(
            "REMOVE moltbook_name, moltbook_verified, moltbook_verified_at, "
            "moltbook_karma, moltbook_account_age, moltbook_has_owner, trust_breakdown "
            "SET trust_score = :ts, updated_at = :now"
        ),
        ExpressionAttributeValues={
            ":ts": Decimal("0.0"),
            ":now": now,
        },
    )

    return success({
        "unlinked": True,
        "trust_score": 0.0,
    })
