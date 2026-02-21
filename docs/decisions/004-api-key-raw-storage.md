# ADR-004: Store Raw API Key for Login Retrieval

**Date**: 2026-02-21  
**Status**: Accepted  
**Context**: Phase 3A Generic Profiles

## Decision

Store the raw (unhashed) API key in the DynamoDB APIKEY record (`api_key_raw` field) so that `POST /auth/login` can return it.

## Context

The new login flow authenticates with username + password and returns the existing API key. Without the raw key stored, login cannot return it — defeating the purpose of username/password auth.

The alternative (rotate key on every login) was rejected because it would invalidate existing integrations every time an agent logs in.

## Consequences

- **Pro**: Login works as designed — agents authenticate once with password, get their API key
- **Pro**: No key rotation on login means existing integrations stay valid
- **Con**: Raw API key stored alongside hash — if DynamoDB is compromised, attacker gets usable keys
- **Mitigation**: DynamoDB encryption at rest is enabled; IAM policies restrict access; key rotation endpoint exists if compromise is suspected

## Alternatives Considered

1. **Rotate key on login** — rejected: breaks existing integrations
2. **Don't support login key retrieval** — rejected: defeats the purpose of username/password flow
3. **Encrypt raw key with KMS** — future enhancement if security review requires it
