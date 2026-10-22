# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Reapply bound default joints after initialization, then run real ownership CLI.

The initialization physics step may already resolve an authored ground overlap.
This explicit initial-impact fixture restores only the manifest's default q/dq,
without taking a physics step, changing assets, thresholds, forces or filters.
The entry observer still enforces two steps, fixed base, zero gains, no gravity
and force timing False. This is contact wiring evidence, not standing support.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from unittest.mock import patch

import palm_entry_wiring as observer


def inspect_case(out: Path, expect_contact: bool) -> dict:
    """Read actual entry, backend and ground-filter evidence without running Kit."""
    audit = json.loads((out / 'audit.json').read_text(encoding='utf-8'))
    report = json.loads((out / 'report.json').read_text(encoding='utf-8'))
    prep = json.loads((out / 'preparation.json').read_text(encoding='utf-8'))
    require = observer._require
    require(audit['closed'] and audit['fixed_base'] and audit['force_timing'] is False
            and audit['max_joint_stiffness'] == audit['max_joint_damping'] == 0.
            and len(audit['body_disable_gravity']) == 31 and all(audit['body_disable_gravity'].values()),
            'runtime flags mismatch')
    require(len(audit['env_steps']) == 2 and len(audit['physics_steps']) == 8
            and audit['decimation'] == 4 and prep['physics_steps_added'] == 0, 'step budget mismatch')
    require(prep['after_joint_pos_rad'] == prep['requested_joint_pos_rad'] == [[0.] * 30], 'default q mismatch')
    require(prep['requested_joint_vel_rad_s'] == [[0.] * 30], 'default dq mismatch')
    require(all(v == 0. for step in audit['env_steps'] for row in step['action'] for v in row), 'nonzero action')
    require(observer.sha256_file(out / 'source.py') == audit['source_sha256']
            and observer.sha256_file(out / 'observer.py') == audit['observer_sha256']
            and observer.sha256_file(out / 'preparation.py') == prep['source_sha256'], 'source snapshot mismatch')
    require(observer.sha256_file(Path(audit['manifest'])) == audit['manifest_sha256'], 'manifest changed')
    names = audit['sensor_body_names']
    if 'native_contact_sensor_paths' in audit:
        require([p.rsplit('/', 1)[-1] for p in audit['native_contact_sensor_paths']] == names,
                'native contact order mismatch')
    peaks = {name: 0. for name in names}
    ground_peaks = {}
    require({row['body'] for row in audit['ground_contact_mapping']}
            == {'lf_wrist', 'rf_wrist', 'rl_ankle', 'rr_ankle'}, 'missing ground row')
    for row in audit['ground_contact_mapping']:
        require(row['sensor_paths'] in ([row['source']], [[row['source']]])
                and row['filter_paths'] in (row['ground'], [row['ground']])
                and len(row['ground']) == 1 and row['ground'][0].startswith('/World/ground/'),
                'ground row/column mismatch')
    for step in audit['physics_steps']:
        require(set(step['foot_ground_forces_w_n']) == {'lf_wrist', 'rf_wrist', 'rl_ankle', 'rr_ankle'},
                'missing ground force column')
        require(len(step['net_forces_w_n']) == len(names), 'native force width mismatch')
        for name, force in zip(names, step['net_forces_w_n']):
            require(len(force) == 3 and all(math.isfinite(v) for v in force), 'nonfinite force')
            peaks[name] = max(peaks[name], math.sqrt(sum(v * v for v in force)))
        for name, matrix in step['foot_ground_forces_w_n'].items():
            require(len(matrix) == len(matrix[0]) == 1 and len(matrix[0][0]) == 3, 'ground matrix shape')
            force = matrix[0][0]
            require(all(math.isfinite(v) for v in force), 'nonfinite ground force')
            native = step['net_forces_w_n'][names.index(name)]
            require(max(abs(a-b) for a,b in zip(force, native)) <= .001, 'ground/net force disagreement')
            ground_peaks[name] = max(ground_peaks.get(name, 0.), math.sqrt(sum(v*v for v in force)))
    require(report['threshold'] == 1., 'contact threshold changed')
    touching = sorted(name for name, force in peaks.items() if force > report['threshold'])
    require(report['touching'] == touching, 'producer missed native physics-step contact')
    require(bool(touching) == expect_contact and not report['blind'], 'unexpected contact classification')
    require(report['status'] == ('PASS' if expect_contact else 'FAIL'), 'wrong producer verdict')
    for name, peak in peaks.items():
        if name in report['bodies']:
            require(abs(report['bodies'][name]['peak_n']-peak) <= .001, 'producer peak mismatch')
    require(report['sampling']['period_s'] == .005 and report['sampling']['history_length'] >= 4
            and report['sampling']['lazy_sensor_update'] is False, 'sparse producer sampling')
    require(int((out.parent / (out.name + '.exit')).read_text().strip()) == (0 if expect_contact else 1),
            'process exit mismatch')
    return {'status': 'PASS', 'touching': touching, 'ground_peak_n': ground_peaks,
            'scope': 'two-step contact entry wiring; no support/performance verdict'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--target_config', type=Path)
    parser.add_argument('--inspect', choices=('contact', 'air'))
    parser.add_argument('producer_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.inspect:
        print(json.dumps(inspect_case(args.out, args.inspect == 'contact'), indent=2))
        return
    if args.target_config is None:
        parser.error('--target_config is required for execution')
    forwarded = args.producer_args[1:] if args.producer_args[:1] == ['--'] else args.producer_args
    observer._require(not any(item == '--target_config' or item.startswith('--target_config=')
                              for item in forwarded), 'pass target_config only to fixture')
    import gymnasium as gym
    original_make = gym.make

    def make(*a, **kw):
        import torch
        import warp as wp

        env = original_make(*a, **kw)
        live = env.unwrapped
        document = json.loads(args.target_config.read_text(encoding='utf-8'))
        observer._require(live.num_envs == 1 and observer.sha256_file(Path(document['target_binding']['urdf']))
                          == observer.URDF_SHA256, 'unexpected impact target')
        robot = live.scene['robot']
        before = wp.to_torch(robot.root_physx_view.get_dof_positions()).clone()
        q, dq = robot.data.default_joint_pos.torch.clone(), robot.data.default_joint_vel.torch.clone()
        observer._require(bool(torch.isfinite(q).all()) and bool((q == 0).all())
                          and bool((dq == 0).all()), 'fixture requires bound zero default joints')
        robot.write_joint_state_to_sim(q, dq)
        live.sim.forward()
        after = wp.to_torch(robot.root_physx_view.get_dof_positions()).clone()
        observer._require(bool((after == q).all()), 'default state not applied to backend')
        (args.out / 'preparation.py').write_bytes(Path(__file__).read_bytes())
        (args.out / 'preparation.json').write_text(json.dumps({
            'source_sha256': observer.sha256_file(Path(__file__)), 'physics_steps_added': 0,
            'before_joint_pos_rad': before.cpu().tolist(), 'requested_joint_pos_rad': q.cpu().tolist(),
            'after_joint_pos_rad': after.cpu().tolist(), 'requested_joint_vel_rad_s': dq.cpu().tolist(),
            'scope': 'explicit initial-impact state injection after gym.make; no support verdict'}, indent=2),
            encoding='utf-8')
        return env

    with patch.object(gym, 'make', make):
        observer.collect(observer.ENTRIES['ownership'], args.out,
                         ['--target_config', str(args.target_config.resolve()), *forwarded])


if __name__ == '__main__':
    main()
