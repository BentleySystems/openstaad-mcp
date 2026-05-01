# File I/O for User Workflows

**Status:** Proposal  
**Author:** Dave Hanson  
**Date:** 2026-05-01

## The problem

Users want workflows like "read this CSV and create a beam for each row" or "run this analysis and put results in a CSV with these columns." The WASM sandbox physically cannot access the filesystem, and that is by design. But file I/O is a must-have for the workflows that structural engineers actually do with STAAD. Ignoring this is not an option.

The current architecture gives the agent exactly one way to interact with STAAD: `execute_code`. That tool runs JavaScript inside a WebAssembly isolate with zero filesystem access. We are not going to change that. The sandbox stays clean. So how do we get data in and out of files without opening a hole in the isolation model?

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

## Proposed solution: MCP-layer file tools (outside the sandbox)

Two new MCP tools at the server layer. Completely outside the WASM sandbox. The agent orchestrates data flow between them and `execute_code`.

```
Agent context
  |
  +-- read_tabular_data(path, max_rows?)              -> JSON rows
  |       (agent holds data in context or embeds in code)
  |
  +-- execute_code(code)                              -> results via console.log / return
  |       (agent captures structured output)
  |
  +-- write_tabular_data(path, rows, columns)         -> {success, path, rows_written}
```

The agent is the data broker. Same pattern as a human copying data between a CSV and a script. No sandbox modification, no new host functions, no filesystem access from inside WASM.

### Design decision: CSV + xlsx via openpyxl

We support `.csv` and `.xlsx`. No `.xls`, no `.xlsm`, no `.tsv`.

Both tools are a common data broker. Regardless of file format, the interface is:
- **Read:** file on disk → library parses → JSON rows to agent context
- **Write:** JSON rows from agent context → library serializes → file on disk

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

1. Agent calls `read_tabular_data(path="schedule.xlsx")`
2. Path validation fires (see "Path validation strategy"): model guard, resolve, UNC reject, containment check, existence check.
3. File size check fires (10 MB on-disk cap)
4. Only THEN does openpyxl open the file
5. openpyxl reads cell values, server converts to JSON rows
6. JSON rows returned to agent context

openpyxl never sees an unvalidated path. The file has already passed all security gates before the library touches it. The 10 MB file size cap also limits the blast radius from any hypothetical XML parsing issue (billion laughs payloads need large files to be effective, and `defusedxml` blocks them regardless).

**Write path:** `write_tabular_data` constructs the workbook from the agent-supplied `rows` JSON array. The data originates from the agent's context (already validated as JSON arrays of primitives). openpyxl never parses untrusted xlsx content on the write path.

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

The sandbox never touches files. Each tool is independently auditable with a clear risk profile. `read_tabular_data` is read-only (`readOnlyHint=true`, auto-approved, no confirmation dialog). `write_tabular_data` is destructive (`destructiveHint=true`, host confirmation dialog fires before invocation). No elicitation required at any point.

The data flow is explicit and visible to the agent's host. The host can inspect what the agent intends to write before it happens. This is exactly the trust model Claude Desktop already uses for destructive tools.

### `read_tabular_data`

| Control                | Implementation                                                                                                                                    |
|------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|
| Path validation        | See "Path validation strategy" above. Shared validation function handles model guard, resolve, UNC rejection, and containment.                    |
| Format                 | `.csv` (comma delimiter, first row = headers) or `.xlsx` (openpyxl read-only mode, `data_only=True`, active sheet by default)                     |
| Size cap               | 10 MB on-disk file size. `max_rows` parameter (default 10,000). Hard ceiling 50,000 rows, 500 columns.                                             |
| Output shape           | `{"success": true, "columns": [...], "rows": [[...], ...], "truncated": bool, "total_rows": int}`                                              |
| Tool annotation        | `readOnlyHint=true`, `openWorldHint=false`, `title="Read tabular file"`. Auto-approved: tool is read-only on the filesystem                        |

Parameters:
- `path` (required): Absolute path to the `.csv` or `.xlsx` file. Validated and resolved before any read.
- `max_rows` (optional): Maximum rows to return. Defaults to 10,000. Hard ceiling at 50,000.
- `columns` (optional): Column name or index filter. Only return specified columns to reduce token usage.
- `start_row` (optional): Pagination support. Skip this many rows before returning data.
- `sheet_name` (optional): For `.xlsx` files only. Name of the worksheet to read. Defaults to the active sheet. Ignored for `.csv`.

