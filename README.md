# OpenSTAAD MCP Server

A Model Context Protocol (MCP) server for Bentley [STAAD.Pro](https://www.bentley.com/software/staad/) that **enables AI agents** like Claude Desktop, Gemini, or VSCode Copilot **to interact with your STAAD.Pro models** and perform various time-consuming tasks like load cases definition, data extraction, repetitive property setting and more.

This MCP server was introduced as part of Bentley's [Infrastructure AI Co-Innovation Initiative](https://www.bentley.com/software/infrastructure-ai-co-innovation-initiative/) to help our users and accounts discover opportunities and innovate faster, while connecting Bentley's unique engineering tool capabilities to their emerging agentic workflows.

## Key Features

- **Fast and flexible**: Enjoy minimal latency, interact with every STAAD.Pro features covered by the OpenSTAAD API.
- **AI-friendly**: Provides documentation, guidance and feedback via dedicated tools to help your AI agent ramp up quickly on the STAAD.Pro API.
- **Multi-instance support**: Connects to multiple running STAAD.Pro instances simultaneously to parallelize tasks across models.
- **Privacy-first**: All processing happens locally on your machine. No data is sent to the cloud. No telemetry.

## Prerequisites

- OS: **Windows 11 or newer**
- [STAAD.Pro](https://www.bentley.com/software/staad/) 2025 or newer installed and running

## Quick Start with Claude Desktop (<2min)

1. Download the latest **`openstaad-mcp.mcpb`** file from the [GitHub Releases](https://github.com/BentleySystems/openstaad-mcp/releases) page.
2. Open **Claude Desktop**.
3. Click the **☰ menu** (top-left) → **File** → **Settings** → **Extensions**.
4. Click **Advanced** → **Install Extensions**.
5. Select the downloaded `.mcpb` file.
6. Click the **☰ menu** (top-left) → **File** → **Exit**
7. Restart Claude Desktop.

Claude Desktop will install the server automatically. Open a new conversation and ask Claude to interact with your STAAD.Pro model.

**Tip: Make sure STAAD.Pro is running with a model open before you start chatting.**

---

## Other Clients & Configuration

**TL;DR:**

If not already installed, [install uv](https://docs.astral.sh/uv/getting-started/installation/) with the command:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Configure your client to start the server in stdio mode with the command:

```powershell
uvx --from git+https://github.com/BentleySystems/openstaad-mcp openstaad-mcp
```

### VS Code with GitHub Copilot

- For **stdio**: Open the Command Palette → **MCP: Add Server...** → **Command (stdio)** and enter the following command:
  ```powershell
  uvx --from git+https://github.com/BentleySystems/openstaad-mcp openstaad-mcp
  ```

- For **http**: First, start the server in a terminal:
  ```powershell
  uvx --from git+https://github.com/BentleySystems/openstaad-mcp openstaad-mcp --transport http
  ```
  Look for the generated token and URL in the terminal output. It should look like this:
  ```
  WARNING: No --token provided. Auto-generated token: abc123def456ghi789jkl012mno345pq
  INFO:  Starting MCP server 'OpenSTAAD MCP' with transport 'http' (stateless) on http://127.0.0.1:18120/mcp
  ```

  Then, in VS Code, open the Command Palette → **MCP: Add Server...** → **HTTP URL** and enter the URL shown in the terminal (e.g. `http://127.0.0.1:18120/mcp`). `18120` is the default port, but yours may differ if you have multiple instances running or if you changed the default. Add the header `Authorization: Bearer <token>` with the token shown in the MCP server terminal.

### GitHub Copilot CLI

Use the `/mcp add` command inside a Copilot CLI session to add the server. See the [Copilot CLI documentation](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers) for more details.

- For **stdio** transport, use the command:
  ```powershell
  uvx --from git+https://github.com/BentleySystems/openstaad-mcp openstaad-mcp
  ```

- For **HTTP** transport, first start the server in a terminal:
  ```powershell
  uvx --from git+https://github.com/BentleySystems/openstaad-mcp openstaad-mcp --transport http
  ```
  Look for the generated token and URL in the terminal output. It should look like this:
  ```
  WARNING: No --token provided. Auto-generated token: abc123def456ghi789jkl012mno345pq
  INFO:  Starting MCP server 'OpenSTAAD MCP' with transport 'http' (stateless) on http://127.0.0.1:18120/mcp
  ```

  Then add the server in Copilot CLI using the URL shown in the terminal (e.g. `http://127.0.0.1:18120/mcp`). `18120` is the default port, but yours may differ if you have multiple instances running or if you changed the default. Add the header `Authorization: Bearer <token>` with the token shown in the MCP server terminal.

### Claude Desktop (manual configuration)

If you prefer manual setup over the `.mcpb` bundle, edit the Claude Desktop
config file directly:

- **Windows (MSIX)**: `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\claude_desktop_config.json`
- **Windows (classic)**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

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

### Claude Code (CLI)

- For **stdio** transport, use the command:
  ```powershell
  claude mcp add --transport stdio openstaad -- uvx --from git+https://github.com/BentleySystems/openstaad-mcp openstaad-mcp
  ```

- For **HTTP** transport, first start the server in a terminal:
  ```powershell
  uvx --from git+https://github.com/BentleySystems/openstaad-mcp openstaad-mcp --transport http
  ```
  Look for the generated token and URL in the terminal output. It should look like this:
  ```
  WARNING: No --token provided. Auto-generated token: abc123def456ghi789jkl012mno345pq
  INFO:  Starting MCP server 'OpenSTAAD MCP' with transport 'http' (stateless) on http://127.0.0.1:18120/mcp
  ```

  Then add the server in Claude Code with the command:
  ```powershell
  claude mcp add --transport http openstaad http://127.0.0.1:18120/mcp --header "Authorization: Bearer <your-token>"
  ```
  `18120` is the default port, but yours may differ if you have multiple instances running or if you changed the default.

### Gemini CLI

- For **stdio** transport, use the command:
  ```powershell
  gemini mcp add openstaad uvx --from git+https://github.com/BentleySystems/openstaad-mcp openstaad-mcp
  ```

- For **HTTP** transport, first start the server in a terminal:
  ```powershell
  uvx --from git+https://github.com/BentleySystems/openstaad-mcp openstaad-mcp --transport http
  ```
  Look for the generated token and URL in the terminal output. It should look like this:
  ```
  WARNING: No --token provided. Auto-generated token: abc123def456ghi789jkl012mno345pq
  INFO:  Starting MCP server 'OpenSTAAD MCP' with transport 'http' (stateless) on http://127.0.0.1:18120/mcp
  ```

  Then add the server in Gemini CLI with the command:
  ```powershell
  gemini mcp add --transport http --header "Authorization: Bearer <your-token>" openstaad http://127.0.0.1:18120/mcp
  ```
  `18120` is the default port, but yours may differ if you have multiple instances running or if you changed the default.

### Transport Modes

The server supports two transport modes:

| Mode | When to use |
|------|-------------|
| **stdio** (default) | The MCP client launches the server process directly. Used by Claude Desktop, Claude Code, VS Code Copilot (stdio config). |
| **HTTP** | The server runs persistently and clients connect over the network. |


### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--transport {stdio,http}` | `stdio` | Transport mode |
| `--log-level LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `--log-file PATH` | OS default | Path to log file |
| `--port PORT` | `18120` | **[http]** TCP port to listen on |
| `--token TOKEN` | - | **[http]** Bearer token for authentication |

---

## Available MCP Tools

| Tool | Description |
|------|-------------|
| `discover_api` | Lists available API skills and usage guidance |
| `read_skills` | Returns detailed guidance for requested skills |
| `list_instances` | Lists active STAAD.Pro instances with model paths and versions |
| `execute_code` | Runs validated Python code against the connected STAAD.Pro model |
| `get_status` | Returns connection state, STAAD version, model path, analysis status |

### File I/O

The `execute_code` tool supports optional **server-side file I/O** for bulk data workflows.
Instead of passing large datasets through the agent's context window, the server reads/writes
CSV and XLSX files directly and injects the data into the sandbox as the `input_data` variable.

| Parameter | Description |
|-----------|-------------|
| `input_path` | Path to a `.csv` or `.xlsx` file. The server reads and parses it, then injects the data as the immutable `input_data` variable in the sandbox. |
| `output_path` | Path where the sandbox return value will be written. The return value must be a list-of-lists (CSV) or a `{sheet_name: {columns, rows}}` dict (multi-sheet XLSX). |
| `overwrite` | Allow overwriting an existing output file (default `false`). |

**Path containment:** File paths must resolve inside a configured allowed boundary before any read/write occurs.
The server supports both **client-configured MCP roots** and **server-configured allowed directories** (via `--allowed-dirs` or `user_config.allowed_directories` in the manifest).
The server validates paths against these boundaries before any file access.

**Limits:** Max file size 50 MB, max 100K rows, max 500 columns, max 50 input sheets.

## Security Notes

- **Bearer token authentication.** Pass `--token MY_SECRET_TOKEN` when running in HTTP mode and include `Authorization: Bearer <token>` in client requests.
- **DNS rebinding protection.** Starlette Middlewares validate `Host`, `Sec-Fetch-Site` and `Origin` headers.
- **Code sandbox.** The `execute_code` tool validates all Python code via
  AST analysis before execution. Imports, file access, and dangerous
  builtins are blocked.

## Privacy Policy

Please find the Bentley Systems privacy policy [here](https://www.bentley.com/legal/privacy-policy/).

---

## Development Setup

### 1. Clone the repository

```powershell
git clone https://github.com/BentleySystems/openstaad-mcp.git
cd openstaad-mcp
```

### 2. Create a virtual environment

```powershell
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# Windows (cmd)
.venv\Scripts\activate.bat
```

### 3. Install in editable mode with dev dependencies

```powershell
pip install -e ".[dev]"
```

### 4. Run the server from source

```powershell
# stdio mode (default)
openstaad-mcp

# HTTP mode
openstaad-mcp --transport http
```

### 5. Run tests

```powershell
# All unit tests (no STAAD.Pro needed)
pytest

# Specific test files
pytest tests/test_skills.py tests/test_connection.py -v

# Integration tests (requires a running STAAD.Pro instance on Windows)
pytest -m integration -v
```

### 6. Lint

```powershell
ruff check .
ruff format --check .
```

### 7. Building the MCPB Bundler

1. To produce the standalone `.exe` files distributed via the installer:

  ```powershell
  pip install -e ".[build]"
  pyinstaller mcpb/openstaad-mcp.spec --noconfirm
  ```

  This creates one file in the `dist/` directory:

  - `openstaad-mcp.exe`: console executable (stdio & http transport)

2. To create the `.mcpb` installer bundle, run:

  ```powershell
  npm install -g @anthropic-ai/mcpb
  New-Item -ItemType Directory -Path mcpb-staging -Force
  Copy-Item dist/openstaad-mcp.exe mcpb-staging/

  $version = (Select-String -Path pyproject.toml -Pattern '^version\s*=\s*"(.+)"$').Matches[0].Groups[1].Value
  $manifest = Get-Content mcpb/manifest.json -Raw | ConvertFrom-Json
  $manifest.version = $version
  $manifest | ConvertTo-Json -Depth 10 | Set-Content mcpb-staging/manifest.json -Encoding utf8

  mcpb pack mcpb-staging/ openstaad-mcp.mcpb
  ```

The output MCPB bundle is written to `.\openstaad-mcp.mcpb`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on setting up your
development environment, branch naming, running tests, and submitting pull
requests.
