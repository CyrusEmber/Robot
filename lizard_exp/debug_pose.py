# -*- coding: utf-8 -*-
"""Dump world positions of every leg pivot right after reset (pose debug)."""

import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
simulation_app = AppLauncher(args_cli).app

import gymnasium as gym
import torch

import isaaclab_tasks  # noqa: F401
from lizard_exp.tasks.lizard_env_cfg import LizardFlatEnvCfg_PLAY

cfg = LizardFlatEnvCfg_PLAY()
cfg.scene.num_envs = 1
env = gym.make("Lizard-Velocity-Flat-Play-v0", cfg=cfg)
env.reset()
robot = env.unwrapped.scene["robot"]

body_names = list(robot.data.body_names)
body_pos = robot.data.body_pos_w[0]
base_pos = robot.data.root_pos_w[0]
print("BASE (%.3f, %.3f, %.3f)" % (float(base_pos[0]), float(base_pos[1]), float(base_pos[2])))
for leg in ("lf", "rf", "rl", "rr"):
    for part in ("haa", "hfe", "kfe", "foot"):
        name = "%s_%s" % (leg, part)
        idx = body_names.index(name)
        pos = body_pos[idx]
        print("PIVOT %s (%.3f, %.3f, %.3f) rel_z=%.3f"
              % (name, float(pos[0]), float(pos[1]), float(pos[2]), float(pos[2] - base_pos[2])))
env.close()
