# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Create a two-axis Blender candidate without modifying the v6 source."""
import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from rl_exp.tools.runrecord.binding import sha256_file  # noqa: E402
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
source = args.source.resolve()
out = args.out.resolve()
if not out.is_relative_to((ROOT / 'rl_exp/out').resolve()) or out.exists():
    raise ValueError('output must be a new file under rl_exp/out')
source_hash = sha256_file(source)
if source_hash != 'beeac4c09726260bf392a6ecc81a04ebcf9b54a210416493bbb2689c4909cdea':
    raise ValueError('source Blender identity is not the v6 spatial checkpoint')
bpy.ops.wm.open_mainfile(filepath=str(source))
arm = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
if any(b.matrix_basis != Matrix.Identity(4) for b in arm.pose.bones):
    raise ValueError('source has non-neutral bone transforms')

def sample():
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    result = {}
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        try:
            ids = sorted({i * (len(mesh.vertices) - 1) // 31 for i in range(32)})
            result[obj.name] = [evaluated.matrix_world @ mesh.vertices[i].co for i in ids]
        finally:
            evaluated.to_mesh_clear()
    return result

before = sample()
bpy.context.view_layer.objects.active = arm
arm.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
for leg, tip in [('lf', 'wrist'), ('rf', 'wrist'), ('rl', 'ankle'), ('rr', 'ankle')]:
    old = arm.data.edit_bones[leg + '_' + tip]
    carrier = arm.data.edit_bones.new(old.name + '_lateral_carrier')
    carrier.head, carrier.tail, carrier.roll = old.head.copy(), old.tail.copy(), old.roll
    carrier.parent = old.parent
    carrier.use_connect = False
    old.use_connect = False
    old.parent = carrier
bpy.ops.object.mode_set(mode='OBJECT')
after = sample()
if before.keys() != after.keys():
    raise ValueError('mesh inventory changed')
error = max((a-b).length for name in before for a, b in zip(before[name], after[name]))
if error > 1e-5:
    raise ValueError('neutral mesh position changed: ' + str(error))
bpy.ops.wm.save_as_mainfile(filepath=str(out))
report = {'source': str(source), 'source_sha256': source_hash, 'candidate': str(out),
          'candidate_sha256': sha256_file(out),
          'max_sampled_neutral_vertex_error_m': error,
          'scope': 'visual/armature candidate; URDF axes and dynamics require separate verification'}
out.with_suffix('.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('TWO_AXIS_BLEND_OK', json.dumps(report), flush=True)
