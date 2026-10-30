# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Generate an isolated two-axis ankle kinematic candidate, not a training asset."""

import argparse
import copy
import json
import math
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from rl_exp.tools.runrecord.binding import sha256_file as digest  # noqa: E402

SOURCE = ROOT / 'rl_exp/lizard2_palm_spatial/lizard2_palm_spatial.urdf'


def generate(out):
    out = out.resolve()
    if not out.is_relative_to((ROOT / 'rl_exp/out').resolve()) or out.exists():
        raise ValueError('output must be a fresh directory under rl_exp/out')
    tree = ET.parse(SOURCE)
    root = tree.getroot()
    evidence = {}
    for leg, tip in [('lf', 'wrist'), ('rf', 'wrist'), ('rl', 'ankle'), ('rr', 'ankle')]:
        name = f'{leg}_{tip}'
        link = root.find(f"./link[@name='{name}']")
        joint = root.find(f"./joint[@name='{name}_joint']")
        xyz = [float(v) for v in joint.find('axis').get('xyz').split()]
        if abs(xyz[2]) > 1e-9:
            raise ValueError('expected a horizontal original axis')
        new_axis = [-xyz[1], xyz[0], 0.0]
        carrier = ET.Element('link', {'name': name + '_lateral_carrier'})
        inertia = link.find('inertial')
        carrier_inertia = copy.deepcopy(inertia)
        # Identical COM + proportional inertia preserve original zero-pose spatial inertia.
        for node, keys in [('mass', ['value']), ('inertia', ['ixx', 'ixy', 'ixz', 'iyy', 'iyz', 'izz'])]:
            a, b = inertia.find(node), carrier_inertia.find(node)
            for key in keys:
                value = float(a.get(key))
                a.set(key, format(value * 0.9, '.12g'))
                b.set(key, format(value * 0.1, '.12g'))
        carrier.append(carrier_inertia)
        root.insert(list(root).index(link), carrier)
        new_joint = copy.deepcopy(joint)
        new_joint.set('name', name + '_lateral_joint')
        new_joint.find('child').set('link', carrier.get('name'))
        new_joint.find('axis').set('xyz', ' '.join(format(v, '.12g') for v in new_axis))
        limit = new_joint.find('limit')
        limit.set('lower', str(-math.pi / 6)); limit.set('upper', str(math.pi / 6))
        joint.find('parent').set('link', carrier.get('name'))
        joint.find('origin').set('xyz', '0 0 0')
        root.insert(list(root).index(joint), new_joint)
        evidence[leg] = {'original_axis': xyz, 'new_axis': new_axis,
                         'bounds_rad': [-math.pi / 6, math.pi / 6]}
    out.mkdir(parents=True)
    shutil.copytree(SOURCE.parent / 'meshes', out / 'meshes')
    target = out / 'lizard2_two_axis.urdf'
    tree.write(target, encoding='utf-8', xml_declaration=True)
    report = {'source': str(SOURCE), 'source_sha256': digest(SOURCE), 'candidate': str(target),
              'candidate_sha256': digest(target), 'axes': evidence,
              'status': 'kinematic candidate; provisional limits and inertia, not trained or adopted',
              'inertia': 'foot inertia split 90/10 at the same COM solely to preserve zero-pose mass properties'}
    (out / 'candidate.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    generate(parser.parse_args().out)
