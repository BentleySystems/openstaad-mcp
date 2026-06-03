# AGENTS.md

## Project Overview

MCP server bridging AI agents to Bentley STAAD.Pro via the OpenSTAAD COM API.  
Windows-only (pywin32/COM). Python 3.11+. See [README.md](README.md) for full details.

## Build & Test

```bash
pip install -e ".[dev]"          # Install with dev dependencies
ruff check . ; ruff format --check .  # Lint + format check
ruff check --fix . ; ruff format .    # Auto-fix
pytest                                # Unit tests (any OS, no STAAD needed)
pytest -m integration -v              # Integration tests (Windows + STAAD running)
```

## Architecture

| Component | Purpose |
|-----------|---------|
| `main.py` | CLI entry point, transport setup (stdio/HTTP) |
| `server.py` | MCP tool definitions (`discover_api`, `read_skills`, `execute_code`, `get_status`) |
| `connection.py` | Multi-instance management via Windows ROT scan, STA-thread COM dispatch |
| `sandbox/executor.py` | AST-validated sandboxed `exec()` with stdout/stderr capture |
| `sandbox/com_proxy.py` | COM object proxy — blocks internal attrs, validates file paths |
| `sandbox/ast.py` | AST validation, format-string bypass detection, last-expr rewriting |
| `sandbox/const.py` | Allowlists for builtins, exceptions, and module attributes |
| `sandbox/path_validator.py` | Blocks writes to protected dirs, detects UNC paths (NTLM relay prevention) |
| `http_middleware.py` | `SecFetchMiddleware` — blocks cross-origin browser requests |
| `skills.py` | Skill discovery from `staad_skills/` with YAML frontmatter extraction |

## Conventions

- **Line length**: 120 characters
- **Linter/formatter**: Ruff (Black-compatible). Config in [pyproject.toml](pyproject.toml)
- **Ruff rules**: `E, F, W, I, UP, B, SIM, RUF` (ignoring `E501`, `RUF200`)
- **Tests**: pytest + pytest-asyncio (`asyncio_mode = "auto"`). Mark integration tests with `@pytest.mark.integration`
- **100% test coverage expected** for new code
- **All async tests** use `pytest-asyncio` auto mode — no manual event loop setup
- **Limit the number of if-else branches**: Use polymorphism (or equivalents) when possible. 
- **Single responsibility**: Aim for functions and classes with a single responsibility.
- **Data validation**: Use Pydantic models when runtime validation is needed. For static type checking, use type hints.

## Security

 Security is critical. This project handles arbitrary code execution via a sandboxed `exec()`. A better sandboxing strategy is underway. For now:

**Always enforce when modifying sandbox code:**
- AST validation runs before any `exec()` — never bypass it
- `ALLOWED_BUILTINS` and `ALLOWED_MODULE_ATTRS` in `sandbox/const.py` are allowlists, not blocklists
- `COMProxy` must block all internal COM attributes (`_oleobj_`, `_ApplyTypes_`, etc.)
- File path validation must reject UNC paths and writes to `Windows/`, `Program Files/`, `ProgramData/`
- Inputs passed to the sandbox must be deep-frozen (tuples, not lists) to prevent mutation
- HTTP mode requires `SecFetchMiddleware` and supports optional bearer token auth
- Never expose stack traces to end users — sanitize error messages

## Key Patterns

**COM threading**: All COM calls must run on a dedicated STA thread via `connect_and_run()`. Never call COM from the main asyncio thread.

**Sandbox execution flow**: Request → AST validate → rewrite last expression → build restricted globals → `exec()` → capture stdout/stderr → JSON-serialize result.

**Skills**: Each skill lives in `staad_skills/<name>/SKILL.md` with YAML frontmatter. The skill index is pre-scanned at startup — skill reads are validated against this index to prevent path traversal.
