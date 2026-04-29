# Tool Capability Manifests — openstaad-mcp v2.0.0

Project-specific Tool Capability Manifests (TCMs) for the six MCP tools exposed by the OpenSTAAD MCP server. Generated per the
[TCM Specification](plan-research-support/Tool-Capability-Manifest-Specification.md)
from the Bentley MCP security architecture.

## Applicability notes

openstaad-mcp is a **local, single-user desktop tool** that bridges an AI agent to a running STAAD.Pro instance via COM. Several TCM fields are
designed for cloud/web scenarios and are adapted here:

| TCM field | Platform-MCP intent | openstaad-mcp adaptation |
|-----------|--------------------|-----------------------|
| `endpoint` | OAuth-protected HTTP API | Mapped to MCP transport (stdio or HTTP loopback). `audience` is `local://openstaad-mcp`. |
| `sandboxingDirectives.csp` | Browser Content Security Policy | N/A — no browser execution. Set to empty sandbox (maximum restriction). |
| `signature.jws` | Discovery Service trust chain | Placeholder — no Discovery Service in local deployment. Code-signed PyInstaller artifact provides integrity. |
| `sandboxingDirectives.networkPolicy` | Cloud network controls | Mapped to host-header allowlist (`HostHeaderMiddleware`) and loopback bind. |
| `securityMetadata.riskScore` | SRAB-assigned | Self-assessed for documentation; not enforced at runtime. |

## Tool Capability Matrix

| Tool | Category | User Approval | Side-Effect Scope | Risk | Isolation |
|------|----------|--------------|-------------------|------|-----------|
| `discover_api` | Read-Only | No | None | Low | process (Python) |
| `read_skills` | Read-Only | No | None (reads bundled files only) | Low | process (Python) |
| `list_instances` | Read-Only | No | None (enumerates COM ROT) | Low | process (Python) |
| `get_status` | Read-Only | No | None (reads COM properties) | Low | process (Python + COM thread) |
| `read_analysis_output` | Read-Only | No | None (reads local `.ANL`/`.LOG` file derived from open model) | Low | process (Python + COM thread) |
| `execute_code` | Data Modification | **Yes** | Backend data modification (STAAD model via COM) | Medium | **vm** (WASM isolate: Extism + QuickJS-ng + Wasmtime) |

---

## Individual manifests

### discover_api

```json
{
  "manifestVersion": "0.1.0",
  "version": "2.0.0",
  "spec": {
    "name": "discover_api",
    "description": "Discover available API guidance and skills. Call this before using other openstaad-mcp tools to understand the API surface and see what skills are available.",
    "inputSchema": {
      "type": "object",
      "properties": {},
      "required": []
    }
  },
  "capability": {
    "category": "Read-Only",
    "requiresUserApproval": false
  },
  "endpoint": {
    "verb": "GET",
    "path": "mcp://openstaad-mcp/discover_api",
    "audience": "local://openstaad-mcp"
  },
  "sandboxingDirectives": {
    "csp": {
      "sandbox": []
    },
    "networkPolicy": {
      "allowedHosts": [],
      "maxRequestsPerMinute": 60
    }
  },
  "signature": {
    "jws": "placeholder—integrity-via-code-signing"
  },
  "sandboxingRequirements": {
    "isolationLevel": "process",
    "networkPolicy": {
      "allowedHosts": []
    },
    "fileSystemAccess": {
      "readOnly": ["<install-dir>/openstaad_mcp/staad_skills/"],
      "readWrite": []
    }
  },
  "behavioralBaseline": {
    "maxExecutionTimeMs": 500,
    "expectedNetworkCalls": [],
    "maxResourceUsage": {
      "memory": "10MB",
      "cpu": 0.01
    }
  },
  "securityMetadata": {
    "riskScore": "low",
    "dataClassification": ["internal"]
  }
}
```

**Security notes:**
- Pure in-memory operation: scans the bundled `staad_skills/` directory for `SKILL.md` files and returns their names/descriptions.
- No COM interaction, no network access, no user-supplied file paths.

---

### read_skills

