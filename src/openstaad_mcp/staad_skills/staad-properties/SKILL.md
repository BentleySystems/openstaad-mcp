---
name: staad-properties
description: "Use when assigning section profiles to beams, plate thickness, materials, creating prismatic or tapered sections, or defining member specs (releases, truss, tension, compression, cable, inactive, offset). Covers: CreateBeamPropertyFromTable (country codes), CreateAngle/Channel/Tube/Pipe/TeePropertyFromTable, CreateBeamPropertyFromTableEx, CreatePrismaticRectangle/Circle/Tee/GeneralProperty, CreateTaperedIProperty/TaperedTubeProperty, CreatePlateThicknessProperty (list of 4 floats), AssignBeamProperty, AssignPlateThickness, CreateIsotropicMaterial/Steel/Concrete/Aluminum/Timber, GetIsotropicMaterialProperties, GetOrthotropic2D/3DMaterialProperties, AssignMaterialToMember/Plate/Solid, CreateMemberReleaseSpec, CreateMemberPartialReleaseSpec, CreateMemberTrussSpec, CreateMemberTensionSpec, CreateMemberCompressionSpec, CreateMemberInactiveSpec, CreateMemberOffsetSpec, CreateMemberFireProofingSpec, CreateElementPlaneStressSpec, CreateElementOffsetSpec, CreateElementIgnoreInplaneRotnSpec, CreateElementNodeReleaseSpec, AssignBetaAngle, GetBeamProperty, GetSectionPropertyList, GetBeamSectionPropertyTypeNo, CreateUPTTable (user provided tables), AddUPTPropertyWIDEFLANGE/CHANNEL/ANGLE/DOUBLEANGLE/TEE/PIPE/TUBE/ISECTION/PRISMATIC/GENERAL, CreatePropertyFromUserTable, CreateMemberAttribute, AssignMemberAttribute, GetMemberListByAttribute, GetElementListByAttribute. Requires staad-core."
---

# STAAD.Pro Properties & Materials

## Instructions

- Define the shorthand once per script: `prop = staad.Property`

### Beam Sections from Database

```python
prop_id = prop.CreateBeamPropertyFromTable(countryCode, sectionName, typeSpec, v1, v2)
prop.AssignBeamProperty(beam_ids, prop_id)   # returns True on success, raises on failure
```

**Country codes** (full table in the Reference section — PROPERTY_CODES.md):

| Code | Country    | Code | Country       |
| ---- | ---------- | ---- | ------------- |
| 1    | American   | 9    | German        |
| 2    | Australian | 10   | Indian        |
| 3    | British    | 11   | Japanese      |
| 4    | Canadian   | 12   | Russian       |
| 5    | Chinese    | 13   | South African |
| 7    | European   | 16   | Korean        |

**Type spec:**

| Code | Spec | Description             |
| ---- | ---- | ----------------------- |
| 0    | ST   | Standard single section |
| 2    | D    | Double                  |
| 5    | T    | Tee                     |
| 6    | CM   | Composite               |
| 7    | TC   | Top cover plate         |
| 8    | BC   | Bottom cover plate      |
| 9    | TB   | Top+bottom cover plates |

**Specialized shape creation:**

| Function                                                            | Shape                |
| ------------------------------------------------------------------- | -------------------- |
| `CreateAnglePropertyFromTable(country, name, spec, addSpec)`        | Angle (L)            |
| `CreateChannelPropertyFromTable(country, name, spec, addSpec)`      | Channel (C)          |
| `CreateTubePropertyFromTable(country, name, spec, v1, v2, v3)`      | Hollow rectangular   |
| `CreatePipePropertyFromTable(country, name, spec, v1, v2)`          | Hollow circular      |
| `CreateTeePropertyFromTable(country, name, spec)`                   | Tee (WT)             |
| `CreateWideFlangePropertyFromTable(country, name, spec, specsList)` | Wide flange extended |
| `CreateBeamPropertyFromTableEx(country, name, solidShapeType)`      | Solid/cable/plate-strip shapes (1=Plate Strip, 2=Solid Rect, 3=Solid Round, 4=Round, 5=Cable) — distinct from `CreateBeamPropertyFromTable`, not a newer replacement for it |

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
- `GetRecordForSection(country, name)` → record number within that country's section database table

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
prop.CreateIsotropicMaterialPropertiesEx(name, E, poisson, G, density, alpha, damping, fy, fu, ry, rt, fcu)  # preferred — adds yield/ultimate strength; CreateIsotropicMaterialProperties(name, E, poisson, G, density, alpha, damping) also available without strength values

