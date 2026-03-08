"""V-Token (Verification Token) handlers for AgentPier.

Transaction-level identity verification tokens.
Endpoints: create, verify (public), claim, list, get claims.
"""

import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

from utils.response import success, error, not_found, unauthorized, too_many_requests, handler
from utils.auth import authenticate
from utils.rate_limit import check_rate_limit
from utils.enhanced_rate_limit import check_enhanced_rate_limit, rate_limit_middleware
from utils.pagination import sign_cursor, verify_cursor

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")
VTOKEN_SECRET = os.environ.get("CURSOR_SECRET", "vtoken-signing-secret-key-placeholder")

VALID_PURPOSES = {"general", "service_inquiry", "transaction", "identity_proof"}
MIN_EXPIRES = 300       # 5 minutes
MAX_EXPIRES = 86400     # 24 hours
DEFAULT_EXPIRES = 3600  # 1 hour
MAX_LABEL_LEN = 200
MAX_NOTES_LEN = 500
AUDIT_TRAIL_DAYS = 7


def _get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _generate_vtoken_id():
    """Generate an opaque, unguessable token ID."""
    return f"vt_{secrets.token_urlsafe(16)}"


def _generate_signature(token, issuer_id, purpose, trust_score, created_at, expires_at):
    """Generate HMAC-SHA256 signature for token verification response."""
    message = f"{token}:{issuer_id}:{purpose}:{trust_score}:{created_at}:{expires_at}"
    return hmac.new(
        VTOKEN_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _get_user_profile(table, user_id):
    """Fetch user profile from DynamoDB."""
    resp = table.get_item(Key={"PK": f"USER#{user_id}", "SK": "META"})
    return resp.get("Item")


def _create_trust_event(table, user_id, event_type, vtoken_id):
    """Create a trust event for v-token activity."""
    now = _now_iso()
    event_id = str(uuid.uuid4())

    trust_event = {
        "PK": f"TRUST#{user_id}",
        "SK": f"EVENT#{now}#{event_id}",
        "event_id": event_id,
        "user_id": user_id,
        "event_type": event_type,
        "timestamp": now,
        "source": "vtoken",
        "vtoken_id": vtoken_id,
    }

    table.put_item(Item=trust_event)


# === POST /vtokens ===
@rate_limit_middleware("vtokens_create")
@handler
def create_vtoken(event, context):
    """Create a verification token. Requires API key."""
    user = authenticate(event)
    if not user:
        return unauthorized()

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    user_id = user["user_id"]
    table = _get_table()

    # Validate purpose
    purpose = body.get("purpose", "general")
    if purpose not in VALID_PURPOSES:
        return error(
            f"purpose must be one of: {', '.join(sorted(VALID_PURPOSES))}",
            "invalid_purpose",
        )

    # Validate expires_in
    expires_in = body.get("expires_in", DEFAULT_EXPIRES)
    try:
        expires_in = int(expires_in)
    except (ValueError, TypeError):
        return error("expires_in must be an integer", "invalid_expires_in")

    if expires_in < MIN_EXPIRES or expires_in > MAX_EXPIRES:
        return error(
            f"expires_in must be between {MIN_EXPIRES} and {MAX_EXPIRES} seconds",
            "invalid_expires_in",
        )

    # Validate single_use
    single_use = body.get("single_use", False)
    if not isinstance(single_use, bool):
        return error("single_use must be a boolean", "invalid_single_use")

    # Validate max_claims
    max_claims = body.get("max_claims", 1)
    try:
        max_claims = int(max_claims)
    except (ValueError, TypeError):
        return error("max_claims must be an integer", "invalid_max_claims")

    if max_claims < 0:
        return error("max_claims must be 0 (unlimited) or a positive integer", "invalid_max_claims")

    # Validate listing_id if provided
    listing_id = body.get("listing_id")
    if listing_id:
        listing_id = str(listing_id).strip()
        listing_resp = table.get_item(Key={"PK": f"LISTING#{listing_id}", "SK": "META"})
        listing = listing_resp.get("Item")
        if not listing:
            return not_found(f"Listing {listing_id} not found")
        if listing.get("posted_by") != user_id:
            return error("You can only create tokens for your own listings", "forbidden", 403)

    # Validate metadata.label
    metadata = body.get("metadata") or {}
    label = metadata.get("label")
    if label is not None:
        label = str(label).strip()
        if len(label) > MAX_LABEL_LEN:
            return error(
                f"metadata.label must be {MAX_LABEL_LEN} characters or less",
                "invalid_label",
            )

    # Generate token
    token_id = _generate_vtoken_id()
    now = _now_iso()
    now_epoch = int(time.time())
    expires_epoch = now_epoch + expires_in
    expires_at = datetime.fromtimestamp(expires_epoch, tz=timezone.utc).isoformat()
    ttl_epoch = expires_epoch + (AUDIT_TRAIL_DAYS * 86400)

    # Token record
    token_item = {
        "PK": f"VTOKEN#{token_id}",
        "SK": "META",
        "token": token_id,
        "issuer_id": user_id,
        "purpose": purpose,
        "single_use": single_use,
        "max_claims": max_claims,
        "claims_count": 0,
        "status": "active",
        "created_at": now,
        "expires_at": expires_at,
        "ttl": ttl_epoch,
    }

    if listing_id:
        token_item["listing_id"] = listing_id

    if label:
        token_item["label"] = label

    # Issuer index entry (for listing tokens by issuer via GSI2)
    issuer_index = {
        "PK": f"AGENT#{user_id}",
        "SK": f"VTOKEN#{now}",
        "GSI2PK": f"AGENT#{user_id}",
        "GSI2SK": f"VTOKEN#{now}",
        "token": token_id,
        "purpose": purpose,
        "status": "active",
        "created_at": now,
        "expires_at": expires_at,
        "ttl": ttl_epoch,
    }

    table.put_item(Item=token_item)
    table.put_item(Item=issuer_index)

    return success(
        {
            "token": token_id,
            "issuer_id": user_id,
            "purpose": purpose,
            "listing_id": listing_id,
            "created_at": now,
            "expires_at": expires_at,
            "verify_url": f"/vtokens/{token_id}/verify",
            "status": "active",
        },
        201,
    )


# === GET /vtokens/{token}/verify ===
@rate_limit_middleware("vtokens_verify")
@handler
def verify_vtoken(event, context):
    """Verify a token's authenticity. Public — no auth required."""

    path_params = event.get("pathParameters") or {}
    token_id = path_params.get("token", "")
    if not token_id:
        return success({"valid": False, "reason": "missing_token"})

    table = _get_table()

    # Look up token
    resp = table.get_item(Key={"PK": f"VTOKEN#{token_id}", "SK": "META"})
    token_item = resp.get("Item")

    if not token_item:
        # Return 200 with valid=false (prevents enumeration)
        return success({"valid": False, "reason": "not_found"})

    # Check expiry
    now_epoch = int(time.time())
    try:
        expires_dt = datetime.fromisoformat(
            token_item["expires_at"].replace("Z", "+00:00")
        )
        expires_epoch = int(expires_dt.timestamp())
    except (ValueError, KeyError):
        return success({"valid": False, "reason": "invalid_token"})

    if now_epoch > expires_epoch:
        return success({"valid": False, "reason": "expired"})

    # Check status
    status = token_item.get("status", "active")
    if status == "exhausted":
        return success({"valid": False, "reason": "exhausted"})

    if status != "active":
        return success({"valid": False, "reason": status})

    # If single_use, invalidate after this verification
    if token_item.get("single_use"):
        table.update_item(
            Key={"PK": f"VTOKEN#{token_id}", "SK": "META"},
            UpdateExpression="SET #status = :s",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":s": "exhausted"},
        )

    # Fetch issuer profile
    issuer_id = token_item["issuer_id"]
    issuer_profile = _get_user_profile(table, issuer_id)

    issuer_data = {}
    if issuer_profile:
        trust_score = float(issuer_profile.get("trust_score", 0))
        issuer_data = {
            "agent_id": issuer_id,
            "agent_name": issuer_profile.get("username")
            or issuer_profile.get("agent_name", ""),
            "trust_tier": issuer_profile.get("trust_tier", "untrusted"),
            "trust_score": trust_score,
            "registered_at": issuer_profile.get("created_at", ""),
        }

    # Build listing data if present
    listing_data = None
    listing_id = token_item.get("listing_id")
    if listing_id:
        listing_resp = table.get_item(Key={"PK": f"LISTING#{listing_id}", "SK": "META"})
        listing = listing_resp.get("Item")
        if listing:
            listing_data = {
                "listing_id": listing_id,
                "title": listing.get("title", ""),
                "category": listing.get("category", ""),
            }

    # Generate signature
    trust_score_for_sig = issuer_data.get("trust_score", 0)
    signature = _generate_signature(
        token_id,
        issuer_id,
        token_item["purpose"],
        trust_score_for_sig,
        token_item["created_at"],
        token_item["expires_at"],
    )

    result = {
        "valid": True,
        "issuer": issuer_data,
        "purpose": token_item["purpose"],
        "created_at": token_item["created_at"],
        "expires_at": token_item["expires_at"],
        "claims_count": int(token_item.get("claims_count", 0)),
        "signature": signature,
        "signature_algorithm": "HMAC-SHA256",
        "signed_fields": "token:issuer_id:purpose:trust_score:created_at:expires_at",
    }

    if listing_data:
        result["listing"] = listing_data

    return success(result)


