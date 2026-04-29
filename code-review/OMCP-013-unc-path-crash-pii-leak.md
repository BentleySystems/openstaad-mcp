# OMCP-013: UNC Path Causes Blocking Modal Dialogs via OpenSTAADFile

## Overview
| Field | Value |
|-------|-------|
| ID | OMCP-013 |
| Title | UNC Path Causes Blocking Modal Dialogs via OpenSTAADFile |
| Severity | Low |
| CVSS Score | 3.1 |
| Auth Required | No |
| Local/Remote | Local |
| Status | Confirmed |
| Category | Product Code Finding |

## SVS Mapping
- **TASVS**: N/A
- **ASVS**: ASVS-5.1.3 - All input is validated on a trusted service layer

## CWE Reference
- **CWE-357**: Insufficient UI Warning of Dangerous Operations

## Vulnerability Details

### Description

Passing a UNC path (e.g. `\\attacker.example.com\share\model.std`) to `OpenSTAADFile` — which is on the root method allowlist — causes STAAD.Pro to display **blocking modal error dialogs** such as:

> `\\attacker.example.com\ cannot be accessed, please check your network`

Each invalid UNC path produces a separate dialog that the user must manually dismiss before STAAD.Pro resumes. An agent manipulated by prompt injection (OMCP-009) could trigger multiple `OpenSTAADFile` calls with different UNC paths, spamming the user with dialogs and disrupting their workflow.

**STAAD.Pro does not crash.** After all dialogs are dismissed, the application continues normally with the original model still open. The COM call returns `null`.

### Reproduction (2026-04-26, live MCP test)

Three UNC paths tested via the `execute_code` MCP tool against STAAD.Pro v25.00.01.424 (PID 10920):

| UNC Path | Result |
|----------|--------|
| `\\attacker.example.com\share\model.std` | Modal dialog, returns `null`, STAAD alive |
| `\\nonexistent-host\share\model.std` | Modal dialog, returns `null`, STAAD alive |
| `\\127.0.0.1\nonexistent\model.std` | Modal dialog, returns `null`, STAAD alive |

No crash. No crash artifacts generated. No PII leak. STAAD continued running after all dialogs were dismissed.

### Correction of original report

The original OMCP-013 (2026-04-23) reported a STAAD.Pro crash with `System.ArgumentNullException` in `MappedDriveResolver.ResolveToUNC()` and a PII leak via `Exception.log` and crash dialog. **This did not reproduce** on 2026-04-26 with the same STAAD.Pro version. The `Exception.log` at `%LOCALAPPDATA%\Bentley\Engineering\STAAD.Pro 2025\CrashReports\` contains crash data from the April 23 session, but it is unclear whether that crash was caused by the UNC path test or by another operation during the same adversarial testing session (42 tests ran, including several deliberately destructive operations). The crash and PII leak claims are **retracted** pending reproduction.

### Relationship to OMCP-005

OMCP-005 covers NTLM relay and file-write vectors through COM API path methods. This finding is a minor UX nuisance, not a security vulnerability in the same class. The modal dialog may trigger an outbound SMB authentication attempt before displaying — this overlaps with OMCP-005's NTLM relay concern.

### Affected Code

**File:** `src/openstaad_mcp/sandbox/constants.py`
```python
ALLOWED_ROOT_METHODS = {
    ...
    "OpenSTAADFile",
    ...
}
```

`OpenSTAADFile` is on the root allowlist. The WASM sandbox correctly gates the method call but does not validate path arguments before passing them to COM.

### Root Cause Analysis
- **Vulnerable code explanation**: `com_invoke` passes path arguments to COM methods without validation. STAAD.Pro handles the invalid path with a modal dialog rather than returning an error through COM.
- **Attack prerequisites**: Ability to call `execute_code`. A running STAAD.Pro instance. A prompt injection payload (OMCP-009) that convinces the agent to call `OpenSTAADFile` with a UNC path.
- **Impact assessment**: UX disruption only. The user must click through modal dialogs. No data loss, no crash, no PII leak confirmed.

## Fix Recommendations

1. **Optional input validation in `com_invoke`**: Before dispatching `OpenSTAADFile` and `NewSTAADFile`, reject paths that start with `\\` (UNC prefix). Low priority — the impact is a nuisance, not a vulnerability.

## Acceptance Decision

**Accepted risk.** The impact is limited to modal dialog spam, which requires the agent to be manipulated by prompt injection (OMCP-009) first. Not worth adding path validation complexity for a nuisance-level finding.

---

## Source Reports
- Live MCP test: 2026-04-26 (3 UNC path variants, no crash, dialogs only)
- Original adversarial test session: 2026-04-23 (crash reported but not reproduced)
- Test suite: `tests/adversarial/test_omcp009_modern_pi.py`
- Cross-references: OMCP-005, OMCP-009

## Report Metadata
- **Discovered by**: Dave Hanson (manual adversarial testing)
- **Original report**: 2026-04-23 (crash + PII leak — retracted)
- **Validated**: 2026-04-26 (downgraded to modal dialog nuisance)
- **Version**: openstaad-mcp v2.0.0-rc
