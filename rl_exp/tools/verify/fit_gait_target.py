# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Solve a leg chain against ONE engineered gait cycle, phase by phase, and report the residuals.

``check_leg_reachability`` answers "can this chain pose a level pad somewhere inside its limits" -- a
reachability question. The design question is "can this chain follow the target cycle", and answering
it needs a target, a solve, and a per-criterion residual per phase. The target is data, not code:
``gait_targets/lizard2_low_speed_v0.json``. Every number in it carries a source label and the fields it
does NOT have are listed there too; read that file's ``status`` before quoting any output. An
engineered target says what a robot was asked to do, never what an animal did.

What the solver maximises, and it is a solve rather than a search with post-hoc checks:

* **Every criterion is in the objective, normalised by its own tolerance** (position, pad facing while
  the phase is stance, ground contact or clearance, thigh direction where an anchor exists). A criterion
  that is merely reported after the fact says only that *this* pose failed -- it cannot rule out another
  pose, and removing it from the checks then looks like an improvement. Each term is ``residual /
  tolerance``, so no scale is invented here: the tolerances are the target's own.
* **Joint excursion is a micro tie-break (1e-6 m per radian)**, not a weighted term: a weight large
  enough to choose between equally good poses is also large enough to buy position error (measured: 1 cm
  per radian left a reachable target 13 mm short).

Three readings this tool refuses to let a reader conflate:

* **Thigh direction is read as an elevation off the HORIZONTAL PLANE**, with the azimuth reported next
  to it. The x-z projection was reported once before: at phase 4 it gave -89 deg for a femur that is
  actually (0.0037, 0.4129, -0.2849) m, i.e. -34.6 deg off the horizontal and almost entirely sideways.
  A projection that drops the lateral component reads a sprawling leg as a vertical one.
* **Ground contact is the pad's own lowest vertex** (``pad_state``'s ``lowest_z``), never the pad
  origin: the origin can be exactly where the path says while the sole is 3 cm under the floor. A
  target that declares ``stance_reference: sole_on_floor`` is lifted by the standing sole's own height
  before its offsets apply, because a stance phase is a contact and the contact is the sole.
