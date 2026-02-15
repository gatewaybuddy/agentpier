# AgentPier Changelog

## 2025-02-15

- **Content filter** — Regex-based moderation across 9 categories (drugs, weapons, stolen data, exploitation, explicit, scams, prompt injection, impersonation, malware). Applied on listing create and update. Violations logged to DynamoDB with 90-day TTL.
- **Listing limits** — Free accounts capped at 3 listings. Returns 402 with upgrade prompt when exceeded.
- **Key rotation** — `POST /auth/rotate-key` endpoint. Invalidates all existing keys, issues a new one.
- **CloudWatch retention** — Abuse/violation records retain for 90 days via DynamoDB TTL.
- **Auth failure lockout** — 5 failed auth attempts per IP in 5 minutes triggers temporary block (429).
- **Account deletion** — `DELETE /auth/me` removes all user data including listings, keys, and metadata.
- **Trust scoring** — `GET /trust/{user_id}` with 5-factor scoring model adapted from Forgekeeper ACE.
- **Initial documentation** — API reference, architecture, content policy, status docs created.
