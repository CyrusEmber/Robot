# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Fixed-body two-leg step sample for the restored lizard2 palm candidate [m, rad, s].

Question: with the body held still, can a front leg and a diagonal rear leg run a closed
stance -> lift -> swing -> touch-down cycle with the palm sole kept level, inside the URDF joint
limits and without penetrating other links? Body-frame kinematics only: no support force, no
world-frame foot slip, no propulsion.

Method: one analytic constraint set per leg (4 DOF = 3 sole-point position conditions + 1 level
condition), solved by bounded least squares with continuation from the previous frame. Every frame's
residuals are kept. ``oracle`` re-evaluates the exported angles with an unperturbed ``Leg`` built from
the same URDF, so it catches a perturbed axis/sign inside the solver (``--inject_error axis_sign``) but
is NOT an independent FK: a shared mistake in ``Leg.pose`` is invisible to it. Collision uses
mesh-surface gaps (``check_self_collision.mesh_gap``);
the six approved connection pairs and directly jointed pairs are excluded as in the live probe.

Limits of this sample: sampled, not a continuous-domain proof; the trajectory is engineering geometry,
not measured animal gait; level palm is a choice of this sample, not a claim about every gait.
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import ConvexHull

_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[3]
sys.path.insert(0, str(_REPO / "rl_exp/tools/verify"))
sys.path.insert(0, str(_REPO / "rl_exp/tools/runrecord"))
sys.path.insert(0, str(_REPO))
import binding  # noqa: E402
import check_self_collision as csc  # noqa: E402

# Same six connection pairs as palm_pd_probe.py ``approved``; copy kept in sync by hand.
APPROVED = {frozenset(p) for p in (
    ("tail2_pitch", "tail1_pitch"), ("tail1_pitch", "base_link"),
    ("base_link", "rr_hip_abduct"), ("base_link", "rl_hip_abduct"),
    ("rf_shoulder_abduct", "chest_pitch"), ("lf_shoulder_abduct", "chest_pitch"))}
ROLES = {"lf": ("shoulder_swing", "shoulder_abduct", "elbow", "wrist"),
         "rf": ("shoulder_swing", "shoulder_abduct", "elbow", "wrist"),
         "rl": ("hip_swing", "hip_abduct", "knee", "ankle"),
         "rr": ("hip_swing", "hip_abduct", "knee", "ankle")}
SAMPLE_LEGS = ("lf", "rr")
PHASE = {"lf": 0., "rr": 0., "rf": .5, "rl": .5}  # diagonal pairs in phase, the other diagonal half a cycle later


def mirror_signs(left, right, flip=False):
    """Per joint s with q_right = s * q_left for a body-mirrored motion, from the URDF axes alone.

    Reflection through the sagittal plane maps a rotation axis (a pseudovector) a -> (-ax, ay, -az);
    s = +1 if the right joint axis equals that, -1 if opposite, nan if neither (not mirror-related).
    """
    signs = []
    for a, b in zip(left.axes, right.axes):
        a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
        m = np.array([-1., 1., -1.]) * a
        signs.append(1. if np.allclose(b, m, atol=1e-6) else -1. if np.allclose(b, -m, atol=1e-6) else np.nan)
    signs = np.array(signs)
    if flip:
        signs[0] *= -1
    return signs


def rotation(axis, angle):
    axis = axis / np.linalg.norm(axis)
    k = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + np.sin(angle) * k + (1 - np.cos(angle)) * k @ k


