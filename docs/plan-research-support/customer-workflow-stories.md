# Customer Workflow Stories for openstaad-mcp

Catalog of expected user workflows derived from 105+ researched OpenSTAAD tutorials, GitHub repos (yuominae/STAADModel, AkkachaiCE/OpenSTAAD), Bentley documentation, openstaad.com, and structural engineering practice. Used to inform tool design decisions for file I/O, context window management, and sandbox execution patterns.

## Data Pattern Legend

- **Incremental**: Can be processed row-by-row or in small batches. Pagination-friendly.
- **All-at-once**: Agent needs the full dataset simultaneously to reason about it correctly.
- **Iterative**: Requires multiple analysis-modify-analyze cycles.
- **Control-only**: Sends commands, minimal data transfer.

## Priority Tiers

- **P0**: Every engineer, every project. Must work flawlessly.
- **P1**: Most engineers, most projects. Should work well.
- **P2**: Power users or specialized workflows. Should be possible.
- **P3**: Edge cases. Acceptable to require workarounds.

---

## P0: Universal Workflows (Every Engineer, Every Project)

### 1. Export all member forces to Excel/CSV
- **What**: Extract FX/FY/FZ/MX/MY/MZ for all members across all load cases, write to spreadsheet
- **Category**: results-extraction
- **Direction**: Read from STAAD
- **Data volume**: Large (members x load-cases x 6 force components). A 500-member model with 20 LCs = 60,000 values.
- **Data pattern**: Incremental (can paginate by member group or load case)
- **MCP implication**: `read_tabular_data` with column filtering + pagination. Agent may need multiple calls but can stream results.
- **Sandbox role**: Minimal. This is a pure data extraction, better served by a dedicated MCP tool than sandbox code.

### 2. Extract support reactions for foundation design
- **What**: Get vertical loads, moments, shears at all support nodes for all combinations
- **Category**: results-extraction
- **Direction**: Read from STAAD
- **Data volume**: Medium (supports x combinations). Typical: 20-100 supports x 50-200 combos = 1K-20K values.
- **Data pattern**: Incremental (can filter by support node or load case)
- **MCP implication**: Same as #1 but smaller dataset. Usually fits in one response.
- **Sandbox role**: May need sandbox for computed columns (eccentricity ex=My/P, ey=Mx/P).

### 3. Steel design ratio extraction
- **What**: Get unity ratios for all steel members, identify overstressed members (ratio > 1.0)
- **Category**: design-check
- **Direction**: Read from STAAD
- **Data volume**: Medium (one ratio per member per combo). 500 members = 500 rows.
- **Data pattern**: Incremental, but agent needs ALL ratios to find the max/critical ones
- **MCP implication**: Fits comfortably in single response for most models.
- **Sandbox role**: Agent can filter/sort in sandbox. Or dedicated tool returns sorted by ratio descending.

### 4. Load combination generation
- **What**: Generate all code-required load combinations (ASCE 7, Eurocode, IS 875) from primary load cases
- **Category**: load-generation
- **Direction**: Write to STAAD
- **Data volume**: Medium (50-200 combinations from 5-15 primary cases)
- **Data pattern**: All-at-once write (combos reference each other by number)
- **MCP implication**: Agent generates combo definitions, sandbox writes them. Entire set fits easily in context.
- **Sandbox role**: Core sandbox use case. Code generates combos, calls COM API to create them.

### 5. Run analysis programmatically
- **What**: Trigger STAAD analysis without GUI interaction
- **Category**: batch-processing
- **Direction**: Control command to STAAD
- **Data volume**: None (single command)
- **Data pattern**: Control-only
- **MCP implication**: Existing `execute_code` tool handles this directly.
- **Sandbox role**: Single COM call. Trivial.

---

## P1: Common Engineering Workflows

### 6. Parametric frame generation
- **What**: Generate a complete portal frame or multi-bay frame from parameters (bays, widths, heights, sections)
- **Category**: parametric-design
- **Direction**: Write to STAAD
- **Data volume**: Medium (10-500 nodes, 10-500 members for typical frames)
- **Data pattern**: All-at-once write (nodes must exist before members reference them)
- **MCP implication**: Agent generates geometry in sandbox, pushes to STAAD via COM.
- **Sandbox role**: Core use case. JS code computes node coordinates, creates members. Sequential COM calls.

