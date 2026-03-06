"""Transaction handlers for AgentPier."""

import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key, Attr

from utils.response import success, error, not_found, unauthorized
from utils.auth import authenticate
from utils.pagination import sign_cursor, verify_cursor
from utils.ace_scoring import calculate_ace_score

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")

VALID_STATUSES = {"pending", "completed", "disputed", "cancelled"}
VALID_RATINGS = {1, 2, 3, 4, 5}


def _get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _create_trust_event(table, user_id, event_type, transaction_id, rating=None):
    """Create a trust event for a user based on transaction outcome."""
    now = _now_iso()
    event_id = str(uuid.uuid4())

    trust_event = {
        "PK": f"TRUST#{user_id}",
        "SK": f"EVENT#{now}#{event_id}",
        "event_id": event_id,
        "user_id": user_id,
        "event_type": event_type,
        "timestamp": now,
        "source": "transaction",
        "transaction_id": transaction_id,
        "rating": rating,
    }

    table.put_item(Item=trust_event)


def _update_user_trust_score(table, user_id):
    """Recalculate and update user's trust score based on their trust events."""
    # Get user profile
    user_resp = table.get_item(Key={"PK": f"USER#{user_id}", "SK": "META"})
    user = user_resp.get("Item")
    if not user:
        return

    # Get trust events
    trust_resp = table.query(
        KeyConditionExpression=Key("PK").eq(f"TRUST#{user_id}"),
        ScanIndexForward=False,  # Most recent first
        Limit=200,
    )
    events = trust_resp.get("Items", [])

    # Calculate new trust score using existing ACE scoring logic
    try:
        score_data = calculate_ace_score(user, events)
        new_score = score_data.get("trust_score", 0.0)

        # Update user record
        table.update_item(
            Key={"PK": f"USER#{user_id}", "SK": "META"},
            UpdateExpression="SET trust_score = :score, updated_at = :time",
            ExpressionAttributeValues={
                ":score": Decimal(str(new_score)),
                ":time": _now_iso(),
            },
        )
    except Exception:
        # If trust scoring fails, continue - don't break transaction flow
        pass


def create_transaction(event, context):
    """POST /transactions — Create a transaction record."""
    user = authenticate(event)
    if not user:
        return unauthorized()

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    # Validate required fields
    listing_id = body.get("listing_id", "").strip()
    if not listing_id:
        return error("listing_id is required", "missing_listing_id")

    table = _get_table()

    # Verify listing exists
    listing_resp = table.get_item(Key={"PK": f"LISTING#{listing_id}", "SK": "META"})
    listing = listing_resp.get("Item")
    if not listing:
        return not_found(f"Listing {listing_id} not found")

    # Extract IDs
    consumer_id = user["user_id"]
    provider_id = listing["posted_by"]

    # Can't create transaction with yourself
    if consumer_id == provider_id:
        return error("Cannot create transaction with yourself", "invalid_transaction")

    # Generate transaction ID
    transaction_id = f"txn_{uuid.uuid4().hex[:12]}"
    now = _now_iso()

    # Create transaction record
    transaction = {
        "PK": f"TRANSACTION#{transaction_id}",
        "SK": "META",
        # GSI1: for listing-based queries
        "GSI1PK": f"LISTING#{listing_id}",
        "GSI1SK": now,
        # GSI2: for user-based queries (both provider and consumer can find it)
        "GSI2PK": f"AGENT#{provider_id}",
        "GSI2SK": f"PROVIDER#{now}",
        # Data
        "transaction_id": transaction_id,
        "listing_id": listing_id,
        "listing_title": listing.get("title", ""),
        "provider_id": provider_id,
        "provider_name": listing.get("agent_name", ""),
        "consumer_id": consumer_id,
        "consumer_name": user.get("agent_name", ""),
        "status": "pending",
        "amount": (
            Decimal(str(body.get("amount"))) if body.get("amount") is not None else None
        ),
        "currency": body.get("currency", "USD"),
        "notes": body.get("notes", ""),
        "created_at": now,
        "updated_at": now,
    }

    table.put_item(Item=transaction)

    # Also create a consumer-side index entry
    consumer_index = {
        "PK": f"TRANSACTION#{transaction_id}",
        "SK": f"CONSUMER#{consumer_id}",
        "GSI2PK": f"AGENT#{consumer_id}",
        "GSI2SK": f"CONSUMER#{now}",
        "transaction_id": transaction_id,
        "role": "consumer",
        "created_at": now,
    }
    table.put_item(Item=consumer_index)

    return success(
        {
            "transaction_id": transaction_id,
            "listing_id": listing_id,
            "provider_id": provider_id,
            "consumer_id": consumer_id,
            "status": "pending",
            "created_at": now,
        },
        201,
    )


