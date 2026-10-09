# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Where the initial action distribution lands relative to each joint's hard stop. Offline.

Why this is a pre-training question and not a reward question. The actor's mean starts near zero and
its spread is the exploration standard deviation it was initialized with, so the first samples a
policy ever issues are ``scale * N(0, sigma)`` per channel. A target outside the joint's stop is a
command the joint cannot reach: the solver holds the joint at the stop while the PD keeps pushing
into it, so those samples spend their episode learning about a wall rather than about the leg. How
much of that is acceptable needs a requirement (a target velocity band, a posture goal) which this
repo has not declared for this line, so **nothing here passes or fails** -- it prints the number that
a decision would be made from.

What it reads, all offline (no simulator, no app):

* the action terms off the built env cfg -- which joints each one commands, its ``scale``, whether a
  ``clip`` is declared, whether the target rides the asset's default pose;
* each joint's hard stops off the URDF the family's own ``assets.json`` declares (``family_urdf``),
  so the table cannot describe a body nothing runs;
* the exploration standard deviation off the task's own runner cfg entry.

What it cannot say: what the policy does after training (the mean stops being zero); what the solver
does with an unreachable target (that is a torque question -- ``check_actuator_budget.py``); and
whether a fraction out of reach is a defect, which is the undeclared requirement above.

``Nm@stop`` and ``p_eff`` are read at each joint's NEARER stop, which is the side that binds: see
:func:`stop_readings`. Every joint of the current asset has symmetric stops, so that choice does not
show in today's table -- it starts to matter the moment the limits go asymmetric, which
``work/active/joint-limit-shape-and-range-pass.md`` is about to do.

Usage (from the repo root):

    python rl_exp\\tools\\verify\\action_range_check.py --task Lizard2-Flat-v3
    python rl_exp\\tools\\verify\\action_range_check.py --task Lizard2-Flat-v3 --json "%TEMP%\\range.json"
    python rl_exp\\tools\\verify\\action_range_check.py --self-check
"""

import argparse
import json
import math
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "rl_exp" / "tools" / "verify"))

import gymnasium as gym  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

import rl_exp.tasks  # noqa: E402
from isaaclab.utils.string import string_to_callable  # noqa: E402
from rl_exp.tasks import obs_protocol  # noqa: E402

from check_leg_reachability import family_urdf  # noqa: E402  (one home for "which body")

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument("--task", default="Lizard2-Flat-v3")
parser.add_argument("--sigma", type=float, default=None,
                    help="override the exploration std (default: the task's own runner cfg)")
parser.add_argument("--reach", type=float, default=3.0,
                    help="the multiple of sigma whose target is reported as the reach case")
parser.add_argument("--json", help="write the measured table here")
parser.add_argument("--self-check", action="store_true",
                    help="test this tool's stop arithmetic (asymmetric limits) instead of reading a task")
args_cli = parser.parse_args()


def joint_limits(urdf: pathlib.Path) -> dict[str, tuple[float, float]]:
    """``<joint name>`` -> ``(lower, upper)`` in rad, read off the URDF, never a hand-written table."""
    out: dict[str, tuple[float, float]] = {}
    for joint in ET.parse(urdf).getroot().findall("joint"):
        limit = joint.find("limit")
        if limit is not None and limit.get("lower") is not None and limit.get("upper") is not None:
            out[joint.get("name")] = (float(limit.get("lower")), float(limit.get("upper")))
    return out


def tail_probability(limit: float, mean: float, sigma: float, side: str) -> float:
    """P(reaching past ``limit``) for a Gaussian target: the fraction of samples that ask for it."""
    if sigma <= 0.0:
        return 0.0
    z = (limit - mean) / (sigma * math.sqrt(2.0))
    if side == "upper":
        return 0.5 * math.erfc(z)
    return 0.5 * math.erfc(-z)


def stop_readings(lower: float, upper: float, kp: float | None, effort: float | None,
                  sigma_target: float, reach: float) -> dict:
    """The stop-side readings for one channel. **The NEARER stop binds.**

    Seated there the PD has the longer way to travel, so it sees the larger demand, and it is the side
    a target centred on zero crosses first. Every joint of the current asset has symmetric stops
    (``hip``/``haa`` ±0.60, ``hfe`` ±1.20, ``kfe`` ±1.60, spine ±0.50/±0.60), so which side is taken
    does not show in today's table -- but reading the FARTHER side would under-report both the demand
    and the tail probability the moment the limits go asymmetric, which is what
    ``work/active/joint-limit-shape-and-range-pass.md`` is about to do. ``--self-check`` pins the
    choice with a hand case.
    """
    near = min(abs(lower), abs(upper))
    demand_stop = None if (kp is None or effort is None) else near + effort / kp
    return {
        "near_stop": near,
        "target_at_reach": reach * sigma_target,
        "reach_out": reach * sigma_target > near,
        "nm_at_stop": None if kp is None else kp * max(0.0, reach * sigma_target - near),
        # Seated at the stop, the PD estimate is Kp*(target - stop): the samples whose demand exceeds
        # the joint's own effort limit are the ones the solver would clip. Both sides are asked, and
        # with a target centred on zero the nearer side's threshold subsumes the farther side's.
        "p_demand_over_effort": None if demand_stop is None else (
            tail_probability(demand_stop, 0.0, sigma_target, "upper")
            + tail_probability(-demand_stop, 0.0, sigma_target, "lower")),
    }


def scale_for(joint: str, scale) -> float:
    """The term's scale, whether it is one number or a per-pattern mapping."""
    if isinstance(scale, (int, float)):
        return float(scale)
    for pattern, value in scale.items():
        if re.fullmatch(pattern, joint):
            return float(value)
    raise KeyError(f"{joint}: the term's scale mapping matches no pattern of {sorted(scale)}")


