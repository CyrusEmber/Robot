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

* **drive audit** (``--drive-audit``): no sweep -- one build, then the per-joint comparison between what
  each actuator DECLARED and what the solver HOLDS. The group table below reports the actuator objects'
  own cfg (what they were asked for); this layer adds the readback (``data.joint_stiffness`` /
  ``joint_damping`` / ``joint_effort_limits`` / ``joint_vel_limits``, cloned from the PhysX
  ``get_dof_stiffnesses`` / ``get_dof_dampings`` / ``get_dof_max_forces`` / ``get_dof_max_velocities``
  view when the data buffers are built, i.e. after the cfg was handed over). It answers "did the declared
  value become the solver's value" -- per joint, not per group -- which the yaml-side coverage gate
  cannot (``work/closed/2026/actuator-params-audit.md``).

* **static load** (``--static-only``): gravity on, ZERO action -- the robot holds its default joint
  targets, which is a posture, not a policy. Reports per joint the PD-estimate magnitude against that
  joint's own solver-side limit. It is the load FLOOR (what standing costs), and it cannot answer the
  command window's question. The report carries ``settle_reached``: this body's stance never quiets
  below the tolerance, so the cap normally fires and the window is a micro-motion window. Caliber in
  :func:`run_static`.

Usage (from the repo root):

    python rl_exp/tools/verify/check_actuator_budget.py --task Lizard2-Flat-Play-v1
    python rl_exp/tools/verify/check_actuator_budget.py --task Lizard2-Flat-Play-v1 --json <report>
    python rl_exp/tools/verify/check_actuator_budget.py --task Lizard2-Flat-Play-v1 --drive-audit
    python rl_exp/tools/verify/check_actuator_budget.py --task Lizard2-Flat-Play-v1 --static-only

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
parser.add_argument("--static-settle", type=float, default=2.0,
                    help="zero-action seconds before the static (layer 3) window opens")
parser.add_argument("--static-s", type=float, default=2.0, help="seconds measured, static layer")
parser.add_argument("--static-vel", type=float, default=0.05,
                    help="static layer: settle until the fastest joint is below this [rad/s]")
parser.add_argument("--static-only", action="store_true",
                    help="skip layers 1-2 and the unloaded sweep: run the static load layer and exit")
parser.add_argument("--inertia", type=float, default=1.57,
                    help="swing inertia estimate [kg m^2] for the inertia-only column (printed, not used to pass/fail)")
parser.add_argument("--drive-audit", action="store_true",
                    help="skip the sweep: compare what each actuator declared against what the solver "
                         "holds per joint (the PhysX readback), and exit")
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


def run_drive_audit(task: str) -> dict:
    """What the SOLVER holds per joint, against what each actuator was asked for.

    ``joint_stiffness`` / ``joint_damping`` / ``joint_effort_limits`` / ``joint_vel_limits`` are cloned
    from the PhysX view at data-init, after the articulation handed the actuator cfg over -- so they are
    the solver's values, not the yaml's. This is the readback the group table above lacks: a group cfg
    says what was REQUESTED for its joints, this says what those joints GOT.

    What it still does not say: whether a policy ever asks those joints for anything, and whether the
    torque estimate in the sweeps below was clipped -- the readback is a statement about the drive, not
    about behaviour.
    """
    env = build(task, gravity_off=False)
    env.reset()
    robot = env.unwrapped.scene["robot"]
    names = list(robot.joint_names)
    held = {
        "stiffness": [float(v) for v in robot.data.joint_stiffness.torch[0]],
        "damping": [float(v) for v in robot.data.joint_damping.torch[0]],
        "effort_limit": [float(v) for v in robot.data.joint_effort_limits.torch[0]],
        "velocity_limit": [float(v) for v in robot.data.joint_vel_limits.torch[0]],
    }
    asked: dict[int, dict] = {}
    for key, actuator in robot.actuators.items():
        for index in actuator.joint_indices:
            config = actuator.cfg
            asked[int(index)] = {
                "group": key,
                "stiffness": float(config.stiffness),
                "damping": float(config.damping),
                "effort_limit": None if config.effort_limit_sim is None else float(config.effort_limit_sim),
                "velocity_limit": None if config.velocity_limit_sim is None else float(config.velocity_limit_sim),
            }

    rows: list[dict] = []
    print("=== drive audit: solver readback vs the actuator's declaration, per joint ===")
    print(f"  (readback = PhysX get_dof_* at data-init, after the cfg was handed over; task {task})")
    by_group: dict[str, list[dict]] = {}
    for index, joint in enumerate(names):
        spec = asked.get(index)
        row = {"joint": joint, "group": None if spec is None else spec["group"], "asked": spec,
               "solver": {name: values[index] for name, values in held.items()}}
        rows.append(row)
        by_group.setdefault(row["group"] or "<no actuator claims it>", []).append(row)
    for group, group_rows in by_group.items():
        lines, mismatched = [], False
        for name in ("stiffness", "damping", "effort_limit", "velocity_limit"):
            wanted = sorted({r["asked"][name] for r in group_rows if r["asked"]}, key=lambda v: (v is None, v))
            got = sorted({r["solver"][name] for r in group_rows})
            if wanted == [None]:
                # The cfg declared no value (this fork drops a bare velocity_limit), so the drive kept
                # whatever the spawn gave it. That is the known fork behaviour, and the held number IS
                # the finding -- counting it as a disagreement would report every run as broken.
                lines.append(f"      {name:15s} asked=none (cfg dropped by the fork) held={got}")
                continue
            match = len(wanted) == 1 and all(abs(wanted[0] - value) < 1e-6 for value in got)
            mismatched = mismatched or not match
            lines.append(f"      {name:15s} asked={wanted} held={got}" + ("" if match else "   <-- differs"))
        print(f"  {group:22s} joints={len(group_rows):2d} {'differs' if mismatched else 'matches'}")
        for line in lines:
            print(line)
    unclaimed = [row["joint"] for row in rows if row["asked"] is None]
    print(f"  joints audited: {len(rows)}; claimed by no actuator: {unclaimed if unclaimed else 'none'}")
    print("  the velocity row is the answer to \"did the yaml velocity_limit reach the sim\": whatever")
    print("  'held' shows is the drive's cap, and no cfg value has to be involved in it.")
    env.close()
    return {"task": task, "joints": rows, "unclaimed": unclaimed}


