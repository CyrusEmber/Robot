# -*- coding: utf-8 -*-
"""Smoke test for the Lizard-Rough-v5 teacher env: three obs groups + v5 wiring.

Validates end-to-end what check_obs_layout.py asserts statically:
* obs delivered as proprio/extero/priv groups with dims 90/208/83 (total 381)
* v5 anti-collapse reward set active (track_lin_vel_xy_lin / feet_slide /
  belly_contact_force), exp tracking retired, no speed curriculum
* tilt termination active; all obs/reward finite

The per-term layout is DERIVED from the live observation manager, never
hardcoded by slice index. Expected dims are pinned per recipe version
(versions/lizard/v5/NOTES.md).
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
from rl_exp.tasks.teacher_env_cfg import LizardRoughTeacherEnvCfg_V5_PLAY

EXPECTED_GROUP_DIMS = {"proprio": 90, "extero": 208, "priv": 83}  # v5 recipe
EXPECTED_EXTERO_ORDER = ("lf_foot_ring", "rf_foot_ring", "rl_foot_ring", "rr_foot_ring")

cfg = LizardRoughTeacherEnvCfg_V5_PLAY()
cfg.scene.num_envs = 2
env = gym.make("Lizard-Rough-Play-v5", cfg=cfg)
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
for required in ("track_lin_vel_xy_lin", "feet_slide", "belly_contact_force", "foot_clearance"):
    assert required in rm.active_terms, f"v5 reward '{required}' missing: {rm.active_terms}"
assert "track_lin_vel_xy_exp" not in rm.active_terms, "v5 must replace the exp tracking kernel"
assert "track_ang_vel_z_exp" in rm.active_terms, "yaw tracking stays (user decision)"
cm = env.unwrapped.curriculum_manager
assert "speed_curriculum" not in cm.active_terms, "v5 must drop the staged speed curriculum"
assert "terrain_levels" not in cm.active_terms, "v5 PLAY must drop the SIR terrain curriculum (no roaming)"
print("TERMS v5 rewards + no speed curriculum + no SIR in PLAY OK")

cmd = env.unwrapped.command_manager.get_term("base_velocity").vel_command_b
assert (cmd[:, 0] >= -1.0e-6).all(), f"forward-only commands violated: {cmd[:, 0]}"
print("COMMANDS forward-only OK (sample vx: %s)" % (cmd[:, 0].tolist(),))

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
env.close()

# --- TRAIN env (2 envs): the SIR curriculum must instantiate against the REAL
# terrain importer (8-type column split from the generator proportions) and
# run its reset + bookkeeping paths on live tensors -- the unit test only
# covers mocked terrains.
from rl_exp.tasks.teacher_env_cfg import LizardRoughTeacherEnvCfg_V5  # noqa: E402

train_cfg = LizardRoughTeacherEnvCfg_V5()
train_cfg.scene.num_envs = 2
train_env = gym.make("Lizard-Rough-v5", cfg=train_cfg)
train_obs, _ = train_env.reset()
for group, dim in EXPECTED_GROUP_DIMS.items():
    assert train_obs[group].shape == (2, dim), f"train group '{group}' shape {tuple(train_obs[group].shape)}"

cm = train_env.unwrapped.curriculum_manager
assert "terrain_levels" in cm.active_terms, f"SIR term missing in TRAIN: {cm.active_terms}"
terrain = train_env.unwrapped.scene.terrain
num_rows, num_cols = terrain.terrain_origins.shape[0], terrain.terrain_origins.shape[1]
assert num_rows == 10 and num_cols == 20, f"terrain grid {num_rows}x{num_cols} != 10x20"
for i in range(2):
    lvl = terrain.terrain_levels[i].item()
    col = terrain.terrain_types[i].item()
    assert 0 <= lvl < num_rows and 0 <= col < num_cols, f"env {i} spawned at ({lvl}, {col}) out of grid"
    assert torch.equal(terrain.env_origins[i], terrain.terrain_origins[lvl, col]), f"env {i} origin mismatch"
print("SIR_TRAIN origins re-pointed inside the 10x20 grid OK (levels %s cols %s)" %
      (terrain.terrain_levels.tolist(), terrain.terrain_types.tolist()))

with torch.inference_mode():
    for _ in range(30):
        train_obs, rew, term, trunc, info = train_env.step(
            torch.zeros(2, train_env.unwrapped.action_manager.total_action_dim)
        )
assert torch.isfinite(rew).all(), f"non-finite train reward: {rew}"
lvl_log = info.get("log", {}).get("Curriculum/terrain_levels")
assert lvl_log is not None and torch.isfinite(torch.tensor(float(lvl_log))), f"Curriculum/terrain_levels {lvl_log}"
print("SIR_TRAIN stepped, Curriculum/terrain_levels = %s" % (lvl_log,))
train_env.close()
print("=== DONE ===")
