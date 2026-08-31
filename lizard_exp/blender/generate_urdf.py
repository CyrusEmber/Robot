import bpy
import bmesh
import os
import shutil
import struct
from mathutils import Vector, Matrix

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BLEND_IN = os.path.join(_SCRIPT_DIR, "lizard_stance.blend")
OUT_DIR = os.path.join(_SCRIPT_DIR, "..", "lizard_urdf")
TOTAL_MASS = 72.0
MICRO_MASS = 0.05
SHELL_FACTOR = 1.4

AXIS_MAP = {
    "yaw": ("0 0 1", -0.6, 0.6, 80, 4),
    "pitch": ("1 0 0", -0.5, 0.5, 80, 4),
    "haa": ("0 1 0", -0.6, 0.6, 120, 8),
    "hfe": ("0 0 1", -1.2, 1.2, 150, 8),
    "kfe": ("0 1 0", -1.6, 1.6, 150, 8),
    "foot": ("1 0 0", -0.5, 0.5, 30, 6),
}

BALL_MESHES = {
    "Roundcube.001", "Roundcube.017", "Roundcube.025", "Roundcube.018", "Roundcube.019",
    "Roundcube.014", "Roundcube.007", "Roundcube.010", "Roundcube.002",
    "Roundcube.013", "Roundcube.006", "Roundcube.005", "Roundcube",
    "Roundcube.015", "Roundcube.008", "Roundcube.011", "Roundcube.003",
}

bpy.ops.wm.open_mainfile(filepath=_BLEND_IN)
depsgraph = bpy.context.evaluated_depsgraph_get()
scene = bpy.context.scene

arm = next(o for o in scene.objects if o.type == "ARMATURE")
bones = {b.name: {"head": b.head_local.copy(), "parent": b.parent.name if b.parent else None} for b in arm.data.bones}

link_meshes = {}
for obj in scene.objects:
    if obj.type == "MESH" and obj.parent_type == "BONE":
        link_meshes.setdefault(obj.parent_bone, []).append(obj)

missing = [b for b in bones if b not in link_meshes]
print("links_without_mesh=%s" % missing)

for sub in ("visual", "collision"):
    sub_path = os.path.join(OUT_DIR, "meshes", sub)
    if os.path.exists(sub_path):
        shutil.rmtree(sub_path)
os.makedirs(os.path.join(OUT_DIR, "meshes", "visual"), exist_ok=True)
os.makedirs(os.path.join(OUT_DIR, "meshes", "collision"), exist_ok=True)


def build_bmesh(mesh_objects, offset, evaluated):
    bm = bmesh.new()
    for obj in mesh_objects:
        source = obj.evaluated_get(depsgraph) if evaluated else obj
        me = source.to_mesh()
        mat = obj.matrix_world.copy()
        mat.translation -= offset
        me.transform(mat)
        bm.from_mesh(me)
        source.to_mesh_clear()
    return bm


def export_stl(bm, path):
    tris = []
    for face in bm.faces:
        vs = face.verts
        if len(vs) == 3:
            tris.append((vs[0].co, vs[1].co, vs[2].co))
        else:
            for i in range(1, len(vs) - 1):
                tris.append((vs[0].co, vs[i].co, vs[i + 1].co))
    with open(path, "wb") as fh:
        fh.write(b"lizard urdf export".ljust(80, b"\0"))
        fh.write(struct.pack("<I", len(tris)))
        for va, vb, vc in tris:
            normal = (vb - va).cross(vc - va)
            length = normal.length
            normal = normal / length if length > 0 else Vector((0.0, 0.0, 0.0))
            fh.write(struct.pack("<12fH", normal.x, normal.y, normal.z,
                                 va.x, va.y, va.z, vb.x, vb.y, vb.z, vc.x, vc.y, vc.z, 0))
    bm.free()


