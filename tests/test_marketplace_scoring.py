"""Tests for marketplace scoring engine (Issue #43).

Tests all 5 scoring dimensions, tier assignment, endpoint integration,
fairness anomaly detection, and flywheel integration.
"""

import json
import math
import os
import sys
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.marketplace_scoring import (
    calculate_marketplace_score,
    get_marketplace_tier,
    _score_data_quality,
    _score_reporting_volume,
    _score_fairness,
    _score_integration_health,
    _score_dispute_resolution,
    WEIGHT_DATA_QUALITY,
    WEIGHT_REPORTING_VOLUME,
    WEIGHT_FAIRNESS,
    WEIGHT_INTEGRATION_HEALTH,
    WEIGHT_DISPUTE_RESOLUTION,
)

_tests_dir = os.path.dirname(__file__)
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)
from conftest import make_api_event


# === Helpers ===

def _now():
    return datetime.now(timezone.utc)


def _signal(signal_type="transaction_outcome", outcome="completed",
            agent_id="agent-1", marketplace_id="mp_test",
            days_ago=0, hours_ago=None, metrics=None, transaction_ref=None,
            include_optional=True):
    """Create a test signal dict."""
    if hours_ago is not None:
        ts = (_now() - timedelta(hours=hours_ago)).isoformat()
    else:
        ts = (_now() - timedelta(days=days_ago)).isoformat()
    s = {
        "signal_id": "sig-" + os.urandom(4).hex(),
        "marketplace_id": marketplace_id,
        "agent_id": agent_id,
        "signal_type": signal_type,
        "outcome": outcome,
        "timestamp": ts,
        "received_at": ts,
    }
    if include_optional:
        if transaction_ref:
            s["transaction_ref"] = transaction_ref
        if metrics:
            s["metrics"] = metrics
    return s


def _audit_record(action="ingest", marketplace_id="mp_test"):
    """Create a test audit record."""
    return {
        "audit_id": os.urandom(4).hex(),
        "accessor_id": marketplace_id,
        "accessor_type": "marketplace",
        "marketplace_id": marketplace_id,
        "action": action,
        "timestamp": _now().isoformat(),
    }


def _profile(signal_count=0, last_signal_at=None):
    """Create a test marketplace profile."""
    return {
        "marketplace_id": "mp_test",
        "name": "Test Marketplace",
        "signal_count": signal_count,
        "last_signal_at": last_signal_at,
        "tier": "registered",
        "marketplace_score": Decimal("0"),
    }


# === Tier Assignment Tests ===

class TestMarketplaceTier:
    def test_registered_tier(self):
        assert get_marketplace_tier(0) == "registered"
        assert get_marketplace_tier(10) == "registered"
        assert get_marketplace_tier(19) == "registered"

    def test_verified_tier(self):
        assert get_marketplace_tier(20) == "verified"
        assert get_marketplace_tier(30) == "verified"
        assert get_marketplace_tier(39) == "verified"

    def test_trusted_tier(self):
        assert get_marketplace_tier(40) == "trusted"
        assert get_marketplace_tier(50) == "trusted"
        assert get_marketplace_tier(59) == "trusted"

    def test_certified_tier(self):
        assert get_marketplace_tier(60) == "certified"
        assert get_marketplace_tier(70) == "certified"
        assert get_marketplace_tier(79) == "certified"

    def test_enterprise_tier(self):
        assert get_marketplace_tier(80) == "enterprise"
        assert get_marketplace_tier(90) == "enterprise"
        assert get_marketplace_tier(100) == "enterprise"

    def test_clamped_values(self):
        assert get_marketplace_tier(-5) == "registered"
        assert get_marketplace_tier(150) == "enterprise"


# === Data Quality Dimension Tests ===