def get_transaction(event, context):
    """GET /transactions/{id} — Get transaction details."""
    user = authenticate(event)
    if not user:
        return unauthorized()

    transaction_id = event.get("pathParameters", {}).get("id", "")
    if not transaction_id:
        return error("Transaction ID required", "missing_id")

    table = _get_table()

    # Get transaction
    resp = table.get_item(Key={"PK": f"TRANSACTION#{transaction_id}", "SK": "META"})
    transaction = resp.get("Item")
    if not transaction:
        return not_found(f"Transaction {transaction_id} not found")

    user_id = user["user_id"]
    provider_id = transaction["provider_id"]
    consumer_id = transaction["consumer_id"]

    # Only participants can view transaction
    if user_id not in (provider_id, consumer_id):
        return error("You can only view your own transactions", "forbidden", 403)

    # Get reviews if transaction is completed
    reviews = []
    if transaction["status"] == "completed":
        review_resp = table.query(
            KeyConditionExpression=Key("PK").eq(f"TRANSACTION#{transaction_id}")
            & Key("SK").begins_with("REVIEW#")
        )
        reviews = review_resp.get("Items", [])

        # Clean up review data
        for review in reviews:
            review.pop("PK", None)
            review.pop("SK", None)

    # Clean up transaction data
    for key in ["PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK"]:
        transaction.pop(key, None)

    transaction["reviews"] = reviews
    return success(transaction)


def list_transactions(event, context):
    """GET /transactions — List transactions for authenticated user."""
    user = authenticate(event)
    if not user:
        return unauthorized()

    params = event.get("queryStringParameters") or {}
    user_id = user["user_id"]

    # Query parameters
    role = params.get("role")  # provider, consumer, or both (default)
    status = params.get("status")  # pending, completed, disputed, cancelled
    try:
        limit = max(1, min(int(params.get("limit", "20")), 50))
    except (ValueError, TypeError):
        limit = 20
    cursor = params.get("cursor")

    if role and role not in {"provider", "consumer"}:
        return error("role must be 'provider' or 'consumer'", "invalid_role")

    if status and status not in VALID_STATUSES:
        return error(f"status must be one of: {VALID_STATUSES}", "invalid_status")

    table = _get_table()

    # For proper pagination, we recommend specifying a role when using cursors
    if cursor and not role:
        return error(
            "Pagination with cursor requires specifying a role (provider or consumer)",
            "pagination_requires_role",
        )

    # Query based on role filter
    roles_to_query = [role] if role else ["provider", "consumer"]
    results = []
    last_evaluated_key = None

    for query_role in roles_to_query:
        # Build query
        key_condition = Key("GSI2PK").eq(f"AGENT#{user_id}")
        if query_role == "provider":
            key_condition = key_condition & Key("GSI2SK").begins_with("PROVIDER#")
        else:  # consumer
            key_condition = key_condition & Key("GSI2SK").begins_with("CONSUMER#")

        query_kwargs = {
            "IndexName": "GSI2",
            "KeyConditionExpression": key_condition,
            "ScanIndexForward": False,  # Most recent first
            "Limit": limit,
        }

        # Handle pagination cursor (only applies when role is specified)
        if cursor:
            decoded = verify_cursor(cursor)
            if not decoded:
                return error("Invalid pagination cursor", "invalid_cursor")
            query_kwargs["ExclusiveStartKey"] = decoded

        response = table.query(**query_kwargs)
        items = response.get("Items", [])

        # Store the last evaluated key for pagination
        if response.get("LastEvaluatedKey"):
            last_evaluated_key = response["LastEvaluatedKey"]

        # For each transaction reference, get the full transaction
        for item in items:
            if item.get("SK") == "META":  # This is the main transaction record
                results.append(item)
            else:  # This is an index entry, get the main record
                trans_id = item["transaction_id"]
                trans_resp = table.get_item(
                    Key={"PK": f"TRANSACTION#{trans_id}", "SK": "META"}
                )
                if trans_resp.get("Item"):
                    results.append(trans_resp["Item"])

        # If querying single role and we have enough results, break
        if role and len(results) >= limit:
            results = results[:limit]
            break

        # If querying both roles, continue to get more results
        if not role and len(results) >= limit:
            results = results[:limit]
            break

    # Apply status filter (post-query)
    if status:
        results = [t for t in results if t.get("status") == status]

    # Limit results
    results = results[:limit]

    # Clean up results
    for transaction in results:
        for key in ["PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK"]:
            transaction.pop(key, None)
        # Add user's role in this transaction
        if transaction.get("provider_id") == user_id:
            transaction["user_role"] = "provider"
        else:
            transaction["user_role"] = "consumer"

    # Build pagination response
    result = {
        "results": results,
        "count": len(results),
    }

    # Add next_cursor if there are more results
    if last_evaluated_key and len(results) == limit:
        next_cursor = sign_cursor(last_evaluated_key)
        result["next_cursor"] = next_cursor
        result["has_more"] = True
    else:
        result["has_more"] = False

    return success(result)


