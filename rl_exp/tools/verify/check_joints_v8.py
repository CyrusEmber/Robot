# -*- coding: utf-8 -*-
"""Joint function check on the v8 (anatomy-correct) asset: layout + actuation.

Part 1 prints every body's position in the BASE frame (yaw-randomized spawn
removed via quat_apply_inverse) -- expect thighs sprawling along +/-y, shanks
pointing down (-z), feet near ground, the SPHERE HEAD (neck_pitch link) at +x,
the ANTENNA TAIL (tail3_pitch link) at -x, front legs (lf/rf) ahead of the
root, rear legs (rl/rr) behind.

Part 2 injects +0.3 rad into one joint at a time (all others zero) via the
position-action channel, lets the PD settle, and prints the BASE-frame
displacement of the segment's endpoint. Reading key (head = +x, left = +y):
  hfe (axis Z)  -> endpoint moves in the x-y plane, z ~ 0
  kfe (axis X)  -> endpoint lifts: dz dominant
  haa (axis -X) -> endpoint lifts/spreads: dz or dy dominant
  foot (axis Y) -> dy dominant
  yaw joints (axis Z) -> head/tail endpoints move in the x-y plane

CAVEAT (same as the v6-era reading, by design of the asset): the two
HEAD-SIDE pitch joints (chest_pitch, neck_pitch) carry the front legs + ball
head on a ~1 m lever propped by the planted legs -- underdamped (I ~ 30 kg m^2
vs damping 20), oscillation period ~ 90 steps > the 40-step settle window, so
their `achieved`/delta readings mix gravity sag + oscillation phase. Yaw
joints (no gravity torque) and the antenna tail (light) read clean.

v8 ground truth (rename_flip_v8.py): the old "neck1-3" chain was the tail,
the old "tail_yaw/tail_pitch" chain carried the head -- names now match
anatomy and the body was rotated net +90 deg (sphere head -y -> +x).
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
from isaaclab.utils.math import quat_apply_inverse

from rl_exp.tasks.teacher_env_cfg import LizardRoughTeacherEnvCfg_V8_PLAY

INJECT_RAD = 0.3
SETTLE_STEPS = 40

cfg = LizardRoughTeacherEnvCfg_V8_PLAY()
cfg.scene.num_envs = 1
env = gym.make("Lizard-Rough-Play-v8", cfg=cfg)
env.reset()
robot = env.unwrapped.scene["robot"]
joint_names = list(robot.joint_names)
body_names = list(robot.data.body_names)


def pos_b():
    """All body positions in the base frame, tensor (num_bodies, 3)."""
    root_q = robot.data.root_quat_w.torch
    rel = robot.data.body_pos_w.torch - robot.data.root_pos_w.torch
    return quat_apply_inverse(root_q, rel)


print("=== LAYOUT (base frame: sphere head=+x, antenna tail=-x, left=+y, up=+z) ===")
p = pos_b()[0]
base = p[body_names.index("base_link")]
for name in ("neck_pitch", "chest_pitch", "tail1_pitch", "tail3_pitch",
             "lf_haa", "lf_hfe", "lf_kfe", "lf_foot",
             "rf_haa", "rf_hfe", "rf_kfe", "rf_foot",
             "rl_haa", "rl_hfe", "rl_kfe", "rl_foot",
             "rr_haa", "rr_hfe", "rr_kfe", "rr_foot"):
    i = body_names.index(name)
    print("BODY %-11s rel=(%7.3f, %7.3f, %7.3f)" % (name, p[i, 0] - base[0], p[i, 1] - base[1], p[i, 2] - base[2]))

# hard gate: anatomy must match the names -- the v6 lesson (names trusted over
# geometry for two versions) dies here
assert p[body_names.index("neck_pitch"), 0] - base[0] > 1.0, "sphere head (neck_pitch) must sit at +x"
assert p[body_names.index("tail3_pitch"), 0] - base[0] < -1.0, "antenna tail (tail3_pitch) must sit at -x"
for n in ("lf_haa", "rf_haa"):
    assert p[body_names.index(n), 0] - base[0] > 0, f"front leg {n} must be ahead of the root"
for n in ("rl_haa", "rr_haa"):
    assert p[body_names.index(n), 0] - base[0] < 0, f"rear leg {n} must be behind the root"
for n in ("lf_haa", "rl_haa"):
    assert p[body_names.index(n), 1] - base[1] > 0, f"left leg {n} must be on +y"
for n in ("rf_haa", "rr_haa"):
    assert p[body_names.index(n), 1] - base[1] < 0, f"right leg {n} must be on -y"
print("LAYOUT_GATES PASSED (head +x / tail -x / legs anatomical)")

print("=== ACTUATION (+%.2f rad single joint, endpoint delta in base frame) ===" % INJECT_RAD)
PROBES = [
    ("lf_hfe_joint", "lf_foot"),      # thigh
    ("rf_hfe_joint", "rf_foot"),      # thigh (other side)
    ("lf_kfe_joint", "lf_foot"),      # shank
    ("lf_haa_joint", "lf_foot"),      # hip (context)
    ("lf_foot_joint", "lf_foot"),     # foot pad
    ("chest_pitch_joint", "neck_pitch"),  # chest pitch: ball head nods (dz)
    ("neck_yaw_joint", "neck_pitch"),     # neck yaw: ball head sweeps in xy
    ("neck_pitch_joint", "neck_pitch"),   # neck pitch: ball head nods (dz)
    ("tail1_yaw_joint", "tail3_pitch"),   # tail yaw: antenna sweeps in xy
    ("tail3_pitch_joint", "tail3_pitch"), # tail tip pitch
]

# action layout = concat of manager terms; map joint -> (action idx, scale)
am = env.unwrapped.action_manager
joint_to_action = {}
offset = 0
for term_name in am.active_terms:
    term = am.get_term(term_name)
    t_scale = term._scale
    t_scale = float(t_scale) if not hasattr(t_scale, "reshape") else float(t_scale.reshape(-1)[0])
    print("ACTION_TERM %s %s scale=%s joints=%s" %
          (term_name, type(term).__name__, t_scale, term._joint_names))
    for i, jn in enumerate(term._joint_names):
        joint_to_action[jn] = (offset + i, t_scale)
    offset += len(term._joint_names)
print("TOTAL_ACTION_DIM %d" % am.total_action_dim)

act_dim = am.total_action_dim
for joint, endpoint in PROBES:
    zero = torch.zeros(1, act_dim)
    idx = joint_names.index(joint)
    e_idx = body_names.index(endpoint)
    # settle back to stance
    for _ in range(SETTLE_STEPS):
        env.step(zero)
    p0 = pos_b()[0, e_idx]
    cmd = zero.clone()
    a_idx, a_scale = joint_to_action[joint]
    cmd[0, a_idx] = INJECT_RAD / a_scale if a_scale > 0 else 1.0  # scale 0 = dead channel, poke anyway
    for _ in range(SETTLE_STEPS):
        env.step(cmd)
    p1 = pos_b()[0, e_idx]
    d = p1 - p0
    achieved = float(robot.data.joint_pos[0][idx])
    print("JOINT %-17s scale=%.2f -> %-11s achieved=%+.3f delta=(%7.3f, %7.3f, %7.3f)"
          % (joint, a_scale, endpoint, achieved, d[0], d[1], d[2]))

env.close()
print("=== DONE ===")