### `write_tabular_data`

| Control                | Implementation                                                                            |
|------------------------|-------------------------------------------------------------------------------------------|
| Path validation        | See "Path validation strategy" above. Same shared validation function as `read_tabular_data`. |
| Format                 | `.csv` (comma delimiter, all text quoted) or `.xlsx` (openpyxl write-only mode, single sheet)                                                     |
| Overwrite protection   | If file exists and `overwrite=false` (default), return error with `"error": "FILE_EXISTS"` and the existing file path. Agent can retry with `overwrite=true`. The host's `destructiveHint` confirmation dialog is the consent gate, not a separate existence check. |
| Size cap               | 100,000 rows max, 500 columns max, 50 MB output file size                                 |
| Data-only input        | `rows` parameter is a JSON array of arrays. No formulas, no macros, no embedded objects   |
| Tool annotation        | `destructiveHint=true`, `idempotentHint=true`, `openWorldHint=false`, `title="Write tabular file"` |
| No directory creation  | Parent directory must already exist. We do not mkdir.                                      |
| Atomic write           | Write to `.~omcp_{random}.tmp` in same directory, then `os.replace()` to target. `try/finally` deletes temp on failure. Stale `.~omcp_*.tmp` files older than 1 hour are cleaned up on each invocation. |

Parameters:
- `path` (required): Absolute path for the output `.csv` or `.xlsx` file. Extension determines format.
- `columns` (required): Array of column header strings.
- `rows` (required): Array of arrays (each inner array is one row, positionally matched to columns).
- `overwrite` (optional): Boolean. Defaults to `false`.

### How the consent model works across hosts

