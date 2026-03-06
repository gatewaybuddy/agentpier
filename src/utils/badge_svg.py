"""SVG badge generator for AgentPier trust badges.

Generates inline SVG badges similar to shields.io style.
4 agent tiers with distinct colors, compact and detailed styles.
"""

# Tier colors (background)
TIER_COLORS = {
    "untrusted": "#9e9e9e",
    "provisional": "#9e9e9e",
    "established": "#607d8b",
    "trusted": "#2196f3",
    "highly_trusted": "#4caf50",
    # Marketplace tiers
    "registered": "#9e9e9e",
    "verified": "#4caf50",
    "certified": "#ffc107",
    "enterprise": "#9c27b0",
}

TIER_LABELS = {
    "untrusted": "Untrusted",
    "provisional": "Provisional",
    "established": "Established",
    "trusted": "Trusted",
    "highly_trusted": "Highly Trusted",
    "registered": "Registered",
    "verified": "Verified",
    "certified": "Certified",
    "enterprise": "Enterprise",
}

# Label section color (left side)
_LABEL_BG = "#555"


def _text_width(text: str) -> int:
    """Estimate text width for SVG layout (approximate)."""
    return len(text) * 6 + 10


def generate_compact_badge(tier: str, score: int) -> str:
    """Generate a compact shield badge (~90x20px).

    Shows "AgentPier | Trusted 87" style badge.
    """
    tier_color = TIER_COLORS.get(tier, "#9e9e9e")
    tier_label = TIER_LABELS.get(tier, tier.replace("_", " ").title())
    label_text = "AgentPier"
    value_text = f"{tier_label} {score}"

    label_width = _text_width(label_text)
    value_width = _text_width(value_text)
    total_width = label_width + value_width

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" aria-label="{label_text}: {value_text}">
  <title>{label_text}: {value_text}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{total_width}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="20" fill="{_LABEL_BG}"/>
    <rect x="{label_width}" width="{value_width}" height="20" fill="{tier_color}"/>
    <rect width="{total_width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="11">
    <text aria-hidden="true" x="{label_width / 2}" y="15" fill="#010101" fill-opacity=".3">{label_text}</text>
    <text x="{label_width / 2}" y="14">{label_text}</text>
    <text aria-hidden="true" x="{label_width + value_width / 2}" y="15" fill="#010101" fill-opacity=".3">{value_text}</text>
    <text x="{label_width + value_width / 2}" y="14">{value_text}</text>
  </g>
</svg>"""


def _dimension_bar(label: str, value: float, y: int, width: int = 140) -> str:
    """Generate an SVG bar for a dimension score."""
    bar_width = int((value / 100.0) * width)
    bar_color = "#4caf50" if value >= 70 else "#ffc107" if value >= 40 else "#f44336"
    return f"""  <text x="10" y="{y}" fill="#fff" font-size="10" font-family="Verdana,Geneva,DejaVu Sans,sans-serif">{label}</text>
  <rect x="90" y="{y - 9}" width="{width}" height="10" rx="2" fill="#444"/>
  <rect x="90" y="{y - 9}" width="{bar_width}" height="10" rx="2" fill="{bar_color}"/>
  <text x="{90 + width + 5}" y="{y}" fill="#fff" font-size="10" font-family="Verdana,Geneva,DejaVu Sans,sans-serif">{int(value)}</text>"""


def generate_detailed_badge(tier: str, score: int, dimensions: dict) -> str:
    """Generate a detailed badge (~260x100px) with dimension breakdown.

    Args:
        tier: Trust tier string.
        score: Overall score (0-95).
        dimensions: Dict with reliability, safety, capability, transparency scores.
    """
    tier_color = TIER_COLORS.get(tier, "#9e9e9e")
    tier_label = TIER_LABELS.get(tier, tier.replace("_", " ").title())

    width = 260
    height = 100

    reliability = dimensions.get("reliability", 0)
    safety = dimensions.get("safety", 0)
    capability = dimensions.get("capability", 0)
    transparency = dimensions.get("transparency", 0)

    bars = "\n".join(
        [
            _dimension_bar("Reliability", reliability, 42, 120),
            _dimension_bar("Safety", safety, 56, 120),
            _dimension_bar("Capability", capability, 70, 120),
            _dimension_bar("Transparency", transparency, 84, 120),
        ]
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" role="img" aria-label="AgentPier Trust Badge: {tier_label} {score}">
  <title>AgentPier Trust Badge: {tier_label} {score}</title>
  <rect width="{width}" height="{height}" rx="4" fill="#333"/>
  <rect width="{width}" height="24" rx="4" fill="{tier_color}"/>
  <rect y="20" width="{width}" height="4" fill="{tier_color}"/>
  <text x="10" y="17" fill="#fff" font-size="13" font-weight="bold" font-family="Verdana,Geneva,DejaVu Sans,sans-serif">AgentPier</text>
  <text x="{width - 10}" y="17" fill="#fff" font-size="13" font-weight="bold" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-anchor="end">{tier_label} {score}</text>
{bars}
</svg>"""


def generate_marketplace_badge(tier: str, score: int, style: str = "compact") -> str:
    """Generate a marketplace badge.

    Args:
        tier: Marketplace tier string.
        score: Marketplace score (0-100).
        style: 'compact' or 'detailed'.
    """
    if style == "compact":
        tier_color = TIER_COLORS.get(tier, "#9e9e9e")
        tier_label = TIER_LABELS.get(tier, tier.replace("_", " ").title())
        label_text = "AgentPier"
        value_text = f"Verified Marketplace {score}"

        label_width = _text_width(label_text)
        value_width = _text_width(value_text)
        total_width = label_width + value_width

        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" aria-label="{label_text}: {value_text}">
  <title>{label_text}: {value_text}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{total_width}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="20" fill="{_LABEL_BG}"/>
    <rect x="{label_width}" width="{value_width}" height="20" fill="{tier_color}"/>
    <rect width="{total_width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="11">
    <text aria-hidden="true" x="{label_width / 2}" y="15" fill="#010101" fill-opacity=".3">{label_text}</text>
    <text x="{label_width / 2}" y="14">{label_text}</text>
    <text aria-hidden="true" x="{label_width + value_width / 2}" y="15" fill="#010101" fill-opacity=".3">{value_text}</text>
    <text x="{label_width + value_width / 2}" y="14">{value_text}</text>
  </g>
</svg>"""
    else:
        # Detailed marketplace badge (no dimension bars — marketplaces show score + tier only)
        tier_color = TIER_COLORS.get(tier, "#9e9e9e")
        tier_label = TIER_LABELS.get(tier, tier.replace("_", " ").title())
        width = 260
        height = 50

        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" role="img" aria-label="AgentPier Verified Marketplace: {tier_label} {score}">
  <title>AgentPier Verified Marketplace: {tier_label} {score}</title>
  <rect width="{width}" height="{height}" rx="4" fill="#333"/>
  <rect width="{width}" height="24" rx="4" fill="{tier_color}"/>
  <rect y="20" width="{width}" height="4" fill="{tier_color}"/>
  <text x="10" y="17" fill="#fff" font-size="13" font-weight="bold" font-family="Verdana,Geneva,DejaVu Sans,sans-serif">AgentPier</text>
  <text x="{width - 10}" y="17" fill="#fff" font-size="13" font-weight="bold" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-anchor="end">{tier_label} {score}</text>
  <text x="{width / 2}" y="40" fill="#ccc" font-size="11" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-anchor="middle">Verified Marketplace</text>
</svg>"""
