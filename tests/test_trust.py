"""Tests for ACE trust scoring logic."""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal


class TestCalculateTrustScore:
    """Test the trust score calculation engine."""

    def test_new_user_baseline(self):
        """Brand new user with no history gets near-baseline score."""
        from handlers.trust import calculate_trust_score

        user = {
            "listings_count": 0,
            "transactions_completed": 0,
            "disputes": 0,
            "human_verified": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        result = calculate_trust_score(user, [])
        assert result["trust_score"] >= 0.0
        assert result["trust_score"] <= 0.2  # Only accuracy neutral + tiny maturity
        assert result["factors"]["verification_bonus"] == 0.0

    def test_verified_user_bonus(self):
        """Human-verified users get the verification bonus."""
        from handlers.trust import calculate_trust_score

        user = {
            "listings_count": 5,
            "transactions_completed": 10,
            "disputes": 0,
            "human_verified": True,
            "created_at": (datetime.now(timezone.utc) - timedelta(days=100)).isoformat(),
        }
        result = calculate_trust_score(user, [])
        assert result["factors"]["verification_bonus"] == 0.15
        assert result["trust_score"] > 0.5

    def test_high_dispute_rate_lowers_reliability(self):
        """Users with many disputes get low reliability."""
        from handlers.trust import calculate_trust_score

        user = {
            "listings_count": 10,
            "transactions_completed": 20,
            "disputes": 15,
            "human_verified": False,
            "created_at": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
        }
        result = calculate_trust_score(user, [])
        assert result["factors"]["transaction_reliability"] < 0.1

    def test_accuracy_from_events(self):
        """Accuracy factor uses trust event history."""
        from handlers.trust import calculate_trust_score

        user = {
            "listings_count": 5,
            "transactions_completed": 5,
            "disputes": 0,
            "human_verified": False,
            "created_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
        }
        events = [
            {"event_type": "listing_accurate"},
            {"event_type": "listing_accurate"},
            {"event_type": "listing_inaccurate"},
        ]
        result = calculate_trust_score(user, events)
        # 2/3 accurate = ~0.133
        assert 0.1 < result["factors"]["listing_accuracy"] < 0.15

    def test_max_score_cap(self):
        """Score never exceeds 1.0."""
        from handlers.trust import calculate_trust_score

        user = {
            "listings_count": 100,
            "transactions_completed": 100,
            "disputes": 0,
            "human_verified": True,
            "created_at": (datetime.now(timezone.utc) - timedelta(days=365)).isoformat(),
        }
        events = [{"event_type": "listing_accurate"} for _ in range(50)]
        result = calculate_trust_score(user, events)
        assert result["trust_score"] <= 1.0

    def test_maturity_caps_at_90_days(self):
        """Account maturity maxes out at 90 days."""
        from handlers.trust import calculate_trust_score

        user_90 = {
            "listings_count": 0, "transactions_completed": 0, "disputes": 0,
            "human_verified": False,
            "created_at": (datetime.now(timezone.utc) - timedelta(days=90)).isoformat(),
        }
        user_365 = {**user_90, "created_at": (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()}

        r90 = calculate_trust_score(user_90, [])
        r365 = calculate_trust_score(user_365, [])
        assert r90["factors"]["account_maturity"] == r365["factors"]["account_maturity"]
