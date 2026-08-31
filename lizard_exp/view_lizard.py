# -*- coding: utf-8 -*-
"""View the lizard in Isaac Sim GUI without a checkpoint.

Holds default joint pose with zero actions. Ctrl+C to quit.
Usage: python view_lizard.py --viz kit
"""
import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym
import torch

import isaaclab_tasks  # noqa: F401
from lizard_exp.tasks.lizard_env_cfg import LizardFlatEnvCfg_PLAY

cfg = LizardFlatEnvCfg_PLAY()
cfg.scene.num_envs = 4
if hasattr(cfg.events, 'reset_robot_joints'):
    cfg.events.reset_robot_joints = None
env = gym.make('Lizard-Velocity-Flat-Play-v0', cfg=cfg)
env.reset()

num_envs = env.unwrapped.num_envs
action_dim = env.unwrapped.action_manager.total_action_dim
actions = torch.zeros(num_envs, action_dim)
try:
	while simulation_app.is_running():
		with torch.inference_mode():
			env.step(actions)
except KeyboardInterrupt:
	pass
env.close()
