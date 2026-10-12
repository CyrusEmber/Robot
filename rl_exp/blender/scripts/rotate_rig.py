"""v5.6 asset fix: rotate the whole lizard rig -90 deg about Z (head +y -> +x).

Root cause of v5 crab-walking: URDF long axis was Y while the velocity task
commands/reward assume base +X is forward. Rigid world rotation of the SSOT
blend, baked into bone data (armature object transform back to identity so
generate_urdf.py's armature-local == world assumption still holds).

Self-check: every mesh anchor and every bone head must land exactly at
R @ old_world (tol 1e-6) after the object-level rotation. Any bone-roll/
parenting surprise trips an assert.

The rotation is kept as the armature's object transform (NOT baked via
transform_apply -- that introduces float drift through bone roll round-trips).
Consumers read world space: generate_urdf.py uses matrix_world @ head_local,
fix_bones.py converts world<->armature explicitly.

Run: blender.exe --background --python rotate_rig.py
"""

import math
import os

import bpy
from mathutils import Matrix

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BLEND = os.path.join(_SCRIPT_DIR, "lizard_stance.blend")
R = Matrix.Rotation(math.radians(-90.0), 4, "Z")
TOL = 1e-6

bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene

print("=== OBJECT TREE ===")
top_level = []
for o in scene.objects:
    print("obj=%s type=%s parent=%s parent_type=%s" % (o.name, o.type, o.parent.name if o.parent else None, o.parent_type))
    if o.parent is None:
        top_level.append(o)
arm = next(o for o in scene.objects if o.type == "ARMATURE")

def bone_world(b):
    return (arm.matrix_world @ b.head_local).copy()

snap_bones = {b.name: bone_world(b) for b in arm.data.bones}
snap_mesh = {}
for o in scene.objects:
    if o.type == "MESH" and o.data and len(o.data.vertices):
        snap_mesh[o.name] = (o.matrix_world @ o.data.vertices[0].co).copy()

# 1) rigid world rotation: rotate every top-level object (children follow)
for o in top_level:
    o.matrix_world = R @ o.matrix_world
bpy.context.view_layer.update()

def verify(tag):
    for name, old in snap_bones.items():
        w = bone_world(arm.data.bones[name])
        assert (w - R @ old).length < TOL, "bone %s %s: %s != %s" % (tag, name, w, R @ old)
    for name, old in snap_mesh.items():
        o = scene.objects[name]
        w = o.matrix_world @ o.data.vertices[0].co
        assert (w - R @ old).length < TOL, "mesh %s %s: %s != %s" % (tag, name, w, R @ old)

verify("after-rotate")

for name in ("neck1_yaw", "tail_yaw", "lf_haa", "rf_haa", "rl_haa", "rr_haa"):
    print("HEAD %-10s = (%.3f, %.3f, %.3f)" % ((name,) + tuple(bone_world(arm.data.bones[name]))))

bpy.ops.wm.save_mainfile(filepath=BLEND)
print("ROTATED -90deg Z (object-level, no bake), verified %d bones %d mesh anchors" % (len(snap_bones), len(snap_mesh)))
print("=== DONE ===")
