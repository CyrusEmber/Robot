# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Reset contract check: does a reset put the joints back, and only for the envs it names?

No version in the name: what is checked is a platform contract, not a recipe property, so
the same check serves the baseline line and the teacher line.

The contract, from the source this stack is pinned to:

* ``InteractiveScene.reset(env_ids)`` calls ``Articulation.reset(env_ids)``
  (``source/isaaclab/isaaclab/scene/interactive_scene.py``), and that reset clears actuator
  state and the two wrench composers ONLY -- it does not write joint positions or
  velocities (``source/isaaclab_physx/isaaclab_physx/assets/articulation/articulation.py``).
* The writers of joint state at reset are the reset-mode events ``mdp.reset_joints_by_scale``
  / ``mdp.reset_joints_by_offset`` (``source/isaaclab/isaaclab/envs/mdp/events.py``).

So a recipe that removes those events removes joint reset itself: a respawned env keeps the
joints it fell with, the true simulator state is never restored, and every episode after the
first starts from the previous one's residue. Nothing in a config snapshot can show that --
the snapshot is the declaration, and a missing writer is not a field.

Only a rollout sees it, and only if it *moves the joints first*: reading the joint state
after a reset cannot tell "wrote the default" apart from "never wrote anything", because
both read as the default while nothing has moved. Hence the phases:

  A  spawn -> actual joint state equals the default template
  B  excite with actions (auto-reset suppressed) -> the joints really left the default;
     this is the vacuity guard, without it A and C prove nothing
  C  full reset -> back to the default (the assertion that catches a deleted joint reset)
  D  excite again, then reset a subset -> those envs come back AND the envs not named are
     bitwise untouched (a subset reset that overwrites every env is the other half of the
     same contract; the second excitation is what makes "untouched" mean something)

The assertions are on the state after a reset, so they hold whichever layer writes it.

Usage (repo root, IsaacLab venv):
    "E:/IsaacLab/env_isaaclab/Scripts/python.exe" rl_exp\\tools\\verify\\reset_check.py --task Lizard-Baseline-Flat-v1

