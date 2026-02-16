"""Tests for ACE-T trust scoring engine and trust API handlers."""

import math
import pytest
from datetime import datetime, timezone, timedelta

# Test the scoring engine directly
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.ace_scoring import (
    calculate_ace_score,
    calculate_precedent,
    calculate_reversibility,
    calculate_blast_radius,
    get_trust_tier,
    apply_decay,
    PRECEDENT_BASE,
    PRECEDENT_CAP,
)


# === Helpers ===

def _now():
    return datetime.now(timezone.utc)

def _event(event_type, days_ago=0, **kwargs):
    ts = (_now() - timedelta(days=days_ago)).isoformat()
    e = {"event_type": event_type, "timestamp": ts}
    e.update(kwargs)
    return e

def _profile(**kwargs):
    p = {"capabilities": [], "declared_scope": "network_call"}
    p.update(kwargs)
    return p


# === Trust Tier Tests ===

class TestTrustTiers:
    def test_untrusted_boundary(self):
        assert get_trust_tier(0) == "untrusted"
        assert get_trust_tier(19) == "untrusted"

    def test_provisional_boundary(self):
        assert get_trust_tier(20) == "provisional"
        assert get_trust_tier(39) == "provisional"

    def test_established_boundary(self):
        assert get_trust_tier(40) == "established"
        assert get_trust_tier(59) == "established"

    def test_trusted_boundary(self):
        assert get_trust_tier(60) == "trusted"
        assert get_trust_tier(79) == "trusted"

    def test_highly_trusted_boundary(self):
        assert get_trust_tier(80) == "highly_trusted"
        assert get_trust_tier(95) == "highly_trusted"

    def test_clamping(self):
        assert get_trust_tier(-5) == "untrusted"
        assert get_trust_tier(100) == "highly_trusted"


# === Decay Tests ===

class TestDecay:
    def test_recent_event_full_weight(self):
        ts = _now().isoformat()
        assert apply_decay(ts, _now()) == pytest.approx(1.0, abs=0.01)

    def test_old_event_decays(self):
        ts = (_now() - timedelta(days=69)).isoformat()  # ~1 half-life
        weight = apply_decay(ts, _now())
        assert 0.45 < weight < 0.55  # should be ~0.5

    def test_safety_violation_decays_slower(self):
        ts = (_now() - timedelta(days=69)).isoformat()
        normal = apply_decay(ts, _now(), is_safety_violation=False)
        safety = apply_decay(ts, _now(), is_safety_violation=True)
        assert safety > normal  # safety decays much slower

    def test_very_old_event_near_zero(self):
        ts = (_now() - timedelta(days=500)).isoformat()
        weight = apply_decay(ts, _now())
        assert weight < 0.01


# === Precedent Tests ===

class TestPrecedent:
    def test_cold_start(self):
        """No events → base score of 10."""
        score = calculate_precedent([])
        assert score == PRECEDENT_BASE

    def test_successes_increase_score(self):
        events = [_event("success") for _ in range(10)]
        score = calculate_precedent(events)
        assert score > PRECEDENT_BASE + 20  # log2(11) * 10 ≈ 34.6

    def test_single_failure_hurts(self):
        events = [_event("success") for _ in range(5)]
        score_clean = calculate_precedent(events)
        events_with_fail = events + [_event("failure")]
        score_dirty = calculate_precedent(events_with_fail)
        assert score_dirty < score_clean
        # Failure should cause significant drop
        assert score_clean - score_dirty > 15

    def test_asymmetry_failures_hurt_more(self):
        """One failure should hurt more than one success helps, given enough headroom."""
        # Give agent a baseline of 10 successes so floor doesn't mask asymmetry
        base_events = [_event("success") for _ in range(10)]
        base = calculate_precedent(base_events)
        with_extra_success = calculate_precedent(base_events + [_event("success")])
        with_failure = calculate_precedent(base_events + [_event("failure")])
        success_gain = with_extra_success - base
        failure_loss = base - with_failure
        assert failure_loss > success_gain * 2  # failures hurt at least 2x more

    def test_safety_violation_catastrophic(self):
        events = [_event("success") for _ in range(20)]
        score_clean = calculate_precedent(events)
        events_with_violation = events + [_event("safety_violation")]
        score_violated = calculate_precedent(events_with_violation)
        assert score_clean - score_violated >= 25  # catastrophic drop

    def test_old_failure_hurts_less(self):
        recent_fail = [_event("failure", days_ago=1)]
        old_fail = [_event("failure", days_ago=200)]
        score_recent = calculate_precedent(recent_fail)
        score_old = calculate_precedent(old_fail)
        assert score_old > score_recent  # old failure hurts less

    def test_score_capped_at_95(self):
        events = [_event("success") for _ in range(10000)]
        score = calculate_precedent(events)
        assert score <= PRECEDENT_CAP

    def test_recovery_after_failure(self):
        """Agent can recover trust after failures with sustained good behavior."""
        # Start with a failure
        events = [_event("failure", days_ago=60)]
        # Then 20 successes over time
        for i in range(20):
            events.append(_event("success", days_ago=59 - i * 2))
        score = calculate_precedent(events)
        # Should have recovered significantly
        assert score > 30

    def test_timeout_partial_penalty(self):
        fail_score = calculate_precedent([_event("failure")])
        timeout_score = calculate_precedent([_event("timeout")])
        base = calculate_precedent([])
        # Timeout should be less severe than failure
        assert timeout_score > fail_score
        assert timeout_score < base