link_data = {}
for link, bone in bones.items():
    offset = bone["head"]
    entry = {"parent": bone["parent"], "origin": offset}
    if link in link_meshes:
        objs = link_meshes[link]
        vis_bm = build_bmesh(objs, offset, True)
        area = sum(f.calc_area() for f in vis_bm.faces)
        coords = [v.co.copy() for v in vis_bm.verts]
        export_stl(vis_bm, os.path.join(OUT_DIR, "meshes", "visual", "%s_visual.stl" % link))
        col_objs = [o for o in objs if o.name not in BALL_MESHES]
        if col_objs:
            col_bm = build_bmesh(col_objs, offset, False)
            export_stl(col_bm, os.path.join(OUT_DIR, "meshes", "collision", "%s_collision.stl" % link))
        entry["has_collision"] = bool(col_objs)
        entry["area"] = area
        entry["aabb_min"] = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
        entry["aabb_max"] = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
    else:
        entry["has_collision"] = False
        entry["area"] = 0.0
        entry["aabb_min"] = Vector((-0.005, -0.005, -0.005))
        entry["aabb_max"] = Vector((0.005, 0.005, 0.005))
    link_data[link] = entry

micro_count = sum(1 for e in link_data.values() if e["area"] == 0.0)
solid_budget = TOTAL_MASS - micro_count * MICRO_MASS
total_area = sum(e["area"] for e in link_data.values())
for entry in link_data.values():
    entry["mass"] = MICRO_MASS if entry["area"] == 0.0 else solid_budget * entry["area"] / total_area


def inertia_box(mass, aabb_min, aabb_max):
    x = max(aabb_max.x - aabb_min.x, 1e-4)
    y = max(aabb_max.y - aabb_min.y, 1e-4)
    z = max(aabb_max.z - aabb_min.z, 1e-4)
    ixx = mass / 12.0 * (y * y + z * z)
    iyy = mass / 12.0 * (x * x + z * z)
    izz = mass / 12.0 * (x * x + y * y)
    return ixx, iyy, izz


def joint_spec(link):
    for suffix, spec in AXIS_MAP.items():
        if link.endswith("_" + suffix):
            return spec
    return None


xml = ['<?xml version="1.0"?>', '<robot name="lizard_robot">']
for link, entry in link_data.items():
    mass = entry["mass"]
    com = (entry["aabb_min"] + entry["aabb_max"]) / 2.0
    ixx, iyy, izz = inertia_box(mass, entry["aabb_min"], entry["aabb_max"])
    xml.append('  <link name="%s">' % link)
    xml.append('    <inertial>')
    xml.append('      <origin xyz="%.6f %.6f %.6f" rpy="0 0 0"/>' % (com.x, com.y, com.z))
    xml.append('      <mass value="%.4f"/>' % mass)
    xml.append('      <inertia ixx="%.6f" ixy="0" ixz="0" iyy="%.6f" iyz="0" izz="%.6f"/>' % (ixx, iyy, izz))
    xml.append('    </inertial>')
    if entry["area"] > 0.0:
        xml.append('    <visual>')
        xml.append('      <origin xyz="0 0 0" rpy="0 0 0"/>')
        xml.append('      <geometry><mesh filename="../meshes/visual/%s_visual.stl"/></geometry>' % link)
        xml.append('    </visual>')
        if entry["has_collision"]:
            xml.append('    <collision>')
            xml.append('      <origin xyz="0 0 0" rpy="0 0 0"/>')
            xml.append('      <geometry><mesh filename="../meshes/collision/%s_collision.stl"/></geometry>' % link)
            xml.append('    </collision>')
    xml.append('  </link>')

for link, entry in link_data.items():
    parent = entry["parent"]
    if parent is None:
        continue
    rel = entry["origin"] - link_data[parent]["origin"]
    spec = joint_spec(link)
    axis, lo, hi, effort, vel = spec
    xml.append('  <joint name="%s_joint" type="revolute">' % link)
    xml.append('    <parent link="%s"/>' % parent)
    xml.append('    <child link="%s"/>' % link)
    xml.append('    <origin xyz="%.6f %.6f %.6f" rpy="0 0 0"/>' % (rel.x, rel.y, rel.z))
    xml.append('    <axis xyz="%s"/>' % axis)
    xml.append('    <limit lower="%.2f" upper="%.2f" effort="%d" velocity="%d"/>' % (lo, hi, effort, vel))
    xml.append('  </joint>')

xml.append('</robot>')
urdf_path = os.path.join(OUT_DIR, "lizard.urdf")
with open(urdf_path, "w") as f:
    f.write("\n".join(xml) + "\n")

mass_sum = sum(e["mass"] for e in link_data.values())
print("=== URDF ===")
print("links=%d joints=%d total_mass=%.2fkg" % (len(link_data), len(link_data) - 1, mass_sum))
print("saved=%s" % urdf_path)
print("=== DONE ===")
