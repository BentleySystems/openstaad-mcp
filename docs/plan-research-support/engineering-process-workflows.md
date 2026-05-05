# Structural Engineering Process Workflows for MCP Automation

Research compiled 2025-05-05. Sources: steelconstruction.info, Bentley STAAD documentation, CSI Knowledge Base, Tekla/Trimble resources, and standard structural engineering practice.

---

## 1. Structural Design Report Generation

**Source:** Standard practice per IStructE/ASCE/Engineers Australia reporting guidelines; ideCAD workflow documentation (idecad.com)

**Workflow Name:** Complete Structural Calculation Report Production

**Process Steps:**
1. Extract project metadata (job title, engineer, checker, revision, date)
2. Document design basis (codes, load combinations, material properties, design life)
3. Compile load derivations (dead, live, wind, seismic) with calculations showing how loads were determined
4. Extract analysis results per element type (beams, columns, slabs, foundations)
5. For each critical element: show applied forces, capacity calculation, utilization ratio
6. Generate worst-case summaries (most utilized beam, most loaded column, max drift)
7. Include deflection checks against serviceability limits
8. Document connection design summaries
9. Compile foundation reactions for geotechnical engineer
10. Assemble appendices (input echo, output summaries, sketches)
11. Apply report template with pagination, headers, table of contents
12. Generate revision history comparing to previous version

**Data Inputs:**
- STAAD model (.std file): geometry, sections, loads, load combinations
- Analysis results: member forces, reactions, displacements
- Design results: utilization ratios, governing load cases, code check status
- Project data: client, job number, engineer initials, checker initials
- Report template: corporate format, logo, disclaimers

**Outputs:**
- Formatted PDF/DOCX calculation report (typically 50-500 pages)
- Summary tables: member schedules, reaction tables, drift tables
- Design certificate or design brief

**OpenSTAAD Role:**
- `GetNodeDisplacement()` for every node at every load case
- `GetMemberEndForces()` for critical members
- `GetSupportReaction()` for all supports
- `GetMemberDesignRatio()` for utilization
- `GetMemberProperty()` for section data
- Iterate all members to find worst cases
- Model metadata extraction

**Volume:** A typical 10-storey building: ~500 beams, ~100 columns, ~50 load cases = 25,000 member force extractions, 5,000 displacement checks, ~500 design ratio checks. Report: 100-300 pages.

---

## 2. Design Verification / Code Compliance Checking

**Source:** Standard QA/QC practice; BS EN 1993/1992/1991 series (Eurocodes); AISC 360; ACI 318; AS 4100

**Workflow Name:** Automated Code Compliance Verification

**Process Steps:**
1. Identify applicable design code (IS 456, AISC 360, EC3, AS 4100, etc.)
2. For each member, extract: material grade, section properties, effective length, unbraced length
3. Extract applied forces from all load combinations
4. Compute capacity per code: axial, flexural, shear, combined
5. Check interaction equations (e.g., H1-1a/b for AISC, Eq 6.61/6.62 for EC3)
6. Verify serviceability: deflection vs L/360, drift vs H/500
7. Check local stability: width-thickness ratios, section classification
8. Verify connection adequacy at member ends
9. Flag non-compliant elements with specific clause violations
10. Generate compliance matrix: member vs check type vs pass/fail
11. Produce exception report: items needing redesign

**Data Inputs:**
- Full analysis model with all load combination results
- Design code parameters (effective length factors, Cb values, bracing conditions)
- Acceptance criteria per code clause
- Member grouping information

**Outputs:**
- Pass/fail matrix per member per check
- Utilization ratio heat map
- Non-compliance report with clause references
- Redesign recommendations (larger section needed, additional bracing, etc.)

**OpenSTAAD Role:**
- `GetMemberEndForces()` for all members, all load cases
- `GetMemberProperty()` for section dimensions
- `GetMemberDesignRatio()` where STAAD has already done the check
- `GetMemberLength()` / `GetMemberIncidence()` for geometry
- Read STAAD design parameters (Ky, Kz, Lb, Cb)
- Read material properties

**Volume:** 500-member building, 50 load combinations, 8 checks per member = 200,000 individual verifications. Compliance report: 20-50 pages of exceptions.

---

## 3. Peer Review Checklist Automation (QA/QC)

**Source:** IStructE "Manual for the design of building structures"; ASCE/SEI recommended practice; typical firm QA procedures

