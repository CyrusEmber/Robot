# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Actuator response curve for a family: what can ONE leg joint follow, and how fast under load?

Why this exists: this line's command window is a hypothesis about the robot's speed, and the geometry
only says how far a leg can reach (0.55 m fore-aft at load) -- not how fast it can cycle. This measures
two layers, and states exactly what each one is:

* **unloaded** (``--unloaded``, the default): gravity is switched off on the built env
  (``cfg.sim.gravity = (0, 0, 0)``) so the robot floats at its spawn pose with the legs extended and no
  ground contact, ONE named joint is commanded a sine (amplitude ``--amplitude``), and **every other
  joint is held at the settled reference pose it had when the run started**. That is the experiment the
  plan's "layer 1" means: no gravity, no ground, no other joint moving. Failing here says this
  trajectory is hard for the servo to follow -- it does NOT say no gait reaches the window's top;
* **loaded** (``--loaded``): gravity on, released on the plane, all four legs paddling (hip sine, knee
  counter-phase at half amplitude) at the same frequencies, and the body's forward speed is read. It is
  a crude coordinated motion, not a gait: a LOWER bound on what a trained policy could reach.

The first version of this script called the pinned-root case "airborne" and drove all four legs while
measuring one, which is not the same experiment (review 2026-09-22); the current splits are named for
what they do, not for what they were meant to be.

What it reports, and what it cannot:

* the EFFECTIVE limits, read off the built env's actuator objects: this fork drops a bare
  ``velocity_limit`` on implicit actuators (``actuator_pd.py:80-91``), so the cfg value prints as
  dropped and the sim limit prints as unset. NOTE: the effort limit bounds the COMPOSITE torque, so a
  P term can cancel a D term -- nothing here converts it into a speed ceiling;
* tracking error (RMS and max) against the commanded sine, peak joint speed, and the fraction of steps
  where the error exceeds 20% of the amplitude (the saturation proxy that needs no torque at all);
* a PD-equation torque ``Kp*(target - q) - Kd*qd`` (the sign the actuator model uses), labelled as an
  ESTIMATE: ``applied_torque`` is structurally all-zero for implicit actuators in this fork
  (``parkour_mdp.py:275``), and the solver's implicit terms are invisible from here;
