// hydrostatic-tank.js
// Assigns hydrostatic water pressure to walls and base of a plate tank.
// Reads baseUnit from staad.GetBaseUnit() and vertical axis from staad.Geometry.IsZUp().
// Uses AddElementTrapPressureEx for wall plates (variable pressure with depth)
// and AddElementPressure for the base plate (uniform full-head pressure).

const geo = staad.Geometry;
const load = staad.Load;

// Read units and axis from model — never hardcode
const baseUnit = staad.GetBaseUnit();          // 'English' or 'Metric'
const verticalAxis = geo.IsZUp() ? 'Z' : 'Y';

// Water unit weight in model units
let gammaWater;
if (baseUnit === 'English') {
    gammaWater = 62.4 / 1728000.0;   // kip/in^3
} else if (baseUnit === 'Metric') {
    gammaWater = 9.81;               // kN/m^3
} else {
    throw new Error(`Unsupported baseUnit: ${baseUnit}`);
}

const axisIndex = verticalAxis === 'Y' ? 1 : 2;

// Build node elevation map; find water surface (max) and tank base (min)
const nodeCoords = {};
let maxElev = -1e30;
let minElev = 1e30;

for (const nid of geo.GetNodeList()) {
    const coords = geo.GetNodeCoordinates(nid);  // [x, y, z]
    nodeCoords[nid] = coords;
    const elev = coords[axisIndex];
    if (elev > maxElev) maxElev = elev;
    if (elev < minElev) minElev = elev;
}

// Classify plates: horizontal (same elevation all nodes) = base, else = wall
const wallGroups = new Map();   // signature (corner elevations) → [plate_ids]
const basePlates = [];

for (const pid of geo.GetPlateList()) {
    const incidence = geo.GetPlateIncidence(pid);
    const nodes = incidence.filter((n) => n !== 0);
    const elevations = nodes.map((n) => nodeCoords[n][axisIndex]);
    const max = Math.max(...elevations);
    const min = Math.min(...elevations);
    if ((max - min) < 0.001) {
        basePlates.push(pid);
    } else {
        const signature = JSON.stringify(elevations.map((e) => Math.round(e * 1e6) / 1e6));
        if (!wallGroups.has(signature)) wallGroups.set(signature, { elev: elevations, ids: [] });
        wallGroups.get(signature).ids.push(pid);
    }
}

// Create load case (type 7 = fluid/hydrostatic)
const lc = load.CreateNewPrimaryLoadEx('Hydrostatic Water Pressure', 7);
load.SetLoadActive(lc);

// Wall loads — group plates with identical corner elevation signature together
// loadDir=3 (LocalZ normal), varyDir=1 (LocalX varies with depth)
const sorted = [...wallGroups.values()].sort((a, b) => JSON.stringify(a.elev) < JSON.stringify(b.elev) ? -1 : 1);
for (const group of sorted) {
    const e = group.elev;
    const p1 = gammaWater * (maxElev - e[0]);
    const p2 = gammaWater * (maxElev - e[1]);
    const p3 = gammaWater * (maxElev - e[2]);
    const p4 = gammaWater * (maxElev - e[3]);
    load.AddElementTrapPressureEx(group.ids, 3, 1, p1, p2, p3, p4);
}

// Base load — uniform full-head pressure
const fullHead = gammaWater * (maxElev - minElev);
load.AddElementPressure(basePlates, 3, fullHead, 0.0, 0.0, 0.0, 0.0);

console.log(`Load case ${lc}: ${wallGroups.size} wall groups, ${basePlates.length} base plates`);
console.log(`Water surface elevation: ${maxElev.toFixed(3)}, base: ${minElev.toFixed(3)}`);
console.log(`Full head pressure: ${fullHead.toFixed(6)}`);
