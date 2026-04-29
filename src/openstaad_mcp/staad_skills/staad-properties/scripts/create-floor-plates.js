// create-floor-plates.js
// Creates four nodes forming a floor panel, adds a plate element, and assigns thickness.
// Example uses English units (inches). Adjust coordinates for Metric (meters).

const geo = staad.Geometry;

// Floor panel at elevation Y=118.11 in (~3m), 3m x 5m footprint
const n1 = geo.AddNode(0, 118.11, 0);
const n2 = geo.AddNode(118.11, 118.11, 0);
const n3 = geo.AddNode(118.11, 118.11, 196.85);
const n4 = geo.AddNode(0, 118.11, 196.85);

// AddPlate takes 4 separate int args — NOT a list
const pid = geo.AddPlate(n1, n2, n3, n4);
console.log(`Plate ${pid} created with nodes ${n1},${n2},${n3},${n4}`);

// SaveModel(true) flushes in-memory geometry to disk before property assignment.
// Do NOT use UpdateStructure() here — it discards in-memory geometry.
staad.SetSilentMode(true);
staad.SaveModel(true);
staad.SetSilentMode(false);

const prop = staad.Property;

// CreatePlateThicknessProperty takes a list of 4 floats (one per corner)
const t = 3.937;   // 100 mm in inches
const thickId = prop.CreatePlateThicknessProperty([t, t, t, t]);
prop.AssignPlateThickness([pid], thickId);

console.log(`Thickness ${t} in (property ${thickId}) assigned to plate ${pid}`);
