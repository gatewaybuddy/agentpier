"""
airlock/scrubber.py — Redaction engine for AI agent traces.

DEFAULT-DENY design: gate() returns clean=False if anything sensitive is
found or if high-entropy strings are present. scrub() always returns
redacted text with typed placeholders so the lesson survives.

Usage:
    from airlock.scrubber import scrub, gate

    redacted = scrub(raw_text)
    result = gate(raw_text)   # {clean: bool, findings: [...], redacted: str}

Denylist configuration:
    The bucket/hostname denylist is EMPTY by default. Add your own internal
    names via the AIRLOCK_BUCKET_DENYLIST environment variable (comma-separated)
    or by calling load_denylist_from_env() at startup:

        export AIRLOCK_BUCKET_DENYLIST="my-prod-bucket,internal.corp.net,staging-data"
        python3 -m airlock.server

    Alternatively, pass names directly:
        from airlock.scrubber import add_to_denylist
        add_to_denylist(["my-prod-bucket", "internal.corp.net"])

    Names are matched case-insensitively, whole-word, including subdomains
    (e.g. adding "corp.net" will also catch "api.corp.net").
"""

import math
import os
import re
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Known-infra denylist — bucket names and hostnames that must always be
# redacted even without s3:// or --bucket context.
#
# DEFAULT: empty. Users populate this with their own internal names via
# the AIRLOCK_BUCKET_DENYLIST env var (comma-separated) or add_to_denylist().
#
# Why configurable rather than hardcoded: Airlock is a general-purpose tool.
# Hardcoding infra names from any particular org would leak that org's topology
# into the OSS release — exactly the class of leak Airlock prevents.
# ---------------------------------------------------------------------------

_BUCKET_DENYLIST: list[str] = []
_DENYLIST_PATTERN: Optional[re.Pattern] = None  # rebuilt whenever list changes


def add_to_denylist(names: list[str]) -> None:
    """Add bucket/hostname names to the denylist and recompile the pattern."""
    global _DENYLIST_PATTERN
    for n in names:
        n = n.strip()
        if n and n not in _BUCKET_DENYLIST:
            _BUCKET_DENYLIST.append(n)
    _recompile_denylist()


def load_denylist_from_env() -> None:
    """
    Load denylist entries from AIRLOCK_BUCKET_DENYLIST env var (comma-separated).
    Call this once at server startup, or before your first scrub() call.

    Example:
        export AIRLOCK_BUCKET_DENYLIST="prod-data,backup-store,internal.corp.net"
    """
    raw = os.environ.get("AIRLOCK_BUCKET_DENYLIST", "")
    names = [n.strip() for n in raw.split(",") if n.strip()]
    if names:
        add_to_denylist(names)


def _recompile_denylist() -> None:
    global _DENYLIST_PATTERN
    if not _BUCKET_DENYLIST:
        _DENYLIST_PATTERN = None
        return
    # Match bare names AND subdomains of denylist entries.
    # Pattern: optional leading label(s) (e.g. "api.") + denylist entry, word-bounded.
    _DENYLIST_PATTERN = re.compile(
        r'(?i)(?:[a-zA-Z0-9][a-zA-Z0-9\-]*\.)*(?:'
        + '|'.join(re.escape(n) for n in _BUCKET_DENYLIST)
        + r')\b'
    )


# ---------------------------------------------------------------------------
# Shannon entropy helpers
# ---------------------------------------------------------------------------

_ENTROPY_MIN_LEN = 20   # strings shorter than this are ignored
_ENTROPY_THRESHOLD = 4.0  # bits/char; real secrets score 4.0+; camelCase tops ~3.7
# Long runs of alphanum/base64 chars — candidates for entropy check
_HIGH_ENTROPY_PATTERN = re.compile(r'[A-Za-z0-9+/=_\-]{20,}')
# UUID v4 — structural identifier, not a secret; excluded from entropy sweep
_UUID_PATTERN = re.compile(
    r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}'
)


