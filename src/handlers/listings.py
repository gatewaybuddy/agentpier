from decimal import Decimal
"""Listing CRUD handlers for AgentPier."""

import json
import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

from utils.response import success, error, not_found, unauthorized
from utils.auth import authenticate

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")

VALID_TYPES = {"service", "product", "agent_skill", "consulting"}
VALID_CATEGORIES = {
    "plumbing", "electrical", "hvac", "landscaping", "cleaning",
    "auto_repair", "it_support", "consulting", "legal", "accounting",
    "photography", "catering", "tutoring", "pet_care", "home_repair",
    "other",
}


def _get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def create_listing(event, context):
    """POST /listings — Create a new listing."""
    user = authenticate(event)
    if not user:
        return unauthorized()

    try:
        raw_body = event.get("body")
        if not raw_body:
            return error("Request body is required", "missing_body")
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    # Validate required fields
    listing_type = body.get("type", "service")
    if listing_type not in VALID_TYPES:
        return error(f"Invalid type. Must be one of: {VALID_TYPES}", "invalid_type")

    category = body.get("category", "").lower()
    if category not in VALID_CATEGORIES:
        return error(f"Invalid category. Must be one of: {VALID_CATEGORIES}", "invalid_category")

    title = body.get("title", "").strip()
    if not title or len(title) > 200:
        return error("Title is required (max 200 chars)", "invalid_title")

    description = body.get("description", "").strip()
    if len(description) > 2000:
        return error("Description max 2000 chars", "invalid_description")

    # Build listing record
    listing_id = f"lst_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    user_id = user["PK"].replace("USER#", "")
    
    # Validate tags
    tags = body.get("tags", [])
    if not isinstance(tags, list):
        return error("Tags must be an array", "invalid_tags")
    if len(tags) > 10:
        return error("Maximum 10 tags allowed", "too_many_tags")
    clean_tags = []
    for tag in tags:
        if not isinstance(tag, str):
            return error("Tags must be strings", "invalid_tags")
        tag = tag.strip()[:30]  # Enforce 30 char max
        if tag:
            clean_tags.append(tag)

    location = body.get("location", {})
    state = location.get("state", "").upper()
    city = location.get("city", "").lower().replace(" ", "_")

    item = {
        "PK": f"LISTING#{listing_id}",
        "SK": "META",
        # GSI1: category + location for search
        "GSI1PK": category,
        "GSI1SK": f"{state}#{city}#{listing_id}" if state else listing_id,
        # GSI2: agent index
        "GSI2PK": f"AGENT#{user_id}",
        "GSI2SK": now,
        # Data
        "listing_id": listing_id,
        "type": listing_type,
        "category": category,
        "title": title,
        "description": description,
        "location": location,
        "pricing": body.get("pricing", {}),
        "availability": body.get("availability", ""),
        "contact": body.get("contact", {}),
        "tags": clean_tags,
        "posted_by": user_id,
        "agent_name": user.get("agent_name", ""),
        "human_verified": user.get("human_verified", False),
        "trust_score": Decimal("0.0"),
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }

    table = _get_table()
    table.put_item(Item=item)

    return success({
        "id": listing_id,
        "status": "active",
        "trust_score": Decimal("0.0"),
        "created_at": now,
        "url": f"https://agentpier.io/listing/{listing_id}",
    }, 201)


def get_listing(event, context):
    """GET /listings/{id} — Get a specific listing."""
    listing_id = event.get("pathParameters", {}).get("id", "")
    
    if not listing_id:
        return error("Listing ID required", "missing_id")

    table = _get_table()
    response = table.get_item(
        Key={"PK": f"LISTING#{listing_id}", "SK": "META"}
    )

    item = response.get("Item")
    if not item:
        return not_found(f"Listing {listing_id} not found")

    # Strip internal fields from response
    for key in ["PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK", "posted_by"]:
        item.pop(key, None)

    return success(item)


