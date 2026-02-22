"""Content moderation filter for AgentPier listings.

Blocks illegal, exploitative, and off-topic content.
Logs flagged attempts for review and potential reporting.

NOTE: This is the open-source version. Pattern definitions are stubbed.
The hosted AgentPier service uses an extended pattern set.
To contribute patterns, submit a PR or open an issue.
"""

import os
import re
import time
import unicodedata
from datetime import datetime, timezone

import boto3

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")


# === Text normalization (anti-evasion) ===

# Leetspeak substitution map
_LEET_MAP = str.maketrans({
    "@": "a",
    "0": "o",
    "1": "i",
    "3": "e",
    "$": "s",
    "5": "s",
    "!": "i",
    "+": "t",
    "7": "t",
    # Cyrillic homoglyphs
    "\u0430": "a",  # а
    "\u0435": "e",  # е
    "\u043e": "o",  # о
    "\u0440": "p",  # р
    "\u0441": "c",  # с
    "\u0443": "y",  # у
    "\u0445": "x",  # х
    "\u0456": "i",  # і
    # Greek homoglyphs
    "\u03b1": "a",  # α
    "\u03b5": "e",  # ε
    "\u03bf": "o",  # ο
    "\u03c1": "p",  # ρ
    "\u03c4": "t",  # τ
})

# Zero-width and invisible Unicode characters to strip
_INVISIBLE_RE = re.compile(r"[\u200b\u200c\u200d\u200e\u200f\u2060\ufeff\u00ad\u034f\u17b4\u17b5\u2028\u2029]+")

# Spacing evasion: single chars separated by spaces
_SPACED_LETTERS_RE = re.compile(r"(?<!\S)(\S)\s+(?=\S\s+\S(?:\s|$))(\S)\s+")


def normalize_text(text: str) -> str:
    """Normalize text to defeat common evasion techniques.
    
    1. Strip zero-width / invisible Unicode characters
    2. Collapse spaced-out letters (e.g. "E s c o r t" → "Escort")
    3. Apply leetspeak substitutions
    4. Normalize Unicode (NFKD → strip accents → NFKC)
    """
    if not text:
        return text
    
    # Strip invisible characters
    text = _INVISIBLE_RE.sub("", text)
    
    # Collapse spaced-out single letters
    def _collapse_spaced(t: str) -> str:
        words = t.split()
        result = []
        i = 0
        while i < len(words):
            if len(words[i]) == 1 and words[i].isalpha():
                run = [words[i]]
                j = i + 1
                while j < len(words) and len(words[j]) == 1 and words[j].isalpha():
                    run.append(words[j])
                    j += 1
                if len(run) >= 3:
                    collapsed = "".join(run)
                    result.append(collapsed)
                else:
                    result.extend(run)
                i = j
            else:
                result.append(words[i])
                i += 1
        return " ".join(result)
    
    text = _collapse_spaced(text)
    
    # Leetspeak substitutions
    text = text.translate(_LEET_MAP)
    
    # Unicode normalization
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    text = unicodedata.normalize("NFKC", stripped)
    
    return text


# === Category definitions ===
# STUB: Add your own patterns here or use the hosted AgentPier service.
# Each category should contain regex patterns that trigger a content flag.
# See CONTRIBUTING.md for pattern submission guidelines.
#
# Categories: illegal_drugs, weapons, stolen_data, exploitation,
#             sexually_explicit, financial_scam, gambling, hate_speech,
#             prompt_injection, impersonation, malware

try:
    # Production patterns (private, not in public repo)
    from utils.content_filter_patterns import BLOCKED_CATEGORIES, _DANGEROUS_SUBSTRINGS as _PRIVATE_DANGEROUS
except ImportError:
    # Stub patterns for open-source version
    # Add your own patterns here or use the hosted AgentPier service.
    # See CONTRIBUTING.md for pattern submission guidelines.
    BLOCKED_CATEGORIES = {
        "illegal_drugs": [],
        "weapons": [],
        "stolen_data": [],
        "exploitation": [],
        "sexually_explicit": [],
        "financial_scam": [],
        "gambling": [],
        "hate_speech": [],
        "prompt_injection": [],
        "impersonation": [],
        "malware": [],
    }
    _PRIVATE_DANGEROUS = None

# Severity levels for logging/escalation
SEVERITY = {
    "illegal_drugs": "high",
    "weapons": "high",
    "stolen_data": "high",
    "exploitation": "critical",
    "sexually_explicit": "medium",
    "financial_scam": "high",
    "gambling": "medium",
    "hate_speech": "high",
    "prompt_injection": "medium",
    "impersonation": "medium",
    "malware": "high",
}

# Pre-compile all patterns
_COMPILED = {}
for cat, patterns in BLOCKED_CATEGORIES.items():
    _COMPILED[cat] = [re.compile(p, re.IGNORECASE) for p in patterns]


def _check_text_against_patterns(text: str) -> list[str]:
    """Run text against all compiled patterns, return flagged categories."""
    flagged = []
    for category, patterns in _COMPILED.items():
        for pattern in patterns:
            if pattern.search(text):
                flagged.append(category)
                break
    return flagged


