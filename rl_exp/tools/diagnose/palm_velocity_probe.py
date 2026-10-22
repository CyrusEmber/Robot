# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""One isolated left-knee velocity/observation probe with unchanged PD [rad, s].

Use separate fresh processes for legacy and per-iteration external-force timing.
Reuses the approved 5 s settle plus bidirectional 0.02 rad / 12 s trajectory.
No training, asset edits, gain tuning, or automatic adoption of solver settings.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import traceback

import numpy as np
import palm_spatial_runtime as wiring
from palm_spatial_tracking import (_target, _drive_targets, _entity_snapshot,
                                   _joint_force_probe_binding, _joint_force_probe_sample)


def observation_sample(live, q, v, desired, names):
    """Read the actual policy group and its raw term consumers [SI]."""
    manager = live.observation_manager
    group = manager.compute_group('policy')
    terms = []
    configs = manager._group_obs_term_cfgs['policy']
    term_names = manager._group_obs_term_names['policy']
    expected = []
    robot = live.scene['robot']
    for name, cfg in zip(term_names, configs):
        raw = cfg.func(live, **cfg.params).detach().clone().cpu().numpy()[0]
        value = raw.copy()
        assert cfg.noise is None and cfg.history_length == 0
        assert not getattr(cfg, 'modifiers', None)
        if cfg.clip is not None:
            value = np.clip(value, *cfg.clip)
        scale = cfg.scale.detach().cpu().numpy() if hasattr(cfg.scale, 'detach') else cfg.scale
        if cfg.scale is not None:
            value *= np.asarray(scale)
        if name == 'joint_pos':
            assert np.array_equal(raw, q)
        elif name == 'joint_vel':
            assert np.array_equal(raw, v)
        elif name == 'actions':
            assert np.array_equal(raw, desired.astype(np.float32))
        terms.append(dict(name=name, raw=raw.tolist(), processed=value.tolist(),
                          scale=np.asarray(scale).tolist() if scale is not None else None, clip=cfg.clip,
                          function=cfg.func.__module__+'.'+cfg.func.__name__))
        expected.extend(value.tolist())
    actual = group.detach().cpu().numpy()[0]
    assert np.allclose(actual, expected, rtol=1e-6, atol=1e-8)
    return dict(terms=terms, policy=actual.tolist(), joint_names=names,
                root_pose_xyzw=robot.data.root_link_pose_w.torch[0].cpu().tolist(),
                root_velocity=robot.data.root_link_vel_w.torch[0].cpu().tolist())