class TestDataQuality:
    def test_no_signals_returns_zero(self):
        assert _score_data_quality([], []) == 0.0

    def test_complete_signals_high_score(self):
        signals = [
            _signal(transaction_ref=f"tx-{i}", metrics={"user_rating": 4})
            for i in range(10)
        ]
        score = _score_data_quality(signals, [])
        assert score >= 80

    def test_incomplete_signals_lower_score(self):
        """Signals missing optional fields score lower."""
        complete = [_signal(transaction_ref=f"tx-{i}", metrics={"r": 1}) for i in range(10)]
        incomplete = [_signal(include_optional=False) for _ in range(10)]
        complete_score = _score_data_quality(complete, [])
        incomplete_score = _score_data_quality(incomplete, [])
        assert complete_score > incomplete_score

    def test_error_records_reduce_score(self):
        signals = [_signal() for _ in range(10)]
        clean_audit = [_audit_record(action="ingest") for _ in range(10)]
        error_audit = [_audit_record(action="ingest_error") for _ in range(10)]

        clean_score = _score_data_quality(signals, clean_audit)
        error_score = _score_data_quality(signals, error_audit)
        assert clean_score > error_score

    def test_invalid_timestamps_reduce_score(self):
        signals = [_signal() for _ in range(5)]
        # Add signals with invalid timestamps
        bad_signals = [{"agent_id": "a", "signal_type": "transaction_outcome",
                        "outcome": "completed", "timestamp": "not-a-date"} for _ in range(5)]
        mixed_score = _score_data_quality(signals + bad_signals, [])
        good_score = _score_data_quality(signals + [_signal() for _ in range(5)], [])
        assert good_score > mixed_score


# === Reporting Volume Dimension Tests ===

class TestReportingVolume:
    def test_zero_signals(self):
        assert _score_reporting_volume(0) == 0

    def test_ten_signals(self):
        assert _score_reporting_volume(10) == 30

    def test_hundred_signals(self):
        assert _score_reporting_volume(100) == 60

    def test_thousand_signals(self):
        assert _score_reporting_volume(1000) == 80

    def test_five_thousand_signals(self):
        assert _score_reporting_volume(5000) == 100

    def test_above_five_thousand(self):
        assert _score_reporting_volume(10000) == 100

    def test_log_scale_monotonic(self):
        """Volume score should increase monotonically at breakpoints."""
        scores = [
            _score_reporting_volume(0),
            _score_reporting_volume(10),
            _score_reporting_volume(100),
            _score_reporting_volume(1000),
            _score_reporting_volume(5000),
        ]
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1]

    def test_between_breakpoints(self):
        """Signals between breakpoints get the lower tier's score."""
        assert _score_reporting_volume(5) == 0
        assert _score_reporting_volume(50) == 30
        assert _score_reporting_volume(500) == 60
        assert _score_reporting_volume(2000) == 80


# === Fairness Dimension Tests ===

class TestFairness:
    def test_no_signals_neutral(self):
        assert _score_fairness([]) == 50.0

    def test_few_signals_neutral(self):
        signals = [_signal() for _ in range(2)]
        assert _score_fairness(signals) == 50.0

    def test_fair_outcomes_high_score(self):
        """Diverse agent outcomes with reasonable rates = high fairness."""
        signals = []
        for agent in ["agent-1", "agent-2", "agent-3"]:
            for _ in range(8):
                signals.append(_signal(agent_id=agent, outcome="completed"))
            for _ in range(2):
                signals.append(_signal(agent_id=agent, outcome="failed"))
        score = _score_fairness(signals)
        assert score >= 70

    def test_biased_failures_flagged(self):
        """One agent with disproportionate failures = lower fairness score."""
        signals = []
        # agent-1: all completions
        for _ in range(10):
            signals.append(_signal(agent_id="agent-1", outcome="completed"))
        # agent-2: all completions
        for _ in range(10):
            signals.append(_signal(agent_id="agent-2", outcome="completed"))
        # agent-3: mostly failures (disproportionate)
        for _ in range(2):
            signals.append(_signal(agent_id="agent-3", outcome="completed"))
        for _ in range(8):
            signals.append(_signal(agent_id="agent-3", outcome="failed"))

        score = _score_fairness(signals)
        assert score < 90  # penalized for bias

    def test_suspiciously_uniform_ratings_flagged(self):
        """All identical ratings = suspiciously uniform."""
        signals = [
            _signal(signal_type="user_feedback", outcome="completed",
                    metrics={"user_rating": 5})
            for _ in range(20)
        ]
        # Add some outcome signals to make total enough
        signals += [_signal(outcome="completed") for _ in range(5)]
        score = _score_fairness(signals)
        assert score < 80  # penalized for uniformity

    def test_varied_ratings_not_flagged(self):
        """Normal variation in ratings should not be penalized."""
        ratings = [3, 4, 5, 4, 3, 5, 4, 2, 5, 4]
        signals = [
            _signal(signal_type="user_feedback", outcome="completed",
                    metrics={"user_rating": r})
            for r in ratings
        ]
        signals += [_signal(outcome="completed") for _ in range(5)]
        score = _score_fairness(signals)
        assert score >= 70