# Dangerous substrings — checked after stripping all non-alpha chars
if _PRIVATE_DANGEROUS is not None:
    _DANGEROUS_SUBSTRINGS = _PRIVATE_DANGEROUS
else:
    # STUB: Add terms relevant to your deployment
    _DANGEROUS_SUBSTRINGS = []


def check_content(text: str) -> tuple[bool, list[str]]:
    """Check text against content filters.
    
    Checks multiple normalizations to defeat evasion:
    1. Standard normalization (leet, unicode, spacing collapse)
    2. All non-alphanumeric stripped (catches any obfuscation)
    3. Ambiguous leet alternate substitutions
    4. CamelCase splitting
    
    Returns:
        (is_clean, flagged_categories)
    """
    if not text:
        return True, []
    
    normalized = normalize_text(text)
    
    # Check normalized text
    flagged = _check_text_against_patterns(normalized)
    
    # Also check with all non-alnum stripped
    if not flagged:
        stripped = re.sub(r'[^a-zA-Z0-9]', '', normalized).lower()
        flagged = _check_text_against_patterns(stripped)
    
    # Substring check for known dangerous terms
    if not flagged:
        stripped = re.sub(r'[^a-zA-Z]', '', normalized).lower()
        for term in _DANGEROUS_SUBSTRINGS:
            if term in stripped:
                if term in ('csam', 'childporn', 'humantraffick'):
                    flagged.append('exploitation')
                elif term in ('hitman', 'assassin'):
                    flagged.append('weapons')
                else:
                    flagged.append('illegal_drugs')
                break
    
    # Ambiguous leet alternate pass (e.g., 0→o→u for "dr0gs"→"drugs")
    if not flagged:
        _LEET_ALT = str.maketrans({"o": "u"})
        alt_stripped = re.sub(r'[^a-zA-Z]', '', normalized).lower().translate(_LEET_ALT)
        for term in _DANGEROUS_SUBSTRINGS:
            if term in alt_stripped:
                if term in ('csam', 'childporn', 'humantraffick'):
                    flagged.append('exploitation')
                elif term in ('hitman', 'assassin'):
                    flagged.append('weapons')
                else:
                    flagged.append('illegal_drugs')
                break

    # CamelCase splitting
    if not flagged:
        spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', normalized).lower()
        flagged = _check_text_against_patterns(spaced)
    
    return len(flagged) == 0, flagged


_BARE_TAG_BLOCKLIST = re.compile(
    r"^(example_blocked_tag)$",  # STUB: Add blocked tag patterns
    re.IGNORECASE,
)


def check_listing_content(title: str, description: str, tags: list[str] = None) -> tuple[bool, list[str]]:
    """Check all text fields of a listing."""
    combined = f"{title} {description} {' '.join(tags or [])}"
    is_clean, flagged = check_content(combined)
    
    for tag in (tags or []):
        normalized_tag = normalize_text(tag).strip()
        if _BARE_TAG_BLOCKLIST.match(normalized_tag):
            if "blocked_tag" not in flagged:
                flagged.append("blocked_tag")
            is_clean = False
    
    return is_clean, flagged


def log_content_violation(user_id: str, listing_data: dict, categories: list[str], client_ip: str = "unknown"):
    """Log a content violation to DynamoDB for review."""
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(TABLE_NAME)
        now = int(time.time())
        now_iso = datetime.now(timezone.utc).isoformat()
        
        import hashlib
        content_sample = f"{listing_data.get('title', '')} {listing_data.get('description', '')[:200]}"
        content_hash = hashlib.sha256(content_sample.encode()).hexdigest()[:16]
        
        max_severity = max(
            (SEVERITY.get(c, "low") for c in categories),
            key=lambda s: {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(s, 0)
        )
        
        table.put_item(Item={
            "PK": f"ABUSE#{user_id}",
            "SK": f"VIOLATION#{now}",
            "user_id": user_id,
            "client_ip": client_ip,
            "categories": categories,
            "severity": max_severity,
            "content_hash": content_hash,
            "title_preview": listing_data.get("title", "")[:100],
            "description_preview": listing_data.get("description", "")[:200],
            "tags": listing_data.get("tags", []),
            "created_at": now_iso,
            "ttl": now + (90 * 86400),
        })
    except Exception:
        pass


def get_user_violation_count(user_id: str, window_seconds: int = 86400) -> int:
    """Count recent violations for a user (default: last 24h)."""
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(TABLE_NAME)
        now = int(time.time())
        window_start = now - window_seconds
        
        response = table.query(
            KeyConditionExpression="PK = :pk AND SK BETWEEN :start AND :end",
            ExpressionAttributeValues={
                ":pk": f"ABUSE#{user_id}",
                ":start": f"VIOLATION#{window_start}",
                ":end": f"VIOLATION#{now + 1}",
            },
            Select="COUNT",
        )
        return response.get("Count", 0)
    except Exception:
        return 0
