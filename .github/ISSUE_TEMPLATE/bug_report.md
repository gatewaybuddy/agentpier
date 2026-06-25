---
name: Bug report
about: Something isn't working
title: "[BUG] "
labels: bug
assignees: ''
---

## What happened

<!-- Describe what went wrong. -->

## What you expected

<!-- What should have happened instead? -->

## Reproducer

```python
# Minimal code to reproduce the problem
from airlock.scrubber import scrub, gate

text = "..."
print(gate(text))
```

## Environment

- Python version: <!-- e.g. 3.12.3 -->
- airlock version: <!-- e.g. 0.1.0 or commit hash -->
- OS: <!-- e.g. Ubuntu 22.04, macOS 14 -->

## Additional context

<!-- Paste relevant output, tracebacks, or gate() findings here. -->
<!-- IMPORTANT: Do not include real credentials, IPs, account IDs, or hostnames. -->
<!-- Use RFC-reserved values (203.0.113.x, example.com, 123456789012) instead. -->
