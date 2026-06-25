"""
examples/demo.py — Airlock redaction demo.

Runs a realistic synthetic agent trace through scrub() + gate() and
prints a clear BEFORE / AFTER view with all findings listed.

Usage:
    python examples/demo.py

No real identifiers are used — all values are RFC-reserved, AWS-documented
examples, or clearly synthetic.
"""

import sys
import os

# Allow running from the repo root without installing the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from airlock.scrubber import scrub, gate

# ---------------------------------------------------------------------------
# A realistic agent trace stuffed with synthetic sensitive data.
# All values are documentation-safe (RFC-reserved / AWS official examples).
# ---------------------------------------------------------------------------

AGENT_TRACE = """\
[2026-06-24T14:32:01Z] AgentRun#7f3a2c1e — inventory task started
  Caller identity: arn:aws:iam::123456789012:user/deploy-agent
  Account: 123456789012  Region: us-east-1

  Probing EC2 in us-east-1...
  → Instance i-0abc1234def56789 at 203.0.113.42 (public), 10.0.1.55 (private)
  → Security group sg-0123456789abcdef0 allows 0.0.0.0/0:443

  S3 buckets found:
    s3://example-prod-data/logs/2026-06/
    s3://example-backups/snapshots/
  Cross-account replication target: --bucket-name example-dr-replica

  Secrets Manager: arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/db-creds-xK8mP2
  Retrieved value: {"password": "s3cr3tP@ssw0rd!", "host": "db.internal.example.net"}

  Lambda env vars on arn:aws:lambda:us-east-1:123456789012:function:data-processor:
    AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
    AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

  Notification endpoint: ops-alerts@example.com
  On-call SMS: 407-555-0192
  Internal dashboard: https://monitoring.internal.example.net/dashboard

[2026-06-24T14:32:04Z] Inventory complete — 2 instances, 3 buckets, 1 function
"""

# ---------------------------------------------------------------------------
# Run scrub() and gate()
# ---------------------------------------------------------------------------

redacted = scrub(AGENT_TRACE)
result = gate(AGENT_TRACE)

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

WIDTH = 72
SEP = "=" * WIDTH

print(SEP)
print("  AIRLOCK — Redaction Demo")
print(SEP)

print("\n--- BEFORE (raw agent trace) " + "-" * (WIDTH - 29))
print(AGENT_TRACE)

print("--- AFTER (scrubbed) " + "-" * (WIDTH - 21))
print(redacted)

print("--- GATE RESULT " + "-" * (WIDTH - 16))
status = "DIRTY — quarantined" if not result["clean"] else "CLEAN — safe to publish"
print(f"  clean: {result['clean']}   status: {status}")
print(f"  findings: {len(result['findings'])}")
print()

for i, f in enumerate(result["findings"], 1):
    print(f"  [{i:02d}] rule={f['rule']}")
    print(f"       match: {f['match_preview']!r}")
    print(f"       → {f['placeholder']}")

print()
print(SEP)
print(f"  {len(result['findings'])} sensitive tokens redacted."
      f"  The lesson survives; the identifiers don't.")
print(SEP)
