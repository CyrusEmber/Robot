# -*- coding: utf-8 -*-
"""View the lizard standing on a recipe version's actual terrain (pre-training eyeball check).

GUI by default: zero actions, no randomization (PLAY wiring), so the
sole-vs-bump scale is directly readable. Ctrl+C to quit. With --steps N the
script auto-exits after N steps -- use --headless --steps for smoke checks
(env construction + terrain load without a window). To view a trained policy
on a terrain, use the standard play script instead (checkpoint needed).

Usage:
  python view_terrain.py --viz kit                                   # flat (default)
  python view_terrain.py --viz kit --task Lizard-Rough-Play-v4       # v4 rubble
  python view_terrain.py --headless --task Lizard-Rough-Play-v4 --steps 10
"""
import argparse
import importlib

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--task", default="Lizard-Velocity-Flat-Play-v0",
                    help="Registered task id; PLAY variants have no randomization.")
parser.add_argument("--num-envs", type=int, default=4,
                    help="Number of envs (more envs = more sub-terrains visible).")
parser.add_argument("--steps", type=int, default=0,
                    help="Auto-exit after N steps (0 = run until Ctrl+C, GUI mode).")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402

import isaaclab_tasks  # noqa: F401,E402  -- registers the lizard task ids

# resolve the task's env cfg class from the registry (no per-version map to drift)
spec = gym.spec(args_cli.task)
module_name, class_name = spec.kwargs["env_cfg_entry_point"].split(":")
cfg_cls = getattr(importlib.import_module(module_name), class_name)

cfg = cfg_cls()
cfg.scene.num_envs = args_cli.num_envs
# hold the default pose across resets (same trick view_lizard used on flat)
if hasattr(cfg.events, "reset_robot_joints"):
    cfg.events.reset_robot_joints = None

env = gym.make(args_cli.task, cfg=cfg)
env.reset()

num_envs = env.unwrapped.num_envs
action_dim = env.unwrapped.action_manager.total_action_dim
actions = torch.zeros(num_envs, action_dim)

step = 0
try:
    while simulation_app.is_running():
        with torch.inference_mode():
            env.step(actions)
        step += 1
        if args_cli.steps and step >= args_cli.steps:
            break
except KeyboardInterrupt:
    pass
env.close()