# Convenience
prop.CreateIsotropicMaterialSteel(name, E, poisson, G, density, alpha, damping, fu, fy, rt, ry, is_physical)
prop.CreateIsotropicMaterialConcrete(name, E, poisson, G, density, alpha, damping, fc, physical)
prop.CreateIsotropicMaterialAluminum(name, E, poisson, G, density, alpha, damping)
prop.CreateIsotropicMaterialTimber(name, E, poisson, G, density, alpha, damping)

# Assign
prop.AssignMaterialToMember("STEEL", member_ids)
prop.AssignMaterialToPlate("CONCRETE", plate_ids)
prop.AssignMaterialToSolid("CONCRETE", solid_ids)

# Query (by material name)
E, nu, density, alpha, damp, fy, fu, ry, rt, fcu = prop.GetMaterialPropertyEx("STEEL")  # preferred — adds strength values; GetMaterialProperty("STEEL") also available for just the base 5-tuple
name = prop.GetBeamMaterialName(beam_id)
name = prop.GetPlateMaterialName(plate_id)
name = prop.GetSolidMaterialName(solid_id)

# Remove / delete
prop.RemoveMaterialFromBeam(beam_id)
prop.RemoveMaterialFromPlate(plate_ids)      # int or list
prop.RemoveMaterialFromSolid(solid_ids)      # list
prop.DeleteMaterial("Q235")
```

**Isotropic material catalog (indexed by material number, not name)** — use this to enumerate all materials in the model rather than looking each one up by name:
```python
count = prop.GetIsotropicMaterialCount()
for i in range(1, count + 1):
    # preferred — adds strength values; GetIsotropicMaterialProperties(i) also available for just the base 7-tuple
    name, E, poisson, G, density, alpha, damp, fy, fu, ry, rt, fcu = prop.GetIsotropicMaterialPropertiesEx(i)
    # ...Assigned variant also returns whether it's used: 1=unassigned, 2=assigned
    E, poisson, G, density, alpha, damp, is_assigned = prop.GetIsotropicMaterialPropertiesAssigned(i)

beam_count = prop.GetIsotropicMaterialAssignedBeamCount(name)
beam_ids   = prop.GetIsotropicMaterialAssignedBeamList(name)
plate_count = prop.GetIsotropicMaterialAssignedPlateCount(name)
plate_ids  = prop.GetIsotropicMaterialAssignedPlateList(name)
solid_count = prop.GetIsotropicMaterialAssignedSolidCount(name)
solid_ids  = prop.GetIsotropicMaterialAssignedSolidList(name)

# _Ex variants add strength values (fy, fu, ry, rt, fcu) beyond the base 6-tuple
name, E, poisson, G, density, alpha, damp, fy, fu, ry, rt, fcu = prop.GetIsotropicMaterialPropertiesEx(i)
E, poisson, G, density, alpha, damp = prop.GetMaterialPropertyEx("STEEL")
mat_type = prop.GetTypeForIsotropicMaterial(i)          # e.g. steel/concrete/aluminum/timber type code
prop.SetTypeToIsotropicMaterial(i, mat_type)
```

**Orthotropic materials** (2D for plates, 3D for solids) — same 6-value tuple shape as isotropic, no material name:
```python
count = prop.GetOrthotropic2DMaterialCount()
E, poisson, G, density, alpha, damp = prop.GetOrthotropic2DMaterialProperties(material_no)

count = prop.GetOrthotropic3DMaterialCount()
E, poisson, G, density, alpha, damp = prop.GetOrthotropic3DMaterialProperties(material_no)
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
cable_id = prop.CreateMemberCableSpecEx(tension_or_length, value, tension_end_node_indicator=0, self_weight_factor_x=1.0, self_weight_factor_y=1.0, self_weight_factor_z=1.0)  # preferred — CreateMemberCableSpec(tension_or_length, value) also available without the advanced-analysis params
inact_id = prop.CreateMemberInactiveSpec()

