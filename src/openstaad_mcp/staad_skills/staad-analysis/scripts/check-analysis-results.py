# check-analysis-results.py
# Recommended check AFTER AnalyzeEx and BEFORE calling any Output getter.
# Querying results from a failed/incomplete run can raise a misleading
# COMError: "Memory is locked." instead of a clear "results not available" message.
# Checking status + AreResultsAvailable + the solver's own error text first avoids
# that confusing symptom and reports the real cause (e.g. a member missing a material).

staad.SetSilentMode(True)
staad.SaveModel(True)
status = staad.AnalyzeEx(1, 0, 1)   # 2=OK, 3=warnings, 4=errors, -1=terminated
staad.SetSilentMode(False)

out = staad.Output
available = out.AreResultsAvailable()

if status in (4, -1) or not available:
    # STAAD.Pro v26+ only — see staad-core -> Version Compatibility
    errors = staad.GetAnalysisErrorMessages()
    print(f"Analysis failed (status={status}). Errors:")
    for e in errors:
        print(f"  {e}")
    result = {"status": status, "available": available, "errors": list(errors)}
else:
    print(f"Analysis status: {status} | Results available: {available}")
    result = {"status": status, "available": available}
