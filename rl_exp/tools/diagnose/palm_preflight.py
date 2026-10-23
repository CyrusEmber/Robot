# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Short native-task zero-action preflight [s, rad, rad/s, N, N*m].

No policy, reset/terrain/drive overrides, extra sensors or performance verdict.
Use --viz kit --num_envs 4 --hold_seconds 60 for visual inspection; --viz none
without --num_envs checks the registered training environment count. Outputs
must be new directories under rl_exp/out. The report preserves failures too.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import time
import traceback

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from rl_exp.tools.runrecord import binding  # noqa: E402


def main() -> int:
    import gymnasium as gym
    import torch
    import rl_exp.tasks  # noqa: F401
    from isaaclab_tasks.utils import add_launcher_args, launch_simulation, resolve_task_config, setup_preset_cli
    from rl_exp.tasks import obs_protocol
    from rl_exp.tools.verify import cfg_snapshot

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', default='Lizard2-Flat-v4', choices=['Lizard2-Flat-v4'])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--num_envs', type=int)
    parser.add_argument('--steps', type=int, default=100)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--hold_seconds', type=float, default=0.)
    add_launcher_args(parser)
    args, remaining = setup_preset_cli(parser)
    if remaining or args.steps < 1 or args.hold_seconds < 0 or (args.num_envs is not None and args.num_envs < 1):
        parser.error('positive env/step counts, nonnegative hold, and no preset overrides required')
    out = args.out.resolve()
    if REPO/'rl_exp/out' not in out.parents or out.exists():
        parser.error('--out must be a new directory under rl_exp/out')
    out.mkdir(parents=True)
    (out/'source.py').write_bytes(Path(__file__).read_bytes())
    report = dict(completed=False, closed=False, task=args.task, argv=sys.argv,
                  source_sha256=binding.sha256_file(out/'source.py'),
                  git_rev=binding.git_run(REPO, 'rev-parse', 'HEAD'),
                  tag_rev=binding.git_run(REPO, 'rev-parse', 'lizard2-main-v4'),
                  requested_control_steps=args.steps, control_steps=0, samples=[])
    started = time.monotonic()
    env = None
    try:
        # The native Hydra resolver must only see the unconsumed preset arguments.
        sys.argv = [sys.argv[0]]
        cfg, _ = resolve_task_config(args.task, '')
        report['default_num_envs'] = cfg.scene.num_envs
        if args.num_envs is not None:
            cfg.scene.num_envs = args.num_envs
        cfg.seed = args.seed
        if args.device is not None:
            cfg.sim.device = args.device
        if args.hold_seconds:
            cfg.viewer.eye, cfg.viewer.lookat = (3.5, -3.5, 2.4), (0., 0., .45)
        target = obs_protocol.load_diagnostic_target(None, cfg, args.task)
        report.update(num_envs=cfg.scene.num_envs, seed=cfg.seed, device=cfg.sim.device,
                      target=target, asset_sha256={k: binding.sha256_file(Path(target[k]))
                                                   for k in ('target', 'urdf')})
        (out/'config.json').write_text(json.dumps(cfg_snapshot.snapshot(cfg), indent=1)+'\n',
                                      encoding='utf-8', newline='\n')
        torch.manual_seed(args.seed)
        @contextmanager
        def runtime_with_report():
            # Kit may terminate the interpreter from its close callback. Persist
            # before the native context tears the app down, including failures.
            with launch_simulation(cfg, args):
                try:
                    yield
                except BaseException as error:
                    report['error'] = repr(error)
                    report['traceback'] = traceback.format_exc()
                    raise
                finally:
                    if env is not None and not report['closed']:
                        env.close()
                        report['closed'] = True
                    report['elapsed_seconds'] = time.monotonic()-started
                    (out/'report.json').write_text(json.dumps(report, indent=1)+'\n',
                                                   encoding='utf-8', newline='\n')
                    ok = report['completed'] and report['closed'] and 'error' not in report
                    print('PALM_PREFLIGHT_OK' if ok else 'PALM_PREFLIGHT_FAILED', out, flush=True)

        with runtime_with_report():
            import warp as wp
            env = gym.make(args.task, cfg=cfg)
            live = env.unwrapped
            robot, sensor, manager = live.scene['robot'], live.scene['contact_forces'], live.action_manager
            obs_protocol.validate_diagnostic_runtime(target, cfg, robot, sensor, manager)
            observation, _ = env.reset()
            report.update(action_dim=manager.total_action_dim, joint_names=list(robot.joint_names),
                          body_names=list(robot.body_names), sensor_body_names=list(sensor.body_names),
                          dt=live.physics_dt, decimation=cfg.decimation,
                          terrain_type=cfg.scene.terrain.terrain_type,
                          sensor_period=sensor.cfg.update_period, sensor_history=sensor.cfg.history_length,
                          lazy_sensor_update=cfg.scene.lazy_sensor_update)
            scene = live.sim.stage.GetPrimAtPath(cfg.sim.physics_prim_path)
            report['backend'] = dict(
                solver=scene.GetAttribute('physxScene:solverType').Get(),
                force_timing=scene.GetAttribute('physxScene:enableExternalForcesEveryIteration').Get(),
                fixed_base=robot.is_fixed_base)
            assert report['backend'] == dict(solver='TGS', force_timing=False, fixed_base=False)
            params, _ = obs_protocol._params_document(args.task)
            for key, method, field in (('kp', 'get_dof_stiffnesses', 'stiffness'),
                                       ('kd', 'get_dof_dampings', 'damping'),
                                       ('effort', 'get_dof_max_forces', 'effort_limit'),
                                       ('speed', 'get_dof_max_velocities', 'velocity_limit')):
                values = {joint: value for group in params['actuators'].values()
                          for joint, value in group[field].items()}
                actual = wp.to_torch(getattr(robot.root_view, method)())
                expected = torch.tensor([values[j] for j in robot.joint_names], device=actual.device)
                assert torch.equal(actual, expected.expand_as(actual)), key
                report['backend'][key] = actual[0].cpu().tolist()
            resets = 0

            def sample(step, obs):
                tensors = dict(q=robot.data.joint_pos.torch, dq=robot.data.joint_vel.torch,
                               root_pos=robot.data.root_pos_w.torch,
                               contact=sensor.data.net_forces_w.torch,
                               policy=obs['policy'])
                assert all(torch.isfinite(t).all().item() for t in tensors.values()), 'nonfinite state'
                target_vel = wp.to_torch(robot.root_view.get_dof_velocity_targets())
                assert torch.count_nonzero(target_vel).item() == 0, 'nonzero velocity reference'
                return dict(step=step, policy_shape=list(obs['policy'].shape),
                            root_env0=tensors['root_pos'][0].cpu().tolist(),
                            max_abs_q=float(tensors['q'].abs().max()),
                            max_abs_dq=float(tensors['dq'].abs().max()),
                            nonzero_contact_envs=int((tensors['contact'].abs().sum((1, 2)) > 0).sum()),
                            velocity_target_max_abs=float(target_vel.abs().max()))

            report['samples'].append(sample(0, observation))
            actions = torch.zeros((live.num_envs, manager.total_action_dim), device=live.device)
            for step in range(1, args.steps+1):
                with torch.inference_mode():
                    observation, _, terminated, truncated, _ = env.step(actions)
                resets += int((terminated | truncated).sum())
                current = sample(step, observation)
                report['control_steps'] = step
                if step in (1, args.steps):
                    report['samples'].append(current)
            report.update(reset_count=resets, physics_steps=args.steps*cfg.decimation,
                          simulated_seconds=args.steps*live.step_dt,
                          torch_peak_allocated_bytes=torch.cuda.max_memory_allocated()
                          if str(live.device).startswith('cuda') else None)
            print('PREFLIGHT_HOLD_READY', out, flush=True)
            if args.hold_seconds:
                live.sim.pause()
                until = time.monotonic()+args.hold_seconds
                while time.monotonic() < until:
                    live.sim.render()
                    time.sleep(.05)
            report['completed'] = True
            env.close()
            report['closed'] = True
    except BaseException as error:
        if not (isinstance(error, SystemExit) and error.code in (0, None)
                and report['completed'] and report['closed']):
            report['error'] = repr(error)
            traceback.print_exc()
    finally:
        if env is not None and not report['closed']:
            try:
                env.close()
                report['closed'] = True
            except BaseException:
                traceback.print_exc()
        report['elapsed_seconds'] = time.monotonic()-started
        (out/'report.json').write_text(json.dumps(report, indent=1)+'\n', encoding='utf-8', newline='\n')
    success = report['completed'] and report['closed'] and 'error' not in report
    print('PALM_PREFLIGHT_OK' if success else 'PALM_PREFLIGHT_FAILED', out, flush=True)
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