# === POST /vtokens/{token}/claim ===
@handler
def claim_vtoken(event, context):
    """Claim a verification token. Requires API key (mutual verification)."""
    user = authenticate(event)
    if not user:
        return unauthorized()

    path_params = event.get("pathParameters") or {}
    token_id = path_params.get("token", "")
    if not token_id:
        return error("Token ID is required", "missing_token")

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    claimant_id = user["user_id"]
    table = _get_table()

    # Look up token
    resp = table.get_item(Key={"PK": f"VTOKEN#{token_id}", "SK": "META"})
    token_item = resp.get("Item")

    if not token_item:
        return success({"claimed": False, "reason": "not_found"})

    issuer_id = token_item["issuer_id"]

    # Self-claim check
    if claimant_id == issuer_id:
        return success({"claimed": False, "reason": "cannot_claim_own_token"})

    # Check expiry
    now_epoch = int(time.time())
    try:
        expires_dt = datetime.fromisoformat(
            token_item["expires_at"].replace("Z", "+00:00")
        )
        expires_epoch = int(expires_dt.timestamp())
    except (ValueError, KeyError):
        return success({"claimed": False, "reason": "invalid_token"})

    if now_epoch > expires_epoch:
        return success({"claimed": False, "reason": "expired"})

    # Check if already claimed by this agent (before status check — more specific error)
    existing_claim = table.get_item(
        Key={"PK": f"VTOKEN#{token_id}", "SK": f"CLAIM#{claimant_id}"}
    )
    if existing_claim.get("Item"):
        return success({"claimed": False, "reason": "already_claimed"})

    # Check status
    status = token_item.get("status", "active")
    if status == "exhausted":
        return success({"claimed": False, "reason": "max_claims_reached"})

    if status != "active":
        return success({"claimed": False, "reason": status})

    # Validate notes
    notes = body.get("notes", "")
    if notes:
        notes = str(notes).strip()
        if len(notes) > MAX_NOTES_LEN:
            return error(
                f"notes must be {MAX_NOTES_LEN} characters or less",
                "invalid_notes",
            )

    now = _now_iso()
    claims_count = int(token_item.get("claims_count", 0))
    new_claims_count = claims_count + 1

    # Write claim record
    ttl_epoch = int(token_item.get("ttl", now_epoch + AUDIT_TRAIL_DAYS * 86400))
    claim_item = {
        "PK": f"VTOKEN#{token_id}",
        "SK": f"CLAIM#{claimant_id}",
        "token": token_id,
        "claimant_id": claimant_id,
        "claimant_name": user.get("username") or user.get("agent_name", ""),
        "trust_score": Decimal(str(user.get("trust_score", 0))),
        "trust_tier": user.get("trust_tier", "untrusted"),
        "claimed_at": now,
        "ttl": ttl_epoch,
    }

    if notes:
        claim_item["notes"] = notes

    # Claimant index entry (for listing claims by claimant via GSI2)
    claimant_index = {
        "PK": f"AGENT#{claimant_id}",
        "SK": f"VTCLAIM#{now}",
        "GSI2PK": f"AGENT#{claimant_id}",
        "GSI2SK": f"VTCLAIM#{now}",
        "token": token_id,
        "issuer_id": issuer_id,
        "claimed_at": now,
        "ttl": ttl_epoch,
    }

    table.put_item(Item=claim_item)
    table.put_item(Item=claimant_index)

    # Update claims count and check if exhausted
    max_claims = int(token_item.get("max_claims", 1))
    new_status = "active"
    if max_claims > 0 and new_claims_count >= max_claims:
        new_status = "exhausted"

    table.update_item(
        Key={"PK": f"VTOKEN#{token_id}", "SK": "META"},
        UpdateExpression="SET claims_count = :cc, #status = :s",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":cc": new_claims_count,
            ":s": new_status,
        },
    )

    # Create trust events for both parties
    _create_trust_event(table, issuer_id, "vtoken_issued", token_id)
    _create_trust_event(table, claimant_id, "vtoken_claimed", token_id)

    # Build issuer info
    issuer_profile = _get_user_profile(table, issuer_id)
    issuer_data = {}
    if issuer_profile:
        issuer_data = {
            "agent_id": issuer_id,
            "agent_name": issuer_profile.get("username")
            or issuer_profile.get("agent_name", ""),
            "trust_tier": issuer_profile.get("trust_tier", "untrusted"),
            "trust_score": float(issuer_profile.get("trust_score", 0)),
        }

    claimant_data = {
        "agent_id": claimant_id,
        "trust_tier": user.get("trust_tier", "untrusted"),
        "trust_score": float(user.get("trust_score", 0)),
    }

    return success({
        "claimed": True,
        "token": token_id,
        "issuer": issuer_data,
        "claimant": claimant_data,
        "mutual_verification": True,
        "claimed_at": now,
    })