def _shannon_entropy(s: str) -> float:
    """Return Shannon entropy in bits per character."""
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    length = len(s)
    return -sum((c / length) * math.log2(c / length) for c in freq.values())


def _looks_like_high_entropy_secret(token: str) -> bool:
    """True if token is long enough and entropic enough to be a secret."""
    # UUIDs are structural identifiers, not secrets
    if _UUID_PATTERN.search(token):
        return False
    return len(token) >= _ENTROPY_MIN_LEN and _shannon_entropy(token) >= _ENTROPY_THRESHOLD


# ---------------------------------------------------------------------------
# Regex rule definitions
# Each rule: (name, pattern, placeholder)
# Order matters — more-specific rules first.
# ---------------------------------------------------------------------------

@dataclass
class Rule:
    name: str
    pattern: re.Pattern
    placeholder: str


def _r(name: str, pattern: str, placeholder: str, flags: int = 0) -> Rule:
    return Rule(name=name, pattern=re.compile(pattern, flags), placeholder=placeholder)


RULES: list[Rule] = [
    # --- Secrets / Keys ---
    _r(
        "AWS_ACCESS_KEY",
        r'\b(A[SK]IA[0-9A-Z]{16})\b',
        "<ACCESS_KEY>",
    ),
    _r(
        "PRIVATE_KEY_BLOCK",
        r'-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----',
        "<PRIVATE_KEY>",
        re.DOTALL,
    ),
    _r(
        "BEARER_TOKEN",
        r'(?i)\bBearer\s+([A-Za-z0-9\-._~+/]+=*)\b',
        "Bearer <SECRET>",
    ),
    _r(
        "PASSWORD_IN_URL",
        r'(?i)(https?://[^:@\s]+:)([^@\s]+)(@)',
        r'\1<SECRET>\3',
    ),
    _r(
        "PASSWORD_IN_CONFIG",
        r'(?i)(password\s*[=:]\s*)([^\s\n"\']{4,})',
        r'\1<SECRET>',
    ),

    # --- AWS identifiers ---
    _r(
        "AWS_ACCOUNT_ID",
        # 12-digit standalone — catch before ARN rule consumes the context
        r'(?<!\d)(\d{12})(?!\d)',
        "<ACCOUNT_ID>",
    ),
    _r(
        "ARN",
        r'arn:[a-z0-9\-]+:[a-z0-9\-]+:[a-z0-9\-]*:[^:\s]*:[^\s"\'<>]+',
        "<ARN>",
    ),
    _r(
        "S3_BUCKET_NAME",
        # Context-keyed: bucket name in common CLI/SDK patterns
        r'(?i)(?:s3://|bucket[_\- ]?name["\s:=]+|Bucket:\s*)([a-z0-9][a-z0-9\-\.]{2,62})',
        "<BUCKET>",
    ),

    # --- Network ---
    _r(
        "PRIVATE_IP_10",
        r'\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
        "<PRIVATE_IP>",
    ),
    _r(
        "PRIVATE_IP_172",
        r'\b172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b',
        "<PRIVATE_IP>",
    ),
    _r(
        "PRIVATE_IP_192",
        r'\b192\.168\.\d{1,3}\.\d{1,3}\b',
        "<PRIVATE_IP>",
    ),
    _r(
        "PUBLIC_IP",
        # IPv4 — after private ranges are already replaced
        r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b',
        "<PUBLIC_IP>",
    ),
    _r(
        "IPV6",
        r'\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b',
        "<IPV6>",
    ),

    # --- PII (before FQDN so email domain isn't consumed by FQDN rule) ---
    _r(
        "EMAIL",
        r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b',
        "<EMAIL>",
    ),

    # --- Infra topology ---
    # NOTE: denylist rule is injected dynamically in _apply_rules() when
    # _DENYLIST_PATTERN is set — it runs here, after EMAIL, before FQDN.

    _r(
        "FQDN",
        # Hostname with at least one dot and a known-length TLD.
        # Placed after IP and email rules so those don't get consumed here.
        r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b',
        "<FQDN>",
    ),
    _r(
        "ABSOLUTE_PATH",
        r'(?<!\w)/(?:[a-zA-Z0-9_.\-]+/){1,}[a-zA-Z0-9_.\-]*',
        "<PATH>",
    ),
    _r(
        "PHONE_US",
        # Separators limited to -, ., space — NOT colon or T (avoids ISO datetime FP).
        r'(?<![:\dA-Za-z])(?:\+1[.\- ]?)?(?:\(?\d{3}\)?[.\- ]\d{3}[.\- ]\d{4})(?![\d:])',
        "<PHONE>",
    ),
]


