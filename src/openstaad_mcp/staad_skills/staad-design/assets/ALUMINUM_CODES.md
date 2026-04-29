# Aluminum Design Codes Reference

Code numbers for `design.CreateDesignBrief(codeNumber)`.

## Aluminum Design Codes

| Code | Standard |
|------|----------|
| 4001 | ADM 2015 (Aluminum Design Manual — US) |
| 4005 | ADM 2010 |
| 4010 | BS 8118-1:1991 (UK) |
| 4015 | BS EN 1999-1-1:2007 (Eurocode 9) |

## Aluminum Design Parameters

| Parameter | Description | Example Value |
|-----------|-------------|---------------|
| FYLD | Yield strength (alloy-dependent) | "170" (MPa) |
| FU | Ultimate tensile strength | "200" (MPa) |
| KY | Effective length factor Y | "1.0" |
| KZ | Effective length factor Z | "1.0" |
| UNL | Unsupported length | "3000" (mm) |
| CB | Bending coefficient | "1.0" |
| TRACK | Output detail level | "2" |
| DMAX | Maximum section depth | "300" (mm) |
| DMIN | Minimum section depth | "100" (mm) |
| ALLOY | Alloy designation | "6061-T6" |
| TEMPER | Temper designation | "T6" |
| WELD | Welded connection factor | "1" (1=welded, 0=unwelded) |

## Reading Aluminum Design Results

**No COM methods exist for aluminum design results.** Use the `read_analysis_output` MCP tool:

```
read_analysis_output(file_type="anl")
```

The `.ANL` file contains:
- Member-by-member pass/fail status
- Utilization ratios
- Critical load case and governing clause
- Buckling check results

## Notes
- Aluminum sections are typically extruded profiles
- Welded vs unwelded connections significantly affect capacity
- Use repeat loads for factored design cases
- Always run `AnalyzeEx(1, 0, 1)` for design
