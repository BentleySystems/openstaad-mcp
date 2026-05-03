---
name: staad-errors
description: 'Load whenever writing any script that modifies the model, adds geometry, assigns properties, or runs analysis — most OpenSTAAD functions return negative integers on failure rather than raising exceptions, so callers must check return values explicitly. Covers: common error code groups (general -1, file -1003, node -2001, beam -3001, plate -4001, solid -5001, property -6001, load -8001, results -9004/-9911), try/except patterns for COM exceptions, checking return values, robust model-building patterns. NOTE: In the MCP sandbox import is blocked — catch generic Exception, not typed oserrors classes.'
---

# STAAD.Pro Error Handling

## Sandbox Limitation
In the MCP sandbox, `import` is blocked. You cannot import typed exception classes from `openstaadpy.os_analytical.oserrors`. Instead, catch generic `Exception` and inspect the message or code.

## Basic Pattern
```python
geo = staad.Geometry

try:
    beam_no = geo.AddBeam(start_node, end_node)
    print(f"Added beam {beam_no}")
except Exception as e:
    print(f"Error adding beam: {e}")
```

## Checking Return Values
Many methods return negative integers on error instead of raising exceptions:
```python
result = prop.AssignBeamProperty([99], prop_id)
if isinstance(result, int) and result < 0:
    print(f"Failed with error code: {result}")
```

## Robust Model Building Pattern
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

| Range | Category | Examples |
|-------|----------|----------|
| `-1` | General error | Generic failure |
| `-100` to `-125` | Argument errors | Invalid argument, out of range |
| `-1003` | File error | File not found / access denied |
| `-2001` to `-2006` | Node errors | Node not found, duplicate node |
| `-3001` to `-3005` | Beam errors | Beam not found, invalid incidence |
| `-4001` to `-4009` | Plate errors | Plate not found, invalid node count |
| `-5001` to `-5005` | Solid errors | Solid not found |
| `-6001` to `-6045` | Property errors | Profile not found, invalid property |
| `-7001` | Group error | Group not found |
| `-8001` to `-8041` | Load errors | Load case not found, create failed |
| `-9004`, `-9911` | Results errors | Results not available |

## Tips
- Always check `out.AreResultsAvailable()` before querying results
- Always check `AssignDesignCommand` return value (0 = success)
- Wrap `AnalyzeEx` / `AnalyzeModel` calls in try/except — analysis can fail
- Print intermediate values (node IDs, beam IDs, property IDs) to diagnose failures
- If a function returns -999, the operation was not performed (e.g., member not designed)

## Gotchas
- In standalone Python, you can `from openstaadpy.os_analytical.oserrors import OsBeamNotFound` — but NOT in the MCP sandbox
- Some methods silently return 0 even when something went wrong (e.g., `UpdateStructure` on read-only paths)
- Negative return codes are integers, not exceptions — always check `if result < 0`
