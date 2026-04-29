---
name: staad-properties
description: 'Use when assigning section profiles to beams, plate thickness, materials, creating prismatic or tapered sections, or defining member specs (releases, truss, cable, offset). Covers: CreateBeamPropertyFromTable (country codes), CreateAngle/Channel/Tube/Pipe/TeePropertyFromTable, CreatePrismaticRectangle/Circle/Tee/GeneralProperty, CreateTaperedIProperty, CreatePlateThicknessProperty (array of 4 floats), AssignBeamProperty, AssignPlateThickness, CreateIsotropicMaterial, AssignMaterialToMember/Plate/Solid, CreateMemberReleaseSpec, CreateMemberTrussSpec, AssignBetaAngle, GetBeamProperty, GetSectionPropertyList. Requires staad-core.'
---

# STAAD.Pro Properties & Materials

## Instructions

- Define the shorthand once per script: `const prop = staad.Property;`

### Beam Sections from Database

```javascript
const propId = prop.CreateBeamPropertyFromTable(countryCode, sectionName, typeSpec, v1, v2);
prop.AssignBeamProperty(beamIds, propId);
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
```javascript
const code = prop.GetShapeCode(countryCode, sectionName);
if (code < 0) {
    console.log(`Section '${sectionName}' not found in country ${countryCode}`);
} else {
    const staadName = prop.GetSTAADProfileName(sectionName, countryCode);
    console.log(`Valid section: ${staadName} (shape code ${code})`);
}
```
- `GetShapeCode(country, name)` → shape code integer (negative = not found)
- `GetPublishedProfileName(name, country)` → catalog name
- `GetSTAADProfileName(name, country)` → STAAD internal name

### Prismatic Sections (User-Defined)
```javascript
const propId1 = prop.CreatePrismaticRectangleProperty(depthY, depthZ);
const propId2 = prop.CreatePrismaticCircleProperty(diameter);
const propId3 = prop.CreatePrismaticTeeProperty(depth, flangeW, stemD, stemW);
const propId4 = prop.CreatePrismaticTrapezoidalProperty(depth, topW, bottomW);
const propId5 = prop.CreatePrismaticGeneralProperty([AX, AY, AZ, IX, IY, IZ, YD, ZD, YB, ZB]);
```

### Tapered Sections
```javascript
const propId = prop.CreateTaperedIProperty([depthStart, webT, depthEnd, topW, topT, btmW, btmT]);
const propId2 = prop.CreateTaperedTubeProperty(type, startD, endD, thickness);
// type: 0=Round, 1=Hex16, 2=Dodecag, 3=Oct, 4=Hex, 5=Square
```

### Plate Thickness
```javascript
const thickId = prop.CreatePlateThicknessProperty([t, t, t, t]);  // array of 4 floats, one per node
prop.AssignPlateThickness(plateIds, thickId);
```

### Materials
```javascript
// Create
prop.CreateIsotropicMaterialProperties(name, E, poisson, G, density, alpha, damping);
prop.CreateIsotropicMaterialPropertiesEx(name, E, poisson, G, density, alpha, damping, fy, fu, ry, rt, fcu);

// Convenience
prop.CreateIsotropicMaterialSteel(name, E, poisson, G, density, alpha, damping, fu, fy, rt, ry, isPhysical);
prop.CreateIsotropicMaterialConcrete(name, E, poisson, G, density, alpha, damping, fc, physical);

// Assign
prop.AssignMaterialToMember("STEEL", memberIds);
prop.AssignMaterialToPlate("CONCRETE", plateIds);
prop.AssignMaterialToSolid("CONCRETE", solidIds);

// Query
const [E, nu, density, alpha, damp] = prop.GetMaterialProperty("STEEL");
const name = prop.GetBeamMaterialName(beamId);
```

### Beta Angle (Local Axis Rotation)
```javascript
prop.AssignBetaAngle(beamIds, angleDegrees);
const angle = prop.GetBetaAngle(beamId);
```

### Member Specs
```javascript
// Releases
const relId = prop.CreateMemberReleaseSpec(end, dofValues, springConstants);
// end: 0=start, 1=end; dofValues: [FX,FY,FZ,MX,MY,MZ] → 0=fixed, 1=released
prop.AssignMemberSpecToBeam(beamIds, relId);

// Special member types
const trussId = prop.CreateMemberTrussSpec();
const tensId  = prop.CreateMemberTensionSpec();
const compId  = prop.CreateMemberCompressionSpec();
const cableId = prop.CreateMemberCableSpec(tensionOrLength, value);
const inactId = prop.CreateMemberInactiveSpec();
```

### Querying

| Function | Returns |
|----------|---------|
| `GetSectionPropertyCount()` | total section properties |
| `GetSectionPropertyList()` | array of property IDs |
| `GetSectionPropertyName(sid)` | section name string |
| `GetSectionPropertyAssignedBeamList(sid)` | beams using that section |
| `GetBeamSectionName(bid)` | section name for beam |
| `GetBeamProperty(bid)` | `[w, d, AX, AY, AZ, IZ, IY, IX]` |
| `GetBeamPropertyAll(bid)` | adds `tf, tw` to above |
| `GetPlateThickness(pid)` | array of 4 floats |
| `GetThicknessPropertyCount()` | total thickness properties |

## Examples
- [assign-beam-sections.js](./scripts/assign-beam-sections.js) — create and assign a W-section
- [assign-plate-thickness.js](./scripts/assign-plate-thickness.js) — assign plate thickness
- [create-floor-plates.js](./scripts/create-floor-plates.js) — create plates and assign thickness

## Gotchas
- `CreatePlateThicknessProperty` takes an **array of 4 floats**, one value per corner — not a single scalar
- Always retrieve actual IDs via `GetBeamList()` / `GetPlateList()` before assigning — never assume IDs start at 1
- `GetMemberDesignSectionName(bid)` throws an error when results are unavailable — use `GetSectionPropertyName` for pre-analysis lookup
- Built-in material names: `"STEEL"`, `"CONCRETE"`, `"ALUMINUM"` — case-sensitive
