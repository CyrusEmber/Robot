# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Insert shoulder/hip axial rotation in an isolated palm Blender/URDF pair [m, rad, kg].

Run inside Blender with --background --python-exit-code 1 --python <this file> --
--urdf <four-axis.urdf> --probe_report <source measurements.json> --output_dir <fresh rl_exp/out/...>.
The output includes hash-named mesh copies with relative URDF references. This is a
kinematic candidate, not an adopted simulation asset. Existing idealized carrier mass/inertia is
split between two co-located carriers, preserving neutral mass properties without inventing a motor.
Twist bounds are a +/-30 degree diagnostic window, not anatomical ROM or approved policy limits.
"""

import argparse
import copy
import json
import math
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

import bpy
from mathutils import Matrix, Quaternion, Vector

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "rl_exp/tasks"))
import joint_names as names  # noqa: E402
sys.path.insert(0, str(REPO / "rl_exp/tools/runrecord"))
from binding import sha256_file as digest  # noqa: E402


def vec(element, attribute):
    return Vector(tuple(float(x) for x in element.get(attribute).split()))


def sample_meshes(arm):
    """Read deterministic evaluated mesh vertices in world coordinates [m]."""
    result = {}
    graph = bpy.context.evaluated_depsgraph_get()
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        assert obj.parent == arm and obj.parent_type == "BONE", obj.name
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        try:
            indices = sorted({i * (len(mesh.vertices) - 1) // 31 for i in range(32)})
            result[obj.name] = {"link": obj.parent_bone, "vertex_count": len(mesh.vertices),
                                "indices": indices,
                                "points": [list(evaluated.matrix_world @ mesh.vertices[i].co) for i in indices]}
        finally:
            evaluated.to_mesh_clear()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urdf", type=Path, required=True)
    parser.add_argument("--probe_report", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    output = args.output_dir.resolve()
    if REPO / "rl_exp/out" not in output.parents or output.exists():
        raise ValueError("Output must be a fresh directory below rl_exp/out")
    source_urdf = args.urdf.resolve()
    probe = json.loads(args.probe_report.read_text(encoding="utf-8"))
    source_blend = Path(probe["source"]).resolve()
    assert probe["naming"] == "palm" and digest(source_blend) == probe["source_sha256"]
    hashes = {str(p): digest(p) for p in (source_urdf, source_blend, args.probe_report.resolve())}
    root = ET.parse(source_urdf).getroot()
    links = {x.get("name"): x for x in root.findall("link")}
    joints = {x.get("name"): x for x in root.findall("joint")}
    for joint in joints.values():
        assert joint.get("type") == "revolute"
        assert vec(joint.find("origin"), "rpy").length < 1e-12, "Nonzero joint RPY unsupported"
        axis = vec(joint.find("axis"), "xyz")
        assert (axis - Vector(probe["candidate_axes_world"][joint.find("child").get("link")])).length < 2e-6
    mesh_sources = []
    for mesh in root.iter("mesh"):
        path = (source_urdf.parent / mesh.get("filename")).resolve()
        hashes[str(path)] = digest(path)
        mesh_sources.append((mesh, path))

    bpy.ops.wm.open_mainfile(filepath=str(source_blend))
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    assert all(b.matrix_basis == Matrix.Identity(4) for b in arm.pose.bones), "Bake neutral pose first"
    bpy.context.view_layer.update()
    old_meshes = sample_meshes(arm)
    old_heads = {b.name: arm.matrix_world @ b.head_local for b in arm.data.bones}
    # Bind the input URDF to the actual Blender pivots before any candidate is written.
    for j in joints.values():
        parent, child = j.find("parent").get("link"), j.find("child").get("link")
        assert (old_heads[child] - old_heads[parent] - vec(j.find("origin"), "xyz")).length < 3e-6
    remap, axes, definitions = {}, dict(probe["candidate_axes_world"]), {}
    for leg in names.LEGS:
        chain = [names.link_name(leg, r) for r in names.PALM_NAMING[leg]]
        swing, abduct, bend, end = chain
        assert vec(joints[abduct + "_joint"].find("origin"), "xyz").length < 1e-12, "Shoulder/hip axes must share a pivot"
        assert {n for n in links if n.startswith(leg + "_")} == set(chain)
        for parent, child in zip(chain, chain[1:]):
            assert joints[child + "_joint"].find("parent").get("link") == parent
        twist = names.link_name(leg, names.PALM_SPATIAL_NAMING[leg][2])
        direction = vec(joints[bend + "_joint"].find("origin"), "xyz").normalized()
        # Physical positive convention: hip/shoulder -> knee/elbow, on both sides.
        # Mirroring a rotation about this polar direction therefore reverses the angle sign.
        axes[twist] = list(direction)
        old_link = links[abduct]
        new_link = copy.deepcopy(old_link)
        new_link.set("name", twist)
        carrier = copy.deepcopy(links[swing].find("inertial"))
        assert vec(carrier.find("origin"), "xyz").length == 0
        tensor = carrier.find("inertia")
        assert all(float(tensor.get(k)) == 0 for k in ("ixy", "ixz", "iyz"))
        assert len({tensor.get(k) for k in ("ixx", "iyy", "izz")}) == 1
        for element, keys in ((carrier.find("mass"), ("value",)),
                              (tensor, ("ixx", "iyy", "izz", "ixy", "ixz", "iyz"))):
            for key in keys:
                element.set(key, format(float(element.get(key)) / 2, ".12g"))
        links[swing].remove(links[swing].find("inertial"))
        links[swing].append(copy.deepcopy(carrier))
        for child in list(old_link):
            old_link.remove(child)
        old_link.append(carrier)
        root.insert(list(root).index(old_link) + 1, new_link)
        joint = copy.deepcopy(joints[abduct + "_joint"])
        joint.set("name", twist + "_joint")
        joint.find("parent").set("link", abduct)
        joint.find("child").set("link", twist)
        joint.find("axis").set("xyz", " ".join(format(v, ".12g") for v in direction))
        joint.find("limit").set("lower", str(-math.pi / 6))
        joint.find("limit").set("upper", str(math.pi / 6))
        # Effort/speed inherited only as placeholders; no new drive sizing claim.
        root.insert(list(root).index(joints[abduct + "_joint"]) + 1, joint)
        joints[bend + "_joint"].find("parent").set("link", twist)
        remap[abduct] = twist
        definitions[leg] = {"abduct": abduct, "twist": twist, "bend": bend, "end": end,
                            "axis_neutral": list(direction)}

    transforms = {obj.name: obj.matrix_world.copy() for obj in bpy.context.scene.objects if obj.type == "MESH"}
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for item in definitions.values():
        old = arm.data.edit_bones[item["abduct"]]
        twist = arm.data.edit_bones.new(item["twist"])
        twist.head, twist.tail, twist.roll = old.head.copy(), old.tail.copy(), old.roll
        twist.parent = old
        twist.use_connect = False
        bend = arm.data.edit_bones[item["bend"]]
        bend.use_connect = False
        bend.parent = twist
    bpy.ops.object.mode_set(mode="OBJECT")
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and obj.parent_bone in remap:
            obj.parent_bone = remap[obj.parent_bone]
            obj.matrix_world = transforms[obj.name]
    bpy.context.view_layer.update()
    after = sample_meshes(arm)
    residual = max((Vector(a) - Vector(b)).length for name, row in old_meshes.items()
                   for a, b in zip(row["points"], after[name]["points"]))
    assert residual < 5e-6, f"Neutral mesh moved: {residual} m"
    for name, head in old_heads.items():
        assert (arm.matrix_world @ arm.data.bones[name].head_local - head).length < 5e-6
    output.mkdir(parents=True, exist_ok=False)
    (output / "meshes").mkdir()
    # The copied upper-limb link contains copied XML mesh elements, so rewrite all
    # surviving references after the topology edit, not only the source elements.
    filenames = {mesh.get("filename"): path for mesh, path in mesh_sources}
    for mesh in root.iter("mesh"):
        source_mesh = filenames[mesh.get("filename")]
        relative = Path("meshes") / (hashes[str(source_mesh)] + source_mesh.suffix)
        destination = output / relative
        if not destination.exists():
            shutil.copyfile(source_mesh, destination)
        assert digest(destination) == hashes[str(source_mesh)]
        mesh.set("filename", relative.as_posix())
    candidate = output / "palm_spatial.urdf"
    ET.indent(root)
    ET.ElementTree(root).write(candidate, encoding="utf-8", xml_declaration=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "palm_spatial.blend"))
    # Reopen the saved artifact before collecting motion evidence.
    bpy.ops.wm.open_mainfile(filepath=str(output / "palm_spatial.blend"))
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    frames = {b.name: arm.matrix_world @ b.matrix for b in arm.pose.bones}
    cases = [("neutral", {})]
    for leg, item in definitions.items():
        for sign in (-1, 1):
            cases.append((f"{leg}_twist_{sign:+d}", {item["twist"]: sign * math.radians(10)}))
    cases.append(("combined", {name: .04 * (-1 if i % 2 else 1) for i, name in enumerate(axes)}))
    snapshots = []
    for label, q in cases:
        for bone in arm.pose.bones:
            bone.matrix_basis = Matrix.Identity(4)
        for name, angle in q.items():
            bone = arm.pose.bones[name]
            bone.rotation_mode = "QUATERNION"
            bone.rotation_quaternion = Quaternion(frames[name].to_3x3().inverted() @ Vector(axes[name]), angle)
        bpy.context.view_layer.update()
        snapshots.append({"case": label, "q_rad": {n + "_joint": v for n, v in q.items()},
                          "pivots": {b.name: list(arm.matrix_world @ b.head) for b in arm.pose.bones},
                          "meshes": sample_meshes(arm)})
    assert all(digest(path) == value for path, value in hashes.items()), "Source changed"
    report = {"status": "KINEMATIC_CANDIDATE_NOT_ADOPTED", "naming": "palm_spatial",
              "source_urdf": str(source_urdf), "source_blend": str(source_blend), "input_sha256": hashes,
              "candidate_urdf": str(candidate), "candidate_sha256": digest(candidate),
              "candidate_blend_sha256": digest(output / "palm_spatial.blend"),
              "candidate_files_sha256": {p.relative_to(output).as_posix(): digest(p)
                                         for p in sorted(output.rglob("*")) if p.is_file()},
              "builder_sha256": digest(__file__), "definitions": definitions,
              "axes_neutral": axes, "neutral_mesh_residual_m": residual,
              "snapshots": snapshots,
              "limits": "Twist +/-30 deg diagnostic only; effort/velocity copied placeholders. No motor geometry or drive validation."}
    (output / "build.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("SPATIAL_CANDIDATE_BUILT", candidate, "neutral_mesh_residual_m", residual, flush=True)


if __name__ == "__main__":
    main()
