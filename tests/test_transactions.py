"""Tests for transaction handlers."""

import json
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from tests.conftest import make_api_event


@pytest.fixture
def sample_listing(dynamodb, sample_user):
    """Create a sample listing for transactions."""
    user_id, _ = sample_user
    listing_id = "lst_test123"
    now = datetime.now(timezone.utc).isoformat()
    
    listing = {
        "PK": f"LISTING#{listing_id}",
        "SK": "META",
        "GSI1PK": "plumbing",
        "GSI1SK": f"FL#orlando#{listing_id}",
        "GSI2PK": f"AGENT#{user_id}",
        "GSI2SK": now,
        "listing_id": listing_id,
        "type": "service",
        "category": "plumbing",
        "title": "Emergency Plumbing Service",
        "description": "24/7 plumbing repairs",
        "posted_by": user_id,
        "agent_name": "testbot",
        "status": "active",
        "created_at": now,
    }
    
    dynamodb.put_item(Item=listing)
    return listing_id, user_id


@pytest.fixture
def second_user(dynamodb):
    """Create a second user for testing transactions between different users."""
    from utils.auth import generate_api_key
    
    user_id = "testuser456"
    raw_key, key_hash = generate_api_key()
    now = datetime.now(timezone.utc).isoformat()
    
    # Create user
    dynamodb.put_item(Item={
        "PK": f"USER#{user_id}",
        "SK": "META",
        "GSI1PK": "AGENT_NAME#secondbot",
        "GSI1SK": now,
        "user_id": user_id,
        "agent_name": "secondbot",
        "description": "Second test agent",
        "operator_email": "second@example.com",
        "human_verified": False,
        "trust_score": Decimal("0.3"),
        "transactions_completed": 0,
        "created_at": now,
        "updated_at": now,
    })
    
    # Create API key
    dynamodb.put_item(Item={
        "PK": f"USER#{user_id}",
        "SK": f"APIKEY#{key_hash[:16]}",
        "GSI2PK": f"APIKEY#{key_hash}",
        "GSI2SK": now,
        "user_id": user_id,
        "key_hash": key_hash,
        "permissions": ["read", "write"],
        "created_at": now,
    })
    
    return user_id, raw_key


@pytest.fixture
def sample_transaction(dynamodb, sample_listing, second_user):
    """Create a sample transaction."""
    listing_id, provider_id = sample_listing
    consumer_id, _ = second_user
    
    transaction_id = "txn_test123"
    now = datetime.now(timezone.utc).isoformat()
    
    # Main transaction record
    transaction = {
        "PK": f"TRANSACTION#{transaction_id}",
        "SK": "META",
        "GSI1PK": f"LISTING#{listing_id}",
        "GSI1SK": now,
        "GSI2PK": f"AGENT#{provider_id}",
        "GSI2SK": f"PROVIDER#{now}",
        "transaction_id": transaction_id,
        "listing_id": listing_id,
        "listing_title": "Emergency Plumbing Service",
        "provider_id": provider_id,
        "provider_name": "testbot",
        "consumer_id": consumer_id,
        "consumer_name": "secondbot",
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    }
    
    # Consumer index entry
    consumer_index = {
        "PK": f"TRANSACTION#{transaction_id}",
        "SK": f"CONSUMER#{consumer_id}",
        "GSI2PK": f"AGENT#{consumer_id}",
        "GSI2SK": f"CONSUMER#{now}",
        "transaction_id": transaction_id,
        "role": "consumer",
        "created_at": now,
    }
    
    dynamodb.put_item(Item=transaction)
    dynamodb.put_item(Item=consumer_index)
    
    return transaction_id, provider_id, consumer_id


