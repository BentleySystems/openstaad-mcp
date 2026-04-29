---
name: staad-design
description: 'Use when performing member design for any material: steel, concrete, timber, or aluminum. Covers: CreateDesignBrief (code-specific), AssignDesignCommand (CHECK CODE, SELECT, TAKE OFF), AssignDesignParameter (material-specific parameters), AssignDesignGroup, AnalyzeEx (use instead of AnalyzeModel for design). Steel results via COM Output methods; concrete/timber/aluminum results via read_analysis_output tool. Load asset files for material-specific codes and parameters. Requires staad-core.'
---

# STAAD.Pro Design — All Materials

## Instructions

- Define shorthands: `const design = staad.Design;`, `const out = staad.Output;`
- This skill covers steel, concrete, timber, and aluminum design
- The workflow is the same for all materials — only codes, parameters, and result access differ
- Load the material-specific asset file for code numbers and parameter tables

### Design Workflow — 5 Steps (All Materials)

**Step 1 — Create design brief**
```javascript
const briefRef = design.CreateDesignBrief(designCode);
// designCode: see material-specific asset files for code numbers
```

**Step 2 — Assign design commands to members**
```javascript
design.AssignDesignCommand(briefRef, 'CHECK CODE', '', memberList);
// Returns 0 on success — always log and check
```

| Command | Description |
|---------|-------------|
| CHECK CODE | Verify member capacity against the code |
| SELECT | Optimize section (pick lightest passing section) — steel only |
| TAKE OFF | Generate material take-off report |

**Step 3 — Assign parameters (material-specific)**
```javascript
design.AssignDesignParameter(briefRef, paramName, paramValue, memberIds);
// paramName and paramValue are strings — see asset files for each material
```

**Step 4 — Save and run analysis + design**
```javascript
staad.SaveModel(true);
staad.SetSilentMode(true);
const status = staad.AnalyzeEx(1, 0, 1);  // silent, visible, waitTillComplete
staad.SetSilentMode(false);
// status: 2=OK, 3=warnings (usually still valid), 4=errors
```

**Step 5 — Read results**

Results access differs by material:

| Material | How to read results |
|----------|-------------------|
| **Steel** | COM Output methods: `out.GetMemberSteelDesignResults(bid)` — see [STEEL_RESULTS.md](./assets/STEEL_RESULTS.md) |
| **Concrete** | `read_analysis_output` tool (file_type="anl") — no COM methods exist for concrete results |
| **Timber** | `read_analysis_output` tool (file_type="anl") — no COM methods exist for timber results |
| **Aluminum** | `read_analysis_output` tool (file_type="anl") — no COM methods exist for aluminum results |

For non-steel materials, call the `read_analysis_output` MCP tool after analysis completes. The `.ANL` file contains full design results including pass/fail status, critical ratios, reinforcement details (concrete), and governing clauses.

### Design Groups
Group members to use the same section during optimization (steel SELECT command):
```javascript
design.AssignDesignGroup(briefRef, 'scSteelGroup', 'GroupName', sameAsMember, memberIds);
```

### Querying Design Setup
```javascript
const code = design.GetDesignBriefCode(briefRef);
const params = design.GetMemberDesignParameters(briefRef, memberNo);
```

### Repeat Loads for Design
Design codes require factored load cases. Use `AddRepeatLoad` (not `CreateNewLoadCombination`) to create analyzable factored cases:
```javascript
const load = staad.Load;
const lc = load.CreateNewPrimaryLoad('1.2D + 1.5L');
load.SetLoadActive(lc);
load.AddRepeatLoad([deadLC, liveLC], [1.2, 1.5]);
```
See the staad-loading skill for full repeat load documentation.

## Material-Specific References

Load the relevant asset file via `read_skills` for code numbers and parameter tables:

- **Steel**: `staad-design/assets/STEEL_CODES` and `staad-design/assets/STEEL_RESULTS`
- **Concrete**: `staad-design/assets/CONCRETE_CODES`
- **Timber**: `staad-design/assets/TIMBER_CODES`
- **Aluminum**: `staad-design/assets/ALUMINUM_CODES`

## Gotchas
- Use `AnalyzeEx(1, 0, 1)` not `AnalyzeModel` — only `AnalyzeEx` triggers design
- `AssignDesignCommand` returns non-zero on failure — always check the return value
- Parameter values are passed as **strings** to `AssignDesignParameter`
- Concrete/timber/aluminum design results are NOT available via COM — use `read_analysis_output`
- For concrete design, ensure repeat loads (not combinations) are used for factored cases
- Status 3 from `AnalyzeEx` (warnings) usually still produces valid design results — check `read_analysis_output`
