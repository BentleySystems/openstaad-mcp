---
name: staad-view
description: "Use when controlling the STAAD.Pro user interface: camera views, show/hide elements, labels, result diagrams, annotations, screenshots, export to image, window management, saved views, display scales, or switching between modeling and post-processing modes. Covers: SetInterfaceMode, ShowIsometric, ShowPlan, ShowFront, ZoomExtentsMainView, ZoomAll, ShowMember, HideMember, ShowAllMembers, SetLabel (node/beam numbers), SetDiagramMode (displacement/moment/shear diagrams), SetDesignResults (utilization ratios), CopyPicture (clipboard), ExportView (save view as PNG/JPG/BMP/EMF/WMF — path-validated), SelectMembersParallelTo, SetSectionView (clipping plane), SaveView, SetWindowPosition. Requires staad-core."
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
```

## Selection (View-Based)

```python
view.SelectMembersParallelTo("Y")               # all vertical members
view.SelectGroup("ALL")                          # by group name
view.SelectInverse(entityType)                   # 0=node, 1=beam, 2=plate, 3=solid
view.SelectByItemList(entityType, nItems, itemList)
view.SelectEntitiesConnectedToNode(entityType, nodeNo)
view.SelectByMissingAttribute(attributeCode)     # e.g. 4=missing supports
```

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

```python
# Copy to clipboard
x, y = view.CopyPicture()
```

## Export View to File

`ExportView` saves the current view as an image file. It takes a **directory** and a **filename** as separate arguments. The combined path is validated by the sandbox.

```python
# ExportView(directory, filename, formatCode, flag)

# Export to PNG
view.ExportView("C:\\exports", "front_view.png", 3, 0)

# Export to JPG
view.ExportView("C:\\exports", "iso_view.jpg", 2, 0)

# Export to BMP
view.ExportView("C:\\exports", "plan_view.bmp", 1, 0)

# Export to EMF (vector)
view.ExportView("C:\\exports", "detail.emf", 4, 0)
```

**Path rules** (enforced on the combined `directory\filename` — violations raise an error):

- The combined path **must be absolute**
- The filename **must end with** `.png`, `.jpg`, `.jpeg`, `.bmp`, `.emf`, or `.wmf`
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
view.CreateNewViewForSelections()
view.CloseActiveWindow()
```

## Saved Views

```python
view.SaveView("MyView", overWrite=True)
view.OpenView("MyView", windowOptions=True)  # True=current window
view.RenameView("NewName")
```

## Diagram Scales

See **[VIEW_CODES.md — Scale Type IDs](./assets/VIEW_CODES.md)** for the full `scaleTypeId` → enum name → unit table.

```python
scales = view.GetScaleValues()
view.SetScaleValues(scales)
view.SetScaleValueByType(scaleTypeId, value)
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

## Gotchas

- Switch to post-processing mode (`SetInterfaceMode(5)`) before showing result diagrams; always call `staad.ShowApplication()` first
- Do not try to read back the interface mode after setting it — the value is unreliable; trust that `SetInterfaceMode` applies correctly
- Selection via `view.SelectByItemList` should be avoided for geometry — use `geo.SelectMultipleBeams` instead
- `ExportView(directory, filename, ...)` takes a **directory** and **filename** as separate arguments; the combined path must be absolute, end with a supported image extension (`.png`, `.jpg`, `.jpeg`, `.bmp`, `.emf`, `.wmf`), and not target a protected OS directory; UNC paths and `..` traversal are rejected
