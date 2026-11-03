# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Create fixed spherical feet from the formal palm URDF in a fresh isolated folder.

Retain the four terminal body names for contact sampling, but replace their geometry,
COM and inertia; replace wrist/ankle revolute joints by named fixed mounts. The
remaining tree and total mass stay unchanged. Radius is a candidate design input,
not an optimized value or a hardware specification. No training recipe is changed.
"""

from __future__ import annotations

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
from rl_exp.tools.runrecord.binding import sha256_file  # noqa: E402

SOURCE = ROOT / 'rl_exp/lizard2_palm_spatial/lizard2_palm_spatial.urdf'
FEET = ('lf_wrist', 'rf_wrist', 'rl_ankle', 'rr_ankle')
REMOVED = tuple(f'{foot}_joint' for foot in FEET)


ELBOWS = ('lf_elbow_joint', 'rf_elbow_joint')


def _elbow_overrides(source: ET.ElementTree, elbow_limit: float | None) -> dict:
    """Return only allowed symmetric elbow limits [rad], never expanding source."""
    if elbow_limit is None:
        return {}
    if not math.isfinite(elbow_limit) or elbow_limit <= 0:
        raise ValueError('elbow_limit must be positive and finite')
    overrides = {}
    for name in ELBOWS:
        limit = source.getroot().find(f"joint[@name='{name}']/limit")
        lower, upper = (float(limit.get(k)) for k in ('lower', 'upper'))
        if not (math.isfinite(lower) and math.isfinite(upper)
                and lower <= -elbow_limit and elbow_limit <= upper):
            raise ValueError('elbow_limit must not expand source limits: ' + name)
        overrides[name] = {'lower': f'{-elbow_limit:.17g}', 'upper': f'{elbow_limit:.17g}'}
    return overrides


def build_tree(source: Path, radius: float, elbow_limit: float | None = None) -> ET.ElementTree:
    """Replace feet by spheres [m]; optionally narrow both elbows symmetrically [rad]."""
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError('radius must be positive and finite')
    tree = ET.parse(source)
    root = tree.getroot()
    for name in FEET:
        link = root.find(f"link[@name='{name}']")
        joint = root.find(f"joint[@name='{name}_joint']")
        if link is None or joint is None or joint.get('type') != 'revolute':
            raise ValueError(f'expected formal single-axis terminal foot: {name}')
        if any(j.find('parent').get('link') == name for j in root.findall('joint')):
            raise ValueError(f'foot must be a leaf: {name}')
        mass = float(link.find('inertial/mass').get('value'))
        link.clear()
        link.set('name', name)
        inertia = ET.SubElement(link, 'inertial')
        ET.SubElement(inertia, 'origin', xyz='0 0 0', rpy='0 0 0')
        ET.SubElement(inertia, 'mass', value=f'{mass:.12g}')
        moment = f'{0.4 * mass * radius ** 2:.12g}'
        ET.SubElement(inertia, 'inertia', ixx=moment, iyy=moment, izz=moment,
                      ixy='0', ixz='0', iyz='0')
        for kind in ('visual', 'collision'):
            shape = ET.SubElement(link, kind)
            ET.SubElement(shape, 'origin', xyz='0 0 0', rpy='0 0 0')
            ET.SubElement(ET.SubElement(shape, 'geometry'), 'sphere', radius=f'{radius:.12g}')
            if kind == 'visual':
                material = ET.SubElement(shape, 'material', name='round_foot_rubber')
                ET.SubElement(material, 'color', rgba='0.09 0.12 0.15 1')
        joint.set('type', 'fixed')
        joint.set('name', f'{name}_fixed')
        for tag in ('axis', 'limit', 'dynamics'):
            node = joint.find(tag)
            if node is not None:
                joint.remove(node)
    for name, limits in _elbow_overrides(ET.parse(source), elbow_limit).items():
        root.find(f"joint[@name='{name}']/limit").attrib.update(limits)
    validate_tree(ET.parse(source), tree, radius, elbow_limit=elbow_limit)
    return tree


def validate_tree(source: ET.ElementTree, candidate: ET.ElementTree, radius: float,
                  elbow_limit: float | None = None) -> None:
    """Check unchanged upstream bytes except explicitly requested elbow limits [rad]."""
    overrides = _elbow_overrides(source, elbow_limit)
    old, new = source.getroot(), candidate.getroot()
    old_joints = {j.get('name'): j for j in old.findall('joint')}
    new_joints = {j.get('name'): j for j in new.findall('joint')}
    assert set(new_joints) == (set(old_joints) - set(REMOVED)) | {f'{n}_fixed' for n in FEET}
    for name, joint in old_joints.items():
        if name not in REMOVED:
            expected = joint
            if name in overrides:
                expected = copy.deepcopy(joint)
                expected.find('limit').attrib.update(overrides[name])
            assert ET.tostring(expected) == ET.tostring(new_joints[name]), name
    for old_link in old.findall('link'):
        name = old_link.get('name')
        link = new.find(f"link[@name='{name}']")
        assert link is not None, name
        if name not in FEET:
            assert ET.tostring(old_link) == ET.tostring(link), name
            continue
        mount = new_joints[f'{name}_fixed']
        assert mount.get('type') == 'fixed' and mount.find('axis') is None
        original = old_joints[f'{name}_joint']
        for tag in ('parent', 'child', 'origin'):
            assert mount.find(tag).attrib == original.find(tag).attrib
        mass = float(link.find('inertial/mass').get('value'))
        assert mass == float(old_link.find('inertial/mass').get('value'))
        assert link.find('inertial/origin').get('xyz') == '0 0 0'
        for kind in ('visual', 'collision'):
            assert len(link.findall(kind)) == 1
            sphere = link.find(f'{kind}/geometry/sphere')
            assert sphere is not None and math.isclose(float(sphere.get('radius')), radius)
        matrix = link.find('inertial/inertia')
        for key in ('ixx', 'iyy', 'izz'):
            assert math.isclose(float(matrix.get(key)), 0.4 * mass * radius ** 2)
        assert all(float(matrix.get(key)) == 0 for key in ('ixy', 'ixz', 'iyz'))
    assert len(new.findall('link')) == len(old.findall('link'))
    assert sum(j.get('type') != 'fixed' for j in new_joints.values()) == 26


def preview(urdf: Path, target: Path, radius: float) -> dict:
    """Render zero-pose orthographic views and report foot sphere locations [m]."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle
    import numpy as np
    from scipy.spatial import ConvexHull
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from pose_target_solver import geometry, load_model

    model = load_model(urdf)
    q = {n: 0. for n, j in model['joints'].items() if j['axis'] is not None}
    clouds, centers = {}, {}
    for name, link in model['links'].items():
        transform = geometry.fk(model['joints'], name, q)
        if name in FEET:
            centers[name] = transform[:3, 3]
        elif link['collision'] is not None:
            points = geometry.read_obj(link['collision'])
            clouds[name] = points @ transform[:3, :3].T + transform[:3, 3]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), layout='constrained')
    for ax, (i, j), title in zip(axes, ((0, 2), (1, 2), (0, 1)),
                                  ('Side (x/z)', 'Front (y/z)', 'Top (x/y)')):
        for points in clouds.values():
            projected = points[:, [i, j]]
            if np.linalg.matrix_rank(projected - projected.mean(axis=0)) < 2:
                continue
            hull = ConvexHull(projected)
            polygon = projected[hull.vertices]
            ax.fill(polygon[:, 0], polygon[:, 1], color='#7b95a8', alpha=.45,
                    linewidth=.5, edgecolor='#40586d')
        for name, center in centers.items():
            ax.add_patch(Circle((center[i], center[j]), radius, color='#e88936', alpha=.85))
            ax.annotate(name[:2], (center[i], center[j]), fontsize=8, ha='center')
        ax.set_aspect('equal')
        ax.autoscale_view()
        ax.set_title(title)
        ax.grid(alpha=.2)
        ax.set_xlabel('m')
        ax.set_ylabel('m')
    fig.suptitle(f'Fixed round feet | radius {radius * 1000:.0f} mm | zero pose | collision silhouettes')
    fig.savefig(target, dpi=160)
    plt.close(fig)
    return {name: {'center_root_m': center.tolist(), 'bottom_root_z_m': float(center[2] - radius)}
            for name, center in centers.items()}