def run(args):
    report_path = args.reference.resolve()
    assert wiring.binding.sha256_file(report_path) == args.approved_reference_sha256
    prior = json.loads(report_path.read_text(encoding='utf-8'))
    assert prior['completed'] and prior['status'] == 'joint_force_probe_symmetric_pd_left_knee_trial_verified'
    manifest = Path(prior['tracking_manifest'])
    assert wiring.binding.sha256_file(manifest) == prior['tracking_manifest_sha256']
    out = args.out.resolve()
    assert wiring.REPO/'rl_exp/out' in out.parents and not out.exists()
    out.mkdir()
    shutil.copyfile(__file__, out/'source.py')
    result = dict(completed=False, stage='startup', reference=str(report_path),
                  reference_sha256=args.approved_reference_sha256,
                  manifest=str(manifest), manifest_sha256=prior['tracking_manifest_sha256'],
                  code_sha256=wiring.binding.sha256_file(Path(__file__)), samples=[], entities=[],
                  settings=dict(dt_s=.005, settle_s=5., duration_s=17., amplitude_rad=.02,
                                max_steps=3400, full_runs_started=1, retry_allowed=False,
                                stop_absolute_error_rad=.35, stop_contact_n=1., stop_speed_fraction=.5),
                  force_timing=args.force_timing)
    app = env = None
    try:
        from isaaclab.app import AppLauncher
        app = AppLauncher(args).app
        import gymnasium as gym
        import torch
        import warp as wp
        import rl_exp.tasks
        from isaaclab_physx.physics import PhysxCfg
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg, joint_reset_errors
        from palm_spatial_inertia import csc
        from pxr import UsdPhysics
        cfg = copy.deepcopy(resolve_task_cfg(wiring.REGISTERED_TASK))
        target = wiring.obs_protocol.load_diagnostic_target(manifest, cfg, wiring.REGISTERED_TASK)
        cfg.sim.device, cfg.sim.dt, cfg.sim.gravity, cfg.seed = args.device, .005, (0., 0., -9.81), 0
        if cfg.sim.physics is None:
            cfg.sim.physics = PhysxCfg()
        elif not hasattr(cfg.sim.physics, 'class_type') and hasattr(cfg.sim.physics, 'default'):
            # Match SimulationContext's registered-preset resolution exactly.
            cfg.sim.physics = cfg.sim.physics.default
        physics = cfg.sim.physics
        assert physics.solver_type == 1 and physics.enable_external_forces_every_iteration is False
        result['physics_before'] = physics.to_dict()
        physics.enable_external_forces_every_iteration = args.force_timing == 'per_iteration'
        result['physics_after'] = physics.to_dict()
        for key in result['physics_before']:
            if key != 'enable_external_forces_every_iteration':
                assert result['physics_before'][key] == result['physics_after'][key]
        env = gym.make(wiring.REGISTERED_TASK, cfg=cfg)
        wrapper = RslRlVecEnvWrapper(env, clip_actions=None)
        live, robot = env.unwrapped, env.unwrapped.scene['robot']
        live.reset()
        assert robot.is_fixed_base and not joint_reset_errors(robot)
        names = list(robot.joint_names)
        assert names == prior['joint_names']
        backend = lambda value: wp.to_torch(value).cpu().numpy()[0].copy()
        for field, getter in (('kp', 'get_dof_stiffnesses'), ('kd', 'get_dof_dampings'),
                              ('effort_caps', 'get_dof_max_forces'), ('velocity_caps', 'get_dof_max_velocities')):
            value = backend(getattr(robot.root_view, getter)())
            assert np.array_equal(value, prior['readbacks'][field]), field
            result.setdefault('readbacks', {})[field] = value.tolist()
        gravity = {p.GetName(): p.GetAttribute('physxRigidBody:disableGravity').Get()
                   for p in live.sim.stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)}
        assert len(gravity) == 31 and all(value is False for value in gravity.values())
        stage = live.sim.stage
        scene = stage.GetPrimAtPath(cfg.sim.physics_prim_path)
        result['readbacks'].update(fixed_base=robot.is_fixed_base, body_disable_gravity=gravity,
            force_timing=scene.GetAttribute('physxScene:enableExternalForcesEveryIteration').Get(),
            solver_type=scene.GetAttribute('physxScene:solverType').Get(),
            position_iterations=cfg.scene.robot.spawn.articulation_props.solver_position_iteration_count,
            velocity_iterations=cfg.scene.robot.spawn.articulation_props.solver_velocity_iteration_count)
        assert result['readbacks']['force_timing'] == physics.enable_external_forces_every_iteration
        result.update(joint_names=names, target=target, joint_force_probe=_joint_force_probe_binding(stage, robot, backend))
        result['dependencies'] = {}
        for source in (Path(__file__).with_name('palm_spatial_tracking.py'),
                       Path(robot.data.__class__.__module__.replace('.', '/'))):
            if not source.is_absolute():
                import inspect
                source = Path(inspect.getfile(robot.data.__class__))
            filename = 'dependency_'+source.name
            shutil.copyfile(source, out/filename)
            result['dependencies'][filename] = dict(original=str(source), sha256=wiring.binding.sha256_file(source))
        model = csc.load_urdf(Path(target['urdf']))
        action_names, ids = [], []
        for term_name in live.action_manager.active_terms:
            term = live.action_manager.get_term(term_name)
            action_names.extend(term._joint_names)
            ids.extend(range(30) if isinstance(term._joint_ids, slice) else map(int, term._joint_ids))
            assert np.all(np.asarray(torch.as_tensor(term._scale).cpu()) == 1)
            assert np.all(np.asarray(torch.as_tensor(term._offset).cpu()) == 0)
        wiring.exact_channels(names, action_names, ids, names)
        result['action_names'] = action_names
        knee = names.index('rl_knee_joint')
        caps = np.asarray(result['readbacks']['velocity_caps'])
        for step in range(1, 3401):
            t = step*.005
            desired = np.zeros(30)
            desired[knee] = _target(max(t-5., 0.), .02) if t <= 11. else _target(t-11., -.02)
            action = torch.tensor([[desired[names.index(n)] for n in action_names]], device=args.device, dtype=torch.float32)
            live.action_manager.process_action(action)
            live.action_manager.apply_action()
            live.scene.write_data_to_sim()
            drive = _drive_targets(robot, backend, desired)
            live.sim.step(render=False)
            live.scene.update(.005)
            raw_q = backend(robot.root_view.get_dof_positions())
            raw_v = backend(robot.root_view.get_dof_velocities())
            q = robot.data.joint_pos.torch[0].cpu().numpy().copy()
            v = robot.data.joint_vel.torch[0].cpu().numpy().copy()
            contact = float(torch.linalg.vector_norm(live.scene['contact_forces'].data.net_forces_w, dim=-1).max())
            assert all(np.isfinite(a).all() for a in (q, v, raw_q, raw_v))
            assert np.array_equal(q, raw_q) and np.array_equal(v, raw_v), 'backend/cache mismatch'
            row = dict(t_s=t, q_rad=q.tolist(), velocity_rad_s=v.tolist(), backend_q_rad=raw_q.tolist(),
                       backend_velocity_rad_s=raw_v.tolist(), target_rad=desired.tolist(), backend_drive_targets=drive,
                       max_contact_n=contact, joint_force_probe=_joint_force_probe_sample(robot.root_view, backend, result['joint_force_probe']))
            result['samples'].append(row)
            assert abs(q).max() <= .35 and abs(q-desired).max() <= .35
            assert np.all(abs(v) < caps*.5) and contact <= 1., 'unsafe speed/contact'
            if step % 20 == 0:
                row['observation'] = observation_sample(
                    live, q, v, np.asarray([desired[names.index(n)] for n in action_names]), names)
            if step in (1000, 1580, 2180, 2780, 3380):
                result['entities'].append(dict(t_s=t, **_entity_snapshot(robot, model)))
        result.update(completed=True, stage='completed', status='velocity_probe_observed', steps_completed=len(result['samples']))
        wiring.write_json(out/'report.json', result)
        print('VELOCITY_PROBE_COMPLETED', args.force_timing, len(result['samples']), flush=True)
    except BaseException as error:
        result.update(error=repr(error), traceback=traceback.format_exc())
        try:
            wiring.write_json(out/'failure.json', result)
        finally:
            traceback.print_exc()
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(1)
    finally:
        if env is not None:
            env.close()
        if app is not None:
            app.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--approved_reference_sha256', required=True)
    parser.add_argument('--force_timing', choices=('legacy', 'per_iteration'), required=True)
    parser.add_argument('--out', type=Path, required=True)
    from isaaclab.app import AppLauncher
    AppLauncher.add_app_launcher_args(parser)
    run(parser.parse_args())