class TestCreateTransaction:
    def test_success(self, dynamodb, sample_listing, second_user):
        from handlers.transactions import create_transaction
        
        listing_id, provider_id = sample_listing
        consumer_id, consumer_key = second_user
        
        event = make_api_event(
            method="POST",
            api_key=consumer_key,
            body={
                "listing_id": listing_id,
                "amount": 150.00,
                "currency": "USD",
                "notes": "Emergency leak repair"
            }
        )
        
        resp = create_transaction(event, None)
        assert resp["statusCode"] == 201
        
        body = json.loads(resp["body"])
        assert "transaction_id" in body
        assert body["listing_id"] == listing_id
        assert body["provider_id"] == provider_id
        assert body["consumer_id"] == consumer_id
        assert body["status"] == "pending"

    def test_missing_listing_id(self, dynamodb, second_user):
        from handlers.transactions import create_transaction
        
        _, consumer_key = second_user
        
        event = make_api_event(
            method="POST",
            api_key=consumer_key,
            body={"amount": 100}
        )
        
        resp = create_transaction(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "missing_listing_id"

    def test_nonexistent_listing(self, dynamodb, second_user):
        from handlers.transactions import create_transaction
        
        _, consumer_key = second_user
        
        event = make_api_event(
            method="POST",
            api_key=consumer_key,
            body={"listing_id": "lst_nonexistent"}
        )
        
        resp = create_transaction(event, None)
        assert resp["statusCode"] == 404

    def test_self_transaction(self, dynamodb, sample_listing, sample_user):
        from handlers.transactions import create_transaction
        
        listing_id, provider_id = sample_listing
        _, provider_key = sample_user
        
        event = make_api_event(
            method="POST",
            api_key=provider_key,
            body={"listing_id": listing_id}
        )
        
        resp = create_transaction(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "invalid_transaction"

    def test_unauthenticated(self, dynamodb):
        from handlers.transactions import create_transaction
        
        event = make_api_event(
            method="POST",
            body={"listing_id": "lst_test"}
        )
        
        resp = create_transaction(event, None)
        assert resp["statusCode"] == 401


class TestGetTransaction:
    def test_success_provider(self, dynamodb, sample_transaction, sample_user):
        from handlers.transactions import get_transaction
        
        transaction_id, provider_id, _ = sample_transaction
        _, provider_key = sample_user
        
        event = make_api_event(
            api_key=provider_key,
            path_params={"id": transaction_id}
        )
        
        resp = get_transaction(event, None)
        assert resp["statusCode"] == 200
        
        body = json.loads(resp["body"])
        assert body["transaction_id"] == transaction_id
        assert body["provider_id"] == provider_id
        assert "reviews" in body

    def test_success_consumer(self, dynamodb, sample_transaction, second_user):
        from handlers.transactions import get_transaction
        
        transaction_id, _, consumer_id = sample_transaction
        _, consumer_key = second_user
        
        event = make_api_event(
            api_key=consumer_key,
            path_params={"id": transaction_id}
        )
        
        resp = get_transaction(event, None)
        assert resp["statusCode"] == 200
        
        body = json.loads(resp["body"])
        assert body["consumer_id"] == consumer_id

    def test_forbidden_third_party(self, dynamodb, sample_transaction):
        from handlers.transactions import get_transaction
        from utils.auth import generate_api_key, hash_key
        
        # Create a third user
        third_key, third_hash = generate_api_key()
        now = datetime.now(timezone.utc).isoformat()
        
        dynamodb.put_item(Item={
            "PK": "USER#thirduser",
            "SK": "META",
            "user_id": "thirduser",
            "agent_name": "thirdbot",
            "created_at": now,
        })
        
        dynamodb.put_item(Item={
            "PK": "USER#thirduser",
            "SK": f"APIKEY#{third_hash[:16]}",
            "GSI2PK": f"APIKEY#{third_hash}",
            "GSI2SK": now,
            "user_id": "thirduser",
            "key_hash": third_hash,
        })
        
        transaction_id, _, _ = sample_transaction
        
        event = make_api_event(
            api_key=third_key,
            path_params={"id": transaction_id}
        )
        
        resp = get_transaction(event, None)
        assert resp["statusCode"] == 403

    def test_nonexistent(self, dynamodb, sample_user):
        from handlers.transactions import get_transaction
        
        _, user_key = sample_user
        
        event = make_api_event(
            api_key=user_key,
            path_params={"id": "txn_nonexistent"}
        )
        
        resp = get_transaction(event, None)
        assert resp["statusCode"] == 404


class TestListTransactions:
    def test_success(self, dynamodb, sample_transaction, sample_user):
        from handlers.transactions import list_transactions
        
        _, provider_id, _ = sample_transaction
        _, provider_key = sample_user
        
        event = make_api_event(
            api_key=provider_key,
            query_params={"role": "provider"}
        )
        
        resp = list_transactions(event, None)
        assert resp["statusCode"] == 200
        
        body = json.loads(resp["body"])
        assert "results" in body
        assert body["count"] >= 0

    def test_status_filter(self, dynamodb, sample_transaction, sample_user):
        from handlers.transactions import list_transactions
        
        _, user_key = sample_user
        
        event = make_api_event(
            api_key=user_key,
            query_params={"status": "pending"}
        )
        
        resp = list_transactions(event, None)
        assert resp["statusCode"] == 200

    def test_invalid_role(self, dynamodb, sample_user):
        from handlers.transactions import list_transactions
        
        _, user_key = sample_user
        
        event = make_api_event(
            api_key=user_key,
            query_params={"role": "invalid"}
        )
        
        resp = list_transactions(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "invalid_role"


class TestUpdateTransaction:
    def test_provider_complete(self, dynamodb, sample_transaction, sample_user):
        from handlers.transactions import update_transaction
        
        transaction_id, _, _ = sample_transaction
        _, provider_key = sample_user
        
        event = make_api_event(
            method="PATCH",
            api_key=provider_key,
            path_params={"id": transaction_id},
            body={"status": "completed"}
        )
        
        resp = update_transaction(event, None)
        assert resp["statusCode"] == 200
        
        body = json.loads(resp["body"])
        assert body["status"] == "completed"

    def test_consumer_dispute(self, dynamodb, sample_transaction, second_user):
        from handlers.transactions import update_transaction
        
        transaction_id, _, _ = sample_transaction
        _, consumer_key = second_user
        
        event = make_api_event(
            method="PATCH",
            api_key=consumer_key,
            path_params={"id": transaction_id},
            body={"status": "disputed"}
        )
        
        resp = update_transaction(event, None)
        assert resp["statusCode"] == 200
        
        body = json.loads(resp["body"])
        assert body["status"] == "disputed"

    def test_invalid_permissions(self, dynamodb, sample_transaction, second_user):
        from handlers.transactions import update_transaction
        
        transaction_id, _, _ = sample_transaction
        _, consumer_key = second_user
        
        # Consumer trying to mark as completed (only provider can do this)
        event = make_api_event(
            method="PATCH",
            api_key=consumer_key,
            path_params={"id": transaction_id},
            body={"status": "completed"}
        )
        
        resp = update_transaction(event, None)
        assert resp["statusCode"] == 403

    def test_invalid_status(self, dynamodb, sample_transaction, sample_user):
        from handlers.transactions import update_transaction
        
        transaction_id, _, _ = sample_transaction
        _, provider_key = sample_user
        
        event = make_api_event(
            method="PATCH",
            api_key=provider_key,
            path_params={"id": transaction_id},
            body={"status": "invalid"}
        )
        
        resp = update_transaction(event, None)
        assert resp["statusCode"] == 400


class TestCreateReview:
    def test_success(self, dynamodb, sample_transaction, sample_user, second_user):
        from handlers.transactions import update_transaction, create_review
        
        transaction_id, _, _ = sample_transaction
        _, provider_key = sample_user
        _, consumer_key = second_user
        
        # First complete the transaction
        complete_event = make_api_event(
            method="PATCH",
            api_key=provider_key,
            path_params={"id": transaction_id},
            body={"status": "completed"}
        )
        update_transaction(complete_event, None)
        
        # Now leave a review
        event = make_api_event(
            method="POST",
            api_key=consumer_key,
            path_params={"id": transaction_id},
            body={
                "rating": 5,
                "comment": "Excellent service, very professional"
            }
        )
        
        resp = create_review(event, None)
        assert resp["statusCode"] == 201
        
        body = json.loads(resp["body"])
        assert body["rating"] == 5
        assert "review_id" in body

    def test_not_completed(self, dynamodb, sample_transaction, second_user):
        from handlers.transactions import create_review
        
        transaction_id, _, _ = sample_transaction
        _, consumer_key = second_user
        
        event = make_api_event(
            method="POST",
            api_key=consumer_key,
            path_params={"id": transaction_id},
            body={"rating": 4}
        )
        
        resp = create_review(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "invalid_status"

    def test_invalid_rating(self, dynamodb, sample_transaction, second_user):
        from handlers.transactions import create_review
        
        transaction_id, _, _ = sample_transaction
        _, consumer_key = second_user
        
        event = make_api_event(
            method="POST",
            api_key=consumer_key,
            path_params={"id": transaction_id},
            body={"rating": 6}  # Invalid rating
        )
        
        resp = create_review(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "invalid_rating"

    def test_duplicate_review(self, dynamodb, sample_transaction, sample_user, second_user):
        from handlers.transactions import update_transaction, create_review
        
        transaction_id, _, _ = sample_transaction
        _, provider_key = sample_user
        _, consumer_key = second_user
        
        # Complete transaction
        complete_event = make_api_event(
            method="PATCH",
            api_key=provider_key,
            path_params={"id": transaction_id},
            body={"status": "completed"}
        )
        update_transaction(complete_event, None)
        
        # First review
        event = make_api_event(
            method="POST",
            api_key=consumer_key,
            path_params={"id": transaction_id},
            body={"rating": 5}
        )
        create_review(event, None)
        
        # Attempt duplicate review
        resp = create_review(event, None)
        assert resp["statusCode"] == 409
        body = json.loads(resp["body"])
        assert body["error"] == "already_reviewed"