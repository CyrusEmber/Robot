# -*- coding: utf-8 -*-
"""Check lizard spawn position: base height trace + foot contacts over 1 s.

Zero actions, PLAY cfg (no randomization). Judges whether the robot spawns
floating, sunk, or settled. Usage: python position_check.py --headless
"""
import argparse
import sys

if "--rough" in sys.argv:
    sys.argv.remove("--rough")
    _VARIANT = "rough"
else:
    _VARIANT = "flat"

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
simulation_app = AppLauncher(args_cli).app

import gymnasium as gym
import torch

import isaaclab_tasks  # noqa: F401
from lizard_exp.tasks.lizard_env_cfg import LizardFlatEnvCfg_PLAY
from lizard_exp.tasks.curriculum_rough_env_cfg import (
    LizardCurriculumRoughEnvCfg_PLAY,
)

variant = _VARIANT
cfg = LizardCurriculumRoughEnvCfg_PLAY() if variant == "rough" else LizardFlatEnvCfg_PLAY()
cfg.scene.num_envs = 1
env = gym.make(
    "Lizard-Velocity-Curriculum-Rough-Play-v0" if variant == "rough" else "Lizard-Velocity-Flat-Play-v0",
    cfg=cfg,
)
env.reset()
robot = env.unwrapped.scene["robot"]
sensor = env.unwrapped.scene["contact_forces"]

joint_names = list(robot.joint_names)
print("JOINT_COUNT %d" % len(joint_names))
foot_names = [n for n in robot.data.body_names if n.endswith("_foot")]
print("FOOT_BODIES %s" % foot_names)

actions = torch.zeros(1, env.unwrapped.action_manager.total_action_dim)
step_dt = env.unwrapped.step_dt
with torch.inference_mode():
    for step in range(50):
        env.step(actions)
        if step % 10 == 0:
            pos = robot.data.root_pos_w[0]
            print("T=%.2f base=(%.3f, %.3f, %.3f)"
                  % (step * step_dt, float(pos[0]), float(pos[1]), float(pos[2])))

foot_idx = [robot.data.body_names.index(n) for n in foot_names]
forces = sensor.data.net_forces_w[0, foot_idx, :]
for name, force in zip(foot_names, forces):
    print("FOOT %s force_z=%.2f N" % (name, float(force[2])))

root_pos = robot.data.root_pos_w[0]
nan_ok = not torch.isnan(robot.data.joint_pos).any()
print("RESULT z=%.3f nan_free=%s" % (float(root_pos[2]), nan_ok))
env.close()
