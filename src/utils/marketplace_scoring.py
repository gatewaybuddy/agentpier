"""Marketplace scoring engine for AgentPier.

Scores marketplaces on 5 dimensions:
- Data Quality (30%): Completeness of signal fields, consistency, valid agent_ids, low error rate
- Reporting Volume (20%): Total signals submitted (log scale)
- Fairness (20%): Statistical analysis of reported outcomes — flags bias
- Integration Health (15%): Submission cadence regularity and recency
- Dispute Resolution (15%): Ratio of disputed signals that get resolved

Marketplace Tiers:
- registered (0-19): Just signed up
- verified (20-39): Identity confirmed, some data flowing
- trusted (40-59): Consistent quality data, 30+ days
- certified (60-79): High quality, 90+ days, good volume
- enterprise (80-100): Premium partner, SLA
"""

import math
import statistics
from datetime import datetime, timezone
from typing import Optional

# === Dimension Weights ===
WEIGHT_DATA_QUALITY = 0.30
WEIGHT_REPORTING_VOLUME = 0.20
WEIGHT_FAIRNESS = 0.20
WEIGHT_INTEGRATION_HEALTH = 0.15
WEIGHT_DISPUTE_RESOLUTION = 0.15

# === Volume Log Scale Breakpoints ===
VOLUME_BREAKPOINTS = [
    (5000, 100),
    (1000, 80),
    (100, 60),
    (10, 30),
    (0, 0),
]

# === Marketplace Tiers ===
MARKETPLACE_TIERS = [
    (80, 100, "enterprise"),
    (60, 79, "certified"),
    (40, 59, "trusted"),
    (20, 39, "verified"),
    (0, 19, "registered"),
]

# Required signal fields for data quality scoring
REQUIRED_SIGNAL_FIELDS = {"agent_id", "signal_type", "outcome", "timestamp"}
OPTIONAL_SIGNAL_FIELDS = {"metrics", "transaction_ref"}


def get_marketplace_tier(score: float) -> str:
    """Map a marketplace score (0-100) to a tier label."""
    clamped = max(0.0, min(100.0, score))
    for low, high, label in MARKETPLACE_TIERS:
        if low <= clamped <= high:
            return label
    return "registered"


def _score_data_quality(signals: list, audit_records: list) -> float:
    """Score data quality (0-100).

    Measures:
    - Field completeness (required + optional)
    - Timestamp consistency (valid ISO format)
    - Valid agent_ids (non-empty strings)
    - Low error rate from audit records
    """
    if not signals:
        return 0.0

    total = len(signals)
    completeness_scores = []
    valid_timestamps = 0
    valid_agent_ids = 0

    for signal in signals:
        # Required field completeness
        required_present = sum(1 for f in REQUIRED_SIGNAL_FIELDS if signal.get(f))
        optional_present = sum(1 for f in OPTIONAL_SIGNAL_FIELDS if signal.get(f))
        # Required fields are worth 80%, optional 20%
        field_score = (required_present / len(REQUIRED_SIGNAL_FIELDS)) * 80.0
        if OPTIONAL_SIGNAL_FIELDS:
            field_score += (optional_present / len(OPTIONAL_SIGNAL_FIELDS)) * 20.0
        completeness_scores.append(field_score)

        # Timestamp validation
        ts = signal.get("timestamp")
        if ts and isinstance(ts, str):
            try:
                datetime.fromisoformat(ts.replace("Z", "+00:00"))
                valid_timestamps += 1
            except (ValueError, TypeError):
                pass

        # Agent ID validation
        agent_id = signal.get("agent_id")
        if agent_id and isinstance(agent_id, str) and len(agent_id) >= 3:
            valid_agent_ids += 1

    avg_completeness = sum(completeness_scores) / total
    timestamp_rate = (valid_timestamps / total) * 100.0
    agent_id_rate = (valid_agent_ids / total) * 100.0

    # Error rate from audit records (audit entries with action containing "error")
    error_count = sum(1 for r in audit_records if "error" in (r.get("action") or "").lower())
    total_actions = max(len(audit_records), 1)
    error_rate = error_count / total_actions
    error_score = max(0.0, 100.0 - (error_rate * 500.0))  # 20% error = 0 score

    # Weighted composite: completeness 40%, timestamps 20%, agent_ids 20%, errors 20%
    score = (
        avg_completeness * 0.40 +
        timestamp_rate * 0.20 +
        agent_id_rate * 0.20 +
        error_score * 0.20
    )

    return max(0.0, min(100.0, score))


def _score_reporting_volume(signal_count: int) -> float:
    """Score reporting volume (0-100) on log scale.

    0 = 0pts, 10 = 30pts, 100 = 60pts, 1000 = 80pts, 5000+ = 100pts
    """
    for threshold, points in VOLUME_BREAKPOINTS:
        if signal_count >= threshold:
            return float(points)
    return 0.0