def search_listings(event, context):
    """GET /listings?category=X&state=Y&city=Z — Search listings."""
    params = event.get("queryStringParameters") or {}

    category = params.get("category", "").lower()
    if not category:
        return error("category parameter is required", "missing_category")

    if category not in VALID_CATEGORIES:
        return error(f"Invalid category. Must be one of: {VALID_CATEGORIES}", "invalid_category")

    state = params.get("state", "").upper()
    city = params.get("city", "").lower().replace(" ", "_")
    try:
        limit = max(1, min(int(params.get("limit", "20")), 50))
    except (ValueError, TypeError):
        limit = 20
    cursor = params.get("cursor")
    try:
        min_trust = max(0.0, min(float(params.get("min_trust", "0")), 1.0))
    except (ValueError, TypeError):
        min_trust = 0.0

    table = _get_table()

    # Build query
    key_condition = Key("GSI1PK").eq(category)
    if state and city:
        key_condition = key_condition & Key("GSI1SK").begins_with(f"{state}#{city}")
    elif state:
        key_condition = key_condition & Key("GSI1SK").begins_with(f"{state}#")

    query_kwargs = {
        "IndexName": "GSI1",
        "KeyConditionExpression": key_condition,
        "Limit": limit,
    }

    if cursor:
        import base64
        try:
            decoded = json.loads(base64.b64decode(cursor).decode())
            # Validate cursor has expected GSI1 keys only
            if not isinstance(decoded, dict) or "GSI1PK" not in decoded:
                return error("Invalid pagination cursor", "invalid_cursor")
            # Only allow keys that belong to the queried category
            if decoded.get("GSI1PK") != category:
                return error("Invalid pagination cursor", "invalid_cursor")
            query_kwargs["ExclusiveStartKey"] = decoded
        except Exception:
            return error("Invalid pagination cursor", "invalid_cursor")

    response = table.query(**query_kwargs)
    items = response.get("Items", [])

    # Filter by trust score (post-query for now)
    if min_trust > 0:
        items = [i for i in items if float(i.get("trust_score", 0)) >= min_trust]

    # Clean up internal fields
    for item in items:
        for key in ["PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK", "posted_by"]:
            item.pop(key, None)

    result = {
        "results": items,
        "count": len(items),
    }

    # Pagination
    last_key = response.get("LastEvaluatedKey")
    if last_key:
        import base64
        result["next_cursor"] = base64.b64encode(
            json.dumps(last_key, default=str).encode()
        ).decode()

    return success(result)


def update_listing(event, context):
    """PATCH /listings/{id} — Update a listing."""
    user = authenticate(event)
    if not user:
        return unauthorized()

    listing_id = event.get("pathParameters", {}).get("id", "")
    if not listing_id:
        return error("Listing ID required", "missing_id")

    table = _get_table()

    # Verify ownership
    existing = table.get_item(
        Key={"PK": f"LISTING#{listing_id}", "SK": "META"}
    ).get("Item")

    if not existing:
        return not_found(f"Listing {listing_id} not found")

    user_id = user["PK"].replace("USER#", "")
    if existing.get("posted_by") != user_id:
        return error("You can only update your own listings", "forbidden", 403)

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    # Allowed update fields
    allowed = {"title", "description", "pricing", "availability", "contact", "tags", "status"}
    updates = {k: v for k, v in body.items() if k in allowed}
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Build update expression
    update_parts = []
    values = {}
    names = {}
    for i, (key, val) in enumerate(updates.items()):
        attr = f"#attr{i}"
        placeholder = f":val{i}"
        update_parts.append(f"{attr} = {placeholder}")
        values[placeholder] = val
        names[attr] = key

    table.update_item(
        Key={"PK": f"LISTING#{listing_id}", "SK": "META"},
        UpdateExpression="SET " + ", ".join(update_parts),
        ExpressionAttributeValues=values,
        ExpressionAttributeNames=names,
    )

    return success({"id": listing_id, "updated": list(updates.keys())})


def delete_listing(event, context):
    """DELETE /listings/{id} — Remove a listing."""
    user = authenticate(event)
    if not user:
        return unauthorized()

    listing_id = event.get("pathParameters", {}).get("id", "")
    if not listing_id:
        return error("Listing ID required", "missing_id")

    table = _get_table()

    # Verify ownership
    existing = table.get_item(
        Key={"PK": f"LISTING#{listing_id}", "SK": "META"}
    ).get("Item")

    if not existing:
        return not_found(f"Listing {listing_id} not found")

    user_id = user["PK"].replace("USER#", "")
    if existing.get("posted_by") != user_id:
        return error("You can only delete your own listings", "forbidden", 403)

    table.delete_item(
        Key={"PK": f"LISTING#{listing_id}", "SK": "META"}
    )

    return success({"id": listing_id, "deleted": True})
