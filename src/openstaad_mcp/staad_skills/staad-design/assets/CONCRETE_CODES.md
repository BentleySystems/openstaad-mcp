# Concrete Design Codes Reference

Code numbers for `design.CreateDesignBrief(codeNumber)`.

## Common Concrete Codes

| Code | Standard |
|------|----------|
| 2001 | ACI 318-19 |
| 2010 | ACI 318-14 |
| 2004 | ACI 318-05 |
| 2020 | BS EN 1992-1-1:2004 (Eurocode 2) |
| 2030 | IS 456:2000 |
| 2005 | BS 8110-1:1997 |
| 2015 | CSA A23.3-14 |
| 2025 | AS 3600:2018 |

## Concrete Design Parameters

| Parameter | Description | Example Value |
|-----------|-------------|---------------|
| FC | Concrete compressive strength (f'c) | "30" (MPa) |
| FYMAIN | Main reinforcement yield strength | "415" (MPa) |
| FYSEC | Secondary reinforcement yield strength | "415" (MPa) |
| CLT | Clear cover top | "40" (mm) |
| CLB | Clear cover bottom | "40" (mm) |
| CLS | Clear cover side | "40" (mm) |
| MINMAIN | Minimum main bar size | "12" (mm) |
| MAXMAIN | Maximum main bar size | "32" (mm) |
| TRACK | Output detail level | "2" |
| BRESSION | Biaxial bending check | "1" |
| EFACE | Exposure face (for crack width) | "1" |
| SFACE | Start face distance | "0" |

## Reading Concrete Design Results

**No COM methods exist for concrete design results.** Use the `read_analysis_output` MCP tool:

```
read_analysis_output(file_type="anl")
```

The `.ANL` file contains:
- Member-by-member design status (PASS/FAIL)
- Required reinforcement areas (top/bottom/shear)
- Critical load case and governing clause
- Interaction ratios for columns
- Crack width calculations (where applicable)

## Concrete Design Workflow Notes

1. Use **repeat loads** (not combinations) for factored cases — see `staad-loading` skill
2. Concrete sections must be rectangular or T-shaped (assigned via Property)
3. The design brief must specify concrete-specific parameters (FC, FYMAIN, etc.)
4. Always run `AnalyzeEx(1, 0, 1)` — not `AnalyzeModel`
5. After analysis, call `read_analysis_output` to get results
