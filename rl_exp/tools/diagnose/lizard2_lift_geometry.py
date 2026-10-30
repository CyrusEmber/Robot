# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Sample declared foot-support lift IK targets; no contact or dynamics verdict."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from rl_exp.tools.runrecord.binding import sha256_file  # noqa: E402

from pose_target_solver import geometry, load_model, solve


def run(urdf, heights, support=None, clearance=0.04, tail_pitch=0.):
    model = load_model(urdf)
    initial = {n: 0. for n, j in model["joints"].items() if j["axis"] is not None}
    if not np.isfinite(tail_pitch) or not model["joints"]["tail1_pitch_joint"]["limits"][0] <= tail_pitch <= model["joints"]["tail1_pitch_joint"]["limits"][1]:
        raise ValueError("invalid tail pitch")
    initial["tail1_pitch_joint"] = tail_pitch
    feet = ["lf_wrist", "rf_wrist", "rl_ankle", "rr_ankle"]
    support = feet if support is None else support
    if not support or not set(support) <= set(feet) or len(support) != len(set(support)):
        raise ValueError("invalid support feet")
    if not np.isfinite(clearance) or clearance < 0:
        raise ValueError("invalid clearance")
    free = sorted({n for foot in feet for n in geometry.chain_up(model["joints"], foot)
                   if n in initial and n.startswith(foot[:2] + "_")})
    soles = {}
    for foot in feet:
        pose = geometry.fk(model["joints"], foot, initial)
        vertices = geometry.read_obj(model["links"][foot]["collision"])
        world = vertices @ pose[:3, :3].T + pose[:3, 3]
        bottom = world[world[:, 2] < world[:, 2].min() + 0.001].mean(axis=0)
        soles[foot] = {"local": pose[:3, :3].T @ (bottom - pose[:3, 3]),
                       "point": bottom, "normal": pose[:3, 2]}
    samples = []
    for height in heights:
        targets = [{"link": foot, "point_local": value["local"],
                    "point_target": value["point"] + [0., 0., (0. if foot in support else clearance) - height],
                    "normal_local": [0., 0., 1.], "normal_target": value["normal"]}
                   for foot, value in soles.items()]
        result = solve(model, initial, free, targets, position_tolerance=1e-4,
                       normal_tolerance=1e-3, max_evaluations=300)
        result["root_rise_m"] = height
        samples.append(result)
        if not result["passed"]:
            break
        initial = result["q_rad"]
    return {"urdf": str(urdf.resolve()), "urdf_sha256": sha256_file(urdf),
            "support": support, "nominal_swing_clearance_m": clearance,
            "tail1_pitch_rad": tail_pitch,
            "free_joints": free, "initial_sole_heights_m": {k: float(v["point"][2]) for k, v in soles.items()},
            "samples": samples, "scope": "foot point and normal IK only; no ground, collision, path or dynamics checks"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urdf", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--support", choices=("all", "lf-rr", "rf-rl"), default="all")
    parser.add_argument("--tail_pitch", type=float, default=0.)
    parser.add_argument("--clearance", type=float, default=0.04, help="Nominal non-support foot clearance [m]")
    parser.add_argument("--samples", type=int, default=0,
                        help="Number of equally spaced rise samples from 0 to 0.05 m; 0 uses endpoint set")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output exists")
    supports = {"all": None, "lf-rr": ["lf_wrist", "rr_ankle"], "rf-rl": ["rf_wrist", "rl_ankle"]}
    if args.samples and args.samples < 2:
        parser.error("samples must be zero or at least 2")
    heights = np.linspace(0., 0.05, args.samples).tolist() if args.samples else (
        [0.02, 0.05] if args.support == "all" else [0., 0.02, 0.05])
    data = run(args.urdf, heights, support=supports[args.support], tail_pitch=args.tail_pitch, clearance=args.clearance)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
    print(json.dumps({"out": str(args.out), "passed": [s["passed"] for s in data["samples"]]}))
    raise SystemExit(0 if len(data["samples"]) == len(heights) and all(s["passed"] for s in data["samples"]) else 1)
