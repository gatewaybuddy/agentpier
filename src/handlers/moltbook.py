"""AgentPier Moltbook Identity Integration Handlers.

Phase 3A: Profile Verification Service
- Challenge-response verification (no Moltbook API key needed)
- Enhanced trust score calculation with full Moltbook signals
- Public trust lookup for any Moltbook agent
"""

import json
import os
import secrets
import math
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

from utils.response import success, error, not_found, unauthorized, too_many_requests
from utils.auth import authenticate
from utils.rate_limit import check_rate_limit, check_auth_failures, record_auth_failure
from utils.moltbook import (
    fetch_trust_metrics, MoltbookError, MoltbookNotFoundError, MoltbookAPIError,
)

from decimal import Decimal

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")

# Challenge expires after 30 minutes
CHALLENGE_TTL_SECONDS = 1800
CHALLENGE_PREFIX = "agentpier-verify-"


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


def calculate_enhanced_trust_score(moltbook_profile):
    """Calculate enhanced trust score (0-100) using the full spec formula.

    Uses all available Moltbook signals:
    - Karma contribution: min(karma * 0.5, 40) points
    - Account age: min(age_days * 0.1, 20) points
    - Social proof: min(log(follower_count + 1) * 2, 20) points
    - Activity: min(posts_count * 2 + comments_count * 0.1, 20) points

    Returns 0 if account is not claimed.
    """
    agent = moltbook_profile.get("agent", {})

    # Required: must be claimed
    if not agent.get("is_claimed", False):
        return {
            "trust_score": 0,
            "breakdown": {
                "karma": 0, "account_age": 0,
                "social_proof": 0, "activity": 0,
            },
            "raw": {
                "karma": 0, "account_age_days": 0,
                "follower_count": 0, "following_count": 0,
                "posts_count": 0, "comments_count": 0,
                "is_claimed": False, "is_active": agent.get("is_active", False),
            },
        }

    # Extract fields
    karma = int(agent.get("karma", 0)) if agent.get("karma") is not None else 0
    if isinstance(karma, str):
        karma = int(karma)

    follower_count = int(agent.get("follower_count", 0) or 0)
    following_count = int(agent.get("following_count", 0) or 0)
    posts_count = int(agent.get("posts_count", 0) or 0)
    comments_count = int(agent.get("comments_count", 0) or 0)

    # Account age in days
    created_at_str = agent.get("created_at", "")
    age_days = 0
    if created_at_str:
        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age_days = max(0, (datetime.now(timezone.utc) - created_at).days)
        except (ValueError, TypeError):
            pass

    # Calculate components
    karma_score = min(karma * 0.5, 40)
    age_score = min(age_days * 0.1, 20)
    social_score = min(math.log(follower_count + 1) * 2, 20)
    activity_score = min(posts_count * 2 + comments_count * 0.1, 20)

    total = min(karma_score + age_score + social_score + activity_score, 100)
    total = round(total, 2)

    return {
        "trust_score": total,
        "breakdown": {
            "karma": round(karma_score, 2),
            "account_age": round(age_score, 2),
            "social_proof": round(social_score, 2),
            "activity": round(activity_score, 2),
        },
        "raw": {
            "karma": karma,
            "account_age_days": age_days,
            "follower_count": follower_count,
            "following_count": following_count,
            "posts_count": posts_count,
            "comments_count": comments_count,
            "is_claimed": True,
            "is_active": agent.get("is_active", False),
        },
    }


