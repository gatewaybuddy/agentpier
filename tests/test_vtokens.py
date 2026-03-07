"""Tests for V-Token (Verification Token) handlers."""

import hashlib
import hmac
import json
import time
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import patch

from boto3.dynamodb.conditions import Key
from tests.conftest import make_api_event


@pytest.fixture
def second_user(dynamodb):
    """Create a second user for mutual verification tests."""
    from utils.auth import generate_api_key

    user_id = "testuser456"
    raw_key, key_hash = generate_api_key()
    now = datetime.now(timezone.utc).isoformat()

    dynamodb.put_item(
        Item={
            "PK": f"USER#{user_id}",
            "SK": "META",
            "GSI1PK": "AGENT_NAME#secondbot",
            "GSI1SK": now,
            "user_id": user_id,
            "username": "secondbot",
            "agent_name": "secondbot",
            "description": "Second test agent",
            "human_verified": False,
            "trust_score": Decimal("0.3"),
            "trust_tier": "emerging",
            "transactions_completed": 0,
            "created_at": now,
            "updated_at": now,
        }
    )

    dynamodb.put_item(
        Item={
            "PK": f"USER#{user_id}",
            "SK": f"APIKEY#{key_hash[:16]}",
            "GSI2PK": f"APIKEY#{key_hash}",
            "GSI2SK": now,
            "user_id": user_id,
            "key_hash": key_hash,
            "permissions": ["read", "write"],
            "created_at": now,
        }
    )

    return user_id, raw_key


@pytest.fixture
def sample_listing(dynamodb, sample_user):
    """Create a sample listing owned by sample_user."""
    user_id, _ = sample_user
    listing_id = "lst_vtoken_test"
    now = datetime.now(timezone.utc).isoformat()

    dynamodb.put_item(
        Item={
            "PK": f"LISTING#{listing_id}",
            "SK": "META",
            "GSI2PK": f"AGENT#{user_id}",
            "GSI2SK": now,
            "listing_id": listing_id,
            "type": "service",
            "category": "development",
            "title": "Expert Code Review",
            "description": "Professional code review service",
            "posted_by": user_id,
            "agent_name": "testbot",
            "status": "active",
            "created_at": now,
        }
    )

    return listing_id


@pytest.fixture
def sample_vtoken(dynamodb, sample_user):
    """Create a v-token by calling the handler."""
    from handlers.vtokens import create_vtoken

    _, api_key = sample_user

    event = make_api_event(
        method="POST",
        api_key=api_key,
        body={"purpose": "service_inquiry", "expires_in": 3600},
    )

    resp = create_vtoken(event, None)
    body = json.loads(resp["body"])
    return body["token"]


# === POST /vtokens ===


