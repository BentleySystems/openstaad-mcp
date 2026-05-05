# Changelog

## 2.1.0 (2026-04-28)

### Changed

- **HTTP auth: OTS share URL replaces email delivery.** The v2 guest API does not support sending emails without an OTS account. The server now pushes the bearer token to OneTimeSecret and displays only the one-time share URL in a prominent auth banner (rendered via Rich). The MCP server never transmits or stores the secret — only a URL is shared, so zero secrets flow through the MCP transport layer. If OTS is unreachable, the raw token is shown in the banner instead.
- **`--email` removed.** The `--email` flag and `OPENSTAAD_EMAIL` env var have been removed entirely. The auth banner no longer displays or requires an email address.
- **Auth banner uses Rich panels.** Matches FastMCP's own banner style. Includes OTS link (with OSC 8 terminal hyperlink support), server URL, and a ready-to-paste `mcp.json` snippet. Printed 3 seconds after startup to appear below FastMCP/uvicorn splash output.
- **OTS response parsing aligned to v2 OpenAPI spec.** Share URL constructed from `record.secret.key` and `record.share_domain` fields (no `share_url` field exists in the API). Falls back to `--ots-base-url` when `share_domain` is null.

### Added

- Tutorial 3 (Analysis of a Slab) verified end-to-end through the MCP server. Plate elements, area loads, and plate stress/force output all matched Bentley documentation to 4+ significant figures.

## 2.0.0 (2026-04-26)

Complete sandbox rewrite. The Python `exec()`-based sandbox is gone, replaced by a WASM isolate (Extism + QuickJS-ng + Wasmtime). This eliminates 5 of 7 High-severity findings from the April 2026 security audit and fixes the rest. See `docs/v2-changes-summary.md` for the full story.

### Breaking changes

- **`execute_code` now runs JavaScript, not Python.** Clean break, no compatibility shim. COM method names and call patterns are identical; only the syntax changes (`const` instead of `=`, `console.log` instead of `print`, etc.). All 15 bundled skill scripts have been converted.
- **HTTP transport: `--token` removed.** The server generates a cryptographic bearer token in memory and delivers it via a OneTimeSecret share URL displayed in the terminal auth banner. The token never appears on the command line or in any file. Clients send `Authorization: Bearer <token>` as before. *(Updated in 2.1.0: `--email` flag removed entirely.)*
- **Old sandbox modules removed:** `sandbox/ast.py`, `sandbox/executor.py`, `sandbox/module_proxy.py`, `sandbox/const.py`, and all 15 Python skill scripts.

### Added

- WASM sandbox (`sandbox/wasm_executor.py`). Fresh plugin per `execute_code` call. No filesystem, network, or host-memory access from user code.
- Allowlist-gated COM bridge. Two host functions (`com_get`, `com_invoke`) are the only way out of the sandbox. Root object gated by 26 allowed methods and 9 named sub-objects. Sub-objects gated by per-object method allowlists (deny-by-default, 727 methods total). Global deny list blocks `SetStandardProfileDBFolder`.
- Consent gate for destructive operations (Control 4 — Explicit Consent). Filesystem-write and session-destructive COM methods (`NewSTAADFile`, `SaveModel`, `ExportView`, `Quit`, etc.) are blocked by default inside the sandbox. When destructive method names are detected, the server triggers MCP elicitation — a host-mediated confirmation dialog the user must approve. The LLM cannot self-confirm this gate. UNC paths are always rejected regardless of consent (NTLM relay prevention).
- Per-call execution limits: 30s wall-clock, 128 MiB WASM memory, 256 KiB stdout/stderr, 256 KiB max code size.
- `HostHeaderMiddleware` for DNS rebinding defense (HTTP 421 before auth). Default: loopback only. Extend via `--allowed-host`.
- OTS-based HTTP auth (`ots_delivery.py`). Bearer token auto-generated and pushed to OneTimeSecret; one-time share URL displayed in the terminal auth banner. Fallback: raw token printed in the banner if OTS is unreachable. *(Updated in 2.1.0: `--email` flag removed entirely.)*
- `--ots-base-url` flag (default: `https://uk.onetimesecret.com`).
- Bounded COM threads: `MAX_COM_THREADS=20` semaphore. Fail-fast at the limit.
- Error sanitization: COM exceptions replaced with generic messages before crossing the WASM boundary.
- 41 adversarial tests (prompt injection, sandbox escape, OOB verification).
- Evaluator.js runtime hardening: `Host.getFunctions()` neutered, `Host.__hostFunctions` emptied, `Host.invokeFunc` wrapped to reject negative memory offsets (CFFI OverflowError DoS prevention), `fetch` removed. 9 new tests in `TestGlobalHardening`.
- MCP integration test harness (`tests/test_mcp_live.py`). 19 end-to-end tests that spawn the real server via stdio and verify hardening, allowlists, consent gates, and protocol edge cases.
- 15 JavaScript skill scripts replacing the Python originals.

### Changed

- `read_skills` path traversal hardened. `Path.resolve()` + `is_relative_to()` containment.
- Removed hardcoded `C:\Temp` from `create-new-model.js` and `take-screenshot.js`; replaced with user-prompt placeholders.
- PyInstaller spec updated to bundle `evaluator.wasm`, `extism`/`extism_sys` shared libs, `fastmcp` metadata.
- `.mcpb` manifest bumped to 2.0.0.
- Example MCP config files updated for OTS auth flow.

### Security findings resolved

| Title | Severity | Resolution |
|-------|----------|------------|
| `str.format()` dunder bypass | High | Eliminated (no Python `exec()`) |
| Path traversal in `read_skills` | High | Fixed (`Path.resolve()` + containment) |
| COM internal attributes bypass | High | Eliminated (COM objects never enter WASM) |
| Executor deadlock after timeout | High | Eliminated (no threading lock) |
| COM filesystem write / NTLM relay | Medium | **Fixed** (consent gate + UNC rejection + deny list + allowlist) |
| HTTP unauthenticated by default | High | Fixed (mandatory OTS bearer auth) |
| Unbounded resource consumption | High | Fixed (WASM memory/time/output caps) |
| MRO type hierarchy leak | High | Eliminated (no Python type system in WASM) |
| Prompt injection via COM output | Medium | Accepted risk (agent-layer concern) |
| Missing DNS-rebinding defense | Medium | Fixed (`HostHeaderMiddleware`) |
| Stack trace info disclosure | Low | Improved (error sanitization) |
| Token in process args | Info | Fixed (`--token` removed, OTS delivery) |
| CFFI OverflowError DoS via negative offset | Medium | Fixed (evaluator.js runtime hardening) |

### Known issues

- **QuickJS-NG CVEs** (CVE-2026-0821, -0822, -1144, -1145, -3979). Affect bundled QuickJS-NG <=0.11.0. Mitigated by WASM isolation: memory corruption stays inside the isolate and cannot forge valid COM calls. Tracking upstream for extism-js update.
- **Open sub-object method surface.** Sub-object handles allow any method name past the global deny list. Audited safe for current STAAD.Pro version (727 methods, 2026-04-15). Generated per-sub-object allowlist ready to deploy if needed.

### Rollback

v1.x remains available via `pip install openstaad-mcp<2.0`.
