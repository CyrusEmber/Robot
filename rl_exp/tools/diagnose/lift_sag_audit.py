# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Summarize a recorded guided lift prefix without running physics.

Ground force is the sum of stored ground-filtered normal-force vectors. The
guide axial component is reported in its recorded joint frame. Whole-body
acceleration inferred from vertical balance assumes level ground, matching
frames and no unrecorded external vertical forces; it is not a COM measurement.
"""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from rl_exp.tools.runrecord.binding import sha256_file  # noqa: E402

FOCUS = ("lf_elbow_joint", "rr_knee_joint", "lf_shoulder_abduct_joint", "rr_hip_abduct_joint",
         "lf_wrist_joint", "rr_ankle_joint")


def run(report_path, calibration_path):
    report = json.loads(report_path.read_text(encoding="utf-8"))
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    meta, samples = report["metadata"], report["samples"]
    if not samples or calibration["asset_sha256"] != meta["usd_sha256"] or calibration["terminated"]:
        raise ValueError("empty report or calibration asset mismatch")
    mass = float(calibration["mass_kg"])
    gravity = float(calibration["gravity"][2])
    if not np.isfinite(mass) or mass <= 0 or not np.isfinite(gravity) or gravity >= 0:
        raise ValueError("invalid mass or gravity")
    names, bodies, controlled = meta["joints"], meta["bodies"], report["controlled"]
    if not set(FOCUS) <= set(controlled) or len(set(names)) != len(names):
        raise ValueError("missing or duplicate joint binding")
    weight = -mass * gravity
    rows = []
    for i, sample in enumerate(samples):
        if abs(sample["t_s"] - (i + 1) * meta["settings"]["dt_s"]) > 1e-9:
            raise ValueError("unexpected time grid")
        if len(sample["target"]) != len(controlled) or len(sample["q"]) != len(names):
            raise ValueError("joint sample width mismatch")
        quat = np.asarray(sample["base_pose"][3:], dtype=float)
        if quat.shape != (4,) or not np.isfinite(quat).all() or abs(np.linalg.norm(quat) - 1) > 1e-4:
            raise ValueError("invalid base orientation")
        if 2 * (quat[0] ** 2 + quat[1] ** 2) > 1e-5:
            raise ValueError("guide joint axis is not aligned to world vertical")
        target = dict(zip(controlled, sample["target"]))
        current = dict(zip(names, sample["q"]))
        backend = sample.get("backend_position_target")
        backend_velocity = sample.get("backend_velocity_target")
        if backend is None or backend_velocity is None:
            raise ValueError("backend drive target readback required")
        target_error = max(abs(backend[names.index(n)] - target[n]) for n in controlled)
        speed_target = max(abs(backend_velocity[names.index(n)]) for n in controlled)
        if target_error > 1e-5 or speed_target > 1e-5:
            raise ValueError("backend drive targets differ")
        force_z = sum(force[2] for force in sample["ground_forces"].values())
        guide_z = sample["incoming_wrench"][bodies.index("base_link")][2]
        rows.append({"t_s": sample["t_s"], "base_z_m": sample["base_pose"][2],
                     "ground_total_z_n": force_z, "guide_axis_force_n": guide_z,
                     "support_z_n": sum(sample["ground_forces"][n][2] for n in meta["support"]),
                     "balance_acceleration_estimate_m_s2": (force_z + guide_z - weight) / mass,
                     "joint_error_rad": {n: current[n] - target[n] for n in FOCUS},
                     "projected_joint_effort_nm": {n: sample["joint_projected_effort"][names.index(n)] for n in FOCUS},
                     "backend_target_max_error_rad": target_error})
    return {"report_sha256": sha256_file(report_path),
            "calibration_sha256": sha256_file(calibration_path),
            "mass_kg": mass, "gravity_z_m_s2": gravity, "weight_n": weight, "rows": rows,
            "scope": "recorded load, angle and force-balance estimate; no causal or motor-rating claim"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output exists")
    result = run(args.report, args.calibration)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print("LIFT_SAG_AUDIT", len(result["rows"]), str(args.out))
