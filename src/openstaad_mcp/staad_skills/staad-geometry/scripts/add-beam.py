# add-beam.py
# Adds a single beam between two new nodes.
# Adjust coordinates to match the model baseUnit (English=inches, Metric=meters).

geo = staad.Geometry

# Example: horizontal beam at 10ft (120in) elevation, 20ft (240in) span
n1 = geo.AddNode(0, 118.11, 0)      # node at start (118.11 in = ~3m)
n2 = geo.AddNode(236.22, 118.11, 0) # node at end   (236.22 in = ~6m)
b = geo.AddBeam(n1, n2)

print(f'Node {n1}: (0, 118.11, 0)')
print(f'Node {n2}: (236.22, 118.11, 0)')
print(f'Beam {b}: from node {n1} to node {n2}')
