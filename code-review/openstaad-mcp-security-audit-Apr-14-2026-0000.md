# openstaad-mcp Security Audit -- Validated Summary -- Apr-14-2026

## Executive Summary

Validated security audit of the **openstaad-mcp** MCP server (Python 3.11+, FastMCP, pywin32 COM bridge to STAAD.Pro). After independent review of 13 merged findings against source code, **12 findings** were retained: 5 High, 4 Medium, 1 Low, and 2 Informational. One finding (AST validation bypass via ast.unparse() round-trip gap) was removed as a false positive -- no concrete exploit exists and Gate 4 (PoC) fails. One finding (missing Sec-Fetch-Site middleware) was downgraded from Medium to Informational as a defense-in-depth gap. The primary attack surface remains the `execute_code` sandbox, which has confirmed bypass vectors.

## Validation Statistics

| Metric | Value |
|--------|-------|
| Merged findings reviewed | 13 |
| Confirmed (kept) | 10 |
| Informational (downgraded) | 1 (OMCP-010) |
| Informational (unchanged) | 1 (OMCP-012) |
| False Positives removed | 1 (OMCP-011: ast.unparse gap) |
| Validated findings total | 12 |
| Severity changes | 1 |
| ID renumbering | 2 |

## Findings Summary

| ID | Title | Severity | Auth Required | Local/Remote | Status | Category | TASVS | ASVS |
|----|-------|----------|---------------|--------------|--------|----------|-------|------|
| OMCP-001 | Sandbox Escape via str.format() Dunder Attribute Access | High | No | Remote | Confirmed | Product Code Finding | N/A | ASVS-5.2.4 |
| OMCP-002 | Path Traversal in read_skills Allows Arbitrary File Read | High | No | Remote | Confirmed | Product Code Finding | N/A | ASVS-12.3.1 |
| OMCP-003 | Sandbox Escape via Unproxied COM Object Internal Attributes | High | No | Remote | Confirmed | Product Code Finding | N/A | ASVS-5.2.4 |
| OMCP-004 | Permanent Executor Deadlock After COM Timeout | High | No | Remote | Confirmed | Product Code Finding | N/A | ASVS-11.1.4 |
| OMCP-005 | Arbitrary Filesystem Write and NTLM Credential Relay via STAAD COM API | High | No | Remote | Potential Likely | Product Code Finding | N/A | ASVS-5.2.4 |
| OMCP-006 | HTTP Transport Allows Unauthenticated Access by Default | Medium | No | Local | Confirmed | Configuration Risk | N/A | ASVS-4.1.1 |
| OMCP-007 | Denial of Service via Unbounded Sandbox Resource Consumption | Medium | No | Remote | Confirmed | Product Code Finding | N/A | ASVS-11.1.4 |
| OMCP-008 | Sandbox Type Hierarchy Leak via Unblocked mro() Method | Medium | No | Remote | Confirmed | Product Code Finding | N/A | ASVS-5.2.4 |
| OMCP-009 | Indirect Prompt Injection via COM Return Values to AI Agent | Medium | No | Remote | Confirmed | Product Code Finding | N/A | ASVS-5.5.1 |
| OMCP-010 | Documented Sec-Fetch-Site SecurityMiddleware Not Implemented | Informational | No | Local | Informational | Hardening | N/A | ASVS-14.5.3 |
| OMCP-011 | Information Disclosure via Sandbox Stack Traces | Low | No | Remote | Confirmed | Product Code Finding | N/A | ASVS-7.4.1 |
| OMCP-012 | Bearer Token Exposed in Process Arguments | Informational | Yes (high-priv) | Local | Informational | Hardening | N/A | ASVS-2.10.4 |

## Validation Changes

### False Positive Removed
- **OMCP-011 (merged)**: AST Validation Bypass via ast.unparse() Round-Trip Gap -- No concrete exploit; Gate 4 (PoC) fails. The code gap is real (validated code != executed code) but no known `ast.unparse()` edge case in Python 3.11+ produces a security-relevant semantic change. The `__result__` variable introduction is benign. Code improvement suggestion (compile AST directly) preserved in todo.

### Severity Downgrade
- **OMCP-010**: Medium -> Informational. Missing Sec-Fetch-Site filtering is defense-in-depth; the primary DNS rebinding protection is provided by the FastMCP SDK's TransportSecurityMiddleware. No evidence that the SDK's protection is insufficient.

### ID Renumbering
- Merged OMCP-012 (stack traces) -> Validated OMCP-011
- Merged OMCP-013 (token in args) -> Validated OMCP-012

## Key Themes (Validated)

### 1. Sandbox Bypass Vectors (OMCP-001, 003, 008) -- All Confirmed
- `str.format()` runtime attribute access bypasses AST dunder check (OMCP-001)
- pywin32 COM internal attributes (`_oleobj_` etc.) bypass BLOCKED_ATTRS (OMCP-003)
- `mro()` type method leaks class hierarchy, aids sandbox escape chains (OMCP-008)
- The `staad` COM object is the primary gap -- injected raw without a proxy

### 2. Input Validation (OMCP-002, 009) -- Both Confirmed
- `read_skills` path traversal: no `resolve()` or `is_relative_to()` checks
- COM return values flow unsanitized to AI agents (prompt injection vector)

### 3. Availability (OMCP-004, 007) -- Both Confirmed
- `_exec_lock` permanent deadlock after timeout (daemon thread holds lock forever)
- Unbounded StringIO buffers + allowed `print()` = memory exhaustion

### 4. Authentication/Transport (OMCP-006, 010, 012)
- HTTP mode defaults to no auth (OMCP-006, Confirmed Medium)
- Missing Sec-Fetch-Site middleware (OMCP-010, downgraded to Informational)
- Token only via CLI args (OMCP-012, Informational)

## SAST Inconsistency Summary

No SAST results (Semgrep, Gitleaks, BinSkim) were found in any audit run. No inconsistencies to report.

## Appendix: Endpoint Map

### MCP Tools

| Tool | Auth Required | Parameters | Security Notes |
|------|---------------|------------|----------------|
| discover_api | No | (none) | Returns skill listing; low risk |
| read_skills | No | skills: list[str] | Path traversal (OMCP-002) |
| list_instances | No | (none) | Returns all STAAD instance info |
| get_status | No | instance?: str | Returns connection details |
| execute_code | No | code: str, instance?: str | Primary attack surface (OMCP-001, 003, 004, 005, 007, 008) |

### Transport Modes

| Transport | Default Port | Auth | Binding |
|-----------|-------------|------|---------|
| stdio | N/A | None (process pipe) | N/A |
| http | 18120 | Optional bearer token (OMCP-006) | 127.0.0.1 only |

---

## Report Metadata
| Field | Value |
|-------|-------|
| Agent | GitHub Copilot |
| Model | Claude Opus 4.6 |
| Timestamp | Apr-14-2026-0000 |
