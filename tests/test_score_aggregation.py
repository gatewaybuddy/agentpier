"""Tests for cross-platform score aggregation engine (Issue #42).

Tests the clearinghouse scoring function and new trust endpoints.
"""

import json
import math
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.ace_scoring import (
    calculate_clearinghouse_score,
    get_trust_tier,
    CH_BASE_SCORE,
    CH_CROSS_PLATFORM_BONUS_MAX,
    CH_CROSS_PLATFORM_BONUS_THRESHOLD,
    CH_INCIDENT_PENALTY_MULTIPLIER,
    _calculate_reliability,
    _calculate_safety,
    _calculate_capability,
    _calculate_transparency,
    _calculate_confidence,
    _get_marketplace_weight,
)
from utils.score_response import sanitize_score_response

# make_api_event is in conftest.py — import by adding tests dir to path
_tests_dir = os.path.dirname(__file__)
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)
from conftest import make_api_event


# === Helpers ===

def _now():
    return datetime.now(timezone.utc)


def _signal(signal_type, outcome, marketplace_id="mp_alpha", agent_id="agent-1",
            days_ago=0, metrics=None, transaction_ref=None):
    """Create a test signal dict."""
    ts = (_now() - timedelta(days=days_ago)).isoformat()
    s = {
        "PK": f"SIGNAL#{marketplace_id}#{agent_id}",
        "SK": f"TS#{ts}#abc123",
        "signal_id": "sig-" + os.urandom(4).hex(),
        "marketplace_id": marketplace_id,
        "agent_id": agent_id,
        "signal_type": signal_type,
        "outcome": outcome,
        "timestamp": ts,
        "received_at": ts,
        "GSI1PK": f"AGENT_SIGNALS#{agent_id}",
        "GSI1SK": f"TS#{ts}#abc123",
    }
    if metrics:
        s["metrics"] = metrics
    if transaction_ref:
        s["transaction_ref"] = transaction_ref
    return s


# === Confidence Score Tests ===

class TestConfidenceScore:
    def test_low_signal_count(self):
        assert _calculate_confidence(0) == 0.20
        assert _calculate_confidence(5) == 0.20
        assert _calculate_confidence(9) == 0.20

    def test_medium_signal_count(self):
        assert _calculate_confidence(10) == 0.50
        assert _calculate_confidence(30) == 0.50
        assert _calculate_confidence(49) == 0.50

    def test_good_signal_count(self):
        assert _calculate_confidence(50) == 0.80
        assert _calculate_confidence(100) == 0.80
        assert _calculate_confidence(199) == 0.80

    def test_high_signal_count(self):
        assert _calculate_confidence(200) == 0.95
        assert _calculate_confidence(500) == 0.95
        assert _calculate_confidence(10000) == 0.95


# === Marketplace Weight Tests ===

class TestMarketplaceWeight:
    def test_unscored_marketplace_default(self):
        assert _get_marketplace_weight("unknown", {}) == 1.0

    def test_high_score_marketplace(self):
        weight = _get_marketplace_weight("good_mp", {"good_mp": 90})
        assert weight > 1.0  # 90/50 = 1.8

    def test_low_score_marketplace(self):
        weight = _get_marketplace_weight("bad_mp", {"bad_mp": 20})
        assert weight < 1.0  # 20/50 = 0.4

    def test_weight_clamped(self):
        # Very high score
        weight = _get_marketplace_weight("max_mp", {"max_mp": 200})
        assert weight == 2.0
        # Very low score
        weight = _get_marketplace_weight("min_mp", {"min_mp": 1})
        assert weight >= 0.1


# === Reliability Dimension Tests ===

