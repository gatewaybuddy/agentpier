# ADR-005: API Keys Returned Once Only, Rotation for Lost Keys

**Date**: 2026-02-21  
**Status**: Accepted  
**Context**: Phase 3A Generic Profiles Security Fix

## Decision

- API keys are returned **only once** at registration time
- Raw API keys are **never stored** in DynamoDB (hash only)
- Lost keys are recovered via `POST /auth/rotate-key` endpoint
- Login returns success confirmation but **not** the API key

## Context

ADR-004 approved storing raw API keys to support login key retrieval, but this created a security vulnerability. If the database is compromised, attackers get immediately usable API keys rather than just hashes.

The convenience of login returning the API key does not justify the security risk.

## Implementation

1. **Registration** (`POST /auth/register`): Returns API key once, stores hash only
2. **Login** (`POST /auth/login`): Authenticates and returns success with username/user_id, but no API key
3. **Key rotation** (`POST /auth/rotate-key`): Existing endpoint for recovering lost keys
   - Authenticates via current API key
   - Invalidates old key, generates new key pair
   - Returns new raw key once

## Consequences

- **Pro**: Eliminates raw key storage vulnerability
- **Pro**: Forces better key management practices
- **Pro**: Rotation endpoint already exists and works correctly
- **Con**: Users must store keys more carefully at registration
- **Con**: Lost keys require rotation rather than login retrieval

## Migration

Existing systems with raw keys stored will work until next registration. No immediate breaking changes for active users.

## Alternatives Considered

1. **Encrypt raw keys with KMS** — adds complexity, keys still recoverable if KMS is compromised
2. **Store keys in separate encrypted service** — over-engineering for the threat model
3. **Keep current approach** — rejected due to security risk