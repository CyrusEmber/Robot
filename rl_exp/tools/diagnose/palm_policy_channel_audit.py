# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Inspect candidate action authority and replay existing nonzero targets without physics.

Builds the registered frozen configuration and an isolated current-candidate override.
Reuses recorded single-axis evidence for action-column reachability, not current-gain
load acceptance. Angles and target offsets are [rad], gain units [N*m/rad, N*m*s/rad].
This neither adopts an asset nor opens a policy channel in a training recipe.
"""
import argparse
import copy
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import numpy as np
import palm_spatial_runtime as wiring


def channels(cfg, names):
    """Resolve configured action selections against the bound actual joint names."""
    result = []
    for term_name, term in vars(cfg.actions).items():
        if term is None:
            continue
        selected = []
        if term.preserve_order:
            for pattern in term.joint_names:
                selected.extend(n for n in names if re.fullmatch(pattern, n))
        else:
            selected = [n for n in names if any(re.fullmatch(p, n) for p in term.joint_names)]
        assert len(selected) == len(set(selected)), 'overlapping action selectors'
        result.append(dict(term=term_name, selectors=list(term.joint_names), resolved=selected,
                           scale=term.scale, offset=term.offset, clip=term.clip,
                           preserve_order=term.preserve_order, use_default_offset=term.use_default_offset))
    flat = [n for group in result for n in group['resolved']]
    assert len(flat) == len(set(flat)), 'joint owned by multiple action groups'
    return result


def audit(tracking_path, tracking_hash, current_path, current_hash):
    assert wiring.binding.sha256_file(tracking_path) == tracking_hash
    assert wiring.binding.sha256_file(current_path) == current_hash
    tracking = json.loads(tracking_path.read_text(encoding='utf-8'))
    current = json.loads(current_path.read_text(encoding='utf-8'))
    assert tracking['completed'] and tracking['status'] == 'small_tracking_verified'
    assert current['completed'] and current['status'] == 'standing_force_observation_standing_failed'
    names = current['joint_names']
    assert len(names) == 30 and names == tracking['joint_names']
    assert set(tracking['action_names']) == set(current['action_names']) == set(names)
    assert len(current['action_names']) == len(tracking['action_names']) == len(names)
    manifest_path = Path(current['manifest'])
    tracking_manifest = Path(tracking['tracking_manifest'])
    assert wiring.binding.sha256_file(manifest_path) == current['manifest_sha256']
    assert wiring.binding.sha256_file(tracking_manifest) == tracking['tracking_manifest_sha256']
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    old_manifest = json.loads(tracking_manifest.read_text(encoding='utf-8'))
    assert manifest['sha256']['urdf'] == old_manifest['sha256']['urdf']
    for doc in (manifest, old_manifest):
        for field in ('urdf', 'target'):
            assert wiring.binding.sha256_file(Path(doc['target_binding'][field])) == doc['sha256'][field]
    import rl_exp.tasks
    from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg
    frozen = resolve_task_cfg(wiring.REGISTERED_TASK)
    candidate = copy.deepcopy(frozen)
    target = wiring.obs_protocol.load_diagnostic_target(manifest_path, candidate, wiring.REGISTERED_TASK)
    assert set(target['joint_names']) == set(names)
    candidate_channels = channels(candidate, names)
    assert set(n for group in candidate_channels for n in group['resolved']) == set(names)
    for group in candidate_channels:
        assert group['scale'] == 1. and group['offset'] == 0. and group['clip'] is None
        assert group['preserve_order'] and group['use_default_offset']
    assert candidate.scene.robot.init_state.joint_pos == {n: 0. for n in names}
    carried = []
    for actuator in candidate.scene.robot.actuators.values():
        for name in actuator.joint_names_expr:
            i = names.index(name)
            assert np.float32(actuator.stiffness[name]) == current['readbacks']['kp'][i]
            assert np.float32(actuator.damping[name]) == current['readbacks']['kd'][i]
            carried.append(name)
    assert len(carried) == len(names) and set(carried) == set(names)
    formal_target = wiring.obs_protocol.load_diagnostic_target(None, copy.deepcopy(frozen), wiring.REGISTERED_TASK)
    formal_names = [j.get('name') for j in ET.parse(formal_target['urdf']).getroot().findall('joint')
                    if j.get('type') != 'fixed']
    formal_channels = channels(frozen, formal_names)
    old_on_new = channels(frozen, names)
    cases = {case['joint']: case for case in tracking['cases']}
    assert len(cases) == len(names) and set(cases) == set(names)
    measured = []
    max_target_error = 0.
    for name in names:
        path = tracking_path.parent/(name+'.json')
        data = json.loads(path.read_text(encoding='utf-8'))
        assert data['summary'] == cases[name] and cases[name]['passed']
        samples = data['samples']
        assert len(samples) == 1200
        desired = np.asarray([s['target_rad'] for s in samples])
        actual_targets = np.asarray([s['backend_drive_targets']['position_rad'] for s in samples])
        actual_velocity_targets = np.asarray([s['backend_drive_targets']['velocity_rad_s'] for s in samples])
        q = np.asarray([s['q_rad'] for s in samples])
        assert desired.shape == actual_targets.shape == q.shape == (1200, 30)
        assert all(np.isfinite(a).all() for a in (desired, actual_targets, actual_velocity_targets, q))
        assert all(s['backend_drive_targets']['joint_names'] == names for s in samples)
        assert np.allclose(actual_targets, desired, atol=1e-8, rtol=1e-6)
        assert np.all(actual_velocity_targets == 0)
        i = names.index(name)
        other = [j for j in range(len(names)) if j != i]
        assert np.all(desired[:, other] == 0)
        peak = int(np.argmax(abs(desired[:, i])))
        command = float(desired[peak, i])
        assert abs(command) == .02 and command*q[peak, i] > 0
        assert cases[name]['entity_fk_max_error'] < 1e-5
        max_target_error = max(max_target_error, float(abs(actual_targets-desired).max()))
        measured.append(dict(joint=name, case_sha256=wiring.binding.sha256_file(path),
                             nonzero_target_rad=command, q_at_target_peak_rad=float(q[peak, i]),
                             source_gain_scope='historical fixed-base no-gravity case; not current loaded precision',
                             current_kp=current['readbacks']['kp'][i], current_kd=current['readbacks']['kd'][i]))
    return dict(status='candidate_channels_replayed_not_training_adoption', physics_runs_started=0,
                task=wiring.REGISTERED_TASK, tracking_report_sha256=tracking_hash, current_report_sha256=current_hash,
                manifest_sha256=current['manifest_sha256'], current_urdf_sha256=manifest['sha256']['urdf'],
                frozen_asset=str(frozen.scene.robot.spawn.usd_path), candidate_asset=target['target'],
                frozen_action_count=sum(len(g['resolved']) for g in formal_channels),
                candidate_action_count=sum(len(g['resolved']) for g in candidate_channels),
                frozen_channels=formal_channels, candidate_channels=candidate_channels,
                frozen_selectors_on_candidate=old_on_new,
                missing_if_only_asset_replaced=[n for n in names if n not in {n for g in old_on_new for n in g['resolved']}],
                nonzero_target_max_readback_error_rad=max_target_error, joints=measured,
                boundary='Diagnostic reachability only; formal role permissions, obs semantics, speed anomaly, integration review and training evaluation remain open')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tracking_report', type=Path, required=True)
    parser.add_argument('--approved_tracking_sha256', required=True)
    parser.add_argument('--current_report', type=Path, required=True)
    parser.add_argument('--approved_current_sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert args.out.parent.is_dir() and not args.out.exists()
    result = audit(args.tracking_report.resolve(), args.approved_tracking_sha256,
                   args.current_report.resolve(), args.approved_current_sha256)
    wiring.write_json(args.out, result)
    print('POLICY_CHANNEL_AUDIT_OK', result['candidate_action_count'], 'candidate,',
          result['frozen_action_count'], 'frozen; missing with asset-only replacement:',
          len(result['missing_if_only_asset_replaced']))
