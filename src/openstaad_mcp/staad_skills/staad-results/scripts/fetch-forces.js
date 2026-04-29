// fetch-forces.js
// Fetches member end forces, bending moments, and support reactions for the first load case.
// Always call AreResultsAvailable() before reading any output.

const out = staad.Output;

// Guard: check results exist before querying
if (!out.AreResultsAvailable()) {
    console.log('No results available — run analysis first');
} else {
    const load = staad.Load;
    const geo = staad.Geometry;

    // Always fetch load case numbers dynamically — never hardcode
    const lcNumbers = load.GetPrimaryLoadCaseNumbers();
    console.log(`Load cases: ${JSON.stringify(lcNumbers)}`);
    const lc = lcNumbers[0];

    const beamList = geo.GetBeamList();
    const nodeList = geo.GetNodeList();

    // Member end forces — local axis, start end (0=StartA, 1=EndB; 0=Local, 1=Global)
    const bid = beamList[0];
    const f = out.GetMemberEndForces(bid, 0, lc, 0);
    console.log(
        `Member ${bid} (StartA, Local): ` +
        `FX=${f[0].toFixed(3)} FY=${f[1].toFixed(3)} FZ=${f[2].toFixed(3)}  ` +
        `MX=${f[3].toFixed(3)} MY=${f[4].toFixed(3)} MZ=${f[5].toFixed(3)}`
    );

    // Min/max bending moment — dir is a string ('MY' or 'MZ'), not an integer
    const mz = out.GetMinMaxBendingMoment(bid, 'MZ', lc);
    console.log(`Member ${bid} MZ range: [${mz[0].toFixed(3)}, ${mz[2].toFixed(3)}]`);

    // Min/max shear force
    const fy = out.GetMinMaxShearForce(bid, 'FY', lc);
    console.log(`Member ${bid} FY range: [${fy[0].toFixed(3)}, ${fy[2].toFixed(3)}]`);

    // Support reactions — returns [FX, FY, FZ, MX, MY, MZ]
    const nid = nodeList[0];
    const r = out.GetSupportReactions(nid, lc);
    console.log(`Node ${nid} reactions: FX=${r[0].toFixed(3)} FY=${r[1].toFixed(3)} FZ=${r[2].toFixed(3)}`);

    // Output units
    const forceUnit = out.GetOutputUnitForForce();
    const momentUnit = out.GetOutputUnitForMoment();
    console.log(`Units: Force=${forceUnit}, Moment=${momentUnit}`);
}
