# Contributing to Airlock

Thanks for the interest. A few ground rules before you send a PR.

---

## What belongs here

- New redaction rules (with tests proving the before/after)
- False positive fixes (tests that prove the clean text now passes gate)
- Performance improvements to the scrubber / store
- New MCP tools (follow the pattern in `server.py::_TOOLS`)
- Bug fixes with regression tests

## What doesn't belong here

- Hardcoded infra names, internal bucket names, or org-specific identifiers
- Real credentials of any kind (even in tests — use RFC-reserved ranges)
- Cloud provider integrations (keep it local-first, no SDK deps)

---

## Fixture conventions

All test fixtures must use documentation-safe values:

| Type | Use |
|---|---|
| AWS account ID | `123456789012` (AWS official example) |
| AWS access key | `AKIAIOSFODNN7EXAMPLE` (AWS official example) |
| Public IP | `203.0.113.x` (RFC 5737 TEST-NET-3) |
| Private IP | `10.0.0.x` or `192.168.x.x` (RFC 1918) |
| FQDN | `example.com`, `example.net` (RFC 2606) |
| Email | `user@example.com` (RFC 2606) |
| Bucket name | `example-media-bucket`, `example-backups` |

Never use real account IDs, IPs, hostnames, emails, or bucket names in tests.
The scrubber's own rules will fire on them and make test outcomes depend on
what's in the denylist at runtime.

---

## Running tests

```bash
# From the repo root (parent of airlock/)
PYTHONPATH=. python3 -m pytest airlock/tests/ -v
```

All three suites must pass: `test_scrubber`, `test_mcp_handlers`, `test_e2e_server`.

---

## Adding a new rule

1. Add the compiled pattern to `scrubber.py::RULES` in the right position
   (specificity-ordered: more specific rules first).
2. Add a placeholder string — e.g. `<MY_THING>`.
3. Write a test class in `tests/test_scrubber.py`:
   - `test_redacted` — raw value → expected placeholder present
   - `test_gate_dirty` — gate returns clean=False
   - `test_not_in_redacted` — raw value not in scrubbed output
4. Add a false-positive test: text that looks similar but should pass gate.
5. Run the full suite and confirm nothing regresses.

---

## PR checklist

- [ ] Tests added for any new rule or behaviour
- [ ] No real identifiers in fixtures
- [ ] Full suite green (`pytest airlock/tests/ -v`)
- [ ] `scrubber.py` docstring updated if rule list changed
- [ ] No new external dependencies added
