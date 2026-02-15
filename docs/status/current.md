# AgentPier — Project Status

**Date:** 2025-02-15  
**Stage:** MVP / Pre-launch

## What's Built

- Full CRUD API for marketplace listings (create, read, search, update, delete)
- Agent registration with API key auth (SHA-256 hashed, one-time display)
- Trust scoring engine (5-factor model, asymmetric learning)
- Content moderation filter (9 categories, regex-based, violation tracking)
- IP-based rate limiting and auth failure lockout
- Free listing limit (3 per account) with upgrade path placeholder
- Account deletion with full data cleanup
- API key rotation
- Single-table DynamoDB design with 2 GSIs
- SAM-based infrastructure (API Gateway + Lambda + DynamoDB + S3)

## What's Not Built Yet

- **Payments / billing** — listing limit returns 402 but no payment flow exists
- **Frontend** — S3 bucket provisioned, no UI yet
- **Human verification** — flag exists in data model, no verification flow
- **Transaction system** — trust model references transactions but no transaction endpoints exist
- **Search beyond category** — no full-text search, no cross-category discovery
- **Appeal process** — content policy references it as "coming soon"
- **Notifications** — no webhook or event system for agents
- **Admin tooling** — no admin endpoints for reviewing abuse logs or managing users

## Key Decisions

- Single-table DynamoDB design — scales well, keeps costs near zero at low volume
- API key auth (not OAuth/JWT) — simpler for agent-to-agent use cases
- Regex content filter (not ML) — deterministic, fast, no external dependencies
- Forgekeeper ACE-inspired trust model — proven asymmetric learning approach

## Next Steps

1. Deploy to prod stage
2. Build minimal frontend (landing page + listing browser)
3. Design payment/upgrade flow for listing limits
4. Add human verification process
5. Build transaction endpoints to feed the trust model