# Offset (start=0/end=1 location, wrt Global=0/Local=1 axis)
off_id = prop.CreateMemberOffsetSpec(location, wrtAxis, dx, dy, dz)
prop.AssignMemberSpecToBeam(beam_ids, off_id)
```

Removing a spec from a beam (each returns `bool`, symmetric to the `Create*` above):
```python
prop.RemoveMemberOffsetSpecFromBeam(beam_id, location)      # location: 0=start, 1=end
prop.RemoveMemberTrussSpecFromBeam(beam_id)
prop.RemoveMemberTensionSpecFromBeam(beam_id)
prop.RemoveMemberCompressionSpecFromBeam(beam_id)
prop.RemoveMemberCableSpecFromBeam(beam_id, tension_or_length)
prop.RemoveMemberInactiveSpecFromBeam(beam_id)
```

Partial release (fractional stiffness instead of a full release) and querying an existing release:
```python
partial_id = prop.CreateMemberPartialReleaseSpec(location, dofRelease, factor)  # dofRelease: [FX,FY,FZ] 0/1; factor: 0.0-1.0 per DOF
prop.AssignMemberSpecToBeam(beam_ids, partial_id)
dofs, springs = prop.GetMemberReleaseSpecEx(beam_id, location)  # location: 0=start, 1=end
```

### Element (Plate) Specs
Verified live against a real model — `AssignElementSpecToPlate` accepts a single plate ID or a list:
```python
spec_id = prop.CreateElementPlaneStressSpec()          # spec_id can be 0 — don't treat 0 as failure
prop.AssignElementSpecToPlate(plate_ids, spec_id)      # plate_ids: int or list

spec_id = prop.CreateElementIgnoreInplaneRotnSpec()
prop.AssignElementSpecToPlate(plate_ids, spec_id)

node_rel_id = prop.CreateElementNodeReleaseSpec(node_id, dofRelease)  # dofRelease: [FX,FY,FZ,MX,MY,MZ] 0/1
prop.AssignElementSpecToPlate(plate_ids, node_rel_id)

# Removal
prop.RemoveElementPlaneStressSpecFromPlate(plate_id)
prop.RemoveElementNodeReleaseSpecFromPlate(plate_id, node_id)
```

### Element Offset Specs
```python
off_id = prop.CreateElementOffsetSpec(direction, nodeIndex, dx, dy, dz)  # direction: 0=Local, 1=Global; nodeIndex: 1-4
prop.AssignElementSpecToPlate(plate_ids, off_id)

z_off_id = prop.CreateElementLocalZOffsetSpec(node1Z, node2Z, node3Z, node4Z)  # one Z-offset value per plate node

count = prop.GetElementOffsetSpecCount()
direction, dx, dy, dz = prop.GetElementOffSetSpec(plate_id, nodeIndex)
dx, dy, dz = prop.GetElementLocalOffset(plate_id, nodeIndex)
```

### User Provided Tables (UPT)
For custom (non-database) section catalogs:
```python
table_id = prop.CreateUPTTable(table_type)   # 1=WideFlange, 2=Channel, 3=Angle, 4=DoubleAngle,
                                              # 5=Tee, 6=Pipe, 7=Tube, 8=General, 9=Isection, 10=Prismatic
prop.AddUPTPropertyWIDEFLANGE(table_id, name, area, depth, webThk, flangeW, flangeThk, torsConst, Iy, Iz, shearAy, shearAz)
# AddUPTProperty<SHAPE> exists per table_type (CHANNEL, ANGLE, TEE, PIPE, TUBE, GENERAL, ISECTION, PRISMATIC, ...)

sec_id = prop.CreatePropertyFromUserTable(sectionName, table_id)   # 0 if not found
prop.AssignBeamProperty(beam_ids, sec_id)

count  = prop.GetUserProvidedTableCount()
ids    = prop.GetUserProvidedTableList()
prop.RemoveUPTTable(table_id)
```

### Member/Element Attributes (Named Metadata)
Arbitrary string tags on members/elements, independent of any physical property:
```python
prop.CreateMemberAttribute(attributeName, value)
prop.AssignMemberAttribute(attributeName, value, member_ids)  # int or list
prop.DeleteMemberAttribute(attributeName, value)
# CreateElementAttribute/AssignElementAttribute/DeleteElementAttribute follow the same pattern for plates/solids
```

Querying attributes — two independent approaches:
```python
# By name+value pair (find everything tagged with a specific attribute/value)
count     = prop.GetMemberCountByAttribute("MEMBTYPE", "BRACE")
member_ids = prop.GetMemberListByAttribute("MEMBTYPE", "BRACE")
count     = prop.GetElementCountByAttribute("MEMBTYPE", "BRACE")
element_ids = prop.GetElementListByAttribute("MEMBTYPE", "BRACE")
prop.RemoveAttribute("MEMBTYPE", "BRACE", member_ids)  # int or list