def update_transaction(event, context):
    """PATCH /transactions/{id} — Update transaction status."""
    user = authenticate(event)
    if not user:
        return unauthorized()

    transaction_id = event.get("pathParameters", {}).get("id", "")
    if not transaction_id:
        return error("Transaction ID required", "missing_id")

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    new_status = body.get("status", "").lower()
    if new_status not in VALID_STATUSES:
        return error(f"status must be one of: {VALID_STATUSES}", "invalid_status")

    table = _get_table()

    # Get current transaction
    resp = table.get_item(Key={"PK": f"TRANSACTION#{transaction_id}", "SK": "META"})
    transaction = resp.get("Item")
    if not transaction:
        return not_found(f"Transaction {transaction_id} not found")

    user_id = user["user_id"]
    provider_id = transaction["provider_id"]
    consumer_id = transaction["consumer_id"]
    current_status = transaction["status"]

    # Verify user is a participant
    if user_id not in (provider_id, consumer_id):
        return error("You can only update your own transactions", "forbidden", 403)

    # State machine validation
    if current_status == "completed":
        return error(
            "Cannot change status of completed transaction", "invalid_transition"
        )

    if current_status == "cancelled":
        return error(
            "Cannot change status of cancelled transaction", "invalid_transition"
        )

    # Role-based permissions
    if new_status == "completed":
        # Only provider can mark as completed
        if user_id != provider_id:
            return error(
                "Only the provider can mark transaction as completed", "forbidden", 403
            )

    elif new_status == "disputed":
        # Only consumer can dispute
        if user_id != consumer_id:
            return error(
                "Only the consumer can dispute a transaction", "forbidden", 403
            )
        # Can only dispute pending or completed transactions
        if current_status not in ("pending", "completed"):
            return error(
                "Can only dispute pending or completed transactions",
                "invalid_transition",
            )

    elif new_status == "cancelled":
        # Either party can cancel a pending transaction
        if current_status != "pending":
            return error("Can only cancel pending transactions", "invalid_transition")

    # Update transaction
    now = _now_iso()
    table.update_item(
        Key={"PK": f"TRANSACTION#{transaction_id}", "SK": "META"},
        UpdateExpression="SET #status = :status, updated_at = :time",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": new_status, ":time": now},
    )

    # Create trust events on completion or dispute
    if new_status == "completed":
        # Positive trust event for both parties
        _create_trust_event(table, provider_id, "transaction_completed", transaction_id)
        _create_trust_event(table, consumer_id, "transaction_completed", transaction_id)
        _update_user_trust_score(table, provider_id)
        _update_user_trust_score(table, consumer_id)

        # Update user transaction counts
        for uid in [provider_id, consumer_id]:
            try:
                table.update_item(
                    Key={"PK": f"USER#{uid}", "SK": "META"},
                    UpdateExpression="SET transactions_completed = if_not_exists(transactions_completed, :zero) + :one",
                    ExpressionAttributeValues={":zero": 0, ":one": 1},
                )
            except Exception:
                # If update fails, continue - don't break transaction flow
                pass

    elif new_status == "disputed":
        # Negative trust events
        _create_trust_event(table, provider_id, "transaction_disputed", transaction_id)
        _create_trust_event(table, consumer_id, "transaction_disputed", transaction_id)
        _update_user_trust_score(table, provider_id)
        _update_user_trust_score(table, consumer_id)

    return success(
        {
            "transaction_id": transaction_id,
            "status": new_status,
            "updated_at": now,
            "updated_by": user_id,
        }
    )