# === GET /vtokens ===
@handler
def list_vtokens(event, context):
    """List tokens issued by the authenticated user. Paginated."""
    user = authenticate(event)
    if not user:
        return unauthorized()

    user_id = user["user_id"]
    params = event.get("queryStringParameters") or {}

    # Query params
    status_filter = params.get("status")
    if status_filter and status_filter not in {"active", "expired", "exhausted"}:
        return error(
            "status must be one of: active, expired, exhausted",
            "invalid_status",
        )

    try:
        limit = max(1, min(int(params.get("limit", "20")), 50))
    except (ValueError, TypeError):
        limit = 20

    cursor = params.get("cursor")

    table = _get_table()

    # Query issuer index via main table (PK = AGENT#{user_id}, SK begins_with VTOKEN#)
    query_kwargs = {
        "KeyConditionExpression": Key("PK").eq(f"AGENT#{user_id}")
        & Key("SK").begins_with("VTOKEN#"),
        "ScanIndexForward": False,  # Most recent first
        "Limit": limit,
    }

    if cursor:
        decoded = verify_cursor(cursor)
        if not decoded:
            return error("Invalid pagination cursor", "invalid_cursor")
        query_kwargs["ExclusiveStartKey"] = decoded

    response = table.query(**query_kwargs)
    items = response.get("Items", [])

    # Fetch full token records and apply filters
    results = []
    now_epoch = int(time.time())

    for item in items:
        token_id = item.get("token")
        if not token_id:
            continue

        # Get full token record
        token_resp = table.get_item(Key={"PK": f"VTOKEN#{token_id}", "SK": "META"})
        token_item = token_resp.get("Item")
        if not token_item:
            continue

        # Determine effective status (check if expired)
        effective_status = token_item.get("status", "active")
        if effective_status == "active":
            try:
                expires_dt = datetime.fromisoformat(
                    token_item["expires_at"].replace("Z", "+00:00")
                )
                if now_epoch > int(expires_dt.timestamp()):
                    effective_status = "expired"
            except (ValueError, KeyError):
                pass

        # Apply status filter
        if status_filter and effective_status != status_filter:
            continue

        results.append({
            "token": token_id,
            "purpose": token_item.get("purpose", "general"),
            "listing_id": token_item.get("listing_id"),
            "status": effective_status,
            "claims_count": int(token_item.get("claims_count", 0)),
            "max_claims": int(token_item.get("max_claims", 1)),
            "created_at": token_item.get("created_at", ""),
            "expires_at": token_item.get("expires_at", ""),
        })

    result = {
        "tokens": results,
        "count": len(results),
    }

    last_key = response.get("LastEvaluatedKey")
    if last_key and len(items) == limit:
        result["next_cursor"] = sign_cursor(last_key)
        result["has_more"] = True
    else:
        result["has_more"] = False

    return success(result)


