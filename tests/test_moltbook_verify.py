"""Tests for Phase 3A: Moltbook Identity Verification Service.

Covers:
- calculate_enhanced_trust_score() unit tests
- moltbook_verify_initiate handler
- moltbook_verify_confirm handler
- moltbook_trust handler (public lookup)
"""

import json
import math
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tests.conftest import make_api_event

# ---------------------------------------------------------------------------
# 1. Unit tests for calculate_enhanced_trust_score()
# ---------------------------------------------------------------------------


class TestEnhancedTrustScore:
    """Tests for the spec's enhanced trust formula (0-100 scale)."""

    def test_unclaimed_returns_zero(self):
        from handlers.moltbook import calculate_enhanced_trust_score

        profile = {"agent": {"karma": 500, "is_claimed": False}}
        result = calculate_enhanced_trust_score(profile)
        assert result["trust_score"] == 0
        assert result["raw"]["is_claimed"] is False

    def test_empty_profile_zero(self):
        from handlers.moltbook import calculate_enhanced_trust_score

        result = calculate_enhanced_trust_score({})
        assert result["trust_score"] == 0

    def test_max_score(self):
        """High karma, old account, many followers, lots of activity → near 100."""
        from handlers.moltbook import calculate_enhanced_trust_score

        created = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
        profile = {
            "agent": {
                "karma": 200,
                "created_at": created,
                "is_claimed": True,
                "follower_count": 1000,
                "posts_count": 50,
                "comments_count": 100,
            }
        }
        result = calculate_enhanced_trust_score(profile)
        # karma: min(200*0.5, 40) = 40
        # age: min(365*0.1, 20) = 20
        # social: min(log(1001)*2, 20) = min(13.8, 20) = 13.8
        # activity: min(50*2 + 100*0.1, 20) = 20
        assert result["trust_score"] >= 90
        assert result["breakdown"]["karma"] == 40
        assert result["breakdown"]["account_age"] == 20
        assert result["breakdown"]["activity"] == 20

    def test_karma_only(self):
        from handlers.moltbook import calculate_enhanced_trust_score

        profile = {"agent": {"karma": 40, "is_claimed": True}}
        result = calculate_enhanced_trust_score(profile)
        # karma: 40 * 0.5 = 20
        assert result["breakdown"]["karma"] == 20
        assert result["breakdown"]["account_age"] == 0
        assert result["breakdown"]["social_proof"] == 0
        assert result["breakdown"]["activity"] == 0
        assert result["trust_score"] == 20

    def test_karma_caps_at_40(self):
        from handlers.moltbook import calculate_enhanced_trust_score

        profile = {"agent": {"karma": 1000, "is_claimed": True}}
        result = calculate_enhanced_trust_score(profile)
        assert result["breakdown"]["karma"] == 40

    def test_social_proof_logarithmic(self):
        from handlers.moltbook import calculate_enhanced_trust_score

        # 10 followers: log(11)*2 ≈ 4.8
        profile = {"agent": {"is_claimed": True, "follower_count": 10}}
        result = calculate_enhanced_trust_score(profile)
        expected = round(min(math.log(11) * 2, 20), 2)
        assert result["breakdown"]["social_proof"] == expected

    def test_activity_mixed(self):
        from handlers.moltbook import calculate_enhanced_trust_score

        # 5 posts * 2 + 50 comments * 0.1 = 10 + 5 = 15
        profile = {
            "agent": {"is_claimed": True, "posts_count": 5, "comments_count": 50}
        }
        result = calculate_enhanced_trust_score(profile)
        assert result["breakdown"]["activity"] == 15

    def test_activity_caps_at_20(self):
        from handlers.moltbook import calculate_enhanced_trust_score

        profile = {
            "agent": {"is_claimed": True, "posts_count": 100, "comments_count": 1000}
        }
        result = calculate_enhanced_trust_score(profile)
        assert result["breakdown"]["activity"] == 20

    def test_age_partial(self):
        from handlers.moltbook import calculate_enhanced_trust_score

        created = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        profile = {"agent": {"is_claimed": True, "created_at": created}}
        result = calculate_enhanced_trust_score(profile)
        # min(100 * 0.1, 20) = 10
        assert result["breakdown"]["account_age"] == 10

    def test_raw_signals_present(self):
        from handlers.moltbook import calculate_enhanced_trust_score

        profile = {
            "agent": {
                "karma": 50,
                "is_claimed": True,
                "is_active": True,
                "follower_count": 3,
                "following_count": 16,
                "posts_count": 2,
                "comments_count": 5,
            }
        }
        result = calculate_enhanced_trust_score(profile)
        assert result["raw"]["karma"] == 50
        assert result["raw"]["follower_count"] == 3
        assert result["raw"]["following_count"] == 16
        assert result["raw"]["posts_count"] == 2
        assert result["raw"]["comments_count"] == 5
        assert result["raw"]["is_active"] is True


