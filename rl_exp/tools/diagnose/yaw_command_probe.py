# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Probe native yaw command sampling and observation delivery [rad/s], without training.

Keep the task's native command timer; zero actions isolate command wiring from policy
performance. Run for more than one resampling interval and retain a JSON report.
"""

import argparse
import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def probe(args) -> dict:
    """Check both yaw signs, observation delivery and timed resampling [rad/s, s]."""
    import gymnasium as gym
    import torch
    from isaaclab.utils.string import string_to_callable
    from isaaclab_tasks.utils.hydra import resolve_presets
    import rl_exp.tasks  # noqa: F401

    cfg = resolve_presets(string_to_callable(gym.spec(args.task).kwargs['env_cfg_entry_point'])())
    cfg.scene.num_envs, cfg.seed = 16, 42
    cfg.commands.base_velocity.debug_vis = False
    cfg.observations.policy.enable_corruption = False
    env = gym.make(args.task, cfg=cfg)
    try:
        live = env.unwrapped
        obs, _ = env.reset()
        command = live.command_manager.get_term('base_velocity')
        manager = live.observation_manager
        names = manager.active_terms['policy']
        dims = manager.group_obs_term_dim['policy']
        index = names.index('velocity_commands')
        offset = sum(shape[0] for shape in dims[:index])
        assert dims[index] == (3,)
        interval = cfg.commands.base_velocity.resampling_time_range
        assert interval[0] == interval[1] == 10.
        snapshots = []
        observation_ok = True
        bounds_ok = True
        resets = 0
        initial_counter = command.command_counter.clone()
        steps = round((interval[1] + .1)/live.step_dt)
        with torch.inference_mode():
            for step in range(steps + 1):
                current = live.command_manager.get_command('base_velocity')
                observation_ok &= bool(torch.allclose(obs['policy'][:, offset:offset+3], current))
                bounds_ok &= bool(((current[:, 2].abs() <= .5) &
                                   (current[:, 0] >= 0.) & (current[:, 0] <= 3.) &
                                   current[:, 1].eq(0.)).all())
                if step in (0, round(9.9/live.step_dt), steps):
                    snapshots.append(dict(time_s=step*live.step_dt,
                                          commands=current.cpu().tolist(),
                                          counter=command.command_counter.cpu().tolist()))
                if step < steps:
                    obs, _, terminated, truncated, _ = env.step(
                        torch.zeros(live.num_envs, live.action_manager.total_action_dim, device=live.device))
                    resets += int((terminated | truncated).sum())
        initial = torch.tensor(snapshots[0]['commands'])[:, 2]
        both_signs = bool((initial > .05).any() and (initial < -.05).any())
        timed_resampling = bool((command.command_counter > initial_counter).all()) and resets == 0
        passed = observation_ok and bounds_ok and both_signs and timed_resampling
        return dict(task=args.task, seed=42, num_envs=live.num_envs, step_dt_s=live.step_dt,
                    resampling_time_range_s=interval, obs_width=obs['policy'].shape[1],
                    command_observation_offset=offset, snapshots=snapshots, reset_count=resets,
                    observation_ok=observation_ok, bounds_ok=bounds_ok, both_signs=both_signs,
                    timed_resampling=timed_resampling, passed=passed)
    finally:
        env.close()


def main() -> int:
    from isaaclab.app import AppLauncher

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', default='Lizard2-Flat-Play-v6')
    parser.add_argument('--out', type=Path, required=True)
    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('--out must be a new report path')
    app = AppLauncher(args).app
    report = dict(task=args.task, passed=False)
    try:
        report = probe(args)
    except BaseException as error:
        report['error'] = repr(error)
        traceback.print_exc()
    finally:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        print(json.dumps(report), flush=True)
        print('YAW_COMMAND_PROBE_OK' if report['passed'] else 'YAW_COMMAND_PROBE_FAILED', flush=True)
        app.close(exit_code=0 if report['passed'] else 1)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
