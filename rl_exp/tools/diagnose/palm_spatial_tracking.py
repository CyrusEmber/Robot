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


def _run(args):
    reference = json.loads(args.inertia_report.read_text(encoding='utf-8'))
    assert reference['completed'] and reference['status'] == 'authored_inertia_and_mass_matrix_verified'
    manifest = Path(reference['replay_manifest'])
    assert wiring.binding.sha256_file(manifest) == reference['replay_manifest_sha256']
    source = json.loads(manifest.read_text(encoding='utf-8'))
    assert source['sha256']['urdf'] == wiring.URDF_HASH
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
    shutil.copyfile(__file__, out / 'source.py')
    result = dict(completed=False, stage='startup', settings=SETTINGS,
                  input={str(args.inertia_report): wiring.binding.sha256_file(args.inertia_report),
                         str(manifest): wiring.binding.sha256_file(manifest)},
                  code_sha256=wiring.binding.sha256_file(Path(__file__)), cases=[], combined=args.combined,
                  scope='fixed base at z=2m; zero gravity; registered action manager; zero target velocity; no support')
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
        wiring.check_registered_manifest(manifest)
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
        cases = [wiring.joint_names.joint_name(leg, root) for leg in wiring.joint_names.LEGS
                 for root in wiring.joint_names.roots_of(wiring.joint_names.PALM_SPATIAL_NAMING, leg)]
        assert len(cases) == 20 and len(set(cases)) == 20
        model = None
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
            for t in times:
                action = torch.zeros((1, len(action_names)), device=args.device)
                desired = np.zeros(len(names))
                for name, amplitude in amplitudes.items():
                    desired[names.index(name)] = _target(max(t-settle, 0.), amplitude)
                    action[0, action_names.index(name)] = desired[names.index(name)]
                live.action_manager.process_action(action)
                live.action_manager.apply_action()
                live.scene.write_data_to_sim()
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
    parser.add_argument('--combined', action='store_true')
    parser.add_argument('--gain_reference', type=Path)
    parser.add_argument('--level_leg_plan', type=Path)
    parser.add_argument('--wrist_frequency_hz', type=float, choices=(1., 6.), default=1.)
    if '--self_check' in sys.argv:
        _self_check()
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
        sys.exit(0 if _run(args) else 1)
