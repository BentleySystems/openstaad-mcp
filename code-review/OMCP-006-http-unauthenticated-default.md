# OMCP-006: HTTP Transport Allows Unauthenticated Access by Default

## Overview
| Field | Value |
|-------|-------|
| ID | OMCP-006 |
| Title | HTTP Transport Allows Unauthenticated Access by Default |
| Severity | Medium |
| CVSS Score | 6.5 |
| Auth Required | No |
| Local/Remote | Local |
| Status | Confirmed |
| Category | Configuration Risk |

## SVS Mapping
- **TASVS**: N/A
- **ASVS**: ASVS-4.1.1 - Access controls are enforced on a trusted service layer

## CWE Reference
- **CWE-306**: Missing Authentication for Critical Function
- **CWE-862**: Missing Authorization

## Vulnerability Details

### Description

When the MCP server is started with `--transport http` without providing a `--token` argument, the HTTP endpoint has **no authentication**. Any process on the local machine (or any process that can reach the loopback interface) can invoke all MCP tools, including `execute_code` which runs arbitrary sandboxed Python code against STAAD.Pro.

While the server binds to `127.0.0.1` (not `0.0.0.0`), this still allows:
- **Local privilege escalation**: Any unprivileged process or user on the machine can control STAAD.Pro
- **Browser-based attacks**: DNS rebinding or CORS misconfiguration could allow a malicious web page to invoke MCP tools (the server docstring mentions `TransportSecurityMiddleware` but the token-less configuration has no secret to validate)
- **Malware lateral movement**: Malware running on the same machine can silently interact with STAAD.Pro

The `--token` parameter defaults to `None`, and no warning is emitted when HTTP mode is started without a token. The help text normalizes unauthenticated operation.

### Affected Code

**File:** [/sources/openstaad-mcp/src/openstaad_mcp/main.py:93-107](/sources/openstaad-mcp/src/openstaad_mcp/main.py#L93-L107)
```python
    else:  # http
        fastmcp_kwargs = {}
        if args.token:
            fastmcp_kwargs["auth"] = StaticTokenVerifier(
                tokens={args.token: {"client_id": "authorized-user", "scopes": ["read:data"]}},
                required_scopes=["read:data"],
            )
        mcp = create_mcp_server(fastmcp_kwargs=fastmcp_kwargs)
        try:
            mcp.run(transport="http", host="127.0.0.1", port=args.port, stateless_http=True)
```

When `args.token` is `None` (the default), no auth provider is configured.

**File:** [/sources/openstaad-mcp/src/openstaad_mcp/main.py:59-62](/sources/openstaad-mcp/src/openstaad_mcp/main.py#L59-L62)
```python
    parser.add_argument(
        "--token",
        type=str,
        default=_HTTP_ONLY_DEFAULTS["token"],  # None
```

**Token default is `None`, making auth opt-in:**
**File:** [/sources/openstaad-mcp/src/openstaad_mcp/main.py:20](/sources/openstaad-mcp/src/openstaad_mcp/main.py#L20)
```python
_HTTP_ONLY_DEFAULTS = {"port": 18120, "token": None}
```

### Root Cause Analysis
- **Vulnerable code explanation**: Token-based authentication is fully implemented but is opt-in. The default state for HTTP transport is unauthenticated. Authentication is conditionally added only when `--token` is provided.
- **Attack prerequisites**: HTTP transport mode enabled. Attacker must be on the same machine (loopback binding) or able to perform DNS rebinding. This could be via malware, a compromised application, or another user on a shared system.
- **Impact assessment**: Full access to all MCP tools including code execution against STAAD.Pro, arbitrary file reading (via OMCP-002), and instance enumeration. An attacker can read engineering model data, modify structures, and execute arbitrary COM commands.

## Proof of Concept

```bash
# Start server without token (default)
openstaad-mcp --transport http --port 18120

# Any local process can now call tools without authentication
curl -X POST http://127.0.0.1:18120/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"execute_code","arguments":{"code":"result = staad.GetSTAADFile()"}},"id":1}'
```

## Fix Recommendations

**Resolved in v2.0.0, updated in v2.1.0.** HTTP mode now requires authentication with no opt-out. The server auto-generates a cryptographic bearer token (`secrets.token_urlsafe(32)`) in memory at startup, pushes it to [OneTimeSecret](https://uk.onetimesecret.com) via the v2 guest API, and displays only the one-time share URL in a Rich auth banner. The token itself never appears on the command line, in logs, in config files, or in process listings. The MCP server never transmits or stores the secret — OTS holds it, and the user retrieves it directly. Zero secret handling in the MCP transport layer. If OTS is unreachable, the raw token is printed in the banner as a fallback. There is no `--token` flag, no default, no dev flag, no escape hatch.

Additionally, `HostHeaderMiddleware` rejects requests with non-allowlisted `Host` headers (HTTP 421) before auth fires, defeating DNS rebinding. See [OMCP-010](OMCP-010-missing-sec-fetch-middleware.md).

### Original recommendations (superseded)

1. **Require token for HTTP mode**: Make `--token` mandatory when `--transport http` is used:
```python
if args.transport == "http" and not args.token:
    parser.error("--token is required for HTTP transport mode")
```

2. **Auto-generate token**: Generate a secure random token if none is provided:
```python
import secrets
if args.transport == "http" and not args.token:
    args.token = secrets.token_urlsafe(32)
    logging.warning(f"No --token provided. Auto-generated token: {args.token}")
```

3. **Warn on missing token**: At minimum, emit a prominent warning when HTTP mode starts without authentication:
```python
if not args.token:
    logging.warning("HTTP mode started WITHOUT authentication -- all local processes can access this server")
```

---

## Source Reports
- [/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_1/OMCP-005-http-unauthenticated-default.md](/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_1/OMCP-005-http-unauthenticated-default.md)
- [/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_2/OMCP-003-http-missing-auth-default.md](/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_2/OMCP-003-http-missing-auth-default.md)
- First discovered: Apr-14-2026-0000
- Validated: Apr-14-2026

## Report Metadata
| Field | Value |
|-------|-------|
| Agent | GitHub Copilot |
| Model | Claude Opus 4.6 |
| Timestamp | Apr-14-2026-0000 |
