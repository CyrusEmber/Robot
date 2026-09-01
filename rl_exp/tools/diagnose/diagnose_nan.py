"""Diagnose NaN observations in Lizard-Velocity-Flat-v0.

Spawns a few envs, resets once, then reports which observation terms and
which raw robot state quantities contain NaN.

Usage:
    python diagnose_nan.py --headless
"""

import argparse
import sys

TASK = "Lizard-Velocity-Flat-v0"
if len(sys.argv) > 1 and not sys.argv[-1].startswith("-"):
    TASK = sys.argv.pop()

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Diagnose NaN observations.")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym
import torch

import isaaclab_tasks  # noqa: F401
from isaaclab_tasks.utils import parse_env_cfg

OBS_LAYOUT = [
    ("base_lin_vel", 3),
    ("base_ang_vel", 3),
    ("projected_gravity", 3),
    ("velocity_commands", 3),
    ("joint_pos_rel", 18),
    ("joint_vel_rel", 18),
    ("last_action", 18),
]


def main():
    task = TASK
    print(f"TASK: {task}")
    env_cfg = parse_env_cfg(task, num_envs=64)
    env = gym.make(task, cfg=env_cfg)
    obs, _ = env.reset()
    print("-" * 80)
    print("NaN at reset:", torch.isnan(obs["policy"]).any().item())

    robot = env.unwrapped.scene["robot"]
    action = torch.zeros(env.action_space.shape, device=env.unwrapped.device)
    total_terminated = 0
    for step in range(100):
        obs, reward, terminated, truncated, info = env.step(action)
        total_terminated += int(terminated.sum().item())
        if step % 10 == 0:
            root_z = robot.data.root_pos_w[:, 2]
            has_nan = torch.isnan(obs["policy"]).any().item()
            print(
                f"step {step:3d}: nan={has_nan} "
                f"root_z=[{root_z.min().item():.3f},{root_z.max().item():.3f}] "
                f"max_vel={robot.data.joint_vel.abs().max().item():.2f} "
                f"total_terminated={total_terminated}"
            )
        if torch.isnan(obs["policy"]).any().item():
            print(f"NaN at step {step}, aborting")
            break
    print("-" * 80)
    print(f"RESULT: total terminations over 100 steps x 64 envs: {total_terminated}")
    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
