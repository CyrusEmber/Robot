import bpy
import mathutils
import os

_BLEND_IN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lizard_stance.blend")
BLEND_OUT = _BLEND_IN

# bone name -> (head mesh, tail mesh or None for outward stub)
LEG_MAP = {
    "lf": {"haa": ("Roundcube.014", "Roundcube.013"), "hfe": ("Roundcube.013", "Roundcube.015"),
           "kfe": ("Roundcube.015", "Roundcube.016"), "foot": ("Roundcube.016", None)},
    "rf": {"haa": ("Roundcube.007", "Roundcube.006"), "hfe": ("Roundcube.006", "Roundcube.008"),
           "kfe": ("Roundcube.008", "Roundcube.009"), "foot": ("Roundcube.009", None)},
    "rl": {"haa": ("Roundcube.010", "Roundcube.005"), "hfe": ("Roundcube.005", "Roundcube.011"),
           "kfe": ("Roundcube.011", "Roundcube.012"), "foot": ("Roundcube.012", None)},
    "rr": {"haa": ("Roundcube.002", "Roundcube"), "hfe": ("Roundcube", "Roundcube.003"),
           "kfe": ("Roundcube.003", "Roundcube.004"), "foot": ("Roundcube.004", None)},
}

scene = bpy.context.scene
meshes = {o.name: o for o in scene.objects if o.type == "MESH"}
world_cache = {o.name: o.matrix_world.copy() for o in scene.objects if o.type == "MESH"}

arm = next(o for o in scene.objects if o.type == "ARMATURE")
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
eb = arm.data.edit_bones

moved = 0
for leg, joints in LEG_MAP.items():
    for joint, (head_mesh, tail_mesh) in joints.items():
        bone = eb["%s_%s" % (leg, joint)]
        head = mathutils.Vector(meshes[head_mesh].matrix_world.translation)
        if tail_mesh is not None:
            tail = mathutils.Vector(meshes[tail_mesh].matrix_world.translation)
        else:
            outward = 0.1 if head.x > 0 else -0.1
            tail = head + mathutils.Vector((outward, 0.0, 0.0))
        bone.head = head
        bone.tail = tail
        moved += 1

bpy.ops.object.mode_set(mode="OBJECT")

for obj in scene.objects:
    if obj.type == "MESH":
        obj.matrix_world = world_cache[obj.name]

bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)
print("BONES_FIXED %d saved=%s" % (moved, BLEND_OUT))
