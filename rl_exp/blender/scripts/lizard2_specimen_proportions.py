# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Build the isolated, single-specimen hindlimb candidate in Blender [m].

Run with Blender --background --python-exit-code 1 --python this_file --
--output_dir PATH. Existing outputs require --check_only. Ratios are from
acceptance/records/2026-10-13-lizard2-specimen-hindlimb.md; this is not adoption.
Use --restore_source_lengths to retain the original limb lengths and palms
while solving the same four-sole ground constraint.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree


SOURCE = Path(__file__).resolve().parents[1] / (
    "lizard2_palm_p2_sample_claw_all_lowered_body75_vertical_tail_ground/sample_neutral.blend"
)
SOURCE_SHA256 = "c6566679f514581dd972e40dfbbb9d6f115a43e975f861ab4c57a53e3496ca47"
FORE_TOTAL_CM = 28.7
HIND_TOTAL_CM = 37.9
PES_CM = 12.7
GROUND_M = -0.9711321443319321
LEGS = ("lf", "rf", "rl", "rr")


def vertices(obj):
    """Return evaluated world vertices [m]."""
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    result = [evaluated.matrix_world @ v.co for v in mesh.vertices]
    evaluated.to_mesh_clear()
    return result


def center(points):
    return sum(points, Vector()) / len(points)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--check_only", action="store_true")
    parser.add_argument("--restore_source_lengths", action="store_true")
    parser.add_argument("--regression_without_fix", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    output = args.output_dir.resolve()
    if output.exists() and not args.check_only:
        raise ValueError("Output exists; use --check_only or a new directory")
    assert output != SOURCE.parent.resolve()
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    assert digest == SOURCE_SHA256, "Unexpected source; review its geometry before rebuilding"
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    mw = arm.matrix_world.copy()
    inv = mw.inverted()
    objects = {o.name: o for o in bpy.context.scene.objects if o.type == "MESH"}
    old_vertices = {n: vertices(o) for n, o in objects.items()}
    bindings = {n: (o.parent.name if o.parent else None, o.parent_type, o.parent_bone)
                for n, o in objects.items()}
    old_bones = {b.name: (mw @ b.head, mw @ b.tail) for b in arm.pose.bones}
    bases = {b.name: b.matrix_basis.copy() for b in arm.pose.bones}
    samples = {}
    for leg in LEGS:
        roles = ("shoulder_swing", "shoulder_abduct", "elbow", "wrist") if leg.endswith("f") else (
            "hip_swing", "hip_abduct", "knee", "ankle")
        names = [leg + "_" + role for role in roles]
        assert all(bases[n] == Matrix.Identity(4) for n in names), "Source leg pose must be identity"
        attached = [[n for n in objects if bindings[n][2] == name] for name in names]
        palm = next(n for n in attached[3] if len(objects[n].data.vertices) == 72)
        cylinders = [next(n for n in attached[i]
                          if sum(len(f.vertices) > 4 for f in objects[n].data.polygons) == 2)
                     for i in (1, 2)]
        points = [old_bones[n][0] for n in names[1:]]
        lengths = [(points[i + 1] - points[i]).length for i in range(2)]
        palm_length = max(p.x - points[2].x for p in old_vertices[palm])
        caps = [sorted([list(f.vertices) for f in objects[n].data.polygons if len(f.vertices) > 4],
                       key=lambda ids, i=i, n=n: center([old_vertices[n][j] for j in ids]).dot(
                           points[i + 1] - points[i])) for i, n in enumerate(cylinders)]
        samples[leg] = dict(names=names, attached=attached, palm=palm, cylinders=cylinders,
                            old_points=points, lengths=lengths, palm_length=palm_length, caps=caps)
    front_total = sum(samples["lf"]["lengths"]) + samples["lf"]["palm_length"]
    rear_proximal = front_total * (HIND_TOTAL_CM - PES_CM) / FORE_TOTAL_CM
    rear_palm = front_total * PES_CM / FORE_TOTAL_CM
    transforms = {n: Matrix.Identity(4) for n in objects}
    targets = {}
    for leg, s in samples.items():
        names, old = s["names"], s["old_points"]
        scale_hind = leg in ("rl", "rr") and not args.restore_source_lengths
        factor = rear_proximal / sum(s["lengths"]) if scale_hind else 1.0
        palm_factor = rear_palm / s["palm_length"] if scale_hind else 1.0
        lengths = [x * factor for x in s["lengths"]]
        ankle_z = GROUND_M - min(p.z - old[2].z for p in old_vertices[s["palm"]])
        dz = ankle_z + lengths[1] - old[0].z
        assert abs(dz) < lengths[0], "No vertical-lower solution at preserved body height"
        yaw = old[1] - old[0]
        yaw.z = 0
        yaw.normalize()
        p = [old[0].copy(), old[0] + yaw * math.sqrt(lengths[0] ** 2 - dz ** 2) + Vector((0, 0, dz))]
        p.append(p[1] - Vector((0, 0, lengths[1])))
        s.update(points=p, target_lengths=lengths, target_palm=s["palm_length"] * palm_factor,
                 axis=(p[1] - p[0]).cross(Vector((0, 0, -1))).normalized())
        if leg in ("rf", "rr"):
            s["axis"] = -(Matrix.Diagonal((1, -1, 1)) @ samples["lf" if leg == "rf" else "rl"]["axis"])
        targets[names[0]] = old_bones[names[0]]
        for i in (1, 2):
            targets[names[i]] = (p[i - 1], p[i])
            d = (old[i] - old[i - 1]).normalized()
            rotation = (old[i] - old[i - 1]).rotation_difference(p[i] - p[i - 1]).to_matrix()
            stretch = Matrix.Identity(3)
            for row in range(3):
                for col in range(3):
                    stretch[row][col] += (factor - 1) * d[row] * d[col]
            for n in s["attached"][i]:
                linear = rotation @ stretch if n == s["cylinders"][i - 1] else rotation
                transforms[n] = Matrix.Translation(p[i - 1]) @ linear.to_4x4() @ Matrix.Translation(-old[i - 1])
        targets[names[3]] = (p[2], p[2] + (old_bones[names[3]][1] - old[2]) * palm_factor)
        for n in s["attached"][3]:
            stretch = Matrix.Diagonal((palm_factor, 1, 1, 1)) if n == s["palm"] else Matrix.Identity(4)
            transforms[n] = Matrix.Translation(p[2]) @ stretch @ Matrix.Translation(-old[2])
    expected = {n: [transforms[n] @ v for v in ps] for n, ps in old_vertices.items()}
    # This is a float32 construction tolerance, not a user-approved anatomy tolerance.
    epsilon = 64 * 2 ** -23 * max(1, *(abs(x) for ps in expected.values() for p in ps for x in p))

    def check():
        bpy.context.view_layer.update()
        actual = {n: vertices(o) for n, o in objects.items()}
        measured = {}
        for leg, s in samples.items():
            bs = [arm.pose.bones[n] for n in s["names"][1:]]
            lengths = [(mw.to_3x3() @ (b.tail - b.head)).length for b in bs[:2]]
            root = mw @ bs[2].head
            palm_length = max(v.x - root.x for v in actual[s["palm"]])
            measured[leg] = dict(upper_m=lengths[0], lower_m=lengths[1], palm_m=palm_length,
                                 total_m=sum(lengths) + palm_length,
                                 sole_z_m=min(v.z for v in actual[s["palm"]]))
        if args.restore_source_lengths:
            for leg, s in samples.items():
                for key, expected_length in zip(("upper_m", "lower_m", "palm_m"),
                                                [*s["lengths"], s["palm_length"]]):
                    assert abs(measured[leg][key] - expected_length) < epsilon, "source length not restored: " + leg + ":" + key
        else:
            for leg in ("rl", "rr"):
                assert abs(measured[leg]["total_m"] - front_total * HIND_TOTAL_CM / FORE_TOTAL_CM) < epsilon, "hind total ratio"
                assert abs(measured[leg]["palm_m"] - rear_palm) < epsilon, "hind palm ratio"
        for leg, s in samples.items():
            assert abs(measured[leg]["sole_z_m"] - GROUND_M) < epsilon, "four soles not coplanar: " + leg
            bs = [arm.pose.bones[n] for n in s["names"][1:]]
            delta = mw.to_3x3() @ (bs[1].tail - bs[1].head)
            assert math.hypot(delta.x, delta.y) < epsilon and delta.z < 0, "lower not vertical"
            upper = mw.to_3x3() @ (bs[0].tail - bs[0].head)
            assert upper.x * (-1 if leg.endswith("f") else 1) > 0, "upper direction"
            for i, n in enumerate(s["cylinders"]):
                caps = [center([actual[n][j] for j in group]) for group in s["caps"][i]]
                assert max((caps[0] - mw @ bs[i].head).length,
                           (caps[1] - mw @ bs[i].tail).length) < epsilon, "mesh cap disconnected: " + n
            assert (center(actual[s["palm"]][:12]) - mw @ bs[2].head).length < epsilon, "palm root disconnected"
            for n in s["names"]:
                assert (mw @ arm.pose.bones[n].head - targets[n][0]).length < epsilon, "bone head mismatch"
                assert (mw @ arm.pose.bones[n].tail - targets[n][1]).length < epsilon, "bone tail mismatch"
        for n in old_bones:
            if n not in targets:
                assert arm.pose.bones[n].matrix_basis == bases[n], "nonleg pose changed"
                assert (mw @ arm.pose.bones[n].head - old_bones[n][0]).length < epsilon
                assert (mw @ arm.pose.bones[n].tail - old_bones[n][1]).length < epsilon
        for n in objects:
            assert len(actual[n]) == len(expected[n]), "mesh vertex count changed: " + n
            assert max((a - b).length for a, b in zip(actual[n], expected[n])) < epsilon, "mesh transform mismatch: " + n
            o = objects[n]
            assert (o.parent.name if o.parent else None, o.parent_type, o.parent_bone) == bindings[n]
        for left, right in (("lf", "rf"), ("rl", "rr")):
            for ln, rn in zip(samples[left]["names"], samples[right]["names"]):
                for attr in ("head", "tail"):
                    a = mw @ getattr(arm.pose.bones[ln], attr)
                    b = mw @ getattr(arm.pose.bones[rn], attr)
                    assert (Vector((a.x, -a.y, a.z)) - b).length < epsilon, "bone mirror"
            for lg, rg in zip(samples[left]["attached"], samples[right]["attached"]):
                for ln, rn in zip(lg, rg):
                    # Source object list order is not a role contract: match by mesh size.
                    rn = next(n for n in rg if len(actual[n]) == len(actual[ln]))
                    for p in actual[ln]:
                        reflected = Vector((p.x, -p.y, p.z))
                        assert min((reflected - q).length for q in actual[rn]) < epsilon, "mesh mirror"
        return measured

    if args.regression_without_fix:
        check()  # The source lacks either the requested scaling or coplanar soles.
        raise AssertionError("Unmodified source was incorrectly accepted")
    if args.check_only:
        bpy.ops.wm.open_mainfile(filepath=str(output / "sample_neutral.blend"))
        arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
        objects = {n: bpy.data.objects[n] for n in old_vertices}
    else:
        for n, o in objects.items():
            if bindings[n][2] in targets:
                o.parent = None
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode="EDIT")
        for n, (h, t) in targets.items():
            b = arm.data.edit_bones[n]
            b.use_connect = False
            b.head, b.tail = inv @ h, inv @ t
        for s in samples.values():
            for n in s["names"][1:]:
                b = arm.data.edit_bones[n]
                b.align_roll((inv.to_3x3() @ s["axis"]).cross((b.tail - b.head).normalized()))
        bpy.ops.object.mode_set(mode="OBJECT")
        for n, o in objects.items():
            if bindings[n][2] not in targets:
                continue
            parent, kind, bone = bindings[n]
            o.parent, o.parent_type, o.parent_bone = bpy.data.objects[parent], kind, bone
            o.matrix_parent_inverse = Matrix.Identity(4)
            bpy.context.view_layer.update()
            # Bake axial scaling into the mesh. An object TRS decomposition cannot
            # represent arbitrary shear from world-axis scaling of a rotated mesh.
            assert not o.modifiers, "Bake requires the known source's unmodified meshes"
            o.data = o.data.copy()
            o.matrix_world = Matrix.Identity(4)
            bpy.context.view_layer.update()
            local = o.matrix_world.inverted()
            for vertex, point in zip(o.data.vertices, expected[n]):
                vertex.co = local @ point
            o.data.update()
        check()
        output.mkdir(parents=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(output / "sample_neutral.blend"))
        bpy.ops.wm.open_mainfile(filepath=str(output / "sample_neutral.blend"))
        arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
        objects = {n: bpy.data.objects[n] for n in old_vertices}
    report = dict(source=str(SOURCE), source_sha256=digest, ground_m=GROUND_M,
                  geometry_mode="source_lengths" if args.restore_source_lengths else "specimen_ratios",
                  tolerance_m=epsilon, measured=check(), negatives={}, diagnostics=[])
    # Real geometry mutation, restored before diagnostics or preview rendering.
    palm = objects[samples["lf"]["palm"]]
    saved = palm.matrix_world.copy()
    palm.matrix_world = Matrix.Translation((0, 0, .01)) @ saved
    try:
        check()
    except AssertionError as exc:
        assert str(exc).startswith("four soles not coplanar"), str(exc)
        report["negatives"]["raised_palm"] = str(exc)
    else:
        raise AssertionError("Raised palm not rejected")
    finally:
        palm.matrix_world = saved
    check()

    def overlap(a, b):
        trees = []
        for n in (a, b):
            o = objects[n]
            trees.append(BVHTree.FromPolygons(vertices(o), [list(f.vertices) for f in o.data.polygons]))
        return len(trees[0].overlap(trees[1]))

    for leg, s in samples.items():
        report["measured"][leg]["neutral_lower_palm_surface_pairs"] = overlap(s["cylinders"][1], s["palm"])
        for name in s["names"][2:]:
            bone = arm.pose.bones[name]
            old_mode, old_quat = bone.rotation_mode, bone.rotation_quaternion.copy()
            pivot = mw @ bone.head
            axis = s["axis"]
            local_axis = arm.data.bones[name].matrix_local.to_3x3().inverted() @ (inv.to_3x3() @ axis)
            children = {name} | {b.name for b in arm.data.bones[name].children_recursive}
            for angle in (-10, 10):
                bone.rotation_mode = "QUATERNION"
                bone.rotation_quaternion = Quaternion(local_axis, math.radians(angle))
                bpy.context.view_layer.update()
                rotation = Matrix.Translation(pivot) @ Matrix.Rotation(math.radians(angle), 4, axis) @ Matrix.Translation(-pivot)
                residual = max((p - rotation @ q).length
                               for n in objects if bindings[n][2] in children
                               for p, q in zip(vertices(objects[n]), expected[n]))
                assert residual < epsilon, "joint mesh motion disconnected"
                report["diagnostics"].append(dict(joint=name, angle_deg=angle, residual_m=residual,
                    lower_palm_surface_pairs=overlap(s["cylinders"][1], s["palm"])))
            bone.rotation_quaternion, bone.rotation_mode = old_quat, old_mode
            bpy.context.view_layer.update()
    check()
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == digest
    report["saved_sha256"] = hashlib.sha256((output / "sample_neutral.blend").read_bytes()).hexdigest()
    if args.check_only:
        print("SPECIMEN CHECK PASS", json.dumps(report))
        return
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x, scene.render.resolution_y = 1400, 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = True
    scene.display.shading.background_type = "WORLD"
    scene.world.color = (.035, .035, .035)
    camera = bpy.data.objects.new("SPECIMEN_CAMERA", bpy.data.cameras.new("SPECIMEN_CAMERA"))
    scene.collection.objects.link(camera)
    camera.data.type, camera.data.ortho_scale = "ORTHO", 5.2
    scene.camera = camera
    target = Vector((-1.55, 0, -.45))
    for name, direction in (("full_side", (0, -1, 0)), ("full_front", (1, 0, 0)),
                            ("full_top", (0, 0, 1)), ("full_oblique", (1.3, -2, 1))):
        camera.location = target + Vector(direction).normalized() * 8
        camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(output / (name + ".png"))
        bpy.ops.render.render(write_still=True)
    (output / "measurements.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("SPECIMEN BUILD PASS", output)


if __name__ == "__main__":
    main()