### 7. Import geometry from CSV/Excel coordinates
- **What**: Read node coordinates and member connectivity from spreadsheet, create STAAD model
- **Category**: interop
- **Direction**: Read file, write to STAAD
- **Data volume**: Medium-Large (100-5,000 nodes typical)
- **Data pattern**: All-at-once (needs all nodes before creating members that reference them)
- **MCP implication**: `read_tabular_data` loads the CSV, agent passes coordinates to sandbox, sandbox creates model.
- **Sandbox role**: Receives data from agent, iterates over rows calling COM. May need batching for very large imports.

### 8. Foundation load takedown with eccentricity
- **What**: Extract reactions, compute eccentricities (ex=My/P, ey=Mx/P), format for footing design
- **Category**: foundation-design
- **Direction**: Read from STAAD + compute
- **Data volume**: Medium (20-100 supports x 50-200 combos)
- **Data pattern**: All-at-once (needs P, Mx, My simultaneously per support to compute ratios)
- **MCP implication**: Extract via tool, compute in sandbox or let agent do arithmetic.
- **Sandbox role**: Good sandbox use case. Code extracts reactions, computes derived values, formats output.

### 9. Interstory drift ratio calculation
- **What**: Extract floor-level displacements, compute drift ratios between floors, flag code exceedances
- **Category**: seismic-analysis
- **Direction**: Read from STAAD + compute
- **Data volume**: Medium (floor nodes x seismic LCs). 10 floors x 10 nodes/floor x 5 LCs = 500 values.
- **Data pattern**: All-at-once (needs adjacent floor data simultaneously for ratio)
- **MCP implication**: Agent needs full floor displacement data to compute ratios. Usually fits in one response.
- **Sandbox role**: Ideal sandbox use case. Code extracts displacements, loops floors, computes drift ratios.

### 10. Wind load generation from code calculations
- **What**: Compute wind pressures from code (ASCE 7/IS 875/EC1) based on building geometry, apply to members
- **Category**: load-generation
- **Direction**: Compute + write to STAAD
- **Data volume**: Medium-Large (exterior members grouped by zone and height)
- **Data pattern**: All-at-once (needs full building geometry to determine exposure/zones)
- **MCP implication**: Agent needs building dimensions and member locations. Complex calculation in sandbox.
- **Sandbox role**: Heavy sandbox use. Code implements wind code logic, computes pressures by zone, applies loads.

### 11. Seismic base shear distribution
- **What**: Compute equivalent static seismic forces, distribute vertically per code (Cv factors)
- **Category**: load-generation
- **Direction**: Compute + write to STAAD
- **Data volume**: Small-Medium (one force per floor level)
- **Data pattern**: All-at-once (needs all floor weights/heights for distribution)
- **MCP implication**: Needs building weight and height data. Computation in sandbox.
- **Sandbox role**: Good sandbox use case. Code computes seismic distribution, applies lateral forces.

### 12. Member force extraction for connection design
- **What**: Get beam end forces at beam-column joints, format for connection design software
- **Category**: results-extraction
- **Direction**: Read from STAAD
- **Data volume**: Large (joints x LCs x force components). 200 connections x 100 combos x 6 forces = 120K values.
- **Data pattern**: Incremental (can process connection by connection)
- **MCP implication**: Large dataset. Needs pagination or filtering by joint/group.
- **Sandbox role**: Could extract in batches via sandbox, accumulate results.

### 13. Bill of quantities / material takeoff
- **What**: Sum steel weight by section type, concrete volume by grade, format procurement report
- **Category**: reporting
- **Direction**: Read from STAAD + aggregate
- **Data volume**: Medium (one row per member, aggregate to section groups)
- **Data pattern**: Incremental (can accumulate running totals)
- **MCP implication**: Read member properties + lengths, group and sum. Agent can do this.
- **Sandbox role**: Sandbox extracts data, computes totals. Good fit.

