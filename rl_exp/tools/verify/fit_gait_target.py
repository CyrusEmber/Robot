# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Score two leg chains against ONE engineered gait cycle, phase by phase.

``check_leg_reachability`` answers "can this chain pose a level pad somewhere inside its limits" -- a
reachability question. The design question is different: *can this chain follow the target cycle*, and
it needs a target, a per-phase verdict and a named failure position so two candidates can be argued
about with the same numbers.

The target is data, not code: ``gait_targets/lizard2_low_speed_v0.json``. Every number in it carries a
source label and the fields it does NOT have are listed there too; read that file's ``status`` before
quoting any output of this tool. An engineered target says what a robot was asked to do, never what an
animal did.

Four things are deliberately not hidden:

* **The objective is position plus a tie-break, not a weighted sum.** Facing, limit margin, continuity
  and the thigh anchor are *criteria that are checked and flagged*, never terms someone could pay off
  with a smaller position error, and the tie-break is a rounding of the position error rather than an
  invented weight (see :func:`_score` for the measured reason).
* **The fit is under-determined and says so.** Five (or six) joints against a three-component position
  target: many poses reach the same point. The tie is broken toward small joint excursion -- a choice
  (the least-excursion stance), not a property of the leg. A reader wanting a different pose out of the
  same point is arguing with the objective, not with FK.
* **Verdicts come from the target's own tolerances**, one flag per criterion per phase, so a chain that
  meets the position but wrecks the limit margin is reported as failing.
* **Nothing here is a design approval.** The target's tolerances are exploration thresholds; a green
  table says the candidate can follow *this* engineered cycle, nothing about an animal.

``--self-check`` runs three controls: a target drawn from a chain's own FK must be reached (the search
works), a target a metre away must be reported as a failure (the verdict fires), and the search must
stay inside the limits. It exits non-zero if any control misbehaves, which is what makes a green table
worth reading.

The inserted-joint candidate reuses ``check_leg_reachability``'s own fixture (``_inserted_joint_urdf``)
on purpose: one construction of "the asset plus a femoral revolute" in the repo, not two that drift.

Usage:

    python rl_exp/tools/verify/fit_gait_target.py --self-check
    python rl_exp/tools/verify/fit_gait_target.py
    python rl_exp/tools/verify/fit_gait_target.py --leg rr --candidate-b <candidate>.urdf
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
import tempfile

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
    return target


def zero_pose(urdf: pathlib.Path, leg: str, base_z: float):
    """The leg's standing pose: what target offsets are relative to, and what excursion is priced from."""
    chain = K.load_chain(urdf, leg)
    normal = K.pad_normal_in_link(urdf, leg)
    vertices = K.pad_vertices(urdf, leg)
    angles = [0.0] * len(chain)
    position = K.foot_pose(chain, angles)[0]
    return chain, normal, vertices, angles, position


def _distance(a, b) -> float:
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def _score(chain, angles, point, zero) -> float:
    """Position error, with joint excursion as a *micro*-tie-break rather than a weight.

    A weighted sum was tried and dropped: any weight large enough to choose between equally good
    positions is also large enough to buy position error with excursion (measured: 1 cm per rad left a
    reachable target 13 mm short). Rounding the error was tried and dropped too: the flat spots stop a
    descent while it is still 13 mm away. One micrometre per radian is small enough to only order
    positions that are otherwise equal.
    """
    position, _ = K.foot_pose(chain, angles)
    excursion = sum(abs(angles[i] - zero[i]) for i in range(len(angles)))
    return _distance(position, point) + 1e-6 * excursion


def _clipped(chain, angles):
    return [min(max(angles[i], chain[i]["limits"][0]), chain[i]["limits"][1]) for i in range(len(chain))]


def fit(chain, point, zero, samples: int, sweeps: int = 15):
    """Best pose found for one phase, by scanning one joint at a time and repeating.

    A coarse grid over every joint at once was tried and dropped: with five or six joints the grid is
    either too coarse to seed the descent near a solution or too large to run, and the descent then
    stalled against a limit 13 mm from a target its own FK had produced. Scanning a single joint across
    its whole range is 9 poses instead of 3000, and repeating it monotonically improves until a sweep
    changes nothing. The standing pose is the start, so the answer is the nearest one to the leg's own
    posture rather than to an arbitrary grid point.
    """
    best = _clipped(chain, list(zero))
    best_score = _score(chain, best, point, zero)
    for _ in range(sweeps):
        improved = False
        for index in range(len(chain)):
            low, high = chain[index]["limits"]
            span = [low + (high - low) * step / max(1, samples - 1) for step in range(samples)]
            for value in span:
                trial = list(best)
                trial[index] = value
                score = _score(chain, trial, point, zero)
                if score < best_score:
                    best, best_score, improved = trial, score, True
        if not improved:
            break
    for step in (0.02, 0.005, 0.001):
        for _ in range(30):
            improved = False
            for index in range(len(chain)):
                for delta in (step, -step):
                    trial = _clipped(chain, list(best[:index] + [best[index] + delta] + best[index + 1:]))
                    score = _score(chain, trial, point, zero)
                    if score < best_score:
                        best, best_score, improved = trial, score, True
            if not improved:
                break
    return best