class Leg:
    """Solver-side model of one leg, built from the URDF; ``flip`` perturbs one axis for the negative test."""

    def __init__(self, urdf, leg, flip=None):
        self.leg = leg
        self.unsolved = False
        self.names = [f"{leg}_{r}_joint" for r in ROLES[leg]]
        self.link = f"{leg}_{ROLES[leg][-1]}"
        actual = [name for name in csc.chain_up(urdf["joints"], self.link)
                  if urdf["joints"][name]["child"].startswith(leg + "_")]
        if actual != self.names:
            raise ValueError(f"{leg}: historical four-axis palm solver cannot consume {actual}; "
                             f"expected {self.names}. Use a verified palm_spatial solver.")
        self.spec = [urdf["joints"][n] for n in self.names]
        self.axes = [s["axis"] * (-1. if i == flip else 1.) for i, s in enumerate(self.spec)]
        self.lo = np.array([s["limits"][0] for s in self.spec])
        self.hi = np.array([s["limits"][1] for s in self.spec])
        self.root = csc.fk(urdf["joints"], urdf["joints"][self.names[0]]["parent"], {})
        self.verts = csc.read_obj(urdf["links"][self.link]["collision"])
        zero = self.pose(np.zeros(4))
        world = (zero[:3, :3] @ self.verts.T).T + zero[:3, 3]
        low = world[:, 2] < world[:, 2].min() + 1e-3
        self.sole_local = zero[:3, :3].T @ (world[low].mean(0) - zero[:3, 3])
        self.neutral_sole = zero[:3, :3] @ self.sole_local + zero[:3, 3]

    def pose(self, q):
        transform = self.root.copy()
        for spec, axis, angle in zip(self.spec, self.axes, q):
            move = np.eye(4)
            move[:3, 3] = spec["origin"]
            spin = np.eye(4)
            spin[:3, :3] = rotation(axis, angle)
            transform = transform @ move @ spin
        return transform

    def sole(self, q):
        t = self.pose(q)
        return t[:3, :3] @ self.sole_local + t[:3, 3], t[:3, 2]

    def solve(self, target, guess):
        def residual(q):
            point, up = self.sole(q)
            return np.r_[point - target, up[:2]]

        def once(start):
            out = least_squares(residual, np.clip(start, self.lo + 1e-6, self.hi - 1e-6),
                                bounds=(self.lo, self.hi), xtol=1e-14, ftol=1e-14, gtol=1e-14)
            return out.x, out.fun

        q, fun = once(guess)
        if np.linalg.norm(fun) < 1e-6:
            self.unsolved = False
            return q, fun
        # Continuation stuck in a local minimum: pick the converged solution nearest the previous frame.
        # A branch jump then shows up as a large frame step instead of being hidden.
        # Once a frame is already unsolvable, later frames get a cheap retry so a rejected run ends fast.
        rng = np.random.default_rng(0)
        best = (q, fun)
        converged = []
        for _ in range(3 if self.unsolved else 40):
            cand, cfun = once(rng.uniform(self.lo, self.hi))
            if np.linalg.norm(cfun) < 1e-6:
                converged.append(cand)
            if np.linalg.norm(cfun) < np.linalg.norm(best[1]):
                best = (cand, cfun)
        if converged:
            pick = min(converged, key=lambda c: np.linalg.norm(c - guess))
            self.unsolved = False
            return pick, residual(pick)
        self.unsolved = True
        return best


def trajectory(neutral, phase, step, lift, stance_fraction):
    x0, y0, z0 = neutral
    if phase < stance_fraction:
        return np.array([x0 + step / 2 - step * phase / stance_fraction, y0, z0])
    s = (phase - stance_fraction) / (1 - stance_fraction)
    return np.array([x0 - step / 2 + step * (0.5 - 0.5 * np.cos(np.pi * s)), y0,
                     z0 + lift * np.sin(np.pi * s) ** 2])