class TestReliabilityDimension:
    def test_no_signals_returns_base(self):
        assert _calculate_reliability([], {}) == CH_BASE_SCORE

    def test_all_completions_high_score(self):
        signals = [_signal("transaction_outcome", "completed") for _ in range(10)]
        score = _calculate_reliability(signals, {})
        assert score >= 80

    def test_all_failures_low_score(self):
        signals = [_signal("transaction_outcome", "failed") for _ in range(10)]
        score = _calculate_reliability(signals, {})
        assert score < 20

    def test_mixed_outcomes(self):
        signals = (
            [_signal("transaction_outcome", "completed") for _ in range(7)] +
            [_signal("transaction_outcome", "failed") for _ in range(3)]
        )
        score = _calculate_reliability(signals, {})
        assert 20 < score < 80

    def test_refund_partial_penalty(self):
        """Refunds should be less severe than failures."""
        base = [_signal("transaction_outcome", "completed") for _ in range(10)]
        fail_signals = base + [_signal("transaction_outcome", "failed") for _ in range(3)]
        refund_signals = base + [_signal("transaction_outcome", "refunded") for _ in range(3)]
        fail_score = _calculate_reliability(fail_signals, {})
        refund_score = _calculate_reliability(refund_signals, {})
        assert refund_score > fail_score

    def test_non_outcome_signals_ignored(self):
        signals = [_signal("user_feedback", "completed", metrics={"user_rating": 5})]
        score = _calculate_reliability(signals, {})
        assert score == CH_BASE_SCORE  # only transaction_outcome matters


# === Safety Dimension Tests ===

class TestSafetyDimension:
    def test_no_signals_high_baseline(self):
        score = _calculate_safety([], {})
        assert score >= 70

    def test_clean_record_bonus(self):
        """Many non-incident signals should increase safety above baseline."""
        signals = [_signal("transaction_outcome", "completed") for _ in range(50)]
        score = _calculate_safety(signals, {})
        assert score > 80

    def test_incident_massive_penalty(self):
        """A single incident should cause significant drop."""
        clean_signals = [_signal("transaction_outcome", "completed") for _ in range(10)]
        clean_score = _calculate_safety(clean_signals, {})

        incident_signals = clean_signals + [_signal("incident", "security")]
        incident_score = _calculate_safety(incident_signals, {})
        assert incident_score < clean_score
        # Asymmetric: big drop
        assert clean_score - incident_score > 15

    def test_data_breach_worst_severity(self):
        """Data breaches should be penalized more than other incidents."""
        security = _calculate_safety([_signal("incident", "security")], {})
        breach = _calculate_safety([_signal("incident", "data_breach")], {})
        assert breach < security

    def test_incident_near_permanent_decay(self):
        """Incidents should persist much longer than normal signals."""
        recent_incident = [_signal("incident", "security", days_ago=1)]
        old_incident = [_signal("incident", "security", days_ago=100)]
        recent_score = _calculate_safety(recent_incident, {})
        old_score = _calculate_safety(old_incident, {})
        # Old incident should still hurt significantly (near-permanent decay)
        assert old_score < 80
        # But slightly less than recent
        assert old_score > recent_score or abs(old_score - recent_score) < 5

    def test_asymmetric_failure_penalty(self):
        """Incidents should hurt 4x more than clean record helps."""
        # Many clean signals
        many_clean = [_signal("transaction_outcome", "completed") for _ in range(50)]
        clean_score = _calculate_safety(many_clean, {})

        # One incident among many clean signals
        one_incident = many_clean + [_signal("incident", "safety")]
        incident_score = _calculate_safety(one_incident, {})

        # The single incident should cause a disproportionate drop
        assert clean_score - incident_score > 10


# === Capability Dimension Tests ===

class TestCapabilityDimension:
    def test_no_signals_returns_base(self):
        assert _calculate_capability([], {}) == CH_BASE_SCORE

    def test_high_ratings_high_score(self):
        signals = [_signal("user_feedback", "completed",
                           metrics={"user_rating": 5}) for _ in range(10)]
        score = _calculate_capability(signals, {})
        assert score >= 90

    def test_low_ratings_low_score(self):
        signals = [_signal("user_feedback", "completed",
                           metrics={"user_rating": 1}) for _ in range(10)]
        score = _calculate_capability(signals, {})
        assert score < 10

    def test_mixed_ratings(self):
        signals = (
            [_signal("user_feedback", "completed", metrics={"user_rating": 5}) for _ in range(5)] +
            [_signal("user_feedback", "completed", metrics={"user_rating": 2}) for _ in range(5)]
        )
        score = _calculate_capability(signals, {})
        assert 30 < score < 80

    def test_fast_completion_bonus(self):
        """Fast completion times should provide a small bonus."""
        fast_signals = [_signal("user_feedback", "completed",
                                metrics={"user_rating": 4, "completion_time_ms": 500})
                        for _ in range(10)]
        slow_signals = [_signal("user_feedback", "completed",
                                metrics={"user_rating": 4, "completion_time_ms": 15000})
                        for _ in range(10)]
        fast_score = _calculate_capability(fast_signals, {})
        slow_score = _calculate_capability(slow_signals, {})
        assert fast_score > slow_score

    def test_non_feedback_signals_ignored(self):
        signals = [_signal("transaction_outcome", "completed") for _ in range(10)]
        score = _calculate_capability(signals, {})
        assert score == CH_BASE_SCORE


