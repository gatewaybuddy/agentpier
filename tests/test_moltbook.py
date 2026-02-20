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
    """Mock HTTP responses for Moltbook API calls."""

    @patch("utils.moltbook.urlopen")
    def test_success(self, mock_urlopen):
        from utils.moltbook import verify_moltbook_key

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"agent": {"name": "testbot"}}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = verify_moltbook_key("valid-key-123")
        assert result["agent"]["name"] == "testbot"
        # Check auth header was set
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.get_header("Authorization") == "Bearer valid-key-123"

    @patch("utils.moltbook.urlopen")
    def test_invalid_key_401(self, mock_urlopen):
        from utils.moltbook import verify_moltbook_key, MoltbookAuthError

        mock_urlopen.side_effect = HTTPError(
            url="https://www.moltbook.com/api/v1/agents/me",
            code=401, msg="Unauthorized", hdrs={}, fp=None,
        )
        with pytest.raises(MoltbookAuthError, match="Invalid Moltbook API key"):
            verify_moltbook_key("bad-key")

    @patch("utils.moltbook.urlopen")
    def test_not_found_404(self, mock_urlopen):
        from utils.moltbook import verify_moltbook_key, MoltbookNotFoundError

        mock_urlopen.side_effect = HTTPError(
            url="https://www.moltbook.com/api/v1/agents/me",
            code=404, msg="Not Found", hdrs={}, fp=None,
        )
        with pytest.raises(MoltbookNotFoundError):
            verify_moltbook_key("some-key")

    @patch("utils.moltbook.urlopen")
    def test_rate_limited_429(self, mock_urlopen):
        from utils.moltbook import verify_moltbook_key, MoltbookRateLimitError

        mock_urlopen.side_effect = HTTPError(
            url="https://www.moltbook.com/api/v1/agents/me",
            code=429, msg="Too Many Requests", hdrs={}, fp=None,
        )
        with pytest.raises(MoltbookRateLimitError):
            verify_moltbook_key("some-key")

    @patch("utils.moltbook.urlopen")
    def test_timeout(self, mock_urlopen):
        from utils.moltbook import verify_moltbook_key, MoltbookAPIError

        mock_urlopen.side_effect = URLError("timed out")
        with pytest.raises(MoltbookAPIError, match="unreachable"):
            verify_moltbook_key("some-key")


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
            code=404, msg="Not Found", hdrs={}, fp=None,
        )
        with pytest.raises(MoltbookNotFoundError):
            fetch_trust_metrics("nonexistent-agent")

    @patch("utils.moltbook.urlopen")
    def test_server_error(self, mock_urlopen):
        from utils.moltbook import fetch_trust_metrics, MoltbookAPIError

        mock_urlopen.side_effect = HTTPError(
            url="https://www.moltbook.com/api/v1/agents/profile",
            code=500, msg="Internal Server Error", hdrs={}, fp=None,
        )
        with pytest.raises(MoltbookAPIError, match="500"):
            fetch_trust_metrics("some-agent")


# ---------------------------------------------------------------------------
# 3. Integration tests for link_moltbook handler
# ---------------------------------------------------------------------------

