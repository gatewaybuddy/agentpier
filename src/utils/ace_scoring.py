"""ACE-T Scoring Engine for AgentPier.

Adapted from Forgekeeper's ACE (Action Confidence Engine).
Three axes: Reversibility, Precedent, Blast Radius.
Informed by FICO, EigenTrust, and reputation system research.

Design principles:
- Asymmetric: failures hurt 4x more than successes help (FICO-inspired)
- Exponential decay: recent events matter more (half-life ~69 days)
- Safety violations are near-permanent (half-life ~693 days)
- Cold start: new agents begin at low trust (Tier 0-1)
- Score cap at 95: no agent is ever fully trusted

Cross-platform clearinghouse scoring (issue #42):
- Four dimensions: reliability, safety, capability, transparency
- Source weighting by marketplace trust score
- Cross-platform bonus for consistent multi-platform agents
- Confidence scoring based on signal volume
"""

import math
import os
import statistics
from datetime import datetime, timezone
from typing import List, Optional

# === Axis Weights ===
WEIGHT_REVERSIBILITY = 0.25
WEIGHT_PRECEDENT = 0.50
WEIGHT_BLAST_RADIUS = 0.25

# === Precedent Constants ===
PRECEDENT_BASE = 10.0
PRECEDENT_CAP = 95.0
PRECEDENT_SUCCESS_SCALE = 10.0  # log2(successes+1) * this
PRECEDENT_FAILURE_PENALTY = 20.0  # per failure, before decay
PRECEDENT_SAFETY_PENALTY = 30.0  # catastrophic

# === Decay Constants ===
DECAY_LAMBDA_NORMAL = 0.01  # half-life ~69 days
DECAY_LAMBDA_SAFETY = 0.001  # half-life ~693 days (near-permanent)

# === Blast Radius Scope Scores ===
SCOPE_SCORES = {
    "read_only": 95,
    "file_write": 75,
    "database_write": 70,
    "network_call": 50,
    "messaging": 45,
    "api_integration": 40,
    "financial": 20,
    "infrastructure": 15,
    "code_deployment": 10,
}
DEFAULT_SCOPE_SCORE = 50  # unknown scope

# === Trust Tiers ===
TIERS = [
    (0, 19, "untrusted"),
    (20, 39, "provisional"),
    (40, 59, "established"),
    (60, 79, "trusted"),
    (80, 95, "highly_trusted"),
]


def get_trust_tier(score: float) -> str:
    """Map a composite score (0-95) to a trust tier label."""
    clamped = max(0.0, min(95.0, score))
    for low, high, label in TIERS:
        if low <= clamped <= high:
            return label
    return "untrusted"


