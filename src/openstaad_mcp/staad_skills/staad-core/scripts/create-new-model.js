// create-new-model.js
// Creates a new STAAD.Pro model file and adds basic geometry.
// WARNING: Only call NewSTAADFile when the user explicitly requests it.
// staad stays valid after NewSTAADFile — do NOT reinitialize.
// IMPORTANT: Ask the user for the save path before calling this script.
// Do NOT hardcode a path — use the path the user provides.

staad.SetSilentMode(true);

// Create new model (lenUnit=1=Feet, forceUnit=0=KIP)
// Replace the path below with the user's chosen location.
staad.NewSTAADFile('C:\\Users\\<username>\\Documents\\MyModel.std', 1, 0);

// staad is still valid after NewSTAADFile — do NOT reinitialize
const geo = staad.Geometry;
const n1 = geo.AddNode(0, 0, 0);
const n2 = geo.AddNode(0, 10, 0);
const b1 = geo.AddBeam(n1, n2);

staad.SetSilentMode(false);
console.log(`New model created: nodes ${n1},${n2} beam ${b1}`);
console.log(`File: ${staad.GetSTAADFile()}`);
