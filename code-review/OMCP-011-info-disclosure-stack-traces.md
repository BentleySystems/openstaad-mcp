# OMCP-011: Information Disclosure via Sandbox Stack Traces

## Overview
| Field | Value |
|-------|-------|
| ID | OMCP-011 |
| Title | Information Disclosure via Sandbox Stack Traces |
| Severity | Low |
| CVSS Score | 3.7 |
| Auth Required | No |
| Local/Remote | Remote |
| Status | Confirmed |
| Category | Product Code Finding |

## SVS Mapping
- **TASVS**: N/A
- **ASVS**: ASVS-7.4.1 - Generic error messages are shown to minimize information disclosure

## CWE Reference
- **CWE-209**: Generation of Error Message Containing Sensitive Information

## Vulnerability Details

### Description

When sandbox code execution raises an exception, the full Python traceback is captured and returned in the `error` field of the MCP response. If the exception propagates through framework code (COM wrappers, openstaadpy, Python standard library), the traceback reveals:

- **Real filesystem paths** to installed packages (e.g., `C:\Users\<username>\AppData\...\site-packages\openstaadpy\...`)
- **System username** from the path
- **Internal module structure** and import chain
- **Argument values** in some exception types

### Affected Code

**File:** [/sources/openstaad-mcp/src/openstaad_mcp/sandbox/executor.py:130-136](/sources/openstaad-mcp/src/openstaad_mcp/sandbox/executor.py#L130-L136)
```python
        if exec_error is not None:
            tb = "".join(traceback.format_exception(type(exec_error), exec_error, exec_error.__traceback__))
            return ExecutionResult(
                success=False,
                stdout=stdout_text,
                stderr=stderr_text,
                error=tb,
                duration_seconds=round(duration, ndigits=4),
            )
```

### Root Cause Analysis
- **Vulnerable code explanation**: `traceback.format_exception()` produces full stack traces including absolute file paths from all frames, not just the sandbox's `<sandbox>` frames.
- **Attack prerequisites**: Ability to cause an exception in sandbox code that propagates through framework code. Trivially achievable by calling COM methods with invalid arguments.
- **Impact assessment**: Leaks system username, installation paths, internal module structure. Low severity for a local desktop tool, but provides useful reconnaissance for an attacker with partial access.

## Proof of Concept

```python
# Trigger a COM exception that propagates through openstaadpy
result = staad.GetNodeCoordinates(999999)
# The traceback will reveal real paths like:
# File "C:\Users\john.doe\AppData\...\openstaadpy\os_analytical.py", line XX
```

## Fix Recommendations

1. **Sanitize tracebacks**: Strip absolute paths from error messages, replacing them with relative or generic paths:
```python
import re
tb = re.sub(r'File ".*[\\/]site-packages[\\/]', 'File ".../', tb)
tb = re.sub(r'File ".*[\\/]openstaad_mcp[\\/]', 'File "openstaad_mcp/', tb)
```

2. **Return only sandbox frames**: Filter the traceback to only include frames from `<sandbox>`, omitting framework internals.

---

## Source Reports
- [/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_1/OMCP-009-info-disclosure-stack-traces.md](/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_1/OMCP-009-info-disclosure-stack-traces.md)
- First discovered: Apr-14-2026-0000
- Validated: Apr-14-2026

## Report Metadata
| Field | Value |
|-------|-------|
| Agent | GitHub Copilot |
| Model | Claude Opus 4.6 |
| Timestamp | Apr-14-2026-0000 |
