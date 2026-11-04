# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Record paired policy/zero-action landing state before automatic resets."""

import argparse
import importlib.metadata
import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument('--checkpoint', required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--speed', type=float, default=0.5)
parser.add_argument('--seed', type=int, default=123)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
if args.out.exists():
    parser.error('output already exists')
app = AppLauncher(args).app

try:
    import gymnasium as gym
    import torch
    from isaaclab.utils.string import string_to_callable
    from isaaclab_tasks.utils.hydra import resolve_presets
    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper, handle_deprecated_rsl_rl_cfg
    from rsl_rl.runners import OnPolicyRunner
    import rl_exp.tasks  # noqa: F401
    from ablation_harness.components.dr_controller import apply_eval_mode
    from ablation_harness.record import checkpoint_digest

    spec = gym.spec('Lizard2-Flat-Play-v6')
    cfg = resolve_presets(string_to_callable(spec.kwargs['env_cfg_entry_point'])())
    cfg.scene.num_envs, cfg.seed = 4, args.seed
    cfg.episode_length_s = 20.0
    apply_eval_mode(cfg, 'nominal')
    agent = handle_deprecated_rsl_rl_cfg(string_to_callable(spec.kwargs['rsl_rl_cfg_entry_point'])(),
                                         importlib.metadata.version('rsl-rl-lib'))
    env = gym.make('Lizard2-Flat-Play-v6', cfg=cfg)
    wrapper = RslRlVecEnvWrapper(env, clip_actions=agent.clip_actions)
    live = env.unwrapped
    runner = OnPolicyRunner(wrapper, agent.to_dict(), log_dir=None, device=live.device)
    runner.load(args.checkpoint)
    policy = runner.get_inference_policy(device=live.device)
    robot, sensor = live.scene['robot'], live.scene['contact_forces']
    rows = []
    original_compute = live.termination_manager.compute
    step = 0

    def capture():
        done = original_compute()
        d = robot.data
        forces = torch.linalg.vector_norm(sensor.data.net_forces_w_history.torch, dim=-1).amax(dim=1)
        rows.append(dict(step=step, time_s=step * live.step_dt,
                         position=d.joint_pos.torch.cpu().tolist(),
                         target=d.joint_pos_target.torch.cpu().tolist(),
                         velocity=d.joint_vel.torch.cpu().tolist(),
                         body_pos=d.body_link_pos_w.torch.cpu().tolist(),
                         root_quat=d.root_quat_w.torch.cpu().tolist(),
                         forces=forces.cpu().tolist(), done=done.cpu().tolist()))
        return done

    live.termination_manager.compute = capture
    command = live.command_manager.get_term('base_velocity')
    command.vel_command_b[:] = torch.tensor([args.speed, 0., 0.], device=live.device)
    obs = wrapper.get_observations()
    leg_term = live.action_manager.get_term('joint_pos_legs')
    leg_names = leg_term._joint_names
    fold_indices = [i for i, name in enumerate(leg_names) if 'elbow' in name or 'knee' in name]
    assert len(fold_indices) == 4 and live.action_manager.active_terms[0] == 'joint_pos_legs'
    for step in range(1, 51):
        command.vel_command_b[:] = torch.tensor([args.speed, 0., 0.], device=live.device)
        with torch.no_grad():
            actions = policy(obs)
            actions[1].zero_()
            actions[2, fold_indices] = 0.0
            keep = actions[3, fold_indices].clone()
            actions[3].zero_()
            actions[3, fold_indices] = keep
            obs, _, _, _ = wrapper.step(actions)
    report = dict(checkpoint=checkpoint_digest(args.checkpoint), task='Lizard2-Flat-Play-v6',
                  speed=args.speed, seed=args.seed, dt=live.step_dt,
                  cases=['policy', 'zero', 'policy_without_elbow_knee', 'elbow_knee_only'],
                  initial_command_set_before_observation=True,
                  leg_action_names=leg_names, fold_action_indices=fold_indices,
                  joint_names=robot.joint_names, body_names=robot.body_names,
                  sensor_body_names=sensor.body_names, rows=rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print('LANDING_PROBE_OK', args.out, flush=True)
    wrapper.close()
    app.close(exit_code=0)
except BaseException:
    traceback.print_exc()
    app.close(exit_code=1)
    raise
