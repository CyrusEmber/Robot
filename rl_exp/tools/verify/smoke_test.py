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
assert policy_obs.numel() > 0, f"empty policy obs: {tuple(policy_obs.shape)}"
assert torch.isfinite(policy_obs).all(), "non-finite obs after reset"
print('OBS_DIM', tuple(policy_obs.shape))
act_dim = env.unwrapped.action_manager.total_action_dim
for i in range(10):
    with torch.inference_mode():
        obs, rew, term, trunc, info = env.step(torch.zeros(2, act_dim))
    obs_t = obs['policy'] if isinstance(obs, dict) else obs
    assert obs_t.shape == policy_obs.shape, f"obs shape drifted: {obs_t.shape} != {policy_obs.shape}"
    assert torch.isfinite(obs_t).all(), f"non-finite obs at step {i}"
    assert torch.isfinite(rew).all(), f"non-finite reward at step {i}"
print('STEPPED_OK', True)
env.close()
