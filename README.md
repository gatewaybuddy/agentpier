# Airlock

[![CI](https://github.com/gatewaybuddy/agentpier/actions/workflows/ci.yml/badge.svg)](https://github.com/gatewaybuddy/agentpier/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12-blue.svg)](pyproject.toml)
[![PyPI](https://img.shields.io/pypi/v/agentpier-airlock.svg)](https://pypi.org/project/agentpier-airlock/)

**Redaction engine + MCP server for AI agent traces. By AgentPier.**

Airlock is the missing seam between your secret scanner and your PII redactor.
It catches the identifiers that neither tool covers alone: AWS account IDs,
ARNs, private and public IPs, hostnames, emails, access keys, bearer tokens,
and high-entropy secrets — all in one pass, all replaced with typed placeholders
so the lesson survives and the identifier doesn't.

Built to protect war stories: battle-tested lessons from real agent sessions,
published without the infra details that would make them a reconnaissance target.

---

## Quickstart

```bash
pip install agentpier-airlock
python -c "from airlock.scrubber import scrub; print(scrub('account 123456789012 at 10.0.0.5'))"
# → account <ACCOUNT_ID> at <PRIVATE_IP>
```

Or run the demo:

```bash
git clone https://github.com/gatewaybuddy/agentpier.git
cd agentpier
python examples/demo.py
```

---

## Demo output

```
========================================================================
  AIRLOCK — Redaction Demo
========================================================================

--- BEFORE (raw agent trace) -------------------------------------------
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

--- AFTER (scrubbed) ---------------------------------------------------
[2026-06-24T14:32:01Z] AgentRun#7f3a2c1e — inventory task started
  Caller identity: <ARN>
  Account: <ACCOUNT_ID>  Region: us-east-1

  Probing EC2 in us-east-1...
  → Instance i-0abc1234def56789 at <PUBLIC_IP> (public), <PRIVATE_IP> (private)
  → Security group sg-0123456789abcdef0 allows <PUBLIC_IP>/0:443

  S3 buckets found:
    <BUCKET><PATH>
    <BUCKET><PATH>
  Cross-account replication target: --<BUCKET>

  Secrets Manager: <ARN>
  Retrieved value: {"password": "s3cr3tP@ssw0rd!", "host": "<FQDN>"}

  Lambda env vars on <ARN>
    AWS_ACCESS_KEY_ID=<ACCESS_KEY>
    AWS_SECRET_ACCESS_KEY=<SECRET>

  Notification endpoint: <EMAIL>
  On-call SMS: <PHONE>
  Internal dashboard: https://<FQDN>/dashboard

[2026-06-24T14:32:04Z] Inventory complete — 2 instances, 3 buckets, 1 function

--- GATE RESULT --------------------------------------------------------
  clean: False   status: DIRTY — quarantined
  findings: 22

========================================================================
  22 sensitive tokens redacted.  The lesson survives; the identifiers don't.
========================================================================
```

---

## What it catches

| Category | Examples | Placeholder |
|---|---|---|
| AWS access keys | `AKIA...` | `<ACCESS_KEY>` |
| Private key blocks | `-----BEGIN RSA PRIVATE KEY-----` | `<SECRET>` |
| Bearer tokens / passwords | `Authorization: Bearer ...` | `<SECRET>` |
| AWS account IDs | 12-digit numeric IDs | `<ACCOUNT_ID>` |
| ARNs | `arn:aws:...` | `<ARN>` |
| S3 bucket names (in URIs) | `s3://my-bucket/` | `<BUCKET>` |
| Private IPs | RFC 1918 (10.x, 172.16–31.x, 192.168.x) | `<PRIVATE_IP>` |
| Public IPs | Routable IPv4 | `<PUBLIC_IP>` |
| Hostnames / FQDNs | `api.example.com` | `<FQDN>` |
| Email addresses | `user@example.com` | `<EMAIL>` |
| US phone numbers | `407-555-0192` | `<PHONE>` |
| Absolute paths | `/home/user/.ssh/id_rsa` | `<PATH>` |
| High-entropy strings | Tokens, UUIDs-as-secrets (Shannon > 4.0 bits/char) | flagged by gate |
| **Your infra names** | Bucket/host names you configure | `<BUCKET>` |

---

## Usage

### Scrub a string

```python
from airlock.scrubber import scrub, gate

text = "Deployed to account 123456789012, endpoint api.example.com"

# scrub() — always redacts, returns clean string
print(scrub(text))
# → "Deployed to account <ACCOUNT_ID>, endpoint <FQDN>"

# gate() — DEFAULT-DENY: returns clean=False on ANY finding
result = gate(text)
print(result["clean"])    # False
print(result["findings"]) # [{rule: "AWS_ACCOUNT_ID", ...}, ...]
```

### Add your org's infra names to the denylist

```python
from airlock.scrubber import add_to_denylist
add_to_denylist(["my-prod-bucket", "internal.corp.net"])
```

Or via environment variable (for MCP server deployments):

```bash
export AIRLOCK_BUCKET_DENYLIST="my-prod-bucket,internal.corp.net,staging-data"
airlock-mcp
```

### Start the MCP server

```bash
# As a console script (after pip install):
AIRLOCK_BUCKET_DENYLIST="my-bucket" airlock-mcp

# Or directly from the repo:
PYTHONPATH=. python airlock/server.py
```

See `airlock/SKILL.md` for Claude Code / Cursor install config.

---

## Safety design

**DEFAULT-DENY gate**: `gate()` returns `clean=False` if *anything* sensitive
is found. There is no partial-clean state. A story either passes the gate
completely or it is quarantined.

**Double-gating**:
1. Gate on ingest — story is rejected if dirty; not stored
2. Scrub on egress — every return path runs `scrub()` (defense-in-depth)

**Denylist is empty by default**: Airlock ships with zero hardcoded infra names.
You bring your own via `AIRLOCK_BUCKET_DENYLIST` or `add_to_denylist()`. This
keeps the library from embedding any org's topology.

---

## MCP tools

| Tool | Description |
|---|---|
| `submit_story` | Submit a war story. Gate-on-ingest: rejected with findings if dirty. |
| `search_stories` | Keyword + tag search. All results scrubbed on egress. |
| `get_story` | Fetch story by UUID. Scrubbed on egress. |

See `airlock/SKILL.md` for the full install guide and MCP config snippet.

---

## Schema

Stories follow the AgentErrorTaxonomy. Required fields: `id`, `title`,
`situation`, `goal`, `what_i_tried`, `what_failed`, `what_worked`, `lesson`,
`tags`, `narrator_id`, `timestamp`, `trust`. At least one taxonomy tag is
required: `memory | reflection | planning | action | system`.

See `airlock/STORY_TEMPLATE.md` for the fill-in-the-blanks template.

---

## Running tests

```bash
# From the repo root
PYTHONPATH=. python -m pytest airlock/tests/ -v
```

The test suite includes unit tests for the scrubber (41 tests), handler tests
(18 tests), and end-to-end subprocess smoke tests speaking real JSON-RPC 2.0
wire protocol (10 tests). All fixtures use RFC-reserved / AWS-documented
identifiers — no real infrastructure values.

---

## License

Apache 2.0. See [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
