# Tutorial 2: RC Framed Structure - MCP Walkthrough

Completed April 23, 2026 using the OpenSTAAD MCP server and GitHub Copilot in VS Code.

## What this is

A full end-to-end run of [Bentley's STAAD.Pro Tutorial 2](https://docs.bentley.com/LiveContent/web/STAAD.Pro%20Help-v2024/en/topics/Getting_Started/Tutorial%20Problem%202/c-stpst_TUT02_RC_Framed_Structure.html) (RC Framed Structure), driven entirely through the MCP server rather than the STAAD.Pro GUI. The goal was to validate that the MCP can handle a realistic modeling and analysis workflow from scratch.

## Tutorial description

The structure is a 2-bay, 1-story reinforced concrete frame with 6 joints and 5 members. The tutorial covers geometry creation, prismatic section assignment, material constants, P-Delta analysis, and ACI 318-14 concrete design for beams and columns.

## Steps completed

| # | Tutorial step | How it was done via MCP |
|---|--------------|------------------------|
| 1 | Create new structure | Wrote the `.std` command file directly, opened with `OpenSTAADFile` |
| 2 | Define geometry | 6 joints, 5 members matching tutorial coordinates exactly |
| 3 | Assign member properties | Prismatic rectangular (300x275, 350x275) and circular (350mm dia) |
| 4 | Set material constants | E=22 kN/mm2, Density=25 kN/m3, Poisson=0.17 |
| 5 | Beta angle | 90 degrees on member 4 |
| 6 | Fixed supports | Nodes 1, 4, 5 |
| 7 | Dead load (LC1) | Self-weight Y -1 + UNI GY -400 kgf/m on beams 2,5 |
| 8 | Live load (LC2) | UNI GY -600 kgf/m on beams 2,5 |
| 9 | Wind load (LC3) | UNI GX +300 kgf/m on member 1, +500 kgf/m on member 4 |
| 10 | Repeat loads | LC4 = 1.2*Dead + 1.5*Live, LC5 = 1.1*Dead + 1.3*Wind |
| 11 | P-Delta analysis | `PDELTA ANALYSIS` command, ran via `AnalyzeEx` |
| 12 | Concrete design | ACI 318-14, CLT=25, CLB=30, CLS=25, FC=25, FYMAIN=415 |
| 13 | View output file | Read the `.ANL` file, confirmed no errors |
| 14 | Node displacements | Pulled via `GetNodeDisplacements` for all nodes and load cases |
| 15 | Beam forces table | Pulled via `GetMemberEndForces` for all members, LC4 and LC5 |
| 16 | Member query | `GetMinMaxBendingMoment`, `GetMinMaxShearForce`, `GetMinMaxAxialForce` |
| 17 | Support reactions | `GetSupportReactions` at nodes 1, 4, 5 for LC4 and LC5 |

## Concrete design results summary

All 5 members passed ACI 318-14 design. From the `.ANL` output:

| Member | Type | Status | Critical Ratio | Criteria | Clause |
|--------|------|--------|----------------|----------|--------|
| 1 | Column (Rect 275x300) | Pass | 0.634 | Flexure | 10.5.2 |
| 2 | Beam (Rect 275x350) | Pass | 1.000 | Torsion | 9.5.3/9.5.4 |
| 3 | Column (Circular 350) | Pass | 0.812 | Flexure | 10.5.2 |
| 4 | Column (Rect 275x300) | Pass | 1.000 | Torsion | 10.5.3/10.5.4 |
| 5 | Beam (Rect 275x350) | Pass | 1.000 | Torsion | 9.5.3/9.5.4 |

These match the expected results from the Bentley tutorial documentation.

## Environment

- STAAD.Pro 2025 (v25.00.01.424)
- OpenSTAAD MCP Server v2.0.0
- Python 3.14, fastmcp 3.2.4, extism 1.1.1
- GitHub Copilot (Claude) in VS Code

## Evidence files

- [Tutorial2_RC_Frame.std](Tutorial2_RC_Frame.std) - The STAAD input command file
- [Tutorial2_RC_Frame.ANL](Tutorial2_RC_Frame.ANL) - Full analysis output with concrete design results
