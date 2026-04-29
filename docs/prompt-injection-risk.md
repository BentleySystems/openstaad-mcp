# Prompt Injection Risk Commentary -- openstaad-mcp

## What this document is

A standalone risk commentary on indirect prompt injection (OWASP LLM01) as it applies to openstaad-mcp v2.0.0. This is the place we lay out the threat, what we did about it, what we deliberately chose not to do, and why we think the residual risk is acceptable.

Cross-references:
- Security architecture: [security-architecture.md](plan-research-support/security-architecture.md) sections 4.1, 4.2.2, Controls 3/4/7
- TCM: [tool-capability-manifests.md](tool-capability-manifests.md) (residual risks, Control 7 row)
- Adversarial tests: `tests/adversarial/test_prompt_injection.py`, `tests/adversarial/test_modern_prompt_injection.py`

Last updated: 2026-04-27.

---

## 1. The threat

An attacker embeds prompt injection payloads inside a STAAD.Pro model file (.std). Load case titles, member unique IDs, group names, and comments are all viable carriers. The payloads are invisible or near-invisible in the STAAD GUI.

When a structural engineer opens the file and asks their AI agent to analyze the model, the agent calls `execute_code`, reads model data via COM, and the payloads land unsanitized in the agent's context. The agent may then follow the injected instructions -- planning tool calls the user did not ask for, disclosing information from its context, or sabotaging the analysis with plausible-looking but wrong modifications.

This is textbook indirect prompt injection per OWASP LLM01. It is a real vector and we have confirmed it end-to-end.

## 2. What we confirmed with testing

We ran 41 adversarial tests (30 modern PI + 11 classic) against a live STAAD.Pro instance. The tests cover the full attack chain: payload planted in model via COM, saved to disk, read back through COM, and returned to the agent.

**Payload categories tested:**

- LLM delimiter injection (OpenAI `<|im_start|>`, Anthropic `Human:`/`Assistant:`, Llama `[INST]`)
- Fake tool output and fake error messages with "fix" instructions
- Social engineering via plausible structural engineering commentary
- Split payloads reassembled across multiple load case titles
- Unicode tricks (zero-width chars, RTL overrides, Cyrillic homoglyphs)
- UNC path injection disguised as backup/recovery instructions
- Fake Bentley security advisories recommending sabotage

**Key findings:**

1. **All 19 PI payloads survive the full round-trip** through COM and arrive in the agent context verbatim. The vector is confirmed.
2. **STAAD's COM layer strips all non-ASCII Unicode** during the IDispatch round-trip, replacing it with `?`. This is a natural defense against Unicode-based PI tricks (zero-width chars, homoglyphs, RTL overrides) -- though it is not something we control or can rely on long-term.
3. **Zero network exfiltration.** 7 outbound vectors tested with Burp Collaborator (unique subdomain per vector). Zero DNS hits. `fetch()`, `XMLHttpRequest`, `WebSocket`, `import()`, `eval()+fetch`, `new Request()` -- all physically blocked by the WASM sandbox.
4. **Zero code-level exploitation.** `require('child_process')`, file reads, process spawning, inner WASM instantiation, `eval()`, `Function()` constructor -- all blocked.

## 3. What we built to contain the blast radius

We cannot prevent prompt injection payloads from reaching the agent -- that is the nature of a tool that reads external data. What we can do is limit what the agent is able to do if it follows injected instructions.

### 3.1. WASM sandbox (Control 3, Layer 1)

LLM-generated code runs inside a WebAssembly isolate (Extism + QuickJS-ng + Wasmtime). No filesystem, no network, no OS access. Even if a PI payload tricks the agent into writing malicious JavaScript, the sandbox physically cannot reach anything outside WASM linear memory.

### 3.2. COM allowlists (Control 3, Layer 2)

The COM API surface is deny-by-default. 23 root methods, 9 sub-objects, 695 sub-object methods -- all explicitly enumerated. Anything not in the allowlist is rejected before `getattr` fires. `DENIED_METHODS` blocks known-dangerous methods unconditionally.

This matters because the most realistic PI attack is not a sandbox escape -- it is the agent calling legitimate COM methods with bad intent (e.g. reassigning every beam to an incorrect section, or opening a UNC path). The allowlists limit the surface available for that kind of misuse.

### 3.3. Consent gate (Control 4)

Methods that write to the filesystem or modify the STAAD session (`NewSTAADFile`, `SaveModel`, `ExportView`, `Quit`, etc.) are blocked unless the user explicitly approves via MCP elicitation -- a host-mediated dialog the LLM cannot see or self-confirm.

This is the critical PI defense for this product. Even if a payload tricks the agent into calling `SaveModel` or `OpenSTAADFile` with a malicious path, the consent gate stops it. The user sees exactly what the agent wants to do and must approve it.

We previously used a `confirm_destructive_operations` boolean parameter on the tool itself. The LLM could (and did) self-confirm by setting `true` in the same call, completely bypassing the gate. MCP elicitation eliminates this class of bypass.