class TestCreateVToken:
    def test_success_minimal(self, dynamodb, sample_user):
        from handlers.vtokens import create_vtoken

        user_id, api_key = sample_user

        event = make_api_event(method="POST", api_key=api_key, body={})

        resp = create_vtoken(event, None)
        assert resp["statusCode"] == 201

        body = json.loads(resp["body"])
        assert body["token"].startswith("vt_")
        assert body["issuer_id"] == user_id
        assert body["purpose"] == "general"
        assert body["status"] == "active"
        assert "created_at" in body
        assert "expires_at" in body
        assert "verify_url" in body

    def test_success_all_fields(self, dynamodb, sample_user, sample_listing):
        from handlers.vtokens import create_vtoken

        user_id, api_key = sample_user
        listing_id = sample_listing

        event = make_api_event(
            method="POST",
            api_key=api_key,
            body={
                "purpose": "transaction",
                "listing_id": listing_id,
                "expires_in": 7200,
                "single_use": True,
                "max_claims": 3,
                "metadata": {"label": "Code review consultation"},
            },
        )

        resp = create_vtoken(event, None)
        assert resp["statusCode"] == 201

        body = json.loads(resp["body"])
        assert body["purpose"] == "transaction"
        assert body["listing_id"] == listing_id

    def test_invalid_purpose(self, dynamodb, sample_user):
        from handlers.vtokens import create_vtoken

        _, api_key = sample_user

        event = make_api_event(
            method="POST", api_key=api_key, body={"purpose": "hacking"}
        )

        resp = create_vtoken(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "invalid_purpose"

    def test_expires_too_short(self, dynamodb, sample_user):
        from handlers.vtokens import create_vtoken

        _, api_key = sample_user

        event = make_api_event(
            method="POST", api_key=api_key, body={"expires_in": 60}
        )

        resp = create_vtoken(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "invalid_expires_in"

    def test_expires_too_long(self, dynamodb, sample_user):
        from handlers.vtokens import create_vtoken

        _, api_key = sample_user

        event = make_api_event(
            method="POST", api_key=api_key, body={"expires_in": 100000}
        )

        resp = create_vtoken(event, None)
        assert resp["statusCode"] == 400

    def test_nonexistent_listing(self, dynamodb, sample_user):
        from handlers.vtokens import create_vtoken

        _, api_key = sample_user

        event = make_api_event(
            method="POST",
            api_key=api_key,
            body={"listing_id": "lst_nonexistent"},
        )

        resp = create_vtoken(event, None)
        assert resp["statusCode"] == 404

    def test_listing_not_owned(self, dynamodb, sample_user, second_user, sample_listing):
        from handlers.vtokens import create_vtoken

        _, second_key = second_user

        event = make_api_event(
            method="POST",
            api_key=second_key,
            body={"listing_id": sample_listing},
        )

        resp = create_vtoken(event, None)
        assert resp["statusCode"] == 403

    def test_label_too_long(self, dynamodb, sample_user):
        from handlers.vtokens import create_vtoken

        _, api_key = sample_user

        event = make_api_event(
            method="POST",
            api_key=api_key,
            body={"metadata": {"label": "x" * 201}},
        )

        resp = create_vtoken(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "invalid_label"

    def test_unauthenticated(self, dynamodb):
        from handlers.vtokens import create_vtoken

        event = make_api_event(method="POST", body={})

        resp = create_vtoken(event, None)
        assert resp["statusCode"] == 401

    def test_negative_max_claims(self, dynamodb, sample_user):
        from handlers.vtokens import create_vtoken

        _, api_key = sample_user

        event = make_api_event(
            method="POST", api_key=api_key, body={"max_claims": -1}
        )

        resp = create_vtoken(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "invalid_max_claims"


# === GET /vtokens/{token}/verify ===


class TestVerifyVToken:
    def test_valid_token(self, dynamodb, sample_user, sample_vtoken):
        from handlers.vtokens import verify_vtoken

        event = make_api_event(
            method="GET",
            path_params={"token": sample_vtoken},
        )

        resp = verify_vtoken(event, None)
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert body["valid"] is True
        assert "issuer" in body
        assert body["issuer"]["agent_id"] == sample_user[0]
        assert body["purpose"] == "service_inquiry"
        assert "signature" in body
        assert body["signature_algorithm"] == "HMAC-SHA256"
        assert body["signed_fields"] == "token:issuer_id:purpose:trust_score:created_at:expires_at"
        assert body["claims_count"] == 0

    def test_nonexistent_token(self, dynamodb):
        from handlers.vtokens import verify_vtoken

        event = make_api_event(
            method="GET",
            path_params={"token": "vt_nonexistent"},
        )

        resp = verify_vtoken(event, None)
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert body["valid"] is False
        assert body["reason"] == "not_found"

    def test_expired_token(self, dynamodb, sample_user):
        from handlers.vtokens import create_vtoken, verify_vtoken

        _, api_key = sample_user

        # Create a token with minimum expiry
        create_event = make_api_event(
            method="POST",
            api_key=api_key,
            body={"expires_in": 300},
        )
        create_resp = create_vtoken(create_event, None)
        token_id = json.loads(create_resp["body"])["token"]

        # Manually set the token to be expired
        table = dynamodb
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        table.update_item(
            Key={"PK": f"VTOKEN#{token_id}", "SK": "META"},
            UpdateExpression="SET expires_at = :ea",
            ExpressionAttributeValues={":ea": past},
        )

        event = make_api_event(
            method="GET",
            path_params={"token": token_id},
        )

        resp = verify_vtoken(event, None)
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert body["valid"] is False
        assert body["reason"] == "expired"

    def test_single_use_invalidation(self, dynamodb, sample_user):
        from handlers.vtokens import create_vtoken, verify_vtoken

        _, api_key = sample_user

        # Create single_use token
        create_event = make_api_event(
            method="POST",
            api_key=api_key,
            body={"single_use": True},
        )
        create_resp = create_vtoken(create_event, None)
        token_id = json.loads(create_resp["body"])["token"]

        # First verify — should work
        event = make_api_event(method="GET", path_params={"token": token_id})
        resp = verify_vtoken(event, None)
        body = json.loads(resp["body"])
        assert body["valid"] is True

        # Second verify — should be exhausted
        resp2 = verify_vtoken(event, None)
        body2 = json.loads(resp2["body"])
        assert body2["valid"] is False
        assert body2["reason"] == "exhausted"

    def test_signature_verification(self, dynamodb, sample_user, sample_vtoken):
        from handlers.vtokens import verify_vtoken, VTOKEN_SECRET

        event = make_api_event(
            method="GET",
            path_params={"token": sample_vtoken},
        )

        resp = verify_vtoken(event, None)
        body = json.loads(resp["body"])

        # Recompute signature
        message = (
            f"{sample_vtoken}:{body['issuer']['agent_id']}:{body['purpose']}"
            f":{body['issuer']['trust_score']}:{body['created_at']}:{body['expires_at']}"
        )
        expected_sig = hmac.new(
            VTOKEN_SECRET.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        assert body["signature"] == expected_sig

    def test_with_listing(self, dynamodb, sample_user, sample_listing):
        from handlers.vtokens import create_vtoken, verify_vtoken

        _, api_key = sample_user

        create_event = make_api_event(
            method="POST",
            api_key=api_key,
            body={"listing_id": sample_listing, "purpose": "transaction"},
        )
        create_resp = create_vtoken(create_event, None)
        token_id = json.loads(create_resp["body"])["token"]

        event = make_api_event(method="GET", path_params={"token": token_id})
        resp = verify_vtoken(event, None)
        body = json.loads(resp["body"])

        assert body["valid"] is True
        assert "listing" in body
        assert body["listing"]["listing_id"] == sample_listing
        assert body["listing"]["title"] == "Expert Code Review"

    def test_rate_limiting(self, dynamodb, sample_vtoken):
        from handlers.vtokens import verify_vtoken

        with patch(
            "handlers.vtokens.check_rate_limit", return_value=(False, 0, 3600)
        ):
            event = make_api_event(
                method="GET",
                path_params={"token": sample_vtoken},
            )
            resp = verify_vtoken(event, None)
            assert resp["statusCode"] == 429


# === POST /vtokens/{token}/claim ===


class TestClaimVToken:
    def test_success(self, dynamodb, sample_user, second_user, sample_vtoken):
        from handlers.vtokens import claim_vtoken

        issuer_id, _ = sample_user
        claimant_id, claimant_key = second_user

        event = make_api_event(
            method="POST",
            api_key=claimant_key,
            path_params={"token": sample_vtoken},
            body={"notes": "Interested in code review"},
        )

        resp = claim_vtoken(event, None)
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert body["claimed"] is True
        assert body["token"] == sample_vtoken
        assert body["mutual_verification"] is True
        assert body["issuer"]["agent_id"] == issuer_id
        assert body["claimant"]["agent_id"] == claimant_id
        assert "claimed_at" in body

    def test_self_claim(self, dynamodb, sample_user, sample_vtoken):
        from handlers.vtokens import claim_vtoken

        _, api_key = sample_user

        event = make_api_event(
            method="POST",
            api_key=api_key,
            path_params={"token": sample_vtoken},
            body={},
        )

        resp = claim_vtoken(event, None)
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert body["claimed"] is False
        assert body["reason"] == "cannot_claim_own_token"

    def test_duplicate_claim(self, dynamodb, sample_user, second_user, sample_vtoken):
        from handlers.vtokens import claim_vtoken

        _, claimant_key = second_user

        event = make_api_event(
            method="POST",
            api_key=claimant_key,
            path_params={"token": sample_vtoken},
            body={},
        )

        # First claim
        resp1 = claim_vtoken(event, None)
        assert json.loads(resp1["body"])["claimed"] is True

        # Duplicate claim
        resp2 = claim_vtoken(event, None)
        body2 = json.loads(resp2["body"])
        assert body2["claimed"] is False
        assert body2["reason"] == "already_claimed"

    def test_expired_token(self, dynamodb, sample_user, second_user, sample_vtoken):
        from handlers.vtokens import claim_vtoken

        _, claimant_key = second_user

        # Manually expire the token
        table = dynamodb
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        table.update_item(
            Key={"PK": f"VTOKEN#{sample_vtoken}", "SK": "META"},
            UpdateExpression="SET expires_at = :ea",
            ExpressionAttributeValues={":ea": past},
        )

        event = make_api_event(
            method="POST",
            api_key=claimant_key,
            path_params={"token": sample_vtoken},
            body={},
        )

        resp = claim_vtoken(event, None)
        body = json.loads(resp["body"])
        assert body["claimed"] is False
        assert body["reason"] == "expired"

    def test_max_claims_exhausted(self, dynamodb, sample_user, second_user):
        from handlers.vtokens import create_vtoken, claim_vtoken

        _, issuer_key = sample_user
        _, claimant_key = second_user

        # Create token with max_claims=1
        create_event = make_api_event(
            method="POST",
            api_key=issuer_key,
            body={"max_claims": 1},
        )
        create_resp = create_vtoken(create_event, None)
        token_id = json.loads(create_resp["body"])["token"]

        # First claim by second_user
        claim_event = make_api_event(
            method="POST",
            api_key=claimant_key,
            path_params={"token": token_id},
            body={},
        )
        resp1 = claim_vtoken(claim_event, None)
        assert json.loads(resp1["body"])["claimed"] is True

        # Create a third user and try to claim
        from utils.auth import generate_api_key

        third_key, third_hash = generate_api_key()
        now = datetime.now(timezone.utc).isoformat()
        dynamodb.put_item(
            Item={
                "PK": "USER#thirduser",
                "SK": "META",
                "user_id": "thirduser",
                "username": "thirdbot",
                "trust_score": Decimal("0.1"),
                "created_at": now,
            }
        )
        dynamodb.put_item(
            Item={
                "PK": "USER#thirduser",
                "SK": f"APIKEY#{third_hash[:16]}",
                "GSI2PK": f"APIKEY#{third_hash}",
                "GSI2SK": now,
                "user_id": "thirduser",
                "key_hash": third_hash,
            }
        )

        claim_event2 = make_api_event(
            method="POST",
            api_key=third_key,
            path_params={"token": token_id},
            body={},
        )
        resp2 = claim_vtoken(claim_event2, None)
        body2 = json.loads(resp2["body"])
        assert body2["claimed"] is False
        assert body2["reason"] == "max_claims_reached"

    def test_nonexistent_token(self, dynamodb, second_user):
        from handlers.vtokens import claim_vtoken

        _, claimant_key = second_user

        event = make_api_event(
            method="POST",
            api_key=claimant_key,
            path_params={"token": "vt_nonexistent"},
            body={},
        )

        resp = claim_vtoken(event, None)
        body = json.loads(resp["body"])
        assert body["claimed"] is False
        assert body["reason"] == "not_found"

    def test_unauthenticated(self, dynamodb, sample_vtoken):
        from handlers.vtokens import claim_vtoken

        event = make_api_event(
            method="POST",
            path_params={"token": sample_vtoken},
            body={},
        )

        resp = claim_vtoken(event, None)
        assert resp["statusCode"] == 401

    def test_notes_too_long(self, dynamodb, sample_user, second_user, sample_vtoken):
        from handlers.vtokens import claim_vtoken

        _, claimant_key = second_user

        event = make_api_event(
            method="POST",
            api_key=claimant_key,
            path_params={"token": sample_vtoken},
            body={"notes": "x" * 501},
        )

        resp = claim_vtoken(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "invalid_notes"

    def test_trust_events_created(self, dynamodb, sample_user, second_user, sample_vtoken):
        from handlers.vtokens import claim_vtoken

        issuer_id, _ = sample_user
        claimant_id, claimant_key = second_user

        event = make_api_event(
            method="POST",
            api_key=claimant_key,
            path_params={"token": sample_vtoken},
            body={},
        )

        claim_vtoken(event, None)

        # Check trust events were created for issuer
        issuer_events = dynamodb.query(
            KeyConditionExpression=Key("PK").eq(f"TRUST#{issuer_id}")
            & Key("SK").begins_with("EVENT#"),
        )
        issuer_vtoken_events = [
            e for e in issuer_events["Items"] if e.get("event_type") == "vtoken_issued"
        ]
        assert len(issuer_vtoken_events) == 1

        # Check trust events were created for claimant
        claimant_events = dynamodb.query(
            KeyConditionExpression=Key("PK").eq(f"TRUST#{claimant_id}")
            & Key("SK").begins_with("EVENT#"),
        )
        claimant_vtoken_events = [
            e for e in claimant_events["Items"] if e.get("event_type") == "vtoken_claimed"
        ]
        assert len(claimant_vtoken_events) == 1


# === GET /vtokens ===


class TestListVTokens:
    def test_success(self, dynamodb, sample_user, sample_vtoken):
        from handlers.vtokens import list_vtokens

        _, api_key = sample_user

        event = make_api_event(method="GET", api_key=api_key)

        resp = list_vtokens(event, None)
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert "tokens" in body
        assert body["count"] >= 1
        assert any(t["token"] == sample_vtoken for t in body["tokens"])

    def test_status_filter(self, dynamodb, sample_user, sample_vtoken):
        from handlers.vtokens import list_vtokens

        _, api_key = sample_user

        event = make_api_event(
            method="GET", api_key=api_key, query_params={"status": "active"}
        )

        resp = list_vtokens(event, None)
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        for token in body["tokens"]:
            assert token["status"] == "active"

    def test_invalid_status(self, dynamodb, sample_user):
        from handlers.vtokens import list_vtokens

        _, api_key = sample_user

        event = make_api_event(
            method="GET", api_key=api_key, query_params={"status": "invalid"}
        )

        resp = list_vtokens(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "invalid_status"

    def test_empty_list(self, dynamodb, second_user):
        from handlers.vtokens import list_vtokens

        _, api_key = second_user

        event = make_api_event(method="GET", api_key=api_key)

        resp = list_vtokens(event, None)
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert body["tokens"] == []
        assert body["count"] == 0

    def test_unauthenticated(self, dynamodb):
        from handlers.vtokens import list_vtokens

        event = make_api_event(method="GET")

        resp = list_vtokens(event, None)
        assert resp["statusCode"] == 401


# === GET /vtokens/{token}/claims ===


class TestGetVTokenClaims:
    def test_success(self, dynamodb, sample_user, second_user, sample_vtoken):
        from handlers.vtokens import claim_vtoken, get_vtoken_claims

        _, issuer_key = sample_user
        claimant_id, claimant_key = second_user

        # First claim the token
        claim_event = make_api_event(
            method="POST",
            api_key=claimant_key,
            path_params={"token": sample_vtoken},
            body={},
        )
        claim_vtoken(claim_event, None)

        # Now get claims as issuer
        event = make_api_event(
            method="GET",
            api_key=issuer_key,
            path_params={"token": sample_vtoken},
        )

        resp = get_vtoken_claims(event, None)
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert body["token"] == sample_vtoken
        assert len(body["claims"]) == 1
        assert body["claims"][0]["claimant_id"] == claimant_id
        assert "trust_score" in body["claims"][0]
        assert "claimed_at" in body["claims"][0]

    def test_forbidden_non_issuer(self, dynamodb, sample_user, second_user, sample_vtoken):
        from handlers.vtokens import get_vtoken_claims

        _, claimant_key = second_user

        event = make_api_event(
            method="GET",
            api_key=claimant_key,
            path_params={"token": sample_vtoken},
        )

        resp = get_vtoken_claims(event, None)
        assert resp["statusCode"] == 403

    def test_nonexistent_token(self, dynamodb, sample_user):
        from handlers.vtokens import get_vtoken_claims

        _, api_key = sample_user

        event = make_api_event(
            method="GET",
            api_key=api_key,
            path_params={"token": "vt_nonexistent"},
        )

        resp = get_vtoken_claims(event, None)
        assert resp["statusCode"] == 404

    def test_no_claims(self, dynamodb, sample_user, sample_vtoken):
        from handlers.vtokens import get_vtoken_claims

        _, issuer_key = sample_user

        event = make_api_event(
            method="GET",
            api_key=issuer_key,
            path_params={"token": sample_vtoken},
        )

        resp = get_vtoken_claims(event, None)
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert body["claims"] == []

    def test_unauthenticated(self, dynamodb, sample_vtoken):
        from handlers.vtokens import get_vtoken_claims

        event = make_api_event(
            method="GET",
            path_params={"token": sample_vtoken},
        )

        resp = get_vtoken_claims(event, None)
        assert resp["statusCode"] == 401


# === Full Flow Integration ===


class TestFullVerificationFlow:
    def test_complete_mutual_verification(
        self, dynamodb, sample_user, second_user, sample_listing
    ):
        """Test the complete v-token flow: create → verify → claim → check claims."""
        from handlers.vtokens import (
            create_vtoken,
            verify_vtoken,
            claim_vtoken,
            get_vtoken_claims,
        )

        issuer_id, issuer_key = sample_user
        claimant_id, claimant_key = second_user

        # 1. Seller creates a v-token
        create_event = make_api_event(
            method="POST",
            api_key=issuer_key,
            body={
                "purpose": "transaction",
                "listing_id": sample_listing,
                "metadata": {"label": "Code review consultation"},
            },
        )
        create_resp = create_vtoken(create_event, None)
        assert create_resp["statusCode"] == 201
        token_id = json.loads(create_resp["body"])["token"]

        # 2. Buyer verifies the token (public, no auth)
        verify_event = make_api_event(
            method="GET", path_params={"token": token_id}
        )
        verify_resp = verify_vtoken(verify_event, None)
        assert verify_resp["statusCode"] == 200
        verify_body = json.loads(verify_resp["body"])
        assert verify_body["valid"] is True
        assert verify_body["issuer"]["agent_id"] == issuer_id
        assert verify_body["purpose"] == "transaction"
        assert verify_body["listing"]["listing_id"] == sample_listing

        # 3. Buyer claims the token (proves their identity)
        claim_event = make_api_event(
            method="POST",
            api_key=claimant_key,
            path_params={"token": token_id},
            body={"notes": "I'd like the code review service"},
        )
        claim_resp = claim_vtoken(claim_event, None)
        assert claim_resp["statusCode"] == 200
        claim_body = json.loads(claim_resp["body"])
        assert claim_body["claimed"] is True
        assert claim_body["mutual_verification"] is True

        # 4. Seller checks who claimed
        claims_event = make_api_event(
            method="GET",
            api_key=issuer_key,
            path_params={"token": token_id},
        )
        claims_resp = get_vtoken_claims(claims_event, None)
        assert claims_resp["statusCode"] == 200
        claims_body = json.loads(claims_resp["body"])
        assert len(claims_body["claims"]) == 1
        assert claims_body["claims"][0]["claimant_id"] == claimant_id

    def test_unlimited_claims(self, dynamodb, sample_user, second_user):
        """Test max_claims=0 allows unlimited claims."""
        from handlers.vtokens import create_vtoken, claim_vtoken
        from utils.auth import generate_api_key

        _, issuer_key = sample_user
        _, claimant_key = second_user

        # Create token with unlimited claims
        create_event = make_api_event(
            method="POST",
            api_key=issuer_key,
            body={"max_claims": 0},
        )
        create_resp = create_vtoken(create_event, None)
        token_id = json.loads(create_resp["body"])["token"]

        # First claim
        claim_event = make_api_event(
            method="POST",
            api_key=claimant_key,
            path_params={"token": token_id},
            body={},
        )
        resp1 = claim_vtoken(claim_event, None)
        assert json.loads(resp1["body"])["claimed"] is True

        # Create third user and claim again
        third_key, third_hash = generate_api_key()
        now = datetime.now(timezone.utc).isoformat()
        dynamodb.put_item(
            Item={
                "PK": "USER#thirduser2",
                "SK": "META",
                "user_id": "thirduser2",
                "username": "thirdbot2",
                "trust_score": Decimal("0.2"),
                "created_at": now,
            }
        )
        dynamodb.put_item(
            Item={
                "PK": "USER#thirduser2",
                "SK": f"APIKEY#{third_hash[:16]}",
                "GSI2PK": f"APIKEY#{third_hash}",
                "GSI2SK": now,
                "user_id": "thirduser2",
                "key_hash": third_hash,
            }
        )

        claim_event2 = make_api_event(
            method="POST",
            api_key=third_key,
            path_params={"token": token_id},
            body={},
        )
        resp2 = claim_vtoken(claim_event2, None)
        assert json.loads(resp2["body"])["claimed"] is True
