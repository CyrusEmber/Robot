# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Capture actual Blender palm pivots and bound meshes without changing the source [m, rad]."""

import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runrecord"))
import binding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe_report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    probe = json.loads(options.probe_report.read_text(encoding="utf-8"))
    source = Path(probe["source"])
    assert binding.sha256_file(source) == probe["source_sha256"]
    output = options.output.resolve()
    assert Path(__file__).resolve().parents[2] / "out" in output.parents
    assert not output.exists()
    bpy.ops.wm.open_mainfile(filepath=str(source))
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    bpy.context.view_layer.update()
    pivots = {b.name: list(arm.matrix_world @ b.head_local) for b in arm.data.bones}
    frames = {b.name: arm.matrix_world @ b.matrix for b in arm.pose.bones}
    assert all(b.matrix_basis == Matrix.Identity(4) for b in arm.pose.bones)
    exporter = Path(__file__).resolve().parents[2] / "blender/scripts/generate_urdf.py"
    namespace = {"__file__": str(exporter), "__name__": "__main__"}
    saved = sys.argv
    try:
        sys.argv = [str(exporter), "--", "--robot", "lizard2_palm_contract", "--contract_check", "--memory_scene"]
        try:
            exec(compile(exporter.read_text(encoding="utf-8"), str(exporter), "exec"), namespace)
        except SystemExit as exc:
            assert exc.code == 0
    finally:
        sys.argv = saved
    balls = namespace["BALL_MESHES"]
    snapshots = []
    for angle in (0., .03):
        for name, axis in probe["candidate_axes_world"].items():
            bone = arm.pose.bones[name]
            bone.rotation_mode = "QUATERNION"
            bone.rotation_quaternion = Quaternion(frames[name].to_3x3().inverted() @ Vector(axis), angle)
        bpy.context.view_layer.update()
        meshes = []
        for obj in bpy.context.scene.objects:
            if obj.type != "MESH":
                continue
            assert obj.parent == arm and obj.parent_type == "BONE" and obj.parent_bone in pivots
            evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh = evaluated.to_mesh()
            try:
                points = [list(evaluated.matrix_world @ v.co) for v in mesh.vertices]
                faces = [list(face.vertices) for face in mesh.polygons]
                raw = obj.to_mesh()
                try:
                    collision_points = [list(obj.matrix_world @ v.co) for v in raw.vertices]
                finally:
                    obj.to_mesh_clear()
                meshes.append({"object": obj.name, "link": obj.parent_bone,
                               "collision": obj.name not in balls, "points_world_m": points,
                               "collision_points_world_m": collision_points, "faces": faces})
            finally:
                evaluated.to_mesh_clear()
        snapshots.append({"q_rad": angle,
                          "pivots_world_m": {b.name: list(arm.matrix_world @ b.head) for b in arm.pose.bones},
                          "meshes": meshes})
    assert binding.sha256_file(source) == probe["source_sha256"]
    report = {"source": str(source), "source_sha256": probe["source_sha256"],
              "script_sha256": binding.sha256_file(Path(__file__)),
              "exporter_sha256": binding.sha256_file(exporter),
              "parents": {b.name: b.parent.name if b.parent else None for b in arm.data.bones},
              "rest_pivots_world_m": pivots, "snapshots": snapshots,
              "blender_version": bpy.app.version_string, "source_unchanged": True, "completed": True}
    with output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1)
    print("BLENDER_PALM_SNAPSHOT_COMPLETE", output, flush=True)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback

        traceback.print_exc()
        raise SystemExit(1)
