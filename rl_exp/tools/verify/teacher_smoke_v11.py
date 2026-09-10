# -*- coding: utf-8 -*-
"""Smoke test for the Lizard-Rough-v11 teacher env: obs groups + joint SIR wiring.

v11 = v10 recipe (tilt removed) + the joint particle terrain curriculum
(plan versions/lizard/v11/PLAN.md). Same contract as teacher_smoke_v8.py
except where noted:
* obs delivered as proprio/extero/priv groups with dims 90/208/83 (total 381)
* v5 anti-collapse reward set active, exp tracking retired, no speed curriculum
* tilt termination REMOVED (v10 single variable; only time_out terminates)
* PLAY drops the joint SIR; its ParticleVelocityCommand falls back to the
  (0, 3) uniform range sample
* TRAIN swaps in the param-sampled terrain grid (4 x 120, one sub-terrain per
  parameter combination) and the joint SIR term; commands come from the
  particle's velocity bucket (+- jitter)

The per-term layout is DERIVED from the live observation manager, never
hardcoded by slice index. Expected dims are pinned per recipe version
(versions/lizard/v11/PLAN.md).
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
from rl_exp.tasks.teacher_env_cfg import LizardRoughTeacherEnvCfg_V11_PLAY
from rl_exp.tasks.teacher_mdp import ParticleVelocityCommand

EXPECTED_GROUP_DIMS = {"proprio": 90, "extero": 208, "priv": 83}  # v11 recipe (= v5..v10)
EXPECTED_EXTERO_ORDER = ("lf_foot_ring", "rf_foot_ring", "rl_foot_ring", "rr_foot_ring")
V11_YAML = r"rl_exp\versions\lizard\v11\lizard_params.yaml"

cfg = LizardRoughTeacherEnvCfg_V11_PLAY()
cfg.scene.num_envs = 2
env = gym.make("Lizard-Rough-Play-v11", cfg=cfg)
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
assert "tilt" not in tm.active_terms, f"v11 must drop the tilt termination: {tm.active_terms}"
assert "time_out" in tm.active_terms, f"time_out termination missing: {tm.active_terms}"
rm = env.unwrapped.reward_manager
for required in ("track_lin_vel_xy_lin", "feet_slide", "belly_contact_force", "foot_clearance"):
    assert required in rm.active_terms, f"v11 reward '{required}' missing: {rm.active_terms}"
assert "track_lin_vel_xy_exp" not in rm.active_terms, "v11 must replace the exp tracking kernel"
assert "track_ang_vel_z_exp" in rm.active_terms, "yaw tracking stays (user decision)"
cm = env.unwrapped.curriculum_manager
assert "speed_curriculum" not in cm.active_terms, "v11 must drop the staged speed curriculum"
assert "joint_sir" not in cm.active_terms, "v11 PLAY must drop the joint SIR curriculum (no roaming)"
print("TERMS v11 rewards + no tilt + no speed curriculum + no joint SIR in PLAY OK")

cmd = env.unwrapped.command_manager.get_term("base_velocity")
assert isinstance(cmd, ParticleVelocityCommand), f"PLAY command term is {type(cmd).__name__}, not ParticleVelocityCommand"
assert (cmd.vel_command_b[:, 0] >= -1.0e-6).all(), f"forward-only commands violated: {cmd.vel_command_b[:, 0]}"
print("COMMANDS forward-only fallback OK (sample vx: %s)" % (cmd.vel_command_b[:, 0].tolist(),))

# v6.1+ spine unlock rides the yaml spine_scale (chest + neck + tail1-3, 10 joints)
spine_scale = float(env.unwrapped.action_manager.get_term("joint_pos_spine")._scale)
assert spine_scale == 0.25, f"v11 spine action scale {spine_scale} != yaml 0.25"
print("SPINE_UNLOCKED scale=%.2f OK" % spine_scale)

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

# --- TRAIN env (2 envs): the joint SIR curriculum must instantiate against
# the REAL terrain importer (combo column split from the generator proportions)
# and run its reset + bookkeeping paths on live tensors -- the unit test only
# covers mocked terrains.
from rl_exp.tasks.teacher_env_cfg import LizardRoughTeacherEnvCfg_V11  # noqa: E402

train_cfg = LizardRoughTeacherEnvCfg_V11()
train_cfg.scene.num_envs = 2
train_env = gym.make("Lizard-Rough-v11", cfg=train_cfg)
train_obs, _, _, _, train_info = train_env.reset()
for group, dim in EXPECTED_GROUP_DIMS.items():
    assert train_obs[group].shape == (2, dim), f"train group '{group}' shape {tuple(train_obs[group].shape)}"

cm = train_env.unwrapped.curriculum_manager
assert "joint_sir" in cm.active_terms, f"joint SIR term missing in TRAIN: {cm.active_terms}"
assert "terrain_levels" not in cm.active_terms, "TRAIN must drop the frozen v5 row SIR"
terrain = train_env.unwrapped.scene.terrain
num_rows, num_cols = terrain.terrain_origins.shape[0], terrain.terrain_origins.shape[1]
assert num_rows == 4 and num_cols == 120, f"terrain grid {num_rows}x{num_cols} != 4x120 (yaml terrain_grid)"
gen = terrain.cfg.terrain_generator
assert gen.curriculum is True, "generator-swap pit: curriculum flag lost (column split would be random)"
assert any("|" in n for n in gen.sub_terrains) and "flat" in gen.sub_terrains, "param-grid combo names missing"
for i in range(2):
    lvl = terrain.terrain_levels[i].item()
    col = terrain.terrain_types[i].item()
    assert 0 <= lvl < num_rows and 0 <= col < num_cols, f"env {i} spawned at ({lvl}, {col}) out of grid"
    assert torch.equal(terrain.env_origins[i], terrain.terrain_origins[lvl, col]), f"env {i} origin mismatch"
print("JOINT_SIR_TRAIN origins re-pointed inside the 4x120 grid OK (levels %s cols %s)" %
      (terrain.terrain_levels.tolist(), terrain.terrain_types.tolist()))

# commands come from the particle's velocity bucket (+- jitter) -- the Eq. 2
# label accumulator rides the same term
term = train_env.unwrapped.command_manager.get_term("base_velocity")
assert isinstance(term, ParticleVelocityCommand), f"TRAIN command term is {type(term).__name__}"
import pathlib  # noqa: E402

import yaml  # noqa: E402

v11y = yaml.safe_load(open(pathlib.Path(__file__).resolve().parents[3] / V11_YAML, encoding="utf-8"))["v11"]
buckets = torch.tensor(v11y["velocity_buckets"])
vx = term.vel_command_b[:, 0]
for i in range(2):
    dist = (buckets - vx[i]).abs().min()
    assert dist <= v11y["velocity_command"]["command_jitter"] + 1.0e-6, (
        f"env {i} commanded vx {float(vx[i]):.3f} is not within jitter of a bucket {buckets.tolist()}"
    )
print("COMMANDS particle buckets OK (vx: %s, buckets %s)" % (vx.tolist(), buckets.tolist()))

with torch.inference_mode():
    for _ in range(30):
        train_obs, rew, term, trunc, info = train_env.step(
            torch.zeros(2, train_env.unwrapped.action_manager.total_action_dim))
assert torch.isfinite(rew).all(), f"non-finite train reward: {rew}"
# no tilt termination in v11: mid-episode resets are not guaranteed within 30
# steps, so the curriculum log key is asserted on the reset info
fmv = train_info.get("log", {}).get("Curriculum/joint_sir/frontier_max_v")
assert fmv is not None and torch.isfinite(torch.tensor(float(fmv))), f"Curriculum/joint_sir/frontier_max_v {fmv}"
print("JOINT_SIR_TRAIN stepped, Curriculum/joint_sir/frontier_max_v = %s" % (fmv,))
train_env.close()
print("=== DONE ===")