def read_phase(chain, normal, vertices, base_z, angles, point):
    """One phase's readings: the numbers the verdicts are made of, and nothing weighted."""
    state = K.pad_state(chain, angles, normal, vertices, base_z)
    margins = [min(angles[i] - chain[i]["limits"][0], chain[i]["limits"][1] - angles[i])
               for i in range(len(chain))]
    frames = state["frames"]
    femur = [frames[3][i][3] - frames[2][i][3] for i in range(3)]
    return {
        "position_error_m": _distance(state["position"], point),
        "facing_deg": state["tilt_deg"],
        "facing_cos": state["facing_cos"],
        "lowest_z_m": state["lowest_z"],
        "min_limit_margin_rad": min(margins),
        "thigh_dir_actual_deg": math.degrees(math.atan2(femur[2], femur[0])),
        "angles": angles,
    }


def _flags(entry, target, facing_required, step_rad, have_previous) -> list[str]:
    tol = target["tolerances"]
    flags = []
    if entry["position_error_m"] > tol["position_m"]:
        flags.append("POS")
    if facing_required and entry["facing_deg"] > tol["facing_deg"]:
        flags.append("FACE")
    if entry["min_limit_margin_rad"] < tol["limit_margin_rad"]:
        flags.append("LIMIT")
    if have_previous and step_rad > tol["joint_step_rad"]:
        flags.append("STEP")
    return flags


def run_one(label, urdf, target, leg, base_z, args, reference) -> dict:
    chain, normal, vertices, zero, _ = zero_pose(urdf, leg, base_z)
    scale = (args.speed / target["gait"]["speed_m_per_s"]) if args.speed else 1.0
    stance_at = [index for index, phase in enumerate(target["phases"]) if phase["contact"] == "stance"]
    if args.facing_mid_stance:
        half = len(stance_at) // 4
        stance_at = stance_at[half:len(stance_at) - half]
    rows, previous = [], None
    for index, phase in enumerate(target["phases"]):
        stance = phase["contact"] == "stance"
        facing_required = (stance and target["facing"]["required_during_stance"]
                           and (not args.facing_mid_stance or index in stance_at))
        point = [reference[0] + phase["dx_m"] * scale, reference[1], reference[2] + phase["dz_m"]]
        angles = fit(chain, point, zero, args.samples)
        entry = read_phase(chain, normal, vertices, base_z, angles, point)
        step = max((abs(angles[i] - previous[i]) for i in range(len(chain))) if previous is not None else [0.0])
        entry.update(phase)
        entry["dx_sweep_m"] = phase["dx_m"] * scale
        entry["step_rad"] = step
        entry["flags"] = _flags(entry, target, facing_required, step, previous is not None)
        anchor = phase.get("thigh_dir_deg")
        if anchor is not None and abs(entry["thigh_dir_actual_deg"] - anchor) > target["tolerances"]["thigh_dir_deg"]:
            entry["flags"] = entry["flags"] + ["THIGH"]
        rows.append(entry)
        previous = angles
    return {"label": label, "urdf": urdf, "joints": len(chain), "rows": rows}


def _table(result: dict) -> None:
    print(f"  {result['label']}: {result['urdf']}  ({result['joints']} joints)")
    print(f"  {'ph':>3} {'contact':<6} {'dx_mm':>7} {'dz_mm':>6} {'err_mm':>7} {'face_deg':>8} "
          f"{'margin_deg':>10} {'step_deg':>8} {'thigh_deg':>9}  flags")
    for row in result["rows"]:
        print(f"  {int(row['phase']):>3} {row['contact']:<6} {row['dx_sweep_m'] * 1000:>7.1f} "
              f"{row['dz_m'] * 1000:>6.1f} {row['position_error_m'] * 1000:>7.1f} {row['facing_deg']:>8.1f} "
              f"{math.degrees(row['min_limit_margin_rad']):>10.1f} {math.degrees(row['step_rad']):>8.1f} "
              f"{row['thigh_dir_actual_deg']:>9.1f}  {','.join(row['flags']) or '-'}")
    failed = [int(row["phase"]) for row in result["rows"] if row["flags"]]
    thigh = [row["thigh_dir_actual_deg"] for row in result["rows"]]
    print(f"  failed phases: {failed or 'none'} | thigh direction over the cycle {min(thigh):.1f} .. "
          f"{max(thigh):.1f} deg")