def _score_fairness(signals: list) -> float:
    """Score fairness (0-100).

    Flags suspicious patterns:
    - One agent getting disproportionate failures vs platform average
    - Suspiciously uniform outcomes (all 5-star ratings)
    - Standard deviation of outcomes too low or too high
    """
    if not signals:
        return 50.0  # neutral with no data

    outcome_signals = [s for s in signals if s.get("signal_type") == "transaction_outcome"]
    if len(outcome_signals) < 3:
        return 50.0  # not enough data to judge

    # Calculate per-agent failure rates
    agent_outcomes = {}
    for signal in outcome_signals:
        agent_id = signal.get("agent_id", "unknown")
        if agent_id not in agent_outcomes:
            agent_outcomes[agent_id] = {"total": 0, "failures": 0}
        agent_outcomes[agent_id]["total"] += 1
        if signal.get("outcome") in ("failed", "disputed"):
            agent_outcomes[agent_id]["failures"] += 1

    # Platform average failure rate
    total_outcomes = len(outcome_signals)
    total_failures = sum(v["failures"] for v in agent_outcomes.values())
    platform_failure_rate = total_failures / total_outcomes if total_outcomes > 0 else 0

    # Check for disproportionate failures per agent
    bias_penalty = 0.0
    for agent_id, data in agent_outcomes.items():
        if data["total"] < 3:
            continue
        agent_failure_rate = data["failures"] / data["total"]
        # If any agent's failure rate is 2x+ the platform average, flag it
        if platform_failure_rate > 0 and agent_failure_rate > platform_failure_rate * 2:
            bias_penalty += 20.0
        elif platform_failure_rate == 0 and agent_failure_rate > 0.5:
            bias_penalty += 15.0

    bias_penalty = min(50.0, bias_penalty)

    # Check for suspiciously uniform outcomes
    uniformity_penalty = 0.0
    feedback_signals = [s for s in signals if s.get("signal_type") == "user_feedback"]
    if len(feedback_signals) >= 5:
        ratings = []
        for s in feedback_signals:
            metrics = s.get("metrics") or {}
            rating = metrics.get("user_rating")
            if rating is not None:
                try:
                    ratings.append(float(rating))
                except (ValueError, TypeError):
                    pass

        if len(ratings) >= 5:
            stdev = statistics.stdev(ratings) if len(ratings) > 1 else 0.0
            # Too low stdev (< 0.2) = suspiciously uniform
            if stdev < 0.2:
                uniformity_penalty += 30.0
            elif stdev < 0.5:
                uniformity_penalty += 15.0
            # Too high stdev (> 2.0) = inconsistent marketplace
            elif stdev > 2.0:
                uniformity_penalty += 10.0

    # Outcome distribution check
    distribution_penalty = 0.0
    if len(outcome_signals) >= 10:
        outcome_counts = {}
        for s in outcome_signals:
            oc = s.get("outcome", "unknown")
            outcome_counts[oc] = outcome_counts.get(oc, 0) + 1

        rates = [c / total_outcomes for c in outcome_counts.values()]
        if len(rates) > 1:
            stdev = statistics.stdev(rates)
            # Very low variance in outcome distribution is suspicious
            if stdev < 0.05 and len(outcome_counts) <= 1:
                distribution_penalty += 10.0

    score = 100.0 - bias_penalty - uniformity_penalty - distribution_penalty
    return max(0.0, min(100.0, score))


