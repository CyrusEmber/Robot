# -*- coding: utf-8 -*-
"""Smoke test for the Lizard-Rough-v3 teacher env: three obs groups + v3 wiring.

Validates end-to-end what check_obs_layout.py asserts statically:
* obs delivered as proprio/extero/priv groups with dims 90/208/83 (total 381)
* extero term order lf/rf/rl/rr (the network reshape contract)
* tilt termination and foot_clearance reward active; all obs/reward finite

The per-term layout is DERIVED from the live observation manager, never
hardcoded by slice index. Expected dims are pinned per recipe version
(versions/lizard/v3/NOTES.md).
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
from rl_exp.tasks.teacher_env_cfg import LizardRoughTeacherEnvCfg_V3_PLAY

EXPECTED_GROUP_DIMS = {"proprio": 90, "extero": 208, "priv": 83}  # v3 recipe
EXPECTED_EXTERO_ORDER = ("lf_foot_ring", "rf_foot_ring", "rl_foot_ring", "rr_foot_ring")

cfg = LizardRoughTeacherEnvCfg_V3_PLAY()
cfg.scene.num_envs = 2
env = gym.make("Lizard-Rough-Play-v3", cfg=cfg)
obs, _ = env.reset()

print("OBS_KEYS %s" % (sorted(obs.keys()),))
assert set(obs.keys()) == set(EXPECTED_GROUP_DIMS), f"obs groups {sorted(obs.keys())} != contract"
for group, dim in EXPECTED_GROUP_DIMS.items():
    assert obs[group].shape == (2, dim), f"group '{group}' shape {tuple(obs[group].shape)} != (2, {dim})"
    print("GROUP %s %s" % (group, tuple(obs[group].shape)))
assert sum(EXPECTED_GROUP_DIMS.values()) == 381

om = env.unwrapped.observation_manager
extero_terms = om.active_terms["extero"]
assert tuple(extero_terms) == EXPECTED_EXTERO_ORDER, f"extero order {extero_terms} != {EXPECTED_EXTERO_ORDER}"
print("EXTERO_ORDER %s" % (extero_terms,))

tm = env.unwrapped.termination_manager
assert "tilt" in tm.active_terms, f"tilt termination missing: {tm.active_terms}"
rm = env.unwrapped.reward_manager
assert "foot_clearance" in rm.active_terms, f"foot_clearance reward missing: {rm.active_terms}"
assert "feet_air_time" not in rm.active_terms, "feet_air_time reward should be replaced (D2)"
print("TERMS tilt+foot_clearance OK")

with torch.inference_mode():
    for _ in range(10):
        obs, rew, term, trunc, info = env.step(torch.zeros(2, env.unwrapped.action_manager.total_action_dim))
assert torch.isfinite(rew).all(), f"non-finite reward: {rew}"
for group, tensor in obs.items():
    assert torch.isfinite(tensor).all(), f"non-finite obs in group '{group}'"
# anti-regression: the ring channels must actually vary (a dead caster reads
# back a constant row and every downstream encoder silently learns nothing)
assert obs["extero"].std() > 1.0e-3, f"extero group is near-constant (std {obs['extero'].std():.2e})"
print("STEP_FINITE %s EXTERO_STD %.4f" % (bool(torch.isfinite(rew).all()), float(obs["extero"].std())))
print("=== DONE ===")
env.close()
