import bpy
import mathutils

BLEND_OUT = r"C:\Users\yanke03\Desktop\1234_rigged.blend"
MICRO = 0.005
Z_SPINE = -0.1674
Z_LEG = -0.2233

b001 = (0.0000, 0.0116, 0.0221)
b017 = (0.0000, 1.2679, Z_SPINE)
b025 = (0.0000, 2.3375, Z_SPINE)
b018 = (0.0055, 2.8817, Z_SPINE)
b019 = (0.0055, 3.3166, Z_SPINE)
sphere_tip = (-0.0000, -0.1792, 0.0669)
antenna_tip = (0.0055, 3.9000, Z_SPINE)

leg_pivots = {
    "lf": {"haa": (-0.3215, 1.8647, Z_LEG), "hfe": (-0.8231, 1.8647, Z_LEG), "kfe": (-1.2053, 1.8647, Z_LEG), "foot": (-1.3309, 1.8647, -0.1870)},
    "rf": {"haa": (0.3358, 1.8708, Z_LEG), "hfe": (0.8375, 1.8708, Z_LEG), "kfe": (1.2196, 1.8708, Z_LEG), "foot": (1.3452, 1.8708, -0.1870)},
    "rl": {"haa": (-0.3633, 0.7924, Z_LEG), "hfe": (-0.8650, 0.7924, Z_LEG), "kfe": (-1.2471, 0.7925, Z_LEG), "foot": (-1.3728, 0.7925, -0.1870)},
    "rr": {"haa": (0.3595, 0.7875, Z_LEG), "hfe": (0.8611, 0.7875, Z_LEG), "kfe": (1.2433, 0.7875, Z_LEG), "foot": (1.3689, 0.7875, -0.1870)},
}

mesh_groups = {
    "base_link": ["Cylinder.010"],
    "rear_pitch": ["Roundcube.017", "Cylinder", "Cylinder.001"],
    "tail_pitch": ["Roundcube.001", "Sphere"],
    "neck1_pitch": ["Roundcube.025", "Cylinder.011"],
    "neck2_pitch": ["Roundcube.018", "Cylinder.012"],
    "neck3_pitch": ["Roundcube.019", "Cylinder.013"],
    "lf_haa": ["Roundcube.014", "Cylinder.008"],
    "lf_hfe": ["Roundcube.013", "Cylinder.009"],
    "lf_kfe": ["Roundcube.015"],
    "lf_foot": ["Roundcube.016"],
    "rf_haa": ["Roundcube.007", "Cylinder.004"],
    "rf_hfe": ["Roundcube.006", "Cylinder.005"],
    "rf_kfe": ["Roundcube.008"],
    "rf_foot": ["Roundcube.009"],
    "rl_haa": ["Roundcube.010", "Cylinder.006"],
    "rl_hfe": ["Roundcube.005", "Cylinder.007"],
    "rl_kfe": ["Roundcube.011"],
    "rl_foot": ["Roundcube.012"],
    "rr_haa": ["Roundcube.002", "Cylinder.002"],
    "rr_hfe": ["Roundcube", "Cylinder.003"],
    "rr_kfe": ["Roundcube.003"],
    "rr_foot": ["Roundcube.004"],
}

scene = bpy.context.scene

for obj in list(scene.objects):
    if obj.type == "MESH":
        for mod in [m for m in obj.modifiers if m.type == "ARMATURE"]:
            obj.modifiers.remove(mod)

mesh_objects = [o for o in scene.objects if o.type == "MESH"]
world_cache = {o.name: o.matrix_world.copy() for o in mesh_objects}
for obj in mesh_objects:
    if obj.parent is not None:
        obj.parent = None
        obj.matrix_world = world_cache[obj.name]

for arm in [o for o in scene.objects if o.type == "ARMATURE"]:
    bpy.data.objects.remove(arm, do_unlink=True)

