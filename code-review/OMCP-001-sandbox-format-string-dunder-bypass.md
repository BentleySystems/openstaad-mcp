# OMCP-001: Sandbox Escape via str.format() Dunder Attribute Access

## Overview
| Field | Value |
|-------|-------|
| ID | OMCP-001 |
| Title | Sandbox Escape via str.format() Dunder Attribute Access |
| Severity | High |
| CVSS Score | 8.1 |
| Auth Required | No |
| Local/Remote | Remote |
| Status | Confirmed |
| Category | Product Code Finding |

## SVS Mapping
- **TASVS**: N/A
- **ASVS**: ASVS-5.2.4 - Dynamic code execution features are disabled or sandboxed
- **ASVS**: ASVS-5.2.8 - Serialization controls

## CWE Reference
- **CWE-94**: Improper Control of Generation of Code ('Code Injection')
- **CWE-200**: Exposure of Sensitive Information to an Unauthorized Actor
- **CWE-693**: Protection Mechanism Failure

## Vulnerability Details

### Description

The `execute_code` MCP tool runs user-supplied Python code in a sandbox that relies on AST-level validation to block access to dunder (double-underscore) attributes like `__class__`, `__mro__`, `__subclasses__`, etc. This prevents direct attribute access such as `staad.__class__`.

However, Python's `str.format()` method performs **runtime attribute lookup** using its mini-language, bypassing the static AST check entirely. The format specification `{0.__class__}` is parsed as a string constant in the AST -- not as an `ast.Attribute` node -- so the validator never sees the dunder access. At runtime, `str.format()` calls `getattr()` internally to resolve the dotted path.

This allows sandbox code to traverse Python's object hierarchy to reach arbitrary classes and potentially achieve code execution via the classic `__subclasses__()` chain. The `staad` COM object is the highest-risk target because it is injected directly into the sandbox without a runtime proxy (unlike `json` and `math` which use `ModuleProxy`). This allows full traversal of the COM wrapper module's internal state.

Note: f-strings like `f"{staad.__class__}"` ARE protected because Python's parser creates `ast.Attribute` nodes for expressions inside f-strings. Only `str.format()` and `format_map()` bypass the check.

### Affected Code

