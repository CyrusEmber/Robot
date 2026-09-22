# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Actuator capability curve for a family: what can the leg joints actually follow, and how fast?

Why this exists: this line's command window is a hypothesis about the robot's speed, and the geometry
only says how far a leg CAN reach (0.55 m fore-aft at load) -- not how fast it can cycle. A first
estimate from `tau = I A (2 pi f)^2` put the window's top (3 m/s) beyond the hip's effort limit, and
an estimate is not a measurement. This measures, in two layers the plan names:

* **layer 1 (airborne)**: the root pose is pinned every step (the robot is effectively hung), gravity
  and ground cannot load the leg, and one hip is commanded a sine of amplitude ``--amplitude`` at
  ``--freqs``. It answers "can the joint servo follow this trajectory", which is a *necessary* and not
  a sufficient condition for a gait: failing here means this trajectory is hard to track, NOT that no
  gait reaches the window's top;
* **layer 2 (load-bearing)**: released onto the plane, all four legs paddle (hip sine, knee
  counter-phase at half amplitude) at the same frequencies, and the body's achieved forward speed is
  read. It is a crude coordinated motion, not a gait: what it gives is a measured envelope of
  "frequency -> speed the machine can actually generate", to be compared against the command window.

What it reports, and what it cannot:

* the EFFECTIVE limits, read off the built env's actuator objects (this fork drops a bare
  ``velocity_limit`` on implicit actuators -- ``actuator_pd.py:80-91`` -- so the cfg value is printed
  as dropped and the sim limit is printed as unset; the effort limit is the one that landed);
* tracking error (RMS and max) against the commanded sine, peak joint speed, and the fraction of steps
  where the error exceeds 20% of the amplitude (the saturation proxy that does not need a torque);
* a PD-equation torque estimate ``Kp*err - Kd*qd``, labelled as an ESTIMATE: ``applied_torque`` is
  structurally all-zero for implicit actuators in this fork (``parkour_mdp.py:275``), and the solver's
  implicit gravity/Coriolis terms are invisible from here. It under-reports; it is not "measured force".

Usage (from the repo root):

    python rl_exp/tools/verify/check_actuator_budget.py --task Lizard2-Flat-Play-v1
    python rl_exp/tools/verify/check_actuator_budget.py --task Lizard2-Flat-Play-v1 --json <report>