# === Transparency Dimension Tests ===

class TestTransparencyDimension:
    def test_no_signals_returns_base(self):
        assert _calculate_transparency([], {}) == CH_BASE_SCORE

    def test_single_marketplace_moderate(self):
        signals = [_signal("transaction_outcome", "completed", marketplace_id="mp_one")
                   for _ in range(20)]
        score = _calculate_transparency(signals, {})
        assert 20 < score < 70  # limited by single platform

    def test_multiple_marketplaces_higher(self):
        """More marketplaces should increase transparency score."""
        single_mp = [_signal("transaction_outcome", "completed", marketplace_id="mp_one")
                     for _ in range(20)]
        multi_mp = (
            [_signal("transaction_outcome", "completed", marketplace_id="mp_one")
             for _ in range(10)] +
            [_signal("transaction_outcome", "completed", marketplace_id="mp_two")
             for _ in range(10)]
        )
        single_score = _calculate_transparency(single_mp, {})
        multi_score = _calculate_transparency(multi_mp, {})
        assert multi_score > single_score

    def test_consistent_cross_platform_bonus(self):
        """Consistent outcomes across platforms should give bonus."""
        # All platforms have 100% completion rate
        signals = []
        for mp in ["mp_a", "mp_b", "mp_c"]:
            for _ in range(10):
                signals.append(_signal("transaction_outcome", "completed", marketplace_id=mp))
        score = _calculate_transparency(signals, {})
        assert score > 60

    def test_inconsistent_cross_platform_lower(self):
        """Inconsistent outcomes across platforms should reduce bonus."""
        signals = []
        # mp_a: 100% completion
        for _ in range(10):
            signals.append(_signal("transaction_outcome", "completed", marketplace_id="mp_a"))
        # mp_b: 0% completion (all failures)
        for _ in range(10):
            signals.append(_signal("transaction_outcome", "failed", marketplace_id="mp_b"))

        score_inconsistent = _calculate_transparency(signals, {})

        # Compare with consistent
        consistent_signals = []
        for mp in ["mp_a", "mp_b"]:
            for _ in range(10):
                consistent_signals.append(
                    _signal("transaction_outcome", "completed", marketplace_id=mp))

        score_consistent = _calculate_transparency(consistent_signals, {})
        assert score_consistent > score_inconsistent


# === Composite Clearinghouse Score Tests ===