# ---------------------------------------------------------------------------
# 2. Handler tests: moltbook_verify_initiate
# ---------------------------------------------------------------------------


class TestMoltbookVerifyInitiate:

    @patch("handlers.moltbook.fetch_trust_metrics")
    def test_successful_initiation(self, mock_fetch, dynamodb, sample_user):
        from handlers.moltbook import moltbook_verify_initiate

        user_id, raw_key = sample_user
        mock_fetch.return_value = {"agent": {"name": "testbot", "is_claimed": True}}

        event = make_api_event(
            method="POST",
            path="/moltbook/verify",
            body={"moltbook_username": "testbot"},
            api_key=raw_key,
        )
        resp = moltbook_verify_initiate(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert "challenge_code" in body
        assert body["challenge_code"].startswith("agentpier-verify-")
        assert body["moltbook_username"] == "testbot"
        assert "instructions" in body
        assert body["expires_in_seconds"] == 1800

    def test_unauthenticated(self, dynamodb):
        from handlers.moltbook import moltbook_verify_initiate

        event = make_api_event(
            method="POST",
            path="/moltbook/verify",
            body={"moltbook_username": "testbot"},
        )
        resp = moltbook_verify_initiate(event, None)
        assert resp["statusCode"] == 401

    def test_missing_username(self, dynamodb, sample_user):
        from handlers.moltbook import moltbook_verify_initiate

        _, raw_key = sample_user
        event = make_api_event(
            method="POST",
            path="/moltbook/verify",
            body={},
            api_key=raw_key,
        )
        resp = moltbook_verify_initiate(event, None)
        assert resp["statusCode"] == 400

    @patch("handlers.moltbook.fetch_trust_metrics")
    def test_moltbook_not_found(self, mock_fetch, dynamodb, sample_user):
        from handlers.moltbook import moltbook_verify_initiate
        from utils.moltbook import MoltbookNotFoundError

        _, raw_key = sample_user
        mock_fetch.side_effect = MoltbookNotFoundError("not found")

        event = make_api_event(
            method="POST",
            path="/moltbook/verify",
            body={"moltbook_username": "nonexistent"},
            api_key=raw_key,
        )
        resp = moltbook_verify_initiate(event, None)
        assert resp["statusCode"] == 404

    @patch("handlers.moltbook.fetch_trust_metrics")
    def test_unclaimed_rejected(self, mock_fetch, dynamodb, sample_user):
        from handlers.moltbook import moltbook_verify_initiate

        _, raw_key = sample_user
        mock_fetch.return_value = {
            "agent": {"name": "unclaimed-bot", "is_claimed": False}
        }

        event = make_api_event(
            method="POST",
            path="/moltbook/verify",
            body={"moltbook_username": "unclaimed-bot"},
            api_key=raw_key,
        )
        resp = moltbook_verify_initiate(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "not_claimed"

    @patch("handlers.moltbook.fetch_trust_metrics")
    def test_already_linked_409(self, mock_fetch, dynamodb, sample_user):
        from handlers.moltbook import moltbook_verify_initiate

        user_id, raw_key = sample_user

        # Pre-set moltbook_verified
        dynamodb.update_item(
            Key={"PK": f"USER#{user_id}", "SK": "META"},
            UpdateExpression="SET moltbook_verified = :mv, moltbook_name = :mn",
            ExpressionAttributeValues={":mv": True, ":mn": "already-linked"},
        )

        event = make_api_event(
            method="POST",
            path="/moltbook/verify",
            body={"moltbook_username": "testbot"},
            api_key=raw_key,
        )
        resp = moltbook_verify_initiate(event, None)
        assert resp["statusCode"] == 409


# ---------------------------------------------------------------------------
# 3. Handler tests: moltbook_verify_confirm
# ---------------------------------------------------------------------------


class TestMoltbookVerifyConfirm:

    @patch("handlers.moltbook.fetch_trust_metrics")
    def test_successful_verification(self, mock_fetch, dynamodb, sample_user):
        from handlers.moltbook import moltbook_verify_initiate, moltbook_verify_confirm

        user_id, raw_key = sample_user

        # Step 1: Initiate
        mock_fetch.return_value = {
            "agent": {
                "name": "verifybot",
                "is_claimed": True,
                "karma": 100,
                "created_at": (
                    datetime.now(timezone.utc) - timedelta(days=30)
                ).isoformat(),
                "follower_count": 5,
                "posts_count": 3,
                "comments_count": 10,
                "is_active": True,
            }
        }

        init_event = make_api_event(
            method="POST",
            path="/moltbook/verify",
            body={"moltbook_username": "verifybot"},
            api_key=raw_key,
        )
        init_resp = moltbook_verify_initiate(init_event, None)
        assert init_resp["statusCode"] == 200
        challenge_code = json.loads(init_resp["body"])["challenge_code"]

        # Step 2: Mock profile now contains the challenge code in description
        mock_fetch.return_value = {
            "agent": {
                "name": "verifybot",
                "is_claimed": True,
                "karma": 100,
                "created_at": (
                    datetime.now(timezone.utc) - timedelta(days=30)
                ).isoformat(),
                "follower_count": 5,
                "posts_count": 3,
                "comments_count": 10,
                "is_active": True,
                "description": f"My cool agent. {challenge_code} Verified!",
                "owner": "owner-123",
            }
        }

        confirm_event = make_api_event(
            method="POST",
            path="/moltbook/verify/confirm",
            api_key=raw_key,
        )
        resp = moltbook_verify_confirm(confirm_event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["verified"] is True
        assert body["moltbook_username"] == "verifybot"
        assert body["verification_method"] == "challenge_response"
        assert body["trust_score"] > 0
        assert "trust_breakdown" in body
        assert "raw_signals" in body

        # Verify DynamoDB updated
        item = dynamodb.get_item(Key={"PK": f"USER#{user_id}", "SK": "META"})["Item"]
        assert item["moltbook_verified"] is True
        assert item["moltbook_name"] == "verifybot"
        assert item["moltbook_verification_method"] == "challenge_response"

        # Verify challenge was cleaned up
        challenge = dynamodb.get_item(
            Key={"PK": f"USER#{user_id}", "SK": "MOLTBOOK_CHALLENGE"}
        )
        assert "Item" not in challenge

    def test_no_pending_challenge(self, dynamodb, sample_user):
        from handlers.moltbook import moltbook_verify_confirm

        _, raw_key = sample_user
        event = make_api_event(
            method="POST",
            path="/moltbook/verify/confirm",
            api_key=raw_key,
        )
        resp = moltbook_verify_confirm(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "no_challenge"

    @patch("handlers.moltbook.fetch_trust_metrics")
    def test_challenge_not_in_description(self, mock_fetch, dynamodb, sample_user):
        from handlers.moltbook import moltbook_verify_initiate, moltbook_verify_confirm

        _, raw_key = sample_user

        mock_fetch.return_value = {"agent": {"name": "testbot", "is_claimed": True}}

        # Initiate
        init_event = make_api_event(
            method="POST",
            path="/moltbook/verify",
            body={"moltbook_username": "testbot"},
            api_key=raw_key,
        )
        moltbook_verify_initiate(init_event, None)

        # Confirm without code in description
        mock_fetch.return_value = {
            "agent": {
                "name": "testbot",
                "is_claimed": True,
                "description": "No challenge here",
            }
        }
        confirm_event = make_api_event(
            method="POST",
            path="/moltbook/verify/confirm",
            api_key=raw_key,
        )
        resp = moltbook_verify_confirm(confirm_event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "challenge_not_found"

    @patch("handlers.moltbook.fetch_trust_metrics")
    def test_expired_challenge(self, mock_fetch, dynamodb, sample_user):
        from handlers.moltbook import moltbook_verify_confirm

        user_id, raw_key = sample_user

        # Manually insert an expired challenge
        dynamodb.put_item(
            Item={
                "PK": f"USER#{user_id}",
                "SK": "MOLTBOOK_CHALLENGE",
                "challenge_code": "agentpier-verify-expired",
                "moltbook_username": "testbot",
                "created_at": "2020-01-01T00:00:00+00:00",
                "expires_at": "0",  # Already expired
            }
        )

        event = make_api_event(
            method="POST",
            path="/moltbook/verify/confirm",
            api_key=raw_key,
        )
        resp = moltbook_verify_confirm(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "challenge_expired"

    def test_unauthenticated(self, dynamodb):
        from handlers.moltbook import moltbook_verify_confirm

        event = make_api_event(
            method="POST",
            path="/moltbook/verify/confirm",
        )
        resp = moltbook_verify_confirm(event, None)
        assert resp["statusCode"] == 401


# ---------------------------------------------------------------------------
# 4. Handler tests: moltbook_trust (public lookup)
# ---------------------------------------------------------------------------


class TestMoltbookTrust:

    @patch("handlers.moltbook.fetch_trust_metrics")
    def test_successful_lookup(self, mock_fetch):
        from handlers.moltbook import moltbook_trust

        mock_fetch.return_value = {
            "agent": {
                "name": "coolbot",
                "display_name": "CoolBot",
                "description": "A cool bot",
                "karma": 54,
                "is_claimed": True,
                "follower_count": 3,
                "following_count": 16,
                "posts_count": 0,
                "comments_count": 0,
                "created_at": (
                    datetime.now(timezone.utc) - timedelta(days=8)
                ).isoformat(),
                "last_active": datetime.now(timezone.utc).isoformat(),
                "is_verified": False,
                "is_active": True,
            }
        }

        event = {
            "pathParameters": {"username": "coolbot"},
            "headers": {},
            "requestContext": {"identity": {"sourceIp": "127.0.0.1"}, "stage": "test"},
        }
        resp = moltbook_trust(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["moltbook_username"] == "coolbot"
        assert body["trust_score"] > 0
        assert "trust_breakdown" in body
        assert "raw_signals" in body
        assert body["display_name"] == "CoolBot"

    @patch("handlers.moltbook.fetch_trust_metrics")
    def test_not_found(self, mock_fetch):
        from handlers.moltbook import moltbook_trust
        from utils.moltbook import MoltbookNotFoundError

        mock_fetch.side_effect = MoltbookNotFoundError("not found")

        event = {
            "pathParameters": {"username": "nonexistent"},
            "headers": {},
            "requestContext": {"identity": {"sourceIp": "127.0.0.1"}, "stage": "test"},
        }
        resp = moltbook_trust(event, None)
        assert resp["statusCode"] == 404

    def test_missing_username(self):
        from handlers.moltbook import moltbook_trust

        event = {
            "pathParameters": {},
            "headers": {},
            "requestContext": {"identity": {"sourceIp": "127.0.0.1"}, "stage": "test"},
        }
        resp = moltbook_trust(event, None)
        assert resp["statusCode"] == 400
