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
"""

import math
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


def calculate_ace_score(agent_profile: dict, trust_events: list,
                        now: Optional[datetime] = None) -> dict:
    """Calculate composite ACE-T trust score.
    
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
