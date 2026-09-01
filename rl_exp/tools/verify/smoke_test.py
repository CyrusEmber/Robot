# -*- coding: utf-8 -*-
"""Smoke test: build lizard env headless and step."""
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
from rl_exp.tasks.lizard_env_cfg import LizardFlatEnvCfg

cfg = LizardFlatEnvCfg()
cfg.scene.num_envs = 2
env = gym.make('Lizard-Velocity-Flat-v0', cfg=cfg)
obs, _ = env.reset()
policy_obs = obs['policy'] if isinstance(obs, dict) else obs
print('OBS_DIM', tuple(policy_obs.shape))
for i in range(10):
	with torch.inference_mode():
		step_out = env.step(torch.zeros(2, env.unwrapped.action_manager.total_action_dim))
dones = step_out[2]
print('STEPPED_OK', bool(dones.any()))
env.close()
