# check-tension-compression-spring.py
# Correctly marks an existing support spring as Tension-Only or Compression-Only, and verifies it.
#
# DO NOT use CreateTensionOnlySpring/CreateCompressionOnlySpring — live-verified broken: the support
# they create never carries a stiffness value, in every scenario tested, independent of node/assign
# order. Use SetSupportSpringBehavior instead — confirmed live and matches STAAD.Pro's own production
# import/export code (StaadWriter.cs), which calls only this function.
#
# Per STAAD.Pro's SPRING TENSION/COMPRESSION command (TR.27.5), this only *marks* an existing support
# spring — it does not create one. The node must already have a real spring in that DOF first.
#
# SetSupportSpringBehavior's built-in validation ("[-7504] Spring not defined at node.") is NODE-level
# only, not per-direction — live-verified: if the node has a real spring in FY but you flag FX (which
# has none), it succeeds silently and creates the same broken, unanalyzable state as the two functions
# above. So this script checks EVERY flagged direction individually before calling — do not rely on
# the function itself to catch a direction-specific mismatch.

sup = staad.Support

node = 9          # target node
compression_or_tension_flag = 1   # 0=compression-only, 1=tension-only (per openstaadpy source docstring)
spring_flags = [0, 1, 0]          # [FX,FY,FZ] enable — each flagged direction must already have a real spring

# Step 1: establish a REAL spring in the target direction(s).
fb_id = sup.CreateSupportFixedBut(ReleaseSpec=[0, -1, 0, 0, 0, 0], SpringSpec=[0, 1000.0, 0, 0, 0, 0])
sup.AssignSupportToEntityList(fb_id, [node])
_, _, _, springs_before = sup.GetSupportInformationEx(node)

# Verify EVERY flagged direction has a real spring — SetSupportSpringBehavior will not catch this itself.
missing = [i for i, flag in enumerate(spring_flags) if flag and springs_before[i] == 0]
if missing:
    print(f'ERROR: node {node} has no real spring in direction(s) {missing} — cannot proceed.')

# Step 2: mark it tension/compression-only — modifies the existing support IN PLACE (same support
# ID, stiffness preserved), unlike CreateTensionOnlySpring/CreateCompressionOnlySpring.
sup.SetSupportSpringBehavior(compression_or_tension_flag, [node], spring_flags)

# Verify the spring stiffness survived — do not assume the call succeeded.
_, support_type, releases, springs = sup.GetSupportInformationEx(node)
broken = [i for i, flag in enumerate(spring_flags) if flag and springs[i] == 0]
if broken:
    print(
        f'ERROR: node {node} has support type {support_type} but NO spring stiffness in '
        f'direction(s) {broken}. Analysis will fail with "SPRING TENSION/COMPRESSION SPECIFIED AT '
        f'A JOINT DIRECTION THAT DOES NOT HAVE A SPRING". Do not proceed to analysis with this '
        f'support as-is.'
    )
else:
    print(f'OK: node {node} has real spring stiffness in every flagged direction: {springs}')

# Gotcha: this marking is added to a persistent, model-level SPRING TENSION/COMPRESSION list that
# RemoveSupportFromNode does NOT clear. If this node's support is later fully removed, analysis
# will fail on the whole model with the same "...DOES NOT HAVE A SPRING" error. To "undo" a
# tension/compression-only marking, leave a real spring on the node instead of removing it entirely.