def run(args):
    urdf_path = args.urdf.resolve()
    urdf = csc.load_urdf(urdf_path)
    velocity_limits = {j.get("name"): float(j.find("limit").get("velocity"))
                       for j in ET.parse(urdf_path).getroot().iter("joint") if j.find("limit") is not None}
    flip_leg, flip_joint = ("rr", 1) if args.inject_error == "axis_sign" else (None, None)
    step = 0.9 if args.inject_error == "step_too_long" else args.step
    legs = {l: Leg(urdf, l, flip_joint if l == flip_leg else None) for l in SAMPLE_LEGS}
    # Independent oracle for the sole point and tilt: unmodified URDF through check_self_collision.fk.
    oracle = {l: Leg(urdf, l) for l in SAMPLE_LEGS}
    n = args.frames
    phases = np.arange(n) / n
    q = {l: np.zeros((n + 1, 4)) for l in SAMPLE_LEGS}
    pos_res = {l: np.zeros(n + 1) for l in SAMPLE_LEGS}
    tilt_res = {l: np.zeros(n + 1) for l in SAMPLE_LEGS}
    oracle_res = {l: np.zeros(n + 1) for l in SAMPLE_LEGS}
    for l, leg in legs.items():
        guess = np.zeros(4)
        for k in range(n + 1):
            target = trajectory(oracle[l].neutral_sole, ((k % n) / n + PHASE[l]) % 1., step, args.lift, args.stance_fraction)
            q[l][k], fun = leg.solve(target, guess)
            guess = q[l][k]
            pos_res[l][k] = np.linalg.norm(fun[:3])
            point, up = oracle[l].sole(q[l][k])
            oracle_res[l][k] = np.linalg.norm(point - target)
            tilt_res[l][k] = np.degrees(np.arccos(np.clip(up[2], -1, 1)))
    dt = args.period / n
    report = {"phases": n, "step_m": step, "lift_m": args.lift, "period_s": args.period,
              "stance_fraction": args.stance_fraction, "legs": {}}
    failures = []
    for l in SAMPLE_LEGS:
        leg = legs[l]
        joint_q = q[l]
        seam = float(np.abs(joint_q[n] - joint_q[0]).max())
        velocity = np.diff(joint_q[:n + 1], axis=0) / dt
        velocity_limit = np.array([velocity_limits[nm] for nm in leg.names])
        margin = np.minimum(joint_q - leg.lo, leg.hi - joint_q).min(0)
        max_jump = float(np.abs(np.diff(joint_q, axis=0)).max())
        stats = {"max_pos_residual_m": float(pos_res[l].max()), "max_oracle_residual_m": float(oracle_res[l].max()),
                 "max_tilt_deg": float(tilt_res[l].max()), "seam_rad": seam, "max_frame_step_rad": max_jump,
                 "min_limit_margin_rad": margin.tolist(), "max_abs_velocity_rad_s": np.abs(velocity).max(0).tolist(),
                 "velocity_limit_rad_s": velocity_limit.tolist(),
                 "q_min": joint_q.min(0).tolist(), "q_max": joint_q.max(0).tolist(), "joints": leg.names}
        report["legs"][l] = stats
        if np.any(np.abs(velocity).max(0) > args.velocity_fraction * velocity_limit):
            failures.append(f"{l}: velocity above {args.velocity_fraction:.0%} of limit")
        if stats["max_pos_residual_m"] > args.pos_tol or stats["max_oracle_residual_m"] > args.pos_tol:
            failures.append(f"{l}: sole position residual {max(stats['max_pos_residual_m'], stats['max_oracle_residual_m']):.4g} m")
        if stats["max_tilt_deg"] > args.tilt_tol_deg:
            failures.append(f"{l}: palm tilt {stats['max_tilt_deg']:.3g} deg")
        if seam > 1e-6:
            failures.append(f"{l}: seam {seam:.3g} rad")
        if margin.min() < args.limit_margin:
            failures.append(f"{l}: limit margin {margin.min():.3g} rad")
        if max_jump > args.max_step_rad:
            failures.append(f"{l}: frame step {max_jump:.3g} rad")
    # Body-mirror check for left/right pairs: axes, limits and the solved motion must agree through the
    # reflection derived from the URDF axes (a wrong sign in either leg's URDF breaks one of the three).
    report["mirror"] = {}
    for left, right in (("lf", "rf"), ("rl", "rr")):
        if left not in legs or right not in legs:
            continue
        s = mirror_signs(oracle[left], oracle[right], flip=args.inject_error == "mirror_sign")
        row = {"signs": s.tolist()}
        if np.isnan(s).any():
            failures.append(f"mirror {left}/{right}: axes are not mirror images")
        else:
            lo_expected = np.where(s > 0, oracle[left].lo, -oracle[left].hi)
            hi_expected = np.where(s > 0, oracle[left].hi, -oracle[left].lo)
            row["limit_mismatch_rad"] = float(max(np.abs(oracle[right].lo - lo_expected).max(),
                                                 np.abs(oracle[right].hi - hi_expected).max()))
            shift = int(round((PHASE[right] - PHASE[left]) * n)) % n
            expect = q[left][(np.arange(n) + shift) % n] * s
            row["motion_mismatch_rad"] = float(np.abs(q[right][:n] - expect).max())
            if row["limit_mismatch_rad"] > 1e-6:
                failures.append(f"mirror {left}/{right}: limits differ by {row['limit_mismatch_rad']:.3g} rad")
            if row["motion_mismatch_rad"] > 1e-4:
                failures.append(f"mirror {left}/{right}: motion differs by {row['motion_mismatch_rad']:.3g} rad")
        report["mirror"][f"{left}/{right}"] = row
    # Collision against surfaces, coarse then refined around flagged frames.
    links = {name: spec for name, spec in urdf["links"].items() if spec["collision"] is not None}
    local = {name: csc.read_obj_faces(spec["collision"]) for name, spec in links.items()}
    moving = {f"{l}_{r}" for l in SAMPLE_LEGS for r in ROLES[l]} & set(links)
    pairs = [(a, b) for a in sorted(moving) for b in sorted(links) if a != b and (b not in moving or a < b)
             and frozenset((a, b)) not in APPROVED and csc.chain_distance(urdf["joints"], a, b) > 1]

    def gap_at(angles):
        reach = max(0.05, 2 * args.clearance)
        placed = {name: csc.fk(urdf["joints"], name, angles) for name in links}
        world = {name: (placed[name][:3, :3] @ local[name][0].T).T + placed[name][:3, 3] for name in links}
        rows = []
        for a, b in pairs:
            wa, wb = world[a], world[b]
            if np.any(np.maximum(wa.min(0), wb.min(0)) - np.minimum(wa.max(0), wb.max(0)) > reach):
                continue
            near_a = wa[np.all((wa >= wb.min(0) - reach) & (wa <= wb.max(0) + reach), axis=1)]
            near_b = wb[np.all((wb >= wa.min(0) - reach) & (wb <= wa.max(0) + reach), axis=1)]
            gaps = ([csc.mesh_gap(near_a, wb, local[b][1])] if len(near_a) else []) + \
                   ([csc.mesh_gap(near_b, wa, local[a][1])] if len(near_b) else [])
            if gaps:
                # mesh_gap's sign is containment evidence only near contact (see its docstring); far
                # away a negative number is a plane-side artefact, so treat it as plain distance.
                rows.append((min(abs(g) if abs(g) > 0.03 else g for g in gaps), a, b))
        return rows

    def frame_angles(k):
        angles = {nm: float(v) for l in SAMPLE_LEGS for nm, v in zip(legs[l].names, q[l][k])}
        if args.inject_error == "collide_control":
            angles["chest_yaw_joint"] = 0.6  # live probe: this pose makes lf_wrist and rl_ankle touch
        return angles

    neutral_gaps = {(a, b): gap for gap, a, b in gap_at({})}
    stride = max(1, n // 100)
    evaluated = {k: gap_at(frame_angles(k)) for k in range(0, n, stride)}
    flagged = {k for k, rows in evaluated.items() if rows and min(r[0] for r in rows) < args.clearance * 2}
    for k in sorted(flagged):
        for j in range(max(0, k - stride + 1), min(n, k + stride)):
            if j not in evaluated:
                evaluated[j] = gap_at(frame_angles(j))
    worst = {}
    for k, rows in evaluated.items():
        for gap, a, b in rows:
            if gap < worst.get((a, b), (np.inf, 0))[0]:
                worst[(a, b)] = (gap, k)
    collisions = []
    for (a, b), (gap, k) in sorted(worst.items(), key=lambda kv: kv[1][0]):
        neutral = neutral_gaps.get((a, b))
        allowed = args.clearance if neutral is None else min(args.clearance, neutral - 0.0005)
        status = "fail" if gap < allowed else "ok"
        collisions.append({"pair": [a, b], "min_gap_mm": gap * 1000, "frame": k, "neutral_gap_mm": None if neutral is None else neutral * 1000,
                           "required_mm": allowed * 1000, "status": status})
        if status == "fail":
            failures.append(f"collision {a}~{b}: {gap * 1000:.2f} mm at frame {k}")
    report["collision_pairs_checked"] = len(pairs)
    report["collision_frames_evaluated"] = len(evaluated)
    report["collisions_closest"] = collisions[:12]
    report["failures"] = failures
    report["status"] = "FAIL" if failures else "PASS_SAMPLED_NOT_CONTINUOUS_NOT_LOADED"
    return report, q, legs, urdf, links, local


def write_outputs(out, report, q, legs, urdf, links, local, args):
    import csv

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PIL import Image

    n = args.frames
    with (out / "trajectory.csv").open("x", newline="") as handle:
        writer = csv.writer(handle)
        names = [nm for l in SAMPLE_LEGS for nm in legs[l].names]
        writer.writerow(["phase", "t_s"] + names)
        for k in range(n + 1):
            writer.writerow([k / n, k / n * args.period] + [f"{v:.9f}" for l in SAMPLE_LEGS for v in q[l][k]])
    frames = {"side": [], "top": []}
    all_names = sorted(links)
    for k in range(0, n, max(1, n // 50)):
        angles = {nm: float(v) for l in SAMPLE_LEGS for nm, v in zip(legs[l].names, q[l][k])}
        placed = {name: csc.fk(urdf["joints"], name, angles) for name in all_names}
        for view, (i, j) in (("side", (0, 2)), ("top", (0, 1))):
            fig, ax = plt.subplots(figsize=(7, 4 if view == "side" else 5))
            for name in all_names:
                pts = (placed[name][:3, :3] @ local[name][0].T).T + placed[name][:3, 3]
                flat = pts[:, [i, j]]
                try:
                    hull = ConvexHull(flat)
                    poly = flat[hull.vertices]
                    moving = name.split("_")[0] in SAMPLE_LEGS
                    ax.fill(poly[:, 0], poly[:, 1], alpha=.5, color="tab:red" if moving else "tab:blue")
                except Exception:
                    pass
            ax.axhline(legs["lf"].neutral_sole[2], color="k", lw=.5) if view == "side" else None
            ax.set_aspect("equal")
            ax.set_title(f"{view} phase {k / n:.2f}")
            fig.canvas.draw()
            frames[view].append(Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[..., :3]))
            plt.close(fig)
    for view, images in frames.items():
        images[0].save(out / f"{view}.gif", save_all=True, append_images=images[1:], duration=40, loop=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urdf", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--step", type=float, default=0.20)
    parser.add_argument("--lift", type=float, default=0.05)
    parser.add_argument("--period", type=float, default=1.0)
    parser.add_argument("--stance_fraction", type=float, default=0.6)
    parser.add_argument("--frames", type=int, default=400)
    parser.add_argument("--pos_tol", type=float, default=1e-4)
    parser.add_argument("--tilt_tol_deg", type=float, default=2.0)
    parser.add_argument("--limit_margin", type=float, default=0.02)
    parser.add_argument("--max_step_rad", type=float, default=0.05)
    parser.add_argument("--clearance", type=float, default=0.005)
    parser.add_argument("--velocity_fraction", type=float, default=0.5)
    parser.add_argument("--legs", choices=("two", "four"), default="two",
                        help="two: lf+rr sample; four: trot with rf+rl half a cycle later")
    parser.add_argument("--inject_error", choices=("axis_sign", "step_too_long", "collide_control", "mirror_sign"))
    args = parser.parse_args()
    global SAMPLE_LEGS
    if args.legs == "four":
        SAMPLE_LEGS = ("lf", "rf", "rl", "rr")
    out = args.output_dir.resolve()
    assert _REPO / "rl_exp/out" in out.parents, "output must stay under rl_exp/out"
    if out.exists():
        raise ValueError("output directory already exists")
    report, q, legs, urdf, links, local = run(args)
    out.mkdir(parents=True, exist_ok=False)
    report["identity"] = {"urdf": str(args.urdf), "urdf_sha256": binding.sha256_file(args.urdf),
                          "script_sha256": binding.sha256_file(_HERE), "revision": binding.git_rev(_REPO),
                          "inject_error": args.inject_error, "args": {k: str(v) for k, v in vars(args).items()}}
    with (out / "report.json").open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1)
    if not args.inject_error:
        write_outputs(out, report, q, legs, urdf, links, local, args)
    print("PALM_GAIT_KINEMATICS", report["status"], out, flush=True)
    for line in report["failures"]:
        print("FAIL", line, flush=True)
    raise SystemExit(1 if report["failures"] else 0)


if __name__ == "__main__":
    main()
