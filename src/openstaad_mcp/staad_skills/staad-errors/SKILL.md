---
name: staad-errors
description: 'Use when handling errors from OpenSTAAD operations, interpreting negative return codes, or writing robust error-handling patterns. Covers: common error code groups (general, file, node, beam, plate, solid, property, group, load, results), try/catch patterns for COM exceptions, checking return values. NOTE: In the MCP sandbox imports are blocked — catch generic Error, not typed exception classes.'
---

# STAAD.Pro Error Handling

## Sandbox Limitation
In the MCP sandbox, `import` and `require` are blocked. You cannot load typed exception classes. Instead, catch generic `Error` and inspect the message. COM errors surface as regular JavaScript `Error` objects with a sanitised message like `"COM error in 'staad.Geometry.AddBeam': ..."`.

## Basic Pattern
```javascript
const geo = staad.Geometry;

try {
    const beamNo = geo.AddBeam(startNode, endNode);
    console.log(`Added beam ${beamNo}`);
} catch (e) {
    console.log(`Error adding beam: ${e.message}`);
}
```

## Checking Return Values
Many methods return negative integers on error instead of throwing:
```javascript
const result = prop.AssignBeamProperty([99], propId);
if (typeof result === 'number' && result < 0) {
    console.log(`Failed with error code: ${result}`);
}
```

## Robust Model Building Pattern
```javascript
const geo = staad.Geometry;

function safeAddBeam(start, end) {
    try {
        return geo.AddBeam(start, end);
    } catch (e) {
        console.log(`  Beam (${start}->${end}) skipped: ${e.message}`);
        return null;
    }
}

for (const [s, e] of [[1, 2], [2, 3], [3, 99]]) {
    const bno = safeAddBeam(s, e);
    if (bno !== null) console.log(`Added beam ${bno}`);
}
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
- Wrap `AnalyzeEx` / `AnalyzeModel` calls in try/catch — analysis can fail
- Log intermediate values (node IDs, beam IDs, property IDs) to diagnose failures
- If a function returns -999, the operation was not performed (e.g., member not designed)

## Gotchas
- You cannot catch typed OpenSTAAD exception classes in the sandbox — there is no module system
- Some methods silently return 0 even when something went wrong (e.g., `UpdateStructure` on read-only paths)
- Negative return codes are integers, not thrown errors — always check `if (result < 0)`
- COM errors bubble up with a sanitised message — the underlying HRESULT text is preserved in `e.message`