arm_data = bpy.data.armatures.new("robot_rig")
arm_obj = bpy.data.objects.new("robot_rig", arm_data)
scene.collection.objects.link(arm_obj)
bpy.context.view_layer.objects.active = arm_obj
bpy.ops.object.mode_set(mode="EDIT")
eb = arm_obj.data.edit_bones


def add_bone(name, head, tail, parent_name=None):
    bone = eb.new(name)
    bone.head = mathutils.Vector(head)
    bone.tail = mathutils.Vector(tail)
    if parent_name:
        bone.parent = eb[parent_name]
        bone.use_connect = False
    return bone


add_bone("base_link", b017, b025)

add_bone("rear_yaw", b017, (b017[0], b017[1] + MICRO, b017[2]), "base_link")
add_bone("rear_pitch", (b017[0], b017[1] + MICRO, b017[2]), b001, "rear_yaw")
add_bone("tail_yaw", b001, (b001[0], b001[1] - MICRO, b001[2]), "rear_pitch")
add_bone("tail_pitch", (b001[0], b001[1] - MICRO, b001[2]), sphere_tip, "tail_yaw")

add_bone("neck1_yaw", b025, (b025[0], b025[1] + MICRO, b025[2]), "base_link")
add_bone("neck1_pitch", (b025[0], b025[1] + MICRO, b025[2]), b018, "neck1_yaw")
add_bone("neck2_yaw", b018, (b018[0], b018[1] + MICRO, b018[2]), "neck1_pitch")
add_bone("neck2_pitch", (b018[0], b018[1] + MICRO, b018[2]), b019, "neck2_yaw")
add_bone("neck3_yaw", b019, (b019[0], b019[1] + MICRO, b019[2]), "neck2_pitch")
add_bone("neck3_pitch", (b019[0], b019[1] + MICRO, b019[2]), antenna_tip, "neck3_yaw")

leg_parent = {"lf": "base_link", "rf": "base_link", "rl": "rear_pitch", "rr": "rear_pitch"}
for leg, piv in leg_pivots.items():
    haa, hfe, kfe, foot = piv["haa"], piv["hfe"], piv["kfe"], piv["foot"]
    outward = 1.0 if foot[0] > 0 else -1.0
    foot_out = (foot[0] + outward * 0.1, foot[1], foot[2])
    add_bone(leg + "_haa", haa, hfe, leg_parent[leg])
    add_bone(leg + "_hfe", hfe, kfe, leg + "_haa")
    add_bone(leg + "_kfe", kfe, foot, leg + "_hfe")
    add_bone(leg + "_foot", foot, foot_out, leg + "_kfe")

bpy.ops.object.mode_set(mode="OBJECT")

bone_names = set(arm_obj.data.bones.keys())
assigned = set()
for bone_name, mesh_names in mesh_groups.items():
    if bone_name not in bone_names:
        print("ERROR: bone missing %s" % bone_name)
        continue
    for mesh_name in mesh_names:
        obj = scene.objects.get(mesh_name)
        if obj is None:
            print("ERROR: mesh missing %s" % mesh_name)
            continue
        mw = obj.matrix_world.copy()
        obj.parent = arm_obj
        obj.parent_type = "BONE"
        obj.parent_bone = bone_name
        obj.matrix_world = mw
        assigned.add(mesh_name)

unassigned = [o.name for o in scene.objects if o.type == "MESH" and o.name not in assigned]
print("=== RESULT ===")
print("bones=%d joints=%d meshes_assigned=%d/%d" % (
    len(bone_names), len(bone_names) - 1, len(assigned), len([o for o in scene.objects if o.type == "MESH"])))
print("unassigned=%s" % (unassigned or "none"))
for bone in arm_obj.data.bones:
    chain = bone.parent.name if bone.parent else "-"
    print("  bone %s parent=%s" % (bone.name, chain))

bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)
print("saved: %s" % BLEND_OUT)
print("=== DONE ===")