class TestLinkMoltbook:
    """Integration tests: link_moltbook handler with moto DynamoDB."""

    @patch("handlers.auth.verify_moltbook_key")
    def test_successful_link(self, mock_verify, dynamodb, sample_user):
        from handlers.auth import link_moltbook

        user_id, raw_key = sample_user
        created_90d_ago = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()

        mock_verify.return_value = {
            "agent": {
                "name": "my-moltbook-agent",
                "karma": 500,
                "created_at": created_90d_ago,
                "is_claimed": True,
                "owner": "owner-123",
            }
        }

        event = make_api_event(
            method="POST", path="/auth/link-moltbook",
            body={"moltbook_api_key": "mb_key_abc"},
            api_key=raw_key,
        )
        resp = link_moltbook(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["linked"] is True
        assert body["moltbook_name"] == "my-moltbook-agent"
        assert body["trust_score"] == 1.0

        # Verify DynamoDB was updated
        item = dynamodb.get_item(
            Key={"PK": f"USER#{user_id}", "SK": "META"}
        )["Item"]
        assert item["moltbook_verified"] is True
        assert item["moltbook_name"] == "my-moltbook-agent"
        assert float(item["trust_score"]) == 1.0

    @patch("handlers.auth.verify_moltbook_key")
    def test_invalid_moltbook_key(self, mock_verify, dynamodb, sample_user):
        from handlers.auth import link_moltbook
        from utils.moltbook import MoltbookAuthError

        _, raw_key = sample_user
        mock_verify.side_effect = MoltbookAuthError("Invalid Moltbook API key")

        event = make_api_event(
            method="POST", path="/auth/link-moltbook",
            body={"moltbook_api_key": "bad_key"},
            api_key=raw_key,
        )
        resp = link_moltbook(event, None)

        assert resp["statusCode"] == 401
        body = json.loads(resp["body"])
        assert body["error"] == "invalid_moltbook_key"

    @patch("handlers.auth.verify_moltbook_key")
    def test_already_linked_409(self, mock_verify, dynamodb, sample_user):
        from handlers.auth import link_moltbook

        user_id, raw_key = sample_user

        # Pre-set moltbook_verified on the user record
        dynamodb.update_item(
            Key={"PK": f"USER#{user_id}", "SK": "META"},
            UpdateExpression="SET moltbook_verified = :mv, moltbook_name = :mn",
            ExpressionAttributeValues={":mv": True, ":mn": "already-linked"},
        )

        event = make_api_event(
            method="POST", path="/auth/link-moltbook",
            body={"moltbook_api_key": "mb_key_abc"},
            api_key=raw_key,
        )
        resp = link_moltbook(event, None)

        assert resp["statusCode"] == 409
        body = json.loads(resp["body"])
        assert body["error"] == "already_linked"
        # verify_moltbook_key should never be called
        mock_verify.assert_not_called()

    @patch("handlers.auth.verify_moltbook_key")
    def test_moltbook_api_down_502(self, mock_verify, dynamodb, sample_user):
        from handlers.auth import link_moltbook
        from utils.moltbook import MoltbookAPIError

        _, raw_key = sample_user
        mock_verify.side_effect = MoltbookAPIError("Moltbook API unreachable: timed out")

        event = make_api_event(
            method="POST", path="/auth/link-moltbook",
            body={"moltbook_api_key": "mb_key_abc"},
            api_key=raw_key,
        )
        resp = link_moltbook(event, None)

        assert resp["statusCode"] == 502
        body = json.loads(resp["body"])
        assert body["error"] == "moltbook_unavailable"

    def test_missing_moltbook_key_field(self, dynamodb, sample_user):
        from handlers.auth import link_moltbook

        _, raw_key = sample_user
        event = make_api_event(
            method="POST", path="/auth/link-moltbook",
            body={},
            api_key=raw_key,
        )
        resp = link_moltbook(event, None)

        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "missing_field"

    def test_unauthenticated(self, dynamodb):
        from handlers.auth import link_moltbook

        event = make_api_event(
            method="POST", path="/auth/link-moltbook",
            body={"moltbook_api_key": "mb_key_abc"},
        )
        resp = link_moltbook(event, None)
        assert resp["statusCode"] == 401


# ---------------------------------------------------------------------------
# 4. Integration tests for unlink_moltbook handler
# ---------------------------------------------------------------------------

class TestUnlinkMoltbook:
    """Integration tests: unlink_moltbook handler."""

    @patch("handlers.auth.verify_moltbook_key")
    def test_successful_unlink(self, mock_verify, dynamodb, sample_user):
        from handlers.auth import link_moltbook, unlink_moltbook

        user_id, raw_key = sample_user
        created_90d_ago = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()

        # First link a Moltbook account
        mock_verify.return_value = {
            "agent": {
                "name": "linked-agent",
                "karma": 300,
                "created_at": created_90d_ago,
                "is_claimed": True,
                "owner": "owner-1",
            }
        }
        link_event = make_api_event(
            method="POST", path="/auth/link-moltbook",
            body={"moltbook_api_key": "mb_key_abc"},
            api_key=raw_key,
        )
        link_resp = link_moltbook(link_event, None)
        assert link_resp["statusCode"] == 200

        # Verify trust_score > 0 after linking
        item = dynamodb.get_item(
            Key={"PK": f"USER#{user_id}", "SK": "META"}
        )["Item"]
        assert float(item["trust_score"]) > 0

        # Now unlink
        unlink_event = make_api_event(
            method="POST", path="/auth/unlink-moltbook",
            api_key=raw_key,
        )
        resp = unlink_moltbook(unlink_event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["unlinked"] is True
        assert body["trust_score"] == 0.0

        # Verify DynamoDB: trust_score reset, moltbook fields removed
        item = dynamodb.get_item(
            Key={"PK": f"USER#{user_id}", "SK": "META"}
        )["Item"]
        assert float(item["trust_score"]) == 0.0
        assert "moltbook_verified" not in item
        assert "moltbook_name" not in item

    def test_not_linked_error(self, dynamodb, sample_user):
        from handlers.auth import unlink_moltbook

        _, raw_key = sample_user
        event = make_api_event(
            method="POST", path="/auth/unlink-moltbook",
            api_key=raw_key,
        )
        resp = unlink_moltbook(event, None)

        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "not_linked"

    def test_unauthenticated(self, dynamodb):
        from handlers.auth import unlink_moltbook

        event = make_api_event(
            method="POST", path="/auth/unlink-moltbook",
        )
        resp = unlink_moltbook(event, None)
        assert resp["statusCode"] == 401


# ---------------------------------------------------------------------------
# 5. Integration tests for get_me showing Moltbook data
# ---------------------------------------------------------------------------

class TestGetMeWithMoltbook:
    """get_me should include Moltbook data when linked."""

    @patch("handlers.auth.verify_moltbook_key")
    def test_get_me_shows_moltbook_when_linked(self, mock_verify, dynamodb, sample_user):
        from handlers.auth import link_moltbook, get_me

        user_id, raw_key = sample_user
        created_60d_ago = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()

        mock_verify.return_value = {
            "agent": {
                "name": "visible-agent",
                "karma": 200,
                "created_at": created_60d_ago,
                "is_claimed": True,
                "owner": "owner-x",
            }
        }

        # Link first
        link_event = make_api_event(
            method="POST", path="/auth/link-moltbook",
            body={"moltbook_api_key": "mb_key_xyz"},
            api_key=raw_key,
        )
        link_resp = link_moltbook(link_event, None)
        assert link_resp["statusCode"] == 200

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
