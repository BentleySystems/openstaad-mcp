---
name: staad-view
description: "Use when controlling the STAAD.Pro user interface: camera views, show/hide elements, labels, result diagrams, annotations, screenshots, export to image, window management, saved views, display scales, or switching between modeling and post-processing modes. Covers: SetInterfaceMode, GetInterfaceMode, ShowIsometric, ShowPlan, ShowFront, ZoomExtentsMainView, ZoomAll, ShowMember, HideMember, HideEntity, HideSurface, ShowAllMembers, SetLabel (node/beam numbers), SetDiagramMode (displacement/moment/shear diagrams), SetStressType (plate/solid stress contour type), SetDesignResults (utilization ratios), CopyPicture (clipboard), ExportView (save view as BMP/JPG/TGA/TIF — path-validated), SelectMembersParallelTo, SetSectionView (clipping plane), SaveView, DetachView, CreateNewViewForSelectionsEx, GetScaleCount, GetScaleValueByType, SetWindowPosition. Requires staad-core."
---

# STAAD.Pro View Control

All view operations go through `view = staad.View`.

## Interface Modes

```python
view.SetInterfaceMode(0)   # 0=Modeling, 5=Post-processing, 6=Foundation, 9=Adv Concrete

# Set page within a mode
view.SetModeSectionPage(interfaceMode, sectionNumber, pageNumber)
```

## Standard Views

```python
view.ShowIsometric()
view.ShowPlan()       # top
view.ShowFront()
view.ShowBack()
view.ShowLeft()
view.ShowRight()
view.ShowBottom()
view.ZoomExtentsMainView()
view.ZoomAll()
view.RefreshView()
```

## Rotation

```python
view.SpinLeft(degrees)
view.SpinRight(degrees)
view.RotateUp(degrees)
view.RotateDown(degrees)
view.RotateLeft(degrees)
view.RotateRight(degrees)
```

## Show/Hide Elements

```python
view.ShowAllMembers()
view.HideAllMembers()
view.ShowMember(memberNo)
view.HideMember(memberNo)
view.HidePlate(plateNo)
view.HideSolid(solidNo)
view.ShowMembers(NMembers, NaMemberNos)
view.HideMembers(NMembers, NaMemberNos)
view.HideEntity(entityNo)     # hides any entity type (Beam/Plate/Solid/Surface) by number, no type argument needed
view.HideSurface(surfaceNo)

count = view.GetNoOfBeamsInView()
# GetBeamsInView(beamList) does NOT populate beamList (verified live) — it only returns the count, same as GetNoOfBeamsInView(). Use geo.GetBeamList() to get actual beam IDs.
```

## Selection (View-Based)

```python
view.SelectMembersParallelTo("Y")               # all vertical members
view.SelectGroup("ALL")                          # by group name
view.SelectInverse(entityType)                   # 1=Node, 2=Beam, 3=Plate, 4=Solid, 5=Surface
view.SelectByItemList(entityType, nItems, itemList)  # same codes as SelectInverse
view.SelectEntitiesConnectedToNode(entityType, nodeNo)      # 0=Geometry, 1=Beam, 2=Plate, 3=Solid (different codes, no Node option)
view.SelectEntitiesConnectedToMember(entityType, memberNo)  # same codes as ConnectedToNode
view.SelectEntitiesConnectedToPlate(entityType, plateNo)    # same codes as ConnectedToNode
view.SelectEntitiesConnectedToSolid(entityType, solidNo)    # same codes as ConnectedToNode
view.SelectByMissingAttribute(attributeCode)     # e.g. 4=missing supports
```

**Two different `entityType` conventions exist** — don't assume one table applies to all `Select*` functions:
- `SelectInverse`/`SelectByItemList`: `1=Node, 2=Beam, 3=Plate, 4=Solid, 5=Surface`
- `SelectEntitiesConnectedTo*`: `0=Geometry, 1=Beam, 2=Plate, 3=Solid` (no dedicated Node code)

## Labels

Common `which` values (full table in the Reference section — VIEW_CODES.md):

| which | Label         |
| ----- | ------------- |
| 0     | Node number   |
| 1     | Member number |
| 4     | Support       |
| 8     | Load value    |

