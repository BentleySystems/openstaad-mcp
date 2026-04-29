# Timber Design Codes Reference

Code numbers for `design.CreateDesignBrief(codeNumber)`.

## Timber Design Codes

| Code | Standard |
|------|----------|
| 3001 | NDS 2018 (US) |
| 3005 | NDS 2015 (US) |
| 3010 | BS EN 1995-1-1:2004 (Eurocode 5) |
| 3015 | CSA O86-14 (Canada) |
| 3020 | AS 1720.1:2010 (Australia) |
| 3025 | IS 883:1994 (India) |

## Timber Design Parameters

| Parameter | Description | Example Value |
|-----------|-------------|---------------|
| DUR | Load duration factor | "1.0" |
| CM | Wet service factor | "1.0" |
| CT | Temperature factor | "1.0" |
| CF | Size factor | "1.0" |
| CL | Beam stability factor | "1.0" |
| CP | Column stability factor | "1.0" |
| FB | Allowable bending stress | "10" (MPa) |
| FV | Allowable shear stress | "1.5" (MPa) |
| FC | Allowable compression stress | "8" (MPa) |
| E | Modulus of elasticity | "12000" (MPa) |
| TRACK | Output detail level | "2" |

## Reading Timber Design Results

**No COM methods exist for timber design results.** Use the `read_analysis_output` MCP tool:

```
read_analysis_output(file_type="anl")
```

The `.ANL` file contains:
- Member-by-member pass/fail status
- Utilization ratios for bending, shear, and combined stresses
- Governing load case and code clause
- Section adequacy checks

## Notes
- Timber sections must be rectangular (standard lumber or glulam dimensions)
- Use repeat loads for factored design cases
- Always run `AnalyzeEx(1, 0, 1)` for design
