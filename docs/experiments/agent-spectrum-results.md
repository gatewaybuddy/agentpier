# Agent Specialization Spectrum — Results

**Date:** Feb 15, 2026
**Target:** Key rotation endpoint (`POST /auth/rotate-key`)

## Raw Data

| Metric | Round 1: Broad | Round 2: Narrow (3 agents) | Round 3: Domain (baseline) |
|--------|---------------|---------------------------|---------------------------|
| Agents | 1 | 3 (QA + Security + Docs) | 3 (QA + Security + Docs) |
| Runtime | ~4 min | ~8 min (QA blocked by rate limits) | <5 min (whole API, not just rotate) |
| Tokens (total) | ~26k | ~64k (15k + 31k + 17k) | ~97k (32k + 31k + 34k) |
| Security findings | 3 (1 HIGH, 2 MEDIUM) | 4 (2 HIGH, 2 MEDIUM) + 2 INFO | Whole-API audit, different scope |
| QA tests passed | 4/9 (5 blocked) | 2/10 (8 blocked) | 31/46 (8 fail, 7 warn) |
| Docs quality | Good endpoint spec | Excellent endpoint spec | Full API reference |

## Scoring (1-5 scale)

### Quality

| Aspect | Broad | Narrow | Notes |
|--------|-------|--------|-------|
| Security depth | 4 | 5 | Narrow found race condition + dual-key risk that broad also found, plus permissions inheritance issue |
| QA coverage | 2 | 1 | Both blocked by rate limits, but broad at least ran some tests first |
| Docs completeness | 4 | 5 | Narrow docs were exceptional — usage notes, safe patterns, caveats |
| **Average** | **3.3** | **3.7** | Narrow wins on depth where it could run |

### Integration Effort

| Aspect | Broad | Narrow | Notes |
|--------|-------|--------|-------|
| Self-contained? | 5 | 2 | Broad output is one file, ready to use. Narrow needs stitching. |
| Contradictions? | N/A | 3 | Security + Docs described the same behavior differently (GSI timing) |
| Format consistency | 5 | 3 | Each narrow agent used different heading styles, severity scales |
| **Average** | **5.0** | **2.7** | Broad wins decisively on integration |

### Resource Efficiency

| Aspect | Broad | Narrow | Notes |
|--------|-------|--------|-------|
| Token cost | 5 | 2 | Narrow used ~2.5x more tokens for same scope |
| Runtime | 4 | 2 | QA agent wasted 8 min mostly waiting on rate limits |
| Infra contention | 5 | 1 | **Critical finding**: narrow agents starved each other on shared rate limits |
| **Average** | **4.7** | **1.7** | Broad is dramatically more efficient |

## Composite Scores

| Model | Quality | Integration | Efficiency | **Total** |
|-------|---------|-------------|------------|-----------|
| Broad (1 agent) | 3.3 | 5.0 | 4.7 | **13.0** |
| Narrow (3 agents) | 3.7 | 2.7 | 1.7 | **8.1** |
| Domain (baseline) | 4.5* | 4.0* | 3.5* | **12.0*** |

*Domain baseline estimated from tonight's full-API run — not apples-to-apples since scope was whole API, not just rotate-key.

## Key Findings

### 1. Narrow agents have a resource contention problem
The most important finding: **three narrow agents sharing the same IP burned through the registration rate limit**, leaving the QA agent completely unable to test. This isn't a test bug — it's a fundamental issue with hyper-specialized agents sharing infrastructure. Domain agents avoid this because their scopes don't overlap on the same API calls.

### 2. Broad agent found the same critical bugs
The broad agent identified all 3 major security issues (non-atomic rotation, GSI consistency, no rate limit) that the narrow security agent found. It missed only the permissions-inheritance issue. For the ~2.5x token savings, that's a good trade.

### 3. Narrow docs were best-in-class
The narrow docs agent produced the most thorough endpoint documentation — including safe rotation patterns, consumer update strategies, and edge case warnings. When quality matters more than efficiency, narrowing scope helps.

### 4. Integration cost is real
Three narrow reports needed manual review to reconcile. Different severity scales, different emphasis, some redundant analysis. The broad agent's single report was immediately usable.

## Recommendations

### Sweet Spot: Domain Specialists (Current Model) ✅
Our current QA/Security/Docs split is the right granularity because:
- **Non-overlapping infrastructure use** — QA hits the API, Security reads code, Docs reads everything
- **Coherent output** — each agent produces a complete artifact in its domain
- **Manageable integration** — 3 reports to review, not 10
- **Shared context within domain** — QA agent understands the full test surface, not just one endpoint

### When to Go Broader
- Quick assessment of a single feature (like tonight's rotate-key review)
- Time-sensitive work where parallelism doesn't help
- When agents would contend on shared resources

### When to Go Narrower
- Documentation that needs exceptional depth (e.g., separate agents for user-facing docs vs internal architecture)
- When you need a "red team vs blue team" adversarial setup
- When one domain is too large for a single context window

### Anti-Pattern: Don't Split by Endpoint
Splitting QA by endpoint (test auth / test listings / test content filter) creates the worst of both worlds: resource contention + integration overhead + no cross-endpoint context (can't catch bugs that span endpoints).

## Next Steps
- Test with pre-provisioned credentials to eliminate rate limit contention
- Try a 2-agent model (QA+Security combined, Docs separate) — might be the actual optimum
- Document agent coordination best practices in `agents/coordination.md`
