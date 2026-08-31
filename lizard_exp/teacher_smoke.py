# -*- coding: utf-8 -*-
"""Smoke test for the Lizard-Rough-v2 teacher env: obs dims + privileged data.

Privileged tail layout (from the end, see versions/v2/NOTES.md):
wrench 6 | thigh_shank 8 | friction 4 | normals 12 | forces 12 | mass 27 |
air 4 | contact 4 | true_vel 6 | scan 135 | proprio 90  ->  total 308
"""

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
env = gym.make("Lizard-Rough-Play-v2", cfg=cfg)
obs, _ = env.reset()
obs = obs["policy"]

print("OBS_SHAPE %s" % (tuple(obs.shape),))
print("ACTION_DIM %d" % env.unwrapped.action_manager.total_action_dim)

with torch.inference_mode():
    for _ in range(10):
        obs, _, _, _, _ = env.step(torch.zeros(2, env.unwrapped.action_manager.total_action_dim))
obs = obs["policy"]
print("OBS_FINITE %s" % bool(torch.isfinite(obs).all()))

mass = obs[:, -69:-42]
forces = obs[:, -42:-30]
normals = obs[:, -30:-18]
friction = obs[:, -18:-14]
thigh_shank = obs[:, -14:-6]
wrench = obs[:, -6:]

# per-body mass truth: PLAY disables mass randomization -> nominal ~72 kg total
print("MASS_SUM %s" % mass.sum(dim=-1).tolist())
# contact force vectors: settled stance -> z components carry the full weight
print("FOOT_FORCES_Z %s" % forces[:, 2::3].sum(dim=-1).tolist())
# terrain normals under the feet: flat spawn -> close to +Z world
print("FOOT_NORMAL_Z %s" % normals[:, 2::3].tolist())
# per-foot static friction: PLAY keeps the default material (no randomization)
print("FOOT_FRICTION %s" % friction.tolist())
print("THIGH_SHANK %s" % thigh_shank.tolist())
# persistent external wrench: PLAY disables the force event -> exactly zero
print("BASE_WRENCH_MAX %.6f" % float(wrench.abs().max()))
print("=== DONE ===")
env.close()
