# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Free-palm 5b geometry, not force/rolling/stability acceptance [m, rad, s].

Retain the prescribed root recovery and horizontal sole reference. Replace the historical normal
target and fixed reference height with lowest collision-mesh height. A contacting palm may tilt;
its centroid need not lie on the ground. Three geometric constraints leave one IK freedom, chosen
by continuation. Reference XY is not a fixed material contact point. The report measures material
point motion at the lowest feature, so apparent contact migration is not mislabeled no-slip rolling.
Non-palm ground penetration and collision failures remain failures. No PD or asset changes.
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

import palm_motion_boundaries as motion

HERE = Path(__file__).resolve()


def contact_state(leg: motion.gait.Leg, q: np.ndarray, rotate: np.ndarray,
                  shift: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """World reference [m], palm normal and collision vertices [m]."""
    pose = leg.pose(q)
    vertices = (leg.verts @ pose[:3, :3].T + pose[:3, 3]) @ rotate.T + shift
    point, normal = leg.sole(q)
    return rotate @ point + shift, rotate @ normal, vertices


def solve_contact(leg: motion.gait.Leg, rotate: np.ndarray, shift: np.ndarray,
                  target_xy: np.ndarray, target_floor: float, guess: np.ndarray,
                  config: dict) -> np.ndarray:
    """Solve reference XY and minimum mesh height [m], allowing palm rotation [rad]."""
    def residual(q):
        point, _, vertices = contact_state(leg, q, rotate, shift)
        return np.r_[point[:2] - target_xy, vertices[:, 2].min() - target_floor]

    bounds = (leg.lo + config['limit_margin_rad'], leg.hi - config['limit_margin_rad'])
    result = least_squares(residual, np.clip(guess, *bounds), bounds=bounds,
                           xtol=1e-12, ftol=1e-12, gtol=1e-12)
    if np.linalg.norm(result.fun) <= config['pos_tol_m']:
        return result.x
    candidates = [result]
    for seed in range(8):
        candidates.append(least_squares(residual, np.random.default_rng(seed).uniform(*bounds),
                                        bounds=bounds, xtol=1e-12, ftol=1e-12, gtol=1e-12))
    return min(candidates, key=lambda item: np.linalg.norm(item.fun)).x


def run_case(name: str, source: Path, output: Path, legs: dict,
             detector: motion.Collision, config: dict) -> dict:
    with (source / f'{name}.csv').open() as handle:
        rows = list(csv.DictReader(handle))
    floor = min(contact_state(leg, np.zeros(4), np.eye(3), np.zeros(3))[2][:, 2].min()
                for leg in legs.values())
    previous = {l: np.zeros(4) for l in legs}
    previous_vertices = {}
    previous_contact = {}
    joint_history = {l: [] for l in legs}
    trace = []
    stats = {l: {'max_reference_xy_error_m': 0., 'max_height_error_m': 0.,
                 'max_palm_tilt_deg': 0., 'max_reference_above_floor_m': 0.,
                 'max_contact_material_speed_m_s': 0., 'contact_feature_switches': 0}
             for l in legs}
    collision_worst, ground_worst = {}, {}
    for k, row in enumerate(rows):
        rotate = np.array([[float(row[f'root_r{i}{j}']) for j in range(3)] for i in range(3)])
        shift = np.array([float(row[f'root_{axis}_m']) for axis in 'xyz'])
        t = float(row['t_s'])
        dt = t - float(rows[k - 1]['t_s']) if k else None
        angles, contacts = {}, {}
        for l, leg in legs.items():
            # These are recovery cases, not stepping. All palms have a geometric ground target.
            target_xy = leg.neutral_sole[:2]
            q = solve_contact(leg, rotate, shift, target_xy, floor, previous[l], config)
            point, normal, vertices = contact_state(leg, q, rotate, shift)
            height = float(vertices[:, 2].min())
            indices = np.flatnonzero(vertices[:, 2] <= height + config['pos_tol_m'])
            feature = tuple(map(int, indices))
            stat = stats[l]
            stat['max_reference_xy_error_m'] = max(stat['max_reference_xy_error_m'], float(np.linalg.norm(point[:2] - target_xy)))
            stat['max_height_error_m'] = max(stat['max_height_error_m'], abs(height - floor))
            stat['max_palm_tilt_deg'] = max(stat['max_palm_tilt_deg'], float(np.degrees(np.arccos(np.clip(normal[2], -1, 1)))))
            stat['max_reference_above_floor_m'] = max(stat['max_reference_above_floor_m'], float(point[2] - floor))
            if k:
                # Same material vertices at both instants, not the difference between changing
                # contact-feature centroids. Nonzero speed indicates a possible slip contribution.
                speed = np.linalg.norm((vertices[indices, :2] - previous_vertices[l][indices, :2]) / dt, axis=1)
                stat['max_contact_material_speed_m_s'] = max(stat['max_contact_material_speed_m_s'], float(speed.max()))
                stat['contact_feature_switches'] += feature != previous_contact[l]
            contacts[l] = {'height_m': height, 'reference_z_m': float(point[2]),
                           'tilt_deg': float(np.degrees(np.arccos(np.clip(normal[2], -1, 1)))),
                           'contact_vertex_indices': list(feature)}
            previous[l], previous_vertices[l], previous_contact[l] = q, vertices, feature
            joint_history[l].append(q)
            angles.update(zip(leg.names, map(float, q)))
        for item in detector.check(angles):
            key = '~'.join(item['pair'])
            if key not in collision_worst or item['gap_lower_m'] < collision_worst[key]['gap_lower_m']:
                collision_worst[key] = dict(item, frame=k)
        for link, (vertices, _) in detector.local.items():
            pose = motion.gait.csc.fk(detector.urdf['joints'], link, angles)
            world = (vertices @ pose[:3, :3].T + pose[:3, 3]) @ rotate.T + shift
            gap = float(world[:, 2].min() - floor)
            if gap < ground_worst.get(link, {'min_gap_m': np.inf})['min_gap_m']:
                ground_worst[link] = {'min_gap_m': gap, 'frame': k}
        trace.append({'t_s': t, 'angles_rad': angles, 'contacts': contacts,
                      'root_rotation': rotate.tolist(), 'root_translation_m': shift.tolist()})
    failures = []
    for l, leg in legs.items():
        stat = stats[l]
        q = np.array(joint_history[l])
        duration = float(rows[-1]['t_s']) - float(rows[0]['t_s'])
        dt = duration / (len(rows) - 1)
        stat['seam_rad'] = float(np.abs(q[-1] - q[0]).max())
        stat['max_frame_step_rad'] = float(np.abs(np.diff(q, axis=0)).max())
        stat['max_velocity_rad_s'] = np.abs(np.diff(q, axis=0) / dt).max(0).tolist()
        if stat['max_reference_xy_error_m'] > config['pos_tol_m'] or stat['max_height_error_m'] > config['pos_tol_m']:
            failures.append(f'{l}: contact geometry residual')
        if stat['max_palm_tilt_deg'] >= 90:
            failures.append(f'{l}: inverted contact palm')
        if stat['seam_rad'] > 1e-6 or stat['max_frame_step_rad'] > config['max_frame_step_rad']:
            failures.append(f'{l}: continuity')
    if any(item['fail'] for item in collision_worst.values()):
        failures.append('self collision clearance')
    penetrated = {link: item for link, item in ground_worst.items() if item['min_gap_m'] < -config['pos_tol_m']}
    if penetrated:
        failures.append('ground penetration')
    case = {'name': name, 'status': 'FAIL' if failures else 'PASS_CONTACT_GEOMETRY_ONLY',
            'failures': failures, 'floor_z_m': float(floor), 'legs': stats,
            'ground_penetration': penetrated,
            'collision_closest': sorted(collision_worst.values(), key=lambda item: item['gap_lower_m'])[:12]}
    (output / f'{name}.json').write_text(json.dumps(case, indent=1))
    (output / f'{name}_trace.json').write_text(json.dumps(trace))
    print('PALM_CONTACT', name, case['status'], failures, flush=True)
    return case


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source_report_dir', type=Path, required=True)
    parser.add_argument('--output_dir', type=Path, required=True)
    args = parser.parse_args()
    source = args.source_report_dir.resolve()
    original = json.loads((source / 'report.json').read_text())
    assert original['completed']
    config = original['config']
    path = Path(config['urdf'])
    motion.validate_geometry(path)
    urdf = motion.gait.csc.load_urdf(path)
    legs = {l: motion.gait.Leg(urdf, l) for l in motion.LEGS}
    detector = motion.Collision(urdf, config['clearance_m'])
    output = args.output_dir.resolve()
    assert motion.REPO / 'rl_exp/out' in output.parents
    files = [HERE, Path(motion.__file__), Path(motion.gait.__file__), Path(motion.gait.csc.__file__),
             Path(motion.gait.binding.__file__), path, source / 'report.json'] + detector.mesh_paths
    names = ['recover_pitch_pos', 'recover_pitch_neg', 'recover_roll_pos', 'recover_roll_neg']
    files += [source / f'{name}.csv' for name in names]
    hashes = {str(p.resolve()): motion.gait.binding.sha256_file(p) for p in files}
    for p in [path] + detector.mesh_paths:
        assert hashes[str(p.resolve())] == original['identity']['files'][str(p.resolve())], 'asset changed'
    output.mkdir(parents=True, exist_ok=False)
    for p in files:
        if p.suffix == '.py':
            target = output / 'source_snapshot' / p.resolve().relative_to(motion.REPO)
            target = target.with_suffix('.py.txt')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(p.read_bytes())
    identity = {'revision': motion.gait.binding.git_rev(motion.REPO), 'files': hashes}
    (output / 'launch_identity.json').write_text(json.dumps(identity, indent=1))
    cases = [run_case(name, source, output, legs, detector, config) for name in names]
    assert all(motion.gait.binding.sha256_file(p) == hashes[str(p.resolve())] for p in files)
    report = {'completed': True, 'identity': identity, 'config': config, 'cases': cases,
              'scope': 'free_palm_recovery_contact_geometry_not_no_slip_or_loaded_acceptance'}
    (output / 'report.json').write_text(json.dumps(report, indent=1))
    raise SystemExit(1 if any(case['failures'] for case in cases) else 0)


if __name__ == '__main__':
    main()