# === Integration Health Dimension Tests ===

class TestIntegrationHealth:
    def test_no_signals_no_profile(self):
        score = _score_integration_health([], _profile())
        assert score == 0.0

    def test_regular_cadence_high_score(self):
        """Regular submission every hour = high integration health."""
        now = _now()
        signals = [
            _signal(hours_ago=i) for i in range(0, 48)  # every hour for 2 days
        ]
        score = _score_integration_health(signals, _profile(), now)
        assert score >= 60

    def test_bursty_cadence_lower_score(self):
        """All signals in one burst = lower score than regular cadence."""
        now = _now()
        # All signals within 1 minute
        bursty = [_signal(hours_ago=0) for _ in range(20)]
        # Regular every 6 hours over 5 days
        regular = [_signal(hours_ago=i * 6) for i in range(20)]

        bursty_score = _score_integration_health(bursty, _profile(), now)
        regular_score = _score_integration_health(regular, _profile(), now)
        assert regular_score >= bursty_score

    def test_recent_signals_better_recency(self):
        """Recent signals get better recency score."""
        now = _now()
        recent = [_signal(days_ago=0)]
        old = [_signal(days_ago=100)]

        recent_score = _score_integration_health(recent, _profile(), now)
        old_score = _score_integration_health(old, _profile(), now)
        assert recent_score > old_score

    def test_longer_span_better_longevity(self):
        """Signals spanning more days get better longevity score."""
        now = _now()
        short_span = [_signal(days_ago=0), _signal(days_ago=1)]
        long_span = [_signal(days_ago=0), _signal(days_ago=100)]

        short_score = _score_integration_health(short_span, _profile(), now)
        long_score = _score_integration_health(long_span, _profile(), now)
        assert long_score > short_score


# === Dispute Resolution Dimension Tests ===

class TestDisputeResolution:
    def test_no_signals_neutral(self):
        assert _score_dispute_resolution([]) == 50.0

    def test_no_disputes_good(self):
        signals = [_signal(outcome="completed") for _ in range(10)]
        score = _score_dispute_resolution(signals)
        assert score >= 70

    def test_all_disputed_no_resolution_low(self):
        signals = [_signal(outcome="disputed", transaction_ref=f"tx-{i}")
                   for i in range(10)]
        score = _score_dispute_resolution(signals)
        assert score < 50

    def test_resolved_disputes_high_score(self):
        """Disputes that get resolved should score well."""
        signals = []
        for i in range(5):
            # Dispute followed by resolution with same transaction_ref
            signals.append(_signal(outcome="disputed", transaction_ref=f"tx-{i}", days_ago=2))
            signals.append(_signal(outcome="completed", transaction_ref=f"tx-{i}", days_ago=1))
        score = _score_dispute_resolution(signals)
        assert score >= 70

    def test_partial_resolution(self):
        """Some resolved, some not = medium score."""
        signals = []
        # 3 resolved disputes
        for i in range(3):
            signals.append(_signal(outcome="disputed", transaction_ref=f"tx-{i}", days_ago=3))
            signals.append(_signal(outcome="refunded", transaction_ref=f"tx-{i}", days_ago=1))
        # 3 unresolved disputes
        for i in range(3, 6):
            signals.append(_signal(outcome="disputed", transaction_ref=f"tx-{i}", days_ago=3))
        score = _score_dispute_resolution(signals)
        # Should be between low (all unresolved) and high (all resolved)
        assert 35 <= score < 80

    def test_high_dispute_rate_penalized(self):
        """Marketplaces with very high dispute rates get penalized."""
        signals = [_signal(outcome="disputed", transaction_ref=f"tx-{i}")
                   for i in range(8)]
        signals += [_signal(outcome="completed") for _ in range(2)]
        score = _score_dispute_resolution(signals)
        # High dispute rate (80%) should bring the score down
        assert score < 60


# === Composite Marketplace Score Tests ===

