"""Transaction signal ingestion handlers for AgentPier."""

import json
import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

from utils.response import success, error, unauthorized, too_many_requests, handler
from utils.marketplace_auth import authenticate_marketplace
from utils.rate_limit import (
    check_rate_limit,
    check_auth_failures,
    record_auth_failure,
    get_client_ip,
)
from utils.audit import log_signal_access

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")

# Allowed signal types and their valid outcomes
SIGNAL_TYPES = {
    "transaction_outcome": {"completed", "failed", "refunded", "disputed"},
    "availability": {"up", "down", "degraded"},
    "user_feedback": {
        "completed",
        "failed",
        "refunded",
        "disputed",
        "up",
        "down",
        "degraded",
    },
    "incident": {"security", "safety", "data_breach"},
}

MAX_BATCH_SIZE = 100

DATA_FIREWALL_HEADER = "X-Data-Firewall"
DATA_FIREWALL_VALUE = "enforced"


def _add_firewall_header(response):
    """Add X-Data-Firewall: enforced header to signal responses."""
    if "headers" not in response:
        response["headers"] = {}
    response["headers"][DATA_FIREWALL_HEADER] = DATA_FIREWALL_VALUE
    return response


def _get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def _validate_signal(signal, index=None):
    """Validate a single signal dict.

    Returns (error_message, error_code) or (None, None) if valid.
    """
    prefix = f"signals[{index}]: " if index is not None else ""

    agent_id = signal.get("agent_id")
    if not agent_id or not isinstance(agent_id, str):
        return f"{prefix}agent_id is required", "invalid_agent_id"

    signal_type = signal.get("signal_type")
    if signal_type not in SIGNAL_TYPES:
        return (
            f"{prefix}signal_type must be one of: {', '.join(sorted(SIGNAL_TYPES))}",
            "invalid_signal_type",
        )

    outcome = signal.get("outcome")
    allowed_outcomes = SIGNAL_TYPES[signal_type]
    if outcome not in allowed_outcomes:
        return (
            f"{prefix}outcome must be one of: {', '.join(sorted(allowed_outcomes))} for signal_type '{signal_type}'",
            "invalid_outcome",
        )

    # user_feedback requires metrics.user_rating
    if signal_type == "user_feedback":
        metrics = signal.get("metrics") or {}
        rating = metrics.get("user_rating")
        if rating is None:
            return (
                f"{prefix}metrics.user_rating is required for user_feedback signals",
                "missing_user_rating",
            )
        if not isinstance(rating, (int, float)) or rating < 1 or rating > 5:
            return (
                f"{prefix}metrics.user_rating must be between 1 and 5",
                "invalid_user_rating",
            )

    return None, None


def _check_idempotency(table, marketplace_id, transaction_ref):
    """Check if a signal with this marketplace_id + transaction_ref already exists.

    Returns True if duplicate found.
    """
    if not transaction_ref:
        return False

    response = table.query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(
            f"DEDUP#{marketplace_id}#{transaction_ref}"
        ),
        Limit=1,
    )
    return len(response.get("Items", [])) > 0


def _store_signal(table, marketplace_id, signal):
    """Store a single signal in DynamoDB. Returns the signal_id."""
    signal_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    timestamp = signal.get("timestamp") or now
    agent_id = signal["agent_id"]
    transaction_ref = signal.get("transaction_ref") or ""

    item = {
        "PK": f"SIGNAL#{marketplace_id}#{agent_id}",
        "SK": f"TS#{timestamp}#{signal_id}",
        "signal_id": signal_id,
        "marketplace_id": marketplace_id,
        "agent_id": agent_id,
        "signal_type": signal["signal_type"],
        "outcome": signal["outcome"],
        "transaction_ref": transaction_ref,
        "timestamp": timestamp,
        "received_at": now,
        "GSI1PK": f"AGENT_SIGNALS#{agent_id}",
        "GSI1SK": f"TS#{timestamp}#{signal_id}",
    }

    if signal.get("metrics"):
        item["metrics"] = signal["metrics"]

    # Dedup record for idempotency (only if transaction_ref provided)
    if transaction_ref:
        item["GSI1PK"] = f"AGENT_SIGNALS#{agent_id}"
        item["GSI1SK"] = f"TS#{timestamp}#{signal_id}"

        dedup_item = {
            "PK": f"DEDUP#{marketplace_id}#{transaction_ref}",
            "SK": "REF",
            "GSI1PK": f"DEDUP#{marketplace_id}#{transaction_ref}",
            "GSI1SK": "REF",
            "signal_id": signal_id,
            "marketplace_id": marketplace_id,
            "agent_id": agent_id,
            "created_at": now,
        }
        table.put_item(Item=dedup_item)

    table.put_item(Item=item)
    return signal_id


