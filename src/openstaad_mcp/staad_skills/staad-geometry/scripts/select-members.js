// select-members.js
// Demonstrates selecting beams in the model — single and multiple.
// Selections are additive: always clear before starting a new selection.

const geo = staad.Geometry;

// Get actual beam IDs first — never assume they start at 1
const beamIds = geo.GetBeamList();
console.log(`All beams: ${JSON.stringify(beamIds)}`);

// Select a single beam
geo.ClearMemberSelection();          // always clear first
let result = geo.SelectBeam(beamIds[0]);
console.log(`SelectBeam(${beamIds[0]}) result: ${result}`);  // 0 = OK
console.log(`Selected: ${JSON.stringify(geo.GetSelectedBeams())}`);

// Select multiple beams at once
geo.ClearMemberSelection();
result = geo.SelectMultipleBeams(beamIds.slice(0, 3));  // first 3 beams
console.log(`SelectMultipleBeams result: ${result}`);  // 0 = OK
console.log(`Selected: ${JSON.stringify(geo.GetSelectedBeams())}`);

// Same pattern works for nodes, plates, solids:
// geo.ClearNodeSelection() / SelectNode(id) / SelectMultipleNodes(ids) / GetSelectedNodes()
// geo.ClearPlateSelection() / SelectPlate(id) / SelectMultiplePlates(ids) / GetSelectedPlates()
