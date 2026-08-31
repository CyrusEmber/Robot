# -*- coding: utf-8 -*-
"""Smoke test for the Lizard-Rough-v1 teacher env: obs dims + privileged data."""

import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
simulation_app = AppLauncher(args_cli).app

import gymnasium as gym
import torch

import isaaclab_tasks  # noqa: F401
from lizard_exp.tasks.teacher_env_cfg import (
    LizardRoughTeacherEnvCfg_PLAY,
)

cfg = LizardRoughTeacherEnvCfg_PLAY()
cfg.scene.num_envs = 2
env = gym.make("Lizard-Rough-Play-v1", cfg=cfg)
obs, _ = env.reset()
obs = obs["policy"]

print("OBS_SHAPE %s" % (tuple(obs.shape),))
print("ACTION_DIM %d" % env.unwrapped.action_manager.total_action_dim)

with torch.inference_mode():
    for _ in range(10):
        obs, _, _, _, _ = env.step(torch.zeros(2, env.unwrapped.action_manager.total_action_dim))
obs = obs["policy"]
print("OBS_FINITE %s" % bool(torch.isfinite(obs).all()))
# privileged slice sanity: last 27 dims are the per-body mass truth (nominal
# total ~72 kg in the PLAY variant, which disables mass randomization)
print("MASS_SUM %s" % obs[:, -27:].sum(dim=-1).tolist())
print("FOOT_CONTACT %s" % obs[:, -35:-31].tolist())
print("=== DONE ===")
env.close()
