# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Short free-base, gravity-enabled standing diagnostic [m, s, rad, N, N*m]."""
import argparse
import copy
import difflib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import traceback

import numpy as np
import palm_spatial_runtime as wiring
from palm_spatial_inertia import csc, _rotation
from palm_spatial_tracking import _entity_snapshot

SETTINGS = dict(dt_s=.005, duration_s=5., start_clearance_m=.001, stop_drop_m=.15,
                stop_tilt_rad=.35, stop_joint_rad=.35, stop_forbidden_ground_n=5.,
                standing_drop_m=.02, standing_tilt_rad=.1, standing_joint_rad=.1,
                standing_vertical_speed_m_s=.05, foot_load_n=5., weight_relative_error=.2,
                max_calibration_variants=3)


def _prepare(report, out, leg_frequency_hz, neck_frequency_hz):
    from pxr import Usd, UsdPhysics
    prior = json.loads(report.read_text(encoding='utf-8'))
    assert prior['completed'] and prior['status'] == 'combined_tracking_verified'
    manifest = Path(prior['tracking_manifest'])
    assert wiring.binding.sha256_file(manifest) == prior['tracking_manifest_sha256']
    doc = json.loads(manifest.read_text(encoding='utf-8'))
    old_usd, old_urdf = Path(doc['target']), Path(doc['urdf'])
    assert wiring.binding.sha256_file(old_usd) == doc['sha256']['target']
    assert wiring.binding.sha256_file(old_urdf) == wiring.URDF_HASH
    model = csc.load_urdf(old_urdf)
    minima = {}
    for name, link in model['links'].items():
        if link['collision']:
            pose = csc.fk(model['joints'], name, {})
            vertices = csc.read_obj(link['collision']) @ pose[:3, :3].T + pose[:3, 3]
            minima[name] = float(vertices[:, 2].min())
    height = -min(minima.values()) + SETTINGS['start_clearance_m']
    stage = Usd.Stage.Open(str(old_usd))
    original = stage.GetRootLayer().ExportToString()
    fixed = [UsdPhysics.FixedJoint(p) for p in stage.Traverse() if p.IsA(UsdPhysics.FixedJoint)
             and (not UsdPhysics.FixedJoint(p).GetBody0Rel().GetTargets()
                  or not UsdPhysics.FixedJoint(p).GetBody1Rel().GetTargets())]
    assert len(fixed) == 1 and not fixed[0].GetJointEnabledAttr().HasAuthoredValueOpinion()
    fixed[0].GetJointEnabledAttr().Set(False)
    text = stage.GetRootLayer().ExportToString()
    stripped, count = re.subn(r'(?m)^[ \t]*(?:uniform )?bool physics:jointEnabled = (?:false|0)\n', '', text)
    assert count == 1 and stripped == original, '\n'.join(difflib.unified_diff(original.splitlines(), text.splitlines()))
    (out / 'palm_spatial.usda').write_text(text, encoding='utf-8')
    shutil.copyfile(old_urdf, out / 'palm_spatial.urdf')
    shutil.copytree(old_usd.parent / 'meshes', out / 'meshes')
    new_manifest = out / 'standing_manifest.json'
    doc['target_binding'].update(target=str(out/'palm_spatial.usda'), urdf=str(out/'palm_spatial.urdf'), source=str(new_manifest))
    for key in ('target', 'urdf'):
        doc[key] = doc['target_binding'][key]
        doc['sha256'][key] = wiring.binding.sha256_file(Path(doc[key]))
    doc['config']['scene.robot.init_state.pos'] = [0., 0., height]
    doc['config']['scene.robot.spawn.rigid_props.disable_gravity'] = False
    for field, power in (('stiffness', 2), ('damping', 1)):
        key = f'scene.robot.actuators.legs.{field}'
        doc['config'][key] = {n: v*leg_frequency_hz**power for n, v in doc['config'][key].items()}
        neck_key = f'scene.robot.actuators.spine.{field}'
        doc['config'][neck_key]['neck_pitch_joint'] *= neck_frequency_hz**power
    doc['standing_adapter'] = dict(prior_manifest=str(manifest), prior_manifest_sha256=wiring.binding.sha256_file(manifest),
                                  world_fixed_joint=str(fixed[0].GetPath()), only_joint_enabled_delta_verified=True,
                                  root_height_m=height, neutral_mesh_minima_m=minima,
                                  leg_frequency_hz=leg_frequency_hz, neck_frequency_hz=neck_frequency_hz, damping_ratio=1.)
    wiring.write_json(new_manifest, doc)
    return prior, new_manifest, model, doc['standing_adapter']


