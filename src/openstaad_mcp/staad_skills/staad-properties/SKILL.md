---
name: staad-properties
description: 'Use when assigning section profiles to beams, plate thickness, materials, creating prismatic or tapered sections, or defining member specs (releases, truss, cable, offset). Covers: CreateBeamPropertyFromTable (country codes), CreateAngle/Channel/Tube/Pipe/TeePropertyFromTable, CreatePrismaticRectangle/Circle/Tee/GeneralProperty, CreateTaperedIProperty, CreatePlateThicknessProperty (list of 4 floats), AssignBeamProperty, AssignPlateThickness, CreateIsotropicMaterial, AssignMaterialToMember/Plate/Solid, CreateMemberReleaseSpec, CreateMemberTrussSpec, AssignBetaAngle, GetBeamProperty, GetSectionPropertyList. Requires staad-core.'
---

# STAAD.Pro Properties & Materials

## Instructions

- Define the shorthand once per script: `prop = staad.Property`

### Beam Sections from Database

```python
prop_id = prop.CreateBeamPropertyFromTable(countryCode, sectionName, typeSpec, v1, v2)
prop.AssignBeamProperty(beam_ids, prop_id)
```

**Country codes:** 1=American, 2=Australian, 3=British, 4=Canadian, 5=Chinese, 6=Dutch, 7=European, 8=French, 9=German, 10=Indian, 11=Japanese, 12=Russian, 13=SouthAfrican, 14=Spanish, 15=Venezuelan, 16=Korean

**Type spec:** 0=ST (standard), 2=D (double), 5=T (tee), 6=CM (composite), 7=TC (top cover), 8=BC (bottom cover), 9=TB (top+bottom cover)

**Specialized shape creation:**

| Function | Shape |
|----------|-------|
| `CreateAnglePropertyFromTable(country, name, spec, addSpec)` | Angle (L) |
| `CreateChannelPropertyFromTable(country, name, spec, addSpec)` | Channel (C) |
| `CreateTubePropertyFromTable(country, name, spec, v1, v2, v3)` | Hollow rectangular |
| `CreatePipePropertyFromTable(country, name, spec, v1, v2)` | Hollow circular |
| `CreateTeePropertyFromTable(country, name, spec)` | Tee (WT) |
| `CreateWideFlangePropertyFromTable(country, name, spec, specsList)` | Wide flange extended |

**Name helpers — CRITICAL validation workflow:**
Before calling `CreateBeamPropertyFromTable`, validate the section name exists in the database:
```python
code = prop.GetShapeCode(countryCode, sectionName)
if code < 0:
    print(f"Section '{sectionName}' not found in country {countryCode}")
else:
    staad_name = prop.GetSTAADProfileName(sectionName, countryCode)
    print(f"Valid section: {staad_name} (shape code {code})")
```
- `GetShapeCode(country, name)` → shape code integer (negative = not found)
- `GetPublishedProfileName(name, country)` → catalog name
- `GetSTAADProfileName(name, country)` → STAAD internal name

### Prismatic Sections (User-Defined)
```python
prop_id = prop.CreatePrismaticRectangleProperty(depthY, depthZ)
prop_id = prop.CreatePrismaticCircleProperty(diameter)
prop_id = prop.CreatePrismaticTeeProperty(depth, flangeW, stemD, stemW)
prop_id = prop.CreatePrismaticTrapezoidalProperty(depth, topW, bottomW)
prop_id = prop.CreatePrismaticGeneralProperty([AX,AY,AZ,IX,IY,IZ,YD,ZD,YB,ZB])
```

### Tapered Sections
```python
prop_id = prop.CreateTaperedIProperty([depth_start, web_t, depth_end, top_w, top_t, btm_w, btm_t])
prop_id = prop.CreateTaperedTubeProperty(type, start_d, end_d, thickness)
# type: 0=Round, 1=Hex16, 2=Dodecag, 3=Oct, 4=Hex, 5=Square
```

### Plate Thickness
```python
thick_id = prop.CreatePlateThicknessProperty([t, t, t, t])  # list of 4 floats, one per node
prop.AssignPlateThickness(plate_ids, thick_id)
```

### Materials
```python
# Create
prop.CreateIsotropicMaterialProperties(name, E, poisson, G, density, alpha, damping)
prop.CreateIsotropicMaterialPropertiesEx(name, E, poisson, G, density, alpha, damping, fy, fu, ry, rt, fcu)

# Convenience
prop.CreateIsotropicMaterialSteel(name, E, poisson, G, density, alpha, damping, fu, fy, rt, ry, is_physical)
prop.CreateIsotropicMaterialConcrete(name, E, poisson, G, density, alpha, damping, fc, physical)

# Assign
prop.AssignMaterialToMember("STEEL", member_ids)
prop.AssignMaterialToPlate("CONCRETE", plate_ids)
prop.AssignMaterialToSolid("CONCRETE", solid_ids)

# Query
E, nu, density, alpha, damp = prop.GetMaterialProperty("STEEL")
name = prop.GetBeamMaterialName(beam_id)
```

### Beta Angle (Local Axis Rotation)
```python
prop.AssignBetaAngle(beam_ids, angle_degrees)
angle = prop.GetBetaAngle(beam_id)
```

### Member Specs
```python
# Releases
rel_id = prop.CreateMemberReleaseSpec(end, dofValues, springConstants)
# end: 0=start, 1=end; dofValues: [FX,FY,FZ,MX,MY,MZ] → 0=fixed, 1=released
prop.AssignMemberSpecToBeam(beam_ids, rel_id)

# Special member types
truss_id = prop.CreateMemberTrussSpec()
tens_id  = prop.CreateMemberTensionSpec()
comp_id  = prop.CreateMemberCompressionSpec()
cable_id = prop.CreateMemberCableSpec(tension_or_length, value)
inact_id = prop.CreateMemberInactiveSpec()
```

### Querying

| Function | Returns |
|----------|---------|
| `GetSectionPropertyCount()` | total section properties |
| `GetSectionPropertyList()` | list of property IDs |
| `GetSectionPropertyName(sid)` | section name string |
| `GetSectionPropertyAssignedBeamList(sid)` | beams using that section |
| `GetBeamSectionName(bid)` | section name for beam |
| `GetBeamProperty(bid)` | `(w, d, AX, AY, AZ, IZ, IY, IX)` |
| `GetBeamPropertyAll(bid)` | adds `tf, tw` to above |
| `GetPlateThickness(pid)` | list of 4 floats |
| `GetThicknessPropertyCount()` | total thickness properties |

## Examples
- [assign-beam-sections.py](./scripts/assign-beam-sections.py) — create and assign a W-section
- [assign-plate-thickness.py](./scripts/assign-plate-thickness.py) — assign plate thickness
- [create-floor-plates.py](./scripts/create-floor-plates.py) — create plates and assign thickness

## Gotchas
- `CreatePlateThicknessProperty` takes a **list of 4 floats**, one value per corner — not a single scalar
- Always retrieve actual IDs via `GetBeamList()` / `GetPlateList()` before assigning — never assume IDs start at 1
- `GetMemberDesignSectionName(bid)` raises an error when results are unavailable — use `GetSectionPropertyName` for pre-analysis lookup
- Built-in material names: `"STEEL"`, `"CONCRETE"`, `"ALUMINUM"` — case-sensitive