# === Reversibility Tests ===

class TestReversibility:
    def test_default_neutral(self):
        score = calculate_reversibility(_profile(), [])
        assert score == 50.0

    def test_undo_capability_bonus(self):
        profile = _profile(capabilities=["undo", "rollback"])
        score = calculate_reversibility(profile, [])
        assert score > 60

    def test_sandbox_bonus(self):
        profile = _profile(capabilities=["sandbox_execution"])
        score = calculate_reversibility(profile, [])
        assert score > 55

    def test_observed_irreversible_penalty(self):
        events = [_event("success", reversibility_observed="irreversible") for _ in range(5)]
        score = calculate_reversibility(_profile(), events)
        assert score < 50


# === Blast Radius Tests ===

class TestBlastRadius:
    def test_read_only_highest(self):
        profile = _profile(declared_scope="read_only")
        score = calculate_blast_radius(profile, [])
        assert score >= 90

    def test_financial_lowest(self):
        profile = _profile(declared_scope="financial")
        score = calculate_blast_radius(profile, [])
        assert score <= 25

    def test_observed_overrides_declared(self):
        """Observed behavior should pull score toward reality."""
        profile = _profile(declared_scope="read_only")  # claims safe
        # But observed doing financial ops
        events = [_event("success", blast_radius_observed="financial") for _ in range(5)]
        score = calculate_blast_radius(profile, events)
        # Should be pulled down from 95 toward 20
        assert score < 60


# === Composite Score Tests ===

class TestCompositeScore:
    def test_cold_start_score(self):
        """New agent with no events should land in provisional or untrusted."""
        result = calculate_ace_score(_profile(), [])
        assert result["trust_tier"] in ("untrusted", "provisional")
        assert result["trust_score"] < 40

    def test_established_agent(self):
        """Agent with good history should reach established+."""
        profile = _profile(capabilities=["undo", "sandbox_execution"], declared_scope="file_write")
        events = [_event("success", days_ago=i) for i in range(30)]
        result = calculate_ace_score(profile, events)
        assert result["trust_score"] >= 40
        assert result["trust_tier"] in ("established", "trusted", "highly_trusted")

    def test_read_only_agent_scores_higher(self):
        """Read-only agent with same history should score higher than financial agent."""
        events = [_event("success") for _ in range(10)]
        safe_profile = _profile(declared_scope="read_only")
        risky_profile = _profile(declared_scope="financial")
        safe_result = calculate_ace_score(safe_profile, events)
        risky_result = calculate_ace_score(risky_profile, events)
        assert safe_result["trust_score"] > risky_result["trust_score"]

    def test_score_never_exceeds_95(self):
        profile = _profile(capabilities=["undo", "rollback", "sandbox_execution", "confirmation"],
                          declared_scope="read_only")
        events = [_event("success") for _ in range(10000)]
        result = calculate_ace_score(profile, events)
        assert result["trust_score"] <= 95

    def test_result_structure(self):
        result = calculate_ace_score(_profile(), [])
        assert "trust_score" in result
        assert "trust_tier" in result
        assert "axes" in result
        assert "reversibility" in result["axes"]
        assert "precedent" in result["axes"]
        assert "blast_radius" in result["axes"]
        assert "weights" in result
        assert "history" in result