**Workflow Name:** Automated Structural Peer Review

**Process Steps:**
1. **Model integrity checks:**
   - All nodes connected (no orphan nodes)
   - No duplicate members
   - No zero-length members
   - All members have sections assigned
   - All loads applied to valid entities
2. **Load path verification:**
   - Every slab has supporting beams
   - Every beam reaches a column or wall
   - Every column reaches foundation
   - Lateral system complete (bracing/moment frames in both directions)
3. **Load magnitude reasonableness:**
   - Dead load within expected range (3-8 kPa for concrete floors)
   - Live load per code (2.5 kPa office, 5 kPa storage)
   - Wind loads consistent with location/terrain
   - Seismic weight approximately correct
4. **Analysis result sanity checks:**
   - No uplift reactions at interior columns
   - Sum of reactions equals sum of applied loads (equilibrium)
   - Maximum deflections reasonable (L/300 to L/500)
   - No excessive member forces (member not grossly undersized)
   - Natural period consistent with building height (~0.1N seconds)
5. **Design adequacy checks:**
   - No members over 95% utilized
   - No members under 30% utilized (overdesigned, waste)
   - Connection forces compatible with standard connections
   - Foundation pressures within soil bearing capacity
6. **Documentation checks:**
   - All load combinations per code present
   - Correct importance factor applied
   - Design life stated and consistent

**Data Inputs:**
- Complete STAAD model
- Analysis and design results
- Project design brief
- Applicable code requirements
- Firm-specific QA checklist

**Outputs:**
- Checklist with pass/fail/warning for each item
- Identified issues with severity rating (critical/major/minor)
- Quantitative summary: "95% of members adequate, 12 members overstressed"
- Suggested remedial actions

**OpenSTAAD Role:**
- Complete model traversal: all nodes, members, plates
- All support reactions for equilibrium check
- All member forces for reasonableness
- All design results for utilization distribution
- Model geometry for load path tracing
- Load data extraction for magnitude checks

**Volume:** Full model audit: thousands of checks depending on model size. Typical output: 50-100 item checklist with narrative.

---

## 4. Steel Fabrication BOM (Bill of Materials) Generation

**Source:** steelconstruction.info (fabrication processes); AISC/BCSA practice; Tekla workflow (trimble.com/blog "From model to metal")

**Workflow Name:** Steel Bill of Materials from Analysis Model

**Process Steps:**
1. Extract all steel members from model with: section size, length, grade
2. Group members by section size and grade
3. Calculate individual member weights: (unit weight kg/m) x length
4. Add connection allowances (typically 10-15% for fittings)
5. Add paint/galvanizing surface area calculations
6. Generate cutting list: number of pieces per section per length
7. Compute total tonnage by section type
8. Map sections to available commercial lengths (6m, 9m, 12m, 15m stock)
9. Calculate wastage from cutting
10. Generate procurement schedule: section, grade, quantity (tonnes), delivery priority
11. Produce erection sequence grouping (by floor level, by grid, by phase)
12. Calculate bolt requirements from connection types and member counts
13. Estimate weld quantities from connection details

**Data Inputs:**
- STAAD model member list with sections and lengths
- Material grades per member
- Connection types (from design or assumed standard)
- Member grouping (by floor, phase, priority)
- Steel stock availability (standard lengths, section availability)

**Outputs:**
- Bill of Materials spreadsheet: section, grade, length, quantity, weight
- Procurement summary: total tonnage by grade, by section series
- Cutting list optimized against stock lengths
- Bolt schedule: type, size, quantity
- Cost estimate: material cost per tonne applied to quantities

**OpenSTAAD Role:**
- `GetMemberCount()` / iterate all members
- `GetMemberProperty()` for section designation
- `GetMemberLength()` for each member
- `GetMemberIncidence()` for coordinates (erection sequencing)
- Material property extraction
- Member grouping information

**Volume:** Typical steel building: 200-2000 members. BOM: 50-200 line items after grouping. Procurement: 10-30 different section sizes.

---

## 5. Rebar Schedule Generation

**Source:** Standard RC detailing practice per BS 8666 / ACI 315; ideCAD Structural automation features

**Workflow Name:** Reinforcement Schedule from Design Results

