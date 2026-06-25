# Airlock

**Redaction engine + MCP server for AI agent traces. By AgentPier.**

Airlock is the missing seam between your secret scanner and your PII redactor.
It catches the identifiers that neither tool covers alone: AWS account IDs,
ARNs, private and public IPs, hostnames, emails, access keys, bearer tokens,
and high-entropy secrets — all in one pass, all replaced with typed placeholders
so the lesson survives and the identifier doesn't.

Built to protect war stories: battle-tested lessons from real agent sessions,
published without the infra details that would make them a reconnaissance target.

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

## Quick start

```bash
git clone https://github.com/agentpier/airlock.git
cd airlock
python3 -m pytest airlock/tests/ -v
```

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
python3 -m airlock.server
```

### Start the MCP server

```bash
PYTHONPATH=/path/to/parent-of-airlock python3 airlock/server.py
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
keeps the OSS release from embedding any org's topology.

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
PYTHONPATH=/path/to/parent-of-airlock python3 -m pytest airlock/tests/ -v
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
