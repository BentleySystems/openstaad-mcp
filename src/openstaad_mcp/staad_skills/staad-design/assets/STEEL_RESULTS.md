# Steel Design Results — COM Output Methods

Steel is the only material with full COM-based result access. All methods are on the `Output` sub-object.

## Quick Check Methods

```javascript
const out = staad.Output;

// Block count — must be > 0 after AnalyzeEx completes
const blocks = out.GetSteelDesignParameterBlockCount();

// Per-member ratio (quick)
const ratio = out.GetMemberSteelDesignRatio(beamId);
// Returns: ratio value; -999 = not designed; -1 = no analysis results

// Model-wide extremes
const maxRatio = out.GetMemberSteelDesignMaxFailureRatio();
const minRatio = out.GetMemberSteelDesignMinFailureRatio();
```

## Full Per-Member Results

```javascript
const r = out.GetMemberSteelDesignResults(beamId);
```

Returns an array:
| Index | Field | Description |
|-------|-------|-------------|
| 0 | codeName | Design code name string |
| 1 | status | `"PASS"` or `"FAIL"` |
| 2 | ratio | Utilization ratio (>1.0 = failure) |
| 3 | allowable | Allowable stress/capacity |
| 4 | critLC | Critical load case number |
| 5 | critPos | Critical position along member |
| 6 | clause | Governing code clause |
| 7 | section | Section name used for design |
| 8-10 | forces | `[FX, MY, MZ]` — critical forces |
| 11 | klr | Slenderness ratio |

## Multi-Block Results

For models with multiple design blocks:
```javascript
const blockCount = out.GetSteelDesignParameterBlockCount();
for (let b = 0; b < blockCount; b++) {
    const members = out.GetSteelDesignParameterBlockMemberList(b);
    for (const bid of members) {
        const r = out.GetMemberSteelDesignResults(bid);
        // ... process
    }
}
```

## Section Mapping (Pre-Design)

```javascript
const beamToSection = {};
for (const sid of prop.GetSectionPropertyList()) {
    const name = prop.GetSectionPropertyName(sid);
    for (const bid of prop.GetSectionPropertyAssignedBeamList(sid)) {
        beamToSection[bid] = name;
    }
}
```

## Gotchas
- `GetSteelDesignParameterBlockCount()` returns 0 until `AnalyzeEx` completes
- `GetMemberSteelDesignResults` throws for members not assigned CHECK CODE
- Design section in results may differ from assigned section if SELECT was used
- These methods work for **steel only** — concrete/timber/aluminum use `read_analysis_output`