```json
{
  "manifestVersion": "0.1.0",
  "version": "2.0.0",
  "spec": {
    "name": "read_skills",
    "description": "Read one or more skills by name. Use discover_api first to list available skills. Each skill provides domain-specific guidance.",
    "inputSchema": {
      "type": "object",
      "required": ["skills"],
      "properties": {
        "skills": {
          "type": "array",
          "description": "Skill names or sub-paths to read",
          "items": {
            "type": "string",
            "maxLength": 256,
            "pattern": "^[a-zA-Z0-9_./-]+$"
          },
          "minItems": 1,
          "maxItems": 20
        }
      }
    }
  },
  "capability": {
    "category": "Read-Only",
    "requiresUserApproval": false
  },
  "endpoint": {
    "verb": "GET",
    "path": "mcp://openstaad-mcp/read_skills",
    "audience": "local://openstaad-mcp"
  },
  "sandboxingDirectives": {
    "csp": {
      "sandbox": []
    },
    "networkPolicy": {
      "allowedHosts": [],
      "maxRequestsPerMinute": 60
    }
  },
  "signature": {
    "jws": "placeholder—integrity-via-code-signing"
  },
  "sandboxingRequirements": {
    "isolationLevel": "process",
    "networkPolicy": {
      "allowedHosts": []
    },
    "fileSystemAccess": {
      "readOnly": ["<install-dir>/openstaad_mcp/staad_skills/"],
      "readWrite": []
    }
  },
  "behavioralBaseline": {
    "maxExecutionTimeMs": 1000,
    "expectedNetworkCalls": [],
    "maxResourceUsage": {
      "memory": "20MB",
      "cpu": 0.05
    }
  },
  "securityMetadata": {
    "riskScore": "low",
    "dataClassification": ["internal"]
  }
}
```

**Security notes:**
- Reads bundled skill files from `staad_skills/` only. Path traversal hardened: `Path.resolve()` + `is_relative_to()` containment check rejects `../` escapes.
- Input pattern constraint (`^[a-zA-Z0-9_./-]+$`) prevents null bytes, backslashes, and special characters.
- No COM interaction, no network access.

---

### list_instances

```json
{
  "manifestVersion": "0.1.0",
  "version": "2.0.0",
  "spec": {
    "name": "list_instances",
    "description": "List all running STAAD.Pro instances with alias, PID, open file path, and version.",
    "inputSchema": {
      "type": "object",
      "properties": {},
      "required": []
    }
  },
  "capability": {
    "category": "Read-Only",
    "requiresUserApproval": false
  },
  "endpoint": {
    "verb": "GET",
    "path": "mcp://openstaad-mcp/list_instances",
    "audience": "local://openstaad-mcp"
  },
  "sandboxingDirectives": {
    "csp": {
      "sandbox": []
    },
    "networkPolicy": {
      "allowedHosts": [],
      "maxRequestsPerMinute": 30
    }
  },
  "signature": {
    "jws": "placeholder—integrity-via-code-signing"
  },
  "sandboxingRequirements": {
    "isolationLevel": "process",
    "networkPolicy": {
      "allowedHosts": []
    },
    "fileSystemAccess": "none"
  },
  "behavioralBaseline": {
    "maxExecutionTimeMs": 2000,
    "expectedNetworkCalls": [],
    "maxResourceUsage": {
      "memory": "10MB",
      "cpu": 0.02
    }
  },
  "securityMetadata": {
    "riskScore": "low",
    "dataClassification": ["internal"]
  }
}
```

**Security notes:**
- Enumerates STAAD.Pro instances from the COM Running Object Table (ROT). Read-only COM access.
- Returns local file paths (model `.std` files) — classified as internal data. - No user-supplied parameters, no file I/O, no network access.

---

### get_status

```json
{
  "manifestVersion": "0.1.0",
  "version": "2.0.0",
  "spec": {
    "name": "get_status",
    "description": "Check the connection to a STAAD.Pro instance. Returns connection state, version, and model path.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "instance": {
          "type": "string",
          "description": "Alias from list_instances (e.g. staadPro1). Omit when only one instance is running.",
          "pattern": "^[a-zA-Z0-9_]+$",
          "maxLength": 64
        }
      }
    }
  },
  "capability": {
    "category": "Read-Only",
    "requiresUserApproval": false
  },
  "endpoint": {
    "verb": "GET",
    "path": "mcp://openstaad-mcp/get_status",
    "audience": "local://openstaad-mcp"
  },
  "sandboxingDirectives": {
    "csp": {
      "sandbox": []
    },
    "networkPolicy": {
      "allowedHosts": [],
      "maxRequestsPerMinute": 30
    }
  },
  "signature": {
    "jws": "placeholder—integrity-via-code-signing"
  },
  "sandboxingRequirements": {
    "isolationLevel": "process",
    "networkPolicy": {
      "allowedHosts": []
    },
    "fileSystemAccess": "none"
  },
  "behavioralBaseline": {
    "maxExecutionTimeMs": 10000,
    "expectedNetworkCalls": [],
    "maxResourceUsage": {
      "memory": "10MB",
      "cpu": 0.02
    }
  },
  "securityMetadata": {
    "riskScore": "low",
    "dataClassification": ["internal"]
  }
}
```

**Security notes:**
- Reads three COM properties (`GetApplicationVersion`, `IsAnalyzing`, `GetSTAADFile`). All read-only.
- COM call runs on a dedicated thread with a 10 s timeout (`connect_and_run` wrapper).
- Returns local file path (model `.std`) — classified as internal data.

---

### read_analysis_output

