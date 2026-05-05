# openstaad-mcp v2.0.0 vs. Security Architecture Guidelines

**Date:** 2026-04-23
**Reviewer:** Dave Hanson (owner, adversarial test author)
**Scope:** openstaad-mcp v2.0.0 sandbox implementation reviewed against internal Security Architecture spec (`security-architecture.md`)
**Test evidence:** 42 adversarial tests in `tests/adversarial/` (12 basic vector + 30 modern PI), Burp Collaborator OOB verification, live STAAD.Pro COM round-trip

---

## The short version

Section 10 ("Code Mode" isolation) is the part of the security architecture most directly written for what we built. We exceed all four baseline requirements. The WASM sandbox (Extism + QuickJS-ng + Wasmtime) is a harder boundary than the Deno/container/Electron options the doc contemplates.

The one real gap is Control 4 (explicit consent). `execute_code` has no approval gate at our layer. We rely on the host (Claude Desktop, VS Code) to provide one, and their "allow for this conversation" UX defeats the gate for the exact attack scenario (OMCP-009) we proved works. That's a known accepted risk, documented and tested, but it's worth flagging cleanly.

Everything else is either a clean pass or not applicable to a single-user desktop MCP server talking to local COM.

---

## Section 10 -- "Code Mode" Isolation (Most Directly Applicable)

openstaad-mcp's `execute_code` tool is textbook **User "Code Mode"** -- an MCP server executing LLM-generated code on a user machine, single-user, single-tenant.

| Requirement | Guideline | What We Built | Verdict |
|---|---|---|---|
| **(1) No external network** | "Restricted to user machine local network by default." Calls out the "lethal trifecta." | WASM sandbox has zero network stack. `fetch()` WASM-traps. `XMLHttpRequest`, `WebSocket`, `Request` are undefined. `import(url)` returns a Promise that never resolves. Verified with 7 Burp Collaborator OOB vectors, unique subdomain per vector -- zero DNS hits. | **PASS.** Exceeds the requirement. Guideline allows local network; we allow nothing. |
| **(2) No arbitrary OS access** | "Restricted to transitive OS access provided under (3) and (4)." | No `process`, `child_process`, `os`, `require`, or `import('node:*')`. `eval('typeof process')` returns `"undefined"`. WASM linear memory is the entire world. | **PASS.** |
| **(3) No arbitrary filesystem** | "Restricted to defined working directory(ies)." | Zero filesystem access. No `fs`, no file handles. The WASM guest has no filesystem at all. | **PASS.** Exceeds the requirement. Guideline contemplates restricted directories; we give zero. |
| **(4) Controlled API access** | "Restricted to defined product APIs." "Progressively exposed based on user consent." | COM API exposed via host functions (`com_get`, `com_invoke`) gated by three-tier allowlist: `ALLOWED_SUB_OBJECTS` (9 objects), `ALLOWED_ROOT_METHODS` (21 methods), `DENIED_METHODS` (explicit blocklist). No progressive-consent UI -- all allowed APIs available immediately. | **PASS with noted gap.** Allowlist is tight, but "progressive exposure based on user consent" isn't implemented. Acceptable for v2 desktop where the user explicitly installs the server. Worth revisiting if this moves to a multi-tool agent environment. |

**Section 10 bottom line:** This is the strongest "code mode" implementation I'm aware of relative to these guidelines. The "lethal trifecta" is broken at the network leg -- adversarially tested and confirmed with live OOB exfil attempts.

---

## Controls 1-7: Applicability and Status

### Control 1 -- User-Context Authorization

| Guideline | What We Built | Verdict |
|---|---|---|
| "No independent MCP Host identity." "User token propagation." "Backend API is final authority." | openstaad-mcp doesn't call backend APIs -- it talks to local COM. No IMS token, no backend delegation chain. Auth is `--token` (static bearer) for HTTP transport, no auth for stdio. | **Not applicable (by design).** The guideline targets cloud MCP servers calling backend APIs. A local desktop server talking to a local COM process has no backend delegation chain. Out of scope, not non-compliant. |

### Control 2 -- Curated Tool Environment

| Guideline | What We Built | Verdict |
|---|---|---|
| "Centralized Discovery Service." "Third-party servers not supported." | Distributed as a `.mcpb` package installed directly by the user. No Discovery Service integration. | **Not applicable (yet).** Guideline targets cloud-hosted multi-server environments. For desktop distribution, the user making an explicit install decision is the "curated environment." Becomes relevant if STAAD.Pro gets cloud agent integration through a central registry. |

### Control 3 -- Two-Layer Sandboxing

| Layer | What We Built | Verdict |
|---|---|---|
| **Layer 1 (Server Sandboxing):** Process isolation, network restrictions, filesystem boundaries | MCP server runs as a standard Python process with user privileges. No container, no seccomp. Network restricted to loopback bind (127.0.0.1). | **Partial.** Server process is not sandboxed -- has full user privileges. Acceptable for single-user desktop (same trust zone as user). Doesn't match the guideline's container aspiration, but the guideline was written for cloud deployments. |
| **Layer 2 (Agent Capability Limitation):** Tool universe constraint, capability boundaries, parameter validation | Five MCP tools (`execute_code`, `list_instances`, `read_skills`, `get_connection_status`, `get_api_schema`). Only `execute_code` does writes. WASM sandbox constrains code to allowed COM surface. | **PASS.** Tool surface is minimal and well-defined. WASM sandbox is the capability boundary. |

### Control 4 -- Explicit Consent (THE GAP)