class TestClearinghouseScore:
    def test_empty_signals_returns_base_score(self):
        result = calculate_clearinghouse_score("agent-1", [], {})
        assert result["trust_score"] >= 0
        assert result["trust_score"] < 40  # low because base scores are low
        assert result["trust_tier"] in ("untrusted", "provisional")
        assert result["confidence"] == 0.20
        assert result["signal_count"] == 0
        assert result["marketplace_count"] == 0

    def test_result_structure(self):
        result = calculate_clearinghouse_score("agent-1", [], {})
        assert "trust_score" in result
        assert "trust_tier" in result
        assert "dimensions" in result
        assert "reliability" in result["dimensions"]
        assert "safety" in result["dimensions"]
        assert "capability" in result["dimensions"]
        assert "transparency" in result["dimensions"]
        assert "confidence" in result
        assert "signal_count" in result
        assert "marketplace_count" in result
        assert "last_updated" in result

    def test_score_cap_at_95(self):
        """Even perfect signals should not exceed 95."""
        signals = []
        for mp in ["mp_a", "mp_b", "mp_c", "mp_d"]:
            for _ in range(100):
                signals.append(_signal("transaction_outcome", "completed", marketplace_id=mp))
                signals.append(_signal("user_feedback", "completed", marketplace_id=mp,
                                       metrics={"user_rating": 5, "completion_time_ms": 100}))
        result = calculate_clearinghouse_score("agent-1", signals, {})
        assert result["trust_score"] <= 95

    def test_single_marketplace_single_type(self):
        """Single marketplace with one signal type."""
        signals = [_signal("transaction_outcome", "completed", marketplace_id="mp_one")
                   for _ in range(20)]
        result = calculate_clearinghouse_score("agent-1", signals, {})
        assert result["trust_score"] > 20
        assert result["marketplace_count"] == 1
        assert result["signal_count"] == 20

    def test_multiple_marketplaces_mixed_types(self):
        """Multiple marketplaces with mixed signal types."""
        signals = (
            [_signal("transaction_outcome", "completed", marketplace_id="mp_a")
             for _ in range(10)] +
            [_signal("user_feedback", "completed", marketplace_id="mp_b",
                     metrics={"user_rating": 4}) for _ in range(10)] +
            [_signal("transaction_outcome", "completed", marketplace_id="mp_c")
             for _ in range(10)]
        )
        result = calculate_clearinghouse_score("agent-1", signals, {})
        assert result["marketplace_count"] == 3
        assert result["signal_count"] == 30
        assert result["trust_score"] > 20

    def test_source_weighting_higher_marketplace(self):
        """Signals from higher-scored marketplaces should carry more weight."""
        marketplace_scores = {"trusted_mp": 90, "sketchy_mp": 10}

        # Identical failures from different marketplaces
        trusted_failure = [_signal("transaction_outcome", "failed", marketplace_id="trusted_mp")
                           for _ in range(5)]
        sketchy_failure = [_signal("transaction_outcome", "failed", marketplace_id="sketchy_mp")
                           for _ in range(5)]

        # Good signals from the other
        base_signals = [_signal("transaction_outcome", "completed", marketplace_id="neutral_mp")
                        for _ in range(20)]

        score_trusted_fail = calculate_clearinghouse_score(
            "agent-1", base_signals + trusted_failure, marketplace_scores
        )["trust_score"]
        score_sketchy_fail = calculate_clearinghouse_score(
            "agent-1", base_signals + sketchy_failure, marketplace_scores
        )["trust_score"]

        # Failures from trusted marketplace should hurt more
        assert score_trusted_fail < score_sketchy_fail

    def test_cross_platform_bonus_3_plus(self):
        """Agents on 3+ platforms with consistent scores get bonus."""
        # 2 marketplaces (no bonus)
        two_mp_signals = []
        for mp in ["mp_a", "mp_b"]:
            for _ in range(15):
                two_mp_signals.append(
                    _signal("transaction_outcome", "completed", marketplace_id=mp))

        # 3 marketplaces (bonus eligible)
        three_mp_signals = []
        for mp in ["mp_a", "mp_b", "mp_c"]:
            for _ in range(10):
                three_mp_signals.append(
                    _signal("transaction_outcome", "completed", marketplace_id=mp))

        score_two = calculate_clearinghouse_score(
            "agent-1", two_mp_signals, {}
        )["trust_score"]
        score_three = calculate_clearinghouse_score(
            "agent-1", three_mp_signals, {}
        )["trust_score"]

        # Three marketplace score should be higher (bonus + transparency)
        assert score_three > score_two

    def test_temporal_decay_recent_weighted_higher(self):
        """Recent signals should be weighted more than old signals."""
        recent_failures = [_signal("transaction_outcome", "failed", days_ago=1)
                           for _ in range(5)]
        old_failures = [_signal("transaction_outcome", "failed", days_ago=200)
                        for _ in range(5)]

        base = [_signal("transaction_outcome", "completed") for _ in range(10)]

        score_recent = calculate_clearinghouse_score(
            "agent-1", base + recent_failures, {}
        )["trust_score"]
        score_old = calculate_clearinghouse_score(
            "agent-1", base + old_failures, {}
        )["trust_score"]

        # Old failures should hurt less
        assert score_old > score_recent

    def test_confidence_reflects_signal_volume(self):
        """Confidence should increase with more signals."""
        few = [_signal("transaction_outcome", "completed") for _ in range(5)]
        many = [_signal("transaction_outcome", "completed") for _ in range(100)]
        lots = [_signal("transaction_outcome", "completed") for _ in range(250)]

        result_few = calculate_clearinghouse_score("agent-1", few, {})
        result_many = calculate_clearinghouse_score("agent-1", many, {})
        result_lots = calculate_clearinghouse_score("agent-1", lots, {})

        assert result_few["confidence"] < result_many["confidence"]
        assert result_many["confidence"] < result_lots["confidence"]

    def test_dimension_scores_all_present(self):
        signals = [_signal("transaction_outcome", "completed") for _ in range(10)]
        result = calculate_clearinghouse_score("agent-1", signals, {})
        dims = result["dimensions"]
        for dim in ("reliability", "safety", "capability", "transparency"):
            assert dim in dims
            assert 0 <= dims[dim] <= 100

    def test_last_updated_is_iso8601(self):
        result = calculate_clearinghouse_score("agent-1", [], {})
        # Should parse without error
        datetime.fromisoformat(result["last_updated"].replace("Z", "+00:00"))


