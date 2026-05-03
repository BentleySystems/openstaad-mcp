---
name: staad-steel-design
description: 'Use when performing steel member design, code checking, computing utilization ratios, optimizing sections, or verifying member capacity against a design code. Covers: AISC 360-16 (code 1067), AISC 360-05 (code 1045), Eurocode 3 (code 1220), IS 800 (code 1032), CreateDesignBrief, AssignDesignCommand (CHECK CODE, SELECT, TAKE OFF), AssignDesignParameter (BEAM, KY, KZ, CB, FYLD, DMAX, DMIN, TRACK), AssignDesignGroup, AnalyzeEx (use instead of AnalyzeModel for design), GetMemberSteelDesignResults (returns tuple with status/ratio/clause/section), GetMemberSteelDesignRatio, GetMemberSteelDesignMaxFailureRatio, multi-block results. Requires staad-core.'
---

# STAAD.Pro Steel Design

## Instructions

- Define the shorthand once per script: `design = staad.Design`

### Design Workflow — 5 Steps

**Step 1 — Create design brief**
```python
brief_ref = design.CreateDesignBrief(1067)  # AISC 360-16
```

| Code | Standard |
|------|----------|
| 1067 | AISC 360-16 |
| 1061 | AISC 360-10 |
| 1045 | AISC 360-05 |
| 1004 | BS 5950-1:2000 |
| 1220 | BS EN 1993-1-1 (Eurocode 3) |
| 1032 | IS 800 2007 LSD |
| 1149 | AS 4100 |
| 1182 | CSA S16-14 |

**Step 2 — Assign design commands to members**
```python
result = design.AssignDesignCommand(brief_ref, 'CHECK CODE', '', beam_list)
# Returns 0 on success — always print and check
```

| Command | Description |
|---------|-------------|
| CHECK CODE | Verify member capacity against the code |
| SELECT | Optimize section (pick the lightest passing section) |
| TAKE OFF | Generate material take-off report |

**Step 3 — Save to persist design commands**
```python
staad.SaveModel(True)
```

**Step 4 — Run analysis + design**
```python
staad.SetSilentMode(True)
status = staad.AnalyzeEx(1, 0, 1)   # silentMode=1, hiddenMode=0, waitTillComplete=1
staad.SetSilentMode(False)
# status == 2 means success
```

**Step 5 — Read results**
```python
out = staad.Output
# Verify first
blk_count = out.GetSteelDesignParameterBlockCount()   # must be > 0

# Per-member full results
r = out.GetMemberSteelDesignResults(bid)
# Returns: (codeName, status, ratio, allowable, critLC, critPos, clause, section, forces[FX,MY,MZ], klr)
# status: 'PASS' or 'FAIL'; ratio > 1.0 = failure

# Quick ratio only
ratio = out.GetMemberSteelDesignRatio(bid)  # -999=not designed, -1=no analysis

# Model-wide extremes
max_r = out.GetMemberSteelDesignMaxFailureRatio()
min_r = out.GetMemberSteelDesignMinFailureRatio()
```

### Design Parameters
Assign parameters before running analysis:
```python
design.AssignDesignParameter(brief_ref, paramName, paramValue, member_ids)
```

| Parameter | Description | Example |
|-----------|-------------|---------|
| BEAM | Member is a beam | "1" |
| FYLD | Yield strength | "250" (MPa) |
| FU | Ultimate strength | "400" (MPa) |
| KY | Effective length factor Y | "0.85" |
| KZ | Effective length factor Z | "1.0" |
| LY | Unbraced length Y | "3000" (mm) |
| LZ | Unbraced length Z | "3000" (mm) |
| CB | Bending coefficient | "1.0" |
| UNL | Unsupported length | "6000" (mm) |
| TRACK | Output detail level | "2" |
| DMAX | Maximum section depth | "600" (mm) |
| DMIN | Minimum section depth | "200" (mm) |

### Design Groups
Group members to use the same section during optimization:
```python
design.AssignDesignGroup(brief_ref, 'scSteelGroup', 'ColumnGroup', sameAsMember=1, member_ids=[1,2,3])
```

### Querying Design Parameters
```python
params = design.GetMemberDesignParameters(brief_ref, memberNo)
# Returns dict with status, count, parameters
```

### Section Mapping (before design runs)
```python
beam_to_section = {}
for sid in list(prop.GetSectionPropertyList()):
    name = prop.GetSectionPropertyName(sid)
    for bid in list(prop.GetSectionPropertyAssignedBeamList(sid)):
        beam_to_section[bid] = name
```

## Example
See [aisc360-design.py](./scripts/aisc360-design.py) for a complete working example.

## Gotchas
- Use `AnalyzeEx(1, 0, 1)` not AnalyzeModel — only `AnalyzeEx` triggers design
- `GetSteelDesignParameterBlockCount()` returns `0` until `AnalyzeEx` completes
- `AssignDesignCommand` returns non-zero on failure — always check the return value
- `GetMemberSteelDesignResults` raises an error for members not assigned `CHECK CODE`
- Design section in results may differ from table section if the optimizer re-selected
- Parameter values are passed as **strings** to `AssignDesignParameter`
