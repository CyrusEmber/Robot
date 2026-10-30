# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Foot-plate-only rise geometry: root height needed for the sole to touch ground vs plate angle.

Every joint is held at a bound IK sample; one support foot joint sweeps its URDF limits. The
rise at an angle is the change in root height that keeps that foot's lowest collision vertex
on the ground (level root, as under the vertical guide). Single-foot, kinematic only: no
second-foot constraint, no ground contact, no torque or dynamics verdict.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from rl_exp.tools.runrecord.binding import sha256_file  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pose_target_solver import geometry, load_model  # noqa: E402

PLATE_JOINT = {"lf_wrist": "lf_wrist_joint", "rf_wrist": "rf_wrist_joint",
               "rl_ankle": "rl_ankle_joint", "rr_ankle": "rr_ankle_joint"}


def run(ik, steps=41, foot_load_n=353.16):
    urdf = Path(ik["urdf"])
    if sha256_file(urdf) != ik["urdf_sha256"]:
        raise ValueError("IK URDF identity changed")
    if steps < 3 or steps % 2 == 0:
        raise ValueError("steps must be odd and at least 3 so the held angle is sampled")
    model = load_model(urdf)
    q0 = dict(ik["samples"][0]["q_rad"])
    result = {}
    for foot in ik["support"]:
        joint = PLATE_JOINT[foot]
        low, high = model["joints"][joint]["limits"]
        vertices = geometry.read_obj(model["links"][foot]["collision"])
        rows = []
        for angle in np.linspace(low, high, steps):
            q = dict(q0, **{joint: float(angle)})
            pose = geometry.fk(model["joints"], foot, q)
            world = vertices @ pose[:3, :3].T + pose[:3, 3]
            lowest_vertex = world[int(np.argmin(world[:, 2]))]
            axis = pose[:3, :3] @ (model["joints"][joint]["axis"] / np.linalg.norm(model["joints"][joint]["axis"]))
            torque = float(np.dot(np.cross(lowest_vertex - pose[:3, 3], [0., 0., foot_load_n]), axis))
            rows.append({"angle_rad": float(angle), "root_height_for_sole_contact_m": -float(lowest_vertex[2]),
                         "static_joint_torque_nm": torque})
        held = min(rows, key=lambda r: abs(r["angle_rad"] - q0[joint]))
        base = held["root_height_for_sole_contact_m"]
        for r in rows:
            r["rise_vs_held_m"] = r["root_height_for_sole_contact_m"] - base
        rises = [r["rise_vs_held_m"] for r in rows]
        result[foot] = {"joint": joint, "limits_rad": [low, high], "held_angle_rad": q0[joint],
                        "max_rise_m": max(rises), "min_rise_m": min(rises),
                        "argmax_angle_rad": rows[int(np.argmax(rises))]["angle_rad"], "rows": rows}
    return {"urdf_sha256": ik["urdf_sha256"], "support": ik["support"], "foot_load_n": foot_load_n, "feet": result,
            "scope": "single-foot kinematic rise and vertical-load joint torque at the lowest vertex; no horizontal "
                     "contact consistency, friction, second-foot or dynamics claim"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ik", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=41)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output exists")
    data = run(json.loads(args.ik.read_text(encoding="utf-8")), args.steps)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
    print("FOOT_PLATE_SWEEP", json.dumps({f: {k: round(v[k], 4) for k in ("max_rise_m", "min_rise_m", "argmax_angle_rad")}
                                           for f, v in data["feet"].items()}))
