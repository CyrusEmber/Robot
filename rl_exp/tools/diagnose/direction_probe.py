# -*- coding: utf-8 -*-
"""Direction probe: does the policy walk head-first under forward commands?

Headless instrument for the "lizard walks backwards" report (v6, 2026-09-08:
the rig's bone names were 180 deg off anatomy, so v6 paid for tail-first
walking). Runs the same deterministic policy loop as play.py (stock wrapper +
runner.load), drives the PLAY env with a forced forward window, and prints,
per 25 steps:

  cmd_vx   commanded forward speed [m/s] (base frame, +X = head by asset)
  v_head   dot(world velocity, head direction +X_b)  <- decisive: negative
           while cmd_vx > 0 means the policy genuinely walks tail-first
  disp_head  100-step displacement projected on head direction [m]

Asset ground truth (v8, blender/rename_flip_v8.py): the sphere HEAD is the
neck_pitch link at base +X (the old "tail" chain); the antenna tail is the
tail3_pitch link at -X (the old "neck1-3" chain).
"""

import argparse
import glob
import os

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(parser)
parser.add_argument("--num_envs", type=int, default=4)
parser.add_argument("--steps", type=int, default=500)
parser.add_argument("--vx_min", type=float, default=1.0)
parser.add_argument("--vx_max", type=float, default=3.0)
parser.add_argument("--checkpoint", default=None, help="default: newest model_*.pt in the newest v8 run dir")
parser.add_argument("--run_dir", default=None, help="default: newest run under logs/rsl_rl/lizard_rough_teacher_v8")
args_cli = parser.parse_args()
simulation_app = AppLauncher(args_cli).app

import torch

import isaaclab_tasks  # noqa: F401
from isaaclab.utils.math import quat_apply
from isaaclab_tasks.utils import load_cfg_from_registry
from rsl_rl.runners import OnPolicyRunner
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper, handle_deprecated_rsl_rl_cfg

from rl_exp.tasks.teacher_env_cfg import LizardRoughTeacherEnvCfg_V8_PLAY

RUN_GLOB = os.path.join("logs", "rsl_rl", "lizard_rough_teacher_v8", "*")

if args_cli.run_dir is None:
    args_cli.run_dir = max(glob.glob(RUN_GLOB), key=os.path.getmtime)
if args_cli.checkpoint is None:
    ckpts = glob.glob(os.path.join(args_cli.run_dir, "model_*.pt"))
    args_cli.checkpoint = max(ckpts, key=os.path.getmtime)
print(f"[INFO] run: {args_cli.run_dir}")
print(f"[INFO] checkpoint: {args_cli.checkpoint}")

cfg = LizardRoughTeacherEnvCfg_V8_PLAY()
cfg.scene.num_envs = args_cli.num_envs
cfg.commands.base_velocity.ranges.lin_vel_x = (args_cli.vx_min, args_cli.vx_max)
import gymnasium as gym  # noqa: E402

env = RslRlVecEnvWrapper(gym.make("Lizard-Rough-Play-v8", cfg=cfg), clip_actions=1.0)

agent_cfg = load_cfg_from_registry("Lizard-Rough-Play-v8", "rsl_rl_cfg_entry_point")
# strip legacy kwargs (e.g. 'stochastic') the installed rsl-rl rejects —
# same pit as ablation_harness v1.1 (v1 NOTES infra section)
import importlib.metadata as metadata  # noqa: E402

agent_cfg = handle_deprecated_rsl_rl_cfg(agent_cfg, metadata.version("rsl-rl-lib"))
runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
runner.load(args_cli.checkpoint)
policy = runner.get_inference_policy(device=env.unwrapped.device)

robot = env.unwrapped.scene["robot"]
cmd_term = env.unwrapped.command_manager.get_term("base_velocity")

obs = env.get_observations()
win_pos = None
with torch.inference_mode():
    for step in range(args_cli.steps):
        actions = policy(obs)
        obs, _, _, _ = env.step(actions)

        pos = robot.data.root_pos_w.torch
        win_pos = pos.clone() if win_pos is None else win_pos
        if step % 25 == 0 or step == args_cli.steps - 1:
            quat = robot.data.root_quat_w.torch
            n = quat.shape[0]
            dev = quat.device
            head_vec = torch.tensor([1.0, 0.0, 0.0], device=dev).expand(n, 3)
            head_dir = quat_apply(quat, head_vec)
            vel_w = robot.data.root_lin_vel_w.torch[:, :3]
            v_head = (vel_w * head_dir).sum(-1)
            cmd_vx = cmd_term.vel_command_b
            cmd_vx = cmd_vx.torch if hasattr(cmd_vx, "torch") else cmd_vx
            cmd_vx = cmd_vx[:, 0]
            disp = pos - win_pos
            disp_head = (disp * head_dir).sum(-1)
            if step % 100 == 99:
                win_pos = pos.clone()
            print(f"step {step:4d} | cmd_vx mean {cmd_vx.mean():+.2f} min {cmd_vx.min():+.2f} "
                  f"| v_head {v_head.mean():+.2f} | disp_head(100) {disp_head.mean():+.2f} m")

print("[DONE] negative v_head/disp_head with positive cmd_vx = tail-first walking confirmed")
simulation_app.close()