def compare(base: dict, other: dict) -> None:
    print("  per-phase comparison (candidate error minus asset error, mm; negative = candidate closer):")
    for first, second in zip(base["rows"], other["rows"]):
        delta = (second["position_error_m"] - first["position_error_m"]) * 1000
        if abs(delta) < 0.5 and first["flags"] == second["flags"]:
            continue
        print(f"    phase {int(first['phase']):>2}: {delta:+7.1f} mm   "
              f"A {first['position_error_m'] * 1000:6.1f} mm [{','.join(first['flags']) or '-'}]"
              f"   B {second['position_error_m'] * 1000:6.1f} mm [{','.join(second['flags']) or '-'}]")
    fixed = [int(b["phase"]) for a, b in zip(base["rows"], other["rows"]) if a["flags"] and not b["flags"]]
    broke = [int(b["phase"]) for a, b in zip(base["rows"], other["rows"]) if b["flags"] and not a["flags"]]
    print(f"    phases the candidate fixes: {fixed or 'none'}; phases it breaks: {broke or 'none'}")


def self_check(target: dict, leg: str, args) -> int:
    """Controls: reach a target drawn from this chain's own FK, fail a far one, stay inside the limits."""
    failures = 0
    base_z = target["body"]["base_z_m"]
    chain, normal, vertices, zero, reference = zero_pose(args.urdf, leg, base_z)
    pose = ([0.3, -0.2, 0.4, -0.5, 0.1] + [0.2])[: len(chain)]
    reachable = K.pad_state(chain, pose, normal, vertices, base_z)["position"]
    found = fit(chain, reachable, zero, args.samples)
    error = _distance(K.foot_pose(chain, found)[0], reachable)
    print(f"  control 1 (target from this chain's own FK): reached to {error * 1000:.3f} mm")
    failures += error > 0.001
    far = [reference[0] + 1.0, reference[1] + 1.0, reference[2] - 1.0]
    found = fit(chain, far, zero, args.samples)
    error = _distance(K.foot_pose(chain, found)[0], far)
    rejected = error > target["tolerances"]["position_m"]
    print(f"  control 2 (target a metre away): best error {error * 1000:.1f} mm -> "
          f"{'reported as unreachable' if rejected else 'WRONGLY ACCEPTED'}")
    failures += not rejected
    inside = all(chain[i]["limits"][0] <= found[i] <= chain[i]["limits"][1] for i in range(len(chain)))
    print(f"  control 3 (search stays inside the limits): {'yes' if inside else 'NO'}")
    failures += not inside
    print(f"  SELF_CHECK_{'OK' if failures == 0 else 'FAILED'}")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", type=pathlib.Path, default=DEFAULT_TARGET)
    parser.add_argument("--urdf", type=pathlib.Path, default=K.DEFAULT_URDF)
    parser.add_argument("--leg", default=None, help="default: the target's own leg")
    parser.add_argument("--candidate-b", type=pathlib.Path, default=None,
                        help="default: the asset plus one revolute along the femur, built as a fixture")
    parser.add_argument("--b-token", default="ferot", help="the inserted joint's name token")
    parser.add_argument("--samples", type=int, default=9, help="values per joint in the one-joint scan")
    parser.add_argument("--speed", type=float, default=None,
                        help="override the target's speed [m/s]; stance offsets scale with it (the sweep "
                             "is linear in speed), which is how a sensitivity run is made")
    parser.add_argument("--asset-only", action="store_true", help="skip the candidate arm")
    parser.add_argument("--facing-mid-stance", action="store_true",
                        help="explore D1's phased-contact option: require a level pad only through the "
                             "middle half of stance, leaving touchdown and liftoff free")
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
    print(f"  body z {base_z} m; facing required in stance: {target['facing']['required_during_stance']}")
    if args.speed:
        print(f"  speed override {args.speed} m/s (target {target['gait']['speed_m_per_s']}): stance offsets "
              f"scaled x{args.speed / target['gait']['speed_m_per_s']:.3f}, so the sweep is "
              f"{target['gait']['stance_sweep_m'] * args.speed / target['gait']['speed_m_per_s']:.4f} m")

    chain_a, _, _, _, reference = zero_pose(args.urdf, leg, base_z)
    femur = math.sqrt(sum(value * value for value in chain_a[2]["origin"]))
    print(f"  A standing pad origin {[round(value, 4) for value in reference]} m; femur length {femur:.4f} m")

    results = [run_one("A (asset)", args.urdf, target, leg, base_z, args, reference)]
    if args.asset_only:
        print()
        _table(results[0])
        return
    with tempfile.TemporaryDirectory(prefix="fit_candidate_") as folder:
        candidate = args.candidate_b or K._inserted_joint_urdf(args.urdf, leg, args.b_token,
                                                              pathlib.Path(folder))
        results.append(run_one(f"B ({args.b_token})", candidate, target, leg, base_z, args, reference))
        print()
        for result in results:
            _table(result)
        print()
        compare(results[0], results[1])


if __name__ == "__main__":
    main()