def _run(args):
    out = args.out.resolve()
    assert wiring.REPO / 'rl_exp/out' in out.parents and not out.exists()
    out.mkdir(parents=True)
    shutil.copyfile(__file__, out/'source.py')
    result = dict(completed=False, stage='startup', settings=SETTINGS,
                  input={str(args.tracking_report): wiring.binding.sha256_file(args.tracking_report)},
                  code_sha256=wiring.binding.sha256_file(Path(__file__)), samples=[])
    app, env = None, None
    try:
        from isaaclab.app import AppLauncher
        app = AppLauncher(args).app
        import gymnasium as gym
        import torch
        import warp as wp
        import rl_exp.tasks
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        from isaaclab_physx.physics import PhysxManager
        from pxr import Usd, UsdPhysics
        from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg, joint_reset_errors
        if args.leg_frequency_hz != 1:
            assert args.leg_frequency_hz == 6 and args.load_reference
            load = json.loads(args.load_reference.read_text(encoding='utf-8'))
            assert load['completed'] and load['status'] == 'standing_failed' and load['stop_reason'] == ['joint_motion']
            result['input'][str(args.load_reference)] = wiring.binding.sha256_file(args.load_reference)
        if args.neck_frequency_hz != 1:
            assert args.neck_frequency_hz == 2 and args.neck_load_reference and args.leg_frequency_hz == 6
            neck_load = json.loads(args.neck_load_reference.read_text(encoding='utf-8'))
            assert neck_load['completed'] and neck_load['status'] == 'standing_failed' and neck_load['stop_reason'] is None
            late_q = np.array([s['q_rad'] for s in neck_load['samples'] if s['t_s'] >= 4])
            bad = [n for n, value in zip(neck_load['joint_names'], abs(late_q).max(axis=0)) if value > SETTINGS['standing_joint_rad']]
            assert bad == ['neck_pitch_joint']
            result['input'][str(args.neck_load_reference)] = wiring.binding.sha256_file(args.neck_load_reference)
        prior, manifest, model, adapter = _prepare(args.tracking_report, out, args.leg_frequency_hz, args.neck_frequency_hz)
        result.update(standing_adapter=adapter, manifest=str(manifest), manifest_sha256=wiring.binding.sha256_file(manifest))
        cfg = copy.deepcopy(resolve_task_cfg(wiring.REGISTERED_TASK))
        target = wiring.obs_protocol.load_diagnostic_target(manifest, cfg, wiring.REGISTERED_TASK)
        cfg.sim.device, cfg.sim.dt, cfg.seed = args.device, SETTINGS['dt_s'], 0
        assert cfg.scene.terrain.terrain_type == 'plane'
        result['runtime_overrides'] = {'sim.dt': cfg.sim.dt, 'sim.device': cfg.sim.device, 'seed': cfg.seed}
        env = gym.make(wiring.REGISTERED_TASK, cfg=cfg)
        wrapper = RslRlVecEnvWrapper(env, clip_actions=None)
        live, robot = env.unwrapped, env.unwrapped.scene['robot']
        assert not robot.is_fixed_base and not joint_reset_errors(robot)
        assert not live._physics_handles_decimation and live.physics_dt == SETTINGS['dt_s']
        names, body_names = list(robot.joint_names), list(robot.body_names)
        assert names == prior['joint_names']
        backend = lambda x: wp.to_torch(x).cpu().numpy()[0]
        kp, kd = backend(robot.root_view.get_dof_stiffnesses()), backend(robot.root_view.get_dof_dampings())
        expected_kp, expected_kd = np.array(prior['readbacks']['kp']), np.array(prior['readbacks']['kd'])
        leg_names = cfg.scene.robot.actuators['legs'].joint_names_expr
        for k, name in enumerate(names):
            if name in leg_names:
                expected_kp[k] *= args.leg_frequency_hz**2
                expected_kd[k] *= args.leg_frequency_hz
            elif name == 'neck_pitch_joint':
                expected_kp[k] *= args.neck_frequency_hz**2
                expected_kd[k] *= args.neck_frequency_hz
        assert np.allclose(kp, expected_kp, rtol=1e-6) and np.allclose(kd, expected_kd, rtol=1e-6)
        bodies = {p.GetName(): p for p in live.sim.stage.Traverse()
                  if p.HasAPI(UsdPhysics.RigidBodyAPI) and p.GetName() in body_names}
        assert set(bodies) == set(body_names)
        assert all(p.GetAttribute('physxRigidBody:disableGravity').Get() is False for p in bodies.values())
        ground = live.sim.stage.GetPrimAtPath(cfg.scene.terrain.prim_path)
        floors = [p for p in Usd.PrimRange(ground) if p.HasAPI(UsdPhysics.CollisionAPI)]
        assert len(floors) == 1, 'expected one actual floor collider'
        floor = str(floors[0].GetPath())
        views, mapping = {}, {}
        for name, prim in bodies.items():
            if not any(p.HasAPI(UsdPhysics.CollisionAPI) for p in Usd.PrimRange(prim)):
                continue
            path = str(prim.GetPath())
            view = PhysxManager.get_physics_sim_view().create_rigid_contact_view(path, filter_patterns=[floor], max_contact_data_count=256)
            wiring.pair_binding(view.sensor_paths, view.filter_paths, path, [floor], (view.sensor_count, view.filter_count, 3))
            views[name] = view
            mapping[name] = dict(body=path, floor=floor, sensor_paths=view.sensor_paths, filter_paths=view.filter_paths)
        assert len(views) == 18
        feet = list(target['end_links'].values())
        allowed = set(feet) | {n for n in views if n.startswith('tail')}
        mass = float(robot.data.body_mass.torch.sum())
        weight = mass * abs(cfg.sim.gravity[2])
        result.update(joint_names=names, body_names=body_names, target=target, ground_pair_mapping=mapping,
                      readbacks=dict(fixed_base=False, kp=kp.tolist(), kd=kd.tolist(), mass_kg=mass, gravity=cfg.sim.gravity,
                                     position_limits=robot.data.joint_pos_limits.torch[0].cpu().tolist(),
                                     velocity_caps=backend(robot.root_view.get_dof_max_velocities()).tolist(),
                                     effort_caps=robot.data.joint_effort_limits.torch[0].cpu().tolist()))
        result['initial_entities'] = _entity_snapshot(robot, model)
        zero = torch.zeros((1, live.action_manager.total_action_dim), device=args.device)
        start_z = float(robot.data.root_link_pose_w.torch[0, 2])
        stop = None
        for step in range(1, int(SETTINGS['duration_s']/SETTINGS['dt_s'])+1):
            live.action_manager.process_action(zero)
            live.action_manager.apply_action()
            live.scene.write_data_to_sim()
            live.sim.step(render=False)
            live.scene.update(SETTINGS['dt_s'])
            q = robot.data.joint_pos.torch[0].cpu().numpy().copy()
            v = robot.data.joint_vel.torch[0].cpu().numpy().copy()
            root_pose = robot.data.root_link_pose_w.torch[0].cpu().numpy().copy()
            root_vel = robot.data.root_link_vel_w.torch[0].cpu().numpy().copy()
            forces = {n: wp.to_torch(view.get_contact_force_matrix(dt=SETTINGS['dt_s'])).cpu().numpy().reshape(3).tolist()
                      for n, view in views.items()}
            tilt = float(np.arccos(np.clip(_rotation(root_pose[3:])[2, 2], -1, 1)))
            forbidden = max(np.linalg.norm(f) for n, f in forces.items() if n not in allowed)
            row = dict(t_s=step*SETTINGS['dt_s'], q_rad=q.tolist(), velocity_rad_s=v.tolist(),
                       root_pose_xyzw=root_pose.tolist(), root_velocity=root_vel.tolist(), tilt_rad=tilt,
                       root_drop_m=start_z-float(root_pose[2]), ground_forces_n=forces,
                       forbidden_ground_n=float(forbidden), reconstructed_pd_request_nm=(-kp*q-kd*v).tolist())
            result['samples'].append(row)
            assert np.isfinite(q).all() and np.isfinite(root_pose).all(), 'non-finite state'
            checks = {'root_drop': row['root_drop_m'] > SETTINGS['stop_drop_m'], 'root_tilt': tilt > SETTINGS['stop_tilt_rad'],
                      'joint_motion': abs(q).max() > SETTINGS['stop_joint_rad'],
                      'forbidden_ground': forbidden > SETTINGS['stop_forbidden_ground_n']}
            if any(checks.values()):
                stop = [k for k, value in checks.items() if value]
                break
        late = [s for s in result['samples'] if s['t_s'] >= SETTINGS['duration_s']-1]
        passed = stop is None and bool(late) and all(
            s['root_drop_m'] <= SETTINGS['standing_drop_m'] and s['tilt_rad'] <= SETTINGS['standing_tilt_rad']
            and max(map(abs, s['q_rad'])) <= SETTINGS['standing_joint_rad']
            and abs(s['root_velocity'][2]) <= SETTINGS['standing_vertical_speed_m_s']
            and all(s['ground_forces_n'][n][2] >= SETTINGS['foot_load_n'] for n in feet)
            for s in late)
        mean_support = float(np.mean([sum(f[2] for f in s['ground_forces_n'].values()) for s in late])) if late else None
        passed = passed and abs(mean_support-weight) <= SETTINGS['weight_relative_error']*weight
        result.update(completed=True, stage='completed', status='standing_verified' if passed else 'standing_failed',
                      stop_reason=stop, weight_n=weight, late_mean_ground_support_n=mean_support,
                      final_entities=_entity_snapshot(robot, model))
        wiring.write_json(out/'report.json', result)
        print('STANDING_COMPLETED', result['status'], 'stop', stop, 'last_t', result['samples'][-1]['t_s'], flush=True)
        if not passed:
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(1)  # Preserve a physical failure before App.close can swallow its exit.
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
    return passed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tracking_report', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--leg_frequency_hz', type=float, choices=(1., 6.), default=1.)
    parser.add_argument('--load_reference', type=Path)
    parser.add_argument('--neck_frequency_hz', type=float, choices=(1., 2.), default=1.)
    parser.add_argument('--neck_load_reference', type=Path)
    from isaaclab.app import AppLauncher
    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()
    sys.exit(0 if _run(args) else 1)