```python
view.SetLabel(which, True)   # show
view.SetLabel(which, False)  # hide
```

## Result Diagrams

Common `which` values (full table in the Reference section — VIEW_CODES.md):

| which | Diagram      |
| ----- | ------------ |
| 0     | Load         |
| 1     | Displacement |
| 2     | MY           |
| 3     | MZ           |
| 4     | FY           |
| 5     | FZ           |
| 6     | Axial (AX)   |
| 7     | Torsion (TR) |

```python
view.SetDiagramMode(which, show=True, refresh=True)
```

### Plate/Solid Stress Type

`SetStressType` picks which stress component the Plate Stress (`which=20`) or Solid Stress
(`which=21`) contour shows, and recomputes its legend range for the currently active load case
(`Load.SetLoadActive`). Enable the diagram first via `SetDiagramMode`, then call `SetStressType`:

```python
view.SetActiveWindow(1)                       # REQUIRED before any diagram/export call — see Gotchas
view.ShowIsometric()
view.SetDiagramMode(20, True, False)         # enable Plate Stress diagram; skip refresh, next call refreshes
view.SetStressType(20, 8, True)              # entityType=20 Plate, stressType=8 Max Von Mises
```

`entityType`: `20`=Plate Stress, `21`=Solid Stress.

**Before calling `SetStressType`, read [VIEW_CODES.md](./assets/VIEW_CODES.md) for the full `stressType`
tables (31 plate values, 10 solid values) and use the exact integer code from it — never guess or
trial-and-error multiple values.** VIEW_CODES.md also lists each code's exact `UI Label` (the literal
text in the Diagrams > Plate/Solid Stress dialog's Type combo box) — several differ from the
descriptive name (e.g. FX/FY/FXY show as "SX (local)"/"SY (local)"/"SXY (local)"; stressType 19 shows
"MXY (local)", not "MZ"); match a user's request against `UI Label`, not just the descriptive name.
Common plate values for quick reference: `1`=Max Absolute, `8`=Max Von Mises.

## Annotations

```python
view.SetNodeAnnotationMode(dFlag=True, refreshFlag=True)
view.SetReactionAnnotationMode(dFlag=True, refreshFlag=True)
view.SetBeamAnnotationMode(Type, DWFlags, RefreshFlag)

# Design results overlay
view.SetDesignResults(
    utilization=1,   # 0=None, 1=Actual Ratio, 2=Normalised
    color=True,
    showValues=True
)
```

## Section View (Clipping Plane)

```python
view.SetSectionView(plane, minVal, maxVal)  # plane: 0=XY, 1=YZ, 2=XZ
```

## Screenshots

**Always call `view.SetActiveWindow(id)` immediately before `CopyPicture`/`ExportView`** — a STAAD.Pro session commonly has multiple windows open (e.g. `<Untitled 1>` main 3D view plus `Nodes`/`Beams` spreadsheet windows; check with `view.GetWindowCount()`/`GetWindowTitle(id)`). Without it, the capture can silently come from whichever window was last active — a spreadsheet, or a stale view left over from earlier in the session — with NO error, just a wrong or blank-looking image. `id=1` is the right choice for the common case (freshly opened model, main view untouched) — but `ExportView`/`CopyPicture` intentionally never assume this for you, so a script that created or opened a DIFFERENT window (`CreateNewViewForSelectionsEx`, `OpenView`, a saved view) must pass that window's own id, not `1`.

```python
# Copy to clipboard
view.SetActiveWindow(1)   # 1 = main view for a freshly opened model; use the real id if targeting another window
x, y = view.CopyPicture()
```

## Export View to File

`ExportView` saves the current view as an image file. It takes a **directory** and a **filename** as separate arguments. The combined path is validated by the sandbox. **Call `view.SetActiveWindow(id)` first** (see Screenshots above) — this is the single most common cause of a wrong/stale capture.

