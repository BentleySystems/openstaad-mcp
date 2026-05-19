# Monty Sandbox Architecture

This document describes the sandboxed code-execution pipeline used by the
`execute_code` MCP tool.  The design is intended to be extracted into a
standalone, reusable package.

## Overview

User-authored Python code is executed inside
[pydantic-monty](https://pypi.org/project/pydantic-monty/), a minimal secure
Python interpreter written in Rust.  COM interaction with STAAD.Pro is bridged
through *external functions* that the host provides — the sandbox code never
touches pywin32 objects directly.

```
┌─────────────────────────────────────────────────────────┐
│  User code (natural Python syntax)                      │
│                                                         │
│    geo = staad.Geometry                                 │
│    count = geo.GetNodeCount()                           │
│    staad.SaveModel()                                    │
└──────────────────────┬──────────────────────────────────┘
                       │
              ┌────────▼─────────┐
              │   AST Rewriter   │  rewriter.py
              │   (compile-time) │
              └────────┬─────────┘
                       │  transforms to:
                       │    geo = _dispatch("staad.Geometry")
                       │    count = _dispatch("staad.Geometry.GetNodeCount")
                       │    _dispatch("staad.SaveModel")
              ┌────────▼─────────┐
              │  Monty Sandbox   │  pydantic_monty.Monty
              │  (Rust runtime)  │
              │  ┌─────────────┐ │
              │  │ _dispatch() ├─┼──── external function
              │  └──────┬──────┘ │
              └─────────┼────────┘
                        │
              ┌─────────▼────────┐
              │  Host Dispatcher │  monty_executor.py
              │                  │
              │  Gate 1: Handle  │
              │  Gate 2: Deny    │
              │  Gate 3: Allow   │
              │  Gate 4: Consent │
              │  Gate 5: Args    │
              └─────────┬────────┘
                        │
              ┌─────────▼────────┐
              │    COM Proxy     │  com_proxy.py
              │                  │
              │  UNC blocking    │
              │  Path validation │
              │  Extension check │
              │  Protected dirs  │
              │  Attr hiding     │
              └─────────┬────────┘
                        │
              ┌─────────▼────────┐
              │  STAAD.Pro COM   │
              │  (pywin32)       │
              └──────────────────┘
```

## Components

### 1. AST Rewriter (`rewriter.py`)

Transforms natural `staad.X.Method()` syntax into `_dispatch("staad.X.Method")`
calls at compile time, before the code enters the Monty sandbox.

**Key behaviours:**

- `staad.GetBaseUnit()` → `_dispatch("staad.GetBaseUnit")`
- `staad.Geometry.GetNodeCount()` → `_dispatch("staad.Geometry.GetNodeCount")`
- Alias expansion: `geo = staad.Geometry; geo.GetNodeCount()` →
  `geo = _dispatch("staad.Geometry"); _dispatch("staad.Geometry.GetNodeCount")`
- Only rewrites call chains rooted at registered proxy names (default: `{"staad"}`)
- Non-proxy code passes through unchanged

**Public API:**

```python
from openstaad_mcp.sandbox.rewriter import rewrite_proxy_calls

rewritten = rewrite_proxy_calls(code, proxy_names=frozenset({"staad"}))
```

### 2. Monty Executor (`monty_executor.py`)

Orchestrates the full execution pipeline:

1. **Pre-flight** — rejects oversized source code
2. **AST rewrite** — transforms natural syntax via `rewrite_proxy_calls()`
3. **State setup** — wraps the COM object with `COMProxy`, builds a handle
   table (handle 0 = root STAAD object)
4. **External functions** — registers `_dispatch` as the single external
   function exposed to the Monty runtime
5. **Resource limits** — configures Monty's Rust-enforced limits (timeout,
   memory, allocations, recursion depth)
6. **Execution** — runs the rewritten code in a fresh `pydantic_monty.Monty`
   instance
7. **Result sanitisation** — truncates oversized outputs, strips system paths

**`_dispatch` routing** handles three path shapes:

| Path | Action |
|------|--------|
| `staad.SubObject` | Resolve sub-object, return handle |
| `staad.Method(...)` | Root method call |
| `staad.SubObject.Method(...)` | Resolve sub-object + method call |

**Security gates** (applied in `_host_com_invoke` before every COM call):

| Gate | Purpose |
|------|---------|
| Handle validation | Rejects forged/invalid handles |
| Global deny list | Unconditionally blocks dangerous methods (e.g. NTLM relay vectors) |
| Positive allowlist | Only explicitly enumerated methods per sub-object are permitted |
| Consent gate | Destructive methods (file writes, `Quit`, `SaveModel`) require `allow_destructive=True` |
| Argument validation | Only JSON-safe scalars and flat lists pass through |

