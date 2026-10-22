# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Replay two isolated TGS force-timing probes without starting physics.

Reports position-difference versus backend joint velocity [rad/s], force [N*m],
and real policy observation term/column agreement. This does not adopt a solver
configuration or revalidate all gains, contacts, free-base motion, or speed caps.
"""
import argparse
import copy
import json
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np
import palm_spatial_runtime as wiring
from palm_spatial_inertia import _rotation


def semantic_fixture_check(cfg):
    """Exercise real observation consumers with distinct nonzero synthetic inputs.

    Fixtures check consumer selection and default subtraction, not backend frame conversion.
    They are never written into a running articulation or a training configuration.
    """
    import torch
    array = lambda values: torch.tensor([values], dtype=torch.float32)
    q = array([.01*(i+1) for i in range(30)])
    v = array([-.02*(i+1) for i in range(30)])
    default_q, default_v = q*.1, v*.2
    source = dict(root_lin_vel_b=array([.13, -.24, .35]), root_ang_vel_b=array([-.46, .57, -.68]),
                  projected_gravity_b=array([.2, -.4, -np.sqrt(.8)]), joint_pos=q, joint_vel=v,
                  default_joint_pos=default_q, default_joint_vel=default_v)
    data = NS(**{name: NS(torch=value) for name, value in source.items()})
    commands = array([.79, -.81, .92])
    actions = array([.03*(i+1) for i in range(30)])
    env = NS(scene={'robot': NS(data=data)}, command_manager=NS(get_command=lambda _: commands),
             action_manager=NS(action=actions))
    expected = dict(base_lin_vel=source['root_lin_vel_b'], base_ang_vel=source['root_ang_vel_b'],
                    projected_gravity=source['projected_gravity_b'], velocity_commands=commands,
                    joint_pos=q-default_q, joint_vel=v-default_v, actions=actions)
    checked = {}
    for name, reference in expected.items():
        term = getattr(cfg.observations.policy, name)
        actual = term.func(env, **term.params)
        assert torch.equal(actual, reference), 'nonzero observation semantic mismatch: '+name
        checked[name] = dict(width=actual.shape[-1], max_error=0., nonzero=True)
    return checked


def read_case(path, timing):
    report = json.loads(path.read_text(encoding='utf-8'))
    assert report['completed'] and report['status'] == 'velocity_probe_observed'
    assert report['force_timing'] == timing and report['steps_completed'] == 3400
    assert report['settings']['full_runs_started'] == 1 and not report['settings']['retry_allowed']
    assert wiring.binding.sha256_file(path.parent/'source.py') == report['code_sha256']
    assert wiring.binding.sha256_file(Path(report['reference'])) == report['reference_sha256']
    reference = json.loads(Path(report['reference']).read_text(encoding='utf-8'))
    for key in ('kp', 'kd', 'effort_caps', 'velocity_caps'):
        assert report['readbacks'][key] == reference['readbacks'][key]
    assert wiring.binding.sha256_file(Path(report['manifest'])) == report['manifest_sha256']
    for name, spec in report['dependencies'].items():
        assert wiring.binding.sha256_file(path.parent/name) == spec['sha256']
    assert report['readbacks']['force_timing'] == (timing == 'per_iteration')
    assert report['readbacks']['fixed_base'] and report['readbacks']['solver_type'] == 'TGS'
    assert all(value is False for value in report['readbacks']['body_disable_gravity'].values())
    for key in report['physics_before']:
        if key != 'enable_external_forces_every_iteration':
            assert report['physics_before'][key] == report['physics_after'][key]
    names = report['joint_names']
    assert len(names) == 30 and len(set(names)) == 30
    assert set(names) == set(report['action_names']) and len(report['action_names']) == 30
    rows = report['samples']
    t = np.asarray([r['t_s'] for r in rows])
    q = np.asarray([r['q_rad'] for r in rows])
    v = np.asarray([r['velocity_rad_s'] for r in rows])
    target = np.asarray([r['target_rad'] for r in rows])
    torque = np.asarray([r['joint_force_probe']['projected_joint_effort_nm'] for r in rows])
    assert len(rows) == 3400 and np.allclose(t, np.arange(1, 3401)*.005, atol=1e-12, rtol=0)
    assert all(a.shape == (3400, 30) and np.isfinite(a).all() for a in (q, v, target, torque))
    assert np.array_equal(q, [r['backend_q_rad'] for r in rows])
    assert np.array_equal(v, [r['backend_velocity_rad_s'] for r in rows])
    assert abs(q).max() <= .35 and abs(q-target).max() <= .35
    assert np.all(abs(v) < np.asarray(report['readbacks']['velocity_caps'])*.5)
    assert max(r['max_contact_n'] for r in rows) <= 1.
    knee = names.index('rl_knee_joint')
    assert np.all(target[:, [i for i in range(30) if i != knee]] == 0)
    assert target[:, knee].max() == .02 and target[:, knee].min() == -.02
    expected_order = ['base_lin_vel', 'base_ang_vel', 'projected_gravity', 'velocity_commands',
                      'joint_pos', 'joint_vel', 'actions']
    obs_error = 0.
    nonzero = set()
    observation_count = 0
    for row in rows:
        assert np.allclose(row['backend_drive_targets']['position_rad'], row['target_rad'], atol=1e-8, rtol=1e-6)
        assert np.all(np.asarray(row['backend_drive_targets']['velocity_rad_s']) == 0)
        if 'observation' not in row:
            continue
        observation_count += 1
        obs = row['observation']
        assert obs['joint_names'] == names
        assert [term['name'] for term in obs['terms']] == expected_order
        concatenated = []
        for term in obs['terms']:
            name, raw = term['name'], np.asarray(term['raw'])
            if np.any(raw != 0):
                nonzero.add(name)
            if name == 'joint_pos':
                assert np.array_equal(raw, row['backend_q_rad'])
            elif name == 'joint_vel':
                assert np.array_equal(raw, row['backend_velocity_rad_s'])
            elif name == 'actions':
                expected = [row['target_rad'][names.index(n)] for n in report['action_names']]
                assert np.array_equal(raw, np.asarray(expected, dtype=np.float32))
            elif name == 'projected_gravity':
                expected = _rotation(obs['root_pose_xyzw'][3:]).T @ np.array([0., 0., -1.])
                assert np.allclose(raw, expected, atol=1e-6, rtol=1e-6)
            processed = raw
            if term['clip'] is not None:
                processed = np.clip(processed, *term['clip'])
            if term['scale'] is not None:
                processed = processed*np.asarray(term['scale'])
            assert np.allclose(processed, term['processed'], atol=1e-8, rtol=1e-6)
            concatenated.extend(processed.tolist())
        assert len(obs['policy']) == len(concatenated) == 102
        obs_error = max(obs_error, float(abs(np.asarray(obs['policy'])-concatenated).max()))
        assert np.allclose(obs['policy'], concatenated, atol=1e-8, rtol=1e-6)
    assert observation_count == 170 and {'joint_pos', 'joint_vel', 'actions'} <= nonzero
    midpoint = (t[1:]+t[:-1])/2
    derivative = np.diff(q, axis=0)/.005
    velocity_midpoint = (v[1:]+v[:-1])/2
    windows = {}
    for name, lower, upper in (('settle', 4.8, 5.), ('positive_hold', 7.8, 8.),
                                ('negative_hold', 13.8, 14.), ('return', 16.8, 17.)):
        mask = (midpoint >= lower) & (midpoint <= upper)
        positions = (t >= lower) & (t <= upper)
        assert mask.sum() == 40
        windows[name] = dict(knee_q_range_rad=float(np.ptp(q[positions, knee])),
            knee_position_velocity_max_rad_s=float(abs(derivative[mask, knee]).max()),
            knee_readback_velocity_mean_rad_s=float(velocity_midpoint[mask, knee].mean()),
            knee_velocity_discrepancy_max_rad_s=float(abs(velocity_midpoint[mask, knee]-derivative[mask, knee]).max()),
            knee_torque_mean_nm=float(torque[positions, knee].mean()),
            knee_target_error_max_rad=float(abs(q[positions, knee]-target[positions, knee]).max()),
            all_joint_discrepancy_max_rad_s=float(abs(velocity_midpoint[mask]-derivative[mask]).max()))
    return report, dict(report_sha256=wiring.binding.sha256_file(path), force_timing=timing,
                        cache_backend_max_difference=0., observation_samples=observation_count,
                        nonzero_observation_terms=sorted(nonzero), policy_concat_max_error=obs_error,
                        windows=windows)


def read_standing(path):
    from palm_standing_force_audit import audit
    force = audit(path, velocity_probe=True)
    report = json.loads(path.read_text(encoding='utf-8'))
    rows = report['samples']
    assert len(rows) == 1000 and force['stop_reason'] is None
    names = report['joint_names']
    q = np.asarray([r['q_rad'] for r in rows])
    v = np.asarray([r['velocity_rad_s'] for r in rows])
    assert np.array_equal(q, [r['backend_q_rad'] for r in rows])
    assert np.array_equal(v, [r['backend_velocity_rad_s'] for r in rows])
    frame_error = concat_error = 0.
    seen = set()
    count = 0
    for row in rows:
        if 'observation' not in row:
            continue
        count += 1
        obs = row['observation']
        terms = {term['name']: term for term in obs['terms']}
        assert list(terms) == ['base_lin_vel', 'base_ang_vel', 'projected_gravity', 'velocity_commands',
                               'joint_pos', 'joint_vel', 'actions']
        rotation = _rotation(row['root_pose_xyzw'][3:])
        raw_root_velocity = np.asarray(row['backend_root_com_velocity_w'])
        expected = dict(base_lin_vel=rotation.T@raw_root_velocity[:3],
                        base_ang_vel=rotation.T@raw_root_velocity[3:],
                        projected_gravity=rotation.T@np.array([0., 0., -1.]),
                        joint_pos=row['backend_q_rad'], joint_vel=row['backend_velocity_rad_s'], actions=[0.]*30)
        concatenated = []
        for name, term in terms.items():
            raw = np.asarray(term['raw'])
            if np.any(raw != 0):
                seen.add(name)
            if name in expected:
                error = float(abs(raw-expected[name]).max())
                frame_error = max(frame_error, error)
                assert np.allclose(raw, expected[name], atol=1e-6, rtol=1e-6)
            value = raw
            if term['clip'] is not None:
                value = np.clip(value, *term['clip'])
            if term['scale'] is not None:
                value = value*np.asarray(term['scale'])
            assert np.allclose(value, term['processed'], atol=1e-8, rtol=1e-6)
            concatenated.extend(value.tolist())
        assert len(obs['policy']) == len(concatenated) == 102
        concat_error = max(concat_error, float(abs(np.asarray(obs['policy'])-concatenated).max()))
        assert np.allclose(obs['policy'], concatenated, atol=1e-8, rtol=1e-6)
    assert count == 50 and {'base_lin_vel', 'base_ang_vel', 'projected_gravity', 'joint_pos', 'joint_vel'} <= seen
    times = np.asarray([r['t_s'] for r in rows])
    mask = (times[1:]+times[:-1])/2 >= 4.
    dq = np.diff(q, axis=0)/.005
    midpoint_v = (v[1:]+v[:-1])/2
    com = np.asarray([r['root_com_pose_xyzw'][:3] for r in rows])
    com_difference = np.diff(com, axis=0)/.005
    com_v = np.asarray([r['backend_root_com_velocity_w'][:3] for r in rows])
    return dict(force=force, observation_samples=count, nonzero_observation_terms=sorted(seen),
                root_frame_and_joint_raw_max_error=frame_error, policy_concat_max_error=concat_error,
                late_all_joint_velocity_discrepancy_max_rad_s=float(abs(dq[mask]-midpoint_v[mask]).max()),
                late_root_com_linear_discrepancy_max_m_s=float(abs(com_difference[mask]-(com_v[1:]+com_v[:-1])[mask]/2).max()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy', type=Path, required=True)
    parser.add_argument('--per_iteration', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--standing', type=Path, help='Optional per-iteration free-base observation report')
    args = parser.parse_args()
    assert args.out.parent.is_dir() and not args.out.exists()
    legacy, a = read_case(args.legacy.resolve(), 'legacy')
    updated, b = read_case(args.per_iteration.resolve(), 'per_iteration')
    assert legacy['reference_sha256'] == updated['reference_sha256']
    assert legacy['manifest_sha256'] == updated['manifest_sha256']
    assert legacy['code_sha256'] == updated['code_sha256']
    assert legacy['physics_before'] == updated['physics_before']
    assert {k: v for k, v in legacy['readbacks'].items() if k != 'force_timing'} == {
        k: v for k, v in updated['readbacks'].items() if k != 'force_timing'}
    result = dict(status='velocity_timing_comparison_observed', legacy=a, per_iteration=b,
                  scope='One fixed-root left-knee trajectory; no solver adoption or free-base/contact validation')
    import rl_exp.tasks
    from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg
    cfg = copy.deepcopy(resolve_task_cfg(wiring.REGISTERED_TASK))
    wiring.obs_protocol.load_diagnostic_target(Path(legacy['manifest']), cfg, wiring.REGISTERED_TASK)
    result['nonzero_consumer_fixtures'] = semantic_fixture_check(cfg)
    if args.standing:
        result['standing'] = read_standing(args.standing.resolve())
    wiring.write_json(args.out, result)
    print('VELOCITY_AUDIT_OK')
    print(json.dumps({name: case['windows']['settle'] for name, case in (('legacy', a), ('per_iteration', b))}, indent=2))