# By member/beam ID (find every attribute tagged on one member)
attr_count = prop.GetAssignedAttributeCount(beam_id)
attribute_name, str_value = prop.GetAssignedAttributeByIndex(attr_count - 1)  # 0-based index

# Whole-model listing (member attributes only — no element equivalent)
count = prop.GetMemberAttributeCount()
names, values, count = prop.GetMemberAttributeList()
```
Also available, index-based rather than name-based: `GetMemberCountByAttributeIndex(index)` / `GetMemberListByAttributeIndex(index)`.

### Member Fire Proofing
```python
spec_id = prop.CreateMemberFireProofingSpec(fire_proof_type, thickness_value, density)  # type: 1=BFP Block, 2=CFP Contour
prop.AssignMemberSpecToBeam(beam_ids, spec_id)
prop.RemoveMemberFireProofingSpecFromBeam(beam_id)

count = prop.GetFireProofedBeamCount()
beam_ids = prop.GetFireProofedBeamList()
fire_proof_type, thickness, density = prop.GetFireProofDataForBeam(beam_id)

spec_count = prop.GetFireProofingSpecCount()
fire_proof_type, thickness, density, assigned_count = prop.GetFireProofingSpecDetails(index)  # 1-based index
assigned_count = prop.GetFireProofingSpecAssignedBeamCount(index)
assigned_beams = prop.GetFireProofingSpecAssignedBeamList(index)
```

### UPT — Additional Shape Types & Section Queries
Each shape family has its own `AddUPTProperty<SHAPE>` with shape-specific parameters (cross-section area, depth, flange/web thickness, etc. — see the function's own signature for the exact list):
```python
prop.AddUPTPropertyWIDEFLANGE(table_id, name, area, depth, webThk, flangeW, flangeThk, torsConst, Iy, Iz, shearAy, shearAz)
prop.AddUPTPropertyCHANNEL(table_id, name, area, depth, webThk, flangeW, flangeThk, torsConst, Iy, Iz, cz, shearAy, shearAz)
prop.AddUPTPropertyANGLE(table_id, name, depth, width, flangeThk, radiusOfGyration, shearAy, shearAz)
prop.AddUPTPropertyDOUBLEANGLE(table_id, name, depth, width, flangeThk, spacing, torsConst, Iy, Iz, cz, shearAy, shearAz)
prop.AddUPTPropertyTEE(table_id, name, area, depth, flangeW, flangeThk, webThk, torsConst, Iy, Iz, cz, shearAy, shearAz)
prop.AddUPTPropertyPIPE(table_id, name, outerDiameter, innerDiameter, shearAy, shearAz)
prop.AddUPTPropertyTUBE(table_id, name, area, depth, flangeW, flangeThk, torsConst, Iy, Iz, shearAy, shearAz)
prop.AddUPTPropertyISECTION(table_id, name, dww, tww, dww1, bff, tff, bff1, tff1, ayf, azf, xif)  # tapered I-shape, distinct start/end flanges
prop.AddUPTPropertyPRISMATIC(table_id, name, area, torsConst, Iy, Iz, shearAy, shearAz, depthY, depthZ)
# AddUPTPropertyGENERAL and AddUPTPropertyWIDEFLANGECOMPOSITE/WIDEFLANGEUNEQUAL follow the same per-shape parameter pattern
prop.AddUPTPropertyWIDEFLANGEUNEQUAL(table_id, name, profile_spec_list)  # asymmetric wide-flange, all dimensions in one list

prop.RemovePropertyFromUPTTable(table_id, section_name)
```

Querying sections within a UPT table:
```python
count = prop.GetUserProvidedTableSectionCount(table_id)
names = prop.GetUserProvidedTableSectionList(table_id)
section_type, prop_values = prop.GetUserProvidedTableSectionProperties(table_id, section_name)  # section_type code + float list, meaning depends on shape (WideFlange/Channel/Angle/etc.)
prop_count = prop.GetUserProvidedTableSectionPropertyCount(table_id, section_name)
section_type = prop.GetUserProvidedTableSectionType(table_id, section_name)
table_no = prop.GetUserProvidedTableNo(beam_id)   # UPT table number a beam's section belongs to
```

### Section/Database Introspection
```python
country_code = prop.GetCountryTableNo(beam_id)
table_no     = prop.GetSectionTableNo(beam_id)
prop_type_no = prop.GetBeamSectionPropertyTypeNo(beam_id)   # e.g. 610=BEAM ST, 630=CHANNEL ST, 640=ANGLE ST — see openstaadpy docstring for full table
alpha_rad    = prop.GetAlphaAngleForSection(section_property_id)   # angle between principal and geometric axis
cy, cz       = prop.GetCentroidLocationForSection(section_property_id)
section_type, prop_values = prop.GetBeamSectionPropertyValuesEx(beam_id)  # float list, meaning keyed by prop_type_no

