"""v8 asset fix: rotate +180 deg about Z and rename bones to real anatomy.

Root cause of v6 tail-first walking: the rig's bone names are 180 deg off the
model's anatomy -- the "neck1-3" chain is the tail (antenna tip, build_rig.py
`antenna_tip`), the "tail_yaw/tail_pitch" chain carries the sphere HEAD
(`sphere_tip`), and the leg names are front/rear + left/right swapped. v6
rotated the NAME-head onto task +X, so the paid direction is anatomically
tail-first.

This one-shot (same discipline as rotate_rig.py):
  1. rigid world rotation R_z(+180 deg) of every top-level object (kept as
     object transform, no bake) -- net from the pre-v6 blend: -90 + 180 =
     +90 deg, sphere head -Y -> +X, antenna tail -> -X
  2. rename 26 bones to anatomy (base_link untouched; URDF joint order =
     bone order, renames never reorder, so obs/action slot ORDER is stable)
  3. re-target every mesh's parent_bone (explicit, no reliance on rename
     propagation; matrix_world preserved via the build_rig.py pattern)
  4. asserts: 1e-6 rigid self-check (bones + mesh anchors at R @ old),
     mesh->bone integrity, final layout (head +X, antenna -X, front legs
     ahead of root, left legs +Y)

Run: E:\\SteamLibrary\\steamapps\\common\\Blender\\blender.exe --background --python rename_flip_v8.py
"""

import math
import os

import bpy
from mathutils import Matrix

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BLEND = os.path.join(_SCRIPT_DIR, "lizard_stance.blend")
R = Matrix.Rotation(math.radians(180.0), 4, "Z")
TOL = 1e-6

# spine: name-head chain -> real tail, name-tail chain -> real neck/head
RENAME = {
    "rear_yaw": "chest_yaw", "rear_pitch": "chest_pitch",
    "tail_yaw": "neck_yaw", "tail_pitch": "neck_pitch",
    "neck1_yaw": "tail1_yaw", "neck1_pitch": "tail1_pitch",
    "neck2_yaw": "tail2_yaw", "neck2_pitch": "tail2_pitch",
    "neck3_yaw": "tail3_yaw", "neck3_pitch": "tail3_pitch",
}
# legs: anatomical swap (old rl = right-front, old rr = left-front,
# old lf = right-rear, old rf = left-rear -- derived from old blend coords
# with head at -Y: left = +X_old)
LEG_SWAP = {"rl": "rf", "rf": "rl", "lf": "rr", "rr": "lf"}
for _old, _new in LEG_SWAP.items():
    for _j in ("haa", "hfe", "kfe", "foot"):
        RENAME["%s_%s" % (_old, _j)] = "%s_%s" % (_new, _j)

bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene
print("=== OBJECT TREE ===")
top_level = []
for o in scene.objects:
    print("obj=%s type=%s parent=%s parent_type=%s" % (o.name, o.type, o.parent.name if o.parent else None, o.parent_type))
    if o.parent is None:
        top_level.append(o)
arm = next(o for o in scene.objects if o.type == "ARMATURE")

assert len(arm.data.bones) == 27, "expected 27 bones, got %d" % len(arm.data.bones)
missing = [n for n in RENAME if n not in arm.data.bones.keys()]
assert not missing, "bones missing from blend: %s" % missing
assert len(RENAME) == 26, "rename map must cover 26 bones, got %d" % len(RENAME)


def bone_world(b):
    return (arm.matrix_world @ b.head_local).copy()


snap_bones = {b.name: bone_world(b) for b in arm.data.bones}
snap_mesh = {}
mesh_retarget = {}
for o in scene.objects:
    if o.type == "MESH" and o.data and len(o.data.vertices):
        snap_mesh[o.name] = (o.matrix_world @ o.data.vertices[0].co).copy()
        if o.parent_type == "BONE":
            mesh_retarget[o.name] = RENAME.get(o.parent_bone, o.parent_bone)


def verify(tag, use_renamed=False):
    for name, old in snap_bones.items():
        cur = RENAME.get(name, name) if use_renamed else name
        w = bone_world(arm.data.bones[cur])
        assert (w - R @ old).length < TOL, "bone %s->%s %s: %s != %s" % (tag, name, cur, w, R @ old)
    for name, old in snap_mesh.items():
        o = scene.objects[name]
        w = o.matrix_world @ o.data.vertices[0].co
        assert (w - R @ old).length < TOL, "mesh %s %s: %s != %s" % (tag, name, w, R @ old)


# 1) rigid world rotation: rotate every top-level object (children follow)
for o in top_level:
    o.matrix_world = R @ o.matrix_world
bpy.context.view_layer.update()
verify("after-rotate")

# 2) two-phase rename (swaps would collide in one phase)
tmp = "__v8tmp__"
for name in list(arm.data.bones.keys()):
    if name in RENAME:
        arm.data.bones[name].name = tmp + name
for name in list(arm.data.bones.keys()):
    if name.startswith(tmp):
        arm.data.bones[name].name = RENAME[name[len(tmp):]]
bpy.context.view_layer.update()

# 3) re-target mesh parenting explicitly (build_rig pattern: keep world)
bone_names = set(arm.data.bones.keys())
for o in scene.objects:
    if o.type == "MESH" and o.name in mesh_retarget:
        assert o.parent_type == "BONE", "mesh %s lost bone parenting" % o.name
        mw = o.matrix_world.copy()
        o.parent_bone = mesh_retarget[o.name]
        o.matrix_world = mw
        assert o.parent_bone in bone_names, "mesh %s -> unknown bone %s" % (o.name, o.parent_bone)
verify("after-rename", use_renamed=True)

# 4) final layout asserts (head +X, tail -X, left +Y)
w = {n: bone_world(arm.data.bones[n]) for n in
     ("base_link", "neck_pitch", "tail3_pitch", "lf_haa", "rf_haa", "rl_haa", "rr_haa")}
root = w["base_link"]
assert w["neck_pitch"].x > root.x + 1.0, "sphere head must be +X: %s" % w["neck_pitch"]
assert w["tail3_pitch"].x < root.x - 1.0, "antenna tail must be -X: %s" % w["tail3_pitch"]
for n in ("lf_haa", "rf_haa"):
    assert w[n].x > root.x, "front leg %s behind root: %s" % (n, w[n])
for n in ("rl_haa", "rr_haa"):
    assert w[n].x < root.x, "rear leg %s ahead of root: %s" % (n, w[n])
for n in ("lf_haa", "rl_haa"):
    assert w[n].y > 0, "left leg %s on -Y: %s" % (n, w[n])
for n in ("rf_haa", "rr_haa"):
    assert w[n].y < 0, "right leg %s on +Y: %s" % (n, w[n])

print("=== LAYOUT (head=+x, left=+y) ===")
for n, v in w.items():
    print("BONE %-11s = (%7.3f, %7.3f, %7.3f)" % (n, v.x, v.y, v.z))

bpy.ops.wm.save_mainfile(filepath=BLEND)
print("ROTATED +180deg Z + renamed 26 bones to anatomy, verified %d bones %d mesh anchors"
      % (len(snap_bones), len(snap_mesh)))
print("=== DONE ===")