# === Response Sanitization Tests ===

class TestResponseSanitization:
    def test_marketplace_fields_stripped(self):
        score_data = {
            "trust_score": 55.0,
            "trust_tier": "established",
            "dimensions": {"reliability": 60, "safety": 70, "capability": 50, "transparency": 40},
            "marketplace_breakdown": {"mp_a": 60, "mp_b": 50},
            "per_source_scores": {"mp_a": 70},
            "source_weights": {"mp_a": 1.5},
            "marketplace_id": "mp_a",
        }
        sanitized = sanitize_score_response(score_data)
        assert "marketplace_breakdown" not in sanitized
        assert "per_source_scores" not in sanitized
        assert "source_weights" not in sanitized
        assert "marketplace_id" not in sanitized
        # Public fields preserved
        assert sanitized["trust_score"] == 55.0
        assert sanitized["trust_tier"] == "established"
        assert sanitized["dimensions"]["reliability"] == 60

    def test_no_marketplace_source_in_output(self):
        """Clearinghouse score response should contain no marketplace identifying info."""
        signals = [
            _signal("transaction_outcome", "completed", marketplace_id="secret_mp_1"),
            _signal("transaction_outcome", "completed", marketplace_id="secret_mp_2"),
        ]
        result = calculate_clearinghouse_score("agent-1", signals, {})
        sanitized = sanitize_score_response(result)

        # Check no marketplace info leaked
        result_str = json.dumps(sanitized)
        assert "secret_mp_1" not in result_str
        assert "secret_mp_2" not in result_str
        assert "marketplace_id" not in result_str

    def test_nested_private_fields_stripped(self):
        score_data = {
            "trust_score": 50.0,
            "dimensions": {
                "reliability": 60,
                "marketplace_contributions": {"mp_a": 30},
            },
        }
        sanitized = sanitize_score_response(score_data)
        assert "marketplace_contributions" not in sanitized.get("dimensions", {})


# === Handler Integration Tests ===

