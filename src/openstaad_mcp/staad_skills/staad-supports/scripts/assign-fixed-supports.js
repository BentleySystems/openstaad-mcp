// assign-fixed-supports.js
// Assigns fixed supports to specified base nodes.
// AssignSupportToNode takes ONE node ID at a time — use a loop for multiple nodes.

const geo = staad.Geometry;
const sup = staad.Support;

// Get actual node IDs — identify base nodes (elevation = 0)
const nodeList = geo.GetNodeList();
const baseNodes = [];
for (const nid of nodeList) {
    const [x, y, z] = geo.GetNodeCoordinates(nid);
    if (Math.abs(y) < 0.001) {   // y=0 for Y-up models; use z for Z-up
        baseNodes.push(nid);
    }
}
console.log(`Base nodes found: ${JSON.stringify(baseNodes)}`);

// Create fixed support once — reuse the ID for all assignments
const fixId = sup.CreateSupportFixed();
console.log(`Fixed support ID: ${fixId}`);

// AssignSupportToNode takes a SINGLE node ID — iterate with a loop
for (const nid of baseNodes) {
    sup.AssignSupportToNode(nid, fixId);
}

console.log(`Fixed support assigned to ${baseNodes.length} nodes`);