class TestCompositeScore:
    def test_empty_marketplace(self):
        result = calculate_marketplace_score("mp_test", [], [], _profile())
        assert result["marketplace_score"] >= 0
        assert result["marketplace_score"] <= 100
        assert result["marketplace_tier"] == "registered"
        assert result["signal_count"] == 0

    def test_result_structure(self):
        result = calculate_marketplace_score("mp_test", [], [], _profile())
        assert "marketplace_score" in result
        assert "marketplace_tier" in result
        assert "dimensions" in result
        dims = result["dimensions"]
        assert "data_quality" in dims
        assert "reporting_volume" in dims
        assert "fairness" in dims
        assert "integration_health" in dims
        assert "dispute_resolution" in dims
        assert "signal_count" in result
        assert "last_updated" in result

    def test_all_dimensions_contribute(self):
        """Each dimension should contribute to the composite score."""
        signals = [
            _signal(transaction_ref=f"tx-{i}", metrics={"user_rating": 4}, days_ago=i)
            for i in range(100)
        ]
        result = calculate_marketplace_score("mp_test", signals, [], _profile())
        dims = result["dimensions"]
        for dim_name, dim_value in dims.items():
            assert 0 <= dim_value <= 100, f"{dim_name} out of range: {dim_value}"

    def test_high_quality_marketplace(self):
        """A marketplace with good data across all dimensions."""
        now = _now()
        signals = []
        for i in range(200):
            signals.append(_signal(
                agent_id=f"agent-{i % 10}",
                outcome="completed",
                transaction_ref=f"tx-{i}",
                metrics={"user_rating": 4 + (i % 2)},
                hours_ago=i * 2,
            ))
        audit = [_audit_record(action="ingest") for _ in range(50)]
        profile = _profile(signal_count=200, last_signal_at=now.isoformat())

        result = calculate_marketplace_score("mp_test", signals, audit, profile, now)
        assert result["marketplace_score"] >= 50
        assert result["marketplace_tier"] in ("trusted", "certified", "enterprise")

    def test_low_quality_marketplace(self):
        """A marketplace with poor data quality."""
        signals = [
            {"agent_id": "a", "signal_type": "transaction_outcome",
             "outcome": "failed", "timestamp": "not-valid"}
            for _ in range(3)
        ]
        audit = [_audit_record(action="ingest_error") for _ in range(10)]
        result = calculate_marketplace_score("mp_test", signals, audit, _profile())
        assert result["marketplace_score"] < 45
        assert result["marketplace_tier"] in ("registered", "verified", "trusted")

    def test_score_capped_at_100(self):
        result = calculate_marketplace_score("mp_test", [], [], _profile())
        assert result["marketplace_score"] <= 100

    def test_score_not_negative(self):
        result = calculate_marketplace_score("mp_test", [], [], _profile())
        assert result["marketplace_score"] >= 0

    def test_last_updated_is_iso8601(self):
        result = calculate_marketplace_score("mp_test", [], [], _profile())
        datetime.fromisoformat(result["last_updated"].replace("Z", "+00:00"))

    def test_tier_matches_score_range(self):
        """Tier should correspond to the score range."""
        # Force known score scenarios
        signals_5k = [_signal(transaction_ref=f"tx-{i}", hours_ago=i)
                      for i in range(5000)]
        result = calculate_marketplace_score("mp_test", signals_5k, [], _profile())
        score = result["marketplace_score"]
        tier = result["marketplace_tier"]
        if score >= 80:
            assert tier == "enterprise"
        elif score >= 60:
            assert tier == "certified"
        elif score >= 40:
            assert tier == "trusted"
        elif score >= 20:
            assert tier == "verified"
        else:
            assert tier == "registered"


# === Endpoint Integration Tests ===