def rows_for(cfg, limits: dict[str, tuple[float, float]], sigma: float, reach: float) -> list[dict]:
    """One row per commanded joint: the target's spread against that joint's own stops."""
    groups = {pattern: group
              for group in (getattr(getattr(cfg.scene, "robot", None), "actuators", {}) or {}).values()
              for pattern in group.joint_names_expr}
    rows: list[dict] = []
    for name in cfg.actions.__dataclass_fields__:
        term = getattr(cfg.actions, name)
        joint_names = getattr(term, "joint_names", None)
        scale = getattr(term, "scale", None)
        if joint_names is None or scale is None:
            continue
        matched = sorted(joint for joint in limits if any(re.fullmatch(p, joint) for p in joint_names))
        for joint in matched:
            lower, upper = limits[joint]
            width = scale_for(joint, scale)
            # The target rides the asset's default pose when use_default_offset is set; this line
            # declares zero default targets, so the distribution is centred on zero either way.
            target_sigma = width * sigma
            group = next((g for p, g in groups.items() if re.fullmatch(p, joint)), None)
            kp = None if group is None else float(group.stiffness)
            effort = None if group is None else scale_for(joint, group.effort_limit)
            rows.append({
                "term": name,
                "joint": joint,
                "scale": width,
                "sigma_target": target_sigma,
                "lower": lower,
                "upper": upper,
                "p_out": tail_probability(upper, 0.0, target_sigma, "upper")
                + tail_probability(lower, 0.0, target_sigma, "lower"),
                "kp": kp,
                "effort": effort,
                **stop_readings(lower, upper, kp, effort, target_sigma, reach),
            })
    return rows


def self_check() -> int:
    """One hand case, run by hand: asymmetric stops are read at the NEARER side.

    It falsifies the farther-side reading -- under it the ``(-0.60, +1.20)`` case would come out equal
    to the symmetric ``(-1.20, +1.20)`` case, so the last two assertions below would fire. Hand
    numbers: ``3 sigma = 1.5 rad`` against a near stop of 0.60 at ``Kp = 800`` -> 720 N.m.
    """
    kw = {"kp": 800.0, "effort": 180.0, "sigma_target": 0.5, "reach": 3.0}
    asymmetric = stop_readings(-0.60, 1.20, **kw)
    mirrored = stop_readings(-1.20, 0.60, **kw)
    symmetric = stop_readings(-1.20, 1.20, **kw)
    problems = []
    if asymmetric != mirrored:
        problems.append(f"mirroring the stops changed the reading: {asymmetric} vs {mirrored}")
    if abs(asymmetric["nm_at_stop"] - 720.0) > 1e-9:
        problems.append("near stop 0.60, 3 sigma 1.5 rad, Kp 800 must read 720 N.m, "
                        f"got {asymmetric['nm_at_stop']}")
    if not (asymmetric["nm_at_stop"] > symmetric["nm_at_stop"]
            and asymmetric["p_demand_over_effort"] > symmetric["p_demand_over_effort"]):
        problems.append("the near stop must demand more than the wide pair "
                        f"(nm {asymmetric['nm_at_stop']} vs {symmetric['nm_at_stop']}, "
                        f"p_eff {asymmetric['p_demand_over_effort']} vs "
                        f"{symmetric['p_demand_over_effort']})")
    if not asymmetric["reach_out"]:
        problems.append("a 1.5 rad target against a 0.60 rad stop is out of reach")
    if problems:
        print("SELF_CHECK_FAILED")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print("SELF_CHECK_OK (asymmetric stops bind at the nearer side; mirroring is a no-op)")
    return 0


