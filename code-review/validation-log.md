# Validation Log -- OPENSTAAD-MCP

## False Positives Removed

| # | Original ID | Title | Reason | AI Error Type |
|---|-------------|-------|--------|---------------|
| 1 | OMCP-011 | AST Validation Bypass via ast.unparse() Round-Trip Gap | No concrete exploit exists; Gate 4 (PoC) fails -- the finding is purely theoretical with no known ast.unparse() edge case that produces a security-relevant semantic change. The `__result__` variable introduction is benign (simple assignment). | Incorrect assumption |

## Detailed False Positive Analysis

### OMCP-011: AST Validation Bypass via ast.unparse() Round-Trip Gap
- **Why AI flagged it**: The original audit noted that `validate_code()` validates the original source, then `capture_last_expr()` rewrites the code via `ast.unparse()`, and the rewritten code is executed without re-validation. The `__result__` dunder name introduced by the rewrite would be rejected by the validator if submitted directly. Historical `ast.unparse()` edge cases (CPython bpo-44896) were cited as theoretical risk.
- **What was actually found**: The code gap is real -- validated code differs from executed code. However: (1) `__result__` is a simple variable assignment that grants no new capabilities; (2) no known `ast.unparse()` edge case in Python 3.11+ produces semantically different code in a security-relevant way; (3) `ast.unparse()` is well-tested in CPython and the bpo-44896 issue was specific to f-strings and was fixed; (4) the rewrite only modifies the last expression to `__result__ = <expr>`, which cannot introduce new dangerous constructs.
- **Specific error**: AI assumed that because validated code != executed code, an exploit must be possible. This is pattern recognition ("looks dangerous") not analysis. No concrete attack path was demonstrated or even hypothesized beyond hand-waving at historical ast bugs.
- **Existing mitigation**: The rewrite is minimal (only the last expression) and well-bounded. The `ast.parse()` -> `ast.unparse()` round-trip is used in many production tools. Python 3.11+ resolved known edge cases.
- **FP checklist items that apply**: #1 (trace full validation chain -- the rewrite is safe), #10 (pattern recognition not analysis), #12 (theoretical vs real impact)
- **Note**: The code improvement suggestion (compile AST directly instead of unparsing) remains valid as defense-in-depth and is preserved in the validated todo file.

## Severity Downgrades

| # | ID | Title | Original Severity | New Severity | Reason |
|---|-----|-------|-------------------|--------------|--------|
| 1 | OMCP-010 | Documented Sec-Fetch-Site SecurityMiddleware Not Implemented | Medium | Informational | Defense-in-depth gap only. The primary DNS rebinding protection (TransportSecurityMiddleware) is provided by the FastMCP SDK (>=3.2.3). Missing Sec-Fetch-Site filtering is a secondary control. Gate 3 (Real Impact) fails -- no evidence that the SDK's protection is insufficient to warrant a Medium finding. The documentation mismatch is real but does not create a directly exploitable vulnerability. |

## Renumbering

| Validated ID | Original Merged ID | Change |
|-------------|-------------------|--------|
| OMCP-001 | OMCP-001 | No change |
| OMCP-002 | OMCP-002 | No change |
| OMCP-003 | OMCP-003 | No change |
| OMCP-004 | OMCP-004 | No change |
| OMCP-005 | OMCP-005 | No change |
| OMCP-006 | OMCP-006 | No change |
| OMCP-007 | OMCP-007 | No change |
| OMCP-008 | OMCP-008 | No change |
| OMCP-009 | OMCP-009 | No change |
| OMCP-010 | OMCP-010 | Downgraded to Informational |
| OMCP-011 | OMCP-012 | Renumbered (OMCP-011 removed as FP) |
| OMCP-012 | OMCP-013 | Renumbered |

## Validation Summary

| Metric | Value |
|--------|-------|
| Total merged findings reviewed | 13 |
| Confirmed | 10 |
| Informational (downgraded) | 1 |
| Informational (unchanged) | 1 |
| False Positives removed | 1 |
| Validated findings total | 12 |
| Severity changes | 1 (OMCP-010: Medium -> Informational) |
| ID renumbering | 2 (OMCP-012->011, OMCP-013->012) |
