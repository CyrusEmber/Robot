# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Prepare a bounded LF lift with stance-foot IK and a preceding body shift [m, s, rad]."""
import argparse
import json
from pathlib import Path

import numpy as np

import local_path_check as check
import palm_spatial_standing as standing


def prepare(standing_path, pose_path, out, load_reference=None):
    prior = json.loads(standing_path.read_text(encoding='utf-8'))
    source = json.loads(pose_path.read_text(encoding='utf-8'))
    assert prior['completed'] and prior['status'] == 'standing_verified'
    assert source['identity']['candidate_files_sha256']['palm_spatial.urdf'] == standing.wiring.URDF_HASH
    build, models, model, zero, collision, _, root, *_ = check.probe._static_prepare(Path(source['identity']['build_report']))
    root[2, 3] = prior['standing_adapter']['root_height_m']
    shift = np.array([-.08, -.10, 0.])
    clearance = .06
    footholds = {leg: root[:3, :3] @ m.neutral + root[:3, 3] for leg, m in models.items()}
    normals = {leg: m.sole(np.zeros(5))[1] for leg, m in models.items()}
    reference = None
    if load_reference:
        reference = json.loads(load_reference.read_text(encoding='utf-8'))
        assert reference['completed'] and reference['status'] == 'single_leg_lift_failed' and reference['stop_reason'] is None
        assert reference['lift_plan']['desired_root_shift_m'] == shift.tolist()
        assert reference['lift_plan']['standing_report_sha256'] == standing.wiring.binding.sha256_file(standing_path)
        assert not reference['lift_verdict']['checks']['supported_hold']
        tail_names = [n for n in zero if n.startswith('tail')]
        pitch_names = [n for n in tail_names if 'pitch' in n]
        tail_clouds, tail_heights = {}, {}
        for link in ('tail2_pitch', 'tail3_pitch'):
            cloud = standing.csc.read_obj(model['links'][link]['collision'])
            pose = standing.csc.fk(model['joints'], link, zero)
            world = cloud @ pose[:3, :3].T + pose[:3, 3]
            tail_clouds[link] = cloud
            tail_heights[link] = world[:, 2].min()+root[2, 3]
        def tail_pose(t):
            base = min(reference['samples'], key=lambda row: abs(row['t_s']-5.))
            sample = min(reference['samples'], key=lambda row: abs(row['t_s']-(13. if t >= 11. else t)))
            goal = {n: float(sample['q_rad'][k]-base['q_rad'][k]) for k, n in enumerate(reference['joint_names']) if n in tail_names}
            desired = np.array([goal[n] for n in pitch_names])
            def residual(angles):
                named = dict(goal, **dict(zip(pitch_names, angles)))
                rows = []
                for link, cloud in tail_clouds.items():
                    pose = standing.csc.fk(model['joints'], link, named)
                    height = (cloud @ pose[:3, :3].T+pose[:3, 3])[:, 2].min()+root[2, 3]
                    rows.append(max(tail_heights[link]-height, 0.)/1e-5)
                return np.r_[rows, angles-desired]
            lo, hi = np.array([model['joints'][n]['limits'] for n in pitch_names]).T
            solved = check.probe.least_squares(residual, desired, bounds=(lo, hi),
                                              max_nfev=200, xtol=1e-12, ftol=1e-12, gtol=1e-12)
            errors = residual(solved.x)
            assert abs(errors[:2]).max() < 1., ('tail follow clearance', t, errors)
            return dict(goal, **dict(zip(pitch_names, map(float, solved.x))))
    paths, previous = [], zero.copy()
    for phase in ('transfer', 'lift'):
        nodes = []
        for u in np.linspace(0., 1., 17):
            q = zero.copy()
            for leg, m in models.items():
                offset = shift*u if phase == 'transfer' else shift
                goal = m.neutral-offset + ([0., 0., clearance*u] if phase == 'lift' and leg == 'lf' else np.zeros(3))
                angles = m.solve(goal, normals[leg], np.array([previous[n] for n in m.names]))
                point, normal = m.sole(angles)
                assert np.linalg.norm(point-goal) < 1e-4 and np.linalg.norm(normal-normals[leg]) < 1e-4, (leg, phase, u, 'IK', np.linalg.norm(point-goal), np.linalg.norm(normal-normals[leg]), angles)
                q.update(dict(zip(m.names, map(float, angles))))
            if reference is not None:
                q.update(tail_pose(5.+3.*u if phase == 'transfer' else 8.+3.*u))
            nodes.append(q)
            previous = q
        paths.append(nodes)
    # Each small joint-linear segment is traversed with quintic time. Check nodes and midpoints.
    readings = []
    for segment, nodes in enumerate(paths):
        for u in np.linspace(0., 1., 33):
            index = min(int(u*16), 15)
            fraction = u*16-index
            q = {n: float(nodes[index][n]+fraction*(nodes[index+1][n]-nodes[index][n])) for n in zero}
            reference_root = root.copy()
            reference_root[:3, 3] += u*shift if segment == 0 else shift
            state = check._body_state(q, reference_root, model, collision)
            assert not state['limit_failures'] and not state['solid_pairs'], (segment, u, state['limit_failures'], state['solid_pairs'])
            assert state['all_ground_min_m'] >= -source['source_config']['position_tolerance_m'], (segment, u, 'ground', state['all_ground_min_m'])
            for leg, m in models.items():
                angles = np.array([q[n] for n in m.names])
                assert m.sole(angles)[1][2] > 0, (leg, 'palm flip')
                bend = m.names.index(build['definitions'][leg]['bend']+'_joint')
                straight = check.probe.reach.straight_hfe(m.chain)
                assert angles[bend]*np.sign(straight) < abs(straight), (leg, 'reverse bend')
            readings.append(dict(segment=segment, u=float(u), **state))
    transfer, lift = paths
    keyframes = [(0., zero), (5., zero)]
    keyframes.extend((5.+3.*i/16, q) for i, q in enumerate(transfer) if i)
    keyframes.extend((8.+3.*i/16, q) for i, q in enumerate(lift) if i)
    keyframes.append((13., lift[-1]))
    keyframes.extend((13.+3.*i/16, q) for i, q in enumerate(reversed(lift)) if i)
    keyframes.extend((16.+3.*i/16, q) for i, q in enumerate(reversed(transfer)) if i)
    keyframes.append((22., zero))
    plan = dict(leg='lf', foot=prior['target']['end_links']['lf'],
                standing_report=str(standing_path.resolve()), standing_report_sha256=standing.wiring.binding.sha256_file(standing_path),
                pose_report=str(pose_path.resolve()), pose_report_sha256=standing.wiring.binding.sha256_file(pose_path),
                code_sha256=standing.wiring.binding.sha256_file(Path(__file__)), lift_settings=standing.LIFT_SETTINGS,
                target_q_rad=lift[-1], keyframes=[dict(t_s=t, q_rad=q) for t, q in keyframes],
                windows=dict(baseline=[4., 5.], transfer=[7., 8.], hold=[12., 13.], recovery=[21., 22.]),
                duration_s=22., desired_root_shift_m=shift.tolist(), nominal_clearance_m=clearance,
                max_physical_attempts=2, geometry=readings,
                footholds_world_m={leg: point.tolist() for leg, point in footholds.items()},
                sole_local_m={leg: m.sole_local.tolist() for leg, m in models.items()},
                root_scope='IK reference only; no runtime base state writes or external forces')
    if reference is not None:
        plan['tail_follow_reference'] = dict(path=str(load_reference.resolve()), sha256=standing.wiring.binding.sha256_file(load_reference),
                                           rule='actual forward tail q minus settled baseline, pitch fitted to avoid nominal ground penetration; reverse on return; no fixed tail XY anchors')
    out = out.resolve()
    assert standing.wiring.REPO/'rl_exp/out' in out.parents and not out.exists()
    out.mkdir(parents=True)
    standing.wiring.write_json(out/'plan.json', plan)
    print('TRANSFER_PLAN_READY', 'shift_m', shift, 'lf_clearance_m', clearance, 'checked_poses', len(readings))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--standing_report', type=Path, required=True)
    parser.add_argument('--pose_report', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--load_reference', type=Path)
    args = parser.parse_args()
    prepare(args.standing_report, args.pose_report, args.out, args.load_reference)
