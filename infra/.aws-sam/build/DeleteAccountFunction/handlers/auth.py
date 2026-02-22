"""Auth handlers for AgentPier."""

import json
import os
import re
import time
from datetime import datetime, timezone
from decimal import Decimal

import boto3

from utils.response import success, error, unauthorized, too_many_requests, handler
from utils.auth import generate_api_key, authenticate
from utils.rate_limit import check_rate_limit, check_auth_failures, record_auth_failure, get_client_ip
from utils.challenges import generate_challenge
from utils.moltbook import MoltbookError  # noqa: F401 — kept for backward compat

CHALLENGE_TTL = 300  # 5 minutes
USERNAME_RE = re.compile(r"^[a-z0-9_]+$")

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")


def _get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


@handler
def request_challenge(event, context):
    """POST /auth/challenge — Request a registration challenge."""
    # Rate limit: 10 challenges per IP per hour
    allowed, remaining, retry_after = check_rate_limit(event, "challenge", max_requests=30, window_seconds=3600)
    if not allowed:
        return too_many_requests("Too many challenge requests. Try again later.", retry_after)

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    username = (body.get("username") or "").strip().lower()
    if not username or len(username) < 3 or len(username) > 30 or not USERNAME_RE.match(username):
        return error(
            "username must be 3-30 chars, lowercase alphanumeric + underscore",
            "invalid_username",
        )

    table = _get_table()

    # Check if username already taken
    existing = table.query(
        IndexName="GSI1",
        KeyConditionExpression=boto3.dynamodb.conditions.Key("GSI1PK").eq(f"USERNAME#{username}"),
        Limit=1,
    )
    # Also check legacy agent names
    if not existing.get("Items"):
        existing = table.query(
            IndexName="GSI1",
            KeyConditionExpression=boto3.dynamodb.conditions.Key("GSI1PK").eq(f"AGENT_NAME#{username}"),
            Limit=1,
        )
    if existing.get("Items"):
        return error("Username already taken", "name_taken", 409)

    # Generate challenge
    challenge = generate_challenge()
    now = datetime.now(timezone.utc).isoformat()
    now_epoch = int(time.time())
    expires_at = now_epoch + CHALLENGE_TTL
    ip = get_client_ip(event)

    # Store challenge in DynamoDB
    table.put_item(Item={
        "PK": f"CHALLENGE#{challenge['challenge_id']}",
        "SK": "META",
        "challenge_id": challenge["challenge_id"],
        "challenge_text": challenge["challenge_text"],
        "expected_answer": challenge["expected_answer"],
        "source_ip": ip,
        "created_at": now,
        "expires_at": expires_at,
        "ttl": expires_at,
        "used": False,
    })

    # Track IP for rate limiting registrations
    table.put_item(Item={
        "PK": f"IP_REG#{ip}",
        "SK": str(now_epoch),
        "ttl": now_epoch + 86400,  # 24h TTL
    })

    return success({
        "challenge_id": challenge["challenge_id"],
        "challenge": challenge["challenge_text"],
        "expires_in_seconds": CHALLENGE_TTL,
    })