def main() -> int:
    if args_cli.self_check:
        return self_check()
    spec = gym.spec(args_cli.task)
    cfg = string_to_callable(spec.kwargs["env_cfg_entry_point"])()
    runner = string_to_callable(spec.kwargs["rsl_rl_cfg_entry_point"])()
    sigma, source_of_sigma = args_cli.sigma, "--sigma override"
    if sigma is None:
        # New-style runner cfgs carry the std on the actor's distribution; older ones on `policy`.
        distribution = getattr(getattr(runner, "actor", None), "distribution_cfg", None)
        sigma = getattr(distribution, "init_std", None)
        source_of_sigma = "runner cfg: actor.distribution_cfg.init_std"
        if sigma is None:
            sigma = getattr(getattr(runner, "policy", None), "init_noise_std", None)
            source_of_sigma = "runner cfg: policy.init_noise_std"
    if sigma is None:
        raise SystemExit("no exploration std found on the task's runner cfg -- pass --sigma")
    family = obs_protocol.family_of(args_cli.task)
    urdf, source = family_urdf(_REPO / "rl_exp", family)
    limits = joint_limits(urdf)
    rows = rows_for(cfg, limits, sigma, args_cli.reach)

    spawn = getattr(getattr(cfg.scene, "robot", None), "init_state", None)
    spawn_z = None if spawn is None else (spawn.pos[2] if getattr(spawn, "pos", None) else None)

    print(f"task            {args_cli.task}")
    print(f"family / urdf   {family} / {urdf.name}  [{source}]")
    print(f"exploration std {sigma} ({source_of_sigma})")
    print(f"spawn z         {spawn_z} m  (declared; the settled stance is a measurement, not this)")
    print(f"channels        {len(rows)} commanded joint(s)")
    print()
    print(f"{'joint':<16}{'term':<12}{'scale':>6}{'limit [rad]':>16}{'sigma_t':>9}"
          f"{'p_out':>10}{'target@%gx' % args_cli.reach:>11}{'Nm@stop':>9}{'p_eff':>9}")
    for row in sorted(rows, key=lambda r: -r["p_out"]):
        limit = f"[{row['lower']:+.2f},{row['upper']:+.2f}]"
        nm = "-" if row["nm_at_stop"] is None else f"{row['nm_at_stop']:.1f}"
        p_eff = "-" if row["p_demand_over_effort"] is None else f"{row['p_demand_over_effort']:.2e}"
        print(f"{row['joint']:<16}{row['term']:<12}{row['scale']:>6.2f}{limit:>16}"
              f"{row['sigma_target']:>9.3f}{row['p_out']:>10.2e}{row['target_at_reach']:>11.2f}{nm:>9}{p_eff:>9}")
    over = [r for r in rows if r["reach_out"]]
    print()
    print(f"  channels whose +{args_cli.reach}x target is past the stop: {len(over)}/{len(rows)}"
          f"  (worst p_out {max((r['p_out'] for r in rows), default=0.0):.2e})")
    print(f"  any single-channel p_out > 1%: {sum(1 for r in rows if r['p_out'] > 0.01)}"
          f" | > 10%: {sum(1 for r in rows if r['p_out'] > 0.10)}")
    print(f"  p_eff = samples whose PD estimate would exceed the joint's own effort limit IF the joint "
          f"sat at its stop; worst {max((r['p_demand_over_effort'] or 0.0) for r in rows):.2e}"
          f" | channels > 1%: {sum(1 for r in rows if (r['p_demand_over_effort'] or 0.0) > 0.01)}")
    print("ACTION_RANGE_MEASURED")

    if args_cli.json:
        pathlib.Path(args_cli.json).write_text(json.dumps({
            "task": args_cli.task, "family": family, "urdf": str(urdf), "urdf_source": source,
            "sigma": sigma, "reach": args_cli.reach, "spawn_z": spawn_z, "rows": rows},
            indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