def _update_counters(table, marketplace_id, agent_ids):
    """Increment signal counters on marketplace and agent trust profiles."""
    now = datetime.now(timezone.utc).isoformat()

    # Update marketplace signal_count and last_signal_at
    table.update_item(
        Key={"PK": f"MARKETPLACE#{marketplace_id}", "SK": "PROFILE"},
        UpdateExpression="SET signal_count = if_not_exists(signal_count, :zero) + :inc, last_signal_at = :now",
        ExpressionAttributeValues={
            ":inc": len(agent_ids),
            ":zero": 0,
            ":now": now,
        },
    )

    # Update each agent's signal_count in their trust profile
    updated_agents = set()
    for agent_id in agent_ids:
        if agent_id in updated_agents:
            continue
        updated_agents.add(agent_id)

        count_for_agent = agent_ids.count(agent_id)
        try:
            table.update_item(
                Key={"PK": f"AGENT#{agent_id}", "SK": "TRUST"},
                UpdateExpression="SET signal_count = if_not_exists(signal_count, :zero) + :inc",
                ExpressionAttributeValues={
                    ":inc": count_for_agent,
                    ":zero": 0,
                },
                ConditionExpression="attribute_exists(PK)",
            )
        except table.meta.client.exceptions.ConditionalCheckFailedException:
            # Agent trust profile doesn't exist yet — that's fine, skip
            pass


@handler
def ingest_signals(event, context):
    """POST /trust/signals — Submit transaction outcome signals."""
    # Check auth failures first
    if check_auth_failures(event):
        return too_many_requests(
            "Too many failed auth attempts. Try again in 5 minutes.", 300
        )

    marketplace = authenticate_marketplace(event)
    if not marketplace:
        record_auth_failure(event)
        return unauthorized(
            "Invalid or missing marketplace API key. Provide X-Marketplace-Key header."
        )

    marketplace_id = marketplace["marketplace_id"]

    # Rate limit: 1000 signals per marketplace per hour
    allowed, remaining, retry_after = check_rate_limit(
        event, f"signals_{marketplace_id}", max_requests=1000, window_seconds=3600
    )
    if not allowed:
        return too_many_requests(
            "Signal submission rate limit exceeded (1000/hour). Try again later.",
            retry_after,
        )

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    # Accept single signal or batch
    if "signals" in body:
        signals = body["signals"]
        if not isinstance(signals, list):
            return error("signals must be an array", "invalid_signals")
        if len(signals) > MAX_BATCH_SIZE:
            return error(
                f"Batch size exceeds maximum of {MAX_BATCH_SIZE}", "batch_too_large"
            )
        if len(signals) == 0:
            return error("signals array must not be empty", "empty_signals")
    else:
        # Single signal — must have agent_id to distinguish from empty object
        if "agent_id" not in body:
            return error("agent_id is required", "invalid_agent_id")
        signals = [body]

    # Validate all signals before storing any
    for i, sig in enumerate(signals):
        err_msg, err_code = _validate_signal(sig, index=i if len(signals) > 1 else None)
        if err_msg:
            return error(err_msg, err_code)

    table = _get_table()
    results = []
    agent_ids = []

    for sig in signals:
        transaction_ref = sig.get("transaction_ref") or ""

        # Idempotency check
        if transaction_ref and _check_idempotency(
            table, marketplace_id, transaction_ref
        ):
            results.append(
                {
                    "agent_id": sig["agent_id"],
                    "transaction_ref": transaction_ref,
                    "status": "already_received",
                }
            )
            continue

        signal_id = _store_signal(table, marketplace_id, sig)
        agent_ids.append(sig["agent_id"])
        results.append(
            {
                "signal_id": signal_id,
                "agent_id": sig["agent_id"],
                "status": "accepted",
            }
        )

    # Update counters for accepted signals
    if agent_ids:
        _update_counters(table, marketplace_id, agent_ids)

    # Audit log for each accepted signal
    ip = get_client_ip(event)
    for agent_id in set(agent_ids):
        log_signal_access(
            accessor_id=marketplace_id,
            accessor_type="marketplace",
            agent_id=agent_id,
            marketplace_id=marketplace_id,
            action="ingest",
            ip_address=ip,
        )

    accepted_count = sum(1 for r in results if r["status"] == "accepted")
    duplicate_count = sum(1 for r in results if r["status"] == "already_received")

    return _add_firewall_header(
        success(
            {
                "accepted": accepted_count,
                "duplicates": duplicate_count,
                "signals": results,
            },
            201 if accepted_count > 0 else 200,
        )
    )