| Guideline | What We Built | Verdict |
|---|---|---|
| "Applications must implement an approval gate for operations that modify state." TCM `requiresUserApproval` field. | No consent gate at our layer. `execute_code` runs immediately when the agent calls it. No TCM metadata. | **Gap.** This is the clearest deviation from the guidelines. |

**Why this matters:** Every `execute_code` call that writes to the model executes without user approval. The agent is the confused deputy and currently has no gate. This is the architectural weak point the OMCP-009 adversarial tests exploit -- a PI payload in model data instructs the agent to call `execute_code` with sabotage code, and nothing stops it.

**Why it's not simple to fix:** `execute_code` is one tool that does both reads and writes. TCM `requiresUserApproval` is per-tool, not per-invocation. Setting it to `true` means prompting on every call. For an agent that calls `execute_code` 10-50 times per session, that's death by dialog. The hosts (Claude Desktop, VS Code) offer "allow for this conversation" which defeats the gate for PI attacks within that session -- exactly the scenario we proved.

**What would actually help:** Splitting the approval decision by what the code does. The allowlist already knows which COM methods are called. A "read vs write" classification on allowlist entries would let the sandbox return a `requires_confirmation` flag, which a smart host could use to gate only write-bearing calls. That's a v3 feature.

**For v2:** The honest posture is that consent relies on whatever the host provides, session-level "always allow" is the realistic UX, and PI payloads in model data can ride that approval. OMCP-009 remains an accepted risk, documented and adversarially tested.

### Control 5 -- Runtime Monitoring

| Guideline | What We Built | Verdict |
|---|---|---|
| Behavioral baseline, execution monitoring, rate limiting, audit logging | 30s timeout, 128 MiB memory cap, 256 KiB console output cap. No rate limiting, no audit log, no behavioral baseline beyond resource limits. | **Partial.** Resource limits are in place (OMCP-007 fix). No audit trail or anomaly detection. The guideline itself acknowledges "client-side/desktop logs are NOT tamper-proof." Acceptable for desktop v2. Needs work if this server moves to shared/cloud deployment. |

### Control 6 (LLM Gateway) and Control 7 (Input Parameterization)

| Guideline | What We Built | Verdict |
|---|---|---|
| Central gateway for guardrails. Separate instructions from data. | Not applicable. openstaad-mcp is a tool server, not an LLM gateway. It doesn't see prompts or manage LLM traffic. | **Out of scope.** These controls apply to the host/agent layer, not the MCP server. |

---

## OWASP LLM Threat Matrix Cross-Check

| Threat | Status |
|---|---|
| **LLM01 -- Indirect Prompt Injection** | **Confirmed risk (OMCP-009).** 42 adversarial tests prove payloads flow through COM round-trip. Sandbox blocks code-level exploitation. Agent-behavior manipulation is unmitigated at our layer -- accepted risk, documented. |
| **LLM02 -- SSRF via Insecure Output Handling** | **Mitigated by sandbox.** No network from WASM. `OpenSTAADFile` with UNC path is the closest SSRF analog -- it reaches COM but crashes STAAD (DoS, not exfil). |
| **Malicious Code Execution (4.2.1 #4)** | **Mitigated.** WASM isolation. Prototype pollution works but is non-persistent. eval/Function available but `process`/`require` are not. |
| **Token Theft (4.2.1 #5)** | **Low risk for desktop.** Static bearer token in CLI args (OMCP-012, accepted). No IMS tokens in play. |
| **Excessive Permissions (4.2.2 #8)** | **Mitigated by allowlist.** 9 sub-objects, 21 root methods, 1 denied method. Surface area audited and documented. |

---

## Summary Scorecard

| Control | Applicability | Status |
|---|---|---|
| Section 10: Code Mode (1) Network | **Direct** | **PASS** -- zero network, Collaborator-verified |
| Section 10: Code Mode (2) OS Access | **Direct** | **PASS** -- zero OS access |
| Section 10: Code Mode (3) Filesystem | **Direct** | **PASS** -- zero filesystem |
| Section 10: Code Mode (4) API Access | **Direct** | **PASS** -- allowlisted COM, no progressive consent |
| Control 1: User-Context AuthZ | Not applicable (local COM) | N/A |
| Control 2: Curated Environment | Not applicable (desktop) | N/A |
| Control 3: Two-Layer Sandboxing | Partially applicable | Layer 1: partial (no container), Layer 2: pass |
| Control 4: Explicit Consent | **Applicable** | **GAP** -- no consent gate on execute_code |
| Control 5: Runtime Monitoring | Partially applicable | Partial -- resource limits yes, audit/rate-limit no |
| Control 6: LLM Gateway | Not applicable | N/A |
| Control 7: Input Parameterization | Not applicable | N/A |

---

## Recommendations

1. **When TCM spec ships:** Declare `execute_code` as `requiresUserApproval: true`. It's a blunt instrument (prompts on every call), but it's the correct metadata declaration and leaves the UX problem to hosts.

2. **v3 consideration:** Read/write classification on the COM allowlist. Let the sandbox distinguish read-only calls from write calls and surface that in tool responses. This would let a smart host auto-approve reads and gate only writes.

3. **If this moves to cloud:** Control 5 (audit logging, rate limiting) and Control 3 Layer 1 (container isolation) become real requirements, not nice-to-haves.

4. **No action needed for v2 release.** The gaps are documented, the risks are accepted with test evidence, and the implementation exceeds the "code mode" isolation spec on every dimension that matters for a desktop deployment.

--Dave