**MCP client feature support** (source: [modelcontextprotocol.io/clients](https://modelcontextprotocol.io/clients)):

- **Claude Desktop**: supports Tools, Resources, Prompts, Roots, DCR, Apps. Does NOT support Elicitation.
- **VS Code GitHub Copilot**: supports Tools, Resources, Prompts, Discovery, Instructions, Sampling, Roots, Elicitation, CIMD, DCR, Tasks, Apps. DOES support Elicitation.

Our primary target is Claude Desktop (top-management priority, Anthropic Extension Store submission). Claude Desktop does not support elicitation but does respect tool annotations. VS Code supports both.

**Claude Desktop (primary target):**

Claude Desktop respects `destructiveHint` and `readOnlyHint` annotations from the MCP spec. When a tool is marked `destructiveHint=true`, Claude shows its own confirmation dialog before invoking it. When `readOnlyHint=true`, Claude invokes without prompting. This is our consent mechanism for file I/O:

- `read_tabular_data` is `readOnlyHint=true`. Claude invokes it without prompting. The tool is read-only on the filesystem. Prompt injection risk from file content is an accepted risk (same class as COM output per OMCP-009), not something we gate on per-call user consent.
- `write_tabular_data` is `destructiveHint=true`. Claude shows its own confirmation before invocation. The user sees the intent ("writing 847 rows to D:\project\results.csv") and approves or declines.

The user confirms writes only. Reads flow without interruption. This matches the mental model: reading a file is not a decision point, writing one is.

**§10(3) consent justification for reads:** For reads, user consent is established at server connection time. The user explicitly adds openstaad-mcp to their MCP client configuration, opting into its declared capabilities. Directory selection occurs when the user opens a STAAD model file. Path validation (see "Path validation strategy") enforces the boundary regardless of agent behaviour.

Claude Desktop also offers an "Allow always" option for destructive tools (source: [support.claude.com/en/articles/11175166](https://support.claude.com/en/articles/11175166), "Taking actions with tools" section). Power users click "Allow always" on `write_tabular_data` once and never see a dialog again. Conservative users keep per-call write approval as a safety net.

**VS Code GitHub Copilot (also supported):**

VS Code has its own approval system (source: [code.visualstudio.com/docs/copilot/agents/agent-tools](https://code.visualstudio.com/docs/copilot/agents/agent-tools)) with three permission levels: Default Approvals, Bypass Approvals, and Autopilot. Under Default Approvals, tools show a confirmation dialog before running. Users can configure per-tool auto-approval or trust entire MCP servers.

VS Code also supports MCP elicitation. This means the existing consent gate in `execute_code` (which triggers `Context.elicit()` for destructive COM methods) works as-is in VS Code. For the file I/O tools, both the tool annotation path AND elicitation would work. We use annotations for consistency across hosts.

**Note:** VS Code's docs do not explicitly document that `destructiveHint` annotations determine default tool approval behavior. VS Code's approval system is user-configurable on a per-tool basis regardless of annotations. However, the annotations are part of the MCP spec and VS Code, as a conformant MCP client, is expected to honour them for default behaviour. Either way, VS Code's own approval system provides an equivalent or stronger consent gate independently of annotations.

**Summary: tool annotations are the universal consent mechanism.** They work on Claude Desktop (our primary target), and VS Code provides equivalent or stronger protections through its own approval system. No host-specific code paths needed.

### Scale considerations

Typical structural engineering tabular inputs for STAAD workflows (engineering estimates based on common model sizes):

| Input type | Typical rows | Columns | ~Bytes/row (JSON) | ~Total JSON size |
|------------|-------------|---------|-------------------|-----------------|
| Beam schedule (small building, 2-3 stories) | 20-80 | 5-8 (label, section, material, length, orientation) | ~120 B | 2-10 KB |
| Beam schedule (medium building, 5-10 stories) | 100-500 | 5-8 | ~120 B | 12-60 KB |
| Load table (floor loads per zone) | 10-50 | 4-6 (zone, dead, live, wind, seismic) | ~80 B | 1-4 KB |
| Node coordinate import | 50-2,000 | 4 (label, X, Y, Z) | ~60 B | 3-120 KB |
| Material properties | 5-20 | 6-8 (name, E, density, Poisson, Fy, Fu) | ~100 B | 0.5-2 KB |
| Analysis results export | 50-5,000 | 6-10 (member, LC, Fx, Fy, Fz, Mx, My, Mz) | ~140 B | 7-700 KB |

The 256 KiB `execute_code` input limit is the binding constraint when the agent inlines data into JavaScript code. For the majority of structural engineering workflows (beam schedules, load tables, material lists), the data fits comfortably: a 500-row beam schedule at ~120 bytes/row produces ~60 KB of JSON, well within the 256 KiB limit.

The edge case is large node-coordinate imports or analysis-result exports (1,000+ rows). At 2,000 rows x 140 bytes/row = ~280 KB, we hit the limit. This is where chunked execution applies: the agent splits data into batches of ~1,000 rows and calls `execute_code` multiple times. Each call creates a subset of the model elements. This works today with no architectural changes.

**Key insight:** The file I/O tools themselves have no 256 KiB limit. `read_tabular_data` can return up to 50,000 rows (the `max_rows` ceiling). The constraint only applies when the agent wants to pass that data INTO the sandbox via `execute_code`. The typical workflow ("read 200 beams, create them in STAAD") fits in a single `execute_code` call. The rare workflow ("import 5,000 nodes from a survey CSV") uses chunking.

The "embed data in code" pattern has limits:

| Rows   | ~JSON size | Fits in 256 KiB code limit? |
|--------|------------|-----------------------------|
| 100    | ~10 KB     | Yes                         |
| 1,000  | ~100 KB    | Yes                         |
| 3,000  | ~250 KB    | Borderline                  |
| 10,000 | ~1 MB      | No                          |

For datasets up to ~2,000 rows, the agent can inline data directly into the `execute_code` call. This covers the majority of structural engineering use cases (a building rarely has more than a few hundred beams).

For larger datasets, two options:

**Option A: Chunked execution.** The agent breaks the work into batches of ~1,000 rows, calling `execute_code` multiple times. Each call creates a subset of beams. This works today with no changes.

**Option B (future): `context_data` parameter.** Add a `context_data` parameter to `execute_code` that pre-loads JSON data into the sandbox as a bound `__input` variable via a new read-only host function (`get_input_data()`). The data is loaded server-side from the `read_tabular_data` result and passed through the same JSON serialization boundary as COM results. No filesystem access granted. This is a Phase 2 enhancement if chunked execution proves insufficient.

### Prompt injection risk

Same class as OMCP-009. Cell content (CSV or xlsx) is untrusted data from external files. A malicious file could embed PI payloads in cell values ("IGNORE PREVIOUS INSTRUCTIONS..."). When `read_tabular_data` returns that data to the agent, the payloads enter the agent's context.

The same accepted-risk reasoning applies:
- The MCP server is a data conduit. It faithfully relays what the file contains.
- Output sanitization is the wrong layer (blocklist arms race, breaks legitimate data).
- The blast radius through our server is bounded by the sandbox controls.
- The agent's system prompt and tool-use policy are the correct mitigation point.

One additional consideration: unlike COM output (which is generated by STAAD's solver from model data), tabular files are directly user-sourced. The agent should treat `read_tabular_data` output with the same caution as any user-provided file content. Host applications should include guidance in the system prompt that tool output from file reads may contain untrusted data.

### Dependencies

- Standard library `csv` module for CSV read/write. No third-party dependency for CSV support.
- `openpyxl==3.1.5` for xlsx read/write. MIT licence, 262M monthly downloads, zero CVEs in NVD, zero vulnerabilities on current version per Snyk.
- `defusedxml==0.7.1` for XML bomb protection (openpyxl auto-detects and uses it when installed).
- No new native DLLs. Both `openpyxl` and `defusedxml` are pure Python.

**Design choice: exact version pinning.** Both `openpyxl` and `defusedxml` are pinned to exact versions (`==`). This is a deliberate security decision. We test against a known version and ship that version. Untested upgrades do not enter the dependency tree silently. Version bumps go through a PR with a test run, same as code changes.

### What this does NOT do

- Does not give the sandbox filesystem access.
- Does not initiate network connections. UNC paths are rejected. If the user has mapped a network share to a drive letter, the OS handles that transparently; the tool does not distinguish mapped drives from local drives.
- Does not require elicitation.
- Does not need a new host function for Phase 1.
- Does not break Anthropic §1B.
- Does not support legacy Excel formats (`.xls`) or macro-enabled workbooks (`.xlsm`).
- Does not execute VBA macros or process embedded objects/images/charts.

### Error response schema

Both tools follow the same response shape as `execute_code`, adapted for file operations:

**Success (read):**
```json
{"success": true, "columns": [...], "rows": [[...], ...], "truncated": false, "total_rows": 147}
```

**Success (write):**
```json
{"success": true, "path": "D:\\project\\results.csv", "rows_written": 847}
```

**Error:**
```json
{"success": false, "error": "FILE_TOO_LARGE", "message": "File is 14.2 MB, limit is 10 MB", "limit_mb": 10, "actual_mb": 14.2}
```

Error codes: `NO_MODEL_OPEN`, `UNC_REJECTED`, `PATH_OUTSIDE_MODEL_DIR`, `FILE_NOT_FOUND`, `FILE_TOO_LARGE`, `FILE_EXISTS`, `UNSUPPORTED_FORMAT`, `PARENT_DIR_MISSING`, `PERMISSION_DENIED`, `ENCODING_ERROR`, `CORRUPTED_WORKBOOK`, `SHEET_NOT_FOUND`, `TOO_MANY_ROWS`, `TOO_MANY_COLUMNS`.

The `error` field is a stable machine-readable code. The `message` field is a human-readable explanation the agent can relay to the user. Additional fields (like `limit_mb`, `actual_mb`) are error-specific context.

### Design decisions

**Atomic writes via temp file.** `write_tabular_data` writes to a temporary file in the same directory (pattern: `.~omcp_{random}.tmp`), then calls `os.replace()` to atomically move it to the target path. The temp file is created and cleaned up inside a `try/finally`: if serialization fails or the tool raises, the finally block deletes the temp file. The only scenario that leaves an orphan is a hard process kill (SIGKILL, power loss, machine crash). To handle that edge case, the tool deletes any `.~omcp_*.tmp` files in the model directory older than 1 hour at the start of each invocation. Self-healing, no user action required. MCP tool execution is sequential (one tool call at a time per session), so there is no risk of deleting an in-progress temp file from a concurrent write.

**CSV formula injection: accepted risk, not mitigated.** `write_tabular_data` does not prefix cell values that start with `=`, `+`, `-`, `@`, or `\t`. Reasoning: the data written by this tool originates from the agent context. In practice, the agent is writing STAAD model data extracted via COM (member numbers, section names like "W12X26", force values). None of these start with formula-triggering characters. Adding `'` prefixes would corrupt legitimate numeric data (negative numbers start with `-`). The risk is theoretical, the mitigation would break real workflows.

**File size cap is on-disk bytes.** The 10 MB read cap measures `os.path.getsize()` (compressed size for xlsx, raw size for CSV). xlsx is a zip archive, so a 10 MB file could decompress to more in memory. openpyxl's read-only mode streams rows one at a time, so memory usage is bounded by row size, not total file size. The 10 MB cap is generous for structural engineering data (a 5,000-row beam schedule is ~600 KB on disk) and conservative enough to block billion-laughs XML payloads.

**Overwrite UX: single confirmation.** When the agent calls `write_tabular_data` with `overwrite=true`, the host's `destructiveHint` confirmation dialog is the only consent gate. There is no additional "file exists, are you sure?" prompt from the tool. If the agent calls with `overwrite=false` (default) and the file exists, the tool returns a `FILE_EXISTS` error with the path. The agent can then ask the user or retry with `overwrite=true` (which triggers a fresh confirmation dialog). One decision, one dialog.

**`idempotentHint=true` on write.** Same input data and path produces the same file. This lets MCP hosts safely retry after network/timeout failures without duplicating side effects. Combined with atomic writes, a retry either succeeds identically or fails cleanly.

**openpyxl version maintenance.** Exact pin means we own the upgrade schedule. A quarterly check of openpyxl releases + Snyk/NVD is sufficient. If a security advisory lands, we bump the pin in a PR with a test run. This is not a high-velocity dependency (6-8 releases per year, mostly bug fixes).

**File locking (write path).** On Windows, Excel holds an exclusive lock on open files. If the write target is open in Excel, `os.replace()` will fail with `PermissionError`. The tool returns `PERMISSION_DENIED` with message: "Cannot write to this file because it is open in another program. Close the file and try again." Reads are not affected: Windows allows shared read access, so `read_tabular_data` works fine even if the file is open in Excel.

## Success criteria

Happy-path scenarios for local manual testing before shipping:

1. **Read CSV.** Agent asks to read a 50-row CSV in the model directory. Tool returns JSON with correct columns, rows, `total_rows: 50`, `truncated: false`.
2. **Read xlsx.** Agent reads a 200-row `.xlsx` beam schedule. Returns same shape. Numeric cells come back as numbers, text as strings.
3. **Read with pagination.** Agent reads with `start_row=50, max_rows=50` on a 200-row file. Returns rows 51-100, `truncated: true`, `total_rows: 200`.
4. **Write CSV.** Agent writes 100 rows to a new `.csv`. File appears on disk, opens correctly in Excel, values match.
5. **Write xlsx.** Agent writes 500 rows to a new `.xlsx`. File opens in Excel, column headers present, data matches.
6. **Overwrite flow.** Agent calls write with `overwrite=false` on existing file. Gets `FILE_EXISTS`. Retries with `overwrite=true`. File is replaced. Single host confirmation dialog.
7. **Path escape rejected.** Agent tries `../../etc/passwd` or `C:\Windows\system32\something`. Gets `PATH_OUTSIDE_MODEL_DIR`.
8. **UNC rejected.** Agent tries `\\server\share\file.csv`. Gets `UNC_REJECTED` with helpful message about mapping a drive letter.
9. **No model open.** Agent calls tool with no model loaded. Gets `NO_MODEL_OPEN` with guidance to open a file.
10. **Large file rejected.** Agent reads a 15 MB file. Gets `FILE_TOO_LARGE` with limit and actual size.
11. **File locked.** Agent writes to a file open in Excel. Gets `PERMISSION_DENIED` with "close the file" guidance.

## Testing strategy

File I/O gets its own test suite (`tests/test_file_io.py`) covering:
- Path validation edge cases: symlinks, junctions, `..` sequences, mixed separators, relative paths, UNC variants
- Read: CSV and xlsx happy paths, encoding fallback (UTF-8 then cp1252), formula cached values, empty files, files at size/row/column limits
- Write: CSV and xlsx output correctness, atomic write (verify no partial files on simulated failure), overwrite semantics, temp cleanup
- Error paths: every error code exercised at least once
- Adversarial: path traversal attempts, oversized files, malformed xlsx, xlsm rejection

Integration tests with real STAAD model (in `tests/test_integration.py`) once implementation is stable.

## Open questions

1. ~~**Path restriction policy.**~~ **Resolved.** Restricted to model directory (derived from `GetSTAADFile().parent`). Same containment pattern as `read_skills` and `read_analysis_output`. Engineers keep input files in the project folder alongside the `.std` model. If they need a file from elsewhere, they copy it in. This satisfies §10(3) to the letter.

2. ~~**CSV encoding detection.**~~ **Resolved.** Handled by the csv module internally. We attempt UTF-8 then `cp1252` fallback. Not applicable to xlsx (XML is always UTF-8).

3. ~~**Formula evaluation.**~~ **Resolved.** openpyxl's `data_only=True` returns cached values. Not applicable to CSV. Library handles this.


## Constraint satisfaction analysis

| # | Constraint | Result | How satisfied |
|---|-----------|--------|---------------|
| 1 | §1B | **PASS** | File tools are MCP-layer endpoints in the Python server process. The WASM sandbox gains zero new capabilities, zero new host functions, zero filesystem access from inside the isolate. |
| 2 | §1D | **PASS** | Tools do not collect or log conversation data. They read only the file content the user explicitly requests via the `path` parameter. No telemetry, no extraneous data retention. |
| 3 | §2B | **PASS** | `read_tabular_data` is annotated `readOnlyHint=true` and is genuinely read-only. `write_tabular_data` is annotated `destructiveHint=true` and genuinely writes to disk. Annotations match actual behaviour. Tool descriptions state formats, size limits, containment boundary. |
| 4 | §2D | **PASS** | Tools are standalone. They do not auto-invoke `execute_code` or chain to other tools. The agent decides workflow orchestration. |
| 5 | §5A | **PASS** | Structured error responses with machine-readable `error` code and human-readable `message`. 14 distinct error codes: `NO_MODEL_OPEN`, `UNC_REJECTED`, `PATH_OUTSIDE_MODEL_DIR`, `FILE_NOT_FOUND`, `FILE_TOO_LARGE`, `FILE_EXISTS`, `UNSUPPORTED_FORMAT`, `PARENT_DIR_MISSING`, `PERMISSION_DENIED`, `ENCODING_ERROR`, `CORRUPTED_WORKBOOK`, `SHEET_NOT_FOUND`, `TOO_MANY_ROWS`, `TOO_MANY_COLUMNS`. |
| 6 | §5B | **PASS** | `max_rows` default 10,000 (ceiling 50,000), `columns` filter, `start_row` pagination, `truncated` flag. Agent requests only what it needs. |
| 7 | §5E | **PASS** | `read_tabular_data`: `readOnlyHint=true`, `openWorldHint=false`, `title="Read tabular file"`. `write_tabular_data`: `destructiveHint=true`, `idempotentHint=true`, `openWorldHint=false`, `title="Write tabular file"`. |
| 8 | §10(1) | **PASS** | `Path.resolve()` normalizes all path variants. Resolved paths starting with `\\` are rejected unconditionally. Neither `csv` nor `openpyxl` initiate network connections. If the model directory is on a mapped network drive (e.g. Z:\), file I/O traverses the network transparently via the OS; this is the user's own environment configuration, not a connection initiated by the server. |
| 9 | §10(3) | **PASS** | Restricted to `GetSTAADFile().parent`. Path validation (see "Path validation strategy") enforces containment. User consent established at server connection time. Directory selection occurs when user opens a model file. |
| 10 | §10(4) | **PASS** | Write requires explicit consent (`destructiveHint=true`). Read is auto-approved (`readOnlyHint=true`) because it does not modify state. Progressive exposure: read is frictionless, write requires approval. |
| 11 | §10 shadow API | **PASS** | Tools are first-class MCP tools with annotations and consent gates, visible to the host, inspectable by the user. Not host functions inside the sandbox. Sandbox retains zero filesystem access. |
| 12 | Control 4 | **PASS** | `write_tabular_data` triggers host confirmation dialog (`destructiveHint=true`). `read_tabular_data` is read-only, does not modify state or cause external side effects. Control 4 does not apply to it. |
