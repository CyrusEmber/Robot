# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Replay one unchanged-candidate standing force observation, without physics.

Torque is a physics-step average [N*m], time [s], angles [rad], force [N].
An early safety stop is an incomplete load envelope, even if no cap was reached.
This audit does not establish motor ratings, continuous capability, or walking margin.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import palm_spatial_runtime as wiring
from palm_spatial_inertia import csc, _rotation


def audit(path):
    report = json.loads(path.read_text(encoding='utf-8'))
    assert report['completed'] and report['stage'] == 'completed'
    assert report['status'] in ('standing_force_observation_standing_verified',
                                'standing_force_observation_standing_failed')
    assert report['retry_allowed'] is False and report['full_runs_started'] == 1
    assert report['code_sha256'] == wiring.binding.sha256_file(path.parent/'source.py')
    for name, digest in report['dependency_sha256'].items():
        assert digest == wiring.binding.sha256_file(path.parent/name)
    for source, digest in report['input'].items():
        assert digest == wiring.binding.sha256_file(Path(source))
    prior = json.loads(Path(next(iter(report['input']))).read_text(encoding='utf-8'))
    names = report['joint_names']
    assert names == prior['joint_names'] and report['readbacks']['fixed_base'] is False
    for key in ('kp', 'kd', 'effort_caps', 'velocity_caps'):
        assert report['readbacks'][key] == prior['readbacks'][key], key
    manifest_path = Path(report['manifest'])
    assert wiring.binding.sha256_file(manifest_path) == report['manifest_sha256']
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    old_manifest = json.loads(Path(prior['tracking_manifest']).read_text(encoding='utf-8'))
    assert old_manifest['config'].keys() == manifest['config'].keys()
    for key, value in old_manifest['config'].items():
        if key != 'scene.robot.init_state.pos':
            assert value == manifest['config'][key], key
    for key in ('urdf', 'target'):
        assert wiring.binding.sha256_file(Path(manifest[key])) == manifest['sha256'][key]
    assert manifest['sha256']['urdf'] == old_manifest['sha256']['urdf']
    rows = report['samples']
    dt = report['settings']['dt_s']
    times = np.asarray([r['t_s'] for r in rows])
    assert np.allclose(times, np.arange(1, len(rows)+1)*dt, atol=1e-12, rtol=0)
    assert 0 < len(rows) <= round(report['settings']['duration_s']/dt)
    binding = report['joint_force_probe']
    assert binding['joint_names'] == names and binding['body_names'] == report['body_names']
    caps = np.asarray(report['readbacks']['effort_caps'])
    velocity_caps = np.asarray(report['readbacks']['velocity_caps'])
    q = np.asarray([r['q_rad'] for r in rows])
    v = np.asarray([r['velocity_rad_s'] for r in rows])
    effort = np.asarray([r['joint_force_probe']['projected_joint_effort_nm'] for r in rows])
    limits = np.asarray(binding['position_limits_rad'])
    explicit_max = projection_error = 0.
    for row in rows:
        sample = row['joint_force_probe']
        raw = np.asarray(sample['incoming_child_joint_wrench'])
        assert raw.shape == (31, 6) and np.isfinite(raw).all()
        manual = np.asarray([raw[binding['joints'][name]['child_index'],
                                 binding['joints'][name]['torque_component']] for name in names])
        assert np.array_equal(manual, sample['manual_axis_projection_nm'])
        projected = np.asarray(sample['projected_joint_effort_nm'])
        # Float32 transform roundoff budget, proportional to the raw wrench scale.
        assert np.allclose(manual, projected, atol=1e-5, rtol=1e-5)
        projection_error = max(projection_error, float(abs(manual-projected).max()))
        explicit_max = max(explicit_max, float(abs(np.asarray(sample['explicit_actuation_input_nm'])).max()))
        assert np.all(np.asarray(row['target_q_rad']) == 0)
        for key in ('position_rad', 'velocity_rad_s'):
            assert np.all(np.asarray(row['backend_drive_targets'][key]) == 0)
        assert row['backend_drive_targets']['joint_names'] == names
    assert all(np.isfinite(a).all() for a in (q, v, effort, caps, limits))
    assert np.all(caps > 0) and explicit_max == 0
    assert np.all(np.asarray(binding['friction_properties']) == 0)
    assert np.all(np.asarray(binding['armatures']) == 0) and not binding['tendon_prims']
    model = csc.load_urdf(Path(manifest['urdf']))
    fk_error = 0.
    for snapshot in (report['initial_entities'], report['final_entities']):
        poses = snapshot['actor_poses_xyzw']
        root_pose = poses[snapshot['body_names'].index('base_link')]
        root = np.eye(4)
        root[:3, :3], root[:3, 3] = _rotation(root_pose[3:]), root_pose[:3]
        angles = dict(zip(names, snapshot['q_rad']))
        for name, pose in zip(snapshot['body_names'], poses):
            predicted = root @ csc.fk(model['joints'], name, angles)
            actual = np.eye(4)
            actual[:3, :3], actual[:3, 3] = _rotation(pose[3:]), pose[:3]
            fk_error = max(fk_error, float(abs(predicted-actual).max()))
    assert fk_error < 1e-5
    settings = report['settings']
    stop = None
    feet = list(report['target']['end_links'].values())
    allowed = set(feet) | {n for n in report['ground_pair_mapping'] if n.startswith('tail')}
    for k, row in enumerate(rows):
        forbidden = max(np.linalg.norm(f) for n, f in row['ground_forces_n'].items() if n not in allowed)
        assert np.isclose(forbidden, row['forbidden_ground_n'])
        checks = dict(root_drop=row['root_drop_m'] > settings['stop_drop_m'],
                      root_tilt=row['tilt_rad'] > settings['stop_tilt_rad'],
                      joint_motion=bool(abs(q[k]).max() > settings['stop_joint_rad']),
                      forbidden_ground=forbidden > settings['stop_forbidden_ground_n'],
                      joint_speed=bool(np.any(abs(v[k]) >= velocity_caps*.5)))
        if any(checks.values()):
            assert k == len(rows)-1, 'continued after stop'
            stop = [name for name, failed in checks.items() if failed]
    assert stop == report['stop_reason']
    late = times >= settings['duration_s']-1
    assert stop is not None or len(rows) == round(settings['duration_s']/dt)
    failures = []
    mean_support = None
    if not late.any():
        failures.append('missing final standing window')
    else:
        late_rows = [r for r, selected in zip(rows, late) if selected]
        mean_support = float(np.mean([sum(f[2] for f in r['ground_forces_n'].values()) for r in late_rows]))
        if max(r['root_drop_m'] for r in late_rows) > settings['standing_drop_m']:
            failures.append('root_drop')
        if max(r['tilt_rad'] for r in late_rows) > settings['standing_tilt_rad']:
            failures.append('root_tilt')
        failures.extend(name for i, name in enumerate(names) if abs(q[late, i]).max() > settings['standing_joint_rad'])
        if max(abs(r['root_velocity'][2]) for r in late_rows) > settings['standing_vertical_speed_m_s']:
            failures.append('root_vertical_speed')
        failures.extend('missing_support:'+foot for foot in feet
                        if min(r['ground_forces_n'][foot][2] for r in late_rows) < settings['foot_load_n'])
        if abs(mean_support-report['weight_n']) > settings['weight_relative_error']*report['weight_n']:
            failures.append('total_ground_support')
    passed = stop is None and not failures
    assert passed == (report['status'] == 'standing_force_observation_standing_verified')
    assert mean_support == report['late_mean_ground_support_n']
    joints = []
    for i, name in enumerate(names):
        ratio = abs(effort[:, i])/caps[i]
        longest = current = 0
        for clipped in ratio >= .99:
            current = current+1 if clipped else 0
            longest = max(longest, current)
        peak = int(np.argmax(ratio))
        joints.append(dict(joint=name, cap_nm=float(caps[i]), max_abs_step_average_nm=float(abs(effort[:, i]).max()),
                           peak_t_s=float(times[peak]), max_cap_fraction=float(ratio[peak]),
                           samples_at_99_percent=int((ratio >= .99).sum()), longest_99_percent_s=longest*dt,
                           late_max_abs_nm=float(abs(effort[late, i]).max()) if late.any() else None,
                           min_limit_margin_rad=float(np.minimum(q[:, i]-limits[i, 0], limits[i, 1]-q[:, i]).min()),
                           max_velocity_cap_fraction=float((abs(v[:, i])/velocity_caps[i]).max()),
                           final_error_rad=float(q[-1, i])))
    return dict(report_sha256=wiring.binding.sha256_file(path), status=report['status'], steps=len(rows),
                duration_s=float(times[-1]), stop_reason=stop, max_projection_error_nm=projection_error,
                fk_max_error=fk_error, explicit_input_max_nm=explicit_max,
                max_joint_error_rad=float(abs(q).max()),
                final_root_drop_m=rows[-1]['root_drop_m'], final_root_tilt_rad=rows[-1]['tilt_rad'],
                final_ground_support_n=sum(f[2] for f in rows[-1]['ground_forces_n'].values()),
                weight_n=report['weight_n'], late_mean_ground_support_n=mean_support,
                standing_failure_reasons=failures,
                joints=sorted(joints, key=lambda j: -j['max_cap_fraction']),
                scope='Observed load only; early stop gives no sustained standing or walking margin; step averages, not substep peaks')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert args.out.parent.is_dir() and not args.out.exists()
    result = audit(args.report.resolve())
    wiring.write_json(args.out, result)
    print('STANDING_FORCE_AUDIT_OK', result['status'], result['duration_s'], result['stop_reason'])
    for row in result['joints'][:6]:
        print(row['joint'], 'peak_Nm', row['max_abs_step_average_nm'], 'cap_fraction', row['max_cap_fraction'])
