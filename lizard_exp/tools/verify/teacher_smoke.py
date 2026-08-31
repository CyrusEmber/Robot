# -*- coding: utf-8 -*-
"""Smoke test for the Lizard-Rough-v2 teacher env: obs dims + privileged data.

The per-term layout is DERIVED from the live observation manager (term order +
dims), never hardcoded by slice index: adding/renaming a term in v3 cannot
make this script silently read the wrong columns. The printed LAYOUT line is
the machine view of the obs layout; FAMILY.md's table is the human view --
compare them when either changes.

Expected total dim is pinned per recipe version (versions/vN/NOTES.md).
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

EXPECTED_POLICY_DIM = 308  # v2 recipe, see versions/v2/NOTES.md

cfg = LizardRoughTeacherEnvCfg_PLAY()
cfg.scene.num_envs = 2
env = gym.make("Lizard-Rough-Play-v2", cfg=cfg)
obs, _ = env.reset()
obs = obs["policy"]

print("OBS_SHAPE %s" % (tuple(obs.shape),))
print("ACTION_DIM %d" % env.unwrapped.action_manager.total_action_dim)

# derive the concatenated layout: (term_name, start, end) in concat order
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
    f"intentionally, bump EXPECTED_POLICY_DIM and FAMILY.md together"
)
print("LAYOUT " + " | ".join(f"{n}:{a}-{b}" for n, a, b in layout))


def seg(name: str) -> torch.Tensor:
    for n, start, end in layout:
        if n == name:
            return obs[:, start:end]
    raise KeyError(f"obs term '{name}' not in layout")


with torch.inference_mode():
    for _ in range(10):
        obs, _, _, _, _ = env.step(torch.zeros(2, env.unwrapped.action_manager.total_action_dim))
obs = obs["policy"]
print("OBS_FINITE %s" % bool(torch.isfinite(obs).all()))

# per-body mass truth: PLAY disables mass randomization -> nominal ~72 kg total
print("MASS_SUM %s" % seg("body_mass").sum(dim=-1).tolist())
# contact force vectors: settled stance -> z components carry the full weight
print("FOOT_FORCES_Z %s" % seg("foot_contact_forces")[:, 2::3].sum(dim=-1).tolist())
# terrain normals under the feet: flat spawn -> close to +Z world
print("FOOT_NORMAL_Z %s" % seg("foot_contact_normals")[:, 2::3].tolist())
# per-foot static friction: PLAY keeps the default material (no randomization)
print("FOOT_FRICTION %s" % seg("foot_friction").tolist())
print("THIGH_SHANK %s" % seg("thigh_shank_contacts").tolist())
# persistent external wrench: PLAY disables the force event -> exactly zero
print("BASE_WRENCH_MAX %.6f" % float(seg("base_external_wrench").abs().max()))
print("=== DONE ===")
env.close()