def apply_decay(event_timestamp: str, now: Optional[datetime] = None,
                is_safety_violation: bool = False) -> float:
    """Calculate decay weight for an event based on age.
    
    Returns a float between 0 and 1 (1 = just happened, decays toward 0).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    try:
        if isinstance(event_timestamp, datetime):
            event_dt = event_timestamp
        else:
            event_dt = datetime.fromisoformat(event_timestamp.replace("Z", "+00:00"))
        if event_dt.tzinfo is None:
            event_dt = event_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError, AttributeError):
        return 1.0  # can't parse → treat as recent

    days_ago = max(0.0, (now - event_dt).total_seconds() / 86400.0)
    lam = DECAY_LAMBDA_SAFETY if is_safety_violation else DECAY_LAMBDA_NORMAL
    return math.exp(-lam * days_ago)


def calculate_reversibility(agent_profile: dict, events: list,
                            now: Optional[datetime] = None) -> float:
    """Calculate reversibility score (0-100).
    
    Starts at 50. Adjusted by declared capabilities and observed behavior.
    """
    score = 50.0

    # Declared capabilities bonuses
    capabilities = agent_profile.get("capabilities", [])
    if isinstance(capabilities, list):
        caps_lower = [c.lower() if isinstance(c, str) else "" for c in capabilities]
    else:
        caps_lower = []

    if any("undo" in c or "rollback" in c for c in caps_lower):
        score += 15.0
    if any("sandbox" in c or "contained" in c for c in caps_lower):
        score += 10.0
    if any("confirmation" in c or "approval" in c for c in caps_lower):
        score += 5.0

    # Observed behavior from events
    for event in events:
        rev_observed = event.get("reversibility_observed")
        if rev_observed is None:
            continue
        decay = apply_decay(event.get("timestamp", ""), now)
        if rev_observed == "reversible":
            score += 2.0 * decay
        elif rev_observed == "irreversible":
            score -= 5.0 * decay

    return max(0.0, min(100.0, score))


def calculate_precedent(events: list, now: Optional[datetime] = None) -> float:
    """Calculate precedent score (0-100).
    
    Starts at 10 (cold start). Grows with successes, decays with failures.
    Asymmetric: failures hurt ~4x more than successes help.
    Safety violations are catastrophic and near-permanent.
    """
    if not events:
        return PRECEDENT_BASE

    successes = 0
    failure_penalty = 0.0
    safety_penalty = 0.0

    for event in events:
        event_type = event.get("event_type", "")
        decay = apply_decay(
            event.get("timestamp", ""), now,
            is_safety_violation=(event_type == "safety_violation")
        )

        if event_type == "success":
            successes += 1
        elif event_type == "failure":
            failure_penalty += PRECEDENT_FAILURE_PENALTY * decay
        elif event_type == "safety_violation":
            safety_penalty += PRECEDENT_SAFETY_PENALTY * decay
        elif event_type == "timeout":
            failure_penalty += (PRECEDENT_FAILURE_PENALTY * 0.5) * decay

    # Growth from successes (logarithmic — diminishing returns)
    success_bonus = math.log2(successes + 1) * PRECEDENT_SUCCESS_SCALE

    score = PRECEDENT_BASE + success_bonus - failure_penalty - safety_penalty
    return max(0.0, min(PRECEDENT_CAP, score))


def calculate_blast_radius(agent_profile: dict, events: list,
                           now: Optional[datetime] = None) -> float:
    """Calculate blast radius score (0-100, INVERTED: high = safer).
    
    Based on declared scope + observed event scope.
    """
    declared_scope = agent_profile.get("declared_scope", "")
    if isinstance(declared_scope, str):
        base_score = SCOPE_SCORES.get(declared_scope, DEFAULT_SCOPE_SCORE)
    else:
        base_score = DEFAULT_SCOPE_SCORE

    # Adjust based on observed blast radius in events
    observed_scores = []
    for event in events:
        br_observed = event.get("blast_radius_observed")
        if br_observed and isinstance(br_observed, str):
            obs_score = SCOPE_SCORES.get(br_observed)
            if obs_score is not None:
                decay = apply_decay(event.get("timestamp", ""), now)
                observed_scores.append((obs_score, decay))

    if observed_scores:
        # Weighted average of observed, blended with declared
        total_weight = sum(w for _, w in observed_scores)
        weighted_obs = sum(s * w for s, w in observed_scores) / total_weight
        # 60% observed, 40% declared (observed behavior > claims)
        score = weighted_obs * 0.6 + base_score * 0.4
    else:
        score = float(base_score)

    return max(0.0, min(100.0, score))


def moltbook_weight(transaction_count: int) -> float:
    """Calculate dynamic Moltbook weight based on transaction count.
    
    As AgentPier transaction count grows, Moltbook weight decreases:
    - 0 transactions: 30% Moltbook, 70% ACE
    - 5 transactions: 20% Moltbook, 80% ACE  
    - 10+ transactions: 10% Moltbook, 90% ACE
    - 20+ transactions: 5% Moltbook, 95% ACE
    """
    if transaction_count >= 20:
        return 0.05
    if transaction_count >= 10:
        return 0.10
    if transaction_count >= 5:
        return 0.20
    return 0.30


def calculate_ace_score(agent_profile: dict, trust_events: list,
                        now: Optional[datetime] = None,
                        moltbook_trust: Optional[float] = None,
                        transaction_count: int = 0) -> dict:
    """Calculate composite ACE-T trust score.

    If moltbook_trust (0.0-1.0) is provided, it's blended in using dynamic weighting
    based on transaction_count. More transactions = less Moltbook weight.

    Returns dict with score, tier, axis breakdown, and diagnostic info.
    """
    reversibility = calculate_reversibility(agent_profile, trust_events, now)
    precedent = calculate_precedent(trust_events, now)
    blast_radius = calculate_blast_radius(agent_profile, trust_events, now)

    composite = (
        reversibility * WEIGHT_REVERSIBILITY +
        precedent * WEIGHT_PRECEDENT +
        blast_radius * WEIGHT_BLAST_RADIUS
    )

    # Blend Moltbook trust if available using dynamic weighting
    if moltbook_trust is not None:
        weight_moltbook = moltbook_weight(transaction_count)
        weight_ace = 1.0 - weight_moltbook
        composite = composite * weight_ace + (moltbook_trust * 100) * weight_moltbook

    # Cap at 95
    composite = min(95.0, composite)

    tier = get_trust_tier(composite)

    # Event summary
    total_events = len(trust_events)
    successes = sum(1 for e in trust_events if e.get("event_type") == "success")
    failures = sum(1 for e in trust_events if e.get("event_type") == "failure")
    violations = sum(1 for e in trust_events if e.get("event_type") == "safety_violation")
    timeouts = sum(1 for e in trust_events if e.get("event_type") == "timeout")

    return {
        "trust_score": round(composite, 2),
        "trust_tier": tier,
        "axes": {
            "reversibility": round(reversibility, 2),
            "precedent": round(precedent, 2),
            "blast_radius": round(blast_radius, 2),
        },
        "weights": {
            "reversibility": WEIGHT_REVERSIBILITY,
            "precedent": WEIGHT_PRECEDENT,
            "blast_radius": WEIGHT_BLAST_RADIUS,
        },
        "history": {
            "total_events": total_events,
            "successes": successes,
            "failures": failures,
            "safety_violations": violations,
            "timeouts": timeouts,
        },
    }


# ============================================================
# Cross-Platform Clearinghouse Scoring (Issue #42)
# ============================================================

# Dimension weights for composite clearinghouse score
CH_WEIGHT_RELIABILITY = 0.35
CH_WEIGHT_SAFETY = 0.30
CH_WEIGHT_CAPABILITY = 0.20
CH_WEIGHT_TRANSPARENCY = 0.15

# Cross-platform bonus: agents on 3+ platforms with consistent scores
CH_CROSS_PLATFORM_BONUS_THRESHOLD = 3
CH_CROSS_PLATFORM_BONUS_MAX = 5.0
CH_CROSS_PLATFORM_CONSISTENCY_THRESHOLD = 15.0  # max stdev for bonus

# Confidence thresholds
CH_CONFIDENCE_THRESHOLDS = [
    (200, 0.95),
    (50, 0.80),
    (10, 0.50),
    (0, 0.20),
]

# Asymmetric incident penalty multiplier (incidents hurt 4x)
CH_INCIDENT_PENALTY_MULTIPLIER = 4.0

# Base score for agents with no signals
CH_BASE_SCORE = 10.0

# Default marketplace weight for unscored marketplaces
CH_DEFAULT_MARKETPLACE_WEIGHT = 1.0


def _get_marketplace_weight(marketplace_id: str, marketplace_scores: dict) -> float:
    """Get source weight for a marketplace based on its trust score."""
    score = marketplace_scores.get(marketplace_id)
    if score is None:
        return CH_DEFAULT_MARKETPLACE_WEIGHT
    # Normalize marketplace score (0-100) to weight (0.1-2.0)
    # Higher-scored marketplaces get more weight
    return max(0.1, min(2.0, score / 50.0))


def _calculate_confidence(signal_count: int) -> float:
    """Calculate confidence score based on total signal volume."""
    for threshold, confidence in CH_CONFIDENCE_THRESHOLDS:
        if signal_count >= threshold:
            return confidence
    return 0.20


def _calculate_reliability(signals: list, marketplace_scores: dict,
                           now: Optional[datetime] = None) -> float:
    """Calculate reliability dimension (0-100).

    Derived from transaction_outcome signals. Completion rate weighted by
    marketplace score and temporal decay.
    """
    outcome_signals = [s for s in signals if s.get("signal_type") == "transaction_outcome"]
    if not outcome_signals:
        return CH_BASE_SCORE

    weighted_completions = 0.0
    weighted_failures = 0.0
    total_weight = 0.0

    for signal in outcome_signals:
        mp_id = signal.get("marketplace_id", "")
        mp_weight = _get_marketplace_weight(mp_id, marketplace_scores)
        decay = apply_decay(signal.get("timestamp", ""), now)
        weight = mp_weight * decay

        outcome = signal.get("outcome", "")
        if outcome == "completed":
            weighted_completions += weight
        elif outcome in ("failed", "disputed"):
            weighted_failures += weight
        elif outcome == "refunded":
            weighted_failures += weight * 0.5  # partial penalty

        total_weight += weight

    if total_weight == 0:
        return CH_BASE_SCORE

    completion_rate = weighted_completions / total_weight
    # Scale: 100% completion = 95, 50% = ~47, 0% = 0
    score = completion_rate * 95.0

    # Asymmetric: failures drag score down more than completions lift it
    failure_ratio = weighted_failures / total_weight
    score -= failure_ratio * 95.0 * (CH_INCIDENT_PENALTY_MULTIPLIER - 1) * 0.25

    return max(0.0, min(100.0, score))


def _calculate_safety(signals: list, marketplace_scores: dict,
                      now: Optional[datetime] = None) -> float:
    """Calculate safety dimension (0-100).

    Derived from incident signals. Asymmetric — incidents hurt 4x more
    than a clean record helps. Uses safety-violation decay (near-permanent).
    """
    # Start with a clean baseline — no incidents = good score
    base_score = 80.0

    incident_signals = [s for s in signals if s.get("signal_type") == "incident"]
    non_incident_count = len([s for s in signals if s.get("signal_type") != "incident"])

    # Clean record bonus (logarithmic, capped)
    if non_incident_count > 0:
        clean_bonus = min(15.0, math.log2(non_incident_count + 1) * 3.0)
        base_score += clean_bonus

    # Incident penalties (asymmetric, near-permanent decay)
    penalty = 0.0
    for signal in incident_signals:
        mp_id = signal.get("marketplace_id", "")
        mp_weight = _get_marketplace_weight(mp_id, marketplace_scores)
        # Incidents use safety-violation decay (near-permanent)
        decay = apply_decay(signal.get("timestamp", ""), now, is_safety_violation=True)

        severity = CH_INCIDENT_PENALTY_MULTIPLIER
        outcome = signal.get("outcome", "")
        if outcome == "data_breach":
            severity *= 1.5  # data breaches are worst
        elif outcome == "security":
            severity *= 1.2

        penalty += 15.0 * severity * mp_weight * decay

    score = base_score - penalty
    return max(0.0, min(100.0, score))


def _calculate_capability(signals: list, marketplace_scores: dict,
                          now: Optional[datetime] = None) -> float:
    """Calculate capability dimension (0-100).

    Derived from user_feedback ratings and completion_time_ms metrics.
    """
    feedback_signals = [s for s in signals if s.get("signal_type") == "user_feedback"]
    if not feedback_signals:
        return CH_BASE_SCORE

    weighted_ratings = 0.0
    total_weight = 0.0

    for signal in feedback_signals:
        mp_id = signal.get("marketplace_id", "")
        mp_weight = _get_marketplace_weight(mp_id, marketplace_scores)
        decay = apply_decay(signal.get("timestamp", ""), now)
        weight = mp_weight * decay

        metrics = signal.get("metrics") or {}
        rating = metrics.get("user_rating")
        if rating is not None:
            try:
                rating = float(rating)
            except (ValueError, TypeError):
                continue
            # Normalize 1-5 rating to 0-100 scale
            normalized = (rating - 1.0) / 4.0 * 100.0
            weighted_ratings += normalized * weight
            total_weight += weight

    if total_weight == 0:
        return CH_BASE_SCORE

    score = weighted_ratings / total_weight

    # Bonus for fast completion times
    completion_times = []
    for signal in feedback_signals:
        metrics = signal.get("metrics") or {}
        ct = metrics.get("completion_time_ms")
        if ct is not None:
            try:
                completion_times.append(float(ct))
            except (ValueError, TypeError):
                continue

    if completion_times:
        median_time = statistics.median(completion_times)
        # Fast agents get a small bonus (up to 5 points)
        # Under 1s = full bonus, over 10s = no bonus
        if median_time < 1000:
            score += 5.0
        elif median_time < 5000:
            score += 3.0
        elif median_time < 10000:
            score += 1.0

    return max(0.0, min(100.0, score))


def _calculate_transparency(signals: list, marketplace_scores: dict) -> float:
    """Calculate transparency dimension (0-100).

    Based on signal volume and consistency across platforms.
    Agents active on more platforms with consistent scores get higher transparency.
    """
    if not signals:
        return CH_BASE_SCORE

    # Count unique marketplaces
    marketplaces = set()
    for signal in signals:
        mp_id = signal.get("marketplace_id", "")
        if mp_id:
            marketplaces.add(mp_id)

    marketplace_count = len(marketplaces)
    signal_count = len(signals)

    # Base: signal volume (logarithmic)
    volume_score = min(50.0, math.log2(signal_count + 1) * 8.0)

    # Platform diversity bonus (up to 30 points)
    diversity_score = min(30.0, marketplace_count * 10.0)

    # Consistency bonus: check if outcome distributions are similar across platforms
    consistency_score = 0.0
    if marketplace_count >= 2:
        # Calculate completion rate per marketplace for transaction outcomes
        mp_rates = {}
        for mp_id in marketplaces:
            mp_signals = [s for s in signals
                          if s.get("marketplace_id") == mp_id
                          and s.get("signal_type") == "transaction_outcome"]
            if mp_signals:
                completions = sum(1 for s in mp_signals if s.get("outcome") == "completed")
                mp_rates[mp_id] = completions / len(mp_signals) * 100.0

        if len(mp_rates) >= 2:
            rates = list(mp_rates.values())
            stdev = statistics.stdev(rates) if len(rates) > 1 else 0.0
            # Low stdev = consistent = high score
            if stdev <= CH_CROSS_PLATFORM_CONSISTENCY_THRESHOLD:
                consistency_score = 20.0 * (1.0 - stdev / CH_CROSS_PLATFORM_CONSISTENCY_THRESHOLD)

    score = volume_score + diversity_score + consistency_score
    return max(0.0, min(100.0, score))


def calculate_clearinghouse_score(agent_id: str, signals: list,
                                  marketplace_scores: dict,
                                  now: Optional[datetime] = None) -> dict:
    """Calculate cross-platform trust score from marketplace-reported signals.

    Args:
        agent_id: The agent being scored.
        signals: All signals across marketplaces (from get_agent_signals_all_sources).
        marketplace_scores: Dict of {marketplace_id: marketplace_trust_score} for source weighting.
        now: Optional datetime for testing (defaults to utcnow).

    Returns:
        Dict with trust_score, trust_tier, dimensions, confidence, signal_count,
        marketplace_count, and last_updated.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Calculate four dimensions
    reliability = _calculate_reliability(signals, marketplace_scores, now)
    safety = _calculate_safety(signals, marketplace_scores, now)
    capability = _calculate_capability(signals, marketplace_scores, now)
    transparency = _calculate_transparency(signals, marketplace_scores)

    # Weighted composite
    composite = (
        reliability * CH_WEIGHT_RELIABILITY +
        safety * CH_WEIGHT_SAFETY +
        capability * CH_WEIGHT_CAPABILITY +
        transparency * CH_WEIGHT_TRANSPARENCY
    )

    # Cross-platform bonus
    marketplaces = set()
    for signal in signals:
        mp_id = signal.get("marketplace_id", "")
        if mp_id:
            marketplaces.add(mp_id)

    marketplace_count = len(marketplaces)

    if marketplace_count >= CH_CROSS_PLATFORM_BONUS_THRESHOLD:
        # Check consistency across platforms for bonus
        mp_rates = {}
        for mp_id in marketplaces:
            mp_signals = [s for s in signals
                          if s.get("marketplace_id") == mp_id
                          and s.get("signal_type") == "transaction_outcome"]
            if mp_signals:
                completions = sum(1 for s in mp_signals if s.get("outcome") == "completed")
                mp_rates[mp_id] = completions / len(mp_signals) * 100.0

        if len(mp_rates) >= CH_CROSS_PLATFORM_BONUS_THRESHOLD:
            rates = list(mp_rates.values())
            stdev = statistics.stdev(rates) if len(rates) > 1 else 0.0
            if stdev <= CH_CROSS_PLATFORM_CONSISTENCY_THRESHOLD:
                # Scale bonus by consistency (lower stdev = higher bonus)
                bonus = CH_CROSS_PLATFORM_BONUS_MAX * (
                    1.0 - stdev / CH_CROSS_PLATFORM_CONSISTENCY_THRESHOLD
                )
                composite += bonus

    # Cap at 95
    composite = min(95.0, max(0.0, composite))

    signal_count = len(signals)
    confidence = _calculate_confidence(signal_count)
    tier = get_trust_tier(composite)

    return {
        "trust_score": round(composite, 2),
        "trust_tier": tier,
        "dimensions": {
            "reliability": round(reliability, 2),
            "safety": round(safety, 2),
            "capability": round(capability, 2),
            "transparency": round(transparency, 2),
        },
        "confidence": confidence,
        "signal_count": signal_count,
        "marketplace_count": marketplace_count,
        "last_updated": now.isoformat(),
    }


def get_marketplace_scores(marketplace_ids: list) -> dict:
    """Fetch current scores for given marketplaces from DynamoDB.

    Returns:
        Dict of {marketplace_id: marketplace_trust_score} for source weighting.
    """
    if not marketplace_ids:
        return {}

    import boto3

    table_name = os.environ.get("TABLE_NAME", "agentpier-dev")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    scores = {}
    for mp_id in set(marketplace_ids):
        try:
            response = table.get_item(
                Key={"PK": f"MARKETPLACE#{mp_id}", "SK": "PROFILE"}
            )
            item = response.get("Item")
            if item and item.get("marketplace_score") is not None:
                scores[mp_id] = float(item["marketplace_score"])
        except Exception:
            continue

    return scores