* the INERTIA-ONLY need ``I*A*(2*pi*f)^2`` from a single-radius estimate of the swinging assembly, as a
  separate column: whether a trajectory is inertial-heavy and whether the servo follows it are two
  different questions, and the first version of this table conflated them.

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
parser.add_argument("--joint", default="lf_hip", help="joint the unloaded sweep commands")
parser.add_argument("--amplitude", type=float, default=0.6, help="sine amplitude [rad]")
parser.add_argument("--freqs", type=float, nargs="*", default=[0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
parser.add_argument("--unloaded-s", type=float, default=2.0, help="seconds per frequency, unloaded layer")
parser.add_argument("--loaded-s", type=float, default=3.0, help="seconds per frequency, loaded layer")
parser.add_argument("--settle", type=int, default=60, help="zero-action steps before each layer")
parser.add_argument("--inertia", type=float, default=1.57,
                    help="swing inertia estimate [kg m^2] for the inertia-only column (printed, not used to pass/fail)")
parser.add_argument("--json", help="write the measured curve here")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
simulation_app = AppLauncher(args_cli).app

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402

import isaaclab_tasks  # noqa: F401,E402
from isaaclab.utils.string import string_to_callable  # noqa: E402


def build(task: str, gravity_off: bool):
    cfg = string_to_callable(gym.spec(task).kwargs["env_cfg_entry_point"])()
    cfg.scene.num_envs = 1
    if gravity_off:
        cfg.sim.gravity = (0.0, 0.0, 0.0)
    return gym.make(task, cfg=cfg)


def act_limits(robot) -> dict:
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


def action_map(env):
    """``joint -> (action index, scale)`` for the deployed interface."""
    am = env.unwrapped.action_manager
    mapping, offset = {}, 0
    for term_name in am.active_terms:
        term = am.get_term(term_name)
        scale = term._scale
        scale = float(scale) if not hasattr(scale, "reshape") else float(scale.reshape(-1)[0])
        for position, joint in enumerate(term._joint_names):
            mapping[joint] = (offset + position, scale)
        offset += len(term._joint_names)
    return mapping, am.total_action_dim


def action_for(target_row: torch.Tensor, names: list[str], mapping: dict, default_pos: torch.Tensor,
               dim: int, device) -> torch.Tensor:
    action = torch.zeros((1, dim), device=device)
    for joint, (index, scale) in mapping.items():
        if scale > 0:
            position = names.index(joint)
            action[0, index] = (float(target_row[position]) - float(default_pos[position])) / scale
    return action


def run_unloaded(task: str, joint_name: str) -> list[dict]:
    """Gravity off, ONE joint on a sine, every other joint held at the settled reference pose."""
    env = build(task, gravity_off=True)
    env.reset()
    robot = env.unwrapped.scene["robot"]
    names = list(robot.joint_names)
    mapping, dim = action_map(env)
    dt = float(env.unwrapped.step_dt)
    joint = names.index(joint_name if joint_name in names else f"{joint_name}_joint")
    zero = torch.zeros((1, dim), device=robot.device)
    settle = max(20, int(1.0 / dt))  # let the leg reach its unloaded pose under the default target
    for _ in range(settle):
        env.step(zero)
    reference = robot.data.joint_pos.torch[0].clone()
    actuator = next(a for a in robot.actuators.values() if joint in a.joint_indices)
    kp, kd = float(actuator.cfg.stiffness), float(actuator.cfg.damping)
    print(f"  unloaded reference captured (|q| mean {float(reference.abs().mean()):.3f} rad); "
          f"only {joint_name} is commanded, others held there (Kp {kp:.0f}, Kd {kd:.0f})")

    rows = []
    for freq in args_cli.freqs:
        steps = max(2, int(args_cli.unloaded_s / dt))
        errors, speeds, efforts = [], [], []
        for step in range(steps):
            t = step * dt
            target = reference.clone()
            target[joint] = args_cli.amplitude * math.sin(2 * math.pi * freq * t)
            env.step(action_for(target, names, mapping, reference, dim, robot.device))
            q = float(robot.data.joint_pos.torch[0, joint])
            qd = float(robot.data.joint_vel.torch[0, joint])
            errors.append(abs(q - float(target[joint])))
            speeds.append(abs(qd))
            # the actuator model's own sign: tau = Kp*(target - q) - Kd*qd. The first version wrote
            # (q - target), which makes the P and D terms ADD when the joint lags and inflated every
            # number in this table (review 2026-09-22).
            efforts.append(abs(kp * (float(target[joint]) - q) - kd * qd))
        rows.append({
            "freq_hz": freq,
            "rms_error_rad": float(torch.tensor(errors).pow(2).mean().sqrt()),
            "max_error_rad": float(max(errors)),
            "peak_speed_rad_s": float(max(speeds)),
            "pd_effort_estimate_nm": float(max(efforts)),
            "inertia_only_nm": float(args_cli.inertia * args_cli.amplitude * (2 * math.pi * freq) ** 2),
            "error_over_20pct_frac": float(sum(e > 0.2 * args_cli.amplitude for e in errors) / len(errors)),
        })
        row = rows[-1]
        print(f"  {row['freq_hz']:5.2f} {row['rms_error_rad']:8.3f} {row['max_error_rad']:8.3f} "
              f"{row['peak_speed_rad_s']:9.2f} {row['pd_effort_estimate_nm']:10.1f} "
              f"{row['inertia_only_nm']:11.1f} {row['error_over_20pct_frac']:6.0%}")
    env.close()
    return rows


def run_loaded(task: str) -> list[dict]:
    """Gravity on, released on the plane, four legs paddling; the body's forward speed is read."""
    env = build(task, gravity_off=False)
    env.reset()
    robot = env.unwrapped.scene["robot"]
    names = list(robot.joint_names)
    mapping, dim = action_map(env)
    dt = float(env.unwrapped.step_dt)
    zero = torch.zeros((1, dim), device=robot.device)
    for _ in range(args_cli.settle):
        env.step(zero)
    hips = [n for n in names if n.endswith("_hip_joint")]
    knees = {leg: f"{leg}_hfe_joint" for leg in (n[:2] for n in hips)}

    rows = []
    for freq in args_cli.freqs:
        env.reset()
        for _ in range(args_cli.settle):
            env.step(zero)
        reference = robot.data.joint_pos.torch[0].clone()
        steps = max(2, int(args_cli.loaded_s / dt))
        forward = []
        for step in range(steps):
            t = step * dt
            target = reference.clone()
            for hip in hips:
                target[names.index(hip)] = args_cli.amplitude * math.sin(2 * math.pi * freq * t)
                knee = knees[hip[:2]]
                target[names.index(knee)] = 0.5 * args_cli.amplitude * math.sin(2 * math.pi * freq * t + math.pi)
            env.step(action_for(target, names, mapping, reference, dim, robot.device))
            forward.append(float(robot.data.root_lin_vel_b.torch[0, 0]))
        rows.append({"freq_hz": freq, "mean_forward_mps": float(sum(forward) / len(forward)),
                     "peak_forward_mps": float(max(forward))})
        row = rows[-1]
        print(f"  {row['freq_hz']:5.2f} {row['mean_forward_mps']:9.3f} {row['peak_forward_mps']:8.3f}")
    env.close()
    return rows


probe = build(args_cli.task, gravity_off=True)
probe.reset()
limits = act_limits(probe.unwrapped.scene["robot"])
print("=== effective actuator limits (what the solver was given) ===")
for group, body in limits.items():
    print(f"  {group:6s} joints={body['joints']:2d} kp={body['stiffness']:6.1f} kd={body['damping']:5.1f} "
          f"effort_limit_sim={body['effort_limit_sim']} velocity_limit_sim={body['velocity_limit_sim']} "
          f"velocity_limit_cfg_dropped={body['velocity_limit_cfg_dropped']}")
print("  note: the effort limit bounds the COMPOSITE torque (a P term can cancel a D term), so this")
print("        number is not convertible into a speed ceiling; and no velocity limit reached the sim.")
probe.close()

print(f"\n=== layer 1 UNLOADED: gravity off, {args_cli.joint} sine {args_cli.amplitude:+.2f} rad, "
      "all other joints held at the settled reference ===")
print("  freq  rms_err  max_err  peak_qd  pd_tau*  inertia_only#")
unloaded = run_unloaded(args_cli.task, args_cli.joint)
print("  * pd_tau = Kp*(target-q) - Kd*qd, an ESTIMATE: applied_torque is structurally zero for implicit")
print("    actuators here (parkour_mdp.py:275) and the solver's implicit terms are invisible from here.")
print("  # inertia_only = I*A*(2*pi*f)^2 with a single-radius I estimate -- a separate question from")
print("    tracking: a trajectory can be inertial-heavy and still followed, or light and still lagging.")

print("\n=== layer 2 LOADED: gravity on, released on the plane, four legs paddling ===")
print("  freq  mean_vx  peak_vx")
loaded = run_loaded(args_cli.task)

clean = [r for r in unloaded if r["rms_error_rad"] < 0.2 * args_cli.amplitude
         and r["error_over_20pct_frac"] < 0.1]
fastest = max(loaded, key=lambda r: r["mean_forward_mps"])
print(f"\nUNLOADED: rms < 20% of amplitude and <10% of steps over it, up to "
      f"{max((r['freq_hz'] for r in clean), default=0.0):.2f} Hz")
print(f"LOADED: best paddle {fastest['freq_hz']:.2f} Hz -> {fastest['mean_forward_mps']:+.3f} m/s mean "
      f"({fastest['peak_forward_mps']:+.3f} peak)")
print("ceiling: a paddle is not a gait (no lift, no duty, no body work), so this is a LOWER bound; and")
print("'paddle speed < window top' is not yet a verdict about any trained policy.")
if args_cli.json:
    pathlib.Path(args_cli.json).write_text(json.dumps(
        {"task": args_cli.task, "amplitude_rad": args_cli.amplitude, "limits": limits,
         "unloaded": unloaded, "loaded": loaded}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"report written: {args_cli.json}")
print("ACTUATOR_CURVE_MEASURED")