@handler
def get_signal_stats(event, context):
    """GET /trust/signals/stats — Signal submission statistics for a marketplace."""
    if check_auth_failures(event):
        return too_many_requests(
            "Too many failed auth attempts. Try again in 5 minutes.", 300
        )

    marketplace = authenticate_marketplace(event)
    if not marketplace:
        record_auth_failure(event)
        return unauthorized(
            "Invalid or missing marketplace API key. Provide X-Marketplace-Key header."
        )

    marketplace_id = marketplace["marketplace_id"]
    table = _get_table()

    # Query all signals for this marketplace using a prefix scan
    # We need to scan for SIGNAL#{marketplace_id}# prefixed PKs
    # Since DynamoDB doesn't support PK prefix queries on the base table,
    # we'll use the marketplace profile counters and augment with a scan for breakdown.
    total_signals = int(marketplace.get("signal_count", 0))
    last_signal_at = marketplace.get("last_signal_at")

    # For detailed breakdown, scan signals by this marketplace
    by_type = {}
    by_outcome = {}
    earliest = None
    latest = None

    # Scan for signal items belonging to this marketplace
    scan_kwargs = {
        "FilterExpression": "marketplace_id = :mp_id AND begins_with(PK, :prefix)",
        "ExpressionAttributeValues": {
            ":mp_id": marketplace_id,
            ":prefix": "SIGNAL#",
        },
    }

    done = False
    while not done:
        response = table.scan(**scan_kwargs)
        for item in response.get("Items", []):
            st = item.get("signal_type", "unknown")
            oc = item.get("outcome", "unknown")
            ts = item.get("timestamp")

            by_type[st] = by_type.get(st, 0) + 1
            by_outcome[oc] = by_outcome.get(oc, 0) + 1

            if ts:
                if earliest is None or ts < earliest:
                    earliest = ts
                if latest is None or ts > latest:
                    latest = ts

        if "LastEvaluatedKey" in response:
            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        else:
            done = True

    # Audit log for stats query
    log_signal_access(
        accessor_id=marketplace_id,
        accessor_type="marketplace",
        agent_id="*",
        marketplace_id=marketplace_id,
        action="stats_query",
        ip_address=get_client_ip(event),
    )

    return _add_firewall_header(
        success(
            {
                "marketplace_id": marketplace_id,
                "total_signals": total_signals,
                "by_type": by_type,
                "by_outcome": by_outcome,
                "last_signal_at": last_signal_at,
                "date_range": {
                    "earliest": earliest,
                    "latest": latest,
                },
            }
        )
    )
