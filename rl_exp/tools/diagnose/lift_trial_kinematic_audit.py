# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Reconstruct sampled foot-mesh minima from recorded joints and base poses.

Uses the shared URDF FK. Counterfactual held-target poses are geometric slices,
not simulations or independent measurements of causation.
"""

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from rl_exp.tools.runrecord.binding import sha256_file as digest  # noqa: E402

from pose_target_solver import geometry, load_model


def run(report_path, ik_path, urdf_path):
    data = json.loads(report_path.read_text(encoding="utf-8"))
    ik = json.loads(ik_path.read_text(encoding="utf-8"))
    if digest(ik_path) != data["metadata"]["ik_sha256"] or digest(urdf_path) != ik["urdf_sha256"]:
        raise ValueError("input hash mismatch")
    model = load_model(urdf_path)
    feet = ("lf_wrist", "rf_wrist", "rl_ankle", "rr_ankle")
    vertices = {name: geometry.read_obj(model["links"][name]["collision"]) for name in feet}
    names, controlled = data["metadata"]["joints"], data["controlled"]
    def minima(q, base):
        rotation = Rotation.from_quat(base[3:]).as_matrix()
        result = {}
        for foot in feet:
            pose = geometry.fk(model["joints"], foot, q)
            mesh_root = vertices[foot] @ pose[:3, :3].T + pose[:3, 3]
            result[foot] = float((mesh_root @ rotation.T + base[:3])[:, 2].min())
        return result
    rows = []
    for row in data["samples"]:
        base = np.array(row["base_pose"], dtype=float)
        if not np.isfinite(base).all() or abs(np.linalg.norm(base[3:]) - 1.) > 1e-4:
            raise ValueError("invalid base quaternion")
        actual = dict(zip(names, row["q"]))
        target = dict(zip(controlled, row["target"]))
        errors = {n: actual[n] - target[n] for n in controlled}
        rows.append({"t_s": row["t_s"], "base_z_m": float(base[2]),
                     "actual_mesh_min_m": minima(actual, base),
                     "held_target_mesh_min_m": minima(target, base),
                     "joint_error_rad": errors, "ground_forces_n": row["ground_forces"]})
    return {"report_sha256": digest(report_path), "ik_sha256": digest(ik_path), "urdf_sha256": digest(urdf_path),
            "scope": "URDF/FK reconstruction and held-target slice; no independent actor pose or causal intervention",
            "rows": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--ik", type=Path, required=True)
    parser.add_argument("--urdf", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output exists")
    result = run(args.report, args.ik, args.urdf)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print("LIFT_KINEMATIC_AUDIT", len(result["rows"]), str(args.out))