Exit code is 0: this is a measurement that feeds the plan, not a pass/fail gate.
"""

import argparse
import json
import math
import pathlib
import sys

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument("--task", default="Lizard2-Flat-Play-v1")
parser.add_argument("--joint", default="lf_hip", help="joint the airborne sweep commands (token after the leg)")
parser.add_argument("--amplitude", type=float, default=0.6, help="sine amplitude [rad]")
parser.add_argument("--freqs", type=float, nargs="*", default=[0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
parser.add_argument("--airborne-s", type=float, default=2.0, help="seconds per frequency, airborne layer")
parser.add_argument("--loaded-s", type=float, default=3.0, help="seconds per frequency, loaded layer")
parser.add_argument("--settle", type=int, default=60, help="zero-action steps before the loaded layer")
parser.add_argument("--json", help="write the measured curve here")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
simulation_app = AppLauncher(args_cli).app

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402

import isaaclab_tasks  # noqa: F401,E402
from isaaclab.utils.string import string_to_callable  # noqa: E402

cfg = string_to_callable(gym.spec(args_cli.task).kwargs["env_cfg_entry_point"])()
cfg.scene.num_envs = 1
env = gym.make(args_cli.task, cfg=cfg)
env.reset()
robot = env.unwrapped.scene["robot"]
dt = float(env.unwrapped.step_dt)
names = list(robot.joint_names)
legs = [name[:2] for name in names if name.endswith("_hip_joint")] or ["lf", "rf", "rl", "rr"]


def act_limits() -> dict:
    """The limits the actuators actually handed the solver, group by group."""
    out = {}
    for key, actuator in robot.actuators.items():
        group = actuator.cfg
        out[key] = {
            "joints": len(actuator.joint_indices),
            "stiffness": float(group.stiffness),
            "damping": float(group.damping),
            "effort_limit_sim": None if group.effort_limit_sim is None else float(group.effort_limit_sim),
            "velocity_limit_sim": None if group.velocity_limit_sim is None else float(group.velocity_limit_sim),
            "velocity_limit_cfg_dropped": group.velocity_limit is None,
        }
    return out


def target_sine(t: float, freq: float, legs_used: list[str], knee_phase: bool) -> torch.Tensor:
    """A position target (1, num_joints): hip sine on every leg, knee in counter-phase when asked."""
    target = robot.data.joint_pos.torch[:1].clone()  # hold everything else where it is
    for leg in legs_used:
        hip = names.index(f"{leg}_hip_joint")
        target[0, hip] = args_cli.amplitude * math.sin(2 * math.pi * freq * t)
        if knee_phase:
            knee = names.index(f"{leg}_hfe_joint")
            target[0, knee] = 0.5 * args_cli.amplitude * math.sin(2 * math.pi * freq * t + math.pi)
    return target


le_top = robot.actuators  # noqa: F841 - kept for readability of the group loop above
am = env.unwrapped.action_manager
# joint -> (action index, scale). The action is what the env actually applies, so the sweep drives
# THAT: the first version called set_joint_position_target() and then stepped with zero actions, which
# put the default pose straight back -- the sweep measured its own bug (RMS error = the sine itself).
joint_to_action: dict[str, tuple[int, float]] = {}
offset = 0
for term_name in am.active_terms:
    term = am.get_term(term_name)
    scale = term._scale
    scale = float(scale) if not hasattr(scale, "reshape") else float(scale.reshape(-1)[0])
    for position, joint in enumerate(term._joint_names):
        joint_to_action[joint] = (offset + position, scale)
    offset += len(term._joint_names)
default_pos = robot.data.default_joint_pos.torch[0].clone()


def action_for(target: torch.Tensor) -> torch.Tensor:
    """The action vector that asks for ``target`` (1, num_joints) under the deployed interface."""
    action = torch.zeros((1, am.total_action_dim), device=robot.device)
    for joint, (index, scale) in joint_to_action.items():
        if scale > 0:
            action[0, index] = (float(target[0, names.index(joint)]) - float(default_pos[names.index(joint)])) / scale
    return action


def pin_root(root_pose: torch.Tensor) -> None:
    """Hold the base where it is: the airborne layer's stand-in for hanging the robot up."""
    robot.write_root_pose_to_sim(root_pose)
    robot.write_root_velocity_to_sim(torch.zeros((1, 6), device=robot.device))


def run_bout(freq: float, seconds: float, airborne: bool, pin: torch.Tensor | None) -> dict:
    """One bout: pin the joint targets to a sine and collect the tracking/limit readings."""
    steps = max(2, int(seconds / dt))
    joint = names.index(args_cli.joint + "_joint")
    actuator = next(a for a in robot.actuators.values() if joint in a.joint_indices)
    kp, kd = float(actuator.cfg.stiffness), float(actuator.cfg.damping)
    errors: list[float] = []
    speeds: list[float] = []
    efforts: list[float] = []
    forward: list[float] = []
    for step in range(steps):
        t = step * dt
        target = target_sine(t, freq, legs, knee_phase=not airborne)
        if airborne and pin is not None:
            pin_root(pin)
        env.step(action_for(target))
        if airborne:
            errors.append(abs(float(robot.data.joint_pos.torch[0, joint]) - float(target[0, joint])))
            speeds.append(abs(float(robot.data.joint_vel.torch[0, joint])))
            efforts.append(abs(kp * float(robot.data.joint_pos.torch[0, joint] - target[0, joint])
                               - kd * float(robot.data.joint_vel.torch[0, joint])))
        else:
            forward.append(float(robot.data.root_lin_vel_b.torch[0, 0]))
    out = {"freq_hz": freq}
    if airborne:
        out.update({
            "rms_error_rad": float(torch.tensor(errors).pow(2).mean().sqrt()),
            "max_error_rad": float(max(errors)),
            "peak_speed_rad_s": float(max(speeds)),
            "pd_effort_estimate_nm": float(max(efforts)),
            "error_over_20pct_frac": float(sum(e > 0.2 * args_cli.amplitude for e in errors) / len(errors)),
        })
    else:
        out.update({
            "mean_forward_mps": float(sum(forward) / len(forward)),
            "peak_forward_mps": float(max(forward)),
        })
    return out


