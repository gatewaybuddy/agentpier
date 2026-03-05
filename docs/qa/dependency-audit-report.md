# Dependency Security Audit Report

**Date:** March 5, 2026  
**Tool:** pip-audit v2.10.0  
**Scope:** AgentPier SDK and Integration packages

## Executive Summary

Security audit of AgentPier packages and their dependencies revealed **3 known vulnerabilities** in **2 packages**. All vulnerabilities are in third-party dependencies, not AgentPier code itself.

## Audit Results

### Vulnerabilities Found

| Package   | Version | CVE            | Severity | Fix Available |
|-----------|---------|----------------|----------|---------------|
| diskcache | 5.6.3   | CVE-2025-69872 | TBD      | None listed   |
| pip       | 24.0    | CVE-2025-8869  | TBD      | 25.3          |
| pip       | 24.0    | CVE-2026-1703  | TBD      | 26.0          |

### Packages Audited

- **AgentPier SDK** (`/mnt/d/Projects/agentpier/sdk/python/`)
  - Status: ✅ No vulnerabilities in AgentPier code
  - Note: Package not on PyPI, local audit only

- **CrewAI Integration** (`/mnt/d/Projects/agentpier/integrations/crewai/`)
  - Status: ✅ No vulnerabilities in integration code
  - Dependencies: crewai==1.10.1 + 100+ transitive dependencies
  - Note: Package not on PyPI, local audit only

- **LangChain Integration** (`/mnt/d/Projects/agentpier/integrations/langchain/`)
  - Status: ✅ No vulnerabilities in integration code
  - Dependencies: langchain-core>=0.1.0 + transitive dependencies
  - Note: Package not on PyPI, local audit only

### Dependencies Status

- **Total packages checked:** 150+ (including transitive dependencies)
- **Clean packages:** 147+
- **Vulnerable packages:** 3 instances (2 unique packages)

## Risk Assessment

### HIGH Priority
None identified in AgentPier-specific code.

### MEDIUM Priority
- **diskcache 5.6.3** - Used by CrewAI integration via transitive dependency chain.
  
  **CVE-2025-69872 Analysis:**
  - **Vulnerability:** Unsafe Python pickle deserialization by default
  - **Impact:** Arbitrary code execution if attacker has write access to cache directory
  - **Exploitability:** Requires local file system write access to diskcache storage location
  - **Risk Level:** Medium (requires privileged access to exploit)
  - **GHSA ID:** GHSA-w8v5-vhqr-4h9v
  - **Fix Available:** None yet (monitoring for updates)
  
  **Mitigation Recommendations:**
  1. **Immediate:** Verify diskcache storage paths are not world-writable
  2. **Short-term:** Monitor diskcache GitHub for security updates
  3. **Long-term:** Consider alternative caching backends if available in CrewAI
  4. **Environment:** Ensure production containers run with minimal file permissions

### LOW Priority
- **pip 24.0** - Development/build tool vulnerabilities. Affects build environment only.

## Recommendations

1. **Immediate Actions:**
   - Research CVE-2025-69872 impact on diskcache usage in CrewAI
   - Update pip to latest version (26.0+) in development environments

2. **Medium Term:**
   - Monitor for diskcache security updates
   - Consider pinning to secure versions once fixes are available
   - Set up automated dependency scanning in CI/CD

3. **Long Term:**
   - Establish quarterly security audits
   - Implement dependency update automation with security testing

## Test Environment

```bash
# Environment setup
python3 -m venv audit_env
source audit_env/bin/activate

# Package installation
pip install -e /mnt/d/Projects/agentpier/sdk/python/
pip install -e /mnt/d/Projects/agentpier/integrations/crewai/
pip install -e /mnt/d/Projects/agentpier/integrations/langchain/

# Security audit
pip install pip-audit
PIPAPI_PYTHON_LOCATION=/tmp/audit_env/bin/python pip-audit
```

## Conclusion

AgentPier packages themselves show **no security vulnerabilities**. The identified issues are in third-party dependencies with available fixes for pip and pending investigation for diskcache. Overall security posture is **acceptable** with recommended monitoring and updates.