def create_review(event, context):
    """POST /transactions/{id}/review — Leave a review after completion."""
    user = authenticate(event)
    if not user:
        return unauthorized()

    transaction_id = event.get("pathParameters", {}).get("id", "")
    if not transaction_id:
        return error("Transaction ID required", "missing_id")

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    rating = body.get("rating")
    comment = body.get("comment", "").strip()

    # Validate rating
    if not isinstance(rating, int) or rating not in VALID_RATINGS:
        return error("rating must be an integer from 1 to 5", "invalid_rating")

    # Validate comment length
    if len(comment) > 1000:
        return error("comment must be 1000 characters or less", "invalid_comment")

    table = _get_table()

    # Get transaction
    resp = table.get_item(Key={"PK": f"TRANSACTION#{transaction_id}", "SK": "META"})
    transaction = resp.get("Item")
    if not transaction:
        return not_found(f"Transaction {transaction_id} not found")

    user_id = user["user_id"]
    provider_id = transaction["provider_id"]
    consumer_id = transaction["consumer_id"]

    # Verify user is a participant
    if user_id not in (provider_id, consumer_id):
        return error("You can only review your own transactions", "forbidden", 403)

    # Only allow reviews on completed transactions
    if transaction["status"] != "completed":
        return error("Can only review completed transactions", "invalid_status")

    # Check if user already reviewed
    existing_review_resp = table.get_item(
        Key={"PK": f"TRANSACTION#{transaction_id}", "SK": f"REVIEW#{user_id}"}
    )
    if existing_review_resp.get("Item"):
        return error(
            "You have already reviewed this transaction", "already_reviewed", 409
        )

    # Create review
    now = _now_iso()
    review_id = str(uuid.uuid4())

    review = {
        "PK": f"TRANSACTION#{transaction_id}",
        "SK": f"REVIEW#{user_id}",
        "review_id": review_id,
        "transaction_id": transaction_id,
        "reviewer_id": user_id,
        "reviewer_name": user.get("agent_name", ""),
        "rating": rating,
        "comment": comment,
        "created_at": now,
    }

    table.put_item(Item=review)

    # Create trust event based on rating
    other_party = provider_id if user_id == consumer_id else consumer_id

    if rating >= 4:
        event_type = "positive_review"
    elif rating <= 2:
        event_type = "negative_review"
    else:
        event_type = "neutral_review"

    _create_trust_event(table, other_party, event_type, transaction_id, rating)
    _update_user_trust_score(table, other_party)

    return success(
        {
            "review_id": review_id,
            "transaction_id": transaction_id,
            "rating": rating,
            "comment": comment,
            "created_at": now,
        },
        201,
    )
