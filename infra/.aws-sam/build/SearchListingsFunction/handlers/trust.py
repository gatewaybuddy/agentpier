"""Trust scoring handlers for AgentPier.

Trust model adapted from Forgekeeper's ACE (Action Confidence Engine).
Three axes: accuracy, reliability, history.
Asymmetric learning: failures weigh more than successes.
Time decay: old reputation fades toward baseline.
"""

import json
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

from utils.response import success, not_found

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")

# Trust constants
BASELINE_SCORE = 0.0
MAX_SCORE = 1.0
SUCCESS_WEIGHT = 0.02   # Small positive increment per success
FAILURE_WEIGHT = 0.08   # Larger negative impact per failure (asymmetric)
VERIFICATION_BONUS = 0.15
TIME_DECAY_RATE = 0.001  # Per day, score drifts toward baseline


def _get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def calculate_trust_score(user_record: dict, trust_events: list) -> dict:
    """Calculate trust score from user record and event history.
    
    Returns dict with overall score and factor breakdown.
    """
    listings_count = int(user_record.get("listings_count", 0))
    transactions = int(user_record.get("transactions_completed", 0))
    disputes = int(user_record.get("disputes", 0))
    human_verified = user_record.get("human_verified", False)
    
    # Factor: Account maturity (0-0.2)
    created = user_record.get("created_at", "")
    if created:
        try:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - created_dt).days
            maturity = min(age_days / 90, 1.0) * 0.2  # Max at 90 days
        except (ValueError, TypeError):
            maturity = 0.0
            age_days = 0
    else:
        maturity = 0.0
        age_days = 0
    
    # Factor: Transaction reliability (0-0.3)
    if transactions > 0:
        dispute_rate = disputes / transactions
        reliability = (1 - dispute_rate) * min(transactions / 20, 1.0) * 0.3
    else:
        reliability = 0.0
        dispute_rate = 0.0
    
    # Factor: Listing accuracy (0-0.2) — based on event history
    accuracy_events = [e for e in trust_events if e.get("event_type") in ("listing_accurate", "listing_inaccurate")]
    if accuracy_events:
        accurate = sum(1 for e in accuracy_events if e["event_type"] == "listing_accurate")
        accuracy = (accurate / len(accuracy_events)) * 0.2
    else:
        accuracy = 0.1  # Neutral starting point
    
    # Factor: Verification bonus (0-0.15)
    verification = VERIFICATION_BONUS if human_verified else 0.0
    
    # Factor: Activity (0-0.15)
    activity = min(listings_count / 10, 1.0) * 0.15
    
    # Overall score
    score = min(maturity + reliability + accuracy + verification + activity, MAX_SCORE)
    
    return {
        "trust_score": float(round(score, 3)),
        "factors": {
            "account_maturity": float(round(maturity, 3)),
            "transaction_reliability": float(round(reliability, 3)),
            "listing_accuracy": float(round(accuracy, 3)),
            "verification_bonus": float(round(verification, 3)),
            "activity_score": float(round(activity, 3)),
            "account_age_days": age_days,
            "human_verified": human_verified,
            "dispute_rate": float(round(dispute_rate, 4)) if transactions > 0 else None,
        },
        "history_summary": {
            "total_listings": listings_count,
            "transactions_completed": transactions,
            "disputes": disputes,
        },
    }


def get_trust(event, context):
    """GET /trust/{user_id} — Get trust profile for a user."""
    user_id = event.get("pathParameters", {}).get("user_id", "")
    
    if not user_id:
        return not_found("User ID required")

    table = _get_table()

    # Get user record
    user_response = table.get_item(
        Key={"PK": f"USER#{user_id}", "SK": "META"}
    )
    user = user_response.get("Item")
    if not user:
        return not_found(f"User {user_id} not found")

    # Get trust events (last 100)
    events_response = table.query(
        KeyConditionExpression=Key("PK").eq(f"TRUST#{user_id}"),
        ScanIndexForward=False,
        Limit=100,
    )
    trust_events = events_response.get("Items", [])

    # Calculate score
    trust_profile = calculate_trust_score(user, trust_events)
    trust_profile["user_id"] = user_id
    trust_profile["agent_name"] = user.get("agent_name", "")

    return success(trust_profile)
