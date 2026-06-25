---
name: Feature request
about: New rule, improvement, or integration idea
title: "[FEATURE] "
labels: enhancement
assignees: ''
---

## What problem does this solve?

<!-- What sensitive data is currently not caught, or what workflow is painful? -->

## Proposed solution

<!-- Describe the change. For a new rule: what pattern, what placeholder, what test fixtures? -->

## Example

```python
# Input that should be caught (use RFC-reserved / documented values only):
text = "some text with 203.0.113.99 in it"

# Expected after fix:
# gate(text)["clean"] == False
# scrub(text) == "some text with <PUBLIC_IP> in it"
```

## False positive risk

<!-- Could this rule accidentally redact legitimate text? Give an example if so. -->

## Alternatives considered

<!-- Any other approaches you considered? -->
