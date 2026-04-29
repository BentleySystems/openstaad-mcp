// assign-plate-thickness.js
// Assigns a uniform thickness to all plates in the model.
// Always retrieve actual plate IDs — never assume they start at 1.
// CreatePlateThicknessProperty requires a list of 4 floats (one per corner node).

const geo = staad.Geometry;
const prop = staad.Property;

// Get actual plate IDs
const plateIds = geo.GetPlateList();
console.log(`Plates found: ${JSON.stringify(plateIds)}`);

// Create thickness property — 4 floats required, one per corner node
const t = 3.937;   // 100 mm expressed in inches (English model); use meters for Metric
const thickId = prop.CreatePlateThicknessProperty([t, t, t, t]);
console.log(`Created thickness property ID: ${thickId} (t=${t} in)`);

// Assign to all plates
prop.AssignPlateThickness(plateIds, thickId);
console.log(`Assigned thickness ${t} in to ${plateIds.length} plates`);