is_standard  = prop.IsStandardDatabaseSection(section_property_id)  # False for UPT/prismatic/tapered sections
db_name      = prop.GetStandardSectionDatabaseName(section_property_id)   # empty string if not a standard-database section
table_name   = prop.GetStandardSectionTableName(section_property_id)
section_name = prop.GetStandardSectionName(section_property_id)
folder       = prop.GetStandardProfileDBFolder()          # currently configured profile DB folder
default_folder = prop.GetDefaultStandardProfileDBFolder() # factory-default profile DB folder
prop.SetStandardProfileDBFolder(folder_path)

ref_no       = prop.GetBeamSectionPropertyRefNo(beam_id)      # section property reference number for a beam
country      = prop.GetSectionPropertyCountry(sec_ref_no)
width, depth, ax, ay, az, ix, iy, iz, tf, tw = prop.GetSectionPropertyValues(prof_type)      # Assign Profile types only (0=Angle,1=DoubleAngle,2=Beam,3=Column,4=Channel)
prop_type, values = prop.GetSectionPropertyValuesEx(section_property_id)                     # general section, float list keyed by prop_type
value_count = prop.GetCountofSectionPropertyValuesEx(section_property_id)
member_spec_code = prop.GetMemberSpecCode(member_id)   # 0=Truss,1=Tension-only,2=Compression-only,3=Cable-only,4=Joist,-1=Other
```
`GetCountryTableNo`/`GetSectionTableNo` return `0` for sections not sourced from a country database (prismatic, tapered, UPT) — this is expected, not an error.

### Misc
```python
prop.DeleteProperty(property_id)
prop.DeleteMemberSpec(spec_id)
prop.DeleteMemberReleaseSpec(beam_id, release_location)  # 0=start, 1=end
prop.RemoveMemberReleaseSpecFromBeam(beam_id, release_location)  # bool variant of the above
prop.RemovePropertyFromBeam(beam_id)
prop.RemovePropertyFromPlate(plate_id)
prop.RemoveAllElementNodeReleaseSpec()
prop.RemoveAllElementOffsetSpec()
prop.RemoveElementIgnoreInplaneRotnSpecFromPlate(plate_id)

prop.SetMaterialName(material_name)   # sets material name for the member context set by preceding beam/plate/solid selection
prop.GetPropertyUniqueID(property_number)
prop.SetPropertyUniqueID(property_number, unique_id_str)

count = prop.GetInactiveMemberCount()
beam_ids = prop.GetInactiveMemberList()

spec_id = prop.CreateMemberIgnoreStiffSpec()
prop.RemoveMemberIgnoreStiffSpecFromBeam(beam_id)

# Member/element global vs local offsets (query-only; complements CreateMemberOffsetSpec/CreateElementOffsetSpec above)
dx, dy, dz = prop.GetMemberGlobalOffSet(beam_id, position)  # position: 0=start, 1=end
dx, dy, dz = prop.GetMemberLocalOffSet(beam_id, position)
dx, dy, dz = prop.GetElementGlobalOffSet(plate_id, node_index)
name = prop.GetElementMaterialName(element_id)  # for plate/solid element IDs — returns empty string for beam IDs (use GetBeamMaterialName for beams)

prop.UpdatePropertiesToDesignSection()   # commits SELECT MEMBER design results as new fixed section properties