def _score_integration_health(signals: list, profile: dict,
                               now: Optional[datetime] = None) -> float:
    """Score integration health (0-100).

    Based on signal submission patterns:
    - Regular submission cadence = good
    - Long gaps or burst patterns = lower score
    - last_signal_at recency
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if not signals:
        # Check recency from profile
        last_signal = profile.get("last_signal_at")
        if not last_signal:
            return 0.0
        return 10.0  # minimal score if profile says there were signals

    # Extract timestamps and sort
    timestamps = []
    for signal in signals:
        ts = signal.get("timestamp") or signal.get("received_at")
        if ts:
            try:
                if isinstance(ts, datetime):
                    dt = ts
                else:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                timestamps.append(dt)
            except (ValueError, TypeError):
                continue

    if not timestamps:
        return 10.0

    timestamps.sort()

    # Recency score (0-40): how recent is the last signal?
    last_signal_dt = timestamps[-1]
    days_since_last = (now - last_signal_dt).total_seconds() / 86400.0
    if days_since_last < 1:
        recency_score = 40.0
    elif days_since_last < 7:
        recency_score = 35.0
    elif days_since_last < 30:
        recency_score = 25.0
    elif days_since_last < 90:
        recency_score = 15.0
    else:
        recency_score = 5.0

    # Cadence regularity score (0-40): check gaps between signals
    if len(timestamps) < 2:
        cadence_score = 20.0  # single signal, neutral
    else:
        gaps = []
        for i in range(1, len(timestamps)):
            gap = (timestamps[i] - timestamps[i - 1]).total_seconds() / 3600.0  # hours
            gaps.append(gap)

        if len(gaps) > 1:
            mean_gap = statistics.mean(gaps)
            stdev_gap = statistics.stdev(gaps)
            # Coefficient of variation: lower = more regular
            cv = stdev_gap / mean_gap if mean_gap > 0 else 0
            if cv < 0.5:
                cadence_score = 40.0  # very regular
            elif cv < 1.0:
                cadence_score = 30.0  # somewhat regular
            elif cv < 2.0:
                cadence_score = 20.0  # bursty
            else:
                cadence_score = 10.0  # very bursty
        else:
            cadence_score = 20.0

    # Longevity score (0-20): time span from first to last signal
    span_days = (timestamps[-1] - timestamps[0]).total_seconds() / 86400.0
    if span_days >= 90:
        longevity_score = 20.0
    elif span_days >= 30:
        longevity_score = 15.0
    elif span_days >= 7:
        longevity_score = 10.0
    else:
        longevity_score = 5.0

    score = recency_score + cadence_score + longevity_score
    return max(0.0, min(100.0, score))


def _score_dispute_resolution(signals: list) -> float:
    """Score dispute resolution (0-100).

    Based on ratio of disputed transactions that get resolved.
    In v1, checks for status updates on disputed signals — more resolution = higher score.
    """
    if not signals:
        return 50.0  # neutral with no data

    disputed_signals = [
        s for s in signals
        if s.get("outcome") == "disputed"
    ]

    if not disputed_signals:
        return 70.0  # no disputes is a good sign

    # Check for resolved disputes (signals with same transaction_ref and resolved outcome)
    transaction_refs = {}
    for signal in signals:
        ref = signal.get("transaction_ref")
        if not ref:
            continue
        if ref not in transaction_refs:
            transaction_refs[ref] = []
        transaction_refs[ref].append(signal)

    # Count disputed refs that have a resolution (completed/refunded follow-up)
    disputed_refs = set()
    resolved_refs = set()
    for signal in disputed_signals:
        ref = signal.get("transaction_ref")
        if ref:
            disputed_refs.add(ref)

    for ref in disputed_refs:
        ref_signals = transaction_refs.get(ref, [])
        for s in ref_signals:
            if s.get("outcome") in ("completed", "refunded"):
                resolved_refs.add(ref)
                break

    # Also consider disputes without transaction_ref — check if there are
    # "completed" or "refunded" signals for the same agent_id after the dispute
    unref_disputed = [s for s in disputed_signals if not s.get("transaction_ref")]
    unref_resolved = 0
    for ds in unref_disputed:
        agent_id = ds.get("agent_id")
        ds_ts = ds.get("timestamp", "")
        # Look for resolution signals from same agent after this dispute
        for s in signals:
            if (s.get("agent_id") == agent_id and
                    s.get("outcome") in ("completed", "refunded") and
                    (s.get("timestamp") or "") > ds_ts):
                unref_resolved += 1
                break

    total_disputed = len(disputed_refs) + len(unref_disputed)
    total_resolved = len(resolved_refs) + unref_resolved

    if total_disputed == 0:
        return 70.0

    resolution_rate = total_resolved / total_disputed
    # Scale: 100% resolved = 90, 50% = 60, 0% = 30
    score = 30.0 + (resolution_rate * 60.0)

    # Penalty for high dispute rate overall
    total_signals = len(signals)
    dispute_rate = len(disputed_signals) / total_signals
    if dispute_rate > 0.3:
        score -= 20.0
    elif dispute_rate > 0.1:
        score -= 10.0

    return max(0.0, min(100.0, score))


def calculate_marketplace_score(marketplace_id: str, signals_submitted: list,
                                 audit_records: list, profile: dict,
                                 now: Optional[datetime] = None) -> dict:
    """Score a marketplace on data quality and trustworthiness.

    Args:
        marketplace_id: The marketplace being scored.
        signals_submitted: All signals submitted by this marketplace.
        audit_records: Audit log entries for this marketplace.
        profile: Marketplace profile dict.
        now: Optional datetime for testing.

    Returns:
        Dict with marketplace_score, marketplace_tier, dimensions,
        signal_count, and last_updated.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    signal_count = len(signals_submitted)

    # Calculate 5 dimensions
    data_quality = _score_data_quality(signals_submitted, audit_records)
    reporting_volume = _score_reporting_volume(signal_count)
    fairness = _score_fairness(signals_submitted)
    integration_health = _score_integration_health(signals_submitted, profile, now)
    dispute_resolution = _score_dispute_resolution(signals_submitted)

    # Weighted composite
    composite = (
        data_quality * WEIGHT_DATA_QUALITY +
        reporting_volume * WEIGHT_REPORTING_VOLUME +
        fairness * WEIGHT_FAIRNESS +
        integration_health * WEIGHT_INTEGRATION_HEALTH +
        dispute_resolution * WEIGHT_DISPUTE_RESOLUTION
    )

    composite = max(0.0, min(100.0, composite))
    tier = get_marketplace_tier(composite)

    return {
        "marketplace_score": round(composite, 2),
        "marketplace_tier": tier,
        "dimensions": {
            "data_quality": round(data_quality, 2),
            "reporting_volume": round(reporting_volume, 2),
            "fairness": round(fairness, 2),
            "integration_health": round(integration_health, 2),
            "dispute_resolution": round(dispute_resolution, 2),
        },
        "signal_count": signal_count,
        "last_updated": now.isoformat(),
    }