### 14. Model QA: detect duplicates, orphans, disconnected members
- **What**: Scan model for coincident nodes, unconnected members, zero-length elements
- **Category**: quality-assurance
- **Direction**: Read from STAAD
- **Data volume**: Medium-Large (all nodes need pairwise distance check)
- **Data pattern**: All-at-once (distance matrix requires all coordinates simultaneously)
- **MCP implication**: Needs all node coordinates in memory. For 2000 nodes, that's 2000 rows x 3 cols. Manageable.
- **Sandbox role**: Core sandbox use. Code loads all coords, runs O(n^2) or spatial-hash check.

### 15. Concrete beam design verification
- **What**: Extract factored moments/shears, compare against section capacity with given rebar
- **Category**: design-check
- **Direction**: Read from STAAD + compute
- **Data volume**: Medium (beams x critical sections x LCs)
- **Data pattern**: Incremental (beam by beam)
- **MCP implication**: Extract demand, compute capacity, compare. Can paginate.
- **Sandbox role**: Good fit. Code implements capacity calculations per code.

---

## P2: Power User / Specialized Workflows

### 16. Section optimization loop
- **What**: Iteratively resize sections (step down if ratio < 0.7, step up if > 1.0), re-analyze each cycle until convergence
- **Category**: optimization
- **Direction**: Both (read ratios, write new sections, trigger re-analysis)
- **Data volume**: Large per iteration, 5-20 iterations
- **Data pattern**: Iterative (each cycle: read all ratios, decide changes, write, re-analyze)
- **MCP implication**: Multiple sandbox executions. Each iteration is a complete read-modify-analyze cycle. Agent orchestrates.
- **Sandbox role**: Critical. Each iteration runs sandbox code that reads ratios, applies logic, modifies sections, re-runs analysis. Agent checks convergence between iterations.

### 17. Parametric truss generation
- **What**: Generate Pratt/Warren/Howe truss from span, depth, panel count
- **Category**: parametric-design
- **Direction**: Write to STAAD
- **Data volume**: Medium (20-200 nodes, 40-400 members for typical trusses)
- **Data pattern**: All-at-once write
- **MCP implication**: Pure computation in sandbox.
- **Sandbox role**: Core use case. Geometric generation + COM writes.

### 18. Progressive collapse analysis
- **What**: Systematically remove each critical member, re-analyze, check remaining members against acceptance criteria
- **Category**: optimization
- **Direction**: Both (read/write/analyze per scenario)
- **Data volume**: Large (N member-removal scenarios x full model results)
- **Data pattern**: Iterative (one scenario per execution, but many scenarios)
- **MCP implication**: Agent runs N scenarios sequentially. Each scenario: remove member, analyze, extract DCRs.
- **Sandbox role**: Each scenario is one sandbox execution. Agent orchestrates the campaign.

### 19. Batch multi-model processing
- **What**: Open each .STD file in a folder, analyze, extract key results, close, next
- **Category**: batch-processing
- **Direction**: Both (file control + results extraction)
- **Data volume**: Large in aggregate (N models x results per model)
- **Data pattern**: Incremental (model by model)
- **MCP implication**: Agent loops over files. Each iteration: open file, run sandbox code, collect results.
- **Sandbox role**: Each model is one sandbox execution. Agent manages the outer loop.

### 20. Pipe rack member classification and parameter assignment
- **What**: Classify members by function (main beam, column, bracing) from topology, assign Ky/Kz/UNL per PIP conventions
- **Category**: industrial-structures
- **Direction**: Both (read topology, write parameters)
- **Data volume**: Medium-Large (100-1000 members)
- **Data pattern**: All-at-once (needs full topology for classification logic)
- **MCP implication**: Needs connectivity data. Sandbox does graph analysis.
- **Sandbox role**: Heavy sandbox use. Code implements classification rules on connectivity graph.

