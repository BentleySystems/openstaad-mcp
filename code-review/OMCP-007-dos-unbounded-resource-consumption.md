# OMCP-007: Denial of Service via Unbounded Sandbox Resource Consumption

## Overview
| Field | Value |
|-------|-------|
| ID | OMCP-007 |
| Title | Denial of Service via Unbounded Sandbox Resource Consumption |
| Severity | Medium |
| CVSS Score | 5.3 |
| Auth Required | No |
| Local/Remote | Remote |
| Status | Confirmed |
| Category | Product Code Finding |

## SVS Mapping
- **TASVS**: N/A
- **ASVS**: ASVS-11.1.4 - Application logic protects against denial of service

## CWE Reference
- **CWE-400**: Uncontrolled Resource Consumption
- **CWE-770**: Allocation of Resources Without Limits or Throttling

## Vulnerability Details

### Description

The sandbox executor has multiple resource exhaustion vectors:

**1. Unbounded stdout buffer**: The sandbox captures stdout/stderr during code execution into `StringIO` buffers. While the output is truncated to `MAX_EXECUTION_STDOUT` (256 KB) AFTER execution completes, the `StringIO` buffers grow **unboundedly during execution**. An attacker can exhaust server memory by printing large amounts of data, causing the server process to crash with an Out-of-Memory error.

**2. Memory allocation**: No memory limit exists for sandbox code. Expressions like `x = [0] * (10**9)` allocate ~8 GB, potentially crashing the server process.

**3. CPU exhaustion**: Infinite or long-running loops consume CPU until the 120-second timeout. The daemon thread is then abandoned, leaking thread resources.

**4. Abandoned thread accumulation**: Each timed-out execution leaves an abandoned daemon thread that may hold COM resources indefinitely, eventually exhausting system resources.

The `print` built-in is allowed (`ALLOWED_BUILTINS`), and string multiplication (`str * int`) is not restricted. The execution timeout is handled by the connection layer (default 120 seconds), but memory exhaustion can occur well within that window.

### Affected Code

**File:** [/sources/openstaad-mcp/src/openstaad_mcp/sandbox/executor.py:118-138](/sources/openstaad-mcp/src/openstaad_mcp/sandbox/executor.py#L118-L138)
```python
captured_out, captured_err = io.StringIO(), io.StringIO()
# ...
with self._exec_lock:
    old_stdout, old_stderr = sys.stdout, sys.stderr
    start = time.perf_counter()
    try:
        sys.stdout, sys.stderr = captured_out, captured_err
        exec(compile(rewritten, "<sandbox>", "exec"), sandbox_globals)
    # ...

stdout_text = captured_out.getvalue()[:MAX_EXECUTION_STDOUT]  # Truncation AFTER execution
stderr_text = captured_err.getvalue()[:MAX_EXECUTION_STDOUT]
```

The truncation at line 137-138 only applies after `exec()` returns. During execution, the buffer grows without limit.

**File:** [/sources/openstaad-mcp/src/openstaad_mcp/sandbox/const.py:156](/sources/openstaad-mcp/src/openstaad_mcp/sandbox/const.py#L156)
```python
MAX_EXECUTION_STDOUT = 256_000
```

This constant is only used for post-execution truncation, not for in-flight limiting.

**File:** [/sources/openstaad-mcp/src/openstaad_mcp/connection.py:173-185](/sources/openstaad-mcp/src/openstaad_mcp/connection.py#L173-L185)
```python
t = threading.Thread(target=_worker, daemon=True)
t.start()
if not done.wait(timeout=timeout):
    raise TimeoutError(f"COM call did not complete within {timeout}s")
# Thread continues running in background
```

### Root Cause Analysis
- **Vulnerable code explanation**: Standard `io.StringIO()` has no size limit. The sandbox redirects `sys.stdout` to this buffer, then allows unrestricted `print()` calls. Truncation happens post-execution, too late to prevent memory exhaustion. No memory limits, no thread resource tracking, no stdout size enforcement during execution.
- **Attack prerequisites**: Ability to invoke the `execute_code` MCP tool.
- **Impact assessment**: Server process OOM crash, affecting all connected MCP clients. Since the server is typically a single process, this is a full denial of service. CPU exhaustion degrades performance for the legitimate user. Abandoned threads leak resources over time.

## Proof of Concept

```python
# Method 1: Rapid large writes (allocates ~1GB quickly)
print("A" * (10 ** 9))

# Method 2: Loop-based (fills buffer over time)
for i in range(10000000):
    print("A" * 100)

# Method 3: String multiplication
x = "A" * 1000000
for i in range(10000):
    print(x)

# Method 4: Memory allocation (no print needed)
x = [0] * (10**9)  # ~8 GB allocation
```

## Fix Recommendations

1. **Implement a size-limited StringIO wrapper**:
```python
class LimitedStringIO(io.StringIO):
    def __init__(self, max_size=MAX_EXECUTION_STDOUT):
        super().__init__()
        self._max_size = max_size
        self._size = 0

    def write(self, s):
        if self._size >= self._max_size:
            return 0  # Silently discard
        remaining = self._max_size - self._size
        to_write = s[:remaining]
        written = super().write(to_write)
        self._size += written
        return written
```

2. **Track abandoned threads** and refuse new executions if too many are outstanding.

3. **Add string length limits**: Cap single `print()` calls or total allocation via a custom `print` wrapper in `safe_builtins`.

4. **Memory monitoring**: Monitor process memory during execution and kill the exec if it exceeds a threshold.

## Semgrep Rule Suggestion (if applicable)

- **Pattern type**: Pattern match -- `io.StringIO()` used as stdout capture without size limiting
- **Why automatable**: Common pattern in Python sandboxes
- **Suggested rule name**: python.security.unbounded-stringio-stdout-capture

---

## Source Reports
- [/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_1/OMCP-004-dos-unbounded-stdout-buffer.md](/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_1/OMCP-004-dos-unbounded-stdout-buffer.md)
- [/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_2/OMCP-005-sandbox-missing-resource-limits.md](/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_2/OMCP-005-sandbox-missing-resource-limits.md)
- First discovered: Apr-14-2026-0000
- Validated: Apr-14-2026

## Report Metadata
| Field | Value |
|-------|-------|
| Agent | GitHub Copilot |
| Model | Claude Opus 4.6 |
| Timestamp | Apr-14-2026-0000 |