* **Continuity includes the cycle closure** (last phase to the next cycle's first) and is reported as a
  joint rate against the URDF's OWN velocity limit, over the target's own sampling interval. Denser
  sampling shrinks adjacent steps without saying anything about branch continuity, which is NOT checked
  here and is named as unchecked in the output.

Candidate B -- the asset plus one revolute along the femur -- is seeded from A's solution with the
inserted joint at zero, so its reachable set provably contains A's answer and B can never score worse
for solver reasons. A B that merely ties A means this target does not ask for the axis; it is not
evidence about the structure.

Usage:

    python rl_exp/tools/verify/fit_gait_target.py --self-check
    python rl_exp/tools/verify/fit_gait_target.py
    python rl_exp/tools/verify/fit_gait_target.py --speed 0.45 --asset-only
    python rl_exp/tools/verify/fit_gait_target.py --speed 0.45 --facing-mid-stance --asset-only
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import check_leg_reachability as K  # noqa: E402 - the FK lives next door on purpose: reused, not copied

DEFAULT_TARGET = pathlib.Path(__file__).resolve().parent / "gait_targets" / "lizard2_low_speed_v0.json"


def load_target(path: pathlib.Path) -> dict:
    target = json.loads(path.read_text(encoding="utf-8"))
    for key in ("meta", "body", "gait", "facing", "tolerances", "phases"):
        if key not in target:
            raise SystemExit(f"{path}: no '{key}' block -- see the tool's docstring for the shape")
    if target["body"].get("leg") is not None and target["meta"].get("leg") != target["body"]["leg"]:
        raise SystemExit(f"{path}: meta.leg and body.leg disagree")
    for tol in ("position_m", "facing_deg", "limit_margin_rad", "joint_step_rad", "contact_m",
                "clearance_m", "thigh_elev_deg"):
        if tol not in target["tolerances"]:
            raise SystemExit(f"{path}: tolerances.{tol} is missing; the solver normalises by it")
    return target


def joint_velocity_limits(urdf: pathlib.Path) -> dict[str, float]:
    """Every joint's own velocity limit [rad/s] from the URDF -- the physical bound, not a chosen one."""
    limits = {}
    for joint in ET.parse(urdf).getroot().iter("joint"):
        velocity = joint.find("limit").get("velocity") if joint.find("limit") is not None else None
        if velocity is not None:
            limits[joint.get("name")] = float(velocity)
    return limits


def zero_pose(urdf: pathlib.Path, leg: str, base_z: float):
    """The leg's standing pose: what target offsets are relative to, and what excursion is priced from."""
    chain = K.load_chain(urdf, leg)
    normal = K.pad_normal_in_link(urdf, leg)
    vertices = K.pad_vertices(urdf, leg)
    angles = [0.0] * len(chain)
    return chain, normal, vertices, angles, K.foot_pose(chain, angles)[0]


def _distance(a, b) -> float:
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def femur_read(chain, frames) -> dict:
    """The femur (the haa frame to the knee axis) as an elevation off the horizontal, plus its azimuth.

    Both ends are located **by joint name**. An index-based read broke twice on a candidate that
    inserted a joint: the femur came out as the shank (indices shifted) and then as a zero vector
    (the fixture moves the knee's own origin into the inserted joint), and a zero femur reads as a
    perfectly level thigh, which quietly satisfies any direction criterion set on it.
    """
    haa = next(index for index, joint in enumerate(chain) if joint["token"] == "haa")
    knee = next(index for index, joint in enumerate(chain) if joint["token"] == "hfe")
    femur = [frames[knee + 1][i][3] - frames[haa + 1][i][3] for i in range(3)]
    lateral = math.hypot(femur[0], femur[1])
    return {
        "femur_m": femur,
        "femur_len_m": math.sqrt(sum(value * value for value in femur)),
        "thigh_elev_deg": math.degrees(math.atan2(femur[2], lateral)),
        "thigh_azim_deg": math.degrees(math.atan2(femur[1], femur[0])),
    }


def residuals(chain, angles, normal, vertices, base_z, phase, target, point, facing_required):
    """Every criterion's residual for one pose, each in its own unit, plus the normalised cost.

    Normalising by the criterion's own tolerance (``tolerances`` in the target) is what lets a facing
    shortfall, a millimetre of ground penetration and a direction error be added without inventing a
    scale: a criterion met has a term below 1, one missed has a term above it.
    """
    state = K.pad_state(chain, angles, normal, vertices, base_z)
    stance = phase["contact"] == "stance"
    tol = target["tolerances"]
    terms, values = [], {}
    values["position_error_m"] = _distance(state["position"], point)
    terms.append(values["position_error_m"] / tol["position_m"])
    values["facing_deg"] = state["tilt_deg"]
    if facing_required:
        terms.append(max(0.0, values["facing_deg"] - tol["facing_deg"]) / tol["facing_deg"])
    values["lowest_z_m"] = state["lowest_z"]
    if stance:
        terms.append(max(0.0, abs(values["lowest_z_m"]) - tol["contact_m"]) / tol["contact_m"])
    else:
        terms.append(max(0.0, tol["clearance_m"] - values["lowest_z_m"]) / tol["clearance_m"])
    values.update(femur_read(chain, state["frames"]))
    anchor = phase.get("thigh_elev_deg")
    if anchor is not None:
        terms.append(max(0.0, abs(values["thigh_elev_deg"] - anchor) - tol["thigh_elev_deg"])
                     / tol["thigh_elev_deg"])
    values["angles"] = angles
    values["terms"] = terms
    values["cost"] = sum(term * term for term in terms) + 1e-6 * sum(abs(value) for value in angles)
    return values


def _clipped(chain, angles):
    return [min(max(angles[i], chain[i]["limits"][0]), chain[i]["limits"][1]) for i in range(len(chain))]


def solve(chain, normal, vertices, base_z, phase, target, point, facing_required, seed, samples=9, sweeps=25):
    """Scan one joint at a time and repeat from ``seed``: monotone, deterministic, limit-respecting.

    A coarse grid over every joint at once was tried and dropped: with five or six joints the grid is
    either too coarse to seed the descent near a solution or too large to run, and the descent then
    stalled against a limit 13 mm from a target its own FK had produced.
    """
    best = _clipped(chain, list(seed))
    best_cost = residuals(chain, best, normal, vertices, base_z, phase, target, point,
                          facing_required)["cost"]
    for _ in range(sweeps):
        improved = False
        for index in range(len(chain)):
            low, high = chain[index]["limits"]
            for step in range(samples):
                trial = list(best)
                trial[index] = low + (high - low) * step / (samples - 1)
                read = residuals(chain, trial, normal, vertices, base_z, phase, target, point,
                                 facing_required)
                if read["cost"] < best_cost:
                    best, best_cost, improved = trial, read["cost"], True
        if not improved:
            break
    for step in (0.02, 0.005, 0.001):
        for _ in range(40):
            improved = False
            for index in range(len(chain)):
                for delta in (step, -step):
                    trial = _clipped(chain, list(best[:index] + [best[index] + delta] + best[index + 1:]))
                    read = residuals(chain, trial, normal, vertices, base_z, phase, target, point,
                                     facing_required)
                    if read["cost"] < best_cost:
                        best, best_cost, improved = trial, read["cost"], True
            if not improved:
                break
    return best


def _mid_stance(phases, enabled):
    """Which phases still demand a level pad: all stance, or only the middle half of it (D1's option b)."""
    stance = [index for index, phase in enumerate(phases) if phase["contact"] == "stance"]
    if not enabled:
        return set(stance)
    quarter = len(stance) // 4
    return set(stance[quarter:len(stance) - quarter])


def _flags(entry, target, step_rad, rate, velocity_limit, have_previous) -> list[str]:
    tol = target["tolerances"]
    flags = []
    if entry["position_error_m"] > tol["position_m"]:
        flags.append("POS")
    if entry["facing_required"] and entry["facing_deg"] > tol["facing_deg"]:
        flags.append("FACE")
    if entry["contact"] == "stance":
        if abs(entry["lowest_z_m"]) > tol["contact_m"]:
            flags.append("CONTACT")
    elif entry["lowest_z_m"] < tol["clearance_m"]:
        flags.append("CLEARANCE")
    if entry["min_limit_margin_rad"] < tol["limit_margin_rad"]:
        flags.append("LIMIT")
    if entry.get("thigh_elev_deg") is not None and entry.get("thigh_anchor_deg") is not None \
            and abs(entry["thigh_elev_deg"] - entry["thigh_anchor_deg"]) > tol["thigh_elev_deg"]:
        flags.append("THIGH")
    if have_previous and step_rad > tol["joint_step_rad"]:
        flags.append("STEP")
    if have_previous and velocity_limit is not None and rate > velocity_limit:
        flags.append("RATE")
    return flags


def run_one(label, urdf, target, leg, base_z, args, reference, seed_rows=None) -> dict:
    chain, normal, vertices, zero, _ = zero_pose(urdf, leg, base_z)
    scale = (args.speed / target["gait"]["speed_m_per_s"]) if args.speed else 1.0
    velocity = joint_velocity_limits(urdf)
    names = [joint["name"] for joint in chain]
    at = _mid_stance(target["phases"], args.facing_mid_stance)
    dt = target["gait"]["period_s"] / target["gait"]["phases_per_cycle"]
    # Where the sole of the standing pose sits relative to the ground: a target that says "stance" has
    # to be stated against the sole, not the pad origin, or the cycle asks for a contact it cannot have.
    sole_at_rest = (K.pad_state(chain, zero, normal, vertices, base_z)["lowest_z"]
                    if target.get("stance_reference") == "sole_on_floor" else 0.0)
    rows, previous = [], None
    for index, phase in enumerate(target["phases"]):
        dz = phase["dz_m"] - sole_at_rest if phase["contact"] == "stance" else phase["dz_m"]
        point = [reference[0] + phase["dx_m"] * scale, reference[1], reference[2] + dz]
        facing_required = (phase["contact"] == "stance"
                           and target["facing"]["required_during_stance"] and index in at)
        seed = list(zero)
        if seed_rows is not None:
            # By NAME, not by position: the inserted joint sits inside the chain, so padding A's angles
            # at the end would shift every angle past it into the wrong joint.
            by_name = seed_rows[index]["angle_by_name"]
            seed = [by_name.get(joint["name"], 0.0) for joint in chain]
        angles = solve(chain, normal, vertices, base_z, phase, target, point, facing_required, seed,
                       samples=args.samples)
        entry = residuals(chain, angles, normal, vertices, base_z, phase, target, point, facing_required)
        entry.update(phase)
        entry["angle_by_name"] = dict(zip(names, angles))
        entry["dx_sweep_m"] = phase["dx_m"] * scale
        entry["facing_required"] = facing_required
        entry["thigh_anchor_deg"] = phase.get("thigh_elev_deg")
        entry["min_limit_margin_rad"] = min(
            min(angles[i] - chain[i]["limits"][0], chain[i]["limits"][1] - angles[i])
            for i in range(len(chain)))
        step = max((abs(angles[i] - previous[i]) for i in range(len(chain))) if previous is not None else [0.0])
        entry["step_rad"] = step
        entry["rate_rad_s"] = step / dt
        entry["velocity_limit_rad_s"] = min(velocity.get(name, math.inf) for name in names)
        entry["flags"] = _flags(entry, target, step, entry["rate_rad_s"], entry["velocity_limit_rad_s"],
                                previous is not None)
        rows.append(entry)
        previous = angles
    closure = max(abs(rows[0]["angles"][i] - rows[-1]["angles"][i]) for i in range(len(chain)))
    return {"label": label, "urdf": urdf, "joints": len(chain), "rows": rows,
            "closure_rad": closure, "closure_rate_rad_s": closure / dt}


def _table(result: dict) -> None:
    print(f"  {result['label']}: {result['urdf']}  ({result['joints']} joints)")
    print(f"  {'ph':>3} {'contact':<6} {'dx_mm':>7} {'dz_mm':>6} {'pos_mm':>7} {'face_deg':>8} "
          f"{'sole_mm':>8} {'margin_deg':>10} {'step_deg':>8} {'rate_deg/s':>10} {'elev_deg':>8} "
          f"{'azim_deg':>8}  flags")
    for row in result["rows"]:
        print(f"  {int(row['phase']):>3} {row['contact']:<6} {row['dx_sweep_m'] * 1000:>7.1f} "
              f"{row['dz_m'] * 1000:>6.1f} {row['position_error_m'] * 1000:>7.1f} {row['facing_deg']:>8.1f} "
              f"{row['lowest_z_m'] * 1000:>8.1f} {math.degrees(row['min_limit_margin_rad']):>10.1f} "
              f"{math.degrees(row['step_rad']):>8.1f} {math.degrees(row['rate_rad_s']):>10.1f} "
              f"{row['thigh_elev_deg']:>8.1f} {row['thigh_azim_deg']:>8.1f}  {','.join(row['flags']) or '-'}")
    failed = [int(row["phase"]) for row in result["rows"] if row["flags"]]
    thigh = [row["thigh_elev_deg"] for row in result["rows"]]
    print(f"  failed phases: {failed or 'none'}")
    print(f"  thigh elevation over the cycle {min(thigh):.1f} .. {max(thigh):.1f} deg (off the HORIZONTAL "
          f"plane; x-z projection would read these wrong)")
    print(f"  cycle closure (last phase -> next cycle's phase 0): {math.degrees(result['closure_rad']):.1f} deg "
          f"= {math.degrees(result['closure_rate_rad_s']):.1f} deg/s; branch continuity: not checked")


def compare(base: dict, other: dict) -> None:
    print("  A vs B (candidate cost minus asset cost, per phase; B is seeded from A, so it cannot be worse):")
    worst = max(second["cost"] - first["cost"] for first, second in zip(base["rows"], other["rows"]))
    print(f"    worst B-minus-A normalised cost: {worst:+.2e}")
    ties = 0
    for first, second in zip(base["rows"], other["rows"]):
        delta = (second["position_error_m"] - first["position_error_m"]) * 1000
        if abs(delta) < 0.1 and first["flags"] == second["flags"]:
            ties += 1
            continue
        print(f"    phase {int(first['phase']):>2}: position {delta:+6.2f} mm   "
              f"A [{','.join(first['flags']) or '-'}]  B [{','.join(second['flags']) or '-'}]")
    print(f"    phases where B merely ties A: {ties}/{len(base['rows'])}")
    if ties == len(base["rows"]):
        print("    -> this target asks nothing of the inserted axis: it does not show a need for it, "
              "and says nothing against the structure")


def _position_only(target: dict) -> dict:
    """The same target with every criterion but position made unfalsifiable: how the search is tested.

    The solve is only asked to reach a point when it is not simultaneously being asked for a pad
    orientation, a ground contact and a thigh direction; a control that left those in would measure the
    compromise, not the search.
    """
    loose = json.loads(json.dumps(target))
    loose["tolerances"].update({"facing_deg": 1e9, "contact_m": 1e9, "clearance_m": 1e9,
                                "thigh_elev_deg": 1e9, "position_m": target["tolerances"]["position_m"]})
    return loose


def self_check(target: dict, leg: str, args) -> int:
    failures = 0
    base_z = target["body"]["base_z_m"]
    chain, normal, vertices, zero, reference = zero_pose(args.urdf, leg, base_z)
    only = _position_only(target)
    phase = target["phases"][0]
    pose = ([0.3, -0.2, 0.4, -0.5, 0.1] + [0.0])[: len(chain)]
    reachable = K.pad_state(chain, pose, normal, vertices, base_z)["position"]
    found = solve(chain, normal, vertices, base_z, phase, only, reachable, False, zero, samples=args.samples)
    error = _distance(K.foot_pose(chain, found)[0], reachable)
    print(f"  control 1 (position-only target drawn from this chain's own FK is reached): "
          f"{error * 1000:.3f} mm")
    failures += error > 0.002
    far = [reference[0] + 1.0, reference[1] + 1.0, reference[2] - 1.0]
    found = solve(chain, normal, vertices, base_z, phase, only, far, False, zero, samples=args.samples)
    error = _distance(K.foot_pose(chain, found)[0], far)
    rejected = error > target["tolerances"]["position_m"]
    print(f"  control 2 (a target a metre away is reported unreachable): {error * 1000:.1f} mm "
          f"-> {'yes' if rejected else 'WRONGLY ACCEPTED'}")
    failures += not rejected
    inside = all(chain[i]["limits"][0] <= found[i] <= chain[i]["limits"][1] for i in range(len(chain)))
    print(f"  control 3 (the solve stays inside the limits): {'yes' if inside else 'NO'}")
    failures += not inside
    with tempfile.TemporaryDirectory(prefix="fit_self_check_") as folder:
        candidate = K._inserted_joint_urdf(args.urdf, leg, args.b_token, pathlib.Path(folder))
        asset = run_one("A", args.urdf, target, leg, base_z, args, reference)
        extra = run_one("B", candidate, target, leg, base_z, args, reference, seed_rows=asset["rows"])
        worst = max(second["cost"] - first["cost"] for first, second in zip(asset["rows"], extra["rows"]))
        print(f"  control 4 (B seeded from A cannot cost more): worst {worst:+.2e} "
              f"-> {'yes' if worst <= 1e-9 else 'NO'}")
        failures += worst > 1e-9
    print(f"  SELF_CHECK_{'OK' if failures == 0 else 'FAILED'}")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", type=pathlib.Path, default=DEFAULT_TARGET)
    parser.add_argument("--urdf", type=pathlib.Path, default=K.DEFAULT_URDF)
    parser.add_argument("--leg", default=None, help="default: the target's own leg")
    parser.add_argument("--candidate-b", type=pathlib.Path, default=None,
                        help="default: the asset plus one revolute along the femur, built as a fixture")
    parser.add_argument("--b-token", default="ferot")
    parser.add_argument("--samples", type=int, default=9, help="values per joint in the one-joint scan")
    parser.add_argument("--speed", type=float, default=None,
                        help="override the target's speed [m/s]; stance offsets scale with it, which is "
                             "how a sensitivity run is made")
    parser.add_argument("--asset-only", action="store_true")
    parser.add_argument("--facing-mid-stance", action="store_true",
                        help="D1's option b: demand a level pad only through the middle half of stance")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()

    target = load_target(args.target)
    leg = args.leg or target["meta"]["leg"]
    base_z = target["body"]["base_z_m"]
    if args.self_check:
        raise SystemExit(self_check(target, leg, args))

    print(f"target {args.target.name}: {target['meta']['status']}")
    print(f"  leg {leg}, period {target['gait']['period_s']} s, speed {target['gait']['speed_m_per_s']} m/s, "
          f"duty {target['gait']['hind_duty']}, stance sweep {target['gait']['stance_sweep_m']} m")
    print(f"  body z {base_z} m; level pad required in: "
          f"{'mid-stance only' if args.facing_mid_stance else 'all stance'}; tolerances pos "
          f"{target['tolerances']['position_m'] * 1000:.0f} mm, contact "
          f"{target['tolerances']['contact_m'] * 1000:.0f} mm, clearance "
          f"{target['tolerances']['clearance_m'] * 1000:.0f} mm, facing "
          f"{target['tolerances']['facing_deg']:.0f} deg, step {target['tolerances']['joint_step_rad']:.2f} rad")
    if args.speed:
        print(f"  speed override {args.speed} m/s -> stance sweep "
              f"{target['gait']['stance_sweep_m'] * args.speed / target['gait']['speed_m_per_s']:.4f} m")
    chain_a, _, _, _, reference = zero_pose(args.urdf, leg, base_z)
    femur = math.sqrt(sum(value * value for value in chain_a[2]["origin"]))
    print(f"  A standing pad origin {[round(value, 4) for value in reference]} m; femur length {femur:.4f} m")

    asset = run_one("A (asset)", args.urdf, target, leg, base_z, args, reference)
    print()
    _table(asset)
    if args.asset_only:
        return
    with tempfile.TemporaryDirectory(prefix="fit_candidate_") as folder:
        candidate = args.candidate_b or K._inserted_joint_urdf(args.urdf, leg, args.b_token,
                                                              pathlib.Path(folder))
        extra = run_one(f"B ({args.b_token})", candidate, target, leg, base_z, args, reference,
                        seed_rows=asset["rows"])
        print()
        _table(extra)
        print()
        compare(asset, extra)


if __name__ == "__main__":
    main()
