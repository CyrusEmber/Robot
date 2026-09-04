# -*- coding: utf-8 -*-
"""Smoke test for the parkour Climb expert env: obs dims + position command.

Layout is derived from the live observation manager (term order + dims), never
hardcoded by slice index. Expected total dim is pinned in the parkour line
SSOT (versions/lizard/parkour/parkour_params.yaml obs_layout).
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
from rl_exp.tasks.parkour_env_cfg import ParkourClimbEnvCfg_PLAY

EXPECTED_POLICY_DIM = 278  # parkour_params.yaml obs_layout (single policy group)

cfg = ParkourClimbEnvCfg_PLAY()
cfg.scene.num_envs = 2
env = gym.make("Lizard-Parkour-Climb-Play-v1", cfg=cfg)
obs, _ = env.reset()
obs = obs["policy"]

print("OBS_SHAPE %s" % (tuple(obs.shape),))
print("ACTION_DIM %d" % env.unwrapped.action_manager.total_action_dim)

om = env.unwrapped.observation_manager
term_names = om.active_terms["policy"]
term_dims = [int(d[0]) for d in om.group_obs_term_dim["policy"]]
layout = []
cursor = 0
for name, dim in zip(term_names, term_dims):
    layout.append((name, cursor, cursor + dim))
    cursor += dim
assert cursor == obs.shape[-1], f"layout sum {cursor} != obs dim {obs.shape[-1]}"
assert cursor == EXPECTED_POLICY_DIM, (
    f"policy obs {cursor} != expected {EXPECTED_POLICY_DIM}; if the layout changed "
    f"intentionally, update parkour_params.yaml obs_layout together"
)
print("LAYOUT " + " | ".join(f"{n}:{a}-{b}" for n, a, b in layout))


def seg(name: str) -> torch.Tensor:
    for n, start, end in layout:
        if n == name:
            return obs[:, start:end]
    raise KeyError(f"obs term '{name}' not in layout")


cmd_term = env.unwrapped.command_manager.get_term("position")

with torch.inference_mode():
    for _ in range(20):
        obs, rew, _, _, _ = env.step(torch.zeros(2, env.unwrapped.action_manager.total_action_dim))
obs = obs["policy"]

print("OBS_FINITE %s" % bool(torch.isfinite(obs).all()))
cmd = seg("position_commands")
print("CMD_SHAPE %s" % (tuple(cmd.shape),))
print("CMD_FINITE %s" % bool(torch.isfinite(cmd).all()))
print("CMD_T_STAR %s" % cmd[:, 3].tolist())
print("CMD_DELTA_R %s" % cmd[:, :2].tolist())
metrics = cmd_term.metrics
print("CMD_METRICS " + " ".join(
    f"{k}={float(metrics[k].mean()):.3f}" for k in sorted(metrics)
))
# reward terms all exercised by the steps above (any bad field access raises)
print("EP_REW %s" % rew.tolist())
print("=== DONE ===")
env.close()
