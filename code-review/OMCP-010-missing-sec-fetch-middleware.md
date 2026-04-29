# OMCP-010: Documented Sec-Fetch-Site SecurityMiddleware Not Implemented

## Overview
| Field | Value |
|-------|-------|
| ID | OMCP-010 |
| Title | Documented Sec-Fetch-Site SecurityMiddleware Not Implemented |
| Severity | ~~Medium~~ Informational |
| CVSS Score | N/A |
| Auth Required | No |
| Local/Remote | Local |
| Status | **Informational** |
| Category | Hardening |

## SVS Mapping
- **TASVS**: N/A
- **ASVS**: ASVS-14.5.3 - HTTP security headers

## CWE Reference
- **CWE-1059**: Insufficient Technical Documentation
- **CWE-693**: Protection Mechanism Failure

## Vulnerability Details

### Description

**Validation note**: Downgraded from Medium to Informational. This is a defense-in-depth gap; the primary DNS rebinding protection (TransportSecurityMiddleware) is provided by the FastMCP SDK (>=3.2.3), and no evidence exists that the SDK's protection is insufficient.

The `server.py` module docstring explicitly claims that a custom `SecurityMiddleware` provides `Sec-Fetch-Site` header filtering for HTTP transport mode. However, no such middleware exists anywhere in the codebase. The project's README also claims DNS rebinding protection via `Host`, `Origin`, and `Sec-Fetch-Site` header validation. The actual authentication is limited to the optional `StaticTokenVerifier` bearer token -- there is no `Sec-Fetch-Site` filtering implementation.

`Sec-Fetch-Site` filtering is a defense-in-depth measure that rejects browser-initiated cross-origin requests. Without it, if the FastMCP SDK's built-in `TransportSecurityMiddleware` (Host/Origin validation) has any gaps, browser-based attacks (DNS rebinding, CSRF from malicious websites) against the localhost endpoint would not be blocked by this additional layer.

The documentation-implementation mismatch creates a false sense of security for operators and security reviewers.

### Affected Code

**Docstring claims middleware exists:**
**File:** [/sources/openstaad-mcp/src/openstaad_mcp/server.py:16-18](/sources/openstaad-mcp/src/openstaad_mcp/server.py#L16-L18)
```python
"""
DNS rebinding protection (Host / Origin validation) is provided by the
MCP SDK's built-in ``TransportSecurityMiddleware``.  Our own
``SecurityMiddleware`` adds Sec-Fetch-Site filtering and Bearer token
auth for LAN mode.
"""
```

**README claims validation exists:**
**File:** [/sources/openstaad-mcp/README.md:163](/sources/openstaad-mcp/README.md#L163)
```markdown
- **DNS rebinding protection.** The server validates `Host`, `Origin`, and
  `Sec-Fetch-Site` headers and never sends CORS headers.
```

**No middleware implementation found in any source file.** The only auth mechanism is `StaticTokenVerifier` in [/sources/openstaad-mcp/src/openstaad_mcp/main.py:102](/sources/openstaad-mcp/src/openstaad_mcp/main.py#L102).

### Root Cause Analysis
- **Vulnerable code explanation**: The docstring and README describe a SecurityMiddleware feature that was either planned but not implemented, or was removed without updating documentation.
- **Attack prerequisites**: HTTP transport mode active. A browser-based attack (DNS rebinding or cross-origin request) must bypass the SDK's TransportSecurityMiddleware.
- **Impact**: Missing defense-in-depth layer. If the SDK's DNS rebinding protection has any gaps, browser-based attacks could reach the unprotected endpoint. No direct exploitability demonstrated.

## Proof of Concept

No PoC demonstrating a bypass of the SDK's TransportSecurityMiddleware was produced. The finding is limited to the missing secondary defense layer and documentation mismatch.

## Fix Recommendations

1. **Implement the documented SecurityMiddleware** with Sec-Fetch-Site filtering:

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        sec_fetch_site = request.headers.get("sec-fetch-site", "")
        if sec_fetch_site in ("cross-site", "same-site"):
            return Response("Forbidden", status_code=403)
        return await call_next(request)
```

2. **Alternatively, update documentation** to accurately reflect the current security posture -- remove references to Sec-Fetch-Site filtering and the custom SecurityMiddleware.

---

## Source Reports
- [/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_2/OMCP-004-missing-sec-fetch-middleware.md](/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_2/OMCP-004-missing-sec-fetch-middleware.md)
- First discovered: Apr-14-2026-0000
- Validated: Apr-14-2026

## Report Metadata
| Field | Value |
|-------|-------|
| Agent | GitHub Copilot |
| Model | Claude Opus 4.6 |
| Timestamp | Apr-14-2026-0000 |
