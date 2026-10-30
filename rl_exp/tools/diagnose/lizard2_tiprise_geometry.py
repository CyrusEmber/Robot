# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Sample 2 cm root rise with mesh-defined front-edge support; no simulation.

Root forward is +x; root orientation stays identity. Eleven nodes only, not a
continuous path certificate. Self-collision is OFF: internal overlaps not tested.
All visual/collision OBJ vertices are checked against a horizontal ground plane.
"""

import argparse
import copy
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rl_exp.tools.runrecord.binding import sha256_file
from pose_target_solver import geometry, load_model, solve

FEET = ('lf_wrist', 'rf_wrist', 'rl_ankle', 'rr_ankle')
POSITION_TOL = 1e-5
GROUND_TOL = 2e-5
FOOT_MARGIN = 0.02


def placed(model, link, q, points):
    """Transform link points into root frame [m] with shared FK."""
    pose = geometry.fk(model['joints'], link, q)
    return np.asarray(points) @ pose[:3, :3].T + pose[:3, 3]


def front_heel(points):
    """Return unique flat-sole front edge and rear midpoint in root frame [m].

    Reject nonhorizontal/point-like ambiguous edges rather than inventing one.
    Mesh export rounding tolerance is 3 micrometres.
    """
    points = np.unique(points, axis=0)
    sole = points[points[:, 2] <= points[:, 2].min() + 3e-6]
    front = sole[sole[:, 0] >= sole[:, 0].max() - 3e-6]
    rear = sole[sole[:, 0] <= sole[:, 0].min() + 3e-6]
    if len(front) < 2 or np.ptp(front[:, 1]) < 0.01 or np.ptp(front[:, 0]) > 3e-6:
        raise ValueError('ambiguous front edge: user geometry choice required')
    if np.ptp(sole[:, 0]) < 0.02:
        raise ValueError('ambiguous heel: user geometry choice required')
    return front, rear.mean(axis=0)


def meshes(urdf):
    """Read every declared visual/collision mesh; reject unsupported transforms."""
    result = []
    for link in ET.parse(urdf).getroot().findall('link'):
        for kind in ('visual', 'collision'):
            for index, item in enumerate(link.findall(kind)):
                origin = item.find('origin')
                if origin is not None and any(not np.allclose(
                        [float(x) for x in origin.get(key, '0 0 0').split()], 0., atol=1e-12)
                        for key in ('xyz', 'rpy')):
                    raise ValueError('unsupported mesh origin')
                mesh = item.find('geometry/mesh')
                if mesh is None or not np.allclose([float(x) for x in mesh.get('scale', '1 1 1').split()], 1.):
                    raise ValueError('unsupported geometry or mesh scale')
                path = (urdf.parent / mesh.get('filename')).resolve()
                if path.suffix.lower() != '.obj':
                    raise ValueError('only OBJ supported')
                vertices = geometry.read_obj(path)
                if vertices.ndim != 2 or vertices.shape[1] != 3 or not np.isfinite(vertices).all():
                    raise ValueError('invalid mesh vertices')
                result.append((link.get('name'), kind, index, path, vertices))
    return result


def run(urdf):
    """Return sampled geometry, full q [rad], positions/gaps [m], bindings."""
    urdf = Path(urdf).resolve()
    model = load_model(urdf)
    mesh_data = meshes(urdf)
    initial = {n: 0. for n, j in model['joints'].items() if j['axis'] is not None}
    # Positive pitch lifts the negative-x tail; explicitly held, not hidden contact.
    initial['tail1_pitch_joint'] = 0.3
    q = dict(initial)
    bounded = copy.deepcopy(model)
    foot_data, axes = {}, {}
    for foot in FEET:
        chain = [n for n in geometry.chain_up(model['joints'], foot) if n.startswith(foot[:2] + '_') and n in q]
        foot_joints = chain[-2:]
        for name in foot_joints:
            lo, hi = model['joints'][name]['limits']
            bounded['joints'][name]['limits'] = (lo + FOOT_MARGIN, hi - FOOT_MARGIN)
        pose = geometry.fk(model['joints'], foot, initial)
        vertices = geometry.read_obj(model['links'][foot]['collision'])
        edge, heel = front_heel(placed(model, foot, initial, vertices))
        front = edge.mean(axis=0)
        local = (np.array([front, heel]) - pose[:3, 3]) @ pose[:3, :3]
        shank = model['joints'][foot_joints[0]]['parent']
        foot_data[foot] = dict(front=front, heel=heel, local=local, edge=edge,
                               chain=chain, foot_joints=foot_joints, shank=shank)
        axes[foot] = {}
        for name in foot_joints:
            spec = model['joints'][name]
            parent = geometry.fk(model['joints'], spec['parent'], initial)
            axis = parent[:3, :3] @ (spec['axis'] / np.linalg.norm(spec['axis']))
            effects = {}
            for angle in (-0.01, 0.01):
                trial = dict(initial, **{name: angle})
                delta = placed(model, foot, trial, local) - np.array([front, heel])
                effects[str(angle)] = {'front_delta_m': delta[0].tolist(), 'heel_delta_m': delta[1].tolist(),
                                       'heel_minus_front_dz_m': float(delta[1, 2] - delta[0, 2])}
            axes[foot][name] = {'axis_root': axis.tolist(), 'effects': effects}
    root_height = -min(v['front'][2] for v in foot_data.values())
    samples = []
    for fraction in np.linspace(0., 1., 11):
        rise, angle = 0.02 * float(fraction), 0.15 * float(fraction)
        rotation = Rotation.from_rotvec([0., angle, 0.]).as_matrix()
        results = {}
        for foot, data in foot_data.items():
            front = data['front'] - np.array([0., 0., rise])
            heel = front + rotation @ (data['heel'] - data['front'])
            targets = [{'link': foot, 'point_local': data['local'][0], 'point_target': front,
                        'normal_local': [0., 0., 1.], 'normal_target': rotation[:, 2]},
                       {'link': foot, 'point_local': data['local'][1], 'point_target': heel}]
            fit = solve(bounded, q, data['chain'], targets, POSITION_TOL, 1e-5, max_evaluations=180)
            q = fit['q_rad']
            results[foot] = fit
        gaps = []
        for link, kind, index, path, vertices in mesh_data:
            gap = float(placed(model, link, q, vertices)[:, 2].min() + root_height + rise)
            gaps.append({'link': link, 'kind': kind, 'index': index, 'min_ground_gap_m': gap})
        failures = []
        if not all(r['passed'] for r in results.values()):
            failures.append('IK residual/budget failure; not proof of unreachable geometry')
        if any(g['min_ground_gap_m'] < -GROUND_TOL for g in gaps):
            failures.append('mesh ground penetration')
        if any(g['min_ground_gap_m'] <= GROUND_TOL for g in gaps if g['link'] not in FEET):
            failures.append('non-foot mesh ground contact')
        feet = {}
        for foot, data in foot_data.items():
            pose = geometry.fk(model['joints'], foot, q)
            shank = geometry.fk(model['joints'], data['shank'], q)
            relative = shank[:3, :3].T @ pose[:3, :3]
            points = placed(model, foot, q, data['local']) + [0., 0., root_height + rise]
            margins = {n: float(min(q[n] - model['joints'][n]['limits'][0],
                                         model['joints'][n]['limits'][1] - q[n])) for n in data['foot_joints']}
            if min(margins.values()) <= FOOT_MARGIN + 1e-7:
                failures.append(foot + ': foot margin boundary reached')
            if fraction > 0 and (points[1, 2] <= GROUND_TOL or points[1, 2] <= points[0, 2] + GROUND_TOL):
                failures.append(foot + ': heel not elevated')
            if fraction > 0 and Rotation.from_matrix(relative).magnitude() < 1e-4:
                failures.append(foot + ': no foot-relative-shank rotation')
            feet[foot] = {'front_world_m': points[0].tolist(), 'heel_world_m': points[1].tolist(),
                          'normal_root': pose[:3, 2].tolist(),
                          'tilt_rad': float(np.arccos(np.clip(pose[2, 2], -1., 1.))),
                          'foot_relative_shank_rotation': relative.tolist(),
                          'foot_relative_shank_angle_rad': float(Rotation.from_matrix(relative).magnitude()),
                          'foot_joint_margin_rad': margins,
                          'solver': {k: v for k, v in results[foot].items() if k != 'q_rad'}}
        margins = {n: float(min(q[n] - j['limits'][0], j['limits'][1] - q[n]))
                   for n, j in model['joints'].items() if n in q}
        if min(margins.values()) <= 1e-7:
            failures.append('joint mechanical bound reached')
        samples.append({'root_position_world_m': [0., 0., root_height + rise], 'root_rise_m': rise,
                        'desired_tilt_rad': angle, 'q_rad': dict(q), 'feet': feet,
                        'all_mesh_ground_gaps': gaps, 'min_ground_gap_m': min(g['min_ground_gap_m'] for g in gaps),
                        'all_joint_margin_rad': margins, 'passed': not failures, 'failures': failures})
        if failures:
            break
    bindings = {str(p): sha256_file(p) for p in {urdf, Path(__file__).resolve(),
                Path(sys.modules[solve.__module__].__file__).resolve(), Path(geometry.__file__).resolve(),
                *[row[3] for row in mesh_data]}}
    return {'passed': len(samples) == 11 and all(s['passed'] for s in samples), 'urdf': str(urdf),
            'bindings_sha256': bindings, 'initial_q_rad': initial, 'axes': axes,
            'edge_selection': {f: {'front_edge_root_m': d['edge'].tolist(),
                                   'front_local_m': d['local'][0].tolist(), 'heel_local_m': d['local'][1].tolist(),
                                   'criterion': 'unique bottom vertices, maximum root +x; edge horizontal along y'}
                               for f, d in foot_data.items()},
            'samples': samples, 'position_tolerance_m': POSITION_TOL, 'ground_tolerance_m': GROUND_TOL,
            'foot_margin_rad': FOOT_MARGIN, 'self_collision': False,
            'scope': '11 discrete geometry nodes only; identity root rotation, 0.15 rad tilt about +root y; '
                     'no continuous path, loads, support stability, physical contact, sliding or PD claim'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--urdf', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('output exists')
    report = run(args.urdf)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    print(json.dumps({'out': str(args.out.resolve()), 'sha256': sha256_file(args.out),
                      'passed': report['passed'], 'nodes': len(report['samples']),
                      'last_failures': report['samples'][-1]['failures']}))
    raise SystemExit(0 if report['passed'] else 1)