**Per-call isolation:** each `execute()` creates a fresh Monty instance with a
new handle table.  No state leaks between calls.

**Public API:**

```python
from openstaad_mcp.sandbox.monty_executor import MontyExecutor

executor = MontyExecutor(
    timeout_seconds=30.0,
    max_memory_bytes=64 * 1024 * 1024,
    max_code_bytes=64 * 1024,
)

result = executor.execute(code, staad_object, allow_destructive=False)
# result.success, result.result, result.stdout, result.stderr, result.error
```

### 3. COM Proxy (`com_proxy.py`)

Runtime wrapper around pywin32 `CDispatch` objects.  Applies argument-level
security that the allowlist/deny-list pipeline cannot enforce:

- **UNC path blocking** — all string arguments to any COM method are checked
  against `\\server\share`, `//server/share`, `\\?\UNC\...` patterns
- **Path validation** for file-writing methods (`NewSTAADFile`, `OpenSTAADFile`,
  `SaveAs`, `ExportView`):
  - Must be absolute paths (drive letter required)
  - Must not contain `..` segments (path traversal)
  - Must have an allowed file extension (`.std`, `.png`, `.jpg`, etc.)
  - Must not target protected OS directories (`Windows`, `Program Files`, etc.)
  - Null bytes are rejected
- **Attribute hiding** — blocks access to pywin32 internals (`_oleobj_`,
  `_ApplyTypes_`, etc.) and all dunder attributes
- **Immutability** — `setattr`/`delattr` on COM objects is blocked
- **Recursive wrapping** — returned sub-objects are automatically wrapped

**Public API:**

```python
from openstaad_mcp.sandbox.com_proxy import COMProxy, validate_file_path

proxied = COMProxy(raw_com_object)
proxied.GetApplicationVersion()       # allowed
proxied.SaveAs("C:\\models\\v2.std")  # path-validated, then forwarded
proxied.SaveAs("\\\\evil\\share.std") # raises ValueError (UNC blocked)
```

### 4. Security Constants (`constants.py`)

Central configuration for all security controls:

```python
ALLOWED_SUB_OBJECTS       # {"Geometry", "Output", "Property", "Load", ...}
ALLOWED_ROOT_METHODS      # {"GetApplicationVersion", "GetSTAADFile", ...}
ALLOWED_SUB_OBJECT_METHODS  # {"Geometry": {"GetNodeCount", ...}, ...}
DENIED_METHODS            # {"SetStandardProfileDBFolder", ...}
DESTRUCTIVE_METHODS       # {"_root": {"SaveModel", "Quit", ...}, ...}

# Resource limits
EXECUTION_TIMEOUT_SECONDS = 30
MAX_MEMORY_BYTES = 64 * 1024 * 1024
MAX_CODE_BYTES = 64 * 1024
MAX_RESULT_LENGTH = 100_000
```

## File Layout

```
sandbox/
├── __init__.py
├── com_proxy.py        # Runtime COM wrapper (path validation, UNC blocking)
├── constants.py        # Allowlists, deny lists, resource limits
├── monty_executor.py   # Orchestrator (Monty setup, dispatch, result handling)
└── rewriter.py         # AST rewriter (natural syntax → _dispatch calls)
```

## Security Model Summary

The sandbox enforces defence-in-depth through three independent layers:

1. **Monty runtime** (Rust) — process isolation, resource limits, no filesystem/
   network/env access, restricted imports
2. **Host dispatcher** (Python) — allowlists, deny list, consent gate, argument
   type validation
3. **COM proxy** (Python) — path validation, UNC blocking, extension checks,
   protected directory guards, pywin32 internals hiding

Each layer is independently testable.  A bypass in any single layer is caught
by the others.

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pydantic-monty` | ≥ 0.0.17 | Rust-based secure Python interpreter |
| `pywin32` | ≥ 311 | COM automation (Windows only) |

## Extracting as a Standalone Package

To extract the sandbox into a reusable package:

1. Copy the `sandbox/` directory as the package root
2. Replace `constants.py` with a configuration API — the allowlists and deny
   lists become constructor parameters or a config file
3. Replace the `staad`-specific proxy name in `_PROXY_NAMES` with a generic
   parameter
4. The `COMProxy` path rules (`VALIDATED_COM_METHODS`) should be passed in
   rather than hardcoded
5. The `MontyExecutor.execute()` signature stays the same — callers provide the
   COM object and code string

The only STAAD-specific pieces are:
- The method allowlists in `constants.py`
- The proxy name `"staad"` in `_PROXY_NAMES`
- The path validation rules in `VALIDATED_COM_METHODS`

Everything else (Monty orchestration, AST rewriting, handle table, security
gates, COM proxy infrastructure) is generic.