### 21. Transmission tower leg force extraction by panel
- **What**: Extract axial forces in tower legs grouped by panel height, identify critical panel
- **Category**: tower-mast
- **Direction**: Read from STAAD + aggregate
- **Data volume**: Medium (50-200 leg members x load cases)
- **Data pattern**: All-at-once (needs all panels to find critical one)
- **MCP implication**: Full extraction then grouping logic.
- **Sandbox role**: Extract + aggregate in sandbox.

### 22. Precast concrete element grouping
- **What**: Group precast elements by capacity requirement vs factory catalog, optimize casting groups
- **Category**: concrete-design
- **Direction**: Both (read forces, write groups/properties)
- **Data volume**: Large (all precast members x all combos)
- **Data pattern**: All-at-once (optimization needs full picture)
- **MCP implication**: Extract demand, match to catalog, assign groups. Complex logic.
- **Sandbox role**: Heavy sandbox use. Optimization algorithm in JS.

### 23. Construction staging analysis
- **What**: Activate/deactivate member groups per stage, analyze each stage, track cumulative forces
- **Category**: construction-staging
- **Direction**: Both (modify model per stage, extract results per stage)
- **Data volume**: Medium per stage, many stages
- **Data pattern**: Iterative (sequential stages)
- **MCP implication**: Agent runs each stage. Sandbox modifies model + extracts results.
- **Sandbox role**: One execution per stage. Agent accumulates history.

### 24. Response spectrum scale factor calibration
- **What**: Run modal analysis, extract RSA base shear, compare to static, compute and apply scale factor
- **Category**: seismic-analysis
- **Direction**: Both (read results, write scale factor, re-analyze)
- **Data volume**: Small (aggregate values)
- **Data pattern**: Iterative (may need 1-2 adjustments)
- **MCP implication**: Simple data, complex logic.
- **Sandbox role**: Good fit. Code extracts modal results, computes factor, applies it.

### 25. Export model to IFC/Revit format
- **What**: Extract full geometry + sections + properties + loads, format for BIM software
- **Category**: interop
- **Direction**: Read from STAAD (entire model)
- **Data volume**: Large (all entities)
- **Data pattern**: Incremental (can serialize entity by entity)
- **MCP implication**: Full model extraction. Needs `write_tabular_data` or file generation.
- **Sandbox role**: Sandbox extracts, formats. May need file write tool for output.

---

## P3: Edge Cases / Specialized

### 26. Automatic buckling length calculation from topology
- **What**: Trace frame topology, identify restraint conditions, compute effective K-factors
- **Category**: design-check
- **Direction**: Both (read topology, write Ky/Kz)
- **Data volume**: Large (needs full connectivity graph)
- **Data pattern**: All-at-once (graph traversal)
- **MCP implication**: Full topology needed. Complex algorithm.
- **Sandbox role**: Heavy sandbox use. Graph algorithms in JS.