```json
{
  "manifestVersion": "0.1.0",
  "version": "2.0.0",
  "spec": {
    "name": "read_analysis_output",
    "description": "Read the analysis output file (.ANL) or solver log (.LOG) for the currently open model. Path is derived server-side from GetSTAADFile() -- no user-supplied path.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "file_type": {
          "type": "string",
          "description": "File type to read: 'anl' (analysis output) or 'log' (solver log)",
          "enum": ["anl", "log"],
          "default": "anl"
        },
        "instance": {
          "type": "string",
          "description": "Alias from list_instances (e.g. staadPro1). Omit when only one instance is running.",
          "pattern": "^[a-zA-Z0-9_]+$",
          "maxLength": 64
        }
      }
    }
  },
  "capability": {
    "category": "Read-Only",
    "requiresUserApproval": false
  },
  "endpoint": {
    "verb": "GET",
    "path": "mcp://openstaad-mcp/read_analysis_output",
    "audience": "local://openstaad-mcp"
  },
  "sandboxingDirectives": {
    "csp": {
      "sandbox": []
    },
    "networkPolicy": {
      "allowedHosts": [],
      "maxRequestsPerMinute": 10
    }
  },
  "signature": {
    "jws": "placeholder--integrity-via-code-signing"
  },
  "sandboxingRequirements": {
    "isolationLevel": "process",
    "networkPolicy": {
      "allowedHosts": []
    },
    "fileSystemAccess": {
      "readOnly": ["<model-dir>/*.ANL", "<model-dir>/*.LOG"],
      "readWrite": []
    }
  },
  "behavioralBaseline": {
    "maxExecutionTimeMs": 10000,
    "expectedNetworkCalls": [],
    "maxResourceUsage": {
      "memory": "20MB",
      "cpu": 0.05
    }
  },
  "securityMetadata": {
    "riskScore": "low",
    "dataClassification": ["internal"]
  }
}
```

**Security notes:**
- File path is derived server-side: calls `GetSTAADFile()` via COM and replaces the extension. No user-supplied path -- eliminates path traversal by design.
- Only reads `.ANL` or `.LOG` files co-located with the open model. The `file_type` parameter is validated against a two-value allowlist (`"anl"`, `"log"`).
- Output capped at 512 KiB. Truncation metadata returned when the file exceeds the cap.
- COM call runs on a dedicated thread with a 10 s timeout. - Returns file content as text -- may contain structural engineering data and model labels. Classified as internal data.
- **Prompt injection risk:** `.ANL` file content is generated by the STAAD solver and reflects model data (member names, load case names, etc.). If an attacker has planted prompt-injection payloads in the model, those payloads will appear in the returned text. Same accepted risk as `execute_code` COM output -- see OMCP-009.

---

### execute_code

```json
{
  "manifestVersion": "0.1.0",
  "version": "2.0.0",
  "spec": {
    "name": "execute_code",
    "description": "Execute JavaScript code against the OpenSTAAD API inside a WASM sandbox. The sandbox provides a pre-connected 'staad' object. Filesystem, network, and module imports are physically unreachable.",
    "inputSchema": {
      "type": "object",
      "required": ["code"],
      "properties": {
        "code": {
          "type": "string",
          "description": "JavaScript source code to execute",
          "maxLength": 262144
        },
        "instance": {
          "type": "string",
          "description": "Alias from list_instances (e.g. staadPro1). Omit when only one instance is running.",
          "pattern": "^[a-zA-Z0-9_]+$",
          "maxLength": 64
        }
      }
    }
  },
  "capability": {
    "category": "Data Modification",
    "requiresUserApproval": true
  },
  "endpoint": {
    "verb": "POST",
    "path": "mcp://openstaad-mcp/execute_code",
    "audience": "local://openstaad-mcp"
  },
  "sandboxingDirectives": {
    "csp": {
      "sandbox": []
    },
    "networkPolicy": {
      "allowedHosts": [],
      "maxRequestsPerMinute": 20
    }
  },
  "signature": {
    "jws": "placeholder—integrity-via-code-signing"
  },
  "sandboxingRequirements": {
    "isolationLevel": "vm",
    "allowedSystemCalls": [],
    "networkPolicy": {
      "allowedHosts": [],
      "blockedPorts": [0, 65535]
    },
    "fileSystemAccess": "none"
  },
  "behavioralBaseline": {
    "maxExecutionTimeMs": 30000,
    "expectedNetworkCalls": [],
    "maxResourceUsage": {
      "memory": "64MB",
      "cpu": 1.0
    }
  },
  "securityMetadata": {
    "riskScore": "medium",
    "dataClassification": ["internal", "confidential"]
  }
}
```

**Security notes:**

This is the only tool with a non-trivial security surface. It is the reason the WASM sandbox exists.

**Consent gate — defense-in-depth chain:**