class TestGetMarketplaceScoreEndpoint:
    def test_marketplace_not_found(self, dynamodb):
        from handlers.marketplace import get_marketplace_score
        event = make_api_event(
            method="GET",
            path="/marketplace/nonexistent/score",
            path_params={"id": "nonexistent"},
        )
        resp = get_marketplace_score(event, {})
        assert resp["statusCode"] == 404

    def test_returns_score_for_existing_marketplace(self, dynamodb):
        from handlers.marketplace import get_marketplace_score

        mp_id = "mp_score_test"
        dynamodb.put_item(Item={
            "PK": f"MARKETPLACE#{mp_id}",
            "SK": "PROFILE",
            "marketplace_id": mp_id,
            "name": "Score Test MP",
            "marketplace_score": Decimal("45.5"),
            "tier": "trusted",
            "signal_count": 100,
            "last_scored_at": _now().isoformat(),
            "marketplace_dimensions": json.dumps({
                "data_quality": 60, "reporting_volume": 40,
                "fairness": 50, "integration_health": 35,
                "dispute_resolution": 45,
            }),
        })

        event = make_api_event(
            method="GET",
            path=f"/marketplace/{mp_id}/score",
            path_params={"id": mp_id},
        )
        resp = get_marketplace_score(event, {})
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert body["marketplace_id"] == mp_id
        assert body["marketplace_score"] == 45.5
        assert body["tier"] == "trusted"
        assert body["signal_count"] == 100
        assert body["dimensions"]["data_quality"] == 60

    def test_sanitized_response_no_internal_fields(self, dynamodb):
        """Score endpoint should not expose internal fields."""
        from handlers.marketplace import get_marketplace_score

        mp_id = "mp_sanitize_test"
        dynamodb.put_item(Item={
            "PK": f"MARKETPLACE#{mp_id}",
            "SK": "PROFILE",
            "marketplace_id": mp_id,
            "name": "Sanitize Test",
            "marketplace_score": Decimal("30"),
            "tier": "verified",
            "signal_count": 50,
            "api_key_hash": "secret_hash_123",
            "contact_email": "secret@example.com",
        })

        event = make_api_event(
            method="GET",
            path=f"/marketplace/{mp_id}/score",
            path_params={"id": mp_id},
        )
        resp = get_marketplace_score(event, {})
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])

        # Internal fields should NOT be exposed
        assert "api_key_hash" not in body
        assert "contact_email" not in body

    def test_missing_id(self, dynamodb):
        from handlers.marketplace import get_marketplace_score
        event = make_api_event(
            method="GET",
            path="/marketplace//score",
            path_params={"id": ""},
        )
        resp = get_marketplace_score(event, {})
        assert resp["statusCode"] == 400


class TestRecalculateMarketplaceScoreEndpoint:
    @pytest.fixture
    def scored_marketplace(self, dynamodb):
        """Create a marketplace with signals for recalculation."""
        from utils.auth import generate_api_key

        mp_id = "mp_recalc_test"
        raw_key, key_hash = generate_api_key()
        now = _now().isoformat()

        dynamodb.put_item(Item={
            "PK": f"MARKETPLACE#{mp_id}",
            "SK": "PROFILE",
            "GSI1PK": f"MARKETPLACE_NAME#Recalc MP",
            "GSI1SK": "META",
            "marketplace_id": mp_id,
            "name": "Recalc MP",
            "url": "https://recalc.example.com",
            "contact_email": "admin@recalc.example.com",
            "api_key_hash": key_hash,
            "registered_at": now,
            "marketplace_score": Decimal("0"),
            "tier": "registered",
            "signal_count": 0,
            "last_signal_at": None,
        })

        dynamodb.put_item(Item={
            "PK": f"MARKETPLACE#{mp_id}",
            "SK": f"APIKEY#{key_hash[:16]}",
            "GSI2PK": f"APIKEY#{key_hash}",
            "GSI2SK": now,
            "marketplace_id": mp_id,
            "key_hash": key_hash,
            "created_at": now,
        })

        # Add some signals
        for i in range(20):
            dynamodb.put_item(Item={
                "PK": f"SIGNAL#{mp_id}#agent-{i % 3}",
                "SK": f"TS#{now}#sig{i}",
                "signal_id": f"sig{i}",
                "marketplace_id": mp_id,
                "agent_id": f"agent-{i % 3}",
                "signal_type": "transaction_outcome",
                "outcome": "completed",
                "timestamp": now,
                "transaction_ref": f"tx-{i}",
            })

        return mp_id, raw_key

    def test_recalculate_updates_stored_profile(self, dynamodb, scored_marketplace):
        from handlers.marketplace import recalculate_marketplace_score

        mp_id, raw_key = scored_marketplace
        event = make_api_event(
            method="POST",
            path=f"/marketplace/{mp_id}/recalculate-score",
            path_params={"id": mp_id},
            api_key=raw_key,
        )
        resp = recalculate_marketplace_score(event, {})
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert body["marketplace_id"] == mp_id
        assert body["marketplace_score"] >= 0
        assert "marketplace_tier" in body
        assert "dimensions" in body
        assert body["signal_count"] == 20

        # Verify profile was updated in DynamoDB
        profile = dynamodb.get_item(
            Key={"PK": f"MARKETPLACE#{mp_id}", "SK": "PROFILE"}
        )["Item"]
        assert float(profile["marketplace_score"]) == body["marketplace_score"]
        assert profile["tier"] == body["marketplace_tier"]
        assert profile.get("last_scored_at") is not None

    def test_unauthorized_no_key(self, dynamodb, scored_marketplace):
        from handlers.marketplace import recalculate_marketplace_score

        mp_id, _ = scored_marketplace
        event = make_api_event(
            method="POST",
            path=f"/marketplace/{mp_id}/recalculate-score",
            path_params={"id": mp_id},
        )
        resp = recalculate_marketplace_score(event, {})
        assert resp["statusCode"] == 401

    def test_unauthorized_wrong_marketplace(self, dynamodb, scored_marketplace):
        from handlers.marketplace import recalculate_marketplace_score

        _, raw_key = scored_marketplace
        event = make_api_event(
            method="POST",
            path="/marketplace/other_mp/recalculate-score",
            path_params={"id": "other_mp"},
            api_key=raw_key,
        )
        resp = recalculate_marketplace_score(event, {})
        assert resp["statusCode"] == 401


