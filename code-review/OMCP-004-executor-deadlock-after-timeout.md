# OMCP-004: Permanent Executor Deadlock After COM Timeout

## Overview
| Field | Value |
|-------|-------|
| ID | OMCP-004 |
| Title | Permanent Executor Deadlock After COM Timeout |
| Severity | High |
| CVSS Score | 7.5 |
| Auth Required | No |
| Local/Remote | Remote |
| Status | Confirmed |
| Category | Product Code Finding |

## SVS Mapping
- **TASVS**: N/A
- **ASVS**: ASVS-11.1.4 - Application logic protects against denial of service

## CWE Reference
- **CWE-833**: Deadlock
- **CWE-400**: Uncontrolled Resource Consumption

## Vulnerability Details

### Description

When a `connect_and_run()` call times out (default 120 seconds), the caller raises `TimeoutError` and abandons the daemon worker thread. However, that daemon thread is still executing inside `Executor.execute()`, holding `self._exec_lock` (a `threading.Lock()` acquired via `with self._exec_lock:`). Since the thread is abandoned (daemon threads cannot be interrupted in Python), the lock is **never released**.

All subsequent calls to `execute_code` will attempt to acquire the same `_exec_lock`, which is permanently held by the abandoned thread. This results in a **permanent deadlock** -- the MCP server requires a full restart to recover.

### Affected Code

**File:** [/sources/openstaad-mcp/src/openstaad_mcp/sandbox/executor.py:118-126](/sources/openstaad-mcp/src/openstaad_mcp/sandbox/executor.py#L118-L126)
```python
        with self._exec_lock:                                    # Lock acquired in worker thread
            old_stdout, old_stderr = sys.stdout, sys.stderr
            start = time.perf_counter()
            try:
                sys.stdout, sys.stderr = captured_out, captured_err
                exec(compile(rewritten, "<sandbox>", "exec"), sandbox_globals)
```

**File:** [/sources/openstaad-mcp/src/openstaad_mcp/connection.py:207-211](/sources/openstaad-mcp/src/openstaad_mcp/connection.py#L207-L211)
```python
    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    if not done.wait(timeout=timeout):
        raise TimeoutError(f"COM call did not complete within {timeout}s")
```

**Execution flow:**
1. `execute_code` -> `connect_and_run(_run, file_path)` -> spawns daemon thread
2. Daemon thread calls `_run(staad)` -> `exc.execute(code, staad)` -> `with self._exec_lock:` -- **lock acquired**
3. COM operation inside `exec()` hangs beyond 120s timeout
4. Main thread: `done.wait(timeout=120)` returns `False` -> `raise TimeoutError`
5. Daemon thread continues running, still holding `_exec_lock` -- **never released**
6. Next `execute_code` call -> new daemon thread -> `with self._exec_lock:` -> **blocks forever**

### Root Cause Analysis
- **Vulnerable code explanation**: The `_exec_lock` is a non-reentrant `threading.Lock()` with no timeout on acquisition. COM operations cannot be cancelled when running in a daemon thread. The `with` statement only releases the lock when the `exec()` call returns, which never happens for the abandoned thread.
- **Attack prerequisites**: Trigger a COM operation that exceeds the timeout. This can be done intentionally (e.g., `staad.AnalyzeEx()` on a large model) or by exploiting a COM server hang.
- **Impact assessment**: Permanent denial of service for the `execute_code` tool. All MCP clients lose code execution capability until the server process is restarted. The `discover_api`, `read_skills`, `list_instances`, and `get_status` tools remain functional.

## Proof of Concept

```python
# Trigger a long-running COM operation that exceeds 120s timeout
# (e.g., full structural analysis on a complex model)
staad.AnalyzeEx(1, 0, 1)

# After timeout, all subsequent execute_code calls hang indefinitely
```

## Fix Recommendations

1. **Move `_exec_lock` acquisition outside `connect_and_run`'s worker thread**: Acquire the lock in the calling context and release it when the timeout fires:
```python
def execute(self, code, staad_object):
    with self._exec_lock:
        # ... validation, rewrite ...
        # Execute without the lock, or use a timeout-aware lock
```

2. **Use a timeout-aware lock**: Replace `threading.Lock()` with a lock that supports `acquire(timeout=...)`:
```python
if not self._exec_lock.acquire(timeout=5.0):
    return ExecutionResult(success=False, error="Executor busy -- previous operation may have timed out")
try:
    # ... execute ...
finally:
    self._exec_lock.release()
```

3. **Alternative**: Move stdout/stderr capture to use `contextlib.redirect_stdout`/`redirect_stderr` with thread-local storage instead of global `sys.stdout`/`sys.stderr` reassignment, eliminating the need for the lock entirely.

## Semgrep Rule Suggestion (if applicable)

- **Pattern type**: Pattern match -- `threading.Lock()` acquired in a thread that may be abandoned via timeout
- **Why automatable**: Common pattern in daemon-thread-with-timeout architectures
- **Suggested rule name**: python.security.deadlock-lock-in-abandoned-daemon-thread

---

## Source Reports
- [/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_1/OMCP-010-executor-deadlock-after-timeout.md](/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_1/OMCP-010-executor-deadlock-after-timeout.md)
- First discovered: Apr-14-2026-0000
- Validated: Apr-14-2026

## Report Metadata
| Field | Value |
|-------|-------|
| Agent | GitHub Copilot |
| Model | Claude Opus 4.6 |
| Timestamp | Apr-14-2026-0000 |