**File:** [/sources/openstaad-mcp/src/openstaad_mcp/sandbox/ast.py:79-80](/sources/openstaad-mcp/src/openstaad_mcp/sandbox/ast.py#L79-L80)
```python
    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__") and node.attr.endswith("__"):
            self._err(node, f"access to dunder attribute '{node.attr}' is not allowed")
```

This check only catches dunder access expressed as `ast.Attribute` nodes (e.g., `obj.__class__`). It does not detect dunder names embedded inside string constants used by `str.format()`. No `visit_Constant` or `visit_Str` method exists in the visitor to inspect string content.

**File:** [/sources/openstaad-mcp/src/openstaad_mcp/sandbox/const.py:20](/sources/openstaad-mcp/src/openstaad_mcp/sandbox/const.py#L20)
```python
ALLOWED_BUILTINS: frozenset[str] = frozenset(
    {
        ...
        "format",
        ...
        "str",
        ...
    }
)
```

Both `format` and `str` are in `ALLOWED_BUILTINS`, giving sandbox code full access to `str.format()`, `str.format_map()`, and the `format()` built-in.

**File:** [/sources/openstaad-mcp/src/openstaad_mcp/sandbox/executor.py:112](/sources/openstaad-mcp/src/openstaad_mcp/sandbox/executor.py#L112)
```python
sandbox_globals["staad"] = staad_object
```

The `staad` COM object is injected raw -- not wrapped in a `ModuleProxy`. There is no runtime enforcement of attribute access on this object.

**File:** [/sources/openstaad-mcp/src/openstaad_mcp/sandbox/module_proxy.py:27-28](/sources/openstaad-mcp/src/openstaad_mcp/sandbox/module_proxy.py#L27-L28)
```python
if name in {"__class__", "__repr__", "__setattr__", "__delattr__"}:
    return object.__getattribute__(self, name)
```

ModuleProxy passes through `__class__` access, so even proxied objects would be partially vulnerable to format string traversal.

### Root Cause Analysis
- **Vulnerable code explanation**: The AST validator implements a denylist for dunder attribute nodes, but `str.format()` performs attribute resolution at runtime via Python's internal `getattr()` mechanism. The format mini-language allows dotted attribute paths (e.g., `{0.__class__.__mro__}`) that resolve to arbitrary object attributes. The AST never sees these attribute accesses -- they appear only as a string constant.
- **Attack prerequisites**: Ability to invoke the `execute_code` MCP tool (any MCP client connected to the server). The sandbox is specifically designed to be called by AI agents.
- **Impact assessment**: Information disclosure (class hierarchy, available subclasses, internal Python state, module globals, file paths, import graphs). Through `__init__.__globals__`, an attacker can reach unrestricted `__builtins__` from external modules. Potential full sandbox escape and arbitrary code execution via `__subclasses__()` chain, though direct method calls through format strings are limited. Combined with other sandbox primitives, this significantly weakens the sandbox boundary.

## Proof of Concept

```python
# Step 1: Leak the class of any sandbox object (passes AST validation)
result = "{0.__class__}".format(staad)
# Output: <class 'win32com.client.CDispatch'>

# Step 2: Traverse the MRO to reach 'object'
result = "{0.__class__.__mro__}".format([])

# Step 3: Traverse to module globals
globals_info = "{0.__class__.__init__.__globals__}".format(staad)
# Output: string repr of win32com.client module's globals dict

# Step 4: Access unrestricted __builtins__ from an external module
builtins_info = "{0.__class__.__init__.__globals__[__builtins__]}".format(staad)
# Output: string repr of the real, unrestricted __builtins__

# Step 5: format_map() also works
result = "{x.__class__.__name__}".format_map({"x": staad})

# Step 6: Traverse ModuleProxy objects
proxy_class = "{0.__class__.__init__.__globals__}".format(json)
# Output: module_proxy.py globals (internal server code structure)
```

**PoC Script:** [/sources/openstaad-mcp/../results/reports_1/poc/OMCP-001-format-bypass.py](/sources/openstaad-mcp/../results/reports_1/poc/OMCP-001-format-bypass.py)

## Fix Recommendations

1. **Add format string content inspection to AST validator** (Recommended): Add a `visit_Constant` method to the `_Visitor` class that scans string literals for format-string patterns containing dunder attribute paths:
```python
import re
_FORMAT_DUNDER_RE = re.compile(r'\{[^}]*\.__[a-zA-Z_]+__')

def visit_Constant(self, node: ast.Constant) -> None:
    if isinstance(node.value, str) and _FORMAT_DUNDER_RE.search(node.value):
        self._err(node, "format strings with dunder attribute access are not allowed")
    self.generic_visit(node)
```

2. **Block `format` and `format_map` method calls in the AST validator**:
```python
def visit_Call(self, node: ast.Call) -> None:
    if isinstance(node.func, ast.Attribute):
        if node.func.attr in ("format", "format_map"):
            self._err(node, f"'{node.func.attr}()' is not allowed in the sandbox")
    # ... existing checks
```

3. **Remove `format` from `ALLOWED_BUILTINS`** or replace it with a safe wrapper that strips dunder path segments from the format spec before calling the real `format()`. Note: the `format` in `ALLOWED_BUILTINS` is the builtin `format()` function, not `str.format()`. Blocking it alone is insufficient.

4. **Wrap the `staad` object in a proxy** (similar to `ModuleProxy`) that intercepts `__getattr__` and enforces the same dunder/blocked-attrs restrictions at runtime.

5. **Block `format_map` as a method call** in the AST validator -- add it to a blocked-methods list for string objects.

6. **Defense-in-depth**: Add a custom `__format__` method to proxy objects that refuses to expose dunder attributes.

## Semgrep Rule Suggestion (if applicable)

- **Pattern type**: Pattern match on `str.format()` calls with dunder field names / string constants containing dunder format specifiers
- **Why automatable**: This is a systematic pattern -- any Python sandbox using AST-only dunder blocking is vulnerable to `str.format()` bypass
- **Suggested rule name**: python.security.sandbox-format-string-dunder-bypass

## Bypass Analysis

### Bypass Hypothesis
- The AST validator blocks `ast.Attribute` nodes containing dunder names, but `str.format()` mini-language performs attribute access at runtime using internal C-level `getattr()`, completely bypassing the static check.
- `str.format_map()` offers the same bypass vector.
- The `format()` built-in function calls `__format__()` on the target object, which may also expose internal state.

### Likelihood Assessment
- **High**: The bypass is trivial, requires zero special knowledge beyond Python format string syntax, and the PoC passes both AST validation and runtime execution.

### Evidence
- `str.format()` is not restricted in any way -- it's a method on string objects, and string literals are allowed
- The AST never sees the attribute access performed by `str.format()` at runtime
- `format` is explicitly whitelisted in `ALLOWED_BUILTINS`
- The `staad` object has no runtime attribute access protection
- AST validator has no `visit_Constant` or `visit_Str` method
- Python's format mini-language supports arbitrary-depth attribute traversal via `.` notation

---

## Source Reports
- [/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_1/OMCP-001-sandbox-format-string-dunder-bypass.md](/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_1/OMCP-001-sandbox-format-string-dunder-bypass.md)
- [/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_2/OMCP-002-sandbox-bypass-format-string-dunder.md](/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_2/OMCP-002-sandbox-bypass-format-string-dunder.md)
- First discovered: Apr-14-2026-0000
- Validated: Apr-14-2026

## Report Metadata
| Field | Value |
|-------|-------|
| Agent | GitHub Copilot |
| Model | Claude Opus 4.6 |
| Timestamp | Apr-14-2026-0000 |
