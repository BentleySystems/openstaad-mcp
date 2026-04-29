# OMCP-008: Sandbox Type Hierarchy Leak via Unblocked mro() Method

## Overview
| Field | Value |
|-------|-------|
| ID | OMCP-008 |
| Title | Sandbox Type Hierarchy Leak via Unblocked mro() Method |
| Severity | Medium |
| CVSS Score | 5.0 |
| Auth Required | No |
| Local/Remote | Remote |
| Status | Confirmed |
| Category | Product Code Finding |

## SVS Mapping
- **TASVS**: N/A
- **ASVS**: ASVS-5.2.4 - Dynamic code execution features are disabled or sandboxed

## CWE Reference
- **CWE-200**: Exposure of Sensitive Information to an Unauthorized Actor
- **CWE-693**: Protection Mechanism Failure

## Vulnerability Details

### Description

The `mro()` method is accessible on all type objects in the sandbox (`int`, `str`, `list`, `dict`, `bool`, `float`, etc. from `ALLOWED_BUILTINS`). This method returns the Method Resolution Order, which includes a reference to the `object` base class. While `type` is blocked and `__class__`, `__mro__`, `__bases__`, `__subclasses__` are caught by the dunder AST check, the plain method `mro()` is not.

Alone, `mro()` only provides the `object` reference, which is not directly exploitable without `__subclasses__()`. However, combined with the `str.format()` bypass (OMCP-001), this provides a clean chain:

```python
bases = int.mro()             # [int, object] -- passes AST
obj = bases[1]                 # <class 'object'>
"{0.__subclasses__}".format(obj)  # Access __subclasses__ via format bypass
```

### Affected Code

**File:** [/sources/openstaad-mcp/src/openstaad_mcp/sandbox/const.py:78-101](/sources/openstaad-mcp/src/openstaad_mcp/sandbox/const.py#L78-L101)
```python
BLOCKED_ATTRS: frozenset[str] = frozenset(
    {
        # ... gi_frame, cr_frame, f_globals, co_consts, tb_frame etc.
        # 'mro' is NOT listed
    }
)
```

### Root Cause Analysis
- **Vulnerable code explanation**: `mro()` is a regular method name (not a dunder, not in BLOCKED_ATTRS). The blocklists were designed for Python runtime internals but did not account for type introspection methods.
- **Attack prerequisites**: Access to `execute_code`. Becomes more severe in combination with OMCP-001 (str.format() bypass).
- **Impact assessment**: Exposes the Python type hierarchy. Combined with format string bypass, enables enumeration of all Python subclasses in the process, potentially revealing dangerous classes for sandbox escape.

## Proof of Concept

```python
# Standalone: get reference to 'object'
result = int.mro()  # Returns [<class 'int'>, <class 'object'>]

# Combined with OMCP-001 for full escalation:
bases = int.mro()
result = "{0.__subclasses__}".format(bases[1])
```

## Fix Recommendations

1. **Add `mro` to `BLOCKED_ATTRS`**.
2. **Consider blocking all type-level methods**: `mro`, `__subclasses__`, `__bases__` (already caught by dunder check), `__mro__` (already caught).

---

## Source Reports
- [/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_1/OMCP-006-sandbox-mro-type-hierarchy-leak.md](/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_1/OMCP-006-sandbox-mro-type-hierarchy-leak.md)
- First discovered: Apr-14-2026-0000
- Validated: Apr-14-2026

## Report Metadata
| Field | Value |
|-------|-------|
| Agent | GitHub Copilot |
| Model | Claude Opus 4.6 |
| Timestamp | Apr-14-2026-0000 |
