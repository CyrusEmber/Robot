# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Offline audit of guided trial time, stopping condition and wrench projection."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from pxr import Usd, UsdPhysics

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from rl_exp.tools.runrecord.binding import sha256_file  # noqa: E402


def run(report_path, usd):
    data = json.loads(report_path.read_text(encoding="utf-8"))
    meta, rows = data["metadata"], data["samples"]
    if sha256_file(usd) != meta["usd_sha256"]:
        raise ValueError("USD hash mismatch")
    names, bodies, settings = meta["joints"], meta["bodies"], meta["settings"]
    stage = Usd.Stage.Open(str(usd))
    joints = {}
    for prim in stage.Traverse():
        if prim.IsA(UsdPhysics.RevoluteJoint):
            joint = UsdPhysics.RevoluteJoint(prim)
            child = joint.GetBody1Rel().GetTargets()
            axis = joint.GetAxisAttr().Get()
            if len(child) != 1 or axis not in ("X", "Y", "Z") or prim.GetName() in joints:
                raise ValueError("ambiguous axis or child")
            joints[prim.GetName()] = (bodies.index(child[0].name), 3 + "XYZ".index(axis))
    if set(joints) != set(names) - {"lift_vertical_joint"}:
        raise ValueError("joint binding mismatch")
    if not rows or any(abs(row["t_s"] - (i + 1) * settings["dt_s"]) > 1e-9 for i, row in enumerate(rows)):
        raise ValueError("invalid time series")
    max_error = 0.
    for row in rows:
        for name, (body, component) in joints.items():
            max_error = max(max_error, abs(row["incoming_wrench"][body][component] - row["joint_projected_effort"][names.index(name)]))
    last = rows[-1]
    forbidden = [(n, float(np.linalg.norm(force))) for n, force in last["ground_forces"].items() if n not in meta["support"]]
    exceeded_contacts = [(n, f) for n, f in forbidden if f > settings["forbidden_contact_n"]]
    exceeded_speeds = [(name, last["velocity"][i], meta["velocity_limits"][i]) for i, name in enumerate(names)
                       if name != "lift_vertical_joint" and abs(last["velocity"][i]) >= meta["velocity_limits"][i] * settings["speed_fraction"]]
    if "forbidden_contact" in data["stop_reason"] and not exceeded_contacts:
        raise ValueError("forbidden contact stop not reproduced")
    if "joint_speed" in data["stop_reason"] and not exceeded_speeds:
        raise ValueError("speed stop not reproduced")
    if max_error > 1e-4:
        raise ValueError("joint wrench projection mismatch")
    return {"report_sha256": sha256_file(report_path), "samples": len(rows),
            "stop_reason": data["stop_reason"], "forbidden_contacts": exceeded_contacts,
            "exceeded_speeds": exceeded_speeds, "max_projection_error_nm": max_error,
            "scope": "time, two stop checks and projection only; no independent contact binding or drive attribution"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--usd", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output exists")
    result = run(args.report, args.usd)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(json.dumps(result))