```python
# ExportView(directory, fileName, fileFormat, overwrite)
# fileFormat: 0=bmp, 1=jpg, 2=tga, 3=tif — no other formats are supported

view.SetActiveWindow(1)   # main view for a freshly opened model

# Export to TIF
view.ExportView("C:\\exports", "iso_view.tif", 3, True)

# Export to JPG
view.ExportView("C:\\exports", "iso_view.jpg", 1, True)

# Export to BMP
view.ExportView("C:\\exports", "plan_view.bmp", 0, True)
```

**Always include the matching extension in `fileName`** (`.bmp` for format 0, `.jpg`/`.jpeg` for 1, `.tga` for 2, `.tif`/`.tiff` for 3). STAAD.Pro's own `MakeFilePath` appends the `fileFormat` extension on top of whatever `fileName` is given — on some builds this doubles the extension (e.g. `iso_view.tif.tif`), on others (where a native fix has landed) it does not. **Never assume which happened** — after calling `ExportView`, list the target directory to see the real filename on disk before reporting a path back to the user or reading the file back.

**Path rules** (enforced on the combined `directory\filename` — violations raise an error):

- The combined path **must be absolute**
- The filename must end with `.bmp`, `.jpg`, `.jpeg`, `.tga`, `.tif`, or `.tiff`, matching the `fileFormat` code used — any other extension, or a mismatched one, is rejected (a bare filename with no extension is also accepted by the sandbox, though not recommended — see above)
- UNC paths (`\\\\server\\share\\...`) are **blocked**
- Paths targeting protected OS directories (`Windows`, `Program Files`, `ProgramData`) are **blocked**
- Path traversal (`..`) in either directory or filename is **blocked**

## Window Management

```python
size = view.GetApplicationDesktopSize()
view.SetWindowPosition(xTop, yTop, xWindow, yWindow)
count = view.GetWindowCount()
title = view.GetWindowTitle(id)   # IDs from 1
view.SetActiveWindow(id)
view.CreateNewViewForSelectionsEx(windowOptions)  # windowOptions: 0=new window, 1=active window (preferred — CreateNewViewForSelections() also available, always opens a new window)
view.CloseActiveWindow()

mode = view.GetInterfaceMode()   # 0=modeling, 1=post-processing, 2=STAAD.etc interop, 4=Piping, 5=BEAVA
view.SetInterfaceMode(interfaceMode)
```

## Saved Views

```python
view.SaveView("MyView", overWrite=True)
view.OpenView("MyView", windowOptions=True)  # True=current window
view.RenameView("NewName")
view.DetachView()   # removes the active (open, non-"Whole Structure") view from the saved-views collection; returns 1=OK, 0=failed
```

## Diagram Scales

See **[VIEW_CODES.md — Scale Type IDs](./assets/VIEW_CODES.md)** for the full `scaleTypeId` → enum name → unit table.

```python
scales = view.GetScaleValues()
view.SetScaleValues(scales)
view.SetScaleValueByType(scaleTypeId, value)
count = view.GetScaleCount()
value = view.GetScaleValueByType(scaleTypeId)   # single-value counterpart to GetScaleValues, in base units
# After changing scale, toggle diagram off/on to force redraw:
view.SetDiagramMode(diagramId, False, True)
view.SetScaleValueByType(scaleTypeId, value)
view.SetDiagramMode(diagramId, True, True)
view.RefreshView()
```

> **Scale is INVERSE:** `visual_displacement = actual / scale`
> Smaller value → more exaggerated deformed shape.
> To target a specific visual size: `scale = max_actual_disp / target_visual_disp`
> e.g. for max_disp=0.06 in and target visual=94 in: `scale = 0.06 / 94 ≈ 0.00064`

## Display Units

```python
# uType: 0=Dimension, 1=Displacement, 5=Force, 6=Moment, 14=Stress
view.SetUnits(uType, strUnit)   # e.g. SetUnits(5, "kN")
```

## Examples

- [export-plate-stress.py](./scripts/export-plate-stress.py) — export a Von Mises plate-stress contour screenshot per load case

## Gotchas