def generate(out: Path, radius: float) -> dict:
    """Write an isolated candidate and source bindings with sphere radius [m]."""
    out = out.resolve()
    if not out.is_relative_to((ROOT / 'rl_exp/out').resolve()) or out.exists():
        raise ValueError('output must be a fresh directory below rl_exp/out')
    tree = build_tree(SOURCE, radius)
    out.mkdir(parents=True)
    bindings = {str(SOURCE): sha256_file(SOURCE), str(Path(__file__).resolve()): sha256_file(__file__)}
    for mesh in tree.getroot().iter('mesh'):
        relative = Path(mesh.get('filename'))
        source = (SOURCE.parent / relative).resolve()
        if relative.is_absolute() or not source.is_relative_to(SOURCE.parent.resolve()):
            raise ValueError('expected local relative mesh')
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        bindings[str(source)] = sha256_file(source)
    target = out / 'lizard2_round_feet.urdf'
    tree.write(target, encoding='utf-8', xml_declaration=True)
    locations = preview(target, out / 'preview.png', radius)
    report = {
        'source': str(SOURCE), 'source_bindings_sha256': bindings,
        'urdf': str(target), 'urdf_sha256': sha256_file(target),
        'radius_m': radius, 'foot_body_names': list(FEET), 'removed_joints': list(REMOVED),
        'fixed_mounts': [f'{n}_fixed' for n in FEET], 'active_joint_count': 26,
        'mass_kg': sum(float(l.find('inertial/mass').get('value')) for l in tree.getroot().findall('link')),
        'mass_policy': 'retain each former foot mass, move COM to sphere center, I=2/5*m*r^2',
        'zero_pose': locations,
        'candidate_files_sha256': {str(p.relative_to(out)): sha256_file(p)
                                   for p in sorted(out.rglob('*')) if p.is_file()},
        'scope': 'isolated fixed-sphere candidate; no physics, training or adoption implied',
    }
    (out / 'candidate.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('urdf', 'radius_m', 'active_joint_count', 'mass_kg', 'zero_pose')}, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--radius', type=float, default=.08, help='sphere radius [m]')
    args = parser.parse_args()
    generate(args.out, args.radius)
