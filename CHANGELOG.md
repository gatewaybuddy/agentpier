# Changelog

All notable changes to Airlock are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Airlock uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2026-06-25

Initial public release.

### Added

**Redaction engine (`airlock/scrubber.py`)**
- `scrub(text)` — redacts all sensitive tokens in one pass, returns clean string with typed placeholders
- `gate(text)` — DEFAULT-DENY: returns `{clean, findings, redacted}`; `clean=False` on any finding
- Rules (in priority order): AWS access keys, private key blocks, bearer tokens, passwords in URLs/config, AWS account IDs, ARNs, S3 bucket URIs, private IPs (RFC 1918), public IPs, IPv6, email addresses, FQDNs, absolute paths, US phone numbers
- Shannon entropy sweep (threshold 4.0 bits/char, min 20 chars) catches high-entropy secrets rules miss
- Configurable denylist: empty by default; populate via `AIRLOCK_BUCKET_DENYLIST` env var (comma-separated) or `add_to_denylist(["name", ...])`; matches bare names AND subdomains

**Story schema and store (`airlock/schema.py`, `airlock/store.py`)**
- War story schema with required AgentErrorTaxonomy tag (`memory | reflection | planning | action | system`)
- `validate_story()`, `scrub_story()` (scrubs all fields, attaches gate snapshot to trust)
- SQLite-backed `StoryStore` with full-text search across all narrative fields
- `_flatten()` helper handles `str | list[str] | None` field types correctly

**MCP server (`airlock/server.py`)**
- Spec-correct JSON-RPC 2.0 over stdio (no SDK dependency)
- Tools: `submit_story` (gate-on-ingest), `search_stories` (scrub-on-egress), `get_story` (scrub-on-egress)
- Double-gating: reject dirty on ingest + scrub every egress path
- `airlock-mcp` console script entry point
- Error codes: -32700 parse, -32601 method-not-found, -32602 invalid-params, -32000 server error

**Seed corpus (`airlock/seed_stories.py`)**
- 3 verified war stories: "Scoped deploy key surprises", "Inventory before deletion", "The quiet identifiers are louder than the key"
- All pass `gate()` clean on every load

**Test suite**
- 69 tests: 41 scrubber unit tests, 18 MCP handler tests, 10 end-to-end subprocess smoke tests
- All fixtures use RFC-reserved / AWS-documented identifiers only
- `conftest.py` autouse fixture ensures hermetic isolation (denylist + store reset per test)

**Packaging and repo**
- `pyproject.toml` (PEP 621, distribution name `agentpier-airlock`)
- GitHub Actions CI matrix: Python 3.10, 3.11, 3.12
- `examples/demo.py` — runnable before/after demo
- Apache 2.0 license
