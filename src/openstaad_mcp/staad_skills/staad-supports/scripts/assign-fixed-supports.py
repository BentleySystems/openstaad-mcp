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

# Create fixed support once — reuse the ID for all assignments
fix_id = sup.CreateSupportFixed()
print(f'Fixed support ID: {fix_id}')

# AssignSupportToNode takes a SINGLE node ID — iterate with a loop
for nid in base_nodes:
    sup.AssignSupportToNode(nid, fix_id)

print(f'Fixed support assigned to {len(base_nodes)} nodes')