- **`which`/`entityType`/`stressType` and every other enum-style parameter in this skill are ALWAYS integers, never strings.** Use the exact documented code from its table (Result Diagrams, Plate/Solid Stress Type, Label Codes, etc. above, or VIEW_CODES.md) — do not trial-and-error/probe multiple values hoping one works, and do not pass the enum's name as a string. If a table looks truncated or incomplete in context, re-read the specific section/asset rather than guessing.
- **`view.SetActiveWindow(id)` is REQUIRED before `CopyPicture`/`ExportView`/any diagram screenshot workflow** — a session can have multiple windows open (main 3D view plus spreadsheet windows like `Nodes`/`Beams`, plus any extra windows from `CreateNewViewForSelectionsEx`/`OpenView`); skipping this call has been reproduced live to silently capture the wrong (or a stale, leftover-from-earlier-in-the-session) window with no error at all — not a rare edge case, verify with `view.GetWindowCount()`/`GetWindowTitle(id)` if in doubt. `id=1` is the right default ONLY for the common case of a freshly opened model's main view — if the script itself just created or opened a different window (e.g. via `CreateNewViewForSelectionsEx`/`OpenView`/`SaveView`+`OpenView` for a saved view), target THAT window's actual id instead of hardcoding `1`.
- `ExportView`/`CopyPicture` intentionally do NOT force window 1 internally — they operate on whatever window is currently active, which is what makes multi-window workflows (export several saved views in one script, or a view built from a specific selection) possible. Always call `SetActiveWindow(id)` explicitly for the window you mean immediately before the capture call, every single time, even if you just switched windows moments earlier in the same script.
- Switch to post-processing mode (`SetInterfaceMode(5)`) before showing result diagrams; always call `staad.ShowApplication()` first
- Do not try to read back the interface mode after setting it — the value is unreliable; trust that `SetInterfaceMode` applies correctly. `GetInterfaceMode()` on its own (not right after a `SetInterfaceMode` call) is reliable — verified live, correctly returned `0` on a freshly opened model in modeling mode
- `GetBeamsInView(beamList)` does **not** populate the passed list — verified live, the list is unchanged after the call and the return value is just the count (identical to `GetNoOfBeamsInView()`). Use `geo.GetBeamList()` for actual beam IDs.
- Selection via `view.SelectByItemList` should be avoided for geometry — use `geo.SelectMultipleBeams` instead
- `geo.ClearMemberSelection()` empties the whole accumulated `Geometry`-side selection in one call (verified live), but raises `OsNoBeamSelected` if the selection is already empty — guard it:
  ```python
  try:
      geo.ClearMemberSelection()
  except Exception:
      pass  # was already empty
  ```
  Beams selected via `staad.View` functions (e.g. `view.SelectByItemList`) are a separate selection track and can survive a `geo.ClearMemberSelection()` call — clear both sides if you mixed `view.Select*` and `geo.Select*` calls.
- Prefer `geo.Select*` over `view.Select*` when both cover the same case (e.g. `geo.IsColumn`/`geo.IsBeam` for axis-aligned member selection instead of `view.SelectMembersParallelTo`) — but `view.Select*` functions with no `geo` equivalent (`SelectGroup`, `SelectInverse`, `SelectByMissingAttribute`, `SelectEntitiesConnectedToNode`, etc.) are fine to use directly:
  ```python
  # geo equivalent of view.SelectMembersParallelTo("Y") for a Y-up model
  all_beams = list(geo.GetBeamList())
  vertical_ids = [b for b in all_beams if geo.IsColumn(b, 5.0)]   # tol in degrees
  geo.SelectMultipleBeams(vertical_ids)
  # geo.IsBeam(bid, tol) is the horizontal equivalent; neither covers arbitrary
  # non-cardinal axes, which only view.SelectMembersParallelTo supports
  ```
- `ExportView(directory, filename, ...)` takes a **directory** and **filename** as separate arguments; the combined path must be absolute, end with a supported image extension (`.bmp`, `.jpg`, `.jpeg`, `.tga`, `.tif`, `.tiff`), and not target a protected OS directory; UNC paths and `..` traversal are rejected. Whether the written file's extension ends up doubled (e.g. `"a.tif"` → `a.tif.tif` on disk) depends on the STAAD.Pro build — always verify the real filename on disk rather than assuming either way (see Export View to File above)
