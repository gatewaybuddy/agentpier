"""Tests for Moltbook identity integration (Phase 3).

Covers:
- calculate_trust_score() unit tests
- verify_moltbook_key() / fetch_trust_metrics() with mocked HTTP
- link_moltbook / unlink_moltbook handler integration tests
- get_me with Moltbook data
"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError

from tests.conftest import make_api_event

# ---------------------------------------------------------------------------
# 1. Unit tests for calculate_trust_score()
# ---------------------------------------------------------------------------


class TestCalculateTrustScore:
    """Unit tests for the Moltbook trust scoring formula."""

    def test_zero_karma_new_unverified(self):
        """Brand new, zero karma, unverified → low score."""
        from utils.moltbook import calculate_trust_score

        profile = {
            "agent": {
                "karma": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "is_claimed": False,
                "owner": None,
            }
        }
        result = calculate_trust_score(profile)
        assert result["trust_score"] == 0.0
        assert result["breakdown"]["karma"] == 0.0
        assert result["breakdown"]["verification"] == 0.0
        assert result["raw"]["karma"] == 0
        assert result["raw"]["is_claimed"] is False
        assert result["raw"]["has_owner"] is False

    def test_high_karma_old_verified(self):
        """High karma, 90-day-old account, fully verified → high score."""
        from utils.moltbook import calculate_trust_score

        created = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        profile = {
            "agent": {
                "karma": 600,
                "created_at": created,
                "is_claimed": True,
                "owner": "some-owner-id",
            }
        }
        result = calculate_trust_score(profile)

        # karma: min(600/500,1)=1.0 → 0.4
        # age: min(90/60,1)=1.0 → 0.3
        # verification: 0.5+0.5=1.0 → 0.3
        # total: 1.0
        assert result["trust_score"] == 1.0
        assert result["breakdown"]["karma"] == 0.4
        assert result["breakdown"]["account_age"] == 0.3
        assert result["breakdown"]["verification"] == 0.3

    def test_mid_range_values(self):
        """Partial karma, 30 days old, only claimed → mid score."""
        from utils.moltbook import calculate_trust_score

        created = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        profile = {
            "agent": {
                "karma": 250,
                "created_at": created,
                "is_claimed": True,
                "owner": None,
            }
        }
        result = calculate_trust_score(profile)

        # karma: 250/500=0.5 → 0.2
        # age: 30/60=0.5 → 0.15
        # verification: 0.5 → 0.15
        # total: 0.5
        assert result["trust_score"] == 0.5
        assert result["breakdown"]["karma"] == 0.2
        assert result["breakdown"]["account_age"] == 0.15
        assert result["breakdown"]["verification"] == 0.15

    def test_missing_agent_key(self):
        """Empty profile (no 'agent' key) → zero score."""
        from utils.moltbook import calculate_trust_score

        result = calculate_trust_score({})
        assert result["trust_score"] == 0.0
        assert result["raw"]["karma"] == 0

    def test_string_karma(self):
        """Karma as string (e.g., from JSON) is handled."""
        from utils.moltbook import calculate_trust_score

        profile = {"agent": {"karma": "100"}}
        result = calculate_trust_score(profile)
        # 100/500=0.2 → 0.2*0.4=0.08
        assert result["breakdown"]["karma"] == 0.08
        assert result["raw"]["karma"] == 100

    def test_no_created_at(self):
        """Missing created_at → age_days=0, age_score=0."""
        from utils.moltbook import calculate_trust_score

        profile = {"agent": {"karma": 500, "is_claimed": True, "owner": "x"}}
        result = calculate_trust_score(profile)
        assert result["raw"]["age_days"] == 0
        assert result["breakdown"]["account_age"] == 0.0
        # karma maxed + verification maxed, no age
        assert result["trust_score"] == 0.7

    def test_invalid_created_at(self):
        """Invalid date string → age_days=0, no crash."""
        from utils.moltbook import calculate_trust_score

        profile = {"agent": {"karma": 0, "created_at": "not-a-date"}}
        result = calculate_trust_score(profile)
        assert result["raw"]["age_days"] == 0

    def test_karma_caps_at_500(self):
        """Karma above 500 still caps at 1.0 karma_score."""
        from utils.moltbook import calculate_trust_score

        profile = {"agent": {"karma": 10000}}
        result = calculate_trust_score(profile)
        assert result["breakdown"]["karma"] == 0.4  # max

    def test_age_caps_at_60_days(self):
        """Account age above 60 days still caps at 1.0 age_score."""
        from utils.moltbook import calculate_trust_score

        created = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
        profile = {"agent": {"created_at": created}}
        result = calculate_trust_score(profile)
        assert result["breakdown"]["account_age"] == 0.3  # max


# ---------------------------------------------------------------------------
# 2. Unit tests for verify_moltbook_key() and fetch_trust_metrics()
# ---------------------------------------------------------------------------


class TestVerifyMoltbookKey:
    """verify_moltbook_key is deprecated — all calls should raise DeprecationWarning."""

    def test_deprecated(self):
        from utils.moltbook import verify_moltbook_key

        with pytest.raises(DeprecationWarning, match="deprecated"):
            verify_moltbook_key("any-key")


class TestFetchTrustMetrics:
    """Mock HTTP for public trust metrics endpoint."""

    @patch("utils.moltbook.urlopen")
    def test_success(self, mock_urlopen):
        from utils.moltbook import fetch_trust_metrics

        payload = {"agent": {"name": "cool-agent", "karma": 200}}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(payload).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = fetch_trust_metrics("cool-agent")
        assert result["agent"]["karma"] == 200
        # Should call profile endpoint without auth
        req = mock_urlopen.call_args[0][0]
        assert "/agents/profile?name=cool-agent" in req.full_url
        assert req.get_header("Authorization") is None

    @patch("utils.moltbook.urlopen")
    def test_not_found(self, mock_urlopen):
        from utils.moltbook import fetch_trust_metrics, MoltbookNotFoundError

        mock_urlopen.side_effect = HTTPError(
            url="https://www.moltbook.com/api/v1/agents/profile",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None,
        )
        with pytest.raises(MoltbookNotFoundError):
            fetch_trust_metrics("nonexistent-agent")

    @patch("utils.moltbook.urlopen")
    def test_server_error(self, mock_urlopen):
        from utils.moltbook import fetch_trust_metrics, MoltbookAPIError

        mock_urlopen.side_effect = HTTPError(
            url="https://www.moltbook.com/api/v1/agents/profile",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )
        with pytest.raises(MoltbookAPIError, match="500"):
            fetch_trust_metrics("some-agent")


# ---------------------------------------------------------------------------
# 3. Integration tests for link_moltbook handler
# ---------------------------------------------------------------------------

# TestLinkMoltbook removed — link_moltbook endpoint removed (pre-launch cleanup)


# ---------------------------------------------------------------------------
# 4. Integration tests for moltbook_unlink handler
# ---------------------------------------------------------------------------


class TestMoltbookUnlink:
    """Integration tests: moltbook_unlink handler (POST /moltbook/unlink)."""

    def test_successful_unlink(self, dynamodb, sample_user):
        from handlers.moltbook import moltbook_unlink

        user_id, raw_key = sample_user

        # Directly set moltbook fields in DB
        dynamodb.update_item(
            Key={"PK": f"USER#{user_id}", "SK": "META"},
            UpdateExpression=(
                "SET moltbook_verified = :mv, moltbook_name = :mn, "
                "trust_score = :ts, moltbook_verified_at = :mvat"
            ),
            ExpressionAttributeValues={
                ":mv": True,
                ":mn": "linked-agent",
                ":ts": Decimal("0.8"),
                ":mvat": "2025-01-01T00:00:00+00:00",
            },
        )

        # Now unlink
        unlink_event = make_api_event(
            method="POST",
            path="/moltbook/unlink",
            api_key=raw_key,
        )
        resp = moltbook_unlink(unlink_event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["unlinked"] is True
        assert body["trust_score"] == 0.0

        # Verify DynamoDB: trust_score reset, moltbook fields removed
        item = dynamodb.get_item(Key={"PK": f"USER#{user_id}", "SK": "META"})["Item"]
        assert float(item["trust_score"]) == 0.0
        assert "moltbook_verified" not in item
        assert "moltbook_name" not in item

    def test_not_linked_error(self, dynamodb, sample_user):
        from handlers.moltbook import moltbook_unlink

        _, raw_key = sample_user
        event = make_api_event(
            method="POST",
            path="/moltbook/unlink",
            api_key=raw_key,
        )
        resp = moltbook_unlink(event, None)

        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "not_linked"

    def test_unauthenticated(self, dynamodb):
        from handlers.moltbook import moltbook_unlink

        event = make_api_event(
            method="POST",
            path="/moltbook/unlink",
        )
        resp = moltbook_unlink(event, None)
        assert resp["statusCode"] == 401


# ---------------------------------------------------------------------------
# 5. Integration tests for get_me showing Moltbook data
# ---------------------------------------------------------------------------


class TestGetMeWithMoltbook:
    """get_me should include Moltbook data when linked."""

    def test_get_me_shows_moltbook_when_linked(self, dynamodb, sample_user):
        from handlers.auth import get_me

        user_id, raw_key = sample_user

        # Directly set moltbook fields in DB (link_moltbook is deprecated)
        dynamodb.update_item(
            Key={"PK": f"USER#{user_id}", "SK": "META"},
            UpdateExpression=(
                "SET moltbook_verified = :mv, moltbook_name = :mn, "
                "moltbook_karma = :mk, moltbook_verified_at = :mvat, "
                "trust_score = :ts, trust_breakdown = :tb"
            ),
            ExpressionAttributeValues={
                ":mv": True,
                ":mn": "visible-agent",
                ":mk": 200,
                ":mvat": "2025-01-01T00:00:00+00:00",
                ":ts": Decimal("0.8"),
                ":tb": {
                    "karma": Decimal("0.4"),
                    "account_age": Decimal("0.3"),
                    "verification": Decimal("0.3"),
                },
            },
        )

        # Now call get_me
        me_event = make_api_event(method="GET", path="/auth/me", api_key=raw_key)
        resp = get_me(me_event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["moltbook_linked"] is True
        assert body["moltbook_name"] == "visible-agent"
        assert body["moltbook_karma"] == 200
        assert "moltbook_verified_at" in body
        assert "trust_breakdown" in body
        assert body["trust_score"] > 0

    def test_get_me_shows_not_linked(self, dynamodb, sample_user):
        from handlers.auth import get_me

        _, raw_key = sample_user
        event = make_api_event(method="GET", path="/auth/me", api_key=raw_key)
        resp = get_me(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["moltbook_linked"] is False
        assert "moltbook_name" not in body
        assert "moltbook_karma" not in body


# ---------------------------------------------------------------------------
# 6. Tests for anti-gaming account age verification
# ---------------------------------------------------------------------------


class TestAntiGaming:
    """Tests for anti-gaming measures in Moltbook verification."""

    @patch("handlers.moltbook.fetch_trust_metrics")
    def test_account_too_new_rejected(self, mock_fetch, dynamodb, sample_user):
        """Account less than 7 days old should be rejected."""
        from handlers.moltbook import moltbook_verify_confirm

        user_id, raw_key = sample_user

        # Clean up any existing challenge and moltbook verification
        try:
            dynamodb.delete_item(
                Key={"PK": f"USER#{user_id}", "SK": "MOLTBOOK_CHALLENGE"}
            )
        except:
            pass  # Ignore if doesn't exist

        # Remove any existing moltbook verification
        try:
            dynamodb.update_item(
                Key={"PK": f"USER#{user_id}", "SK": "META"},
                UpdateExpression=(
                    "REMOVE moltbook_name, moltbook_verified, moltbook_verified_at, "
                    "moltbook_karma, moltbook_account_age, moltbook_has_owner"
                ),
            )
        except:
            pass  # Ignore if fields don't exist

        # Set up a pending challenge
        now = datetime.now(timezone.utc)

        dynamodb.put_item(
            Item={
                "PK": f"USER#{user_id}",
                "SK": "MOLTBOOK_CHALLENGE",
                "challenge_code": "agentpier-verify-test123",
                "moltbook_username": "new-agent",
                "created_at": now.isoformat(),
                "expires_at": str(int(now.timestamp()) + 1800),
            }
        )

        # Mock Moltbook profile with account created 3 days ago
        three_days_ago = (now - timedelta(days=3)).isoformat()
        mock_fetch.return_value = {
            "agent": {
                "name": "new-agent",
                "description": "agentpier-verify-test123",  # Challenge code present
                "karma": 100,
                "created_at": three_days_ago,
                "is_claimed": True,
                "owner": "owner123",
            }
        }

        event = make_api_event(
            method="POST",
            path="/moltbook/verify/confirm",
            api_key=raw_key,
        )

        resp = moltbook_verify_confirm(event, None)

        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "account_too_new"
        assert "7 days old" in body["message"]

    @patch("handlers.moltbook.fetch_trust_metrics")
    def test_account_exactly_seven_days_accepted(
        self, mock_fetch, dynamodb, sample_user
    ):
        """Account exactly 7 days old should be accepted."""
        from handlers.moltbook import moltbook_verify_confirm

        user_id, raw_key = sample_user

        # Clean up any existing challenge and moltbook verification
        try:
            dynamodb.delete_item(
                Key={"PK": f"USER#{user_id}", "SK": "MOLTBOOK_CHALLENGE"}
            )
        except:
            pass  # Ignore if doesn't exist

        # Remove any existing moltbook verification
        try:
            dynamodb.update_item(
                Key={"PK": f"USER#{user_id}", "SK": "META"},
                UpdateExpression=(
                    "REMOVE moltbook_name, moltbook_verified, moltbook_verified_at, "
                    "moltbook_karma, moltbook_account_age, moltbook_has_owner"
                ),
            )
        except:
            pass  # Ignore if fields don't exist

        # Set up a pending challenge
        now = datetime.now(timezone.utc)

        dynamodb.put_item(
            Item={
                "PK": f"USER#{user_id}",
                "SK": "MOLTBOOK_CHALLENGE",
                "challenge_code": "agentpier-verify-test456",
                "moltbook_username": "seven-day-agent",
                "created_at": now.isoformat(),
                "expires_at": str(int(now.timestamp()) + 1800),
            }
        )

        # Mock Moltbook profile with account created exactly 7 days ago
        seven_days_ago = (now - timedelta(days=7)).isoformat()
        mock_fetch.return_value = {
            "agent": {
                "name": "seven-day-agent",
                "description": "agentpier-verify-test456",  # Challenge code present
                "karma": 100,
                "created_at": seven_days_ago,
                "is_claimed": True,
                "owner": "owner123",
                "follower_count": 10,
                "posts_count": 5,
                "comments_count": 20,
                "is_active": True,
            }
        }

        event = make_api_event(
            method="POST",
            path="/moltbook/verify/confirm",
            api_key=raw_key,
        )

        resp = moltbook_verify_confirm(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["verified"] is True
        assert body["moltbook_username"] == "seven-day-agent"

    @patch("handlers.moltbook.fetch_trust_metrics")
    def test_account_old_enough_accepted(self, mock_fetch, dynamodb, sample_user):
        """Account older than 7 days should be accepted."""
        from handlers.moltbook import moltbook_verify_confirm

        user_id, raw_key = sample_user

        # Clean up any existing challenge and moltbook verification
        try:
            dynamodb.delete_item(
                Key={"PK": f"USER#{user_id}", "SK": "MOLTBOOK_CHALLENGE"}
            )
        except:
            pass  # Ignore if doesn't exist

        # Remove any existing moltbook verification
        try:
            dynamodb.update_item(
                Key={"PK": f"USER#{user_id}", "SK": "META"},
                UpdateExpression=(
                    "REMOVE moltbook_name, moltbook_verified, moltbook_verified_at, "
                    "moltbook_karma, moltbook_account_age, moltbook_has_owner"
                ),
            )
        except:
            pass  # Ignore if fields don't exist

        # Set up a pending challenge
        now = datetime.now(timezone.utc)

        dynamodb.put_item(
            Item={
                "PK": f"USER#{user_id}",
                "SK": "MOLTBOOK_CHALLENGE",
                "challenge_code": "agentpier-verify-test789",
                "moltbook_username": "old-agent",
                "created_at": now.isoformat(),
                "expires_at": str(int(now.timestamp()) + 1800),
            }
        )

        # Mock Moltbook profile with account created 30 days ago
        thirty_days_ago = (now - timedelta(days=30)).isoformat()
        mock_fetch.return_value = {
            "agent": {
                "name": "old-agent",
                "description": "agentpier-verify-test789",  # Challenge code present
                "karma": 500,
                "created_at": thirty_days_ago,
                "is_claimed": True,
                "owner": "owner456",
                "follower_count": 50,
                "posts_count": 25,
                "comments_count": 100,
                "is_active": True,
            }
        }

        event = make_api_event(
            method="POST",
            path="/moltbook/verify/confirm",
            api_key=raw_key,
        )

        resp = moltbook_verify_confirm(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["verified"] is True
        assert body["moltbook_username"] == "old-agent"
