// portal-frame.js
// Creates a simple portal frame: 2 columns + 1 beam, fixed supports at base.
// Adjust coordinates to match the model baseUnit (English=inches, Metric=meters).

const geo = staad.Geometry;

// Coordinates in base units — English: 10ft cols = 120in, 20ft span = 240in
const n1 = geo.AddNode(0, 0, 0);       // base left
const n2 = geo.AddNode(0, 120, 0);     // top left
const n3 = geo.AddNode(240, 120, 0);   // top right
const n4 = geo.AddNode(240, 0, 0);     // base right

const b1 = geo.AddBeam(n1, n2);        // left column
const b2 = geo.AddBeam(n2, n3);        // horizontal beam
const b3 = geo.AddBeam(n3, n4);        // right column

// SaveModel(true) flushes in-memory geometry to disk before assigning supports.
// Do NOT use UpdateStructure() here — it discards in-memory geometry.
staad.SetSilentMode(true);
staad.SaveModel(true);
staad.SetSilentMode(false);

const sup = staad.Support;
const fixId = sup.CreateSupportFixed();
sup.AssignSupportToNode(n1, fixId);  // AssignSupportToNode takes ONE node at a time
sup.AssignSupportToNode(n4, fixId);

console.log(`Portal frame: nodes ${n1},${n2},${n3},${n4} beams ${b1},${b2},${b3}`);
console.log(`Fixed supports at nodes ${n1} and ${n4}`);
