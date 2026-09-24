---
name: staad-errors
description: 'Use when handling errors from OpenSTAAD operations, interpreting negative return codes, or writing robust error-handling patterns. Covers: execute_code reports uncaught exceptions automatically (no try/except needed just to report), the three return contracts (raises / silent bool / raw negative int), the code-to-exception dispatcher and its unmapped-code gap, common error code groups (general, file, node, beam, plate, solid, property, spring, group, load, results, export), when to use try/except for control flow (loop-skip, fallback), checking getter return values. NOTE: In the MCP sandbox import is blocked — catch generic Exception, not typed oserrors classes.'
---

# STAAD.Pro Error Handling

## Errors Are Reported Automatically
`execute_code` wraps your whole script in a top-level handler: any uncaught
exception is captured and returned as `success: false` with the (sanitized) error
message plus whatever you printed before it. **You do NOT need `try/except` just to
report a failure** — let it propagate and read the error from the tool result.

Use `try/except` inside a script only when it changes **control flow**, e.g.:
- skipping a bad item inside a bulk loop so the rest keep processing
- providing a fallback value (e.g. version-gated features) and continuing

## Sandbox Limitation
In the MCP sandbox, `import` is blocked. You cannot import typed exception classes from `openstaadpy.os_analytical.oserrors`. Instead, catch generic `Exception` and inspect the message or code.

## Clear COM Errors
The openstaadpy wrapper wraps COM objects in a proxy layer that turns cryptic COM
failures into actionable messages. If a COM method is missing or fails, the error
typically tells you to **update STAAD.Pro to the latest version** — this usually
means the *connected* STAAD instance is older than the function requires (see
staad-core → Version Compatibility), not a coding mistake.

## Return Contracts

There are **three** contracts, and they are not consistent across the API — check the
owning skill before assuming which one applies.

**1. Raises on failure** — most `Create*` functions, nearly all `Get*` functions, and
the support create/assign/query/delete methods. Call them directly and let
`execute_code` surface the error:
```python
prop_id = prop.CreateBeamPropertyFromTable(1, 'W14X120', 0, 0.0, 0.0)   # raises on failure
```

**2. Returns a silent `bool`** — notably `AssignBeamProperty`,
`AssignMemberSpecToBeam`, `RemovePropertyFromBeam`, `RemoveMaterialFromBeam` and the
`RemoveMember*SpecFromBeam` family. These **never raise**; a failed call is
indistinguishable from a no-op unless you check:
```python
if not prop.AssignBeamProperty(beam_ids, prop_id):
    print('assignment reported failure')
```

**3. Returns a raw integer** — some getters return a negative code instead of
raising. Where a function may do either, guard both paths:
```python
try:
    shape = prop.GetShapeCode(country, name)
except Exception as exc:
    shape = -1
    print(f'GetShapeCode failed: {exc}')
if shape < 0:
    print('Section not found')
```

### The Dispatcher Only Knows Some Codes

Internally the wrapper maps a numeric code to an exception class. **Unmapped codes
are swallowed** — the function returns normally with unpopulated output values. Code
`0` in particular is unmapped. So "no exception raised" is not proof of success:
sanity-check suspicious results such as all-zero properties or empty lists. A known
case is `Property.GetMaterialProperty(name)`, which returns `(0.0, 0.0, 0.0, 0.0, 0.0)`
for an unknown material instead of raising — use `GetMaterialPropertyEx(name)`.

## Robust Model Building Pattern
Catch per-item inside a loop so one bad entity doesn't abort the whole batch:
```python
geo = staad.Geometry

def safe_add_beam(start, end):
    try:
        return geo.AddBeam(start, end)
    except Exception as e:
        print(f"  Beam ({start}->{end}) skipped: {e}")
        return None

for s, e in [(1, 2), (2, 3), (3, 99)]:
    bno = safe_add_beam(s, e)
    if bno:
        print(f"Added beam {bno}")
```

## Common Error Code Groups

See **[ERROR_CODES.md](./assets/ERROR_CODES.md)** for the full table of exception class names per code.

| Range | Category | Examples |
|-------|----------|----------|
| `-1` | General error | Generic failure |
| `-2` | Invalid model path | `OsInvalidModelPath` |
| `-100` to `-125` | Argument errors | Invalid argument, out of range |
| `-101` | Model not opened | `OsModelNotOpened` |
| `-114` | OLE exception | `OsOleException` |
| `-115` | License not supported | OpenSTAAD Professional functions unavailable |
| `-130`, `-131` | Argument errors | Index out of range, invalid direction code |
| `-1003` | File error | File not found / access denied |
| `-2001` to `-2006` | Node errors | Node not found, duplicate node |
| `-3001` to `-3005` | Beam errors | Beam not found, invalid incidence |
| `-3006` | Invalid member number | `OsInvalidMemberNo` |
| `-4001` to `-4009` | Plate errors | Plate not found, invalid node count |
| `-5001` to `-5005` | Solid errors | Solid not found |
| `-6001` to `-6045` | Property errors | Profile not found, invalid property |
| `-7001` | Group error | Group not found |
| `-8001` to `-8049` | Load errors | Load case not found, create failed, enclosed zone errors |
| `-8101` to `-8106` | Floor boundary errors | `IdentifyFloorBoundariesFromNodes` boundary validation failures |
| `-9004`, `-9911` | Results errors | Results not available |

### Named Error Classes

These surface as raised exceptions (the message names the condition). In the
sandbox, catch generic `Exception` and read the message:

| Code | Class | Meaning |
|------|-------|---------|
| `-2` | `OsInvalidModelPath` | Invalid model path |
| `-101` | `OsModelNotOpened` | STAAD model is not opened |
| `-114` | `OsOleException` | OLE exception occurred |
| `-115` | `OsLicenseNotSupported` | License lacks OpenSTAAD Professional functions |
| `-3006` | `OsInvalidMemberNo` | Invalid member number ID(s) |

## Tips
- Always check `out.AreResultsAvailable()` before querying results
- Let failures propagate — `execute_code` returns the error; only add `try/except` for loop-skip or fallback control flow
- Print intermediate values (node IDs, beam IDs, property IDs) to diagnose failures
- If a function returns -999, the operation was not performed (e.g., member not designed)

## Gotchas
- In standalone Python, you can `from openstaadpy.os_analytical.oserrors import OsBeamNotFound` — but NOT in the MCP sandbox
- `execute_code` already catches uncaught exceptions — do NOT wrap a single call in `try/except` just to `print` the error
- Some methods silently return 0 even when something went wrong (e.g., `UpdateStructure` on read-only paths)
- `AssignBeamProperty` and `AssignMemberSpecToBeam` return a plain `bool` and **never raise** — check the return value and confirm with a getter. Other `Assign*` methods (`AssignPlateThickness`, `AssignMaterialToMember/Plate/Solid`, `AssignElementSpecToPlate`, `AssignDesignCommand`, `AssignDesignParameter`, `AssignDesignGroup`) and the support create/assign/query/delete methods **do** raise on failure — for those, do NOT check `if result < 0`
- Negative return codes still apply to many **getter** methods — always check `if result < 0` for those
- `-3005` (`OsNoBeamSelected`) isn't only a getter-side error — `geo.ClearMemberSelection()` also raises it when the selection is already empty, so guard the first clear call of a script (see staad-geometry → Selection)
- A "update STAAD.Pro" error usually means the connected instance is older than the called function requires (see staad-core → Version Compatibility)
