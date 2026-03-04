"""Marketplace registration and management handlers for AgentPier."""

import json
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

from utils.response import success, error, unauthorized, not_found, too_many_requests, handler
from utils.auth import generate_api_key, hash_key
from utils.rate_limit import check_rate_limit, check_auth_failures, record_auth_failure, get_client_ip

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")

# Marketplace name: 2-60 chars, alphanumeric, spaces, hyphens, dots
MARKETPLACE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9 .\-]{0,58}[a-zA-Z0-9]$")
URL_RE = re.compile(r"^https?://[^\s]{3,500}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def _authenticate_marketplace(event):
    """Authenticate a marketplace by API key.

    Returns the marketplace record if valid, None otherwise.
    """
    headers = event.get("headers", {}) or {}
    api_key = headers.get("x-api-key") or headers.get("X-API-Key")

    if not api_key:
        auth_header = headers.get("authorization") or headers.get("Authorization") or ""
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]

    if not api_key:
        return None

    try:
        key_hash_val = hash_key(api_key)
        table = _get_table()

        # Look up key hash in GSI2
        response = table.query(
            IndexName="GSI2",
            KeyConditionExpression=Key("GSI2PK").eq(f"APIKEY#{key_hash_val}"),
        )

        items = response.get("Items", [])
        if not items:
            return None

        marketplace_id = items[0].get("marketplace_id")
        if not marketplace_id:
            return None

        # Get the full marketplace record
        mp_response = table.get_item(
            Key={"PK": f"MARKETPLACE#{marketplace_id}", "SK": "PROFILE"}
        )
        return mp_response.get("Item")
    except Exception:
        return None


@handler
def register_marketplace(event, context):
    """POST /marketplace/register — Register a new marketplace."""
    # Rate limit: 5 registrations per IP per hour
    allowed, remaining, retry_after = check_rate_limit(
        event, "mp_register", max_requests=5, window_seconds=3600
    )
    if not allowed:
        return too_many_requests("Marketplace registration rate limit exceeded. Try again later.", retry_after)

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    # Validate required fields
    name = (body.get("name") or "").strip()
    url = (body.get("url") or "").strip()
    contact_email = (body.get("contact_email") or "").strip()
    description = (body.get("description") or "").strip()[:500]

    if not name or not MARKETPLACE_NAME_RE.match(name):
        return error(
            "name is required and must be 2-60 alphanumeric characters (spaces, hyphens, dots allowed)",
            "invalid_name",
        )

    if not url or not URL_RE.match(url):
        return error("url is required and must be a valid HTTP/HTTPS URL", "invalid_url")

    if not contact_email or not EMAIL_RE.match(contact_email):
        return error("contact_email is required and must be a valid email address", "invalid_email")

    table = _get_table()

    # Check name uniqueness via GSI1
    existing = table.query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(f"MARKETPLACE_NAME#{name}"),
        Limit=1,
    )
    if existing.get("Items"):
        return error("A marketplace with this name already exists", "name_taken", 409)

    # Generate IDs and keys
    marketplace_id = uuid.uuid4().hex
    raw_key, key_hash_val = generate_api_key()
    now = datetime.now(timezone.utc).isoformat()

    # Create marketplace record
    marketplace_item = {
        "PK": f"MARKETPLACE#{marketplace_id}",
        "SK": "PROFILE",
        "GSI1PK": f"MARKETPLACE_NAME#{name}",
        "GSI1SK": "META",
        "marketplace_id": marketplace_id,
        "name": name,
        "url": url,
        "description": description,
        "contact_email": contact_email,
        "api_key_hash": key_hash_val,
        "registered_at": now,
        "verified_at": None,
        "marketplace_score": Decimal("0"),
        "tier": "registered",
        "signal_count": 0,
        "last_signal_at": None,
    }

    # Create API key record (hash only)
    key_item = {
        "PK": f"MARKETPLACE#{marketplace_id}",
        "SK": f"APIKEY#{key_hash_val[:16]}",
        "GSI2PK": f"APIKEY#{key_hash_val}",
        "GSI2SK": now,
        "marketplace_id": marketplace_id,
        "key_hash": key_hash_val,
        "created_at": now,
    }

    table.put_item(Item=marketplace_item)
    table.put_item(Item=key_item)

    return success({
        "marketplace_id": marketplace_id,
        "name": name,
        "api_key": raw_key,
        "message": "Marketplace registered. Store your API key securely — it cannot be retrieved again.",
    }, 201)