# === POST /moltbook/verify — Initiate challenge-response verification ===
def moltbook_verify_initiate(event, context):
    """Start Moltbook identity verification via challenge-response.

    1. User provides their Moltbook username
    2. We generate a unique challenge code
    3. User posts the code to their Moltbook profile description
    4. They call POST /moltbook/verify/confirm to complete verification
    """
    user = authenticate(event)
    if not user:
        return unauthorized()

    # Rate limit: 5 verification attempts per hour
    allowed, remaining, retry_after = check_rate_limit(
        event, "moltbook_verify", max_requests=5, window_seconds=3600
    )
    if not allowed:
        return too_many_requests("Verification rate limit exceeded", retry_after)

    body = _parse_body(event)
    moltbook_username = body.get("moltbook_username", "").strip()
    if not moltbook_username:
        return error("moltbook_username is required", "missing_field")

    # Check the username exists on Moltbook
    try:
        profile = fetch_trust_metrics(moltbook_username)
    except MoltbookNotFoundError:
        return not_found(f"Moltbook agent '{moltbook_username}' not found")
    except MoltbookAPIError as e:
        return error("Moltbook service temporarily unavailable. Try again later.", "moltbook_unavailable", 503)

    agent_data = profile.get("agent", {})
    if not agent_data.get("is_claimed", False):
        return error(
            "This Moltbook account is not claimed. Only claimed accounts can be verified.",
            "not_claimed",
        )

    # Check if user already has a verified Moltbook link
    if user.get("moltbook_verified"):
        return error(
            f"Already linked to Moltbook account '{user.get('moltbook_name')}'. Unlink first.",
            "already_linked", 409,
        )

    # Generate challenge code
    challenge_code = CHALLENGE_PREFIX + secrets.token_hex(8)
    now = _now_iso()
    user_id = user.get("user_id")
    table = _get_table()

    # Store the challenge (PK=USER#{id}, SK=MOLTBOOK_CHALLENGE)
    table.put_item(Item={
        "PK": f"USER#{user_id}",
        "SK": "MOLTBOOK_CHALLENGE",
        "challenge_code": challenge_code,
        "moltbook_username": moltbook_username,
        "created_at": now,
        "expires_at": str(int(datetime.now(timezone.utc).timestamp()) + CHALLENGE_TTL_SECONDS),
    })

    return success({
        "challenge_code": challenge_code,
        "moltbook_username": moltbook_username,
        "instructions": (
            f"Add '{challenge_code}' to your Moltbook profile description, "
            f"then call POST /moltbook/verify/confirm to complete verification. "
            f"The challenge expires in 30 minutes."
        ),
        "expires_in_seconds": CHALLENGE_TTL_SECONDS,
    })


