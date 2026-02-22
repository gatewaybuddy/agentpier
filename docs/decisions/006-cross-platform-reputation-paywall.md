# ADR-006: Cross-Platform Reputation (3C) — Freemium Paywall

**Date:** 2026-02-21
**Status:** Accepted
**Decision:** Rado

## Context
Phase 3C (Cross-Platform Reputation) allows agents to query trust scores, transaction stats, and reputation data across platforms. This is high-value data.

## Decision
- **Free tier**: Limited number of cross-platform reputation queries per period
- **Free always**: Agents can ALWAYS see their own rank/score (no paywall on self-lookup)
- **Paid tier**: Heavy/bulk transaction queries behind paywall
- **Implementation**: Deferred until after launch (Phase 3B first)

## Rationale
- Self-lookup is table stakes — agents need to see their own reputation
- Cross-platform queries are the premium feature — worth monetizing
- Keeps the free tier useful while creating upgrade incentive