# Niche/advanced creation functions (each mirrors CreateBeamPropertyFromTable's country/name/spec pattern)
prop.CreateAssignProfileProperty(profile_type)   # 0=Angle,1=DoubleAngle,2=Beam,3=Column,4=Channel — "assign profile" (no fixed properties, evaluated per-country at analysis time)
prop.CreateBeamPropertyFromTableComposite(country_code, section_name, spec_type, additional_spec_list)          # composite deck sections (spec_type -1 to 12, e.g. 6=CM)
prop.CreateBeamPropertyFromTableWithCoverPlates(country_code, section_name, spec_type, additional_spec_list)    # cover-plated sections (spec_type 7=TC, 8=BC, 9=TB)
prop.CreateParametricSurfaceThicknessProperty(node_thickness_list)  # per-node thickness for parametric (non-planar) surfaces
table_id = prop.CreateUPTTableEx(table_ref_id, table_type)   # explicit table number ID instead of auto-assigned (table_type: 1=WideFlange, 2=Channel, 3=Angle, ... see CreateUPTTable)
sec_id = prop.CreatePropertyFromUPTTable(table_reference_id, section_name)  # alt UPT-scoped variant of CreatePropertyFromUserTable
prop.AddControlDependentRelation(control_node, dependent_nodes, dofRelease)  # control/dependent joint (rigid link) specification
prop.DeleteAllControlDependentRelations()
boundary_z, boundary_y = prop.GetUptGeneralProfileBoundaryPoints(table_reference_id, section_name)
point_count = prop.GetUptGeneralProfilePointsCount(table_reference_id, section_name)
stress_z, stress_y = prop.GetUptGeneralStressLocationPoints(table_reference_id, section_name)
```

### Querying

| Function                                  | Returns                          |
| ----------------------------------------- | --------------------------------- |
| `GetSectionPropertyCount()`               | total section properties         |
| `GetSectionPropertyList()`                | list of property IDs             |
| `GetSectionPropertyName(sid)`             | section name string              |
| `GetSectionPropertyType(sid)`             | section type code                |
| `GetSectionPropertyAssignedBeamList(sid)` | beams using that section         |
| `GetSectionPropertyAssignedBeamCount(sid)`| count of beams using that section|
| `GetBeamSectionName(bid)`                 | section name for beam            |
| `GetBeamSectionDisplayName(bid)`          | display-formatted section name   |
| `GetBeamProperty(bid)`                    | `(w, d, AX, AY, AZ, IZ, IY, IX)` |
| `GetBeamPropertyAll(bid)`                 | adds `tf, tw` to above           |
| `GetBeamConstants(bid)`                   | `(E, poisson, density, alpha, damp)` |
| `GetPlateThickness(pid)`                  | list of 4 floats                 |
| `GetThicknessPropertyCount()`             | total thickness properties       |
| `GetThicknessPropertyList()`              | list of thickness property IDs   |
| `GetThicknessPropertyValues(tid)`         | list of 4 floats for that ID     |
| `GetPlateSectionPropertyRefNo(pid)`       | assigned thickness/property ID for a plate |
| `GetThicknessPropertyAssignedPlateCount(tid)` | count of plates using that thickness ID |
| `GetThicknessPropertyAssignedPlateList(tid)`  | plate IDs using that thickness ID |

## Examples

- [assign-beam-sections.py](./scripts/assign-beam-sections.py) — create and assign a W-section
- [assign-plate-thickness.py](./scripts/assign-plate-thickness.py) — assign plate thickness
- [create-floor-plates.py](./scripts/create-floor-plates.py) — create plates and assign thickness
- [assign-element-specs.py](./scripts/assign-element-specs.py) — create and assign element plane-stress and offset specs

## Gotchas

- `CreatePlateThicknessProperty` takes a **list of 4 floats**, one value per corner — not a single scalar
- `AssignBeamProperty` returns `True` on success and **raises on failure** — call it directly; do NOT check `if result < 0` (`execute_code` reports any uncaught error)
- Always retrieve actual IDs via `GetBeamList()` / `GetPlateList()` before assigning — never assume IDs start at 1
- `GetMemberDesignSectionName(bid)` raises an error when results are unavailable — use `GetSectionPropertyName` for pre-analysis lookup
- Built-in material names: `"STEEL"`, `"CONCRETE"`, `"ALUMINUM"` — case-sensitive
- `CreateElementPlaneStressSpec()`/`CreateElementIgnoreInplaneRotnSpec()` can return spec ID `0` on success — don't treat `0` as a failure code for these (unlike most other `Create*` functions where `0` means failure)
- After `CreateElementOffsetSpec` + `AssignElementSpecToPlate`, `GetElementOffsetSpecCount()` correctly reflects the new spec, but `GetElementLocalOffset()`/`GetElementOffSetSpec()` were observed still returning `(0.0, 0.0, 0.0)` in testing — verify offset specs via `GetElementOffsetSpecCount()` rather than assuming the per-node getters immediately reflect an assignment
