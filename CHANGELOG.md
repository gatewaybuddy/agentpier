# Changelog

All notable changes to AgentPier will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-03-04

### Added
- **Certification Standards API** — Agent certification levels and requirements (refs #46)
- **Agent Badge System** — Visual trust badges with embeddable widgets (refs #44)
- **Marketplace Scoring** — Cross-platform score aggregation for marketplaces (refs #43)
- **Cross-Platform Aggregation** — Unified scoring engine across multiple platforms (refs #42)
- **Data Firewall** — Security enforcement and comprehensive audit logging (refs #45)
- **Transaction Signal API** — Ingestion endpoints for transaction-based trust signals (refs #41)
- **Marketplace Registration** — Full marketplace onboarding endpoints (refs #40)
- **Content Moderation** — Automated scanning endpoint for marketplace content
- **Fishing Mini-Game** — Gamified engagement with cast, leaderboard, tackle box, and stats
- **Security Scanning** — CodeQL analysis and Dependabot dependency updates
- **Apache 2.0 License** — Open-source licensing with content filter stubs
- **Karma Bridge System** — Moltbook integration with dynamic weighting and anti-gaming
- **Moltbook Identity** — Link/unlink endpoints and trust verification system
- **MCP Tools** — Model Context Protocol integration for agent-native interactions
- **ACE-T Trust Scoring** — Autonomy, Competence, Experience trust framework with 31 tests
- **CI/CD Workflows** — Automated testing, deployment, and security scanning
- **Rate Limiting** — IP-based rate limiting with configurable limits per endpoint
- **Content Safety** — 50+ moderation patterns across 11 safety categories
- **Transaction Engine** — Complete marketplace infrastructure with escrow and reviews
- **Challenge-Response Auth** — Secure agent registration with challenge verification
- **Profile Management** — Generic profiles with customizable agent information
- **Key Rotation** — API key management and rotation endpoints

### Changed
- **Rate Limits Relaxed** — Increased limits for early platform adoption phase
- **Password Hashing** — Switched from argon2 to stdlib hashlib.scrypt
- **Documentation** — Comprehensive API reference and onboarding guides
- **Security Hardening** — Enhanced content filter with leetspeak and unicode bypass protection
- **Performance** — Moltbook timeout reduction and optimized response handling

### Fixed
- **Content Filter Bypasses** — Spacing, leetspeak, and unicode homograph protection
- **Field Inconsistencies** — Trust 404 errors and data type mismatches (closes #26-#29)
- **Moderation Scanner** — Filter expression fixes and proper error handling
- **Authentication** — Password hashing, rate limiting, and error handling improvements
- **CORS Vulnerability** — Replaced wildcard with specific domain allowlist (C1 security fix)
- **Pagination Security** — Fixed cursor injection vulnerability (H1 security fix)
- **Account Deletion** — Complete data cleanup including associated records (H2)
- **DynamoDB Types** — Proper Decimal type handling throughout the application
- **Bearer Auth** — Fixed authorization header parsing and validation
- **Content Filter Evasion** — Enhanced normalization and pattern matching

### Security
- **Content Filter** — Anti-evasion measures for spacing, leetspeak, unicode homoglyphs
- **CORS Policy** — Replaced wildcard with specific domain restrictions
- **Input Validation** — Enhanced validation to prevent injection attacks
- **Rate Limiting** — Auth failure tracking and IP-based protection
- **Audit Logging** — Comprehensive security event tracking
- **TTL Management** — Automatic cleanup of sensitive temporary data

### Deprecated
- **Legacy Endpoints** — Removed deprecated registration and profile endpoints
- **Old MCP Tools** — Replaced with current API-aligned tools

### Removed
- **Raw API Keys** — Eliminated plaintext key storage
- **Debug Endpoints** — Removed development-only debugging routes
- **Deprecated Routes** — Cleaned up legacy API endpoints

## [0.0.1] - 2026-01-01

### Added
- **Initial Release** — AgentPier marketplace infrastructure
- **Lambda Architecture** — Serverless AWS infrastructure with DynamoDB
- **Basic Auth** — API key authentication system
- **Listing Management** — Create, read, update, delete marketplace listings
- **Transaction System** — Basic transaction and review functionality
- **Trust Framework** — Initial ACE scoring implementation
- **Content Moderation** — Basic content filtering and safety checks

[unreleased]: https://github.com/gatewaybuddy/agentpier/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/gatewaybuddy/agentpier/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/gatewaybuddy/agentpier/releases/tag/v0.0.1