Three layers enforce the consent gate, each independent:

1. **Pre-flight scan (server layer, before WASM).** The server scans the
   submitted JavaScript string for any method name in
   `ALL_DESTRUCTIVE_METHOD_NAMES`. If a match is found, the server calls `Context.elicit()` — a host-mediated confirmation dialog presented directly to the human. The LLM never sees or controls this dialog.
2. **Runtime sandbox (WASM layer).** Even if a destructive method name
   evades the string scan (e.g. via runtime construction), the WASM executor's host-function callbacks check `allow_destructive` and reject the COM call with an error the user must approve via the host dialog.
3. **UNC path rejection (always enforced).** Path arguments at positions
   defined in `PATH_ARGUMENT_INDICES` are checked for `\\` prefixes and rejected unconditionally — no consent flag overrides this.

The previous design used a `confirm_destructive_operations` boolean tool parameter that the LLM controlled. It self-confirmed by setting `true`
in the same call, completely bypassing the gate. MCP elicitation eliminates this class of bypass.

**Isolation (vm level):**
- User code runs inside a WebAssembly isolate: Extism plugin host → QuickJS-ng JS engine → Wasmtime runtime.
- Fresh plugin instance per call — no state leakage between invocations. - WASM linear memory is hardware-isolated by Wasmtime; memory corruption in QuickJS cannot escape the isolate.
- No filesystem, network, `eval()`, `Function()`, `import()`, `fetch()`, `XMLHttpRequest`, `WebSocket`, or `process` available to user code.
- **Runtime hardening (evaluator.js):** `Host.getFunctions()` neutered (returns `{}`), `Host.__hostFunctions` emptied, `Host.invokeFunc` wrapped to reject negative memory offsets (CFFI OverflowError DoS prevention — see OMCP-014), `fetch` explicitly set to `undefined`. Module-scope closures used by the COM Proxy remain intact.

**Resource limits:**
| Limit | Value | Enforcement |
|-------|-------|-------------|
| Wall-clock timeout | 30 s | Wasmtime epoch-based interruption (preemptive) + cooperative `assert_deadline()` in host functions |
| WASM memory | 64 MiB (1024 pages) | Extism manifest `memory.max_pages` → Wasmtime linear memory cap |
| Source code size | 256 KiB | Checked before plugin instantiation |
| stdout/stderr capture | 256 KiB | Truncated silently; execution continues |
| Concurrent COM threads | 20 | Process-wide semaphore; fail-fast `RuntimeError` at limit |

**COM API gating (defense-in-depth):**
| Layer | Control | Method count |
|-------|---------|-------------|
| Global deny list | `DENIED_METHODS` — blocks `SetStandardProfileDBFolder` on any handle | 1 |
| Root allowlist | `ALLOWED_ROOT_METHODS` — only these methods callable on handle 0 | 23 |
| Sub-object name allowlist | `ALLOWED_SUB_OBJECTS` — only these 9 names via `com_get` | 9 |
| Sub-object method allowlists | `ALLOWED_SUB_OBJECT_METHODS` — per-object frozensets, deny-by-default | 695 across 9 objects |
| Consent gate | `DESTRUCTIVE_METHODS` — filesystem-write and session-destructive methods blocked unless user approves via MCP elicitation | 9 (5 root + 1 View + 3 Table) |
| UNC path validation | `PATH_ARGUMENT_INDICES` — path arguments checked for `\\` prefix; always rejected | 3 methods validated |

**Residual risks (accepted):**
- **Indirect prompt injection via COM output.** COM return values (which may contain prompt-injection payloads planted in model data) flow to the AI agent unsanitized. This is an accepted risk -- the blast radius is contained by the WASM sandbox (no network exfiltration), COM allowlists (deny-by-default API surface), and the consent gate (filesystem writes need human approval). Output sanitization was evaluated and rejected: it belongs at the Host/Gateway layer (Controls 6 and 7), not the MCP server, and any server-side blocklist would be an arms race against evolving model delimiters. Engineering HITL review and the improving robustness of modern LLMs further reduce the practical impact. For the full risk analysis, see [Prompt Injection Risk Commentary](prompt-injection-risk.md).
- **UNC path modal dialogs.** `OpenSTAADFile` with a UNC path can trigger a blocking STAAD modal dialog (nuisance, not a crash). The consent gate blocks this by default; UNC paths are always rejected even with the flag.

---

## Maintenance

Re-generate `execute_code` COM gating counts when:
- `ALLOWED_ROOT_METHODS` or `ALLOWED_SUB_OBJECT_METHODS` change in `constants.py` - STAAD.Pro major version upgrade (run `enumerate-com-api.py --generate-allowlist`)

Security architecture control mapping and § 10 "Code Mode" traceability are maintained in [`plan.md`](plan.md).

Last updated: 2026-04-27 (v2.0.0).
