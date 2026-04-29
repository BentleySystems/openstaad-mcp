# OpenSTAAD MCP Server

A Model Context Protocol server that lets AI agents (Claude Desktop, GitHub Copilot, Gemini, and other MCP clients) drive a running [STAAD.Pro](https://www.bentley.com/software/staad/) model. Define loads, extract results, set properties in bulk, generate reports, and anything else the OpenSTAAD API exposes, from a chat.

Part of Bentley's [Infrastructure AI Co-Innovation Initiative](https://www.bentley.com/software/infrastructure-ai-co-innovation-initiative/).

## Key features

- **Full OpenSTAAD coverage.** Every STAAD.Pro feature reachable through the OpenSTAAD API is reachable through the MCP server, with per-skill documentation the agent can read on demand.
- **Sandboxed execution.** Agent-generated code runs as JavaScript inside a WebAssembly isolate ([Extism](https://extism.org/) + [QuickJS-ng](https://github.com/quickjs-ng/quickjs)) with no filesystem, network, or host memory access. The only way out is a pair of allowlist-gated host functions that expose the STAAD COM API.
- **Multi-instance and local-only.** Connects to every STAAD.Pro instance you have running so an agent can work across models in parallel. Everything runs on your workstation. No cloud, no telemetry.

## Prerequisites

- Windows 11 or newer
- [STAAD.Pro](https://www.bentley.com/software/staad/) 2025 or newer, installed and running

You do not need to have a model file open but you do need to have STAAD running. The server discovers STAAD.Pro via COM ProgID as soon as the application is running, even before you create or open a `.std` file.

## Quick start (Claude Desktop)

1. Download the latest `openstaad-mcp.mcpb` from the [Releases page](https://github.com/BentleySystems/openstaad-mcp/releases).
2. In Claude Desktop, open the menu and go to **File → Settings → Extensions → Advanced → Install Extensions**.
3. Select the `.mcpb` file.
4. Quit and restart Claude Desktop.

Open a new conversation and ask Claude to do something with your STAAD.Pro model. Make sure STAAD.Pro is running before you start.

### Example workflow

Here is a prompt you can try right away, even with a fresh STAAD.Pro launch and no file open:

> Create a new STAAD model, save it to my Documents folder, add two nodes 10 feet apart along X, and connect them with a beam.

The agent will call `NewSTAADFile` to create the `.std` file, then add geometry through the sandbox. You can follow up with prompts like:

> Assign a W10X33 section to the beam, pin the left end, fix the right end, add a 1 KIP/ft uniform load, and run analysis.

## Other clients

All non-Claude-Desktop clients share the same pattern: run the server via `uvx`, either spawned by the client (stdio) or as a long-running process they connect to (HTTP).

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) once:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

The server command is always:

```powershell
uvx --from git+https://github.com/BentleySystems/openstaad-mcp openstaad-mcp
```

Add `--transport http` to run in HTTP mode. The server generates a cryptographic bearer token and pushes it to [OneTimeSecret](https://uk.onetimesecret.com), then displays a one-time share URL in a prominent auth banner in the terminal. Ctrl+click the link to reveal the token. If OTS is unreachable, the raw token is printed directly in the banner. The default HTTP URL is `http://127.0.0.1:18120/mcp`.

| Client | stdio setup | HTTP setup |
|--------|-------------|------------|
| **VS Code + Copilot** | Command Palette → **MCP: Add Server** → **Command (stdio)** → paste the `uvx` command above | Start the server on the remote machine with `--transport http`, then on your local machine: Command Palette → **MCP: Add Server** → **HTTP URL** → paste the bearer token from the auth banner (via the one-time link) when prompted |
| **GitHub Copilot CLI** | `/mcp add` in a session, paste the `uvx` command | Start the server, then `/mcp add` with the HTTP URL. See [Copilot CLI docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers). |
| **Claude Code** | `claude mcp add --transport stdio openstaad -- uvx --from git+https://github.com/BentleySystems/openstaad-mcp openstaad-mcp` | `claude mcp add --transport http openstaad http://staad-host:18120/mcp` |
| **Gemini CLI** | `gemini mcp add openstaad uvx --from git+https://github.com/BentleySystems/openstaad-mcp openstaad-mcp` | `gemini mcp add --transport http openstaad http://staad-host:18120/mcp` |
| **Claude Desktop (manual)** | Edit `claude_desktop_config.json` (see below) | Not typical; use the `.mcpb` bundle or stdio config. |

### Claude Desktop manual config

If you want to skip the `.mcpb` bundle, edit `claude_desktop_config.json` directly. Location depends on install type:

- Windows MSIX: `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\claude_desktop_config.json`
- Windows classic: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

```jsonc
{
  "mcpServers": {
    "openstaad": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/BentleySystems/openstaad-mcp", "openstaad-mcp"]
    }
  }
}
```

## CLI options

| Flag | Default | Notes |
|------|---------|-------|
| `--transport {stdio,http}` | `stdio` | stdio is spawned by the client; HTTP is a long-running server. |
| `--log-level LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR`. |
| `--log-file PATH` | OS default | Where log output goes. |
| `--port PORT` | `18120` | HTTP only. |
| `--ots-base-url URL` | `https://uk.onetimesecret.com` | HTTP only. OneTimeSecret regional endpoint. |
| `--allowed-host HOSTNAME` | *(loopback only)* | HTTP only. Repeatable. Adds a hostname to the `Host`-header allowlist. Loopback names (`127.0.0.1`, `localhost`, `::1`, `[::1]`) are always accepted; use this flag to allow tunnel or reverse-proxy hostnames (e.g. `--allowed-host my-tunnel.example.com`). Defeats DNS rebinding. |

## Security model

The server sits on an engineer's workstation next to a live STAAD.Pro process and executes code written by an AI agent. That means two trust boundaries: the agent's code, and (optionally) the HTTP transport. Both are locked down by default.

### Agent code runs in a WASM sandbox

The `execute_code` tool runs JavaScript inside a WebAssembly isolate (Extism hosting QuickJS-ng on Wasmtime). In that environment:

- No filesystem access.
- No network access.
- No host memory access. WebAssembly linear memory is isolated by the runtime.
- No ambient runtime. Bare ECMAScript with `console`, `JSON`, `Math`, and the standard language built-ins. No module loader, no `process`, no host APIs.

The only way out of the sandbox is through two allowlist-gated host functions that expose the STAAD COM API. Only nine top-level sub-objects are reachable (`Geometry`, `Property`, `Support`, `Load`, `Command`, `Output`, `Design`, `Table`, `View`), each gated by a per-object method allowlist (deny-by-default). Only a curated set of root methods is callable, and every return value crosses a JSON boundary, so COM pointers and dispatch objects never enter the sandbox.

### Per-call resource limits

A single `execute_code` call is capped at 30 seconds wall-clock, 64 MiB of linear memory, 256 KiB of source code, and 256 KiB of captured `console` output. Exceeding any of these returns a sanitized error. A process-wide limit of 20 concurrent COM worker threads prevents runaway accumulation if calls time out repeatedly.

### HTTP transport authentication

HTTP mode is designed for remote access: STAAD.Pro and the MCP server run on one machine, and the user connects from another. At startup the server generates a cryptographic bearer token (`secrets.token_urlsafe(32)`) in memory and pushes it to [OneTimeSecret](https://uk.onetimesecret.com) via their v2 guest API. Only the resulting one-time share URL is displayed in the terminal — the token itself never appears on the command line, in logs, in config files, or on the network. The MCP server never transmits or stores the secret; OTS holds it, and the user retrieves it directly from OTS by Ctrl+clicking the link. This means zero secret handling in the MCP transport layer.

A rich auth banner (yellow-bordered panel, same library FastMCP uses) is printed to the terminal showing the one-time share URL, the server URL, and a ready-to-paste `mcp.json` snippet. If OTS is unreachable, the raw token is printed directly in the banner as a fallback.

Clients must send `Authorization: Bearer <token>` on every request. The listener binds to `127.0.0.1` by default and rejects any request whose `Host` header is not in the allowlist (loopback names by default; extend with `--allowed-host` for tunnel or reverse-proxy deployments). The `Host`-header check runs before bearer-auth, so DNS-rebinding attacks fail at the first gate without ever reaching the token layer.

Stdio transport does not use tokens because the MCP client is the one spawning the server process.

### What this does not try to solve

- **Prompt injection via model content.** Member names, load descriptions, and notes flow back to the agent as tool output. If an attacker can put instructions into a model, a naive agent may follow them. That is an agent policy problem, not a server problem.

### Consent gate for destructive operations

Filesystem-write and session-destructive COM methods (`SaveModel`, `NewSTAADFile`, `ExportView`, `Quit`, etc.) are **blocked by default** inside the sandbox. When `execute_code` detects such methods in submitted code, the server triggers **MCP elicitation** — a host-mediated confirmation dialog that the user must approve before the code can run with write permissions. The LLM cannot self-confirm this gate; it is a dialog between the MCP server and the host application (Claude Desktop, VS Code), presented directly to the human. UNC paths (e.g. `\\server\share\...`) are always rejected regardless of consent, to prevent NTLM credential relay.

For the full security audit (14 findings, April 2026) and implementation details, see [`docs/v2-changes-summary.md`](docs/v2-changes-summary.md), [`docs/plan.md`](docs/plan.md), and the individual finding reports in [`code-review/`](code-review/).

## Available tools

| Tool | What it does |
|------|--------------|
| `discover_api` | Lists available API skills and usage guidance. |
| `read_skills` | Returns detailed guidance for requested skills. |
| `list_instances` | Lists active STAAD.Pro instances with model paths and versions. |
| `execute_code` | Runs agent-generated JavaScript against the connected STAAD.Pro model inside the WebAssembly sandbox. |
| `get_status` | Returns connection state, STAAD version, model path, and analysis status. |
| `read_analysis_output` | Reads the `.ANL` or `.LOG` file for the open model. The only way to access concrete, timber, and aluminum design results (not available via COM). |

## Development

```powershell
git clone https://github.com/BentleySystems/openstaad-mcp.git
cd openstaad-mcp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# Run from source
openstaad-mcp                     # stdio
openstaad-mcp --transport http    # HTTP

# Tests
pytest                            # unit + sandbox tests, no STAAD needed
pytest -m integration -v          # requires running STAAD.Pro on Windows

# Lint
ruff check .
ruff format --check .
```

Building the `.mcpb` installer bundle and other contributor workflows are covered in [CONTRIBUTING.md](CONTRIBUTING.md).

## Known security issues

**QuickJS-NG CVEs in bundled WASM engine.** The sandbox uses extism-js v1.6.0, which bundles QuickJS-NG ~v0.11.0 via rquickjs 0.11. Five CVEs affect this version range (heap overflow, UAF, OOB). There is no newer extism-js release to upgrade to yet.

Why this is lower-risk than it sounds: QuickJS-NG runs inside the WASM isolate. Memory corruption stays within WASM linear memory and Wasmtime enforces the boundary at the hardware level. The host functions on the Python side validate all inputs through JSON parsing and handle-table lookups, so corrupted WASM state cannot forge valid COM calls. An attacker would need to chain four steps: trigger a QJS bug, get arbitrary WASM memory access, craft valid JSON that passes the host-side allowlist, and invoke a dangerous COM method. The last two steps are already blocked by the root allowlist and deny list. We are tracking upstream for a new extism-js release that bumps rquickjs past 0.11.

## Reporting security issues

Please do not file public GitHub issues for security vulnerabilities. Report them through Bentley's [Responsible Disclosure Program](https://www.bentley.com/legal/bug-bounty-report/). See [SECURITY.md](SECURITY.md) for a short summary.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming, PR process, and packaging instructions.
