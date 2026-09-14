# OpenSTAAD MCP · PTC-V1

**English** | [简体中文](README.zh-CN.md)

Empower LLMs (OpenAI Codex Desktop, Codex CLI, Claude Code, Cursor, Windsurf, Claude Desktop, etc.) to directly inspect, query, and manipulate local Bentley STAAD.Pro structural models via the Model Context Protocol (MCP).

This project extends the official [Bentley OpenSTAAD MCP](https://github.com/BentleySystems/openstaad-mcp) by introducing a local **Programmatic Tool Calling (PTC)** execution layer. Instead of flooding LLM context windows with thousands of raw nodes, member properties, or force records through repetitive chat turns, the model submits a single Python block. The script executes locally on your Windows workstation right alongside STAAD.Pro's COM interface, performs high-speed filtering, unit conversions, and aggregations, and returns only concise summaries or exports rich Excel/CSV reports.

> **Repository & Branch**: [wenlong888442/openstaad-mcp · PTC-V1](https://github.com/wenlong888442/openstaad-mcp/tree/PTC-V1)  
> **Key Modules**: This branch contains the dedicated PTC engine (`src/openstaad_mcp/ptc/`) and the automated installer (`scripts/install-codex.ps1`). Upstream packages do not include these PTC capabilities.

---

## Table of Contents

- [Why PTC? (Core Advantages)](#why-ptc-core-advantages)
- [System Requirements](#system-requirements)
- [Quick Start: Codex + Local PTC](#quick-start-codex--local-ptc)
  - [1. Clone Branch](#1-clone-branch)
  - [2. Run Automated Installer](#2-run-automated-installer)
  - [3. Configure Codex Client](#3-configure-codex-client)
  - [4. Verify Connection & Model Query](#4-verify-connection--model-query)
- [Client Integration Guide](#client-integration-guide)
  - [Standard STDIO Mode (Recommended)](#standard-stdio-mode-recommended)
  - [Optional HTTP Transport](#optional-http-transport)
- [Available MCP Tools](#available-mcp-tools)
  - [Top-Level MCP Tools](#top-level-mcp-tools)
  - [PTC Query Namespaces (31 Methods)](#ptc-query-namespaces-31-methods)
- [PTC Python Examples](#ptc-python-examples)
  - [Example 1: Model Scale & Base Units Summary](#example-1-model-scale--base-units-summary)
  - [Example 2: Filter Critical Horizontal Members by Steel Design Ratio](#example-2-filter-critical-horizontal-members-by-steel-design-ratio)
  - [Example 3: Multi-Load-Case Force Envelopes](#example-3-multi-load-case-force-envelopes)
- [CSV / XLSX File Workflows](#csv--xlsx-file-workflows)
- [Security, Privacy & Execution Boundaries](#security-privacy--execution-boundaries)
- [Command Line Options](#command-line-options)
- [Frequently Asked Questions (FAQ)](#frequently-asked-questions-faq)
- [Development & Verification](#development--verification)
- [Project Layout & Attribution](#project-layout--attribution)

---

## Why PTC? (Core Advantages)

In traditional LLM tool-calling architectures, querying a structural engineering model requires multiple round trips. Querying 5,000 members and their end forces can generate megabytes of JSON text, easily overflowing the model's context window, blowing up token costs, and introducing hallucination risks during serialization.

**PTC-V1** solves this by providing a local, programmatic execution sandbox:

- **31 Read-Only PTC Queries**: Complete domain coverage across geometry nodes, members, plates, solids, groups, cross-sections, materials, load cases & combinations, supports, FEA analysis results, and steel code check results.
- **Single-Turn Compound Queries**: Call registered `tools.*` functions in a single `execute_ptc` execution. Filter, aggregate, and envelope data locally in memory, returning only key insights to the client.
- **Server-Side File I/O & Reports**: Ingest large datasets via `input_data_path` without context overhead, or export multi-sheet `.xlsx` / `.csv` reports directly to allowed directories.
- **Multi-Instance Routing**: Automatically discovers running STAAD.Pro instances via the Windows Running Object Table (ROT), identifying open `.std` paths and routing commands to designated instance aliases (e.g. `staadPro1`).
- **Dual Execution Modes**:
  - **PTC Mode (`execute_ptc`)**: Strictly read-only, hardened execution sandbox tailored for data querying, filtering, and aggregation.
  - **Native Code Mode (`execute_code`)**: Full OpenSTAAD COM access via `staad.*` for parametric modeling, load modifications, and launching solvers.
- **Self-Hosted & Zero Cloud Overhead**: Standard MCP compliance. No Anthropic cloud execution containers, no OpenAI platform API keys needed on the server side.

---

## System Requirements

| Component | Requirement | Details |
| --- | --- | --- |
| **Operating System** | Windows 11 / Windows 10 (64-bit) | STAAD.Pro OpenSTAAD relies on Windows COM; the server must run natively on Windows. |
| **STAAD.Pro** | 2025 or newer | Must be running with a saved `.std` structural model open during queries. |
| **Python** | **3.11 or newer (64-bit)** | **Must be 64-bit Python** to match STAAD.Pro's 64-bit COM server process. Available on PATH or via explicit path. |
| **MCP Client** | Codex Desktop, Codex CLI, or any MCP client | Standard STDIO or local HTTP transport. |
| **Network** | Internet access for initial setup | Required for downloading Python dependencies and Bentley's official `openstaadpy-26.0.0.62` wheel from GitHub Releases. |

> [!IMPORTANT]
> The automated installer configures the **OpenSTAAD MCP server and its isolated Python environment**. STAAD.Pro, Python 3.11+ (64-bit), and the MCP client must be pre-installed on the machine.

---

## Quick Start: Codex + Local PTC

### 1. Clone Branch

Open Windows PowerShell and clone the `PTC-V1` branch:

```powershell
git clone --branch PTC-V1 --single-branch https://github.com/wenlong888442/openstaad-mcp.git openstaad-mcp-PTC
cd openstaad-mcp-PTC

# Verify key files are present
Test-Path .\scripts\install-codex.ps1
Test-Path .\src\openstaad_mcp\ptc\adapter.py
```

Both tests should print `True`. Alternatively, download the ZIP archive from the GitHub branch page.

### 2. Run Automated Installer

Run the setup script in PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-codex.ps1
```

> **Note**: `-ExecutionPolicy Bypass` only applies to this single PowerShell process. The script will:
> 1. Create or reuse a dedicated virtual environment `.venv-codex` and verify 64-bit Python 3.11+.
> 2. Install dependencies in editable mode (`pip install -e .`) and verify package consistency.
> 3. Validate CLI entry points, the 31 PTC queries, and file access boundaries.
> 4. Generate `.venv-codex\openstaad-codex.toml` containing absolute paths for your machine.

- To specify an explicit 64-bit Python interpreter or install development dependencies:
  ```powershell
  .\scripts\install-codex.ps1 -Python 'C:\Python311\python.exe' -Dev
  ```
- To whitelist additional directories for CSV/XLSX file read/write operations:
  ```powershell
  .\scripts\install-codex.ps1 -AllowedDirectories 'D:\STAAD\Models', 'D:\STAAD\Reports'
  ```

Upon success, the script outputs `PTC queries: 31` along with the path to the generated configuration snippet.

### 3. Configure Codex Client

Open the generated `.venv-codex\openstaad-codex.toml` and merge the table into your Codex configuration:

- **User Configuration**: `%USERPROFILE%\.codex\config.toml` (or `$env:CODEX_HOME\config.toml`).
- **Project Configuration**: `.codex\config.toml` in the project root (trusted projects only).

**Configuration Snippet** (see [examples/codex/config.toml](examples/codex/config.toml) for reference):

```toml
[mcp_servers.openstaad-ptc]
command = 'D:\GPT\openstaad-mcp-PTC\.venv-codex\Scripts\python.exe'
args = ['-m', 'openstaad_mcp.main', '--allowed-dirs', 'D:\GPT\openstaad-mcp-PTC']
cwd = 'D:\GPT\openstaad-mcp-PTC'
startup_timeout_sec = 30
tool_timeout_sec = 180
```

> [!TIP]
> **Using Codex CLI?** You can register the server with a single command from the project root:
> ```powershell
> codex mcp add openstaad-ptc -- "$PWD\.venv-codex\Scripts\python.exe" -m openstaad_mcp.main --allowed-dirs "$PWD"
> codex mcp list
> ```

Restart Codex or restart MCP servers in client settings after saving.

### 4. Verify Connection & Model Query

1. **Schema Check**: Ask Codex to call `discover_ptc`. This verifies all 31 query definitions without needing STAAD.Pro running.
2. **Live Model Test**:
   - Start STAAD.Pro and open a saved test structure (`.std` file).
   - In Codex, submit the following prompt:
   > Use openstaad-ptc: First list running STAAD instances and verify the model path. Once verified, query the base units, total node count, and total member count, returning a concise summary.

When multiple models are open, explicitly specify the instance alias returned by `list_instances` (e.g. `instance="staadPro1"`).

---

## Client Integration Guide

| Client Environment | Recommended Mode | Configuration Notes |
| --- | --- | --- |
| **Local Codex Desktop / CLI** | **STDIO (Recommended)** | Client launches `.venv-codex` Python directly. No open ports, maximum security. |
| **Generic Local MCP Clients** | STDIO / Local HTTP | Compatible with Claude Code, Cursor, Windsurf, Claude Desktop, etc. |
| **ChatGPT Web / Cloud LLMs** | Not directly supported | STAAD.Pro operates via Windows desktop COM; cloud platforms cannot access local desktop processes directly. |

### Standard STDIO Mode (Recommended)

STDIO is the cleanest local setup. The MCP client manages the server lifecycle, with zero network exposure.

### Optional HTTP Transport

When running persistently in the background or serving trusted local network clients:

```powershell
.\.venv-codex\Scripts\openstaad-mcp.exe --transport http --allowed-dirs "$PWD"
```

Default endpoint: `http://127.0.0.1:18120/mcp`. The terminal will display an auto-generated Bearer Token. Configure in your client:

```toml
[mcp_servers.openstaad-ptc]
url = 'http://127.0.0.1:18120/mcp'
bearer_token_env_var = 'OPENSTAAD_MCP_TOKEN'
startup_timeout_sec = 30
tool_timeout_sec = 180
```

Built-in `SecFetchMiddleware` enforces host validation and blocks cross-origin browser requests.

---

## Available MCP Tools

### Top-Level MCP Tools

The server exposes 7 top-level tools through MCP:

| Tool Name | Access Mode | Description |
| --- | --- | --- |
| `discover_ptc` | Read-only | List all 31 PTC queries or retrieve full parameter schema and descriptions for a namespace. |
| `execute_ptc` | Read-only sandbox | Execute synchronized Python scripts calling `tools.*`. Returns structured results or file summary. |
| `list_instances` | Read-only | Enumerate active STAAD.Pro instances, version numbers, and open `.std` file paths. |
| `get_status` | Read-only | Retrieve connection state, STAAD version, active model path, and solver analysis status. |
| `discover_api` | Read-only | Search OpenSTAAD API skills and documentation catalog. |
| `read_skills` | Read-only | Read detailed API reference documents for specified OpenSTAAD skills. |
| `execute_code` | Read/Write sandbox | Execute Python code with direct `staad` object access to modify geometry, loads, and run analysis. |

### PTC Query Namespaces (31 Methods)

Within `execute_ptc`, scripts interact with 31 high-performance queries under `tools.<namespace>.<method>`:

| Namespace | Methods & Capabilities |
| --- | --- |
| **`geometry`** | `get_base_units`, node counts & coordinates (`get_nodes`), member counts & geometry (`get_members`), plates, solids, groups (`get_groups`), member connectivity. |
| **`properties`** | Section profiles & dimensions (`get_member_properties`), materials, plate thicknesses, member end releases (`get_member_releases`). |
| **`loads`** | Primary load cases, load combinations with factors, reference load definitions (`get_load_cases`). |
| **`supports`** | Support node definitions, restraint conditions (fixed/pinned/springs), degrees of freedom releases (`get_supports`). |
| **`analysis`** | Analysis availability check (`are_results_available`), force/displacement units, 6-component end forces (`get_member_forces`), force envelopes, node displacements, reactions, plate stresses. |
| **`design`** | Steel design utilization ratios (`get_utilization`), governing load cases, design codes, critical sections, and full design calculation output. |

> Complete parameter schemas and engineering notes:  
> 📖 [PTC Technical Specification (PTC.zh-CN.md)](docs/PTC.zh-CN.md)  
> 📖 [OpenStaadPython Extension Mapping (PTC-extensions.zh-CN.md)](docs/PTC-extensions.zh-CN.md)

---

## PTC Python Examples

All scripts below are passed as the `code` parameter string to `execute_ptc`.  
The sandbox provides `tools`, `input_data`, `math`, and `json`. Direct access to raw COM objects (`staad`) is disallowed in PTC mode.

### Example 1: Model Scale & Base Units Summary

```python
# Query base unit system and structure scale
units = tools.geometry.get_base_units()
node_count = tools.geometry.get_node_count()
member_count = tools.geometry.get_member_count()

result = {
    "units": units,
    "summary": {
        "total_nodes": node_count,
        "total_members": member_count,
    },
}
```

### Example 2: Filter Critical Horizontal Members by Steel Design Ratio

```python
# 1. Fetch all members with up-axis geometry check
members = tools.geometry.get_members(up_axis="Y")
horizontal_ids = [m["id"] for m in members if m["is_horizontal"]]

# 2. Query latest steel design utilization ratios (stress ratios)
ratios = tools.design.get_utilization(horizontal_ids)

# 3. Filter critical members exceeding 0.9 threshold locally
critical = [r for r in ratios if r.get("available") and r.get("ratio", 0) > 0.9]
unavailable = [r["member_id"] for r in ratios if not r.get("available")]

result = {
    "total_horizontal_members": len(horizontal_ids),
    "critical_count": len(critical),
    "critical_members": critical,
    "missing_design_results": unavailable,
}
```

> [!NOTE]
> For models defined with `SET Z UP`, pass `up_axis="Z"`. Ratios are extracted directly from the solver's steel design parameter block.

### Example 3: Multi-Load-Case Force Envelopes

```python
# Query local 6-component forces across selected members and load cases
member_ids = [101, 102, 103]
load_cases = [1, 2, 101]

forces = tools.analysis.get_member_forces(
    member_ids=member_ids,
    load_cases=load_cases,
    coordinate_system="local",
)

# Locally compute maximum bending moment MZ for each member
envelopes = {}
for f in forces:
    mid = f["member_id"]
    mz = abs(f["mz"])
    if mid not in envelopes or mz > envelopes[mid]["max_mz"]:
        envelopes[mid] = {"max_mz": mz, "load_case": f["load_case"], "end": f["end"]}

result = envelopes
```

Full engineering example scripts:
- Member Forces: [examples/ptc/member_forces.py](examples/ptc/member_forces.py)
- Load Case Envelopes: [examples/ptc/member_envelope.py](examples/ptc/member_envelope.py)
- Plate Stress Reports: [examples/ptc/plate_report.py](examples/ptc/plate_report.py)
- Steel Design Inspection: [examples/ptc/design_details.py](examples/ptc/design_details.py)

---

## CSV / XLSX File Workflows

Both `execute_ptc` and `execute_code` support server-side bulk data streaming:

| Parameter | Type | Behavior |
| --- | --- | --- |
| `input_data_path` | String | Parses a `.csv` or `.xlsx` file on the server and injects contents into sandbox `input_data`. |
| `output_data_path` | String | Writes the script's `result` directly to a `.csv` or `.xlsx` file, returning only row/byte summaries to the client. |
| `overwrite` | Boolean | Default `false`. Set `true` to allow replacing existing destination files. |

### Exporting CSV Data

```python
members = tools.geometry.get_members()
result = [["member_id", "length", "is_horizontal"]] + [[m["id"], m["length"], m["is_horizontal"]] for m in members]
```

### Multi-Sheet Excel Export

Set `result` to `{ "SheetName": { "columns": [...], "rows": [...] } }` to generate formatted multi-tab engineering spreadsheets.

> **Security Guardrails**:
> - Paths must reside within `--allowed-dirs` or client MCP roots.
> - Writes to system directories (`Windows/`, `Program Files/`) and UNC paths are strictly blocked.
> - Safeguards: 50 MB max file size, 100,000 max rows, 500 max columns.

---

## Security, Privacy & Execution Boundaries

1. **Strict Separation of Concerns**: All `tools.*` queries are strictly read-only. Model alterations or solver executions require explicit use of `execute_code`.
2. **Local Data Processing**: Raw model geometry and calculation databases remain within host memory. Only deliberate summaries (`result`), standard output (`stdout`), and exported files are returned.
3. **Static AST Analysis**: Every Python snippet undergoes AST validation prior to execution. Dangerous modules (`os`, `sys`, `subprocess`) and private COM internals (`_oleobj_`) are blocked.
4. **STA Thread Concurrency**: Windows COM requires Single-Threaded Apartment (STA) execution. All COM interactions run on a dedicated STA worker thread with a default 120s timeout.
5. **Inline Result Safeguard**: Inline JSON return data is capped at 64 KB (65,536 bytes). Datasets exceeding this threshold should be summarized or exported via `output_data_path`.

---

## Command Line Options

```powershell
openstaad-mcp [OPTIONS]
```

| Flag | Default | Description |
| --- | --- | --- |
| `--transport {stdio,http}` | `stdio` | MCP transport protocol. |
| `--allowed-dirs DIR [...]` | Unset | Whitelist of directories permitted for CSV/XLSX file I/O. |
| `--log-level {DEBUG,INFO,WARNING,ERROR}` | `INFO` | Stderr logging verbosity. |
| `--port PORT` | `18120` | TCP port for HTTP transport mode. |
| `--token TOKEN` | Random or env | Bearer token for HTTP authentication (`OPENSTAAD_MCP_TOKEN`). |

---

## Frequently Asked Questions (FAQ)

### Setup & Environment

| Issue | Cause & Resolution |
| --- | --- |
| **Missing `ptc/` directory or install script** | Verify you cloned the `PTC-V1` branch; the upstream Bentley repository does not yet have this branch's changes. |
| **`python` not found or version < 3.11** | Install 64-bit Python 3.11+ and add it to PATH, or pass `-Python 'C:\Path\python.exe'` to the script. |
| **PowerShell script execution blocked** | Use the recommended bypass invocation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-codex.ps1`. |
| **WinError 32: File in use during installation** | An active MCP client has locked `.venv-codex` binaries. Close Codex or stop the MCP server, then re-run the installer. |
| **pip cannot download `openstaadpy` wheel** | Check internet access to GitHub Releases; the dependency is pinned to Bentley's official `openstaadpy-26.0.0.62` wheel. |

### Connection & Discovery

| Issue | Cause & Resolution |
| --- | --- |
| **Only 5 tools shown in Codex, missing PTC** | Verify that `command` in Codex's config points to `.venv-codex\Scripts\python.exe`, then restart Codex. |
| **TOML parsing error in Codex** | Ensure there are no duplicate `[mcp_servers.openstaad-ptc]` sections. Use single quotes for Windows file paths. |
| **Cannot detect active STAAD.Pro instance** | Ensure STAAD.Pro is running in the same Windows desktop session with a saved `.std` file open. |
| **Multiple models open, wrong model queried** | Call `list_instances` to inspect paths, then pass `instance="staadPro1"` explicitly in tool arguments. |

### Query Execution & Results

| Issue | Cause & Resolution |
| --- | --- |
| **Steel design utilization unavailable / empty** | Verify the model contains steel design parameters and has been analyzed in STAAD.Pro before querying ratios. |
| **Result exceeds 65,536 bytes limit** | Avoid printing massive intermediate lists; filter key values in Python or specify `output_data_path` to export files. |
| **Path containment error on file export** | Ensure the target path is inside `--allowed-dirs` and not in protected system folders. |
| **Tool call timeout** | Chunk large member ID queries or increase `tool_timeout_sec = 180` in client configuration. |

---

## Development & Verification

For developers extending or testing this server:

```powershell
# 1. Install development dependencies
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-codex.ps1 -Dev

# 2. Run unit tests (Mock environment, no STAAD.Pro required)
.\.venv-codex\Scripts\python.exe -m pytest -o cache_dir="$env:TEMP\pytest_cache" -m "not integration" -q

# 3. Linter & formatting checks
.\.venv-codex\Scripts\ruff.exe check .
.\.venv-codex\Scripts\ruff.exe format --check .
```

### Live STAAD.Pro Integration Tests (Optional)

With a test model open in STAAD.Pro on Windows:

```powershell
$env:OPENSTAAD_PTC_TEST_MODEL = 'D:\STAAD\Models\ptc-test.std'
.\.venv-codex\Scripts\python.exe -m pytest tests/ptc/test_server.py -m integration -v
```

---

## Project Layout & Attribution

```text
openstaad-mcp/
├── scripts/
│   └── install-codex.ps1         # Windows setup & Codex configuration generator
├── examples/
│   ├── codex/config.toml         # Portable Codex configuration template
│   └── ptc/                      # Production-ready PTC Python query examples
├── docs/
│   ├── PTC.zh-CN.md              # PTC technical specifications & engineering semantics
│   └── PTC-extensions.zh-CN.md   # OpenStaadPython method mapping guide
├── src/openstaad_mcp/
│   ├── ptc/                      # PTC engine: namespaces, registry, schema validation
│   ├── sandbox/                  # AST validation, COM proxies, and path security
│   ├── file_io/                  # Secure CSV/XLSX streaming and validation
│   ├── server.py                 # FastMCP protocol setup and top-level tools
│   └── main.py                   # Entry point and CLI arguments
└── tests/
    └── ptc/                      # PTC test suite
```

- **Upstream Foundation**: Built on the open-source [Bentley OpenSTAAD MCP](https://github.com/BentleySystems/openstaad-mcp) using Bentley's `openstaadpy` library.
- **Disclaimer**: This `PTC-V1` branch is a community extension and is not an official release by Bentley Systems or OpenAI.
- **License**: Released under the [MIT License](LICENSE.md). Contributions via issues and pull requests are welcome!
