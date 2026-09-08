# assign-fixed-supports.py
# Assigns fixed supports to specified base nodes.
# AssignSupportToNode takes ONE node ID at a time — use a loop for multiple nodes.

geo = staad.Geometry
sup = staad.Support

# Get actual node IDs — identify base nodes (elevation = 0)
node_list = list(geo.GetNodeList())
base_nodes = []
for nid in node_list:
    x, y, z = geo.GetNodeCoordinates(nid)
    if abs(y) < 0.001:   # y=0 for Y-up models; use z for Z-up
        base_nodes.append(nid)
print(f'Base nodes found: {base_nodes}')

# Assigning to a node that already has a support silently overwrites it — check GetSupportNodes()
# membership FIRST, since GetSupportInformationEx raises "[-1] General error." on a node with no
# support at all; only call it (guarded in try/except) for nodes already confirmed supported.
existing = set(sup.GetSupportNodes())
already_supported = [nid for nid in base_nodes if nid in existing]
if already_supported:
    for nid in already_supported:
        try:
            support_no, support_type, releases, springs = sup.GetSupportInformationEx(nid)
            print(f'WARNING: node {nid} already has support (id={support_no}, type={support_type}) '
                  f'and will be overwritten.')
        except Exception as e:
            print(f'WARNING: node {nid} already has a support and will be overwritten '
                  f'(could not read details: {e}).')

# Create fixed support once — reuse the ID for all assignments
fix_id = sup.CreateSupportFixed()
print(f'Fixed support ID: {fix_id}')

# AssignSupportToNode takes a SINGLE node ID — iterate with a loop
for nid in base_nodes:
    sup.AssignSupportToNode(nid, fix_id)

print(f'Fixed support assigned to {len(base_nodes)} nodes')
