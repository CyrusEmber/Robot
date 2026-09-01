# -*- coding: utf-8 -*-
"""C3 performance risk check: v3 foot-ring scanners vs v2 base grid scan.

Builds each TRAIN env at the target env count, warms up, then times a fixed
number of steps and reports per-step cost + peak GPU memory. Small-env smoke
timings mislead (per-caster fixed cost dominates there), so this must run at
the training scale.

Usage: python rl_exp\\tools\\verify\\time_foot_rings.py --num_envs 4096 --num_steps 100
"""

import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--num_envs", type=int, default=4096)
parser.add_argument("--num_steps", type=int, default=100)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
simulation_app = AppLauncher(args_cli).app

import time

import gymnasium as gym
import torch

import isaaclab_tasks  # noqa: F401


def run_task(task_id: str, label: str) -> None:
    cfg = gym.spec(task_id).kwargs["env_cfg_entry_point"]
    from isaaclab.utils.string import string_to_callable

    env_cfg = string_to_callable(cfg)()
    env_cfg.scene.num_envs = args_cli.num_envs
    env = gym.make(task_id, cfg=env_cfg)
    obs, _ = env.reset()
    act_dim = env.unwrapped.action_manager.total_action_dim
    action = torch.zeros(args_cli.num_envs, act_dim)
    # warmup: sensor buffers, JIT kernels, allocator steady state
    with torch.inference_mode():
        for _ in range(10):
            env.step(action)
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    torch.cuda.reset_peak_memory_stats() if torch.cuda.is_available() else None
    start = time.perf_counter()
    with torch.inference_mode():
        for _ in range(args_cli.num_steps):
            env.step(action)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    elapsed = time.perf_counter() - start
    peak_mb = (torch.cuda.max_memory_allocated() / 2**20) if torch.cuda.is_available() else float("nan")
    print(
        f"TIMING {label}: {elapsed / args_cli.num_steps * 1000.0:.2f} ms/step "
        f"({args_cli.num_envs} envs, {args_cli.num_steps} steps), peak GPU mem {peak_mb:.0f} MB"
    )
    env.close()


run_task("Lizard-Rough-v3", "v3_foot_rings_208rays")
run_task("Lizard-Rough-v2", "v2_base_grid_135rays")
print("=== DONE ===")
