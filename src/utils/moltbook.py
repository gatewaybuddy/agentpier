"""Moltbook API connector for AgentPier.

Verifies Moltbook API keys and fetches agent trust metrics.
Uses www.moltbook.com (non-www strips auth headers).
"""

import logging
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json

logger = logging.getLogger(__name__)

MOLTBOOK_BASE_URL = "https://www.moltbook.com/api/v1"
REQUEST_TIMEOUT = 10  # seconds


def _moltbook_request(path, api_key=None):
    """Make a GET request to the Moltbook API. Returns parsed JSON or raises."""
    url = f"{MOLTBOOK_BASE_URL}{path}"
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        if e.code == 401:
            raise MoltbookAuthError("Invalid Moltbook API key")
        if e.code == 404:
            raise MoltbookNotFoundError("Moltbook agent not found")
        if e.code == 429:
            raise MoltbookRateLimitError("Moltbook API rate limited")
        raise MoltbookAPIError(f"Moltbook API error: {e.code}")
    except URLError as e:
        raise MoltbookAPIError(f"Moltbook API unreachable: {e.reason}")
    except Exception as e:
        raise MoltbookAPIError(f"Moltbook request failed: {e}")


class MoltbookError(Exception):
    """Base error for Moltbook API issues."""


class MoltbookAuthError(MoltbookError):
    """Invalid or expired Moltbook API key."""


class MoltbookNotFoundError(MoltbookError):
    """Agent not found on Moltbook."""


class MoltbookRateLimitError(MoltbookError):
    """Moltbook API rate limited."""


class MoltbookAPIError(MoltbookError):
    """Generic Moltbook API error (timeout, unreachable, etc)."""


def verify_moltbook_key(api_key):
    """DEPRECATED — Do not use. Accepting agent API keys is a trust violation.
    Use challenge-response verification via handlers/moltbook.py instead.
    """
    raise DeprecationWarning(
        "verify_moltbook_key is deprecated. Use challenge-response verification."
    )


def fetch_trust_metrics(agent_name):
    """Fetch public trust metrics for a Moltbook agent by name.

    Calls GET /api/v1/agents/profile?name=X (public endpoint, no auth).
    Returns the profile dict.
    """
    from urllib.parse import quote
    return _moltbook_request(f"/agents/profile?name={quote(agent_name)}")


def calculate_trust_score(moltbook_profile):
    """Calculate a trust score (0.0 - 1.0) from Moltbook profile data.

    Uses the weighted formula from the Phase 3 plan:
    - karma_score (40%): min(karma / 500, 1.0)
    - age_score (30%): min(age_days / 60, 1.0)
    - verification (30%): 0.5 for claimed + 0.5 for has_owner

    Returns dict with trust_score and breakdown.
    """
    agent = moltbook_profile.get("agent", {})

    karma = agent.get("karma", 0)
    if isinstance(karma, str):
        karma = int(karma)
    karma_score = min(karma / 500, 1.0)

    created_at_str = agent.get("created_at", "")
    age_days = 0
    if created_at_str:
        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age_days = max(0, (datetime.now(timezone.utc) - created_at).days)
        except (ValueError, TypeError):
            pass
    age_score = min(age_days / 60, 1.0)

    is_claimed = agent.get("is_claimed", False)
    has_owner = bool(agent.get("owner"))

    verification = 0.0
    if is_claimed:
        verification += 0.5
    if has_owner:
        verification += 0.5

    trust = (karma_score * 0.4) + (age_score * 0.3) + (verification * 0.3)
    trust = round(trust, 2)

    return {
        "trust_score": trust,
        "breakdown": {
            "karma": round(karma_score * 0.4, 2),
            "account_age": round(age_score * 0.3, 2),
            "verification": round(verification * 0.3, 2),
        },
        "raw": {
            "karma": karma,
            "age_days": age_days,
            "is_claimed": is_claimed,
            "has_owner": has_owner,
        },
    }