class TestClearinghouseScoreEndpoint:
    def test_agent_not_found(self, dynamodb):
        from handlers.trust import trust_clearinghouse_score
        event = make_api_event(
            method="GET",
            path="/trust/agents/nonexistent/clearinghouse-score",
            path_params={"agent_id": "nonexistent"},
        )
        response = trust_clearinghouse_score(event, None)
        assert response["statusCode"] == 404

    def test_returns_score_for_existing_agent(self, dynamodb):
        from handlers.trust import trust_clearinghouse_score

        agent_id = "test-agent-42"
        # Create agent profile
        dynamodb.put_item(Item={
            "PK": f"AGENT#{agent_id}",
            "SK": "PROFILE",
            "agent_id": agent_id,
            "agent_name": "Test Agent",
            "trust_score": "0",
            "trust_tier": "untrusted",
        })

        event = make_api_event(
            method="GET",
            path=f"/trust/agents/{agent_id}/clearinghouse-score",
            path_params={"agent_id": agent_id},
        )
        response = trust_clearinghouse_score(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "trust_score" in body
        assert "dimensions" in body
        assert "confidence" in body
        assert "marketplace_id" not in body

    def test_missing_agent_id(self, dynamodb):
        from handlers.trust import trust_clearinghouse_score
        event = make_api_event(
            method="GET",
            path="/trust/agents//clearinghouse-score",
            path_params={"agent_id": ""},
        )
        response = trust_clearinghouse_score(event, None)
        assert response["statusCode"] == 400

    def test_user_profile_also_works(self, dynamodb):
        """Should find agents stored as USER# records too."""
        from handlers.trust import trust_clearinghouse_score

        user_id = "user-agent-42"
        dynamodb.put_item(Item={
            "PK": f"USER#{user_id}",
            "SK": "META",
            "user_id": user_id,
            "username": "test_user",
            "trust_score": Decimal("0.5"),
        })

        event = make_api_event(
            method="GET",
            path=f"/trust/agents/{user_id}/clearinghouse-score",
            path_params={"agent_id": user_id},
        )
        response = trust_clearinghouse_score(event, None)
        assert response["statusCode"] == 200


class TestRecalculateEndpoint:
    def test_agent_not_found(self, dynamodb):
        from handlers.trust import trust_recalculate
        event = make_api_event(
            method="POST",
            path="/trust/agents/nonexistent/recalculate",
            path_params={"agent_id": "nonexistent"},
        )
        response = trust_recalculate(event, None)
        assert response["statusCode"] == 404

    def test_recalculate_updates_profile(self, dynamodb):
        from handlers.trust import trust_recalculate

        agent_id = "recalc-agent"
        dynamodb.put_item(Item={
            "PK": f"AGENT#{agent_id}",
            "SK": "PROFILE",
            "agent_id": agent_id,
            "agent_name": "Recalc Agent",
            "trust_score": "0",
            "trust_tier": "untrusted",
        })

        # Add some signals
        now = datetime.now(timezone.utc).isoformat()
        for i in range(5):
            dynamodb.put_item(Item={
                "PK": f"SIGNAL#mp_test#{agent_id}",
                "SK": f"TS#{now}#sig{i}",
                "signal_id": f"sig{i}",
                "marketplace_id": "mp_test",
                "agent_id": agent_id,
                "signal_type": "transaction_outcome",
                "outcome": "completed",
                "timestamp": now,
                "GSI1PK": f"AGENT_SIGNALS#{agent_id}",
                "GSI1SK": f"TS#{now}#sig{i}",
            })

        event = make_api_event(
            method="POST",
            path=f"/trust/agents/{agent_id}/recalculate",
            path_params={"agent_id": agent_id},
        )
        response = trust_recalculate(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "trust_score" in body
        assert "dimensions" in body

        # Verify profile was updated in DynamoDB
        profile = dynamodb.get_item(
            Key={"PK": f"AGENT#{agent_id}", "SK": "PROFILE"}
        )["Item"]
        assert float(profile["trust_score"]) >= 0
        assert profile.get("last_scored_at") is not None
        assert profile.get("clearinghouse_dimensions") is not None

    def test_missing_agent_id(self, dynamodb):
        from handlers.trust import trust_recalculate
        event = make_api_event(
            method="POST",
            path="/trust/agents//recalculate",
            path_params={"agent_id": ""},
        )
        response = trust_recalculate(event, None)
        assert response["statusCode"] == 400

    def test_recalculate_with_user_profile(self, dynamodb):
        """Should work for USER# records too."""
        from handlers.trust import trust_recalculate

        user_id = "recalc-user"
        dynamodb.put_item(Item={
            "PK": f"USER#{user_id}",
            "SK": "META",
            "user_id": user_id,
            "username": "recalc_test",
            "trust_score": Decimal("0"),
        })

        event = make_api_event(
            method="POST",
            path=f"/trust/agents/{user_id}/recalculate",
            path_params={"agent_id": user_id},
        )
        response = trust_recalculate(event, None)
        assert response["statusCode"] == 200
