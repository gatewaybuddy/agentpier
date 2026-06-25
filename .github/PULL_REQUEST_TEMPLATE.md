## What this PR does

<!-- One paragraph summary. Link to the issue it closes if applicable. -->

Closes #

## Type of change

- [ ] Bug fix (new rule or false-positive correction)
- [ ] New rule (adds a new category of sensitive data)
- [ ] Enhancement (improves an existing rule or the MCP server)
- [ ] Docs / examples

## Checklist

- [ ] Tests added for all new behaviour (see CONTRIBUTING.md for fixture conventions)
- [ ] No real credentials, IPs, account IDs, or hostnames in tests — RFC-reserved values only
- [ ] Full test suite passes: `PYTHONPATH=. pytest airlock/tests/ -v`
- [ ] `scrubber.py` docstring updated if the rule list changed
- [ ] No new external dependencies

## Demo (optional)

<!-- Paste `python examples/demo.py` output or a short before/after snippet showing the change. -->
