# File I/O for User Workflows

**Status:** Proposal  
**Author:** Dave Hanson  
**Date:** 2026-05-01

## The problem

Users want workflows like "read this CSV and create a beam for each row" or "run this analysis and put results in a CSV with these columns." The WASM sandbox physically cannot access the filesystem, and that is by design. But file I/O is a must-have for the workflows that structural engineers actually do with STAAD. Ignoring this is not an option.

The current architecture gives the agent exactly one way to interact with STAAD: `execute_code`. That tool runs JavaScript inside a WebAssembly isolate with zero filesystem access. We are not going to change that. The sandbox stays clean. So how do we get data in and out of files without opening a hole in the isolation model?

[Skip straight to Proposed solution](#proposed-solution-mcp-layer-compound-tools-outside-the-sandbox)

## Constraints

### Anthropic Software Directory Policy

Source: [Anthropic Software Directory Policy](https://support.claude.com/en/articles/13145358-anthropic-software-directory-policy)

1. **§1B.** "Software must not evade or enable users to circumvent Claude's safety guardrails, system instructions, or sandbox environments."

2. **§1D.** "Software must only collect data from the user's context that is necessary to perform their function. Software must not collect extraneous conversation data, even for logging purposes."

3. **§2B.** "Instructional Software tool or capability descriptions must precisely match actual functionality, ensuring the Instructional Software is called at correct and appropriate times. Descriptions must not include unexpected functionality or promise undelivered features."

4. **§2D.** "Instructional Software must not intentionally call or coerce Claude into calling other external software, tools, databases, or resources unless requested and intended by a user."

5. **§5A.** "MCP servers must gracefully handle errors and provide helpful feedback rather than generic error messages."

6. **§5B.** "MCP servers must be frugal with their use of tokens. The amount of tokens a given tool call uses should be roughly commensurate with the complexity or impact of the task. When possible, users should be given options to exclude unnecessary text in the response."

7. **§5E.** "MCP servers must provide all applicable annotations for their tools, in particular readOnlyHint, destructiveHint, and title."

### Bentley Security Architecture, §10 "Isolation Requirements for Code Mode"

Source: [security-architecture.md](security-architecture.md), §10 User "Code Mode" baseline requirements

8. **§10(1).** "No external network access. Restricted to user machine local network by default."

9. **§10(3).** "No arbitrary filesystem access. Restricted to defined working directory(ies). User consent and directory selection should be required."

10. **§10(4).** "Controlled API access. Restricted to defined product APIs based on advertised capabilities of agentic workflows and subject to development governance. Product APIs should be progressively exposed based on user consent such that user opts into increasingly powerful, security-sensitive APIs."

11. **§10 (shadow API prohibition).** "It would be ill-advised to define LLM-enablement shadow APIs that simply open holes in 'code mode' isolation to circumvent requirements (1 - 3)."

### Bentley Security Architecture, Control 4

Source: [security-architecture.md](security-architecture.md), §5 Control 4 "Explicit Consent for State-Changing Actions"

12. **Control 4.** "Applications integrating the MCP Host must implement an approval gate for operations that modify state or have external side effects, as determined by the TCM's requiresUserApproval field."

## Proposed solution: MCP-layer compound tools (outside the sandbox)

Two new MCP tools at the server layer. Completely outside the WASM sandbox. Both are "compound" tools: they combine file I/O with code execution in a single call so bulk data stays server-side and never enters the agent's context window. This is the core design constraint. A 10,000-row member force extraction is ~1.4 MB of JSON. If that transits through agent context (read tool returns data, agent passes data to write tool), it consumes ~350K tokens each direction. That blows the context window on every non-trivial export. The compound architecture eliminates this entirely: bulk data flows from file to sandbox to file without ever touching the LLM.

### Architecture: server-side data brokering

```
Agent context (only sees summaries + sample rows)
  |
  +-- read_and_execute(path, code, instance?)
  |       server: read file -> inject as __input -> run code -> return result
  |       agent sees: code output + first N rows of input for verification
  |
  +-- execute_and_write(code, path, columns, instance?)
          server: run code -> capture return value -> write to file
          agent sees: row count + first N rows for verification
```

Both tools keep bulk data in Python server memory. The sandbox sees data arrive via `__input` (read path) or leave via return value (write path). Neither direction grants new capabilities to the sandbox. The agent never holds raw file content or raw result sets.

**How "peek" works without a simple read tool:** The `read_and_execute` response always includes `input_summary.sample_rows` (first 5 rows). If the agent needs more visibility, it writes code like `return __input.slice(0, 50)` to return a subset as the execution result. This covers the "show me what's in this file" case without a dedicated read tool.

**Why there is no simple write tool:** `execute_and_write` handles both cases. For STAAD extraction (the dominant case), the code is a small loop and the output is huge: 500 members x 20 load cases = 10,000 rows from ~200 bytes of iteration logic. Code size is irrelevant. For agent-assembled data with no STAAD source (e.g. a summary table the agent built in context), the agent puts the data directly in the code as a literal: `return [[1, "W12X26", 3.5], ...]`. The 256 KiB code size limit caps this at ~1,800 rows of inline data. That is not a real constraint because any dataset larger than that should be coming from STAAD extraction or from a file via `read_and_execute`, not from the agent's context window.

### Design decision: CSV + xlsx via openpyxl

We support `.csv` and `.xlsx`. No `.xls`, no `.xlsm`, no `.tsv`.

Both tools are a common data broker. Regardless of file format, the interface is:
- **Read path (`read_and_execute`):** file on disk → library parses → array of arrays injected into sandbox as `__input`
- **Write path (`execute_and_write`):** sandbox returns array of arrays → library serializes → file on disk

The agent never sees format-specific details (encoding, quoting, XML structure). It sees JSON arrays in, JSON arrays out. The libraries handle serialization:

- **CSV:** Python stdlib `csv` module. Handles quoting, encoding, delimiters internally.
- **xlsx:** `openpyxl` in read-only/write-only streaming modes. Handles cell types, shared strings, XML serialization internally. `data_only=True` on read returns cached formula values (the computed number, not the formula string). `defusedxml` installed alongside for XML entity expansion protection.

**Format-specific behaviour worth noting:**
- xlsx read defaults to the active sheet. A `sheet_name` parameter targets a specific sheet.
- xlsx formula cells return their last-computed cached value. Cells never opened in Excel after formula creation return `None`.
- `.xlsm` (macro-enabled) is rejected. No VBA execution.

**Why both formats:**
- CSV is universally readable and has zero dependency cost.
- xlsx is what structural engineers actually produce and consume. Beam schedules, load tables, and material lists from coordination spreadsheets are almost always `.xlsx` files shared via email or SharePoint. Forcing engineers to save-as-CSV before every workflow adds friction that undermines adoption.
- The two formats share the same MCP tool interface. The server dispatches to the correct reader/writer based on file extension. The agent sees identical JSON output regardless of source format.

### openpyxl dependency assessment

**Security posture:**

| Source | Finding |
|--------|---------|
| NVD (NIST) | Zero CVEs. Search: [nvd.nist.gov/vuln/search?query=openpyxl](https://nvd.nist.gov/vuln/search/results?query=openpyxl&search_type=all&results_type=overview) returns no results for openpyxl. |
| Snyk | Zero vulnerabilities on latest version (3.1.5). One historical advisory across 95 versions total, affecting only old versions. Current version: 0 Critical, 0 High, 0 Medium, 0 Low. Source: [security.snyk.io/package/pip/openpyxl](https://security.snyk.io/package/pip/openpyxl) |
| PyPI downloads | ~262 million downloads/month (pypistats.org). Top-tier adoption. |
| Maturity | 15 years on PyPI. 95 releases. MIT licence. Latest release: v3.1.5, June 2024. |
| Dependencies | Single dependency: `et-xmlfile` (lightweight iterative XML parser, also MIT). |
| XML safety | openpyxl documents that it does not guard against quadratic blowup or billion laughs XML attacks by default. It recommends installing `defusedxml` for protection. We will include `defusedxml` as a dependency alongside `openpyxl`. |

**Architectural placement:**

openpyxl runs in the MCP server process (Python side), NOT in the WASM sandbox. The security control sequence is:

1. Agent calls `read_and_execute(path="schedule.xlsx", code="...")`
2. Path validation fires (see "Path validation strategy"): model guard, resolve, UNC reject, containment check, existence check.
3. File size check fires (50 MB on-disk cap)
4. Only THEN does openpyxl open the file
5. openpyxl reads cell values, server converts to Python list of lists
6. Data injected into sandbox as frozen `__input`

openpyxl never sees an unvalidated path. The file has already passed all security gates before the library touches it. The 50 MB file size cap also limits the blast radius from any hypothetical XML parsing issue (billion laughs payloads need large files to be effective, and `defusedxml` blocks them regardless).

**Write path:** `execute_and_write` constructs the workbook from the sandbox's return value (array of arrays of JSON primitives). The data originates from controlled code execution inside the WASM isolate. openpyxl never parses untrusted xlsx content on the write path.

**Supply-chain risk mitigation:** Exact version pins in `pyproject.toml`. Both packages are pure Python, no native compilation step, reproducible installs. See Dependencies section for version details.

### Path validation strategy

Both tools share a single path validation function. The sequence is:

1. **Model guard.** `GetSTAADFile()` must return a valid path. If no model is open, return `NO_MODEL_OPEN` immediately.
2. **Resolve.** `Path.resolve()` normalizes input to a real absolute path. Follows symlinks, collapses `..`, resolves `/` to `\` on Windows. After this call, the path is canonical and all subsequent checks are reliable.
3. **UNC reject.** If the resolved path starts with `\\`, reject with `UNC_REJECTED`. Message: "Network paths (UNC) are not supported. Copy your files to a local drive or map the network location to a drive letter (e.g. Z:\)."
4. **Containment check.** `resolved.is_relative_to(model_dir)` where `model_dir = Path(GetSTAADFile()).resolve().parent`. If the path escapes the model directory, reject with `PATH_OUTSIDE_MODEL_DIR`.
5. **Existence check (read only).** For reads, the file must exist. For writes, the parent directory must exist.

This sequence runs identically for both tools. It is a single function in the codebase, not duplicated logic. Subdirectories under the model directory are accessible (e.g. `project/input/beams.csv`); `is_relative_to` passes for any path at or below `model_dir`.

### Why this works

The sandbox never touches files. Each tool is independently auditable with a clear risk profile:

| Tool | Reads file? | Writes file? | Modifies STAAD? | `destructiveHint` |
|------|------------|-------------|----------------|-------------------|
| `read_and_execute` | Yes | No | Yes (via code) | `true` |
| `execute_and_write` | No | Yes | Maybe (via code) | `true` |

Both tools are `destructiveHint=true`. Both require host confirmation before invocation. The agent cannot silently read or write files. The data flow is explicit and visible to the host. Bulk data stays server-side, reducing both token cost and prompt-injection surface. This is exactly the trust model Claude Desktop already uses for destructive tools.

### `read_and_execute` (compound: file → STAAD)

The bulk-import tool. Reads a file server-side, injects the data into the sandbox as a pre-bound `__input` variable, and executes user code that operates on it. The full dataset never enters agent context.

**Data flow:**
1. Path validation (shared function)
2. Server reads file via csv/openpyxl, converting cell values to JSON primitives during row iteration (datetime → ISO 8601 string, numeric coercion for CSV text)
3. Data injected into sandbox as `Object.freeze`'d `__input` global before code execution
4. User code accesses `__input` directly (no function call, no host function)
5. Return value sent back to agent as normal `execute_code` result

**Example agent call:**
```json
{
  "tool": "read_and_execute",
  "arguments": {
    "path": "D:\\project\\beam_schedule.xlsx",
    "code": "const geo = staad.Geometry;\nconst prop = staad.Property;\nfor (const [label, x1, y1, z1, x2, y2, z2, section] of __input) {\n  const n1 = geo.AddNode(x1, y1, z1);\n  const n2 = geo.AddNode(x2, y2, z2);\n  geo.AddBeam(n1, n2);\n}\nreturn `Created ${__input.length} beams`;",
    "sheet_name": "Beams"
  }
}
```

**Response:**
```json
{
  "success": true,
  "result": "Created 2847 beams",
  "stdout": "",
  "stderr": "",
  "input_summary": {
    "total_rows": 2847,
    "columns": ["label", "x1", "y1", "z1", "x2", "y2", "z2", "section"],
    "sample_rows": [[1, 0, 0, 0, 0, 120, 0, "W12X26"], [2, 0, 0, 0, 120, 0, 0, "W10X19"], [3, 0, 120, 0, 120, 120, 0, "W12X26"]]
  },
  "duration_seconds": 4.2
}
```

The agent sees 3 sample rows (enough to confirm the data shape was correct) and the code's return value. It never holds 2,847 rows in context.

| Control                | Implementation |
|------------------------|----------------|
| Path validation        | Shared function (model guard, resolve, UNC reject, containment, existence) |
| Format                 | `.csv` or `.xlsx` (same parsing as `read_and_execute`) |
| File size cap          | 50 MB on-disk. Prevents pathological xlsx decompression. |
| Row/column caps        | 100,000 rows, 500 columns. Driven by WASM linear memory (128 MiB). |
| `__input` binding      | Deep-frozen array of arrays of JSON primitives. No functions, no prototypes, no proxies. Pre-serialized through JSON round-trip. |
| Code execution         | Same sandbox, same timeout, same allowlist gates as `execute_code` |
| Destructive method detection | Same pre-flight scan as `execute_code` (if code contains destructive methods, elicitation fires) |
| Tool annotation        | `destructiveHint=true` (modifies STAAD model), `idempotentHint=false`, `openWorldHint=false`, `title="Import file data into STAAD"` |
| Sample rows in response | First 5 rows of `__input` returned in `input_summary` for agent verification |

Parameters:
- `path` (required): Absolute path to `.csv` or `.xlsx` file in the model directory.
- `code` (required): JavaScript code to execute. Has access to `staad`, `console`, and `__input`.
- `instance` (optional): Target STAAD instance alias.
- `sheet_name` (optional): For xlsx files. Defaults to active sheet.
- `columns` (optional): Column filter. Only load specified columns into `__input`.
- `start_row` (optional): Skip N rows before loading into `__input`.
- `max_rows` (optional): Limit rows loaded into `__input`. Defaults to 100,000. Hard ceiling 100,000.

### `execute_and_write` (compound: STAAD → file)

The bulk-export tool. Executes code in the sandbox, captures the return value (expected to be an array of arrays), and writes it directly to a file server-side. The full result set never enters agent context.

**Data flow:**
1. Code executes in sandbox (same as `execute_code`)
2. Return value captured in Python server memory
3. Server validates: must be an array of arrays of JSON primitives
4. Path validation (shared function)
5. Server writes to file via csv/openpyxl (atomic write)
6. Agent receives: row count, column headers, and first N sample rows

**Example agent call:**
```json
{
  "tool": "execute_and_write",
  "arguments": {
    "code": "const out = staad.Output;\nconst load = staad.Load;\nconst beams = staad.Geometry.GetBeamList();\nconst cases = load.GetPrimaryLoadCaseNumbers();\nconst rows = [];\nfor (const beam of beams) {\n  for (const lc of cases) {\n    const f = out.GetMemberEndForces(beam, 0, lc, 0);\n    rows.push([beam, lc, f[0], f[1], f[2], f[3], f[4], f[5]]);\n  }\n}\nreturn rows;",
    "path": "D:\\project\\member_forces.xlsx",
    "columns": ["Member", "LC", "Fx", "Fy", "Fz", "Mx", "My", "Mz"]
  }
}
```

**Response:**
```json
{
  "success": true,
  "path": "D:\\project\\member_forces.xlsx",
  "rows_written": 10000,
  "columns": ["Member", "LC", "Fx", "Fy", "Fz", "Mx", "My", "Mz"],
  "sample_rows": [[1, 1, -12.4, 3.2, 0.0, 0.0, 0.0, 45.6], [1, 2, -8.1, 5.7, 0.0, 0.0, 0.0, 32.1], [1, 3, -15.9, 2.1, 0.0, 0.0, 0.0, 51.3]],
  "duration_seconds": 12.8
}
```

The agent sees 3 sample rows (enough to verify correct extraction) and the total count. It never holds 10,000 rows in context.

| Control                | Implementation |
|------------------------|----------------|
| Path validation        | Shared function (model guard, resolve, UNC reject, containment, parent must exist) |
| Format                 | `.csv` or `.xlsx` (determined by file extension) |
| Output file size cap   | 50 MB. Sanity cap; typical 100K-row export is ~14 MB. |
| Row/column caps        | 100,000 rows, 500 columns. Same WASM memory constraint as `read_and_execute`. |
| Return value validation | Must be array of arrays of JSON primitives. Non-conforming return → error with message explaining expected shape. |
| Overwrite protection   | `overwrite` parameter, defaults to `false`. If file exists and `overwrite=false`, returns `FILE_EXISTS` error. Host confirmation via `destructiveHint=true` is the consent gate. |
| Atomic write           | Write to `.~omcp_{random}.tmp` in same directory, then `os.replace()` to target. `try/finally` deletes temp on failure. Stale `.~omcp_*.tmp` files older than 1 hour cleaned up on each invocation. |
| Code execution         | Same sandbox, same timeout as `execute_code`. No destructive method detection needed (extraction code is read-only on STAAD). Actually: destructive detection still runs, because the code COULD modify STAAD before returning results. Same gate as `execute_code`. |
| Tool annotation        | `destructiveHint=true` (writes to filesystem), `idempotentHint=true`, `openWorldHint=false`, `title="Export STAAD data to file"` |
| Sample rows in response | First 5 rows of the written data returned for agent verification |
| Columns parameter      | Required. Agent must declare column headers. Serves as documentation and xlsx header row. |

Parameters:
- `code` (required): JavaScript code to execute. Must `return` an array of arrays.
- `path` (required): Absolute path for the output file. Extension determines format.
- `columns` (required): Array of column header strings.
- `instance` (optional): Target STAAD instance alias.
- `overwrite` (optional): Boolean. Defaults to `false`.

### `__input` injection: security analysis

`__input` is a pre-bound variable injected into the sandbox before code execution. It is NOT a host function. It adds data, not capability.

**What `__input` is:**
- A deeply frozen (`Object.freeze` recursively) array of arrays
- Contains only JSON primitives: string, number, boolean, null
- Read-only (frozen, assignment to `__input` or mutation of contents throws TypeError)
- Guaranteed primitive-only by typed cell conversion during file parsing (openpyxl returns str/int/float/bool/None natively; datetime cells converted to ISO 8601 strings; CSV values coerced to int/float where parseable)

**What `__input` is NOT:**
- Not a function (cannot be called)
- Not a Proxy (no trap handlers, no capability to intercept operations)
- Not connected to the host (no reference to Python objects, no COM handle)
- Not accessible from the prototype chain of any other sandbox global

**Comparison to existing pre-injected globals:**

| Global | Type | Reaches outside sandbox? | Risk |
|--------|------|--------------------------|------|
| `staad` | COM Proxy (callable) | YES, dispatches to Windows COM | High (gated by allowlists) |
| `console` | Function (callable) | YES, writes to captured buffers | Low (exfil to agent context) |
| `__input` | Frozen array (inert data) | NO | **None** |

`__input` is equivalent to the agent writing `const data = [[1,2,3],[4,5,6]];` as a literal at the top of their code. The sandbox already permits arbitrary data literals. We are changing WHERE the literal is assembled (server-side vs. inline in the code string), not WHAT the sandbox can do.

**Implementation requirements:**
1. Server MUST convert cell values to JSON primitives during row iteration. openpyxl cells are already str/int/float/bool/None; only datetime needs conversion (`.isoformat()`). CSV values are all strings; server attempts `int(val)` then `float(val)` then keeps `str`. No separate JSON round-trip step. The parsing libraries produce clean types directly.
2. Server MUST `Object.freeze` the top-level array AND each inner array (prevents sandbox code from using `__input` as mutable shared state across hypothetical re-executions)
3. `__input` MUST be `undefined` when `read_and_execute` is not being used (no stale data from previous calls)
4. Size cap on `__input` enforced server-side before injection (see "Size limits" section)

**Sandbox isolation unchanged:** The WASM linear memory boundary is the security boundary. `__input` exists inside that boundary as initialized data. It does not create a channel across the boundary. It does not grant the sandbox any new ability to affect the host.

### Size limits

Limits are driven by the WASM linear memory allocation: 128 MiB (2048 pages x 64 KiB, defined in `src/openstaad_mcp/sandbox/constants.py` as `WASM_MAX_MEMORY_PAGES`). QuickJS heap lives inside this allocation. At ~200-300 bytes per row (JSValue overhead + array pointers + primitive storage), 100K rows = 20-30 MB. Worst case for `execute_and_write`: `__input` (30 MB) + return value (30 MB) + engine (10 MB) = ~70 MB, well within the 128 MiB cap.

| Parameter | Limit | Constraint driver |
|-----------|-------|-------------------|
| `read_and_execute` file size cap | 50 MB on-disk | Prevents pathological xlsx decompression; `defusedxml` handles XML bombs independently |
| `read_and_execute` max rows (`__input`) | 100,000 | WASM linear memory (128 MiB). ~30 MB at worst case. Ample headroom for engine + return value. |
| `read_and_execute` max columns | 500 | Sanity check; structural data rarely exceeds 20 columns |
| `execute_and_write` max return rows | 100,000 | Same WASM memory constraint (return value lives in WASM until serialized out) |
| `execute_and_write` max columns | 500 | Consistent with read side |
| `execute_and_write` output file size | 50 MB | Disk space sanity; 100K rows x 8 cols x 140 B = ~14 MB typical |
| Code size (both tools) | 256 KiB | Existing `MAX_CODE_BYTES` constant. Unchanged. |
| Execution timeout (both tools) | 30 seconds | Existing `EXECUTION_TIMEOUT_SECONDS` constant. Unchanged. |

These limits are defined as constants alongside the existing sandbox limits in `constants.py`. They can be tuned empirically if real-world usage shows they're too conservative or too generous.

**Chunking for extreme cases.** If a file exceeds 100K rows (rare in structural engineering, possible with survey data), `read_and_execute` supports `start_row` and `max_rows` parameters. The agent calls it N times with offset pagination. Each call processes a chunk independently.

### How the consent model works across hosts

**MCP client feature support** (source: [modelcontextprotocol.io/clients](https://modelcontextprotocol.io/clients)):

- **Claude Desktop**: supports Tools, Resources, Prompts, Roots, DCR, Apps. Does NOT support Elicitation.
- **VS Code GitHub Copilot**: supports Tools, Resources, Prompts, Discovery, Instructions, Sampling, Roots, Elicitation, CIMD, DCR, Tasks, Apps. DOES support Elicitation.

Our primary target is Claude Desktop (top-management priority, Anthropic Extension Store submission). Claude Desktop does not support elicitation but does respect tool annotations. VS Code supports both.

**Claude Desktop (primary target):**

Claude Desktop respects `destructiveHint` and `readOnlyHint` annotations from the MCP spec. When a tool is marked `destructiveHint=true`, Claude shows its own confirmation dialog before invoking it. This is our consent mechanism for file I/O:

- `read_and_execute` is `destructiveHint=true`. Claude shows confirmation before invocation. The user sees the intent (file path + code description) and approves or declines. Bulk file content never enters agent context, so prompt injection from file content is neutralized at the architecture level.
- `execute_and_write` is `destructiveHint=true`. Same confirmation. The user sees the target file path and approves or declines.

Both tools require user confirmation. There are no auto-approved file operations.

**§10(3) consent justification:** Both tools are gated by `destructiveHint=true`. The host confirmation dialog satisfies §10(3) per-call consent. Additionally, the user establishes directory-level consent at server connection time (they add openstaad-mcp to their MCP client, selecting the model directory implicitly). Path validation (see "Path validation strategy") enforces the boundary regardless of agent behaviour.

Claude Desktop also offers an "Allow always" option for destructive tools (source: [support.claude.com/en/articles/11175166](https://support.claude.com/en/articles/11175166), "Taking actions with tools" section). Power users click "Allow always" on `read_and_execute` and `execute_and_write` once and never see a dialog again. Conservative users keep per-call approval as a safety net.

**VS Code GitHub Copilot (also supported):**

VS Code has its own approval system (source: [code.visualstudio.com/docs/copilot/agents/agent-tools](https://code.visualstudio.com/docs/copilot/agents/agent-tools)) with three permission levels: Default Approvals, Bypass Approvals, and Autopilot. Under Default Approvals, tools show a confirmation dialog before running. Users can configure per-tool auto-approval or trust entire MCP servers.

VS Code also supports MCP elicitation. This means the existing consent gate in `execute_code` (which triggers `Context.elicit()` for destructive COM methods) works as-is in VS Code. For the file I/O tools, both the tool annotation path AND elicitation would work. We use annotations for consistency across hosts.

**Note:** VS Code's docs do not explicitly document that `destructiveHint` annotations determine default tool approval behavior. VS Code's approval system is user-configurable on a per-tool basis regardless of annotations. However, the annotations are part of the MCP spec and VS Code, as a conformant MCP client, is expected to honour them for default behaviour. Either way, VS Code's own approval system provides an equivalent or stronger consent gate independently of annotations.

**Summary: tool annotations are the universal consent mechanism.** They work on Claude Desktop (our primary target), and VS Code provides equivalent or stronger protections through its own approval system. No host-specific code paths needed.

### Scale considerations

Typical structural engineering tabular data for STAAD workflows:

| Data type | Typical rows | Columns | ~Bytes/row (JSON) | ~Total JSON size |
|-----------|-------------|---------|-------------------|-----------------|
| Beam schedule (small, 2-3 stories) | 20-80 | 5-8 | ~120 B | 2-10 KB |
| Beam schedule (medium, 5-10 stories) | 100-500 | 5-8 | ~120 B | 12-60 KB |
| Load table (floor loads per zone) | 10-50 | 4-6 | ~80 B | 1-4 KB |
| Node coordinate import | 50-2,000 | 4 | ~60 B | 3-120 KB |
| Material properties | 5-20 | 6-8 | ~100 B | 0.5-2 KB |
| Member forces (small model) | 2,000 | 8 | ~140 B | 280 KB |
| Member forces (medium model, 500 members x 20 LC) | 10,000 | 8 | ~140 B | 1.4 MB |
| Displacement envelope (1,000 nodes x 50 combos) | 50,000 | 8 | ~100 B | 5 MB |

**The context window problem.** The first 5 rows in this table fit comfortably in agent context (~60 KB worst case, ~15K tokens). The last 3 rows do not. A 10,000-row extraction at 1.4 MB is ~350K tokens. If the agent holds that data AND passes it to a write tool, it transits context twice (~700K tokens). No current LLM handles this.

**The compound tools eliminate this problem.** With `execute_and_write`, the 10,000-row extraction stays in Python server memory and goes directly to the file. The agent receives ~500 bytes (row count + 3 sample rows). With `read_and_execute`, the 2,000-row node import goes from file to WASM heap directly. The agent sends only the code (~1 KB).

**Chunking as fallback.** If the dataset exceeds the 100K row limit, `read_and_execute` supports `start_row` and `max_rows` parameters. The agent calls it N times with offset pagination. Each call processes a chunk independently. This only applies to extreme datasets (100K+ rows, which is rare in structural engineering outside survey data imports).

### Prompt injection risk

Same class as OMCP-009. Cell content (CSV or xlsx) is untrusted data from external files. A malicious file could embed PI payloads in cell values ("IGNORE PREVIOUS INSTRUCTIONS...").

However, the compound-only architecture largely neutralizes this risk. `read_and_execute` sends file content to the WASM sandbox as `__input`, NOT to the agent. PI payloads in cell values are treated as string data by the JavaScript code. They never reach the LLM. The only way file content reaches the agent is:
1. The `input_summary.sample_rows` (first 5 rows) in the response. Limited surface area.
2. If user code explicitly returns file content via `return __input.slice(...)`. This is user-initiated, not automatic.

For `execute_and_write`, data flows from STAAD (via COM) to file. No external untrusted input enters the pipeline at all.

The accepted-risk reasoning for the small exposure in sample rows:
- The MCP server is a data conduit. It faithfully relays what the file contains.
- Output sanitization is the wrong layer (blocklist arms race, breaks legitimate data).
- The blast radius is bounded: 5 sample rows, not the full dataset.
- The agent's system prompt and tool-use policy are the correct mitigation point.

Host applications should include guidance in the system prompt that tool output from file reads may contain untrusted data.

### Dependencies

- Standard library `csv` module for CSV read/write. No third-party dependency for CSV support.
- `openpyxl==3.1.5` for xlsx read/write. MIT licence, 262M monthly downloads, zero CVEs in NVD, zero vulnerabilities on current version per Snyk.
- `defusedxml==0.7.1` for XML bomb protection (openpyxl auto-detects and uses it when installed).
- No new native DLLs. Both `openpyxl` and `defusedxml` are pure Python.

**Design choice: exact version pinning.** Both `openpyxl` and `defusedxml` are pinned to exact versions (`==`). This is a deliberate security decision. We test against a known version and ship that version. Untested upgrades do not enter the dependency tree silently. Version bumps go through a PR with a test run, same as code changes.

### What this does NOT do

- Does not give the sandbox filesystem access.
- Does not give the sandbox new callable host functions. `__input` is inert data, not a function.
- Does not put bulk data into agent context. The entire point is keeping large datasets server-side.
- Does not initiate network connections. UNC paths are rejected. If the user has mapped a network share to a drive letter, the OS handles that transparently; the tool does not distinguish mapped drives from local drives.
- Does not provide a "simple read" that puts raw file content into agent context. The agent gets sample rows only.
- Does not require elicitation (tool annotations handle consent).
- Does not break Anthropic §1B.
- Does not support legacy Excel formats (`.xls`) or macro-enabled workbooks (`.xlsm`).
- Does not execute VBA macros or process embedded objects/images/charts.

### Error response schema

Both tools follow the same response shape as `execute_code`, adapted for file operations:

**Success (read_and_execute):**
```json
{"success": true, "result": "Created 2847 beams", "stdout": "", "stderr": "", "input_summary": {"total_rows": 2847, "columns": ["label", "x1", "y1", "z1", "x2", "y2", "z2", "section"], "sample_rows": [["B1", 0, 0, 0, 120, 0, 0, "W12X26"]]}, "duration_seconds": 4.2}
```

**Success (execute_and_write):**
```json
{"success": true, "path": "D:\\project\\results.csv", "rows_written": 10000, "columns": ["Member", "LC", "Fx", "Fy", "Fz", "Mx", "My", "Mz"], "sample_rows": [[1, 1, -12.4, 3.2, 0.0, 0.0, 0.0, 45.6]], "duration_seconds": 12.8}
```

**Error:**
```json
{"success": false, "error": "FILE_TOO_LARGE", "message": "File is 62 MB, limit is 50 MB", "limit_mb": 50, "actual_mb": 62}
```

Error codes: `NO_MODEL_OPEN`, `UNC_REJECTED`, `PATH_OUTSIDE_MODEL_DIR`, `FILE_NOT_FOUND`, `FILE_TOO_LARGE`, `FILE_EXISTS`, `UNSUPPORTED_FORMAT`, `PARENT_DIR_MISSING`, `PERMISSION_DENIED`, `ENCODING_ERROR`, `CORRUPTED_WORKBOOK`, `SHEET_NOT_FOUND`, `TOO_MANY_ROWS`, `TOO_MANY_COLUMNS`, `INVALID_RETURN_SHAPE`.

The `error` field is a stable machine-readable code. The `message` field is a human-readable explanation the agent can relay to the user. Additional fields (like `limit_mb`, `actual_mb`) are error-specific context.

### Design decisions

**Atomic writes via temp file.** `execute_and_write` writes to a temporary file in the same directory (pattern: `.~omcp_{random}.tmp`), then calls `os.replace()` to atomically move it to the target path. The temp file is created and cleaned up inside a `try/finally`: if serialization fails or the tool raises, the finally block deletes the temp file. The only scenario that leaves an orphan is a hard process kill (SIGKILL, power loss, machine crash). To handle that edge case, the tool deletes any `.~omcp_*.tmp` files in the model directory older than 1 hour at the start of each invocation. Self-healing, no user action required. MCP tool execution is sequential (one tool call at a time per session), so there is no risk of deleting an in-progress temp file from a concurrent write.

**CSV formula injection: accepted risk, not mitigated.** `execute_and_write` does not prefix cell values that start with `=`, `+`, `-`, `@`, or `\t`. Reasoning: the data written by this tool originates from code execution inside the sandbox, operating on STAAD COM data (member numbers, section names like "W12X26", force values). None of these start with formula-triggering characters. Adding `'` prefixes would corrupt legitimate numeric data (negative numbers start with `-`). The risk is theoretical, the mitigation would break real workflows.

**File size cap is on-disk bytes.** The 50 MB cap measures `os.path.getsize()` (compressed size for xlsx, raw size for CSV). xlsx is a zip archive, so a 50 MB file could decompress to more in memory. openpyxl's read-only mode streams rows one at a time, so memory usage is bounded by row size, not total file size. The 50 MB cap is generous for structural engineering data (a 5,000-row beam schedule is ~600 KB on disk) and conservative enough to block billion-laughs XML payloads (and `defusedxml` blocks them regardless).

**Overwrite UX: single confirmation.** When the agent calls `execute_and_write` with `overwrite=true`, the host's `destructiveHint` confirmation dialog is the only consent gate. There is no additional "file exists, are you sure?" prompt from the tool. If the agent calls with `overwrite=false` (default) and the file exists, the tool returns a `FILE_EXISTS` error with the path. The agent can then ask the user or retry with `overwrite=true` (which triggers a fresh confirmation dialog). One decision, one dialog.

**`idempotentHint=true` on `execute_and_write`.** Same input code and path produces the same file. This lets MCP hosts safely retry after network/timeout failures without duplicating side effects. Combined with atomic writes, a retry either succeeds identically or fails cleanly.

**openpyxl version maintenance.** Exact pin means we own the upgrade schedule. A quarterly check of openpyxl releases + Snyk/NVD is sufficient. If a security advisory lands, we bump the pin in a PR with a test run. This is not a high-velocity dependency (6-8 releases per year, mostly bug fixes).

**File locking (write path).** On Windows, Excel holds an exclusive lock on open files. If the write target is open in Excel, `os.replace()` will fail with `PermissionError`. The tool returns `PERMISSION_DENIED` with message: "Cannot write to this file because it is open in another program. Close the file and try again." Reads are not affected: Windows allows shared read access, so `read_and_execute` works fine even if the source file is open in Excel.

## Success criteria

Happy-path scenarios for local manual testing before shipping:

**read_and_execute:**
1. **Bulk import (CSV).** Agent imports a 2,000-row node coordinate CSV. Tool reads file, injects as `__input`, code creates 2,000 nodes. Response shows `input_summary.total_rows: 2000` and code result. Agent context cost: ~2 KB (not 120 KB).
2. **Bulk import (xlsx).** Agent imports a 500-row beam schedule xlsx. Same flow. Numeric cells come back as numbers in `__input`, text as strings.
3. **Peek at data.** Agent wants to see file contents. Uses `read_and_execute` with code `return __input.slice(0, 20)`. Response includes first 20 rows as the execution result plus `input_summary.sample_rows`.
4. **Pagination.** Agent imports a 20,000-row file using `start_row=0, max_rows=5000` four times. Each chunk processes correctly. All 20,000 nodes created.
5. **`__input` is frozen.** Code attempts `__input.push([99])` or `__input[0][0] = "hacked"`. Gets TypeError (Object.freeze). Execution continues, `__input` unchanged.
6. **Sheet selection.** Agent reads an xlsx with `sheet_name="Loads"`. Only that sheet's data appears in `__input`.

**execute_and_write:**
7. **Bulk export (CSV).** Agent extracts 500 members x 20 load cases = 10,000 force rows to CSV. Response shows `rows_written: 10000` and 5 sample rows. File opens correctly in Excel.
8. **Bulk export (xlsx).** Same extraction to xlsx. Column headers present, data matches.
9. **Compose and write.** Agent writes a 50-row summary table using inline data literals in code (`return [[...], ...]`). File correct.
10. **Invalid return shape.** Code returns a string instead of array of arrays. Gets `INVALID_RETURN_SHAPE` error with explanation.
11. **Overwrite flow.** Agent calls with `overwrite=false` on existing file. Gets `FILE_EXISTS`. Retries with `overwrite=true`. File is replaced. Single host confirmation dialog.

**Shared error paths:**
12. **Path escape rejected.** Agent tries `../../etc/passwd` or `C:\Windows\system32\something`. Gets `PATH_OUTSIDE_MODEL_DIR`.
13. **UNC rejected.** Agent tries `\\server\share\file.csv`. Gets `UNC_REJECTED` with helpful message about mapping a drive letter.
14. **No model open.** Agent calls tool with no model loaded. Gets `NO_MODEL_OPEN` with guidance to open a file.
15. **Large file rejected.** Agent reads a file exceeding 50 MB. Gets `FILE_TOO_LARGE` with limit and actual size.
16. **File locked.** Agent writes to a file open in Excel. Gets `PERMISSION_DENIED` with "close the file" guidance.

## Testing strategy

File I/O gets its own test suite (`tests/test_file_io.py`) covering:
- Path validation edge cases: symlinks, junctions, `..` sequences, mixed separators, relative paths, UNC variants
- `read_and_execute`: CSV and xlsx parsing correctness, `__input` injection, `__input` freeze enforcement, pagination (start_row/max_rows), encoding fallback (UTF-8 then cp1252), formula cached values, empty files, column filtering, code execution with injected data, sample_rows in response, error paths (bad code + valid file, valid code + bad file)
- `execute_and_write`: return value validation (must be array of arrays), CSV and xlsx output correctness, atomic write (no partial files on failure), overwrite semantics, temp cleanup, sample_rows in response, error paths (code throws, code returns wrong shape, code returns too many rows)
- Error paths: every error code exercised at least once
- Adversarial: path traversal attempts, oversized files, malformed xlsx, xlsm rejection, prompt injection in cell values (verify it stays in `__input` and never reaches agent context beyond sample_rows)

Integration tests with real STAAD model (in `tests/test_integration.py`) once implementation is stable.

## Open questions

1. ~~**Path restriction policy.**~~ **Resolved.** Restricted to model directory (derived from `GetSTAADFile().parent`). Same containment pattern as `read_skills` and `read_analysis_output`. Engineers keep input files in the project folder alongside the `.std` model. If they need a file from elsewhere, they copy it in. This satisfies §10(3) to the letter.

2. ~~**CSV encoding detection.**~~ **Resolved.** Handled by the csv module internally. We attempt UTF-8 then `cp1252` fallback. Not applicable to xlsx (XML is always UTF-8).

3. ~~**Formula evaluation.**~~ **Resolved.** openpyxl's `data_only=True` returns cached values. Not applicable to CSV. Library handles this.


## Constraint satisfaction analysis

| # | Constraint | Result | How satisfied |
|---|-----------|--------|---------------|
| 1 | §1B | **PASS** | Both tools are MCP-layer endpoints in the Python server process. The WASM sandbox gains zero new capabilities, zero new callable host functions, zero filesystem access from inside the isolate. `__input` is pre-initialized inert data (equivalent to a code literal), not a sandbox escape. |
| 2 | §1D | **PASS** | Tools do not collect or log conversation data. They read only the file content the user explicitly requests via the `path` parameter. No telemetry, no extraneous data retention. Compound tools are MORE private than simple reads would be (bulk data never enters agent context where it could be logged by the host). |
| 3 | §2B | **PASS** | All annotations match actual behaviour. Both tools: `destructiveHint=true` (one modifies STAAD, the other writes to filesystem). Tool descriptions state formats, size limits, containment boundary. No hidden functionality. |
| 4 | §2D | **PASS** | Each tool composes file I/O and code execution into a single tool call, but this is explicit in the tool description. The agent calls ONE tool. The server does not auto-invoke other MCP tools or chain calls behind the scenes. The composition is internal to the server process, same as `execute_code` internally calling host functions. |
| 5 | §5A | **PASS** | Structured error responses with machine-readable `error` code and human-readable `message`. 15 distinct error codes including `INVALID_RETURN_SHAPE` for compound write (return value was not array of arrays). |
| 6 | §5B | **PASS** | These tools ARE the §5B mechanism. They reduce token usage by orders of magnitude for bulk operations (10,000-row extraction: ~500 bytes response vs. ~1.4 MB if data transited through agent context). Agent receives only summaries and sample rows. |
| 7 | §5E | **PASS** | Both tools annotated. `read_and_execute`: `destructiveHint=true`, `idempotentHint=false`. `execute_and_write`: `destructiveHint=true`, `idempotentHint=true`. Both: `openWorldHint=false`, `title` set. |
| 8 | §10(1) | **PASS** | All paths validated through shared function. UNC paths rejected unconditionally. Neither `csv` nor `openpyxl` initiate network connections. `__input` data originates from a validated local file, not from the network. |
| 9 | §10(3) | **PASS** | Both tools restricted to `GetSTAADFile().parent`. Shared path validation enforces containment. User consent established via `destructiveHint=true` confirmation per call, plus directory-level consent at server connection time. |
| 10 | §10(4) | **PASS** | Progressive exposure preserved. Both tools are `destructiveHint=true` (host confirmation required). No file operation executes without explicit user approval. |
| 11 | §10 shadow API | **PASS** | Both tools are first-class MCP tools with annotations, visible to the host, inspectable by the user. `__input` is NOT a host function (it's a frozen variable). The sandbox does not gain any new callable. It gains read-only data that was already expressible as a code literal. |
| 12 | Control 4 | **PASS** | `execute_and_write` triggers host confirmation (write to filesystem). `read_and_execute` triggers host confirmation (modifies STAAD model via code execution). Both tools satisfy Control 4 unconditionally. |