### 27. Moving load analysis for bridges
- **What**: Apply vehicle loads at incremental positions along bridge, extract envelope
- **Category**: load-generation
- **Direction**: Both (write loads at each position, analyze, read envelope)
- **Data volume**: Large (many positions x lanes x vehicles)
- **Data pattern**: Iterative (position by position, or STAAD's built-in moving load)
- **MCP implication**: Either use STAAD's native moving load, or many iterations.
- **Sandbox role**: If using COM: many iterations. If using STAAD's native: just setup.

### 28. Floor vibration serviceability check
- **What**: Extract natural frequencies and mode shapes, compute acceleration response per AISC DG11
- **Category**: design-check
- **Direction**: Read + compute
- **Data volume**: Small-Medium (modes x floor nodes)
- **Data pattern**: All-at-once (needs mode shape + frequency simultaneously)
- **MCP implication**: Modal results extraction + hand calculations.
- **Sandbox role**: Good fit. Code implements DG11 methodology.

### 29. Crane load generation
- **What**: Apply crane wheel loads at multiple positions along runway beams
- **Category**: load-generation
- **Direction**: Write to STAAD
- **Data volume**: Medium (positions x wheels)
- **Data pattern**: All-at-once write (all positions defined at once)
- **MCP implication**: Geometry calculation + load application.
- **Sandbox role**: Compute wheel positions, apply loads via COM.

### 30. Sensitivity study / parameter sweep
- **What**: Vary a parameter (load magnitude, section size, support stiffness), analyze each variant, collect results
- **Category**: optimization
- **Direction**: Both
- **Data volume**: Small per variant, many variants
- **Data pattern**: Iterative (one variant per cycle)
- **MCP implication**: Agent orchestrates loop. Each variant is one sandbox call.
- **Sandbox role**: One execution per variant. Agent manages campaign.

---

## Data Pattern Summary (Implications for File I/O Design)

| Pattern | Count | Context Window Risk | Mitigation |
|---------|-------|--------------------|----|
| Incremental | 10 | Low | Pagination works. Default `max_rows` sufficient. |
| All-at-once | 14 | Medium-High | Needs full dataset. Filter by columns, compress representation. |
| Iterative | 8 | Low per iteration | Agent orchestrates loop. Each iteration bounded. |
| Control-only | 2 | None | Trivial. |

### Key Finding: "All-at-once" Workflows

14 of 30 detailed workflows require the agent/sandbox to have ALL relevant data simultaneously. These are the ones that stress context windows:

1. Load combination generation (needs all primary case names)
2. Drift calculation (needs all floor displacements)
3. Wind load generation (needs all exterior member geometry)
4. Seismic distribution (needs all floor weights/heights)
5. QA: duplicate detection (needs all node coordinates)
6. Section optimization (needs all ratios per iteration)
7. Pipe rack classification (needs full connectivity)
8. Precast grouping (needs all demands vs catalog)
9. Progressive collapse (needs full model per scenario)
10. Topology-based K-factor calculation (needs connectivity graph)
11. Tower panel extraction (needs all panels)
12. Foundation takedown (needs all reactions)
13. Connection design forces (needs envelope across all combos)
14. Concrete column interaction (needs all Pu/Mux/Muy)

### Recommended Strategy for All-at-Once Workflows

For these workflows, the data lives INSIDE the sandbox, not in the agent's context window:

1. **Sandbox loads all data internally** via COM calls (e.g., loop all members, store forces in JS arrays)
2. **Sandbox performs computation** (drift ratios, grouping, classification)
3. **Sandbox returns only the summary** to the agent (e.g., "3 members exceed drift limit: M45, M67, M89")

This means the sandbox code itself handles the large dataset. The context window only sees the script (small) and the result summary (small). The 60,000-value force table never enters the context window.

### When File I/O Tools Are Actually Needed

File I/O (`read_tabular_data` / `write_tabular_data`) is needed for:
- **Input files** the user provides (CSV of coordinates, equipment loads, external data)
- **Output files** the user wants (Excel report, CSV for downstream software)
- **NOT** for intermediate data that the sandbox can access directly via COM

The typical flow is:
```
User provides CSV → read_tabular_data → agent sees data → agent writes sandbox code → 
sandbox reads from STAAD + uses CSV data → sandbox produces results →
write_tabular_data → user gets output file
```

---

## Workflow Complexity Distribution

| Complexity | Count | Sandbox Execution Pattern |
|-----------|-------|---------------------------|
| Simple (single COM call or query) | 5 | One short script |
| Medium (loop + compute) | 12 | One medium script (20-50 lines) |
| Complex (multi-step + logic) | 8 | One large script (50-150 lines) |
| Iterative campaign (multiple executions) | 5 | Agent orchestrates N executions |

## Questions This Catalog Raises for Design

1. **Iterative workflows**: How does the agent know when to stop? Convergence criteria need to be in the sandbox output.
2. **Large internal datasets**: Can the sandbox handle 60K values in JS arrays? (Yes, QuickJS can handle millions of values in memory.)
3. **Multi-execution campaigns**: Should there be a "campaign" mode where the agent runs a loop of sandbox executions without re-explaining the plan each time?
4. **External data ingestion**: The `read_tabular_data` tool feeds data INTO the agent context, but for large imports, should there be a way to stream data directly into the sandbox without going through the context window?
5. **Output formatting**: Many workflows end with "write to Excel". Should `write_tabular_data` accept structured data from sandbox output directly?
