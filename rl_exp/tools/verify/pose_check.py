# -*- coding: utf-8 -*-
"""Print rest-pose body positions of the lizard env."""
import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym

import isaaclab_tasks  # noqa: F401
from rl_exp.tasks.lizard_env_cfg import LizardFlatEnvCfg

cfg = LizardFlatEnvCfg()
cfg.scene.num_envs = 1
env = gym.make('Lizard-Velocity-Flat-v0', cfg=cfg)
env.reset()
robot = env.unwrapped.scene['robot']
names = robot.body_names
from isaaclab.utils.math import quat_apply, quat_conjugate
base_pos = robot.data.body_pos_w[0, names.index('base_link')]
base_quat = robot.data.body_quat_w[0, names.index('base_link')]
for want in ('neck3_pitch', 'lf_foot', 'rf_foot', 'rl_foot', 'rr_foot', 'rear_yaw', 'tail_pitch'):
	idx = names.index(want)
	rel = quat_apply(quat_conjugate(base_quat), robot.data.body_pos_w[0, idx] - base_pos)
	print('REL %s (%.3f, %.3f, %.3f)' % (want, rel[0], rel[1], rel[2]))
env.close()
