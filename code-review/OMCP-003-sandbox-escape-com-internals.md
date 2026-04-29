# OMCP-003: Sandbox Escape via Unproxied COM Object Internal Attributes

## Overview
| Field | Value |
|-------|-------|
| ID | OMCP-003 |
| Title | Sandbox Escape via Unproxied COM Object Internal Attributes |
| Severity | High |
| CVSS Score | 7.7 |
| Auth Required | No |
| Local/Remote | Remote |
| Status | Confirmed |
| Category | Product Code Finding |

## SVS Mapping
- **TASVS**: N/A
- **ASVS**: ASVS-5.2.4 - Dynamic code execution features are disabled or sandboxed

## CWE Reference
- **CWE-693**: Protection Mechanism Failure
- **CWE-94**: Improper Control of Generation of Code ('Code Injection')

## Vulnerability Details

### Description

The `staad` COM object injected into the sandbox is a raw `win32com.client.CDispatch` instance with no proxy wrapper. While the sandbox blocks double-underscore (dunder) attributes and a set of blocked attribute names, pywin32 COM dispatch objects expose **single-underscore** internal attributes that bypass all checks:

- `_oleobj_` -- raw `PyIDispatch` COM interface with `Invoke()`, `GetTypeInfo()`, `QueryInterface()`
- `_ApplyTypes_` -- typed method invocation with raw DISPIDs
- `_FlagAsMethod` -- mark arbitrary names as callable
- `_olerepr_` -- internal dispatch representation
- `_mapCachedItems_` -- cached dispatch items
- `_builtMethods_` -- cached method wrappers
- `_enum_` -- `IEnumVARIANT` interface access

None of these names start and end with `__` (so the dunder check in `visit_Attribute` doesn't catch them), and none are listed in `BLOCKED_ATTRS` (which focuses on frame, code, and traceback attributes).

Through `_oleobj_`, sandbox code gains access to the raw COM `IDispatch` interface, enabling invocation of methods by DISPID (bypassing any name-based restrictions), querying type information, and potentially accessing COM interfaces not exposed through the normal Python dispatch wrapper.

### Affected Code

**File:** [/sources/openstaad-mcp/src/openstaad_mcp/sandbox/executor.py:112](/sources/openstaad-mcp/src/openstaad_mcp/sandbox/executor.py#L112)
```python
sandbox_globals["staad"] = staad_object
```

The `staad_object` (a `win32com.client.CDispatch` from `openstaadpy`) is injected directly without a proxy. In contrast, `json` and `math` are wrapped in `ModuleProxy` objects.

**File:** [/sources/openstaad-mcp/src/openstaad_mcp/sandbox/const.py:78-101](/sources/openstaad-mcp/src/openstaad_mcp/sandbox/const.py#L78-L101)
```python
BLOCKED_ATTRS: frozenset[str] = frozenset(
    {
        "gi_frame", "gi_code", "gi_yieldfrom",
        "cr_frame", "cr_code", "cr_origin",
        "ag_frame", "ag_code",
        "f_globals", "f_locals", "f_builtins", "f_code", "f_back", "f_trace", "f_lineno",
        "co_consts", "co_names", "co_varnames", "co_freevars", "co_cellvars", "co_filename", "co_code",
        "tb_frame", "tb_next", "tb_lineno",
    }
)
```

pywin32 internal attributes like `_oleobj_`, `_ApplyTypes_`, etc. are absent from this list.

### Root Cause Analysis
- **Vulnerable code explanation**: The sandbox protects injected modules (`json`, `math`) with `ModuleProxy` wrappers, but the primary attack surface -- the `staad` COM object -- receives no such protection. The `BLOCKED_ATTRS` set was designed for Python runtime internals (frames, code objects, tracebacks) but does not account for pywin32's COM dispatch internals.
- **Attack prerequisites**: Ability to invoke the `execute_code` MCP tool.
- **Impact assessment**: Access to raw `PyIDispatch` allows invoking COM methods by raw DISPID (bypassing any name-based filtering), querying the COM type library for method signatures, and potentially reaching hidden or undocumented COM methods. The attacker could call any method exposed by the STAAD COM server, including those not intended for external use. Through STAAD's API, the attacker may also obtain references to other COM objects with broader capabilities.

## Proof of Concept

```python
# Step 1: Access raw COM dispatch internals (passes AST validation)
raw = staad._oleobj_

# Step 2: Get type information
ti = raw.GetTypeInfo()

# Step 3: Invoke methods by DISPID directly
# (bypasses any name-based restrictions)
result = raw.Invoke(dispid, 0, pythoncom.DISPATCH_METHOD, ...)

# Step 4: Enumerate cached methods for discovery
methods = staad._builtMethods_

# Step 5: Access internal representation
repr_info = staad._olerepr_
```

Note: Steps 3+ require `pythoncom` constants which are not in the sandbox, but the raw `Invoke()` call can use hardcoded integer values for the dispatch flags.

**PoC Script:** [/sources/openstaad-mcp/../results/reports_1/poc/OMCP-003-com-internals.py](/sources/openstaad-mcp/../results/reports_1/poc/OMCP-003-com-internals.py)

## Fix Recommendations

1. **Wrap `staad` in a proxy**: Create a proxy similar to `ModuleProxy` that only exposes whitelisted COM method names. Block access to all single-underscore pywin32 internals:
```python
BLOCKED_COM_ATTRS = frozenset({
    "_oleobj_", "_ApplyTypes_", "_FlagAsMethod", "_olerepr_",
    "_mapCachedItems_", "_builtMethods_", "_enum_", "_lazydata_",
})
```

2. **Extend BLOCKED_ATTRS**: Add pywin32 COM internal attributes to the existing `BLOCKED_ATTRS` set.

3. **Consider a stricter approach**: Only allow COM methods that match the STAAD OpenSTAAD API pattern (e.g., methods starting with `Get`, `Set`, `Create`, etc.) via an allowlist.

## Semgrep Rule Suggestion (if applicable)

- **Pattern type**: Pattern match -- sandbox exec with unproxied COM objects
- **Why automatable**: Any Python sandbox injecting COM dispatch objects without proxying is vulnerable
- **Suggested rule name**: python.security.sandbox-unproxied-com-dispatch

## Bypass Analysis

### Bypass Hypothesis
- Single-underscore attributes on pywin32 CDispatch objects are an entirely separate namespace from the Python dunder and runtime internal attributes that the sandbox was designed to block.

### Likelihood Assessment
- **High**: The attributes exist on every pywin32 CDispatch object. Accessing them requires no special knowledge beyond pywin32 documentation.

### Evidence
- `_oleobj_` is documented in pywin32 as the underlying `PyIDispatch` interface
- The AST validator only blocks `__dunder__` patterns and the specific names in `BLOCKED_ATTRS`
- No runtime enforcement exists on `staad` attribute access

---

## Source Reports
- [/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_1/OMCP-003-sandbox-escape-com-internals.md](/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_1/OMCP-003-sandbox-escape-com-internals.md)
- First discovered: Apr-14-2026-0000
- Validated: Apr-14-2026

## Report Metadata
| Field | Value |
|-------|-------|
| Agent | GitHub Copilot |
| Model | Claude Opus 4.6 |
| Timestamp | Apr-14-2026-0000 |
