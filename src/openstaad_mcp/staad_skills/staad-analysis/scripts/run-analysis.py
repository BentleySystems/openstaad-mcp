﻿# run-analysis.py
# Runs a linear static analysis on the current model.
# Two steps: PerformAnalysis (adds the command to the .std file) + AnalyzeEx (runs the solver).
# AnalyzeEx is the preferred solver function — it returns a status code.
# Do NOT call PerformAnalysis more than once.

# Step 1: Add the PERFORM ANALYSIS command (once only)
cmd = staad.Command
cmd.PerformAnalysis(0)   # 0 = no print option

# Step 2: Save + run the solver
staad.SetSilentMode(True)
staad.SaveModel(True)
status = staad.AnalyzeEx(1, 0, 1)   # silentMode=1, hiddenMode=0, waitTillComplete=1
staad.SetSilentMode(False)
# status: 2=OK, 3=warnings, 4=errors, -1=terminated, 0=general error

# Verify results are available
out = staad.Output
available = out.AreResultsAvailable()
print(f'Analysis status: {status} | Results available: {available}')