Exit code is 0 only when every phase passed.
"""

from __future__ import annotations

import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Reset contract check: full reset + subset reset.")
parser.add_argument("--task", default="Lizard-Baseline-Flat-v1", help="Registered task id (any line).")
parser.add_argument("--num_envs", type=int, default=8)
parser.add_argument("--excite-steps", type=int, default=20, help="control steps of uniform actions in phase B")
parser.add_argument("--subset", type=int, default=2, help="how many envs are reset alone in phase D")
parser.add_argument("--seed", type=int, default=0, help="seeds the phase B actions only")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
simulation_app = AppLauncher(args_cli).app

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402

import isaaclab_tasks  # noqa: F401, E402
from isaaclab.utils.string import string_to_callable  # noqa: E402

# the reset writes the data buffer directly, so "back at the default" is an exact match, not
# a tolerance question; the printed worst deviation is there to make a near-miss visible
ATOL = 1e-5
DEVIATION = 0.05  # [rad] a joint counts as excited once it left the default by this much
PROBLEMS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{'' if ok else f': {detail}'}")
    if not ok:
        PROBLEMS.append(f"{name}: {detail}")


def joint_state(robot) -> tuple[torch.Tensor, torch.Tensor]:
    """Actual joint position and velocity, not the default template. Copies."""
    return robot.data.joint_pos.torch.clone(), robot.data.joint_vel.torch.clone()


def deviation(pos: torch.Tensor, default_pos: torch.Tensor) -> torch.Tensor:
    """(N,) per-env max |q - q_default| [rad]."""
    return (pos - default_pos).abs().amax(dim=1)


def worst_joints(robot, pos: torch.Tensor, default_pos: torch.Tensor, k: int = 5) -> str:
    """The k joints that deviate most, named -- an average would hide a silent one."""
    delta = (pos - default_pos).abs().amax(dim=0)
    order = torch.argsort(delta, descending=True)[:k]
    return ", ".join(f"{robot.joint_names[i]} {delta[i].item():.4f}" for i in order.tolist())


def excite(env, mbenv, robot, steps: int, seed: int) -> tuple[torch.Tensor, int]:
    """Step uniform actions and return the joint positions they left, plus the respawn count.

    Auto-reset is suppressed for the window, not as an optimization: a respawn inside it would
    restore the default and hide the deviation this is here to establish. The count is reported
    so "the env never respawned mid-window" is visible rather than assumed -- it also has to be
    restored afterwards, or the phases below would be testing the patched env.
    """
    original_reset_idx = mbenv._reset_idx
    suppressed = 0

    def _count_reset(env_ids):
        nonlocal suppressed
        suppressed += int(torch.as_tensor(env_ids).numel())

    mbenv._reset_idx = _count_reset
    torch.manual_seed(seed)
    try:
        for _ in range(steps):
            actions = torch.empty(mbenv.num_envs, mbenv.action_manager.total_action_dim,
                                  device=mbenv.device).uniform_(-1.0, 1.0)
            # no torch.inference_mode() here, deliberately: it would make every tensor the
            # managers keep during a step an inference tensor, and a stateful term that writes to
            # its own buffer in reset() (teacher_mdp's dwell term) then dies on the next reset
            # with "Inplace update to inference tensor outside InferenceMode is not allowed".
            # A probe has nothing to gain from it.
            env.step(actions)
        pos, _ = joint_state(robot)
    finally:
        mbenv._reset_idx = original_reset_idx
    return pos, suppressed


def main() -> int:
    # resolve the env cfg the way train.py does: the registered entry point, not a re-derivation
    spec = gym.spec(args_cli.task)
    cfg = string_to_callable(spec.kwargs["env_cfg_entry_point"])()
    cfg.scene.num_envs = args_cli.num_envs
    env = gym.make(args_cli.task, cfg=cfg)
    mbenv = env.unwrapped
    robot = mbenv.scene["robot"]
    device = mbenv.device
    default_pos = robot.data.default_joint_pos.torch.clone()
    default_vel = robot.data.default_joint_vel.torch.clone()
    act_dim = mbenv.action_manager.total_action_dim
    print(f"[reset] task {args_cli.task}  num_envs {args_cli.num_envs}  act_dim {act_dim}  "
          f"max|default_joint_vel| {default_vel.abs().max().item():.4f} rad/s")

    # --- A: one full reset (also the wrapper's prerequisite for step()) ----------------
    # reading the state at construction instead would prove nothing: nothing has moved yet,
    # so a joint reset that does not exist and one that works are indistinguishable
    print("[reset] A full reset")
    env.reset()
    pos_a, vel_a = joint_state(robot)
    dev_a = deviation(pos_a, default_pos)
    check("A/joint-pos-at-default", bool((dev_a <= ATOL).all()),
          f"worst {dev_a.max().item():.4f} rad ({worst_joints(robot, pos_a, default_pos)})")
    check("A/joint-vel-at-default", bool(((vel_a - default_vel).abs() <= ATOL).all()),
          f"worst {(vel_a - default_vel).abs().max().item():.4f} rad/s")

    # --- B: excite, so that C has something to undo ------------------------------------
    print(f"[reset] B excite {args_cli.excite_steps} steps, auto-reset suppressed")
    pos_b, suppressed = excite(env, mbenv, robot, args_cli.excite_steps, args_cli.seed)
    dev_b = deviation(pos_b, default_pos)
    moved = int((dev_b > DEVIATION).sum().item())
    print(f"  excited envs {moved}/{args_cli.num_envs}  worst |dq| {dev_b.max().item():.4f} rad  "
          f"suppressed respawns {suppressed}")
    check("B/excitation-not-vacuous", moved > 0,
          f"no joint left the default by {DEVIATION} rad: C would pass without proving anything")

    # --- C: a full reset returns the joints --------------------------------------------
    print("[reset] C full reset")
    env.reset()
    pos_c, vel_c = joint_state(robot)
    dev_c = deviation(pos_c, default_pos)
    check("C/joint-pos-after-reset", bool((dev_c <= ATOL).all()),
          f"worst {dev_c.max().item():.4f} rad ({worst_joints(robot, pos_c, default_pos)})")
    check("C/joint-vel-after-reset", bool(((vel_c - default_vel).abs() <= ATOL).all()),
          f"worst {(vel_c - default_vel).abs().max().item():.4f} rad/s")

    # --- D: a subset reset must not disturb the envs it did not name -------------------
    # a second excitation: C left every env at the default, and then "the envs that were not
    # reset are unchanged" would hold no matter what a subset reset did
    n_sub = max(1, min(args_cli.subset, args_cli.num_envs - 1))
    ids = torch.arange(n_sub, dtype=torch.int32, device=device)
    rest = torch.arange(n_sub, args_cli.num_envs, dtype=torch.int32, device=device)
    print(f"[reset] D subset reset of envs {ids.tolist()}, after a second excitation")
    excite(env, mbenv, robot, args_cli.excite_steps, args_cli.seed + 1)
    pos_pre, vel_pre = joint_state(robot)
    rest_dev = deviation(pos_pre[rest], default_pos[rest])
    check("D/untouched-envs-were-excited", bool((rest_dev > DEVIATION).any()),
          f"the envs not being reset are already at the default (worst {rest_dev.max().item():.4f} rad) "
          "-- 'unchanged' would prove nothing")
    mbenv.reset(env_ids=ids)
    pos_post, vel_post = joint_state(robot)
    sub_dev = deviation(pos_post[ids], default_pos[ids])
    check("D/subset-back-at-default", bool((sub_dev <= ATOL).all()),
          f"worst {sub_dev.max().item():.4f} rad ({worst_joints(robot, pos_post[ids], default_pos[ids])})")
    same_pos = bool(torch.equal(pos_post[rest], pos_pre[rest]))
    same_vel = bool(torch.equal(vel_post[rest], vel_pre[rest]))
    check("D/untouched-envs-unchanged", same_pos and same_vel,
          f"joint_pos bitwise-equal {same_pos}, joint_vel bitwise-equal {same_vel}")

    env.close()
    if PROBLEMS:
        print(f"RESET_CHECK_FAILED ({len(PROBLEMS)})")
        return 1
    print("RESET_CHECK_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
