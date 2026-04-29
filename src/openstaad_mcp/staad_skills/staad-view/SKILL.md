---
name: staad-view
description: 'Use when controlling the STAAD.Pro user interface: camera views, show/hide elements, labels, result diagrams, annotations, screenshots, window management, saved views, display scales, or switching between modeling and post-processing modes. Covers: SetInterfaceMode, ShowIsometric, ShowPlan, ShowFront, ZoomExtentsMainView, ZoomAll, ShowMember, HideMember, ShowAllMembers, SetLabel (node/beam numbers), SetDiagramMode (displacement/moment/shear diagrams), SetDesignResults (utilization ratios), ExportView (screenshot to file), CopyPicture (clipboard), SelectMembersParallelTo, SetSectionView (clipping plane), SaveView, SetWindowPosition. Requires staad-core.'
---

# STAAD.Pro View Control

All view operations go through `const view = staad.View;`.

## Interface Modes
```javascript
view.SetInterfaceMode(0);   // 0=Modeling, 5=Post-processing, 6=Foundation, 9=Adv Concrete

// Set page within a mode
view.SetModeSectionPage(interfaceMode, sectionNumber, pageNumber);
```

## Standard Views
```javascript
view.ShowIsometric();
view.ShowPlan();       // top
view.ShowFront();
view.ShowBack();
view.ShowLeft();
view.ShowRight();
view.ShowBottom();
view.ZoomExtentsMainView();
view.ZoomAll();
view.RefreshView();
```

## Rotation
```javascript
view.SpinLeft(degrees);
view.SpinRight(degrees);
view.RotateUp(degrees);
view.RotateDown(degrees);
view.RotateLeft(degrees);
view.RotateRight(degrees);
```

## Show/Hide Elements
```javascript
view.ShowAllMembers();
view.HideAllMembers();
view.ShowMember(memberNo);
view.HideMember(memberNo);
view.HidePlate(plateNo);
view.HideSolid(solidNo);
view.ShowMembers(NMembers, NaMemberNos);
view.HideMembers(NMembers, NaMemberNos);
```

## Selection (View-Based)
```javascript
view.SelectMembersParallelTo("Y");               // all vertical members
view.SelectGroup("ALL");                          // by group name
view.SelectInverse(entityType);                   // 0=node, 1=beam, 2=plate, 3=solid
view.SelectByItemList(entityType, nItems, itemList);
view.SelectEntitiesConnectedToNode(entityType, nodeNo);
view.SelectByMissingAttribute(attributeCode);     // e.g. 4=missing supports
```

## Labels
```javascript
// which: 0=NodeNos, 1=BeamNos, 4=SupportLabels, 8=LoadValues
view.SetLabel(which, true);   // show
view.SetLabel(which, false);  // hide
```

## Result Diagrams
```javascript
// which: 0=Load, 1=Displacement, 3=MZ, 4=FY, 5=FX (axial)
view.SetDiagramMode(which, true, true);   // show, refresh
```

## Annotations
```javascript
view.SetNodeAnnotationMode(true, true);         // dFlag, refreshFlag
view.SetReactionAnnotationMode(true, true);
view.SetBeamAnnotationMode(Type, DWFlags, RefreshFlag);

// Design results overlay
view.SetDesignResults(
    1,      // utilization: 0=None, 1=Actual Ratio, 2=Normalised
    true,   // color
    true    // showValues
);
```

## Section View (Clipping Plane)
```javascript
view.SetSectionView(plane, minVal, maxVal);  // plane: 0=XY, 1=YZ, 2=XZ
```

## Screenshots
```javascript
// Export to file
const status = view.ExportView(fileLocation, fileName, fileFormat, overwrite);
// fileFormat: 0=bmp, 1=jpg, 2=tga, 3=tif; returns 1=OK, -1=error

// Copy to clipboard
const [x, y] = view.CopyPicture();
```

## Window Management
```javascript
const size = view.GetApplicationDesktopSize();
view.SetWindowPosition(xTop, yTop, xWindow, yWindow);
const count = view.GetWindowCount();
const title = view.GetWindowTitle(id);   // IDs from 1
view.SetActiveWindow(id);
view.CreateNewViewForSelections();
view.CloseActiveWindow();
```

## Saved Views
```javascript
view.SaveView("MyView", true);               // overWrite
view.OpenView("MyView", true);                // windowOptions: true=current window
view.RenameView("NewName");
```

## Diagram Scales
See **[VIEW_CODES.md — Scale Type IDs](./assets/VIEW_CODES.md)** for the full `scaleTypeId` → enum name → unit table.

```javascript
const scales = view.GetScaleValues();
view.SetScaleValues(scales);
view.SetScaleValueByType(scaleTypeId, value);
// After changing scale, toggle diagram off/on to force redraw:
view.SetDiagramMode(diagramId, false, true);
view.SetScaleValueByType(scaleTypeId, value);
view.SetDiagramMode(diagramId, true, true);
view.RefreshView();
```

> **Scale is INVERSE:** `visual_displacement = actual / scale`
> Smaller value → more exaggerated deformed shape.
> To target a specific visual size: `scale = max_actual_disp / target_visual_disp`
> e.g. for max_disp=0.06 in and target visual=94 in: `scale = 0.06 / 94 ≈ 0.00064`

## Display Units
```javascript
// uType: 0=Dimension, 1=Displacement, 5=Force, 6=Moment, 14=Stress
view.SetUnits(uType, strUnit);   // e.g. SetUnits(5, "kN")
```

## Example
See [take-screenshot.js](./scripts/take-screenshot.js)

## Gotchas
- Switch to post-processing mode (`SetInterfaceMode(5)`) before showing result diagrams; always call `staad.ShowApplication()` first
- Do not try to read back the interface mode after setting it — the value is unreliable; trust that `SetInterfaceMode` applies correctly
- `ExportView` returns -1003 if the file already exists and overwrite=false
- Selection via `view.SelectByItemList` should be avoided for geometry — use `geo.SelectMultipleBeams` instead