# === Flywheel Integration Tests ===

class TestFlywheelIntegration:
    def test_get_marketplace_scores_returns_scores(self, dynamodb):
        """get_marketplace_scores should fetch marketplace scores from DynamoDB."""
        from utils.ace_scoring import get_marketplace_scores

        # Create marketplace profiles with scores
        dynamodb.put_item(Item={
            "PK": "MARKETPLACE#mp_a",
            "SK": "PROFILE",
            "marketplace_id": "mp_a",
            "marketplace_score": Decimal("75"),
        })
        dynamodb.put_item(Item={
            "PK": "MARKETPLACE#mp_b",
            "SK": "PROFILE",
            "marketplace_id": "mp_b",
            "marketplace_score": Decimal("40"),
        })

        scores = get_marketplace_scores(["mp_a", "mp_b"])
        assert scores["mp_a"] == 75.0
        assert scores["mp_b"] == 40.0

    def test_get_marketplace_scores_missing_marketplace(self, dynamodb):
        """Missing marketplaces should not appear in results."""
        from utils.ace_scoring import get_marketplace_scores

        scores = get_marketplace_scores(["nonexistent_mp"])
        assert "nonexistent_mp" not in scores

    def test_get_marketplace_scores_empty_list(self, dynamodb):
        from utils.ace_scoring import get_marketplace_scores
        assert get_marketplace_scores([]) == {}

    def test_marketplace_score_affects_agent_source_weighting(self, dynamodb):
        """Higher marketplace scores should give more weight to agent scoring."""
        from utils.ace_scoring import calculate_clearinghouse_score, _get_marketplace_weight

        # Marketplace A: high score (heavy weight)
        # Marketplace B: low score (light weight)
        marketplace_scores = {"mp_high": 90, "mp_low": 10}

        weight_high = _get_marketplace_weight("mp_high", marketplace_scores)
        weight_low = _get_marketplace_weight("mp_low", marketplace_scores)
        assert weight_high > weight_low

        # Agent with failures from high-scored marketplace should be hurt more
        base_signals = [
            {"signal_type": "transaction_outcome", "outcome": "completed",
             "marketplace_id": "mp_neutral", "agent_id": "agent-1",
             "timestamp": _now().isoformat()}
            for _ in range(20)
        ]
        failures_from_high = [
            {"signal_type": "transaction_outcome", "outcome": "failed",
             "marketplace_id": "mp_high", "agent_id": "agent-1",
             "timestamp": _now().isoformat()}
            for _ in range(5)
        ]
        failures_from_low = [
            {"signal_type": "transaction_outcome", "outcome": "failed",
             "marketplace_id": "mp_low", "agent_id": "agent-1",
             "timestamp": _now().isoformat()}
            for _ in range(5)
        ]

        score_high_fail = calculate_clearinghouse_score(
            "agent-1", base_signals + failures_from_high, marketplace_scores
        )["trust_score"]
        score_low_fail = calculate_clearinghouse_score(
            "agent-1", base_signals + failures_from_low, marketplace_scores
        )["trust_score"]

        # Failures from high-scored marketplace should impact more
        assert score_high_fail < score_low_fail