limits = act_limits()
print("=== effective actuator limits (what the solver was given) ===")
for group, body in limits.items():
    print(f"  {group:6s} joints={body['joints']:2d} kp={body['stiffness']:6.1f} kd={body['damping']:5.1f} "
          f"effort_limit_sim={body['effort_limit_sim']} velocity_limit_sim={body['velocity_limit_sim']} "
          f"velocity_limit_cfg_dropped={body['velocity_limit_cfg_dropped']}")
print("  note: this fork nulls a bare velocity_limit on implicit actuators (actuator_pd.py:80-91), so")
print("        any 'share of the speed budget' claim has no denominator until velocity_limit_sim is set.")

zero = torch.zeros((1, env.unwrapped.action_manager.total_action_dim), device=robot.device)
for _ in range(args_cli.settle):
    env.step(zero)
pin = robot.data.root_state_w.torch[:, :7].clone()

print(f"\n=== layer 1 (airborne: root pinned, {args_cli.joint} sine {args_cli.amplitude:+.2f} rad) ===")
print("  freq  rms_err  max_err  peak_qd  pd_tau*  over20%")
airborne_rows = []
for freq in args_cli.freqs:
    row = run_bout(freq, args_cli.airborne_s, airborne=True, pin=pin)
    airborne_rows.append(row)
    print(f"  {row['freq_hz']:5.2f} {row['rms_error_rad']:8.3f} {row['max_error_rad']:8.3f} "
          f"{row['peak_speed_rad_s']:8.2f} {row['pd_effort_estimate_nm']:8.1f} {row['error_over_20pct_frac']:6.0%}")
print("  * pd_tau = Kp*err - Kd*qd, an ESTIMATE: applied_torque is structurally zero for implicit")
print("    actuators here (parkour_mdp.py:275) and the solver's implicit terms are invisible.")

print(f"\n=== layer 2 (released on the plane, four legs paddling) ===")
print("  freq  mean_vx  peak_vx")
loaded_rows = []
for freq in args_cli.freqs:
    env.reset()
    for _ in range(args_cli.settle):
        env.step(zero)
    row = run_bout(freq, args_cli.loaded_s, airborne=False, pin=None)
    loaded_rows.append(row)
    print(f"  {row['freq_hz']:5.2f} {row['mean_forward_mps']:8.3f} {row['peak_forward_mps']:8.3f}")

fastest = max(loaded_rows, key=lambda r: r["mean_forward_mps"])
tracked = [r for r in airborne_rows if r["rms_error_rad"] < 0.2 * args_cli.amplitude
           and r["error_over_20pct_frac"] < 0.1]
print(f"\nairborne: tracked cleanly up to {max((r['freq_hz'] for r in tracked), default=0.0):.2f} Hz "
      f"(rms < 20% of amplitude and <10% of steps over it)")
print(f"loaded: best paddle {fastest['freq_hz']:.2f} Hz -> {fastest['mean_forward_mps']:+.3f} m/s mean "
      f"({fastest['peak_forward_mps']:+.3f} peak)")
print("ceiling: a paddle is not a gait (no lift, no duty, no body work), so this envelope is a LOWER")
print("bound on what a trained policy could reach, and 'paddle speed < window top' is not yet a verdict.")
if args_cli.json:
    pathlib.Path(args_cli.json).write_text(json.dumps(
        {"task": args_cli.task, "amplitude_rad": args_cli.amplitude, "limits": limits,
         "airborne": airborne_rows, "loaded": loaded_rows}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    print(f"report written: {args_cli.json}")
print("ACTUATOR_CURVE_MEASURED")
env.close()