@handler
def register_with_challenge(event, context):
    """POST /auth/register2 — Register with challenge-response verification."""
    # Rate limit: 5 registrations per IP per hour
    allowed, remaining, retry_after = check_rate_limit(event, "register2", max_requests=20, window_seconds=3600)
    if not allowed:
        return too_many_requests("Registration rate limit exceeded", retry_after)

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    # Validate required fields
    username = (body.get("username") or "").strip().lower()
    password = body.get("password", "")
    challenge_id = body.get("challenge_id", "")
    challenge_answer = body.get("answer")

    if not username or len(username) < 3 or len(username) > 30 or not USERNAME_RE.match(username):
        return error("username must be 3-30 chars, lowercase alphanumeric + underscore", "invalid_username")

    if not password or len(password) < 12 or len(password) > 128:
        return error("password must be 12-128 characters", "invalid_password")

    if not challenge_id:
        return error("challenge_id is required", "missing_challenge")

    if challenge_answer is None:
        return error("answer is required", "missing_answer")

    try:
        challenge_answer = int(challenge_answer)
    except (ValueError, TypeError):
        return error("answer must be an integer", "invalid_answer")

    table = _get_table()

    # Validate challenge
    challenge_resp = table.get_item(
        Key={"PK": f"CHALLENGE#{challenge_id}", "SK": "META"}
    )
    challenge_item = challenge_resp.get("Item")

    if not challenge_item:
        return error("Invalid or expired challenge", "invalid_challenge")

    if challenge_item.get("used"):
        return error("Challenge already used", "challenge_used")

    now_epoch = int(time.time())
    if now_epoch > int(challenge_item.get("expires_at", 0)):
        return error("Challenge expired", "challenge_expired")

    # Mark challenge as used immediately (single-use)
    table.update_item(
        Key={"PK": f"CHALLENGE#{challenge_id}", "SK": "META"},
        UpdateExpression="SET used = :t",
        ExpressionAttributeValues={":t": True},
    )

    # Verify answer
    if challenge_answer != int(challenge_item.get("expected_answer", -1)):
        return error("Incorrect challenge answer", "wrong_answer")

    # Check username uniqueness
    existing = table.query(
        IndexName="GSI1",
        KeyConditionExpression=boto3.dynamodb.conditions.Key("GSI1PK").eq(f"USERNAME#{username}"),
        Limit=1,
    )
    if not existing.get("Items"):
        existing = table.query(
            IndexName="GSI1",
            KeyConditionExpression=boto3.dynamodb.conditions.Key("GSI1PK").eq(f"AGENT_NAME#{username}"),
            Limit=1,
        )
    if existing.get("Items"):
        return error("Username already taken", "name_taken", 409)

    # Hash password with scrypt (stdlib, no native deps)
    import hashlib, os, base64
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    password_hash = "$scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()

    # Optional fields
    display_name = (body.get("display_name") or "")[:50].strip()
    description = (body.get("description") or "")[:500].strip()
    capabilities = body.get("capabilities") or []
    if not isinstance(capabilities, list):
        capabilities = []
    capabilities = [str(c)[:50] for c in capabilities[:20]]
    contact_method = body.get("contact_method")
    if contact_method and isinstance(contact_method, dict):
        cm_type = contact_method.get("type", "")
        cm_endpoint = contact_method.get("endpoint", "")
        if cm_type not in ("mcp", "webhook", "http"):
            contact_method = None
        else:
            contact_method = {"type": cm_type, "endpoint": cm_endpoint[:500]}
    else:
        contact_method = None

    import uuid
    user_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    ip = get_client_ip(event)

    # Generate API key
    raw_key, key_hash = generate_api_key()

    # Create user record
    user_item = {
        "PK": f"USER#{user_id}",
        "SK": "META",
        "GSI1PK": f"USERNAME#{username}",
        "GSI1SK": now,
        "user_id": user_id,
        "username": username,
        "password_hash": password_hash,
        "trust_score": Decimal("0.0"),
        "listings_count": 0,
        "transactions_completed": 0,
        "dispute_rate": Decimal("0.0"),
        "registration_ip": ip,
        "created_at": now,
        "updated_at": now,
        "last_active": now,
        "moltbook_verified": False,
    }
    if display_name:
        user_item["display_name"] = display_name
    if description:
        user_item["description"] = description
    if capabilities:
        user_item["capabilities"] = capabilities
    if contact_method:
        user_item["contact_method"] = contact_method

    # Create API key record (hash only - no raw key storage)
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

    table.put_item(Item=user_item)
    table.put_item(Item=key_item)

    return success({
        "user_id": user_id,
        "username": username,
        "api_key": raw_key,
        "message": "Registration complete. Store your API key securely — it cannot be retrieved again.",
    }, 201)


@handler
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
        "username": user.get("username") or user.get("agent_name"),  # Support legacy agent_name field
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


@handler
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


@handler
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


    # link_moltbook and unlink_moltbook removed — moved to handlers.moltbook module
    # Routes: POST /moltbook/unlink (was /auth/unlink-moltbook)
