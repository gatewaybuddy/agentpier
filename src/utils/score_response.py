"""Score response sanitization for public API.

Ensures that public trust score responses never leak per-marketplace
breakdown or source-identifying information.
"""

# Fields that must be removed from public score responses
_PRIVATE_FIELDS = {
    "marketplace_breakdown",
    "per_source_scores",
    "signal_counts_by_source",
    "source_weights",
    "marketplace_contributions",
    "raw_signals",
    "marketplace_id",
    "source_marketplace",
}

# Fields that are allowed in public score responses
_PUBLIC_FIELDS = {
    "agent_id",
    "overall_score",
    "trust_score",
    "reliability",
    "safety",
    "capability",
    "transparency",
    "dimensions",
    "signal_count",
    "last_updated",
    "confidence",
    "tier",
}


def sanitize_score_response(score_data: dict) -> dict:
    """Remove any per-marketplace breakdown from score responses.

    Public API shows: overall score, dimension scores (reliability, safety,
    capability, transparency).
    Public API NEVER shows: which marketplaces contributed, per-source scores,
    signal counts by source.

    Args:
        score_data: Raw score data dict from the scoring engine.

    Returns:
        Sanitized score dict safe for public API responses.
    """
    sanitized = {}

    for key, value in score_data.items():
        if key in _PRIVATE_FIELDS:
            continue

        # Recursively sanitize nested dicts (e.g. dimensions dict)
        if isinstance(value, dict):
            sanitized[key] = _sanitize_nested(value)
        elif isinstance(value, list):
            sanitized[key] = _sanitize_list(value)
        else:
            sanitized[key] = value

    return sanitized


def _sanitize_nested(data: dict) -> dict:
    """Recursively remove private fields from nested dicts."""
    result = {}
    for key, value in data.items():
        if key in _PRIVATE_FIELDS:
            continue
        if isinstance(value, dict):
            result[key] = _sanitize_nested(value)
        elif isinstance(value, list):
            result[key] = _sanitize_list(value)
        else:
            result[key] = value
    return result


def _sanitize_list(data: list) -> list:
    """Sanitize items in a list."""
    result = []
    for item in data:
        if isinstance(item, dict):
            result.append(_sanitize_nested(item))
        else:
            result.append(item)
    return result
