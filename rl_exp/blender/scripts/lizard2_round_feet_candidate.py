# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Replace eight terminal bones by four rigid spheres in an isolated Blender file.

Run with Blender. Radius [m] is a preview input, not an adopted physical design.
No URDF/USD export, physics, mass assignment or training configuration changes.
"""
import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from rl_exp.tools.runrecord.binding import sha256_file

FEET = {'lf_wrist': 'lf_elbow', 'rf_wrist': 'rf_elbow',
        'rl_ankle': 'rl_knee', 'rr_ankle': 'rr_knee'}
REMOVED = set(FEET) | {name + '_lateral_carrier' for name in FEET}
SOURCE_SHA256 = '4b204706e871220aaec4a6a404e96f99c18a2c6c984771c1c186d2b7ecea6f42'
TOL = 1e-5


def vertices(obj):
    """Read all evaluated world vertices [m]."""
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        return [evaluated.matrix_world @ v.co for v in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def snapshot(arm):
    """Capture upstream topology, frames and evaluated world geometry [m]."""
    bpy.context.view_layer.update()
    return {
        'bones': {b.name: (b.parent.name if b.parent else None, b.matrix_local.copy())
                  for b in arm.data.bones if b.name not in REMOVED},
        'meshes': {o.name: (o.parent_bone, vertices(o))
                   for o in bpy.context.scene.objects if o.type == 'MESH'
                   and o.parent_bone not in REMOVED},
    }


def check(arm, before, centers, radius):
    """Verify removed axes, rigid spheres and unchanged upstream geometry [m]."""
    bpy.context.view_layer.update()
    assert {b.name for b in arm.data.bones} == set(before['bones'])
    assert len(arm.data.bones) == 27 and 'base_link' in arm.data.bones
    assert all(b.matrix_basis == Matrix.Identity(4) for b in arm.pose.bones)
    current = snapshot(arm)
    for name, (parent, matrix) in before['bones'].items():
        actual_parent, actual_matrix = current['bones'][name]
        assert parent == actual_parent, name
        assert max(abs(actual_matrix[i][j] - matrix[i][j])
                   for i in range(4) for j in range(4)) < TOL, name
    spheres = {'round_' + foot for foot in FEET}
    assert set(current['meshes']) == set(before['meshes']) | spheres
    maximum = 0.
    for name, (parent, points) in before['meshes'].items():
        actual_parent, actual = current['meshes'][name]
        assert parent == actual_parent and len(points) == len(actual), name
        maximum = max(maximum, max((a - b).length for a, b in zip(points, actual)))
    assert maximum < TOL, maximum
    for foot, parent in FEET.items():
        obj = bpy.data.objects['round_' + foot]
        assert obj.parent == arm and obj.parent_type == 'BONE' and obj.parent_bone == parent
        assert not obj.modifiers and not obj.constraints and not obj.vertex_groups
        assert (obj.matrix_world.translation - centers[foot]).length < TOL
        assert max(abs((v - centers[foot]).length - radius) for v in vertices(obj)) < TOL
    assert all(o.parent_bone not in REMOVED for o in bpy.context.scene.objects)
    return maximum


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--radius', type=float, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, out = args.source.resolve(), args.out.resolve()
    if sha256_file(source) != SOURCE_SHA256:
        raise ValueError('expected the bound 34-axis Blender candidate')
    if not 0. < args.radius < float('inf'):
        raise ValueError('radius must be positive and finite [m]')
    if not out.is_relative_to((ROOT / 'rl_exp/out').resolve()) or out.exists():
        raise ValueError('output must be a new directory under rl_exp/out')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    arm, = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
    assert len(arm.data.bones) == 35
    assert all(b.matrix_basis == Matrix.Identity(4) for b in arm.pose.bones)
    for foot, parent in FEET.items():
        assert arm.data.bones[foot].parent.name == foot + '_lateral_carrier'
        assert arm.data.bones[foot + '_lateral_carrier'].parent.name == parent
        assert not arm.data.bones[foot].children
    before = snapshot(arm)
    centers = {name: arm.matrix_world @ arm.data.bones[name].head_local for name in FEET}
    old_meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.parent_bone in REMOVED]
    assert len(old_meshes) == 8
    removed_objects = [o.name for o in old_meshes]
    for obj in old_meshes:
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    for name in sorted(REMOVED):
        arm.data.edit_bones.remove(arm.data.edit_bones[name])
    bpy.ops.object.mode_set(mode='OBJECT')
    for foot, parent in FEET.items():
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=args.radius,
                                           location=centers[foot])
        obj = bpy.context.object
        obj.name = 'round_' + foot
        world = obj.matrix_world.copy()
        obj.parent, obj.parent_type, obj.parent_bone = arm, 'BONE', parent
        bpy.context.view_layer.update()
        obj.matrix_world = world
        obj.color = (.95, .35, .08, 1.)
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
    neutral_error = check(arm, before, centers, args.radius)
    rejected = []
    for foot in FEET:
        obj = bpy.data.objects['round_' + foot]
        parent = obj.parent_bone
        obj.parent_bone = 'base_link'
        try:
            check(arm, before, centers, args.radius)
        except AssertionError:
            rejected.append(foot)
        finally:
            obj.parent_bone = parent
        assert foot in rejected, 'check failed to reject disconnected foot'
    check(arm, before, centers, args.radius)
    out.mkdir(parents=True)
    target = out / 'lizard2_round_feet.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(target))
    bpy.ops.wm.open_mainfile(filepath=str(target))
    arm, = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
    reopened_error = check(arm, before, centers, args.radius)
    movement_errors = {}
    for foot, parent in FEET.items():
        obj, bone = bpy.data.objects['round_' + foot], arm.pose.bones[parent]
        inverse = (arm.matrix_world @ bone.matrix).inverted()
        local = [inverse @ p for p in vertices(obj)]
        mode = bone.rotation_mode
        bone.rotation_mode = 'XYZ'
        for angle in (-.1, .1):
            bone.rotation_euler.x = angle
            bpy.context.view_layer.update()
            transform = arm.matrix_world @ bone.matrix
            actual = vertices(obj)
            error = max((p - transform @ q).length for p, q in zip(actual, local))
            assert error < TOL
            movement_errors[foot + ':' + str(angle)] = error
        bone.rotation_euler.x = 0.
        bone.rotation_mode = mode
    check(arm, before, centers, args.radius)
    assert sha256_file(source) == SOURCE_SHA256
    report = dict(source=str(source), source_sha256=SOURCE_SHA256,
                  candidate=str(target), candidate_sha256=sha256_file(target),
                  script_sha256=sha256_file(__file__), blender_version=bpy.app.version_string,
                  source_active_axes=34, removed_axes=8, remaining_active_axes=26,
                  root_bones=1, removed_bones=sorted(REMOVED), removed_mesh_objects=removed_objects,
                  sphere_radius_m=args.radius, sphere_parents=FEET,
                  sphere_centers_world_m={k: list(v) for k, v in centers.items()},
                  max_neutral_vertex_error_m=neutral_error, max_reopened_vertex_error_m=reopened_error,
                  rigid_motion_errors_m=movement_errors, wrong_parent_rejections=rejected,
                  scope='Blender skeleton/visual candidate only; no terminal movable bones; '
                        'radius is provisional; mass, URDF/USD and dynamics not validated')
    with (out / 'build.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print('ROUND_FEET_BLEND_OK', json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