# === POST /moltbook/verify/confirm — Confirm challenge-response verification ===
def moltbook_verify_confirm(event, context):
    """Complete Moltbook identity verification by checking the challenge code.

    Fetches the Moltbook profile and verifies the challenge code appears
    in the profile description.
    """
    user = authenticate(event)
    if not user:
        return unauthorized()

    user_id = user.get("user_id")
    table = _get_table()

    # Fetch the pending challenge
    challenge_resp = table.get_item(
        Key={"PK": f"USER#{user_id}", "SK": "MOLTBOOK_CHALLENGE"}
    )
    challenge = challenge_resp.get("Item")
    if not challenge:
        return error(
            "No pending verification. Call POST /moltbook/verify first.",
            "no_challenge",
        )

    # Check expiration
    expires_at = int(challenge.get("expires_at", "0"))
    if datetime.now(timezone.utc).timestamp() > expires_at:
        # Clean up expired challenge
        table.delete_item(Key={"PK": f"USER#{user_id}", "SK": "MOLTBOOK_CHALLENGE"})
        return error(
            "Challenge expired. Start a new verification with POST /moltbook/verify.",
            "challenge_expired",
        )

    challenge_code = challenge.get("challenge_code", "")
    moltbook_username = challenge.get("moltbook_username", "")

    # Fetch the Moltbook profile and check for challenge code in description
    try:
        profile = fetch_trust_metrics(moltbook_username)
    except MoltbookNotFoundError:
        return not_found(f"Moltbook agent '{moltbook_username}' no longer exists")
    except MoltbookAPIError as e:
        return error("Moltbook service temporarily unavailable. Try again later.", "moltbook_unavailable", 503)

    agent_data = profile.get("agent", {})
    description = agent_data.get("description", "") or ""

    if challenge_code not in description:
        return error(
            f"Challenge code not found in Moltbook profile description. "
            f"Make sure '{challenge_code}' appears in your Moltbook profile description.",
            "challenge_not_found",
        )

    # Verification succeeded! Calculate enhanced trust score
    trust_result = calculate_enhanced_trust_score(profile)
    now = _now_iso()

    # Update user record with verified Moltbook identity
    from decimal import Decimal
    table.update_item(
        Key={"PK": f"USER#{user_id}", "SK": "META"},
        UpdateExpression=(
            "SET moltbook_name = :mn, moltbook_verified = :mv, "
            "moltbook_verified_at = :mvat, moltbook_karma = :mk, "
            "moltbook_account_age = :maa, moltbook_has_owner = :mho, "
            "moltbook_follower_count = :mfc, moltbook_posts_count = :mpc, "
            "moltbook_comments_count = :mcc, moltbook_verification_method = :mvm, "
            "moltbook_trust_score = :mts, "
            "trust_score = :ts, trust_breakdown = :tb, updated_at = :now"
        ),
        ExpressionAttributeValues={
            ":mn": moltbook_username,
            ":mv": True,
            ":mvat": now,
            ":mk": agent_data.get("karma", 0),
            ":maa": agent_data.get("created_at", ""),
            ":mho": bool(agent_data.get("owner")),
            ":mfc": int(agent_data.get("follower_count", 0) or 0),
            ":mpc": int(agent_data.get("posts_count", 0) or 0),
            ":mcc": int(agent_data.get("comments_count", 0) or 0),
            ":mvm": "challenge_response",
            ":mts": Decimal(str(trust_result["trust_score"])),
            ":ts": Decimal(str(trust_result["trust_score"] / 100)),  # normalize to 0-1 for existing field
            ":tb": {k: Decimal(str(v)) for k, v in trust_result["breakdown"].items()},
            ":now": now,
        },
    )

    # Clean up the challenge
    table.delete_item(Key={"PK": f"USER#{user_id}", "SK": "MOLTBOOK_CHALLENGE"})

    return success({
        "verified": True,
        "moltbook_username": moltbook_username,
        "verification_method": "challenge_response",
        "trust_score": trust_result["trust_score"],
        "trust_breakdown": trust_result["breakdown"],
        "raw_signals": trust_result["raw"],
        "message": (
            f"Successfully verified as '{moltbook_username}' on Moltbook. "
            f"You can now remove the challenge code from your profile description."
        ),
    })


# === GET /moltbook/trust/{username} — Public trust score lookup ===
def moltbook_trust(event, context):
    """Fetch Moltbook profile and calculate trust score for any agent.

    Public endpoint — no authentication required.
    Useful for evaluating potential business partners.
    """
    username = event.get("pathParameters", {}).get("username", "")
    if not username:
        return error("username is required", "missing_field")

    try:
        profile = fetch_trust_metrics(username)
    except MoltbookNotFoundError:
        return not_found(f"Moltbook agent '{username}' not found")
    except MoltbookAPIError as e:
        return error("Moltbook service temporarily unavailable. Try again later.", "moltbook_unavailable", 503)

    trust_result = calculate_enhanced_trust_score(profile)
    agent_data = profile.get("agent", {})

    return success({
        "moltbook_username": username,
        "display_name": agent_data.get("display_name", username),
        "description": agent_data.get("description", ""),
        "trust_score": trust_result["trust_score"],
        "trust_breakdown": trust_result["breakdown"],
        "raw_signals": trust_result["raw"],
        "last_active": agent_data.get("last_active", ""),
        "is_verified": agent_data.get("is_verified", False),
    })


# === POST /moltbook/unlink — Remove Moltbook identity link ===
def moltbook_unlink(event, context):
    """Remove Moltbook link from AgentPier profile. Resets trust score."""
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
        "message": "Moltbook account unlinked. Trust score reset.",
    })
