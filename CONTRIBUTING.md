# Contributing to OpenSTAAD MCP

Welcome, and thank you for your interest in contributing to the OpenSTAAD MCP server!

There are many ways to contribute.
The goal of this document is to provide a high-level overview of how you can get involved.

## Development Setup

**Prerequisites:** Python 3.11+ and Git.

```bash
# 1. Clone the repository
git clone https://github.com/BentleySystems/openstaad-mcp.git
cd openstaad-mcp

# 2. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # PowerShell
# or: .venv\Scripts\activate.bat  (cmd)

# 3. Install in editable mode with dev dependencies
pip install -e ".[dev]"

# 4. Verify the install
openstaad-mcp --help
```

> **Note:** The `openstaadpy` dependency is bundled as a local wheel in
> `OpenSTAADPy/Setup/`. It is installed automatically by `pip install -e .`.

## Source Code Edit Workflow

1. Make sure your local `main` branch is up to date: `git pull origin main`.
2. Create a feature branch: `git checkout -b "<your-branch-name>"` (see [Branch Naming Policy](#branch-naming-policy)).
3. Make your source code changes under `src/openstaad_mcp/`.
4. Run the linter: `ruff check .` and `ruff format --check .`.
5. Run unit tests: `pytest`.
6. Commit your changes locally.
7. Push the branch and open a pull request against `main`.

## Running Tests

```bash
# All unit tests (works on any OS — no STAAD.Pro required)
pytest

# Verbose output for a specific test file
pytest tests/test_skills.py -v

# Integration tests (requires running STAAD.Pro on Windows)
pytest -m integration -v
```

Tests are written with [pytest](https://docs.pytest.org/) and
[pytest-asyncio](https://pytest-asyncio.readthedocs.io/).
The `tests/sandbox/` directory contains tests for the code-execution sandbox.

## Linting

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Check for lint errors
ruff check .

# Check formatting
ruff format --check .

# Auto-fix lint issues
ruff check --fix .

# Auto-format
ruff format .
```

## Building the `.mcpb` installer bundle

The `.mcpb` bundle is what end users install into Claude Desktop. Build it with:

```powershell
pip install -e ".[build]"
pyinstaller mcpb/openstaad-mcp.spec --noconfirm

npm install -g @anthropic-ai/mcpb
New-Item -ItemType Directory -Path mcpb-staging -Force
Copy-Item -Recurse dist/openstaad-mcp/* mcpb-staging/
Copy-Item mcpb/manifest.json mcpb-staging/
mcpb pack mcpb-staging openstaad-mcp.mcpb
```

The bundle lands at `.\openstaad-mcp.mcpb`. PyInstaller runs in onedir mode (see `mcpb/openstaad-mcp.spec`), which is necessary because `extism_sys.dll` is a Rust-compiled cdylib and does not survive onefile extraction reliably.

## Reporting Issues

Have you identified a reproducible problem?
Have a feature request?
We want to hear about it!

### Look For an Existing Issue

Before you create a new issue, please search the
[open issues](https://github.com/BentleySystems/openstaad-mcp/issues) to see
if the issue or feature request has already been filed.

If your issue already exists, add relevant comments and your
[reaction](https://github.com/blog/2119-add-reactions-to-pull-requests-issues-and-comments).
Use a reaction in place of a "+1" comment:

- 👍 : upvote
- 👎 : downvote

### Writing Good Bug Reports and Feature Requests

File a single issue per problem or feature request.
Do not enumerate multiple bugs or feature requests in the same issue.

Please include the following with each issue:

- A short description of the issue (this becomes the title)
- Python version and OS
- STAAD.Pro version (if applicable)
- Steps to reproduce, or a minimal code snippet that demonstrates the problem
- What you expected to see versus what actually happened
- Relevant log output (check `%LOCALAPPDATA%\OpenSTAAD MCP\mcp_server.log`)
- Use the [`bug`](https://github.com/BentleySystems/openstaad-mcp/labels/bug)
  or [`enhancement`](https://github.com/BentleySystems/openstaad-mcp/labels/enhancement)
  label to identify the type of issue

### Follow Your Issue

You may be asked to clarify things or try different approaches, so please follow your issue and be responsive.

## Contributons

We'd love to accept your contributions to the OpenSTAAD MCP server.
There are just a few guidelines you need to follow.

### Contributor License Agreement (CLA)

A [Contribution License Agreement with Bentley](https://gist.github.com/imodeljs-admin/9a071844d3a8d420092b5cf360e978ca) must be signed before your contributions will be accepted. Upon opening a pull request, you will be prompted to use [cla-assistant](https://cla-assistant.io/) for a one-time acceptance applicable for all Bentley projects.
You can read more about [Contributor License Agreements](https://en.wikipedia.org/wiki/Contributor_License_Agreement) on Wikipedia.

### Pull Requests

All submissions go through a review process.
We use GitHub pull requests for this purpose.
Consult [GitHub Help](https://help.github.com/articles/about-pull-requests/) for more information on using pull requests.

### Security-Sensitive Changes

Changes to the sandbox allowlists (`constants.py` — `ALLOWED_SUB_OBJECTS`, `ALLOWED_ROOT_METHODS`, `DENIED_METHODS`) or to the WASM host functions (`wasm_executor.py` — `com_get`, `com_invoke`) **require security review** before merge. The reviewer must verify that:

- New allowlisted methods do not perform file I/O, network access, or process operations (see `docs/plan.md` "Sub-object audit methodology").
- Deny-list removals have documented justification.
- Host function changes do not widen the data surface exposed to WASM code.

Tag PRs touching these files with the `security-review` label.

### Types of Contributions

We welcome contributions, large or small, including:

- Bug fixes
- New features and MCP tools
- Documentation corrections or additions
- New STAAD skills content
- Test coverage improvements

Thank you for taking the time to contribute to open source and making the OpenSTAAD MCP server better!