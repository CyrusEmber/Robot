# -*- coding: utf-8 -*-
"""Print joint angles right after reset."""
import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym

import isaaclab_tasks  # noqa: F401
from rl_exp.tasks.lizard_env_cfg import LizardFlatEnvCfg_PLAY

cfg = LizardFlatEnvCfg_PLAY()
cfg.scene.num_envs = 1
env = gym.make('Lizard-Velocity-Flat-Play-v0', cfg=cfg)
env.reset()
robot = env.unwrapped.scene['robot']
for n, v in zip(robot.joint_names, robot.data.joint_pos[0]):
	print('JOINT %s %.3f' % (n, float(v)))
env.close()