### 3.4. UNC path rejection (always enforced)

Path arguments to methods like `NewSTAADFile`, `OpenSTAADFile`, and `ExportView` are checked for `\\` prefixes and rejected unconditionally. No consent flag overrides this. This blocks the NTLM relay vector that PI payloads commonly try to exploit.

## 4. What we chose not to do (and why)

### 4.1. Output sanitization

The original audit fix recommendation was to "strip or escape control characters and known prompt injection markers from output data." We considered this and rejected it.

The reason: any useful sanitizer needs semantic understanding of what the agent will do with the content. Stripping `<|im_start|>` handles one model family. Stripping `[INST]` handles another. The next model family will use different delimiters, and we are back to a blocklist arms race that we will always lose.

The security architecture assigns PI filtering to the Host and Gateway layers (Controls 6 and 7), not the MCP server. An MCP server is a data conduit -- it should faithfully relay what the COM API returns. The agent's system prompt, the host application's tool-use policy, and the LLM gateway's injection detection are the right places to handle this.

Practically: if we started mangling COM output, we would break legitimate engineering data that happens to contain angle brackets or keywords. That is worse than the problem we are trying to solve.

### 4.2. Output length limits on individual fields

The 256 KiB stdout cap already limits output-flooding attacks as a side effect. Capping individual `result` values further would break legitimate large query results (e.g. `GetNodeCoordinates` for a large model). Not worth the breakage for marginal PI benefit.

## 5. Why the residual risk is acceptable

Three arguments, each independent:

### 5.1. The threat model has not actually changed

A tampered STAAD file could already contain incorrect section sizes, wrong load values, missing supports, or bogus material properties. This has always been a risk in structural engineering. The industry mitigates it with human-in-the-loop review: a licensed Professional Engineer signs off on the analysis output before anything gets built. No responsible engineering firm builds from unreviewed STAAD output, regardless of whether an AI agent was involved.

Prompt injection does not give an attacker a new capability -- it gives them a new delivery mechanism for a class of sabotage that was already possible. The existing engineering workflow (HITL review, PE sign-off) is the correct mitigation for that class.

### 5.2. The blast radius is contained on the user's machine

Even if PI succeeds in manipulating the agent's behavior, what can the agent actually do? It can call the six MCP tools we expose, subject to:

- WASM sandbox: no FS, no network, no OS access from user code
- COM allowlists: only audited methods, deny-by-default
- Consent gate: filesystem writes and session changes need human approval
- UNC rejection: NTLM relay paths always blocked

The agent cannot exfiltrate data (no network from sandbox), cannot execute arbitrary OS commands (no process spawning), and cannot silently modify files (consent gate). The worst realistic outcome is that the agent makes incorrect COM calls that modify the in-memory model -- which the user can see, undo, or discard.

### 5.3. LLM robustness is improving rapidly

Modern LLMs are getting significantly better at recognizing and refusing prompt injection attempts. The trajectory of model safety research (instruction hierarchy, input/output tagging, injection-aware training data) means that the severity of this vector decreases with each model generation. We do not need to solve PI at the MCP server layer because the LLM layer is converging on solving it.

This is not a reason to be complacent -- we still test for it, we still document it, and we still maintain the containment controls. But it does mean that investing in server-side output sanitization today would be building a defense against an attack surface that is shrinking on its own.

## 6. Recommendations for host applications

If you are integrating openstaad-mcp into a host application, you should be aware that COM return values are unsanitized and may contain prompt injection payloads from malicious model files. Mitigations you should consider at your layer:

1. **System prompt guidance.** Tell the agent that `execute_code` output may contain untrusted data from external model files and should not be interpreted as instructions.
2. **Tool-use policy.** Restrict which tools the agent can chain after reading model data. If the agent just read member names, it should not be planning filesystem operations.
3. **Gateway-level PI detection.** If you run an LLM gateway (Control 6), enable injection detection on the tool-output-to-agent path.
4. **Human-in-the-loop.** For high-consequence operations, require user confirmation at the host level in addition to the MCP server's consent gate.

## 7. Summary

| Aspect | Status |
|--------|--------|
| Vector confirmed | Yes -- 19 payloads survive full COM round-trip |
| Network exfiltration | Blocked (7 vectors, 0 DNS hits) |
| Code-level exploitation | Blocked (WASM sandbox) |
| Filesystem writes via PI | Blocked (consent gate + UNC rejection) |
| Agent behavior manipulation | Possible -- accepted risk |
| Output sanitization | Rejected (wrong layer, blocklist arms race) |
| Existing mitigation | Engineering HITL review, PE sign-off |
| Trend | LLM robustness improving; risk decreasing |
| Adversarial test coverage | 41 tests (30 modern + 11 classic) |
| Finding | Indirect prompt injection via COM output, severity Medium, CVSS 5.5 |