@handler
def get_marketplace(event, context):
    """GET /marketplace/{id} — View marketplace profile (public)."""
    path_params = event.get("pathParameters") or {}
    marketplace_id = path_params.get("id", "")

    if not marketplace_id:
        return error("marketplace id is required", "missing_id")

    table = _get_table()
    response = table.get_item(
        Key={"PK": f"MARKETPLACE#{marketplace_id}", "SK": "PROFILE"}
    )
    item = response.get("Item")
    if not item:
        return not_found("Marketplace not found")

    # Return only public fields
    return success({
        "marketplace_id": item.get("marketplace_id"),
        "name": item.get("name"),
        "url": item.get("url"),
        "description": item.get("description"),
        "tier": item.get("tier"),
        "marketplace_score": float(item.get("marketplace_score", 0)),
        "registered_at": item.get("registered_at"),
        "signal_count": int(item.get("signal_count", 0)),
    })


@handler
def update_marketplace(event, context):
    """PUT /marketplace/{id} — Update marketplace profile (requires API key)."""
    if check_auth_failures(event):
        return too_many_requests("Too many failed auth attempts. Try again in 5 minutes.", 300)

    marketplace = _authenticate_marketplace(event)
    if not marketplace:
        record_auth_failure(event)
        return unauthorized("Invalid or missing API key.")

    path_params = event.get("pathParameters") or {}
    marketplace_id = path_params.get("id", "")

    if marketplace.get("marketplace_id") != marketplace_id:
        return unauthorized("API key does not match this marketplace.")

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    # Build update expression for allowed fields
    update_parts = []
    expr_names = {}
    expr_values = {}

    if "description" in body:
        desc = (body["description"] or "")[:500].strip()
        update_parts.append("#desc = :desc")
        expr_names["#desc"] = "description"
        expr_values[":desc"] = desc

    if "contact_email" in body:
        email = (body["contact_email"] or "").strip()
        if not email or not EMAIL_RE.match(email):
            return error("contact_email must be a valid email address", "invalid_email")
        update_parts.append("contact_email = :email")
        expr_values[":email"] = email

    if "url" in body:
        new_url = (body["url"] or "").strip()
        if not new_url or not URL_RE.match(new_url):
            return error("url must be a valid HTTP/HTTPS URL", "invalid_url")
        update_parts.append("#u = :url")
        expr_names["#u"] = "url"
        expr_values[":url"] = new_url

    if not update_parts:
        return error("No valid fields to update. Allowed: description, contact_email, url", "no_updates")

    now = datetime.now(timezone.utc).isoformat()
    update_parts.append("updated_at = :now")
    expr_values[":now"] = now

    table = _get_table()
    update_kwargs = {
        "Key": {"PK": f"MARKETPLACE#{marketplace_id}", "SK": "PROFILE"},
        "UpdateExpression": "SET " + ", ".join(update_parts),
        "ExpressionAttributeValues": expr_values,
        "ReturnValues": "ALL_NEW",
    }
    if expr_names:
        update_kwargs["ExpressionAttributeNames"] = expr_names

    result = table.update_item(**update_kwargs)
    updated = result.get("Attributes", {})

    return success({
        "marketplace_id": updated.get("marketplace_id"),
        "name": updated.get("name"),
        "url": updated.get("url"),
        "description": updated.get("description"),
        "updated_at": updated.get("updated_at"),
    })


@handler
def rotate_marketplace_key(event, context):
    """POST /marketplace/{id}/rotate-key — Rotate API key."""
    if check_auth_failures(event):
        return too_many_requests("Too many failed auth attempts. Try again in 5 minutes.", 300)

    marketplace = _authenticate_marketplace(event)
    if not marketplace:
        record_auth_failure(event)
        return unauthorized("Invalid or missing API key.")

    path_params = event.get("pathParameters") or {}
    marketplace_id = path_params.get("id", "")

    if marketplace.get("marketplace_id") != marketplace_id:
        return unauthorized("API key does not match this marketplace.")

    table = _get_table()

    # Delete all existing API key records for this marketplace
    mp_items = table.query(
        KeyConditionExpression=Key("PK").eq(f"MARKETPLACE#{marketplace_id}"),
    )
    with table.batch_writer() as batch:
        for item in mp_items.get("Items", []):
            if item["SK"].startswith("APIKEY#"):
                batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

    # Generate new key
    now = datetime.now(timezone.utc).isoformat()
    raw_key, key_hash_val = generate_api_key()

    # Store new API key record
    key_item = {
        "PK": f"MARKETPLACE#{marketplace_id}",
        "SK": f"APIKEY#{key_hash_val[:16]}",
        "GSI2PK": f"APIKEY#{key_hash_val}",
        "GSI2SK": now,
        "marketplace_id": marketplace_id,
        "key_hash": key_hash_val,
        "created_at": now,
    }
    table.put_item(Item=key_item)

    # Update the hash on the profile record too
    table.update_item(
        Key={"PK": f"MARKETPLACE#{marketplace_id}", "SK": "PROFILE"},
        UpdateExpression="SET api_key_hash = :h, updated_at = :now",
        ExpressionAttributeValues={":h": key_hash_val, ":now": now},
    )

    return success({
        "marketplace_id": marketplace_id,
        "api_key": raw_key,
        "message": "Key rotated. Your previous key is now invalid. Store this new key securely.",
    })
