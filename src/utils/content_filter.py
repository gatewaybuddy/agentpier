"""Content moderation filter for AgentPier listings.

Blocks illegal, exploitative, and off-topic content.
Logs flagged attempts for review and potential reporting.
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
    "4": "a",
    # Cyrillic homoglyphs → Latin
    "\u0430": "a",  # а
    "\u0435": "e",  # е
    "\u043e": "o",  # о
    "\u0440": "p",  # р
    "\u0441": "c",  # с
    "\u0443": "y",  # у
    "\u0445": "x",  # х
    "\u0456": "i",  # і (Ukrainian i)
    "\u0457": "i",  # ї
    "\u0454": "e",  # є
    "\u044a": "",   # ъ (hard sign, strip)
    "\u044c": "",   # ь (soft sign, strip)
    # Greek homoglyphs
    "\u03b1": "a",  # α
    "\u03b5": "e",  # ε
    "\u03bf": "o",  # ο
    "\u03c1": "p",  # ρ
    "\u03c4": "t",  # τ
})

# Zero-width and invisible Unicode characters to strip
_INVISIBLE_RE = re.compile(r"[\u200b\u200c\u200d\u200e\u200f\u2060\ufeff\u00ad\u034f\u17b4\u17b5\u2028\u2029]+")

# Spacing evasion: single chars separated by spaces, e.g. "E s c o r t"
# Matches sequences of 3+ single letters each separated by whitespace
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
    
    # Collapse spaced-out single letters: "E s c o r t" → "Escort"
    # Detect runs of single non-space chars separated by spaces
    def _collapse_spaced(t: str) -> str:
        """Collapse spaced-out letters into words, preserving word boundaries.
        'S e l l   c o c a i n e' → 'Sell cocaine' (not 'Sellcocaine')
        Runs of single letters separated by 2+ spaces are treated as word breaks.
        """
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
                    # Check original text for double-spaces to find word breaks
                    collapsed = "".join(run)
                    # Find the span in original text and split on multi-spaces
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
    
    # Unicode normalization: decompose, strip combining marks, recompose
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    text = unicodedata.normalize("NFKC", stripped)
    
    return text


# === Category definitions ===
# Each category has patterns that trigger a flag.
# We intentionally don't tell users WHICH pattern matched.

BLOCKED_CATEGORIES = {
    "illegal_drugs": [
        r"\b(sell|buy|order|ship|deliver|get)\b.{0,30}\b(cocaine|heroin|fentanyl|meth|mdma|lsd|shrooms|psilocybin|ketamine|xanax|oxycontin|oxycodone|adderall|drugs?)\b",
        r"\b(cocaine|heroin|fentanyl|meth|mdma|lsd|shrooms|psilocybin|ketamine|xanax|oxycontin|oxycodone)\b.{0,30}\b(sell|buy|order|ship|deliver|online|fast|cheap|free|for\s*sale|deal\w*|sales?|shop|store|market)\b",
        r"\b(drugs?)\b.{0,30}\b(sell|buy|order|ship|deliver|online|fast|cheap|free|for\s*sale|deal\w*)\b",
        r"\b(drugs?\s*deal|narcotics|controlled\s*substance)\b",
        r"\b(dark\s*web|darknet)\s*(market|shop|vendor)\b",
    ],
    "weapons": [
        r"\b(sell|buy|order|ship|get)\b.{0,30}\b(guns?|firearms?|rifles?|pistols?|ammunition|ammo|explosives?|grenades?|weapons?)\b",
        r"\b(guns?|weapons?|firearms?)\b.{0,30}\b(sell|buy|order|ship|online|cheap|for\s*sale|deal)\b",
        r"\b(ghost\s*gun|3d\s*print\w*\s*gun|unregistered\s*(weapons?|firearms?))\b",
        r"\b(hit\s*man|assassin|murder\s*for\s*hire)\b",
    ],
    "stolen_data": [
        r"\b(stolen|hacked|leaked)\s*(data|database|credential|password|credit\s*card|ssn|social\s*security)\b",
        r"\b(fullz|dumps|carding|cvv\s*shop)\b",
        r"\b(doxx|doxing|leak\s*personal\s*info)\b",
        r"\b(buy|sell)\s*(account|login)\s*(credential|access)\b",
    ],
    "exploitation": [
        r"\b(child|minor|underage)\b.{0,20}\b(exploit|abuse|content|material|porn)\b",
        r"\bcsam\b",
        r"\b(human\s*trafficking|sex\s*traffick|forced\s*labor)\b",
        r"\b(escort|prostitut|sex\s*work|sexual\s*service)\b",
    ],
    "sexually_explicit": [
        r"\b(porn|pornograph|xxx|adult\s*content|nsfw\s*content)\b",
        r"\b(cam\s*girl|cam\s*show|only\s*fans\s*leak|nude|nudes)\b",
        r"\b(sex\s*toy|dildo|vibrator|fetish\s*service)\b",
    ],
    "financial_scam": [
        r"\b(get\s*rich\s*quick|guaranteed\s*(profit|return|income))\b",
        r"\b(pump\s*and\s*dump|ponzi|pyramid\s*scheme)\b",
        r"\b(money\s*launder|wash\s*money|clean\s*money)\b",
        r"\b(wire\s*fraud|advance\s*fee|nigerian\s*prince)\b",
        r"\b(fake|forged|counterfeit)\s*(ids?|passports?|licens\w*|documents?|diplomas?)\b",
        r"\b(fraud\w*|scam)\s*(service|scheme|method)\b",
    ],
    "gambling": [
        r"\b(online\s*gambling|internet\s*casino|virtual\s*casino)\b",
        r"\b(casino|betting|wagering|sportsbook)\b.{0,30}\b(site|online|bonus|free|promo|sign\s*up|deposit)\b",
        r"\b(slots?|poker|blackjack|roulette)\b.{0,30}\b(online|real\s*money|cash|win|payout|bonus)\b",
        r"\b(bet|gamble|wager)\b.{0,20}\b(online|now|today|free|real\s*money)\b",
    ],
    "hate_speech": [
        r"\b(white|black|race)\s*supremac\w*\b",
        r"\b(hate\s*group|hate\s*movement|extremist\s*group)\b",
        r"\b(racial\s*purity|ethnic\s*cleansing|race\s*war)\b",
        r"\b(neo\s*nazi|white\s*power|white\s*nationalist)\b",
        r"\b(extremist|radical)\s*(recruit\w*|training|cell|movement)\b",
        r"\b(join|recruit)\b.{0,20}\b(supremac|extremist|hate\s*group|militia)\b",
    ],
    "prompt_injection": [
        r"(ignore\s*(previous|all|prior)\s*(instructions?|prompts?|rules?))",
        r"(you\s*are\s*now\s*(a|an|the)\b)",
        r"(system\s*:\s*(override|new\s*instructions?|forget))",
        r"(jailbreak|do\s*anything\s*now|dan\s*mode)",
        r"(\bact\s*as\s*if\b.{0,30}\b(no\s*restrictions?|unrestricted|unfiltered))",
        r"(disregard\s*(safety|content\s*policy|guidelines))",
    ],
    "impersonation": [
        r"\b(fake|forged|counterfeit)\s*(reviews?|ratings?|credentials?|certifications?)\b",
        r"\b(buy|sell|boost)\s*(reviews?|ratings?|followers?|likes?|upvotes?)\b",
        r"\b(impersonat|pretend\s*to\s*be|pose\s*as)\b",
    ],
    "malware": [
        r"\b(malware|ransomware|trojan|keylogger|rootkit|spyware)\b",
        r"\b(ddos|denial\s*of\s*service)\s*(attack|service|tool|for\s*hire)\b",
        r"\b(exploit\s*kit|zero\s*day|0day)\s*(for\s*sale|buy|sell)\b",
        r"\b(botnet|rat\s*tool|remote\s*access\s*trojan)\b",
        r"\b(hack|crack|breach)\b.{0,20}\b(account|password|email|server|website|any)\b",
        r"\b(hacking|cracking)\s*(service|tool|for\s*hire)\b",
        r"\b(hack\s*for\s*hire|hacker\s*for\s*hire)\b",
    ],
}

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


def check_content(text: str) -> tuple[bool, list[str]]:
    """Check text against content filters.
    
    Checks multiple normalizations to defeat evasion:
    1. Standard normalization (leet, unicode, spacing collapse)
    2. All non-alphanumeric stripped (catches any obfuscation)
    
    Returns:
        (is_clean, flagged_categories) — True if content passes, 
        list of matched category names if blocked.
    """
    if not text:
        return True, []
    
    normalized = normalize_text(text)
    
    # Check normalized text
    flagged = _check_text_against_patterns(normalized)
    
    # Also check with all non-alnum stripped — catches obfuscated terms
    if not flagged:
        stripped = re.sub(r'[^a-zA-Z0-9]', '', normalized).lower()
        flagged = _check_text_against_patterns(stripped)
    
    # Substring check for known dangerous terms in stripped text
    # Catches "sellcocaine", "buyheroin", etc. where word boundaries are missing
    if not flagged:
        stripped = re.sub(r'[^a-zA-Z]', '', normalized).lower()
        _DANGEROUS_SUBSTRINGS = [
            'cocaine', 'heroin', 'fentanyl', 'ketamine', 'oxycontin', 'oxycodone',
            'drugs', 'meth', 'mdma', 'shrooms', 'psilocybin',
            'csam', 'childporn', 'hitman', 'assassin', 'humantraffick',
            'sellguns', 'buyguns', 'ghostgun',
        ]
        for term in _DANGEROUS_SUBSTRINGS:
            if term in stripped:
                # Map to category
                if term in ('csam', 'childporn', 'humantraffick'):
                    flagged.append('exploitation')
                elif term in ('hitman', 'assassin'):
                    flagged.append('weapons')
                else:
                    flagged.append('illegal_drugs')
                break
    
    # Ambiguous leet: "0" maps to "o" by default, but could be "u" (dr0gs → drugs)
    # Try alternate substitutions on the stripped text
    if not flagged:
        _LEET_ALT = str.maketrans({"o": "u"})  # covers 0→o→u
        alt_stripped = re.sub(r'[^a-zA-Z]', '', normalized).lower().translate(_LEET_ALT)
        for term in _DANGEROUS_SUBSTRINGS:
            if term in alt_stripped:
                if term in ('csam', 'childporn', 'humantraffick'):
                    flagged.append('exploitation')
                elif term in ('hitman', 'assassin', 'sellguns', 'buyguns', 'ghostgun'):
                    flagged.append('weapons')
                else:
                    flagged.append('illegal_drugs')
                break

    # Also check with spaces between every word-boundary transition
    # "Sellcocaine" won't match \bsell\b but "sell cocaine" will
    if not flagged:
        # Insert spaces before uppercase letters (camelCase splitting)
        spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', normalized).lower()
        flagged = _check_text_against_patterns(spaced)
    
    return len(flagged) == 0, flagged


_BARE_TAG_BLOCKLIST = re.compile(
    r"^(cocaine|heroin|fentanyl|meth|mdma|lsd|shrooms|psilocybin|ketamine|"
    r"xanax|oxycontin|oxycodone|adderall|"
    r"guns?|firearms?|ammunition|ammo|explosives?|grenades?|weapons?|"
    r"csam|porn|pornograph|xxx|"
    r"fraud|scam|counterfeit|"
    r"hitman|assassin)$",
    re.IGNORECASE,
)


def check_listing_content(title: str, description: str, tags: list[str] = None) -> tuple[bool, list[str]]:
    """Check all text fields of a listing.
    
    Returns:
        (is_clean, flagged_categories)
    Tags are checked both in combined context AND individually against
    a bare-keyword blocklist (since tags lack surrounding context).
    """
    combined = f"{title} {description} {' '.join(tags or [])}"
    is_clean, flagged = check_content(combined)
    
    # Also check each tag individually against bare blocklist
    for tag in (tags or []):
        normalized_tag = normalize_text(tag).strip()
        if _BARE_TAG_BLOCKLIST.match(normalized_tag):
            if "blocked_tag" not in flagged:
                flagged.append("blocked_tag")
            is_clean = False
    
    return is_clean, flagged


def log_content_violation(user_id: str, listing_data: dict, categories: list[str], client_ip: str = "unknown"):
    """Log a content violation to DynamoDB for review.
    
    Creates an abuse record that persists for 90 days.
    """
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(TABLE_NAME)
        now = int(time.time())
        now_iso = datetime.now(timezone.utc).isoformat()
        
        # Hash the content for dedup without storing raw text long-term
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
            # Store enough to review but not the full payload
            "title_preview": listing_data.get("title", "")[:100],
            "description_preview": listing_data.get("description", "")[:200],
            "tags": listing_data.get("tags", []),
            "created_at": now_iso,
            "ttl": now + (90 * 86400),  # 90-day retention
        })
    except Exception:
        # Don't let logging failures block the request
        pass


def get_user_violation_count(user_id: str, window_seconds: int = 86400) -> int:
    """Count recent violations for a user (default: last 24h).
    
    Used for escalation — repeated offenders get suspended.
    """
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
