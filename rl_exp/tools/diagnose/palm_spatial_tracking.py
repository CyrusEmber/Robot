# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Bounded fixed-base spatial PD tracking through the registered action manager.

Default: no gravity or support claim. --level_leg_plan tests LF self-weight with the
base fixed and other joints constrained at neutral. Angles [rad], time [s], force [N], torque [N*m].
"""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import shutil
import sys
import traceback
import xml.etree.ElementTree as ET

import numpy as np
import palm_spatial_runtime as wiring


SETTINGS = dict(frequency_hz=1., damping_ratio=1., amplitude_rad=.02, ramp_s=2.,
                hold_s=1., dt_s=.005, max_error_rad=.012, hold_error_rad=.002,
                max_other_joint_rad=.01, stop_position_rad=.1, stop_contact_n=1.,
                max_full_runs=2, velocity_target='zero')

LEVEL_SETTINGS = dict(settle_s=5., fixture_half_range_rad=1e-6, level_tolerance=1e-5,
                      max_absolute_error_rad=.1, stop_absolute_error_rad=.35)


def _target(t, amplitude):
    ramp, hold = SETTINGS['ramp_s'], SETTINGS['hold_s']
    if t <= ramp:
        s = t / ramp
    elif t <= ramp + hold:
        return amplitude
    elif t <= 2*ramp + hold:
        s = (2*ramp + hold - t) / ramp
    else:
        return 0.
    return amplitude * (10*s**3 - 15*s**4 + 6*s**5)


def _verdict(q, target, axis, times):
    axis = np.atleast_1d(axis)
    error = np.abs(q[:, axis] - target[:, axis])
    plateau = (times >= SETTINGS['ramp_s'] + .8*SETTINGS['hold_s']) & (times <= SETTINGS['ramp_s'] + SETTINGS['hold_s'])
    final = times >= 2*SETTINGS['ramp_s'] + 1.8*SETTINGS['hold_s']
    other = np.delete(q, axis, axis=1)
    values = dict(max_error_rad=float(error.max()), plateau_error_rad=float(error[plateau].max()),
                  final_error_rad=float(error[final].max()), max_other_joint_rad=float(np.abs(other).max()))
    values['passed'] = (values['max_error_rad'] <= SETTINGS['max_error_rad']
                        and values['plateau_error_rad'] <= SETTINGS['hold_error_rad']
                        and values['final_error_rad'] <= SETTINGS['hold_error_rad']
                        and values['max_other_joint_rad'] <= SETTINGS['max_other_joint_rad'])
    return values


def _entity_snapshot(robot, model):
    from palm_spatial_inertia import _rotation, csc
    names = list(robot.joint_names)
    q = robot.data.joint_pos.torch[0].cpu().numpy().copy()
    actors = robot.data.body_link_pose_w.torch[0].cpu().numpy().copy()
    actual = {}
    for name, pose in zip(robot.body_names, actors):
        transform = np.eye(4)
        transform[:3, :3], transform[:3, 3] = _rotation(pose[3:]), pose[:3]
        actual[name] = transform
    root = actual['base_link']
    errors = {n: float(abs(actual[n] - root @ csc.fk(model['joints'], n, dict(zip(names, q)))).max())
              for n in robot.body_names}
    assert max(errors.values()) < 1e-5, 'actual actor/FK mismatch'
    return dict(joint_names=names, q_rad=q.tolist(), body_names=list(robot.body_names),
                actor_poses_xyzw=actors.tolist(), actor_fk_max_error=errors)


def _level_verdict(q, target, axes, times, baseline, level_errors):
    relative = _verdict(q-baseline, target, axes, times)
    relative['max_absolute_error_rad'] = float(abs(q[:, axes]-target[:, axes]).max())
    relative['max_chest_level_error'] = float(max(level_errors))
    relative['passed'] = bool(relative['passed'] and relative['max_absolute_error_rad'] <= LEVEL_SETTINGS['max_absolute_error_rad']
                             and relative['max_chest_level_error'] <= LEVEL_SETTINGS['level_tolerance'])
    return relative


def _level_fixture(document, out, plan_path):
    from pxr import Usd, UsdPhysics
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    assert plan['leg'] == 'lf' and 'keyframes' not in plan, 'only the original single-leg pose is accepted'
    assert wiring.binding.sha256_file(Path(plan['pose_report'])) == plan['pose_report_sha256']
    assert set(plan['target_q_rad']) == set(document['target_binding']['joint_names'])
    old_usd, old_urdf = Path(document['target']), Path(document['urdf'])
    assert wiring.binding.sha256_file(old_usd) == document['sha256']['target']
    assert wiring.binding.sha256_file(old_urdf) == wiring.URDF_HASH
    stage = Usd.Stage.Open(str(old_usd))
    constrained = []
    for prim in stage.Traverse():
        if prim.IsA(UsdPhysics.RevoluteJoint) and not prim.GetName().startswith('lf_'):
            joint = UsdPhysics.RevoluteJoint(prim)
            limit = np.degrees(LEVEL_SETTINGS['fixture_half_range_rad'])
            joint.GetLowerLimitAttr().Set(-float(limit))
            joint.GetUpperLimitAttr().Set(float(limit))
            constrained.append(prim.GetName())
    assert len(constrained) == 25
    (out/'palm_spatial.usda').write_text(stage.GetRootLayer().ExportToString(), encoding='utf-8')
    shutil.copyfile(old_urdf, out/'palm_spatial.urdf')
    shutil.copytree(old_usd.parent/'meshes', out/'meshes')
    for key, filename in (('target', 'palm_spatial.usda'), ('urdf', 'palm_spatial.urdf')):
        document[key] = document['target_binding'][key] = str(out/filename)
        document['sha256'][key] = wiring.binding.sha256_file(out/filename)
    document['config']['scene.robot.spawn.rigid_props.disable_gravity'] = False
    document['level_fixture'] = dict(constrained_joints=constrained, settings=LEVEL_SETTINGS,
                                    original_manifest_target=str(old_usd), original_urdf_limits_retained=True,
                                    scope='USD fixture ranges only; fixed base at z=2m; LF self-weight, no ground support')
    return plan


def _fresh_inputs(args):
    from types import SimpleNamespace as NS
    from palm_spatial_inertia import _validate_inputs, _comparison
    assert args.all_joints, 'fresh inertia requires all_joints'
    assert not any(getattr(args, n, None) for n in (
        'combined', 'gain_reference', 'level_leg_plan', 'self_weight_joint',
        'settle_video', 'all_joints_video', 'free_base_video', 'video_path', 'enable_cameras'))
    assert getattr(args, 'wrist_frequency_hz', 1.) == 1.
    assert wiring.binding.sha256_file(args.inertia_report) == args.approved_inertia_sha256, 'inertia approval mismatch'
    reference = json.loads(args.inertia_report.read_text(encoding='utf-8'))
    assert reference['completed'] and reference['status'] == 'authored_inertia_and_mass_matrix_verified'
    approvals = reference['approvals']
    def approved_path(key):
        matches = [Path(p) for p, digest in reference['input'].items() if digest == approvals[key]]
        assert len(matches) == 1, 'approval input must be unique'
        return matches[0]
    reset, manifest, pose, _, fresh = _validate_inputs(NS(
        reset_report=approved_path('reset_report_sha256'), pose_report=approved_path('pose_report_sha256'),
        approved_reset_sha256=approvals['reset_report_sha256'], approved_pose_sha256=approvals['pose_report_sha256'],
        out=args.out, repair_inertia=False))
    assert fresh and manifest.resolve() == Path(reference['replay_manifest']).resolve()
    assert wiring.binding.sha256_file(manifest) == reference['replay_manifest_sha256'] == reset['replay_manifest_sha256']
    source = json.loads(manifest.read_text(encoding='utf-8'))
    names = reference['snapshots'][0]['joint_names']
    assert len(names) == len(set(names)) == 30 and set(names) == set(source['target_binding']['joint_names'])
    snapshots = reference['snapshots']
    assert len(snapshots) == 2 and {s['label'] for s in snapshots} == {'neutral', 'existing_c_0.25'}
    for snapshot in snapshots:
        assert snapshot['joint_names'] == names and snapshot['runtime_fixed_base']
        assert len(snapshot['body_names']) == len(set(snapshot['body_names'])) == 31
        assert set(snapshot['body_names']) == {'base_link'} | {n.removesuffix('_joint') for n in names}
        matrix = np.asarray(snapshot['mass_matrix'])
        assert matrix.shape == (30, 30) and np.isfinite(matrix).all()
        assert _comparison(matrix, matrix.T)['within_roundoff_budget'] and np.linalg.eigvalsh(matrix).min() > 0
        assert all(snapshot['mass_matrix_checks'][k]['within_roundoff_budget'] for k in ('urdf', 'usd', 'raw_actor'))
        assert snapshot['actor_fk_max_error_m_or_rotation'] < 1e-5
        q = np.asarray(snapshot['q_rad'])
        expected = np.zeros(30) if snapshot['label'] == 'neutral' else np.array([pose['q_rad'][n] for n in names])
        assert q.shape == (30,) and np.isfinite(q).all() and abs(q-expected).max() < 1e-5
    return reference


def _tracking_cases(names, all_joints):
    cases = list(names) if all_joints else [
        wiring.joint_names.joint_name(leg, root) for leg in wiring.joint_names.LEGS
        for root in wiring.joint_names.roots_of(wiring.joint_names.PALM_SPATIAL_NAMING, leg)]
    assert len(cases) == len(set(cases)) == (30 if all_joints else 20)
    return cases


def _drive_targets(robot, backend, desired):
    from palm_spatial_inertia import _comparison
    position = backend(robot.root_view.get_dof_position_targets()).copy()
    velocity = backend(robot.root_view.get_dof_velocity_targets()).copy()
    checks = dict(position=_comparison(position, desired), velocity=_comparison(velocity, np.zeros_like(desired)))
    assert all(c['within_roundoff_budget'] for c in checks.values()), 'backend Drive target mismatch'
    return dict(joint_names=list(robot.joint_names), position_rad=position.tolist(), velocity_rad_s=velocity.tolist(), checks=checks)


def _motion_evidence(entities, commanded, model):
    assert len(entities) == 3 and [e['t_s'] for e in entities] == [0., 2.9, 5.9]
    neutral, plateau = entities[:2]
    motion = {}
    for name in commanded:
        child = model['joints'][name]['child']
        index = neutral['body_names'].index(child)
        delta = float(abs(np.array(plateau['actor_poses_xyzw'][index])-neutral['actor_poses_xyzw'][index]).max())
        assert delta > 0., 'commanded child actor did not move: ' + child
        motion[child] = delta
    return motion


def _fresh_self_check(args):
    from unittest.mock import patch
    _fresh_inputs(args)
    for changes in ({'approved_inertia_sha256': '0'*64}, {'all_joints': False}, {'combined': True}, {'gain_reference': args.inertia_report}):
        candidate = copy.copy(args)
        vars(candidate).update(changes)
        try:
            _fresh_inputs(candidate)
        except (AssertionError, ValueError):
            pass
        else:
            raise AssertionError('invalid fresh input accepted')
    reference = json.loads(args.inertia_report.read_text(encoding='utf-8'))
    names = reference['snapshots'][0]['joint_names']
    cases = _tracking_cases(names, args.all_joints)
    assert cases == names and all(n in cases for n in names if n.startswith(('chest_', 'neck_', 'tail')))
    times = np.arange(1, 1201)*SETTINGS['dt_s']
    for axis in range(30):
        desired = np.zeros((1200, 30))
        desired[:, axis] = [_target(t, .02) for t in times]
        assert _verdict(desired, desired, axis, times)['passed']
        assert not _verdict(np.zeros_like(desired), desired, axis, times)['passed']
        assert not _verdict(np.roll(desired, 1, axis=1), desired, axis, times)['passed']
    # Exercise real input branches with altered JSON reads; approved artifacts stay untouched.
    original = Path.read_text
    for mutate in (lambda r: r['snapshots'][0]['mass_matrix'][0].__setitem__(0, -1.),
                   lambda r: r['snapshots'][1]['joint_names'].__setitem__(0, 'missing'),
                   lambda r: r['snapshots'][0]['mass_matrix_checks']['urdf'].update(within_roundoff_budget=False)):
        broken = copy.deepcopy(reference)
        mutate(broken)
        def read(path, *a, **kw):
            return json.dumps(broken) if path.resolve() == args.inertia_report.resolve() else original(path, *a, **kw)
        with patch.object(Path, 'read_text', read):
            try:
                _fresh_inputs(args)
            except (AssertionError, ValueError):
                pass
            else:
                raise AssertionError('invalid matrix/name/check accepted')
    from types import SimpleNamespace as NS
    position, velocity = np.full(30, .02), np.zeros(30)
    robot = NS(joint_names=names, root_view=NS(get_dof_position_targets=lambda: position,
                                             get_dof_velocity_targets=lambda: velocity))
    _drive_targets(robot, lambda x: x, position.copy())
    for actual in (np.zeros(30), np.full(30, np.nan), np.full(29, .02)):
        with patch.object(robot.root_view, 'get_dof_position_targets', return_value=actual):
            try:
                _drive_targets(robot, lambda x: x, position)
            except AssertionError:
                pass
            else:
                raise AssertionError('invalid actual Drive target accepted')
    # Child actor motion is checked independently of FK generation.
    model = {'joints': {'hinge': {'child': 'tip'}}}
    entities = [dict(t_s=t, body_names=['tip'], actor_poses_xyzw=[[0., 0., 0., 0., 0., 0., 1.]]) for t in (0., 2.9, 5.9)]
    entities[1]['actor_poses_xyzw'][0][3] = .01
    _motion_evidence(entities, ['hinge'], model)
    entities[1]['actor_poses_xyzw'][0][3] = 0.
    try:
        _motion_evidence(entities, ['hinge'], model)
    except AssertionError:
        pass
    else:
        raise AssertionError('static child actor accepted')
    print('SPATIAL_TRACKING_FRESH_INPUT_CHECK_OK')


def _self_check():
    assert _target(0, .02) == _target(6, .02) == 0
    assert _target(2, .02) == _target(3, .02) == .02
    assert abs(_target(1, .02) - .01) < 1e-12
    times = np.arange(1, 1201)*.005
    target = np.zeros((1200, 2))
    target[:, 0] = [_target(t, .02) for t in times]
    assert _verdict(target, target, 0, times)['passed']
    assert not _verdict(np.zeros_like(target), target, 0, times)['passed']
    assert not _verdict(target[:, ::-1], target, 0, times)['passed']
    combined = np.column_stack((target[:, 0], -target[:, 0], target[:, 1]))
    assert _verdict(combined, combined, [0, 1], times)['passed']
    assert not _verdict(np.zeros_like(combined), combined, [0, 1], times)['passed']
    baseline = np.array([.03, 0.])
    level = np.zeros(len(times))
    assert _level_verdict(target+baseline, target, [0], times, baseline, level)['passed']
    assert not _level_verdict(np.tile(baseline, (len(times), 1)), target, [0], times, baseline, level)['passed']
    assert not _level_verdict(target+baseline, target, [0], times, baseline, level+.001)['passed']
    assert not _level_verdict(target+baseline+.2, target, [0], times, baseline+.2, level)['passed']
    print('SPATIAL_TRACKING_SELF_CHECK_OK')


def _gravity_design(reference, urdf):
    from palm_spatial_inertia import csc
    model = csc.load_urdf(urdf)
    names = reference['snapshots'][0]['joint_names']
    links = ET.parse(urdf).getroot().findall('link')
    masses = {l.get('name'): float(l.find('inertial/mass').get('value')) for l in links}
    centers = {l.get('name'): np.fromstring(l.find('inertial/origin').get('xyz'), sep=' ') for l in links}
    chains = {n: csc.chain_up(model['joints'], n) for n in masses}
    poses = [{}] + [{n: a} for n in names for a in (-.02, .02)]
    moments = []
    for q in poses:
        frames = {n: csc.fk(model['joints'], n, q) for n in masses}
        com = {n: frames[n][:3, :3] @ centers[n] + frames[n][:3, 3] for n in masses}
        row = []
        for n in names:
            spec = model['joints'][n]
            frame = frames[spec['child']]
            axis = frame[:3, :3] @ spec['axis']
            axis /= np.linalg.norm(axis)
            row.append(sum(float(axis @ np.cross(com[l]-frame[:3, 3], [0., 0., -9.81*masses[l]]))
                           for l in masses if n in chains[l]))
        moments.append(row)
    moments = np.asarray(moments)
    inertia = np.diag(next(s['mass_matrix'] for s in reference['snapshots'] if s['label'] == 'neutral'))
    load = np.abs(moments).max(axis=0)
    kp = np.maximum(inertia*(2*math.pi)**2, load/.03)
    kd = 2*np.sqrt(inertia*kp)
    chest = names.index('chest_pitch_joint')
    assert load[chest] < 280. and moments[0, chest] != 0
    return dict(joint_names=names, sampled_gravity_torque_nm=moments.tolist(),
                max_gravity_torque_nm=load.tolist(), neutral_inertia_diagonal=inertia.tolist(),
                kp=kp.tolist(), kd=kd.tolist(), gravity_m_s2=[0., 0., -9.81], static_error_scale_rad=.03,
                subtree_mass_kg={n: sum(masses[l] for l in masses if n in chains[l]) for n in names},
                chest_amplitude_rad=float(-np.sign(moments[0, chest])*.02),
                scope='fixed-root downstream self-weight at neutral and single-axis +/-0.02 rad; not contact support')


def _self_weight_cases(names):
    cases = {n: [n] for n in names if n != 'chest_pitch_joint'}
    for prefix in ('lf_', 'rf_', 'rl_', 'rr_', 'neck_', 'tail'):
        selected = [n for n in names if n.startswith(prefix)]
        assert len(selected) == (5 if prefix in ('lf_', 'rf_', 'rl_', 'rr_') else 2 if prefix == 'neck_' else 6)
        cases[prefix.rstrip('_') + '_combined'] = selected
    assert len(cases) == 35 and set(n for group in cases.values() for n in group) == set(names)-{'chest_pitch_joint'}
    return cases


def _self_weight_precision_only(verdict):
    """Identify a hold-precision-only failure without relaxing any verdict."""
    return bool(not verdict['passed'] and verdict['settle_drift_rad'] <= .002
                and verdict['settle_absolute_error_rad'] <= .1
                and verdict['max_absolute_error_rad'] <= .1
                and len(verdict['directions']) == 2
                and all(d['max_error_rad'] <= SETTINGS['max_error_rad']
                        and d['final_error_rad'] <= SETTINGS['hold_error_rad']
                        and d['max_other_joint_rad'] <= SETTINGS['max_other_joint_rad']
                        and np.isfinite(d['plateau_error_rad'])
                        for d in verdict['directions'])
                and any(d['plateau_error_rad'] > SETTINGS['hold_error_rad']
                        for d in verdict['directions']))


def _self_weight_axes_resume(args, cases, reference):
    """Validate the completed prefix; select only the remaining 17 single axes."""
    path = args.resume_self_weight
    assert path and args.approved_resume_sha256, 'continuation needs approved report'
    assert wiring.binding.sha256_file(path) == args.approved_resume_sha256, 'continuation approval mismatch'
    previous = json.loads(path.read_text(encoding='utf-8'))
    assert previous['completed'] and previous['status'] == 'self_weight_suite_failed'
    assert previous['stage'] == 'completed' and 'error' not in previous
    assert previous['planned_cases'] == cases and previous['retry_allowed'] is False
    assert previous['design']['joint_names'] == reference['snapshots'][0]['joint_names']
    original_args = copy.copy(args)
    original_args.continue_self_weight_axes = False
    original_args.resume_self_weight = Path(previous['resume']['report'])
    original_args.approved_resume_sha256 = previous['resume']['report_sha256']
    original, _ = _self_weight_resume(original_args, cases, reference)
    assert original == previous['resume'], 'original two-case recovery changed'
    first = json.loads(original_args.resume_self_weight.read_text(encoding='utf-8'))
    assert previous['input'] == first['input'] and previous['design'] == first['design']
    assert previous['settings'] == first['settings'] and previous['chest_effort_limit_nm'] == 280.
    assert previous['steps_completed'] == 10*3400 and len(previous['cases']) == 10
    names = previous['joint_names']
    assert names == previous['design']['joint_names']
    assert list(previous['readbacks']['effort_caps']) == list(first['readbacks']['effort_caps'])
    hashes = {}
    for i, (item, expected) in enumerate(zip(previous['cases'], list(cases)[2:12])):
        assert item['case'] == expected and item['commanded_joints'] == cases[expected]
        assert item['samples_completed'] == 3400
        sample_path = path.parent/(expected+'.json')
        data = json.loads(sample_path.read_text(encoding='utf-8'))
        assert data['summary'] == item
        verdict = _self_weight_verdict(data['samples'], names, cases[expected])
        assert verdict == {k: v for k, v in item.items()
                           if k not in ('case', 'commanded_joints', 'samples_completed')}
        assert verdict['passed'] if i < 9 else _self_weight_precision_only(verdict)
        rows = data['samples']
        q = np.asarray([r['q_rad'] for r in rows])
        desired = np.asarray([r['target_rad'] for r in rows])
        v = np.asarray([r['velocity_rad_s'] for r in rows])
        contact = np.asarray([r['max_contact_n'] for r in rows])
        assert np.isfinite(v).all() and np.isfinite(contact).all()
        assert abs(q).max() <= .35 and abs(q-desired).max() <= .35
        assert np.all(abs(v) < np.asarray(previous['readbacks']['velocity_caps'])*.5)
        assert contact.max() <= 1. and len(data['entities']) == 5
        hashes[str(sample_path)] = wiring.binding.sha256_file(sample_path)
    assert previous['verdict'] == {k: v for k, v in previous['cases'][-1].items()
                                  if k not in ('case', 'commanded_joints', 'samples_completed')}
    for p, h in previous['input'].items():
        assert wiring.binding.sha256_file(Path(p)) == h
    assert wiring.binding.sha256_file(path.parent/'source.py') == previous['code_sha256']
    assert wiring.binding.sha256_file(path.parent/'tracking_manifest.json') == previous['tracking_manifest_sha256']
    completed = original['cases'] + previous['cases']
    assert [c['case'] for c in completed] == list(cases)[:12]
    remaining = {n: group for n, group in cases.items()
                 if n.endswith('_joint') and n not in {c['case'] for c in completed}}
    assert len(remaining) == 17 and next(iter(remaining)) == 'rr_hip_twist_joint'
    return dict(report=str(path), report_sha256=args.approved_resume_sha256, cases=completed,
                files_sha256=hashes, source_sha256=previous['code_sha256'],
                tracking_manifest_sha256=previous['tracking_manifest_sha256'],
                deferred_cases=[n for n in cases if n.endswith('_combined')],
                policy='17 remaining axes only; preserve precision failures; stop all other failures'), remaining


def _self_weight_gain_design(design, selected):
    """Apply the single approved gain increment to the eight failed axes only."""
    assert len(selected) == 8 and set(selected) <= set(design['joint_names'])
    changed = copy.deepcopy(design)
    for i, name in enumerate(design['joint_names']):
        if name in selected:
            changed['kp'][i] *= 1.2
            changed['kd'][i] *= math.sqrt(1.2)
    return changed


def _self_weight_gain_resume(args, cases, reference):
    """Re-read all original axes and select only hold-precision failures."""
    path = args.resume_self_weight
    assert path and wiring.binding.sha256_file(path) == args.approved_resume_sha256
    previous = json.loads(path.read_text(encoding='utf-8'))
    assert previous['completed'] and previous['selected_cases_completed']
    assert previous['status'] == 'self_weight_axes_completed_precision_unmet'
    assert previous['steps_completed'] == previous['planned_max_steps'] == 57800
    assert len(previous['cases']) == 17 and not previous['retry_allowed']
    seed = copy.copy(args)
    seed.precision_gain_trial = False
    seed.continue_self_weight_axes = True
    seed.resume_self_weight = Path(previous['resume']['report'])
    seed.approved_resume_sha256 = previous['resume']['report_sha256']
    original, remaining = _self_weight_resume(seed, cases, reference)
    assert original == previous['resume'] and previous['selected_cases'] == remaining
    prior = json.loads(seed.resume_self_weight.read_text(encoding='utf-8'))
    assert previous['design'] == prior['design'] and previous['settings'] == prior['settings']
    assert previous['input'] == prior['input'] and previous['readbacks'] == prior['readbacks']
    hashes = {}
    for summary, expected in zip(previous['cases'], remaining):
        assert summary['case'] == expected and summary['samples_completed'] == 3400
        sample_path = path.parent/(expected+'.json')
        data = json.loads(sample_path.read_text(encoding='utf-8'))
        assert data['summary'] == summary and summary['commanded_joints'] == [expected]
        verdict = _self_weight_verdict(data['samples'], previous['joint_names'], [expected])
        assert verdict == {k:v for k,v in summary.items()
                           if k not in ('case','commanded_joints','samples_completed')}
        assert verdict['passed'] or _self_weight_precision_only(verdict)
        q = np.asarray([r['q_rad'] for r in data['samples']])
        target = np.asarray([r['target_rad'] for r in data['samples']])
        velocity = np.asarray([r['velocity_rad_s'] for r in data['samples']])
        contact = np.asarray([r['max_contact_n'] for r in data['samples']])
        assert np.isfinite(velocity).all() and np.isfinite(contact).all()
        assert abs(q).max() <= .35 and abs(q-target).max() <= .35
        assert np.all(abs(velocity) < np.asarray(previous['readbacks']['velocity_caps'])*.5)
        assert contact.max() <= 1. and len(data['entities']) == 5
        hashes[str(sample_path)] = wiring.binding.sha256_file(sample_path)
    for p,h in previous['input'].items():
        assert wiring.binding.sha256_file(Path(p)) == h
    assert wiring.binding.sha256_file(path.parent/'source.py') == previous['code_sha256']
    assert wiring.binding.sha256_file(path.parent/'tracking_manifest.json') == previous['tracking_manifest_sha256']
    completed = original['cases']+previous['cases']
    assert len(completed) == 29 and [c['case'] for c in completed] == list(cases)[:29]
    selected = {c['case']: [c['case']] for c in completed if not c['passed']}
    assert set(selected) == {'rl_hip_twist_joint','rr_hip_twist_joint','rl_knee_joint','rr_knee_joint',
                             'lf_shoulder_twist_joint','rf_shoulder_twist_joint','lf_elbow_joint','rf_elbow_joint'}
    assert all(c['passed'] or _self_weight_precision_only(c) for c in completed)
    return dict(report=str(path),report_sha256=args.approved_resume_sha256,cases=completed,
                files_sha256=hashes,source_sha256=previous['code_sha256'],
                tracking_manifest_sha256=previous['tracking_manifest_sha256']), selected


def _self_weight_knee30_design(design):
    """Set only the left rear knee stiffness to 30 N*m/rad, retaining its damping ratio."""
    changed = copy.deepcopy(design)
    i = design['joint_names'].index('rl_knee_joint')
    changed['kp'][i] = 30.
    changed['kd'][i] *= math.sqrt(30./design['kp'][i])
    return changed


def _self_weight_knee30_resume(args, cases, reference):
    path = args.resume_self_weight
    assert path and wiring.binding.sha256_file(path) == args.approved_resume_sha256
    previous = json.loads(path.read_text(encoding='utf-8'))
    assert previous['completed'] and previous['selected_cases_completed']
    assert previous['status'] == 'self_weight_gain_trial_completed_precision_unmet'
    assert previous['steps_completed'] == previous['planned_max_steps'] == 27200
    assert len(previous['cases']) == 8 and previous['retry_allowed'] is False
    seed = copy.copy(args)
    seed.left_knee_kp30 = False
    seed.precision_gain_trial = True
    seed.resume_self_weight = Path(previous['resume']['report'])
    seed.approved_resume_sha256 = previous['resume']['report_sha256']
    original, selected = _self_weight_gain_resume(seed, cases, reference)
    assert original == previous['resume'] and selected == previous['selected_cases']
    baseline = json.loads(seed.resume_self_weight.read_text(encoding='utf-8'))
    assert previous['design'] == _self_weight_gain_design(baseline['design'], selected)
    assert previous['precision_gain_trial']['baseline_design'] == baseline['design']
    assert previous['settings'] == baseline['settings'] and previous['input'] == baseline['input']
    assert previous['joint_names'] == baseline['joint_names']
    for key,value in previous['readbacks'].items():
        if key in ('kp','kd'):
            assert np.array_equal(np.asarray(value), np.asarray(previous['design'][key],dtype=np.float32))
        else:
            assert value == baseline['readbacks'][key]
    hashes = {}
    for summary,expected in zip(previous['cases'],selected):
        assert summary['case'] == expected and summary['commanded_joints'] == [expected]
        assert summary['samples_completed'] == 3400
        sample = path.parent/(expected+'.json')
        data = json.loads(sample.read_text(encoding='utf-8'))
        assert data['summary'] == summary
        verdict = _self_weight_verdict(data['samples'], previous['joint_names'], [expected])
        assert verdict == {k:v for k,v in summary.items() if k not in ('case','commanded_joints','samples_completed')}
        assert _self_weight_precision_only(verdict)
        q = np.asarray([s['q_rad'] for s in data['samples']])
        target = np.asarray([s['target_rad'] for s in data['samples']])
        velocity = np.asarray([s['velocity_rad_s'] for s in data['samples']])
        contact = np.asarray([s['max_contact_n'] for s in data['samples']])
        assert np.isfinite(velocity).all() and np.isfinite(contact).all()
        assert abs(q).max() <= .35 and abs(q-target).max() <= .35
        assert np.all(abs(velocity) < np.asarray(previous['readbacks']['velocity_caps'])*.5)
        assert contact.max() <= 1. and len(data['entities']) == 5
        hashes[str(sample)] = wiring.binding.sha256_file(sample)
    for p,h in previous['input'].items():
        assert wiring.binding.sha256_file(Path(p)) == h
    assert wiring.binding.sha256_file(path.parent/'source.py') == previous['code_sha256']
    assert wiring.binding.sha256_file(path.parent/'tracking_manifest.json') == previous['tracking_manifest_sha256']
    return dict(report=str(path),report_sha256=args.approved_resume_sha256,cases=previous['cases'],
                files_sha256=hashes,source_sha256=previous['code_sha256'],
                tracking_manifest_sha256=previous['tracking_manifest_sha256']), {'rl_knee_joint':['rl_knee_joint']}


def _self_weight_calibrated_design(design, calibration):
    """Estimate local stiffness from measured incremental error, with 5% margin.

    The fitted e=A*k/(Kp+k) relation is a local prediction, not a full-ROM bound.
    Preserve each joint's damping ratio; leave already-passing joints unchanged.
    """
    assert len(calibration) == 8 and len({c['case'] for c in calibration}) == 8
    changed = copy.deepcopy(design)
    for case in calibration:
        assert _self_weight_precision_only(case)
        i = design['joint_names'].index(case['case'])
        error = max(d['plateau_error_rad'] for d in case['directions'])
        assert SETTINGS['hold_error_rad'] < error < SETTINGS['amplitude_rad']
        slope = design['kp'][i]*error/(SETTINGS['amplitude_rad']-error)
        minimum = slope*(SETTINGS['amplitude_rad']/SETTINGS['hold_error_rad']-1.)
        changed['kp'][i] = max(design['kp'][i], float(math.ceil(1.05*minimum)))
        changed['kd'][i] *= math.sqrt(changed['kp'][i]/design['kp'][i])
    return changed


def _self_weight_calibrated_resume(args, cases, reference):
    """Validate the latest knee trial and its full ancestry before calibrating."""
    path = args.resume_self_weight
    assert path and wiring.binding.sha256_file(path) == args.approved_resume_sha256
    previous = json.loads(path.read_text(encoding='utf-8'))
    assert previous['completed'] and previous['selected_cases_completed']
    assert previous['status'] == 'left_knee_kp30_precision_unmet'
    assert previous['steps_completed'] == previous['planned_max_steps'] == 3400
    assert len(previous['cases']) == 1 and previous['retry_allowed'] is False
    seed = copy.copy(args)
    seed.calibrate_precision = False
    seed.left_knee_kp30 = True
    seed.resume_self_weight = Path(previous['resume']['report'])
    seed.approved_resume_sha256 = previous['resume']['report_sha256']
    original, selected = _self_weight_knee30_resume(seed, cases, reference)
    assert original == previous['resume'] and selected == previous['selected_cases']
    baseline = json.loads(seed.resume_self_weight.read_text(encoding='utf-8'))
    assert previous['design'] == _self_weight_knee30_design(baseline['design'])
    assert previous['left_knee_kp30']['baseline_design'] == baseline['design']
    assert previous['settings'] == baseline['settings'] and previous['input'] == baseline['input']
    assert previous['joint_names'] == baseline['joint_names']
    for key, value in previous['readbacks'].items():
        if key in ('kp', 'kd'):
            assert np.array_equal(np.asarray(value), np.asarray(previous['design'][key], dtype=np.float32))
        else:
            assert value == baseline['readbacks'][key]
    sample = path.parent/'rl_knee_joint.json'
    data = json.loads(sample.read_text(encoding='utf-8'))
    summary = previous['cases'][0]
    assert data['summary'] == summary and summary['case'] == 'rl_knee_joint'
    assert summary['commanded_joints'] == ['rl_knee_joint'] and summary['samples_completed'] == 3400
    verdict = _self_weight_verdict(data['samples'], previous['joint_names'], ['rl_knee_joint'])
    assert verdict == {k: v for k, v in summary.items() if k not in ('case', 'commanded_joints', 'samples_completed')}
    assert _self_weight_precision_only(verdict)
    q = np.asarray([s['q_rad'] for s in data['samples']])
    target = np.asarray([s['target_rad'] for s in data['samples']])
    velocity = np.asarray([s['velocity_rad_s'] for s in data['samples']])
    contact = np.asarray([s['max_contact_n'] for s in data['samples']])
    assert np.isfinite(velocity).all() and np.isfinite(contact).all()
    assert abs(q).max() <= .35 and abs(q-target).max() <= .35
    assert np.all(abs(velocity) < np.asarray(previous['readbacks']['velocity_caps'])*.5)
    assert contact.max() <= 1. and len(data['entities']) == 5
    for p, h in previous['input'].items():
        assert wiring.binding.sha256_file(Path(p)) == h
    assert wiring.binding.sha256_file(path.parent/'source.py') == previous['code_sha256']
    assert wiring.binding.sha256_file(path.parent/'tracking_manifest.json') == previous['tracking_manifest_sha256']
    calibration = [summary if c['case'] == 'rl_knee_joint' else c for c in baseline['cases']]
    names = previous['joint_names']
    return dict(report=str(path), report_sha256=args.approved_resume_sha256, cases=previous['cases'],
                files_sha256={str(sample): wiring.binding.sha256_file(sample)},
                source_sha256=previous['code_sha256'], calibration_cases=calibration,
                tracking_manifest_sha256=previous['tracking_manifest_sha256']), {n: [n] for n in names}


def _self_weight_combinations_resume(args, cases, reference):
    """Revalidate the calibrated 30-axis run, then select only six groups."""
    path = args.resume_self_weight
    assert path and wiring.binding.sha256_file(path) == args.approved_resume_sha256
    previous = json.loads(path.read_text(encoding='utf-8'))
    assert previous['completed'] and previous['selected_cases_completed'] and previous['all_selected_cases_passed']
    assert previous['status'] == 'calibrated_precision_verified'
    assert previous['steps_completed'] == previous['planned_max_steps'] == 102000
    assert len(previous['cases']) == 30 and previous['retry_allowed'] is False
    seed = copy.copy(args)
    seed.calibrated_combinations = False
    seed.calibrate_precision = True
    seed.resume_self_weight = Path(previous['resume']['report'])
    seed.approved_resume_sha256 = previous['resume']['report_sha256']
    original, selected = _self_weight_calibrated_resume(seed, cases, reference)
    assert original == previous['resume'] and selected == previous['selected_cases']
    prior = json.loads(seed.resume_self_weight.read_text(encoding='utf-8'))
    assert previous['design'] == _self_weight_calibrated_design(prior['design'], original['calibration_cases'])
    assert previous['precision_calibration']['baseline_design'] == prior['design']
    assert previous['settings'] == prior['settings'] and previous['input'] == prior['input']
    assert previous['joint_names'] == prior['joint_names']
    for key, value in previous['readbacks'].items():
        if key in ('kp', 'kd'):
            assert np.array_equal(np.asarray(value), np.asarray(previous['design'][key], dtype=np.float32))
        else:
            assert value == prior['readbacks'][key]
    hashes = {}
    for summary, expected in zip(previous['cases'], selected):
        assert summary['case'] == expected and summary['commanded_joints'] == [expected]
        assert summary['samples_completed'] == 3400
        sample = path.parent/(expected+'.json')
        data = json.loads(sample.read_text(encoding='utf-8'))
        assert data['summary'] == summary
        verdict = _self_weight_verdict(data['samples'], previous['joint_names'], [expected])
        assert verdict == {k: v for k, v in summary.items() if k not in ('case', 'commanded_joints', 'samples_completed')}
        assert verdict['passed']
        q = np.asarray([s['q_rad'] for s in data['samples']])
        target = np.asarray([s['target_rad'] for s in data['samples']])
        velocity = np.asarray([s['velocity_rad_s'] for s in data['samples']])
        contact = np.asarray([s['max_contact_n'] for s in data['samples']])
        assert np.isfinite(velocity).all() and np.isfinite(contact).all()
        assert abs(q).max() <= .35 and abs(q-target).max() <= .35
        assert np.all(abs(velocity) < np.asarray(previous['readbacks']['velocity_caps'])*.5)
        assert contact.max() <= 1. and len(data['entities']) == 5
        hashes[str(sample)] = wiring.binding.sha256_file(sample)
    for p, h in previous['input'].items():
        assert wiring.binding.sha256_file(Path(p)) == h
    assert wiring.binding.sha256_file(path.parent/'source.py') == previous['code_sha256']
    assert wiring.binding.sha256_file(path.parent/'tracking_manifest.json') == previous['tracking_manifest_sha256']
    remaining = {n: group for n, group in cases.items() if n.endswith('_combined')}
    assert list(remaining) == ['lf_combined', 'rf_combined', 'rl_combined', 'rr_combined', 'neck_combined', 'tail_combined']
    return dict(report=str(path), report_sha256=args.approved_resume_sha256, cases=previous['cases'],
                files_sha256=hashes, source_sha256=previous['code_sha256'],
                tracking_manifest_sha256=previous['tracking_manifest_sha256']), remaining


def _self_weight_resume(args, cases, reference):
    if getattr(args, 'calibrated_combinations', False):
        return _self_weight_combinations_resume(args, cases, reference)
    if getattr(args, 'calibrate_precision', False):
        return _self_weight_calibrated_resume(args, cases, reference)
    if getattr(args, 'left_knee_kp30', False):
        return _self_weight_knee30_resume(args, cases, reference)
    if getattr(args, 'precision_gain_trial', False):
        return _self_weight_gain_resume(args, cases, reference)
    if getattr(args, 'continue_self_weight_axes', False):
        return _self_weight_axes_resume(args, cases, reference)
    path = getattr(args, 'resume_self_weight', None)
    approved = getattr(args, 'approved_resume_sha256', None)
    assert bool(path) == bool(approved), 'resume report and approval required together'
    if path is None:
        return {}, cases
    assert wiring.binding.sha256_file(path) == approved, 'resume approval mismatch'
    previous = json.loads(path.read_text(encoding='utf-8'))
    assert not previous['completed'] and previous['error'] == "FileExistsError(17, 'File exists')"
    assert previous['input'][str(args.inertia_report)] == args.approved_inertia_sha256
    assert previous['design']['joint_names'] == reference['snapshots'][0]['joint_names']
    assert previous['planned_cases'] == cases and previous['retry_allowed'] is False
    assert previous['settings'] == {**SETTINGS, 'max_full_runs': 1, 'settle_s': 5.,
        'max_absolute_error_rad': .1, 'settle_drift_rad': .002, 'stop_absolute_error_rad': .35}
    hashes = {}
    for item, expected in zip(previous['cases'], list(cases)):
        assert item['case'] == expected and item['passed'] and item['samples_completed'] == 3400
        sample_path = path.parent/(expected+'.json')
        data = json.loads(sample_path.read_text(encoding='utf-8'))
        assert data['summary'] == item
        assert _self_weight_verdict(data['samples'], previous['joint_names'], cases[expected]) == {
            k: v for k, v in item.items() if k not in ('case', 'commanded_joints', 'samples_completed')}
        hashes[str(sample_path)] = wiring.binding.sha256_file(sample_path)
    assert len(hashes) == len(previous['cases']) == 2
    for p, h in previous['input'].items():
        assert wiring.binding.sha256_file(Path(p)) == h
    assert wiring.binding.sha256_file(path.parent/'tracking_manifest.json') == previous['tracking_manifest_sha256']
    old_source = path.parent/'source.py'
    assert wiring.binding.sha256_file(old_source) == previous['code_sha256']
    remainder = {k: v for k, v in cases.items() if k not in {c['case'] for c in previous['cases']}}
    assert len(remainder) == 33
    return dict(report=str(path), report_sha256=approved, cases=previous['cases'],
                files_sha256=hashes, tracking_manifest_sha256=previous['tracking_manifest_sha256'],
                source_sha256=previous['code_sha256']), remainder


def _write_self_weight_case(out, result, summary):
    case = summary['case']
    wiring.write_json(out/(case+'.json'), dict(summary=summary, samples=result['samples'], entities=result['entities']))
    wiring.write_json(out/f'progress_{len(result["cases"]):02d}.json', {k: v for k, v in result.items() if k not in ('samples', 'entities')})


def _self_weight_verdict(rows, names, commanded):
    times = np.asarray([r['t_s'] for r in rows])
    q = np.asarray([r['q_rad'] for r in rows])
    desired = np.asarray([r['target_rad'] for r in rows])
    assert len(rows) in (2200, 3400) and q.shape == desired.shape == (len(rows), len(names))
    assert np.isfinite(q).all() and np.isfinite(desired).all()
    assert np.allclose(times, np.arange(1, len(rows)+1)*SETTINGS['dt_s'], atol=1e-12, rtol=0)
    baseline = q[999]
    settling = (times >= 4.8) & (times <= 5.)
    axes = [names.index(n) for n in commanded]
    directions = []
    for start in (5., 11.)[:1 if len(rows) == 2200 else 2]:
        active = (times > start) & (times <= start+6.)
        directions.append(_verdict(q[active]-baseline, desired[active], axes, times[active]-start))
    drift = float(np.ptp(q[settling], axis=0).max())
    static_error = float(np.abs(q[settling]).max())
    absolute = float(np.abs(q-desired).max())
    return dict(passed=bool(all(d['passed'] for d in directions) and drift <= .002 and static_error <= .1 and absolute <= .1),
                directions=directions, baseline_q_rad=baseline.tolist(), settle_drift_rad=drift,
                settle_absolute_error_rad=static_error, max_absolute_error_rad=absolute)


def _self_weight_self_check(args):
    _fresh_inputs(args)
    names = list(_fresh_inputs(args)['snapshots'][0]['joint_names'])
    cases = _self_weight_cases(names)
    assert set(n for n in cases if n.endswith('_joint')) == set(names)-{'chest_pitch_joint'}
    times = np.arange(1, 3401)*.005
    baseline = np.full(30, .03)
    for commanded in ([names[0]], cases['lf_combined'], cases['neck_combined'], cases['tail_combined']):
        target = np.zeros((3400, 30))
        for n in commanded:
            target[:, names.index(n)] = [_target(max(t-5., 0.), .02) if t <= 11. else _target(t-11., -.02) for t in times]
        def rows(q):
            return [dict(t_s=float(t), q_rad=a.tolist(), target_rad=b.tolist()) for t, a, b in zip(times, q, target)]
        assert _self_weight_verdict(rows(target+baseline), names, commanded)['passed']
        assert not _self_weight_verdict(rows(np.tile(baseline, (3400, 1))), names, commanded)['passed']
        assert not _self_weight_verdict(rows(-target+baseline), names, commanded)['passed']
        assert not _self_weight_verdict(rows(target+baseline+.2), names, commanded)['passed']
        broken = target+baseline
        broken[times > 11.] = baseline
        assert not _self_weight_verdict(rows(broken), names, commanded)['passed']
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        out = Path(directory)
        state = dict(samples=[], entities=[], cases=[])
        for label in ('first', 'second'):
            summary = dict(case=label, passed=True)
            state['cases'].append(summary)
            _write_self_weight_case(out, state, summary)
        assert (out/'progress_01.json').is_file() and (out/'progress_02.json').is_file()
        try:
            _write_self_weight_case(out, state, summary)
        except FileExistsError:
            pass
        else:
            raise AssertionError('case writer overwrote existing evidence')
    if getattr(args, 'resume_self_weight', None):
        resume, remaining = _self_weight_resume(args, cases, _fresh_inputs(args))
        expected = ((30, 6) if getattr(args, 'calibrated_combinations', False) else
                    (1, 30) if getattr(args, 'calibrate_precision', False) else
                    (8, 1) if getattr(args, 'left_knee_kp30', False) else
                    (29, 8) if getattr(args, 'precision_gain_trial', False) else
                    (12, 17) if getattr(args, 'continue_self_weight_axes', False) else (2, 33))
        assert (len(resume['cases']), len(remaining)) == expected
        if getattr(args, 'calibrated_combinations', False):
            assert list(remaining) == ['lf_combined', 'rf_combined', 'rl_combined', 'rr_combined', 'neck_combined', 'tail_combined']
            assert [len(v) for v in remaining.values()] == [5, 5, 5, 5, 2, 6]
            assert set(n for group in remaining.values() for n in group) == set(names)-{'chest_pitch_joint', 'chest_yaw_joint'}
        if getattr(args, 'calibrate_precision', False):
            previous = json.loads(args.resume_self_weight.read_text(encoding='utf-8'))
            design = previous['design']
            calibration = resume['calibration_cases']
            changed = _self_weight_calibrated_design(design, calibration)
            expected_kp = {'rl_hip_twist_joint': 62., 'rr_hip_twist_joint': 62.,
                           'lf_shoulder_twist_joint': 63., 'rf_shoulder_twist_joint': 63.,
                           'rl_knee_joint': 65., 'rr_knee_joint': 65., 'lf_elbow_joint': 65., 'rf_elbow_joint': 65.}
            for i, n in enumerate(names):
                assert changed['kp'][i] == expected_kp.get(n, design['kp'][i])
                assert changed['kd'][i] == design['kd'][i]*math.sqrt(changed['kp'][i]/design['kp'][i])
            assert design == previous['design'] and list(remaining) == names
        if getattr(args, 'left_knee_kp30', False):
            design = dict(joint_names=names,kp=[20.]*30,kd=[4.]*30)
            changed = _self_weight_knee30_design(design)
            for i,n in enumerate(names):
                assert changed['kp'][i] == (30. if n == 'rl_knee_joint' else 20.)
                assert changed['kd'][i] == 4.*(math.sqrt(1.5) if n == 'rl_knee_joint' else 1.)
            assert design['kp'] == [20.]*30 and list(remaining) == ['rl_knee_joint']
        if getattr(args, 'precision_gain_trial', False):
            design = dict(joint_names=names, kp=[float(i+1) for i in range(30)], kd=[float(i+2) for i in range(30)])
            changed = _self_weight_gain_design(design, remaining)
            for i,n in enumerate(names):
                assert changed['kp'][i] == design['kp'][i]*(1.2 if n in remaining else 1.)
                assert changed['kd'][i] == design['kd'][i]*(math.sqrt(1.2) if n in remaining else 1.)
            assert design['kp'] == [float(i+1) for i in range(30)]
    example = dict(passed=False, settle_drift_rad=0., settle_absolute_error_rad=.03,
                   max_absolute_error_rad=.04, directions=[dict(passed=False, max_error_rad=.005,
                   plateau_error_rad=.00276, final_error_rad=.00001, max_other_joint_rad=.001)]*2)
    assert _self_weight_precision_only(example)
    for field, value in (('max_error_rad', .02), ('final_error_rad', .003),
                         ('max_other_joint_rad', .02), ('plateau_error_rad', float('nan'))):
        broken = copy.deepcopy(example)
        broken['directions'][1][field] = value
        assert not _self_weight_precision_only(broken), field
    for field, value in (('settle_drift_rad', .003), ('settle_absolute_error_rad', .11),
                         ('max_absolute_error_rad', .11)):
        assert not _self_weight_precision_only({**example, field: value}), field
    print('SELF_WEIGHT_SUITE_CHECK_OK', len(cases), 'cases; bidirectional verdict and exclusive progress writer checked')


def _chest_verdict(rows, names):
    times = np.asarray([r['t_s'] for r in rows])
    q = np.asarray([r['q_rad'] for r in rows])
    desired = np.asarray([r['target_rad'] for r in rows])
    assert len(rows) == 2200 and np.isfinite(q).all() and np.isfinite(desired).all()
    baseline = q[np.flatnonzero(np.isclose(times, 5.))[-1]]
    settling = (times >= 4.8) & (times <= 5.)
    active = times > 5.
    relative = _verdict(q[active]-baseline, desired[active], names.index('chest_pitch_joint'), times[active]-5.)
    drift = float(np.ptp(q[settling], axis=0).max())
    static_error = float(np.abs(q[settling]).max())
    absolute = float(np.abs(q-desired).max())
    relative.update(baseline_q_rad=baseline.tolist(), settle_drift_rad=drift,
                    settle_absolute_error_rad=static_error, max_absolute_error_rad=absolute)
    relative['passed'] = bool(relative['passed'] and drift <= .002 and static_error <= .1 and absolute <= .1)
    return relative


def _chest_self_check(args):
    reference = _fresh_inputs(args)
    manifest = json.loads(Path(reference['replay_manifest']).read_text(encoding='utf-8'))
    design = _gravity_design(reference, Path(manifest['target_binding']['urdf']))
    names = design['joint_names']
    axis = names.index('chest_pitch_joint')
    times = np.arange(1, 2201)*.005
    target = np.zeros((2200, 30))
    target[:, axis] = [_target(max(t-5., 0.), design['chest_amplitude_rad']) for t in times]
    baseline = np.zeros(30)
    baseline[axis] = -.03*np.sign(design['chest_amplitude_rad'])
    def samples(q):
        return [dict(t_s=float(t), q_rad=a.tolist(), target_rad=b.tolist()) for t, a, b in zip(times, q, target)]
    assert _chest_verdict(samples(target+baseline), names)['passed']
    assert not _chest_verdict(samples(np.tile(baseline, (2200, 1))), names)['passed']
    assert not _chest_verdict(samples(-target+baseline), names)['passed']
    assert not _chest_verdict(samples(target+baseline+.2), names)['passed']
    assert design['max_gravity_torque_nm'][axis] > 80.
    assert abs(design['subtree_mass_kg']['chest_pitch_joint']-39.9396) < 1e-5
    print('CHEST_280_SELF_CHECK_OK', json.dumps(design), flush=True)


def _run_chest280(args):
    suite = bool(getattr(args, 'self_weight_suite', False))
    assert not (suite and args.chest_self_weight_280), 'self-weight modes are exclusive'
    reference = _fresh_inputs(args)
    manifest = Path(reference['replay_manifest'])
    wiring.check_registered_manifest(manifest, measured_order=False)
    original = json.loads(manifest.read_text(encoding='utf-8'))
    design = _gravity_design(reference, Path(original['target_binding']['urdf']))
    planned = _self_weight_cases(design['joint_names']) if suite else {}
    resume, remaining = _self_weight_resume(args, planned, reference) if suite else ({}, {})
    knee30 = bool(getattr(args, 'left_knee_kp30', False))
    calibrated = bool(getattr(args, 'calibrate_precision', False))
    combinations = bool(getattr(args, 'calibrated_combinations', False))
    if combinations:
        planned = copy.deepcopy(remaining)
    if calibrated:
        planned = {n: [n] for n in design['joint_names']}
    if resume:
        prior = json.loads(Path(resume['report']).read_text(encoding='utf-8'))
        if combinations:
            design = copy.deepcopy(prior['design'])
        elif calibrated:
            seed = json.loads(Path(prior['resume']['report']).read_text(encoding='utf-8'))
            assert seed['precision_gain_trial']['baseline_design'] == design
            design = copy.deepcopy(prior['design'])
        elif knee30:
            assert prior['precision_gain_trial']['baseline_design'] == design
            design = copy.deepcopy(prior['design'])
        else:
            assert prior['design'] == design
    gain_trial = bool(getattr(args, 'precision_gain_trial', False) or knee30 or calibrated)
    baseline_design = copy.deepcopy(design)
    if calibrated:
        design = _self_weight_calibrated_design(design, resume['calibration_cases'])
    elif knee30:
        design = _self_weight_knee30_design(design)
    elif gain_trial:
        design = _self_weight_gain_design(design, remaining)
    out = args.out.resolve()
    assert out.parent.is_dir() and wiring.REPO / 'rl_exp/out' in out.parents and not out.exists()
    out.mkdir(exist_ok=False)
    source_path = Path(globals().get('__candidate_source__', __file__))
    shutil.copyfile(source_path, out/'source.py')
    result = dict(completed=False, stage='startup', code_sha256=wiring.binding.sha256_file(source_path),
                  input={str(args.inertia_report): args.approved_inertia_sha256,
                         str(manifest): wiring.binding.sha256_file(manifest)}, design=design,
                  scope='one fixed-root chest self-weight hold/lift/return; all bodies gravity; no fixture or ground support',
                  chest_effort_limit_nm=280., settings={**SETTINGS, 'max_full_runs': 1, 'settle_s': 5.,
                      'max_absolute_error_rad': .1, 'settle_drift_rad': .002, 'stop_absolute_error_rad': .35},
                  full_runs_started=1, retry_allowed=False, samples=[], entities=[])
    if suite:
        result.update(scope='29 joints and six group combinations, bidirectional downstream self-weight; fixed root; no fixture/ground support',
                      planned_cases=planned, selected_cases=remaining, planned_max_steps=len(remaining)*3400, cases=[], resume=resume,
                      continue_precision_only=bool(getattr(args, 'continue_self_weight_axes', False) or gain_trial or combinations))
        if gain_trial and not (knee30 or calibrated):
            result.update(scope='eight original hold-precision failures; one +20% Kp trial; no combinations',
                          precision_gain_trial=dict(kp_factor=1.2, kd_factor=math.sqrt(1.2),
                                                    baseline_design=baseline_design, changed_joints=list(remaining)))
        if knee30:
            result.update(scope='left rear knee only, Kp=30 and matched damping; other current gains unchanged',
                          left_knee_kp30=dict(baseline_design=baseline_design,changed_joints=['rl_knee_joint']))
        if calibrated:
            result.update(scope='all 30 single axes, bidirectional self-weight; individually calibrated eight failing axes',
                          precision_calibration=dict(baseline_design=baseline_design, stiffness_margin_factor=1.05,
                              changed_joints=[c['case'] for c in resume['calibration_cases']]))
        if combinations:
            result.update(scope='six calibrated self-weight group combinations; gains unchanged from all-axis verification',
                          combination_verification=dict(baseline_design=baseline_design))
    env, app = None, None
    try:
        from isaaclab.app import AppLauncher
        app = AppLauncher(args).app
        import gymnasium as gym
        import torch
        import warp as wp
        import rl_exp.tasks
        from pxr import UsdPhysics
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg, joint_reset_errors
        from palm_spatial_inertia import csc
        document = copy.deepcopy(original)
        tracking = out/'tracking_manifest.json'
        document['target_binding']['source'] = str(tracking)
        document['config']['scene.robot.spawn.rigid_props.disable_gravity'] = False
        for group in ('legs', 'feet', 'spine'):
            selected = document['config'][f'scene.robot.actuators.{group}.joint_names_expr']
            for field in ('stiffness', 'damping'):
                values = design['kp' if field == 'stiffness' else 'kd']
                document['config'][f'scene.robot.actuators.{group}.{field}'] = {n: values[design['joint_names'].index(n)] for n in selected}
            for field in ('effort_limit', 'effort_limit_sim'):
                key = f'scene.robot.actuators.{group}.{field}'
                if 'chest_pitch_joint' in selected:
                    document['config'][key]['chest_pitch_joint'] = 280.
        wiring.write_json(tracking, document)
        cfg = copy.deepcopy(resolve_task_cfg(wiring.REGISTERED_TASK))
        target = wiring.obs_protocol.load_diagnostic_target(tracking, cfg, wiring.REGISTERED_TASK)
        cfg.sim.device, cfg.sim.dt, cfg.sim.gravity, cfg.seed = args.device, .005, (0., 0., -9.81), 0
        env = gym.make(wiring.REGISTERED_TASK, cfg=cfg)
        wrapper = RslRlVecEnvWrapper(env, clip_actions=None)
        live, robot = env.unwrapped, env.unwrapped.scene['robot']
        assert robot.is_fixed_base and not joint_reset_errors(robot)
        names = list(robot.joint_names)
        assert names == design['joint_names']
        chest = names.index('chest_pitch_joint')
        backend = lambda x: wp.to_torch(x).cpu().numpy()[0]
        kp, kd = backend(robot.root_view.get_dof_stiffnesses()), backend(robot.root_view.get_dof_dampings())
        assert np.allclose(kp, design['kp'], rtol=1e-5) and np.allclose(kd, design['kd'], rtol=1e-5)
        caps = backend(robot.root_view.get_dof_max_forces())
        tree = ET.parse(target['urdf']).getroot()
        expected = {j.get('name'): float(j.find('limit').get('effort')) for j in tree.findall('joint')}
        expected['chest_pitch_joint'] = 280.
        assert np.allclose(caps, [expected[n] for n in names], rtol=1e-6)
        speeds = backend(robot.root_view.get_dof_max_velocities())
        gravity = {p.GetName(): p.GetAttribute('physxRigidBody:disableGravity').Get()
                   for p in live.sim.stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)}
        assert len(gravity) == 31 and all(v is False for v in gravity.values())
        assert np.all(robot.data.joint_armature.torch.cpu().numpy() == 0)
        action_names, action_ids = [], []
        for term_name in live.action_manager.active_terms:
            term = live.action_manager.get_term(term_name)
            ids = list(range(30))[term._joint_ids] if isinstance(term._joint_ids, slice) else list(term._joint_ids)
            action_names.extend(term._joint_names)
            action_ids.extend(map(int, ids))
            assert np.all(np.asarray(torch.as_tensor(term._scale).cpu()) == 1)
            assert np.all(np.asarray(torch.as_tensor(term._offset).cpu()) == 0)
        wiring.exact_channels(names, action_names, action_ids, names)
        result.update(tracking_manifest=str(tracking), tracking_manifest_sha256=wiring.binding.sha256_file(tracking),
                      joint_names=names, action_names=action_names,
                      readbacks=dict(kp=kp.tolist(), kd=kd.tolist(), effort_caps=caps.tolist(), velocity_caps=speeds.tolist(),
                                     fixed_base=robot.is_fixed_base, body_disable_gravity=gravity, gravity=cfg.sim.gravity))
        model = csc.load_urdf(Path(target['urdf']))
        cases = remaining if suite else {'chest_pitch_self_weight': ['chest_pitch_joint']}
        bounds = {j.get('name'): [float(j.find('limit').get(k)) for k in ('lower', 'upper')] for j in tree.findall('joint')}
        failed = False
        for case, commanded in cases.items():
            if suite:
                live.reset()
                assert not joint_reset_errors(robot), 'self-weight case reset mismatch'
            result.update(stage=case, samples=[], entities=[], commanded_joints=commanded)
            sign = 1. if suite else np.sign(design['chest_amplitude_rad'])
            assert all(bounds[n][0] <= -.02 and bounds[n][1] >= .02 for n in commanded)
            count = 3400 if suite else 2200
            checkpoints = (5., 7.9, 10.9, 13.9, 16.9) if suite else (5., 7.9, 10.9)
            for t in np.arange(1, count+1)*.005:
                desired = np.zeros(30)
                angle = _target(max(t-5., 0.), sign*.02) if t <= 11. else _target(t-11., -.02)
                for n in commanded:
                    desired[names.index(n)] = angle
                action = torch.tensor([[desired[names.index(n)] for n in action_names]], device=args.device, dtype=torch.float32)
                live.action_manager.process_action(action)
                live.action_manager.apply_action()
                live.scene.write_data_to_sim()
                drive = _drive_targets(robot, backend, desired)
                live.sim.step()
                live.scene.update(.005)
                q = robot.data.joint_pos.torch[0].cpu().numpy().copy()
                velocity = robot.data.joint_vel.torch[0].cpu().numpy().copy()
                contact = float(torch.linalg.vector_norm(live.scene['contact_forces'].data.net_forces_w, dim=-1).max())
                result['samples'].append(dict(t_s=float(t), q_rad=q.tolist(), velocity_rad_s=velocity.tolist(),
                    target_rad=desired.tolist(), max_contact_n=contact, backend_drive_targets=drive,
                    reconstructed_pd_request_nm=(kp*(desired-q)-kd*velocity).tolist()))
                assert np.isfinite(q).all() and np.isfinite(velocity).all() and np.isfinite(contact), 'nonfinite state'
                assert abs(q-desired).max() <= .35 and abs(q).max() <= .35, 'self-weight unsafe absolute error'
                assert np.all(abs(velocity) < speeds*.5) and contact <= 1., 'unsafe speed/contact'
                if any(abs(t-s) < 1e-9 for s in checkpoints):
                    result['entities'].append(dict(t_s=float(t), **_entity_snapshot(robot, model)))
                if abs(t-5.) < 1e-9:
                    settled = np.array([r['q_rad'] for r in result['samples'] if r['t_s'] >= 4.8])
                    assert abs(settled).max() <= .1 and np.ptp(settled, axis=0).max() <= .002, 'self-weight hold not verified'
            result['verdict'] = (_self_weight_verdict(result['samples'], names, commanded) if suite
                                 else _chest_verdict(result['samples'], names))
            assert len(result['entities']) == len(checkpoints)
            if suite:
                summary = dict(case=case, commanded_joints=commanded, samples_completed=len(result['samples']), **result['verdict'])
                result['cases'].append(summary)
                _write_self_weight_case(out, result, summary)
                print('SELF_WEIGHT_CASE', case, result['verdict']['passed'], flush=True)
            failed = not result['verdict']['passed']
            if failed and not ((getattr(args, 'continue_self_weight_axes', False) or gain_trial or combinations)
                                   and _self_weight_precision_only(result['verdict'])):
                break
        if suite:
            result.pop('samples')
            result.pop('entities')
            result['steps_completed'] = sum(c['samples_completed'] for c in result['cases'])
            finished = len(result['cases']) == len(cases)
            passed = finished and all(c['passed'] for c in result['cases'])
            result.update(all_selected_cases_passed=passed, selected_cases_completed=finished,
                          precision_unmet_cases=[c['case'] for c in result['cases'] if _self_weight_precision_only(c)])
            status = 'self_weight_suite_verified' if passed else 'self_weight_suite_failed'
            if getattr(args, 'continue_self_weight_axes', False):
                status = ('self_weight_axes_verified' if passed else
                          'self_weight_axes_completed_precision_unmet' if finished else 'self_weight_axes_failed')
            if gain_trial:
                status = ('self_weight_gain_trial_verified' if passed else
                          'self_weight_gain_trial_completed_precision_unmet' if finished else 'self_weight_gain_trial_failed')
            if knee30:
                status = ('left_knee_kp30_verified' if passed else
                          'left_knee_kp30_precision_unmet' if _self_weight_precision_only(result['verdict']) else 'left_knee_kp30_failed')
            if calibrated:
                status = ('calibrated_precision_verified' if passed else
                          'calibrated_precision_completed_unmet' if finished else 'calibrated_precision_failed')
            if combinations:
                status = ('calibrated_combinations_verified' if passed else
                          'calibrated_combinations_completed_precision_unmet' if finished else 'calibrated_combinations_failed')
        else:
            passed = not failed
            status = 'chest_self_weight_tracking_verified' if passed else 'chest_self_weight_tracking_failed'
        result.update(completed=True, stage='completed', status=status)
        assert wiring.binding.sha256_file(manifest) == result['input'][str(manifest)]
        assert wiring.binding.sha256_file(args.inertia_report) == args.approved_inertia_sha256
        wiring.write_json(out/'report.json', result)
        print('CHEST_280_COMPLETED', result['status'], flush=True)
        if not passed:
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(1)
    except BaseException as error:
        result.update(error=repr(error), traceback=traceback.format_exc())
        wiring.write_json(out/'failure.json', result)
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
    finally:
        if env is not None:
            env.close()
        if app is not None:
            app.close()
    return True

def _run(args):
    fresh = bool(args.approved_inertia_sha256)
    assert not args.all_joints or fresh, 'all_joints requires approved_inertia_sha256'
    reference = _fresh_inputs(args) if fresh else json.loads(args.inertia_report.read_text(encoding='utf-8'))
    assert reference['completed'] and reference['status'] == 'authored_inertia_and_mass_matrix_verified'
    manifest = Path(reference['replay_manifest'])
    assert wiring.binding.sha256_file(manifest) == reference['replay_manifest_sha256']
    source = json.loads(manifest.read_text(encoding='utf-8'))
    assert source['sha256']['urdf'] == (source['input']['urdf_sha256'] if fresh else wiring.URDF_HASH)
    neutral = next(s for s in reference['snapshots'] if s['label'] == 'neutral')
    assert neutral['runtime_fixed_base'] and neutral['mass_matrix_checks']['urdf']['within_roundoff_budget']
    inertias = dict(zip(neutral['joint_names'], np.diag(neutral['mass_matrix'])))
    omega = 2*math.pi*SETTINGS['frequency_hz']
    kp = {n: float(i*omega**2) for n, i in inertias.items()}
    kd = {n: float(2*SETTINGS['damping_ratio']*i*omega) for n, i in inertias.items()}
    gain_source = None
    if args.gain_reference:
        assert args.combined or args.level_leg_plan
        gained = json.loads(args.gain_reference.read_text(encoding='utf-8'))
        assert gained['completed'] and gained['status'] == 'standing_verified'
        gain_manifest = Path(gained['manifest'])
        assert wiring.binding.sha256_file(gain_manifest) == gained['manifest_sha256']
        assert json.loads(gain_manifest.read_text(encoding='utf-8'))['sha256']['urdf'] == wiring.URDF_HASH
        assert gained['joint_names'] == neutral['joint_names']
        kp = dict(zip(gained['joint_names'], gained['readbacks']['kp']))
        kd = dict(zip(gained['joint_names'], gained['readbacks']['kd']))
        if args.level_leg_plan:
            kp['lf_wrist_joint'] *= args.wrist_frequency_hz**2
            kd['lf_wrist_joint'] *= args.wrist_frequency_hz
        gain_source = dict(report=str(args.gain_reference), sha256=wiring.binding.sha256_file(args.gain_reference),
                           leg_frequency_hz=gained['standing_adapter']['leg_frequency_hz'],
                           neck_frequency_hz=gained['standing_adapter']['neck_frequency_hz'])
    out = args.out.resolve()
    assert wiring.REPO / 'rl_exp/out' in out.parents and not out.exists()
    out.mkdir(parents=True)
    # compile+exec candidates retain the original __file__ for imports, not source identity.
    source_path = Path(globals().get('__candidate_source__', __file__))
    shutil.copyfile(source_path, out / 'source.py')
    result = dict(completed=False, stage='startup', settings=SETTINGS,
                  input={str(args.inertia_report): wiring.binding.sha256_file(args.inertia_report),
                         str(manifest): wiring.binding.sha256_file(manifest)},
                  code_sha256=wiring.binding.sha256_file(source_path), cases=[], combined=args.combined,
                  scope='fixed base at z=2m; zero gravity; registered action manager; zero target velocity; no support')
    if fresh:
        result.update(settings={**SETTINGS, 'max_full_runs': 1}, all_joints=True,
                      approvals={'inertia_report_sha256': args.approved_inertia_sha256, **reference['approvals']},
                      full_runs_started=1, retry_allowed=False)
        result['input'].update(reference['input'])
    if gain_source:
        result['gain_source'] = gain_source
        result['settings'] = {**SETTINGS, 'frequency_hz': None, 'gain_source': 'verified standing readback'}
        result['input'][str(args.gain_reference)] = gain_source['sha256']
    app, env = None, None
    try:
        from isaaclab.app import AppLauncher
        app = AppLauncher(args).app
        import gymnasium as gym
        import torch
        import warp as wp
        import rl_exp.tasks
        from isaaclab.actuators import ImplicitActuatorCfg
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        from pxr import UsdPhysics
        from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg, joint_reset_errors
        wiring.check_registered_manifest(manifest, measured_order=not fresh)
        tracked = copy.deepcopy(source)
        tracked_manifest = out / 'tracking_manifest.json'
        tracked['target_binding']['source'] = str(tracked_manifest)
        if args.level_leg_plan:
            plan = _level_fixture(tracked, out, args.level_leg_plan)
            result.update(level_settings=LEVEL_SETTINGS, level_fixture=tracked['level_fixture'],
                          scope=tracked['level_fixture']['scope'], level_leg_plan=plan, wrist_frequency_hz=args.wrist_frequency_hz)
            result['input'][str(args.level_leg_plan)] = wiring.binding.sha256_file(args.level_leg_plan)
        for group in ('legs', 'feet', 'spine'):
            names = tracked['config'][f'scene.robot.actuators.{group}.joint_names_expr']
            tracked['config'][f'scene.robot.actuators.{group}.stiffness'] = {n: kp[n] for n in names}
            tracked['config'][f'scene.robot.actuators.{group}.damping'] = {n: kd[n] for n in names}
        wiring.write_json(tracked_manifest, tracked)
        cfg = copy.deepcopy(resolve_task_cfg(wiring.REGISTERED_TASK))
        target = wiring.obs_protocol.load_diagnostic_target(tracked_manifest, cfg, wiring.REGISTERED_TASK)
        cfg.sim.device = args.device
        cfg.sim.dt = SETTINGS['dt_s']
        cfg.seed = 0
        result['runtime_overrides'] = {'sim.dt': cfg.sim.dt, 'seed': cfg.seed, 'sim.device': cfg.sim.device}
        assert all(isinstance(a, ImplicitActuatorCfg) for a in cfg.scene.robot.actuators.values())
        env = gym.make(wiring.REGISTERED_TASK, cfg=cfg)
        wrapper = RslRlVecEnvWrapper(env, clip_actions=None)
        live, robot = env.unwrapped, env.unwrapped.scene['robot']
        assert robot.is_fixed_base and not joint_reset_errors(robot)
        names = list(robot.joint_names)
        assert names == neutral['joint_names']
        result.update(target=target, tracking_manifest=str(tracked_manifest),
                      tracking_manifest_sha256=wiring.binding.sha256_file(tracked_manifest), joint_names=names)
        # Read the backend, independently of the cached data buffers.
        backend = lambda x: wp.to_torch(x).cpu().numpy()[0]
        read_kp = backend(robot.root_view.get_dof_stiffnesses())
        read_kd = backend(robot.root_view.get_dof_dampings())
        assert np.allclose(read_kp, [kp[n] for n in names], rtol=1e-5)
        assert np.allclose(read_kd, [kd[n] for n in names], rtol=1e-5)
        assert np.all(robot.data.joint_armature.torch.cpu().numpy() == 0)
        drive_types = {p.GetName(): UsdPhysics.DriveAPI(p, 'angular').GetTypeAttr().Get()
                       for p in live.sim.stage.Traverse() if p.IsA(UsdPhysics.RevoluteJoint)}
        assert len(drive_types) == len(names) and set(drive_types.values()) == {'force'}
        result['readbacks'] = dict(kp=read_kp.tolist(), kd=read_kd.tolist(), drive_types=drive_types,
                                   velocity_caps=backend(robot.root_view.get_dof_max_velocities()).tolist(),
                                   effort_caps=robot.data.joint_effort_limits.torch[0].cpu().tolist(),
                                   position_limits=robot.data.joint_pos_limits.torch[0].cpu().tolist())
        if args.level_leg_plan:
            from palm_spatial_inertia import _rotation
            constrained_ids = [names.index(n) for n in tracked['level_fixture']['constrained_joints']]
            limits = np.array(result['readbacks']['position_limits'])[constrained_ids]
            assert np.allclose(limits, [-LEVEL_SETTINGS['fixture_half_range_rad'], LEVEL_SETTINGS['fixture_half_range_rad']], atol=1e-10)
            gravity = {p.GetName(): p.GetAttribute('physxRigidBody:disableGravity').Get() for p in live.sim.stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)}
            assert gravity and all(value is False for value in gravity.values())
            result['readbacks'].update(fixed_base=robot.is_fixed_base, gravity=cfg.sim.gravity, body_disable_gravity=gravity)
            chest_id = robot.body_names.index('chest_pitch')
        action_names, action_ids = [], []
        for term_name in live.action_manager.active_terms:
            term = live.action_manager.get_term(term_name)
            ids = list(range(len(names)))[term._joint_ids] if isinstance(term._joint_ids, slice) else list(term._joint_ids)
            action_names.extend(term._joint_names)
            action_ids.extend(map(int, ids))
            assert np.all(np.asarray(torch.as_tensor(term._scale).cpu()) == 1)
            assert np.all(np.asarray(torch.as_tensor(term._offset).cpu()) == 0)
        wiring.exact_channels(names, action_names, action_ids, names)
        result['action_names'] = action_names
        tree = ET.parse(target['urdf']).getroot()
        bounds = {j.get('name'): [float(j.find('limit').get(k)) for k in ('lower', 'upper')] for j in tree.findall('joint')}
        cases = _tracking_cases(names, args.all_joints)
        model = None
        if fresh:
            from palm_spatial_inertia import csc
            model = csc.load_urdf(Path(target['urdf']))
            assert robot.is_fixed_base and len(robot.body_names) == 31
            gravity = {p.GetName(): p.GetAttribute('physxRigidBody:disableGravity').Get()
                       for p in live.sim.stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)}
            assert len(gravity) == 31 and all(v is True for v in gravity.values())
            result['readbacks'].update(fixed_base=True, body_disable_gravity=gravity)
            assert np.allclose(result['readbacks']['position_limits'], [bounds[n] for n in names], atol=1e-6)
        if args.combined:
            from palm_spatial_inertia import csc
            model = csc.load_urdf(Path(target['urdf']))
            cases = {leg + '_proximal': [n for n in cases if n.startswith(leg + '_')][:(4 if gain_source else 3)]
                     for leg in wiring.joint_names.LEGS}
            if gain_source:
                cases['neck_pitch'] = ['neck_pitch_joint']
        else:
            cases = {n: [n] for n in cases}
        if args.level_leg_plan:
            from palm_spatial_inertia import csc
            model = csc.load_urdf(Path(target['urdf']))
            cases = {'lf_level_self_weight': [n for n in cases if n.startswith('lf_')]}
        dt = SETTINGS['dt_s']
        settle = LEVEL_SETTINGS['settle_s'] if args.level_leg_plan else 0.
        times = np.arange(1, int((settle+2*SETTINGS['ramp_s'] + 2*SETTINGS['hold_s'])/dt)+1)*dt
        sensor = live.scene['contact_forces']
        for case, commanded in cases.items():
            result['stage'] = case
            live.reset()
            assert not joint_reset_errors(robot)
            axes = [names.index(n) for n in commanded]
            amplitudes = {n: SETTINGS['amplitude_rad'] * (1 if bounds[n][1] >= SETTINGS['amplitude_rad']+.005 else -1)
                          for n in commanded}
            if args.level_leg_plan:
                amplitudes = {n: plan['target_q_rad'][n] for n in commanded}
            assert all(bounds[n][0] <= min(0, a) and max(0, a) <= bounds[n][1] for n, a in amplitudes.items())
            rows, q_rows, target_rows, entities, max_contact = [], [], [], [], 0.
            level_errors, baseline, stop = [], None, None
            if fresh:
                entities.append(dict(t_s=0., **_entity_snapshot(robot, model)))
            for t in times:
                action = torch.zeros((1, len(action_names)), device=args.device)
                desired = np.zeros(len(names))
                for name, amplitude in amplitudes.items():
                    desired[names.index(name)] = _target(max(t-settle, 0.), amplitude)
                    action[0, action_names.index(name)] = desired[names.index(name)]
                live.action_manager.process_action(action)
                live.action_manager.apply_action()
                live.scene.write_data_to_sim()
                drive = _drive_targets(robot, backend, desired) if fresh else None
                live.sim.step(render=False)
                live.scene.update(dt)
                q = robot.data.joint_pos.torch[0].cpu().numpy().copy()
                v = robot.data.joint_vel.torch[0].cpu().numpy().copy()
                force = float(sensor.data.net_forces_w.torch.norm(dim=-1).max())
                max_contact = max(max_contact, force)
                assert np.isfinite(q).all() and np.isfinite(v).all()
                if not args.level_leg_plan:
                    assert abs(q).max() < SETTINGS['stop_position_rad'] and force <= SETTINGS['stop_contact_n'], 'unsafe response/contact'
                assert np.all(abs(v) < np.asarray(result['readbacks']['velocity_caps'])*.5), 'unexpected speed'
                requested = read_kp*(desired-q)-read_kd*v
                rows.append(dict(t_s=float(t), q_rad=q.tolist(), velocity_rad_s=v.tolist(), target_rad=desired.tolist(),
                                 reconstructed_pd_request_nm=requested.tolist(), max_contact_n=force))
                if fresh:
                    rows[-1]['backend_drive_targets'] = drive
                if args.level_leg_plan:
                    pose = robot.data.body_link_pose_w.torch[0, chest_id].cpu().numpy()
                    level_error = float(abs(_rotation(pose[3:])[:, 2]-[0., 0., 1.]).max())
                    rows[-1]['chest_pose_xyzw'] = pose.tolist()
                    rows[-1]['chest_level_error'] = level_error
                    level_errors.append(level_error)
                    if abs(t-settle) < 1e-9:
                        baseline = q.copy()
                    if level_error > LEVEL_SETTINGS['level_tolerance']:
                        stop = 'chest_not_level'
                    elif abs(q[axes]-desired[axes]).max() > LEVEL_SETTINGS['stop_absolute_error_rad']:
                        stop = 'leg_absolute_error'
                    elif force > SETTINGS['stop_contact_n']:
                        stop = 'contact'
                    if stop:
                        break
                if t > settle:
                    q_rows.append(q)
                    target_rows.append(desired)
                if model is not None and (abs(t-settle-2.9) < 1e-9 or abs(t-settle-5.9) < 1e-9):
                    entities.append(dict(t_s=float(t), **_entity_snapshot(robot, model)))
            if args.level_leg_plan:
                verdict = dict(passed=False, stop_reason=stop, completed_trajectory=False) if stop else _level_verdict(
                    np.array(q_rows), np.array(target_rows), axes, times[times > settle]-settle, baseline, level_errors)
                verdict.update(baseline_q_rad=None if baseline is None else baseline.tolist(), completed_trajectory=stop is None,
                               max_chest_level_error=float(max(level_errors)))
            else:
                verdict = _verdict(np.array(q_rows), np.array(target_rows), axes, times)
            verdict.update(joint=case, commanded_joints=commanded, amplitudes_rad=amplitudes, max_contact_n=max_contact)
            if not args.combined and not args.level_leg_plan:
                verdict['amplitude_rad'] = amplitudes[commanded[0]]
            if fresh:
                assert len(rows) == 1200
                verdict['commanded_child_actor_motion'] = _motion_evidence(entities, commanded, model)
            if entities:
                verdict['entity_fk_max_error'] = max(max(e['actor_fk_max_error'].values()) for e in entities)
            result['cases'].append(verdict)
            wiring.write_json(out / (case + '.json'), dict(summary=verdict, samples=rows, entities=entities))
            wiring.write_json(out / f'progress_{len(result["cases"]):02d}.json', result)
            print('TRACKING_CASE', json.dumps(verdict), flush=True)
            if not verdict['passed']:
                break
        passed = len(result['cases']) == len(cases) and all(c['passed'] for c in result['cases'])
        result.update(completed=True, stage='completed', status=('combined_tracking_verified' if args.combined else 'small_tracking_verified') if passed else 'tracking_failed')
        if args.level_leg_plan:
            result['status'] = 'level_leg_tracking_verified' if passed else 'level_leg_tracking_failed'
        wiring.write_json(out / 'report.json', result)
        print('TRACKING_COMPLETED', result['status'], flush=True)
        if not passed:
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(1)  # App.close may terminate the process before main can return failure.
    except BaseException as error:
        result.update(error=repr(error), traceback=traceback.format_exc())
        wiring.write_json(out / 'failure.json', result)
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
    finally:
        if env is not None:
            env.close()
        if app is not None:
            app.close()
    return passed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inertia_report', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--self_check', action='store_true')
    parser.add_argument('--approved_inertia_sha256')
    parser.add_argument('--all_joints', action='store_true')
    parser.add_argument('--chest_self_weight_280', action='store_true')
    parser.add_argument('--self_weight_suite', action='store_true')
    parser.add_argument('--resume_self_weight', type=Path)
    parser.add_argument('--approved_resume_sha256')
    parser.add_argument('--continue_self_weight_axes', action='store_true')
    parser.add_argument('--precision_gain_trial', action='store_true')
    parser.add_argument('--left_knee_kp30', action='store_true')
    parser.add_argument('--calibrate_precision', action='store_true')
    parser.add_argument('--calibrated_combinations', action='store_true')
    parser.add_argument('--combined', action='store_true')
    parser.add_argument('--gain_reference', type=Path)
    parser.add_argument('--level_leg_plan', type=Path)
    parser.add_argument('--wrist_frequency_hz', type=float, choices=(1., 6.), default=1.)
    if '--self_check' in sys.argv:
        args = parser.parse_args()
        _self_check()
        if args.approved_inertia_sha256:
            _fresh_self_check(args)
        if args.chest_self_weight_280:
            _chest_self_check(args)
        if args.self_weight_suite:
            _self_weight_self_check(args)
    else:
        from isaaclab.app import AppLauncher
        AppLauncher.add_app_launcher_args(parser)
        args = parser.parse_args()
        if not args.inertia_report or not args.out:
            parser.error('inertia_report and out are required')
        if args.level_leg_plan and (not args.gain_reference or args.combined):
            parser.error('level_leg_plan requires gain_reference and excludes combined')
        if not args.level_leg_plan and args.wrist_frequency_hz != 1:
            parser.error('wrist override requires level_leg_plan')
        if args.calibrated_combinations and (args.calibrate_precision or args.left_knee_kp30 or args.precision_gain_trial or args.continue_self_weight_axes or not (args.self_weight_suite and args.resume_self_weight and args.approved_resume_sha256)):
            parser.error('calibrated combinations require approved all-axis report and exclude other trial selectors')
        if args.calibrate_precision and (args.left_knee_kp30 or args.precision_gain_trial or args.continue_self_weight_axes or not (args.self_weight_suite and args.resume_self_weight and args.approved_resume_sha256)):
            parser.error('precision calibration requires approved knee30 report and excludes other trial selectors')
        if args.left_knee_kp30 and (args.precision_gain_trial or args.continue_self_weight_axes or not (args.self_weight_suite and args.resume_self_weight and args.approved_resume_sha256)):
            parser.error('left knee 30 requires approved gain trial report and excludes other trial selectors')
        if args.precision_gain_trial and (args.continue_self_weight_axes or not (args.self_weight_suite and args.resume_self_weight and args.approved_resume_sha256)):
            parser.error('gain trial requires approved prior axes report; excludes axes continuation')
        if args.continue_self_weight_axes and not (args.self_weight_suite and args.resume_self_weight and args.approved_resume_sha256):
            parser.error('17-axis continuation requires self_weight_suite and approved prior report')
        if (args.resume_self_weight or args.approved_resume_sha256) and not args.self_weight_suite:
            parser.error('resume is only valid for self_weight_suite')
        if args.chest_self_weight_280 and args.self_weight_suite:
            parser.error('self-weight modes are exclusive')
        if (args.chest_self_weight_280 or args.self_weight_suite) and not args.approved_inertia_sha256:
            parser.error('self-weight tracking requires approved fresh inertia')
        sys.exit(0 if (_run_chest280(args) if args.chest_self_weight_280 or args.self_weight_suite else _run(args)) else 1)