# === GET /vtokens/{token}/claims ===
@handler
def get_vtoken_claims(event, context):
    """See who has claimed your token. Issuer only."""
    user = authenticate(event)
    if not user:
        return unauthorized()

    path_params = event.get("pathParameters") or {}
    token_id = path_params.get("token", "")
    if not token_id:
        return error("Token ID is required", "missing_token")

    table = _get_table()

    # Look up token
    resp = table.get_item(Key={"PK": f"VTOKEN#{token_id}", "SK": "META"})
    token_item = resp.get("Item")

    if not token_item:
        return not_found(f"Token {token_id} not found")

    # Only the issuer can see claims
    if token_item["issuer_id"] != user["user_id"]:
        return error("Only the token issuer can view claims", "forbidden", 403)

    # Query claim records
    claims_resp = table.query(
        KeyConditionExpression=Key("PK").eq(f"VTOKEN#{token_id}")
        & Key("SK").begins_with("CLAIM#"),
    )
    claim_items = claims_resp.get("Items", [])

    claims = []
    for item in claim_items:
        claims.append({
            "claimant_id": item.get("claimant_id", ""),
            "claimant_name": item.get("claimant_name", ""),
            "trust_tier": item.get("trust_tier", "untrusted"),
            "trust_score": float(item.get("trust_score", 0)),
            "claimed_at": item.get("claimed_at", ""),
        })

    return success({
        "token": token_id,
        "claims": claims,
    })