**Process Steps:**
1. Extract concrete member design results: required As (area of steel) per face per location
2. For beams: top and bottom reinforcement at supports and midspan
3. For columns: longitudinal bars and link/stirrup spacing
4. For slabs: reinforcement in two directions, top and bottom
5. Select actual bar sizes to provide >= required area (e.g., need 1200mm2, provide 4T20 = 1257mm2)
6. Calculate bar lengths including anchorage, lap lengths, hook allowances per code
7. Determine cut/bend shapes per BS 8666 shape codes
8. Generate bar marks (unique identifier per bar type)
9. Tabulate: bar mark, shape code, size, length, number-off, total weight
10. Calculate total reinforcement weight per element and per floor
11. Group by bar size for procurement (total kg of T10, T12, T16, T20, T25, T32)
12. Estimate reinforcement density (kg/m3 of concrete) for cost checking

**Data Inputs:**
- STAAD/RCDC concrete design results: required reinforcement areas
- Member dimensions (width, depth, cover)
- Applicable code (lap lengths, anchorage, minimum spacing)
- Detailing preferences (preferred bar sizes, max bar diameter)
- Structural layout (spans, supports)

**Outputs:**
- Bar bending schedule per element (BS 8666 format)
- Bar mark drawings (schematic)
- Weight summary: total kg per bar size
- Reinforcement density check
- Procurement schedule

**OpenSTAAD Role:**
- Concrete design results extraction (required As per member per section)
- Member geometry for bar length calculations
- Support conditions for anchorage requirements
- Design code parameters

**Volume:** 10-storey building: ~200 beams x 5 sections each = 1000 reinforcement calculations, ~80 columns x 4 faces = 320, plus slabs. Total rebar schedule: 500-2000 bar marks. Typical tonnage: 50-200 tonnes of rebar.

---

## 6. Anchor Bolt / Base Plate Design

**Source:** steelconstruction.info/Simple_connections#Column_bases; AISC Design Guide 1; Eurocode 3 Part 1-8

**Workflow Name:** Foundation Interface Design from Column Reactions

