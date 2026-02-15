"""Content moderation filter for AgentPier listings.

Blocks illegal, exploitative, and off-topic content.
Logs flagged attempts for review and potential reporting.
"""

import os
import re
import time
from datetime import datetime, timezone

import boto3

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")

# === Category definitions ===
# Each category has patterns that trigger a flag.
# We intentionally don't tell users WHICH pattern matched.

BLOCKED_CATEGORIES = {
    "illegal_drugs": [
        r"\b(sell|buy|order|ship)\b.{0,30}\b(cocaine|heroin|fentanyl|meth|mdma|lsd|shrooms|psilocybin|ketamine|xanax|oxycontin|oxycodone|adderall)\b",
        r"\b(drug\s*deal|narcotics|controlled\s*substance)\b",
        r"\b(dark\s*web|darknet)\s*(market|shop|vendor)\b",
    ],
    "weapons": [
        r"\b(sell|buy|order|ship)\b.{0,30}\b(gun|firearm|rifle|pistol|ammunition|ammo|explosive|grenade)\b",
        r"\b(ghost\s*gun|3d\s*print\w*\s*gun|unregistered\s*(weapon|firearm))\b",
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
        r"\b(fake\s*(id|passport|license|document|diploma))\b",
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
        r"\b(fake|forged|counterfeit)\s*(review|rating|credential|certification)\b",
        r"\b(buy|sell|boost)\s*(review|rating|follower|like|upvote)\b",
        r"\b(impersonat|pretend\s*to\s*be|pose\s*as)\b",
    ],
    "malware": [
        r"\b(malware|ransomware|trojan|keylogger|rootkit|spyware)\b",
        r"\b(ddos|denial\s*of\s*service)\s*(attack|service|tool|for\s*hire)\b",
        r"\b(exploit\s*kit|zero\s*day|0day)\s*(for\s*sale|buy|sell)\b",
        r"\b(botnet|rat\s*tool|remote\s*access\s*trojan)\b",
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
    "prompt_injection": "medium",
    "impersonation": "medium",
    "malware": "high",
}

# Pre-compile all patterns
_COMPILED = {}
for cat, patterns in BLOCKED_CATEGORIES.items():
    _COMPILED[cat] = [re.compile(p, re.IGNORECASE) for p in patterns]


def check_content(text: str) -> tuple[bool, list[str]]:
    """Check text against content filters.
    
    Returns:
        (is_clean, flagged_categories) — True if content passes, 
        list of matched category names if blocked.
    """
    if not text:
        return True, []
    
    flagged = []
    for category, patterns in _COMPILED.items():
        for pattern in patterns:
            if pattern.search(text):
                flagged.append(category)
                break  # One match per category is enough
    
    return len(flagged) == 0, flagged


def check_listing_content(title: str, description: str, tags: list[str] = None) -> tuple[bool, list[str]]:
    """Check all text fields of a listing.
    
    Returns:
        (is_clean, flagged_categories)
    """
    combined = f"{title} {description} {' '.join(tags or [])}"
    return check_content(combined)


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
