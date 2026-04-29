# OMCP-012: Bearer Token Exposed in Process Arguments

## Overview
| Field | Value |
|-------|-------|
| ID | OMCP-012 |
| Title | Bearer Token Exposed in Process Arguments |
| Severity | Info |
| CVSS Score | 2.0 |
| Auth Required | Yes (high-priv) |
| Local/Remote | Local |
| Status | **Fixed in v2.0.0** |
| Category | Hardening |

## SVS Mapping
- **TASVS**: N/A
- **ASVS**: ASVS-2.10.4 - Service authentication secrets

## CWE Reference
- **CWE-214**: Invocation of Process Using Visible Sensitive Information

## Vulnerability Details

### Description

The `--token` CLI argument is the only way to provide the bearer token for HTTP transport mode. When passed on the command line, the token value is visible in:
- Process listing tools (e.g., `tasklist /v`, `Get-Process`, `ps aux`)
- Process monitoring software
- Shell command history
- System event logs on some configurations

There is no support for reading the token from an environment variable, a file, or stdin, which would reduce exposure.

### Affected Code

**File:** [/sources/openstaad-mcp/src/openstaad_mcp/main.py:54-57](/sources/openstaad-mcp/src/openstaad_mcp/main.py#L54-L57)
```python
parser.add_argument(
    "--token",
    type=str,
    default=_HTTP_ONLY_DEFAULTS["token"],
    help=f"[http] Bearer token required for every request in LAN mode ...",
)
```

### Root Cause Analysis
- **Vulnerable code explanation**: The token is accepted exclusively via command line argument.
- **Attack prerequisites**: Local access to the machine to view process listings.
- **Impact assessment**: Token disclosure to other local users or monitoring software. On single-user workstations (typical for STAAD.Pro), the risk is minimal.

## Fix Recommendations

**Resolved.** The `--token` CLI flag has been removed entirely. The server now auto-generates a cryptographic bearer token in memory at startup (`secrets.token_urlsafe(32)`) and pushes it to [OneTimeSecret](https://uk.onetimesecret.com) via the v2 guest API. Only the one-time share URL is displayed in the terminal auth banner — the token itself never appears on the command line, in logs, in config files, or in process listings. The MCP server never transmits or stores the secret; OTS holds it, and the user retrieves it directly. Zero secret handling in the MCP transport layer.

*(Updated 2026-04-28: `--email` / `OPENSTAAD_EMAIL` removed in v2.1.0. The OTS guest API does not support sending emails without an account, so the server now displays the share URL directly in the auth banner instead.)*

See [`ots_delivery.py`](../src/openstaad_mcp/ots_delivery.py) for implementation details.

### Original recommendation (superseded)

Add environment variable support as an alternative:

```python
import os

parser.add_argument(
    "--token",
    type=str,
    default=os.environ.get("OPENSTAAD_MCP_TOKEN", _HTTP_ONLY_DEFAULTS["token"]),
    help="[http] Bearer token (or set OPENSTAAD_MCP_TOKEN env var)",
)
```

---

## Source Reports
- [/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_2/OMCP-006-token-in-process-args.md](/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_2/OMCP-006-token-in-process-args.md)
- First discovered: Apr-14-2026-0000
- Validated: Apr-14-2026

## Report Metadata
| Field | Value |
|-------|-------|
| Agent | GitHub Copilot |
| Model | Claude Opus 4.6 |
| Timestamp | Apr-14-2026-0000 |