**Process Steps:**
1. Extract all column base reactions: axial (compression and tension), shear Vx/Vy, moments Mx/My for all load combinations
2. Identify governing load combinations per base (max compression, max tension, max shear, max moment)
3. Determine base plate size: based on bearing pressure on concrete (fc' or fck)
4. Calculate base plate thickness: from cantilever bending of plate beyond column flanges
5. Determine anchor bolt requirements:
   - For uplift: bolt tensile capacity >= factored tension
   - For moment: bolt group to resist overturning
   - For shear: bolts in shear or friction or shear key
6. Select bolt size and grade (typically M20-M36, Grade 4.6 or 8.8)
7. Calculate embedment depth for pull-out capacity in concrete
8. Check concrete cone breakout per ACI 318 Appendix D / EN 1992-4
9. Verify edge distances and spacing
10. Design grout (thickness, strength)
11. Produce base plate detail: dimensions, bolt layout, weld sizes
12. Generate anchor bolt schedule: size, grade, embedment, projection, quantity per base

**Data Inputs:**
- Column base reactions from STAAD (all load combinations)
- Column section sizes
- Concrete foundation strength (f'c or fck)
- Soil bearing capacity (for foundation sizing)
- Bolt grade availability
- Connection classification (pinned or moment-resisting)

**Outputs:**
- Base plate schedule: plate size, thickness, grade per column
- Anchor bolt schedule: size, grade, length, embedment per base
- Foundation reaction summary for geotechnical engineer
- Base plate detail drawings (or parametric inputs for CAD)
- Weld sizes at column-to-baseplate connection

**OpenSTAAD Role:**
- `GetSupportReaction()` for all supports, all load combinations
- `GetNodeCoordinate()` for base locations
- Member section at each base
- Load combination identification

**Volume:** Typical building: 20-100 column bases. Each needs 5-50 load combinations checked. Output: 20-100 base plate designs, anchor bolt schedule of 100-400 bolts total.

---

## 7. Building Seismic Weight Calculation

**Source:** ASCE 7 Section 12.7.2; IS 1893; EN 1998-1; CSI Knowledge Base (wiki.csiamerica.com)

**Workflow Name:** Seismic Weight and Base Shear Computation

**Process Steps:**
1. Identify all dead loads in model (self-weight + superimposed dead)
2. Identify portion of live load contributing to seismic weight per code:
   - ASCE 7: 25% of storage live load, 0% of other (typically)
   - IS 1893: 25% for LL <= 3 kPa, 50% for LL > 3 kPa
   - EC8: ψ2 factor x live load
3. Calculate weight floor-by-floor:
   - Structural self-weight (beams, columns, slabs, walls)
   - Superimposed dead (finishes, MEP, cladding, partitions)
   - Applicable live load fraction
4. Sum total seismic weight W
5. Determine fundamental period T (from modal analysis or empirical formula)
6. Determine seismic coefficient Cs from response spectrum:
   - Site class, importance factor, R-factor, spectral parameters
7. Calculate base shear V = Cs x W
8. Distribute base shear vertically per code (triangular, parabolic, or modal)
9. Check against minimum base shear requirements
10. Verify period from modal analysis matches assumed period
11. Determine if dynamic analysis required (height limits, irregularity)
12. Document complete seismic force calculation chain

**Data Inputs:**
- Complete structural model with all dead and live loads
- Self-weight of structural elements
- Site seismicity parameters (PGA, Ss, S1, soil type)
- Importance factor
- Response modification factor (R)
- Building height and configuration (regular/irregular)

**Outputs:**
- Weight breakdown by floor
- Total seismic weight
- Fundamental period (calculated and code-limit)
- Design base shear
- Vertical distribution of seismic forces
- Comparison with code minimums
- Decision on analysis method (ELF vs Response Spectrum vs Time History)

**OpenSTAAD Role:**
- Self-weight extraction from model
- Applied load extraction (dead, live per floor)
- Modal analysis results (periods, mode shapes, participation factors)
- `GetSupportReaction()` for dead load case (= total weight)
- Node coordinates for floor-by-floor weight distribution
- Building height from geometry

**Volume:** 10-storey building: 10 floors of weight calculation, 3-5 modal periods to check, multiple seismic parameters. Calculation: 2-5 pages of standard format.

---

## 8. Weld Design from Member Forces

**Source:** steelconstruction.info (connections); AISC Manual Part 8; Eurocode 3 Part 1-8; AWS D1.1

**Workflow Name:** Connection Weld Sizing from Analysis Forces

**Process Steps:**
1. Extract member end forces at each connection: axial P, shear V, moment M
2. Identify connection type (welded end plate, welded direct, moment connection)
3. Determine weld configuration (fillet vs butt, location on flanges/web)
4. Calculate force demand on each weld group:
   - Flange welds carry moment (M/d) and portion of axial (P x Af/A)
   - Web welds carry shear V and portion of axial (P x Aw/A)
5. Compute weld stress: force per unit length of weld
6. Determine required weld throat: demand / (0.6 x electrode strength x phi)
7. Convert throat to fillet weld leg size: a = throat / 0.707
8. Check minimum weld size per code (based on thicker part joined)
9. Check maximum weld size (not exceed plate thickness minus 1.5mm)
10. Verify weld length adequate (minimum 4x leg size)
11. Select practical weld size (round up to standard: 6mm, 8mm, 10mm, 12mm)
12. Generate weld schedule: connection reference, weld type, size, length, location

**Data Inputs:**
- Member end forces from all governing load combinations
- Member section properties (flange/web dimensions, thickness)
- Weld electrode grade (E70XX / 42W)
- Connection geometry
- Base metal properties (for matching strength)

**Outputs:**
- Weld schedule per connection type
- Weld details for fabrication drawings
- Total weld volume (for cost estimating)
- Welding procedure requirements (preheat, inspection level)
- NDE (non-destructive examination) requirements

**OpenSTAAD Role:**
- `GetMemberEndForces()` at both ends of every member
- `GetMemberProperty()` for section dimensions
- Member incidence and connectivity
- Load combination results for governing cases

**Volume:** 200-member steel frame: ~300-500 welded connections. Each connection: 2-4 welds to size. Total: 600-2000 individual weld calculations.

---

## 9. Structural Cost Estimation

**Source:** Industry practice; steelconstruction.info/Cost_of_structural_steelwork; RSMeans data

**Workflow Name:** Material-Based Cost Estimate from Structural Model

**Process Steps:**
1. Extract steel quantities: tonnage by section type and grade
2. Extract concrete quantities: volume by element type (footings, columns, beams, slabs)
3. Extract reinforcement quantities: kg by bar size
4. Apply unit rates:
   - Structural steel: supply + fabrication + erection ($/tonne by complexity)
   - Concrete: supply + place + finish ($/m3 by element type)
   - Reinforcement: supply + fix ($/kg, varies by complexity)
5. Add connection costs: standard connections cheaper than special
6. Add surface treatment: paint system / galvanizing ($/m2)
7. Add foundation costs: excavation + concrete + backfill
8. Add fire protection costs (intumescent paint, board, spray)
9. Sum to total structural cost
10. Express as cost per m2 of floor area (benchmarking)
11. Compare to industry benchmarks (flag outliers)
12. Break down by building element (substructure, frame, floors, roof)

**Data Inputs:**
- Complete material take-off from model (steel tonnes, concrete m3, rebar kg)
- Current unit rates (location-specific)
- Connection complexity classification
- Fire rating requirements
- Site access constraints (affecting erection costs)
- Procurement strategy (single source vs competitive)

**Outputs:**
- Elemental cost breakdown
- Cost per m2 GFA comparison
- Material quantities summary
- Sensitivity analysis (impact of steel price change)
- Value engineering opportunities (over-designed elements)

**OpenSTAAD Role:**
- All member sections and lengths (steel quantities)
- Plate/slab elements (concrete quantities)
- Design results (reinforcement areas for RC)
- Geometry (floor areas for normalization)

**Volume:** Full building material takeoff: all members quantified. Output: typically 2-5 page cost report plus detailed schedule.

---

## 10. Structural Revision Tracking / Model Comparison

**Source:** Standard engineering QA practice; BIM version control concepts

**Workflow Name:** Structural Model Version Comparison

**Process Steps:**
1. Load two model versions (current and previous)
2. Compare geometry: identify added/removed/moved nodes and members
3. Compare sections: identify where member sizes changed
4. Compare loads: identify new/modified/removed load patterns
5. Compare results: delta in member forces, reactions, displacements
6. Identify members where utilization changed significantly (>10% change)
7. Flag new overstressed members that were previously adequate
8. Quantify impact on quantities (tonnage change, rebar change)
9. Produce revision narrative: "Added 2 bracing bays, increased B12 from 310UB40 to 360UB50"
10. Update revision register and drawing issue log
11. Determine which drawings need reissuing based on changed elements

**Data Inputs:**
- Previous model version (or saved results)
- Current model version
- Tolerance thresholds for "significant change"
- Drawing register (which drawings show which elements)

**Outputs:**
- Change log: what changed, where, by how much
- Impact assessment: which downstream documents affected
- Quantity variation: +/- tonnes steel, +/- m3 concrete
- Drawing reissue list
- Revision cloud data (coordinates of changes for CAD)

**OpenSTAAD Role:**
- Full model data extraction from both versions
- Compare node coordinates, member sections, loads
- Compare analysis results
- Compare design results

**Volume:** Depends on model size and extent of change. Comparison of two 500-member models: 500 member checks, 200 node checks, multiple load case comparisons.

---

## 11. Load Path Verification

**Source:** Engineering first principles; IStructE guidance; building regulation requirements

**Workflow Name:** Gravity and Lateral Load Path Tracing

**Process Steps:**
1. **Gravity load path (top-down):**
   - Roof loads -> purlins/roof beams
   - Roof beams -> columns or walls
   - Floor slab -> floor beams (tributary area or FE)
   - Floor beams -> girders or columns
   - Columns -> foundations
   - At each level: verify sum of loads is conserved (no load "lost")
2. **Lateral load path:**
   - Wind/seismic on cladding -> girts/mullions
   - Girts -> columns (wind columns or main frame)
   - Floor diaphragm collects inertia forces
   - Diaphragm delivers to bracing/moment frames/walls
   - Bracing/walls deliver to foundations
   - Verify continuous path exists in both directions
3. **Checks at each transfer:**
   - Connection adequate for the transfer force
   - Member adequate for applied forces
   - No "gap" in load path (disconnected elements)
4. **Quantitative verification:**
   - Total applied gravity load = sum of foundation reactions (equilibrium)
   - Total lateral base shear = sum of horizontal reactions
   - At each floor: incoming loads = outgoing loads

**Data Inputs:**
- Complete structural model with connectivity
- All applied loads
- Analysis results (reactions for equilibrium check)
- Connection types at each joint

**Outputs:**
- Load path diagram (graphical trace from roof to foundation)
- Equilibrium verification at each level
- Identified gaps or weak links
- Load path efficiency metric (force amplification through path)
- Recommendations for load path improvement

**OpenSTAAD Role:**
- Full model connectivity (member incidences)
- Node coordinates and member orientations
- All support reactions (for equilibrium verification)
- Load application points and magnitudes
- Member forces at each joint

**Volume:** Load path trace for 10-storey building: 10 levels x 2 directions for lateral, full vertical trace for gravity. Output: graphical diagram + numerical verification table.

---

## 12. Performance-Based Seismic Design

**Source:** ASCE 41; FEMA P-58; EN 1998-3; TBI Guidelines for Tall Buildings

**Workflow Name:** Nonlinear Seismic Assessment Workflow

**Process Steps:**
1. **Define performance objectives:** IO (Immediate Occupancy), LS (Life Safety), CP (Collapse Prevention) at different hazard levels
2. **Develop nonlinear model:**
   - Convert linear model to nonlinear (assign plastic hinges)
   - Define force-deformation relationships for hinges (ASCE 41 Table 9-6 for steel, 10-7 for concrete)
   - Model P-Delta effects
3. **Select ground motions:**
   - 7-11 ground motions per hazard level (per ASCE 7)
   - Scale to target spectrum or match using spectral matching
4. **Run analyses:**
   - Pushover analysis (nonlinear static) for preliminary assessment
   - Nonlinear time history (NLTHA) for detailed assessment
5. **Extract demands:**
   - Story drift ratios per floor per earthquake
   - Plastic hinge rotations per member
   - Floor accelerations per level
   - Residual drifts
6. **Evaluate performance:**
   - Compare demands to acceptance criteria per ASCE 41
   - Identify members exceeding LS or CP limits
   - Compute collapse probability (fragility analysis)
7. **Loss estimation (FEMA P-58):**
   - Relate demands (drift, acceleration) to damage states
   - Compute repair costs, downtime, casualties
8. **Iterate design:** strengthen members where performance inadequate

**Data Inputs:**
- Linear analysis model (basis for nonlinear conversion)
- Hinge properties per member type (from code tables or testing)
- Ground motion records (acceleration time histories)
- Performance objectives per building importance
- Component fragility data (for loss estimation)

**Outputs:**
- Pushover curve with performance point
- Drift profiles per earthquake per direction
- Hinge status map (operational/IO/LS/CP/collapsed)
- Expected annual loss (EAL)
- Collapse probability at MCE level
- Retrofit recommendations where needed

**OpenSTAAD Role:**
- Base model extraction for conversion to nonlinear platform
- Linear analysis results as baseline comparison
- Modal properties (periods, mode shapes) for pushover target
- Member properties and geometry for hinge assignment
- *Note: STAAD.Pro does limited nonlinear analysis; this workflow often uses ETABS/SAP2000/PERFORM-3D, but OpenSTAAD feeds the base model*

**Volume:** 7-11 time histories x 2 directions = 14-22 NL analyses. Each produces drift/force/hinge results at every timestep. Total data: millions of result values. Assessment report: 50-100 pages.

---

## 13. Drawing Schedule Generation

**Source:** Standard engineering document control practice; BS 1192/ISO 19650 conventions

**Workflow Name:** Structural Drawing Register from Model

**Process Steps:**
1. Parse model to identify structural elements by level and grid
2. Determine required drawing types:
   - General arrangement plans (one per floor typically)
   - Elevations/sections (as needed for clarity)
   - Foundation layout
   - Beam/slab schedules
   - Connection details
   - Reinforcement details (for RC)
3. Assign drawing numbers per firm numbering system
4. Determine drawing sheet size based on content extent
5. Populate drawing register: number, title, revision, status, scale
6. Assign responsibility (who draws, who checks)
7. Link elements to drawings (which members appear on which drawing)
8. Track revision status (when changed elements force drawing reissue)
9. Generate transmittal lists for submissions

**Data Inputs:**
- Model geometry (levels, grids, extents)
- Firm drawing numbering convention
- Project phases/stages
- Submission requirements (planning, tender, construction)

**Outputs:**
- Drawing register spreadsheet
- Drawing title block data (auto-populated)
- Element-to-drawing mapping
- Transmittal forms
- Progress tracking (% drawings issued)

**OpenSTAAD Role:**
- Model geometry: floor levels, grid coordinates
- Member listing per floor
- Foundation layout from support locations
- Element count per drawing (to estimate drawing complexity)

**Volume:** Typical building: 30-100 structural drawings. Register: 30-100 entries with metadata.

---

## 14. Steel Connection Design (Systematic)

**Source:** steelconstruction.info/Simple_connections (detailed process found); SCI P358 "Green Book"; AISC Steel Construction Manual Part 10

**Workflow Name:** Systematic Connection Design for All Joints

**Process Steps (per SCI P358):**
1. Classify each joint as simple (pinned) or moment-resisting
2. For each connection, extract: beam end shear V, axial N, tying force T
3. Select connection type based on criteria:
   - Partial-depth end plate: up to 75% beam shear capacity
   - Full-depth end plate: up to 100% beam shear capacity
   - Fin plate: up to 50% (single bolt line) or 75% (double line)
4. Design checks (10 for shear + 6 for tying):
   - Check 1: Detailing practice (bolt spacing, edge distances)
   - Check 2: Supported beam (welds or bolt group)
   - Check 3: Fin plate (or N/A for end plates)
   - Check 4: Web in shear
   - Check 5: Resistance at notch (if notched)
   - Check 6: Local stability of notched beam
   - Check 7: Overall stability of notched beam (if unrestrained)
   - Check 8: Bolt group or welds
   - Check 9: End plate in shear
   - Check 10: Supporting column/beam web panel
   - Checks 11-16: Tying resistance checks
5. Standardize: use M20 8.8 bolts, S275 fittings, 6-8mm fillet welds
6. Produce connection schedule: connection ID, type, plate size, bolt pattern, weld sizes
7. Generate detail drawings or parametric data for Tekla/AutoCAD

**Data Inputs:**
- Member end forces (from STAAD, all load combinations)
- Member sections (for depth, flange width, web thickness)
- Column/beam web properties at connection
- Bolt and plate material strengths
- Tying force requirements (per building class)
- Standard connection geometry (from Green Book tables)

**Outputs:**
- Connection schedule (one line per unique connection type)
- Connection details (parametric: plate size, bolt layout, weld)
- Material list for fittings (plates, bolts)
- Verification calculations (for critical connections)
- Standardization summary (e.g., "95% of connections are standard")

**OpenSTAAD Role:**
- `GetMemberEndForces()` at both ends, all combinations (shear is primary demand)
- `GetMemberProperty()` for beam/column sections
- Member connectivity (what connects to what)
- Load combination factors for tying force computation

**Volume:** 200-member steel frame: ~300-500 connection designs. After standardization, typically 5-15 unique connection types. Each type: 10-16 checks. Total: 3000-8000 individual check calculations.

---

## 15. Foundation Reaction Summary for Geotechnical Interface

**Source:** Standard practice at structural/geotechnical interface

**Workflow Name:** Foundation Loading Schedule Production

**Process Steps:**
1. Extract all support reactions for all load combinations
2. Identify type of reaction per support (vertical only, vertical + moment, etc.)
3. For each foundation:
   - Maximum compression (for bearing check)
   - Maximum tension/uplift (for anchor/pile tension)
   - Maximum horizontal shear (for sliding)
   - Maximum overturning moment (for eccentricity/stability)
4. Identify governing load combination for each critical case
5. Present unfactored (service) loads for geotechnical bearing design
6. Present factored (ultimate) loads for structural foundation design
7. Group foundations by similar loading (pad footings, strip footings, piles)
8. Calculate minimum foundation size for bearing capacity
9. Check differential settlement implications (from variable loading)
10. Produce foundation loading plan with reaction arrows
11. Interface document for geotechnical engineer

**Data Inputs:**
- All support reactions from STAAD (all load combinations)
- Support locations and types
- Load combination factors (ULS and SLS separately)
- Soil bearing capacity (from geotech report)
- Settlement limits

**Outputs:**
- Foundation loading schedule (table: foundation ID, max/min axial, shear, moment)
- Loading plan (CAD-ready with arrow magnitudes)
- Unfactored loads for bearing design
- Factored loads for structural design
- Foundation sizing recommendations
- Settlement sensitivity analysis

**OpenSTAAD Role:**
- `GetSupportReaction()` for all supports, all load cases and combinations
- `GetNodeCoordinate()` for foundation locations
- Load case and combination enumeration
- Separate service and ultimate results

**Volume:** 20-100 foundations per building. Each: 50+ load combinations to envelope. Output: 1-2 page foundation schedule + loading plan drawing.

---

## 16. Structural Redundancy / Alternate Load Path Analysis

**Source:** GSA (General Services Administration) guidelines for progressive collapse; DoD UFC 4-023-03; Eurocode 1 Part 1-7; IStructE guidance

**Workflow Name:** Progressive Collapse / Alternate Load Path Assessment

**Process Steps:**
1. Identify threat scenario (column removal locations per code):
   - Corner columns
   - Edge columns at mid-span
   - Interior columns
   - Transfer members
2. For each scenario:
   - Remove the member from model
   - Rerun analysis with applicable load combination (typically 1.2D + 0.5L per DoD)
   - Apply dynamic amplification factor (2.0 for linear static; 1.0 for nonlinear dynamic)
3. Check remaining structure:
   - Are remaining members within capacity? (allow larger utilization, e.g., tension yield OK)
   - Do connections have adequate ductility to redistribute?
   - Is vertical displacement limited (double-span deflection)?
   - Can catenary action develop in beams above removed column?
4. For inadequate cases, design remedial measures:
   - Strengthen members above removal point
   - Provide tying reinforcement for catenary action
   - Add transfer structures
   - Provide key element resistance (design removed member for extreme load)
5. Document assessment per building risk category

**Data Inputs:**
- Complete structural model
- Column removal scenarios (per code requirements)
- Load combination for accidental case
- Material ductility limits (allow higher utilization than normal)
- Connection ductility classification

**Outputs:**
- Scenario-by-scenario assessment (pass/fail)
- Maximum demand-to-capacity ratios in remaining structure
- Displacement profiles showing redistribution
- Remedial design where needed
- Robustness declaration per building class

**OpenSTAAD Role:**
- Full model modification capability (remove members programmatically)
- Rerun analysis for each scenario
- Extract forces in all remaining members
- Compare to original analysis results
- Node displacement tracking above removed member

**Volume:** Typical building: 4-20 removal scenarios. Each requires full reanalysis. Comparison of ~500 members per scenario = 2000-10000 result comparisons.

---

## Summary: Automation Potential by Workflow

| # | Workflow | OpenSTAAD Coverage | Data Volume | Automation Value |
|---|---------|-------------------|-------------|-----------------|
| 1 | Design Report | HIGH - all data available | 25,000+ extractions | Very High (days -> hours) |
| 2 | Code Compliance | HIGH - forces + sections | 200,000 verifications | Very High |
| 3 | Peer Review QA | HIGH - model + results | 1000s of checks | High (consistency) |
| 4 | Steel BOM | HIGH - sections + lengths | 200-2000 members | High (error reduction) |
| 5 | Rebar Schedule | MEDIUM - needs RCDC integration | 500-2000 bar marks | Very High (labor intensive) |
| 6 | Base Plate Design | HIGH - reactions available | 20-100 bases | High (repetitive calcs) |
| 7 | Seismic Weight | HIGH - loads + reactions + modal | 10 floors | Medium (small calc, high importance) |
| 8 | Weld Design | HIGH - member end forces | 600-2000 welds | High (repetitive) |
| 9 | Cost Estimation | HIGH - quantities derivable | Full model | Medium (rates change frequently) |
| 10 | Revision Tracking | HIGH - model comparison | Full model x2 | High (error-prone manually) |
| 11 | Load Path Verify | HIGH - connectivity + forces | Full model | High (safety-critical) |
| 12 | Performance-Based | LOW - needs NL platform | Millions of values | Low for STAAD, High overall |
| 13 | Drawing Schedule | MEDIUM - geometry only | 30-100 drawings | Medium |
| 14 | Connection Design | HIGH - member end forces | 3000-8000 checks | Very High (biggest labor item) |
| 15 | Foundation Reactions | HIGH - direct from supports | 20-100 supports x 50 LCs | High (interface document) |
| 16 | Redundancy Check | HIGH - if model modifiable | 4-20 scenarios | Very High (safety-critical) |

---

## Key Insight for MCP Server Design

These workflows share common patterns:

1. **Bulk extraction** - Get ALL results for ALL members/ALL load cases (not one at a time)
2. **Filtering/enveloping** - Find maximums, minimums, governing cases from bulk data
3. **Cross-referencing** - Link member properties to forces to design results
4. **Iteration** - Run analysis, check, modify, rerun
5. **Reporting** - Format results into professional documents with clauses and references

The MCP server needs to support **batch operations** (get all member forces in one call) rather than requiring thousands of individual API calls. The most valuable automation targets are workflows 1, 2, 14, and 5 (Report, Code Check, Connections, Rebar) which represent the largest manual labor in practice.