# ---------------------------------------------------------------------------
# Finding dataclass
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    rule: str
    match: str
    placeholder: str
    position: int


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def scrub(text: str) -> str:
    """Return text with all sensitive data replaced by typed placeholders."""
    result, _ = _apply_rules(text)
    return result


def gate(text: str) -> dict:
    """
    DEFAULT-DENY gate.

    Returns:
        {
          "clean": bool,       # False if anything was found (including entropy)
          "findings": [...],   # list of Finding dicts
          "redacted": str,     # scrubbed text
        }

    clean=False means: quarantine, do not publish.
    """
    redacted, findings = _apply_rules(text)

    # Entropy sweep on the redacted text — catch anything rules missed
    entropy_hits = _entropy_sweep(redacted)
    findings.extend(entropy_hits)

    clean = len(findings) == 0
    return {
        "clean": clean,
        "findings": [
            {
                "rule": f.rule,
                "match_preview": _preview(f.match),
                "placeholder": f.placeholder,
                "position": f.position,
            }
            for f in findings
        ],
        "redacted": redacted,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _apply_rules(text: str) -> tuple[str, list[Finding]]:
    """Apply all regex rules in order, tracking findings."""
    findings: list[Finding] = []
    result = text

    # Build the effective rule list: inject denylist rule between EMAIL and FQDN
    # if any denylist entries are configured.
    effective_rules = list(RULES)
    if _DENYLIST_PATTERN is not None:
        fqdn_idx = next(i for i, r in enumerate(effective_rules) if r.name == "FQDN")
        effective_rules.insert(fqdn_idx, Rule(
            name="DENYLIST_BUCKET",
            pattern=_DENYLIST_PATTERN,
            placeholder="<BUCKET>",
        ))

    for rule in effective_rules:
        def _replace(m: re.Match, rule: Rule = rule) -> str:
            try:
                replaced = rule.pattern.sub(rule.placeholder, m.group(0))
            except re.error:
                replaced = rule.placeholder
            findings.append(Finding(
                rule=rule.name,
                match=m.group(0),
                placeholder=rule.placeholder,
                position=m.start(),
            ))
            return replaced

        result = rule.pattern.sub(_replace, result)

    return result, findings


def _entropy_sweep(text: str) -> list[Finding]:
    """Find high-entropy tokens not already replaced by rules."""
    findings = []
    for m in _HIGH_ENTROPY_PATTERN.finditer(text):
        token = m.group(0)
        # Skip our own placeholders
        if token.startswith('<') and token.endswith('>'):
            continue
        if _looks_like_high_entropy_secret(token):
            findings.append(Finding(
                rule="HIGH_ENTROPY",
                match=token,
                placeholder="<SECRET>",
                position=m.start(),
            ))
    return findings


def _preview(s: str, max_len: int = 40) -> str:
    """Return a safe preview of a matched string for logging."""
    s = s.strip()
    if len(s) <= max_len:
        return s[:4] + "..." if len(s) > 4 else "***"
    return s[:4] + "..." + s[-4:]