def run_static(task: str, settle_s: float, window_s: float, settle_vel: float) -> dict:
    """Gravity on, zero action: what the settled stance costs each joint, against its OWN limit.

    Caliber, stated because a number without it is not a reading:

    * estimate = ``Kp*(q*-q) - Kd*qd`` with ``Kp``/``Kd`` read from the solver, same expression the
      sweeps and the reward reconstruction use (``parkour_mdp.py:271``);
    * divisor = the joint's OWN limit read back from the solver (``data.joint_effort_limits``), not the
      group cfg -- the per-joint convention the gait probe adopted after one group-wide value was found
      scoring hip joints against the foot's limit (``2026-09-23-lizard2-v1-gait-skate.md`` ⑫);
    * settle = step until BOTH the body has stopped descending (its height moves less than 1e-4 m over
      five frames, minimum 10 frames) AND the fastest joint is slower than ``settle_vel`` [rad/s], with
      ``settle_s`` as the CAP. Joint speed alone is NOT a settle criterion and was tried first: on frame
      1 every joint is slower than the tolerance because nothing has moved yet, so the window opens
      while the body is still falling from its spawn height -- the report carries the steps taken, the
      speed and the height, which is what makes that visible instead of silent;
    * a cap that fires is NOT a settle, and the report says which of the three happened
      (``settle_reached`` / ``settle_landed``): landed-but-still-moving is a MICRO-MOTION window, a body
      still moving in height is not a stance at all, and either way ``base_height_m`` is the height AT
      THE CAP, not a settled stance height. On this body the cap firing is the normal outcome, not a
      defect -- the stance never quiets below the tolerance
      (``2026-10-09-lizard2-static-load-demand.md`` ⑤), so reading the height as "where it settled" is
      exactly the mistake the flags exist to prevent;
    * window = after that, until the first env reset or the frame the base drops below half the height
      the window opened at. A fallen or just-reset frame is not a stance, and averaging one in would
      report a load no stance ever carried;
    * the counter is ``pd_estimate_over_limit_frac``, NOT "saturation": an estimate crossing the limit
      is not the solver clipping. ``applied_torque`` is structurally zero for implicit drives and the
      clip happens inside the solver, so the crossing is a hypothesis about clamping, not a reading.

    What it is for: the load floor. It says how much of the budget a standing robot spends, not what a
    gait at speed needs -- a static reading cannot answer the command window's question.
    """
    env = build(task, gravity_off=False)
    env.reset()
    robot = env.unwrapped.scene["robot"]
    names = list(robot.joint_names)
    limits = [float(v) for v in robot.data.joint_effort_limits.torch[0]]
    dt = float(env.unwrapped.step_dt)
    zero = torch.zeros((1, action_map(env)[1]), device=robot.device)
    settle_steps, cap, quiet = 0, max(20, int(settle_s / dt)), float("inf")
    settle_reached, landed = False, False
    heights: list[float] = []
    while settle_steps < cap:
        env.step(zero)
        settle_steps += 1
        quiet = float(robot.data.joint_vel.torch[0].abs().max())
        heights.append(float(robot.data.root_pos_w.torch[0, 2]))
        landed = len(heights) > 10 and max(heights[-5:]) - min(heights[-5:]) < 1e-4
        if landed and quiet < settle_vel:
            settle_reached = True
            break
    height0 = float(robot.data.root_pos_w.torch[0, 2])

    samples = {index: [] for index in range(len(names))}
    frames, stop = 0, "window closed"
    for _ in range(max(2, int(window_s / dt))):
        env.step(zero)
        if int(env.unwrapped.episode_length_buf[0]) <= 1:
            stop = "env reset inside the window (the frames before it are kept)"
            break
        if float(robot.data.root_pos_w.torch[0, 2]) < 0.5 * height0:
            stop = "base dropped below half its settled height"
            break
        frames += 1
        kp = robot.data.joint_stiffness.torch[0]
        kd = robot.data.joint_damping.torch[0]
        torque = kp * (robot.data.joint_pos_target.torch[0] - robot.data.joint_pos.torch[0]) \
            - kd * robot.data.joint_vel.torch[0]
        for index in range(len(names)):
            samples[index].append(abs(float(torque[index])))

    rows = []
    print(f"\n=== layer 3 STATIC: gravity on, zero action, {frames} frame(s) measured ===")
    if settle_reached:
        settle_note = f"settle REACHED (landed AND quiet): base height {height0:.4f} m"
    elif landed:
        settle_note = (f"settle NOT reached -- the cap fired with the body landed but still moving: "
                       f"MICRO-MOTION window, base height at the cap {height0:.4f} m, not a settled "
                       f"stance")
    else:
        settle_note = (f"settle NOT reached -- the cap fired with the body still moving IN HEIGHT "
                       f"(landed=False): the window below is over a body that never stabilized, so "
                       f"{height0:.4f} m is not a stance height")
    print(f"  settle: {settle_steps}/{cap} step(s) of the {settle_s:.1f}s cap; fastest joint "
          f"{quiet:.4f} rad/s at that point (tol {settle_vel}); {settle_note}")
    print(f"  ({stop}; estimate {('Kp*(q*-q) - Kd*qd')})")
    print("  zero action = the DEFAULT joint targets held by PD: a posture, not a trained policy, and")
    print("  not a gait -- a joint with no budget left here still has to be asked by something.")
    print("  joint                group    p50_nm  p95_nm  max_nm  limit_nm  frac_of_limit_p50  pd_est_over_limit_frac")
    groups: dict[str, list[float]] = {}
    for index, name in enumerate(names):
        values = sorted(samples[index])
        if not values:
            continue
        p50 = values[len(values) // 2]
        p95 = values[min(len(values) - 1, int(0.95 * len(values)))]
        limit = limits[index]
        frac = p50 / limit if limit else float("nan")
        over = sum(1 for value in values if value >= limit) / len(values)
        group = next((key for key, actuator in robot.actuators.items() if index in actuator.joint_indices),
                     "<none>")
        groups.setdefault(group, []).append(frac)
        rows.append({"joint": name, "group": group, "p50_nm": p50, "p95_nm": p95, "max_nm": values[-1],
                     "effort_limit_nm": limit, "frac_of_limit_p50": frac,
                     "pd_estimate_over_limit_frac": over})
        print(f"  {name:20s} {group:8s} {p50:7.2f} {p95:7.2f} {values[-1]:7.2f} {limit:9.0f} "
              f"{frac:18.3f} {over:21.3f}")
    for group, fracs in groups.items():
        print(f"  {group:8s} worst frac_of_limit_p50 = {max(fracs):.3f} over {len(fracs)} joint(s)")
    print("  scope: a stance is not a gait. This is a load FLOOR, and 'estimate over limit' is not")
    print("         'the solver clamped' -- see the caliber in run_static's docstring.")
    env.close()
    return {"task": task, "frames": frames, "settle_s": settle_s, "settle_steps": settle_steps,
            "settle_cap_steps": cap, "settle_reached": settle_reached, "settle_landed": landed,
            "settle_vel_tol": settle_vel, "settle_fastest_rad_s": quiet,
            "stop": stop, "base_height_m": height0, "joints": rows}


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


if args_cli.drive_audit:
    audit = run_drive_audit(args_cli.task)
    if args_cli.json:
        pathlib.Path(args_cli.json).write_text(json.dumps(audit, ensure_ascii=False, indent=1) + "\n",
                                              encoding="utf-8")
        print(f"report written: {args_cli.json}")
    print("DRIVE_AUDIT_MEASURED")
    sys.exit(0)

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

if args_cli.static_only:
    measurement = run_static(args_cli.task, args_cli.static_settle, args_cli.static_s, args_cli.static_vel)
    if args_cli.json:
        pathlib.Path(args_cli.json).write_text(json.dumps(measurement, ensure_ascii=False, indent=1) + "\n",
                                              encoding="utf-8")
        print(f"report written: {args_cli.json}")
    print("STATIC_LOAD_MEASURED")
    sys.exit(0)

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

static = run_static(args_cli.task, args_cli.static_settle, args_cli.static_s, args_cli.static_vel)

if args_cli.json:
    pathlib.Path(args_cli.json).write_text(json.dumps(
        {"task": args_cli.task, "amplitude_rad": args_cli.amplitude, "limits": limits,
         "unloaded": unloaded, "loaded": loaded, "static": static}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    print(f"report written: {args_cli.json}")
print("ACTUATOR_CURVE_MEASURED")
