# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Check configured leg-foot collision pairs at finite wrist/ankle angles."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from rl_exp.tools.runrecord.binding import sha256_file  # noqa: E402

import body_precheck
import palm_motion_boundaries as triangles
from pose_target_solver import geometry, load_model

PAIRS = (("lf_elbow", "lf_wrist"), ("rf_elbow", "rf_wrist"),
         ("rl_knee", "rl_ankle"), ("rr_knee", "rr_ankle"))


def run(path, amplitude):
    model = load_model(path)
    meshes = {name: body_precheck.mesh_prepare(model["links"][name]["collision"], np, geometry, triangles, {})
              for pair in PAIRS for name in pair}
    results = []
    for lower, foot in PAIRS:
        for axis, angle in [(None, 0.), ("original", -amplitude), ("original", amplitude),
                            ("lateral", -amplitude), ("lateral", amplitude)]:
            joint = None if axis is None else foot + ("_lateral_joint" if axis == "lateral" else "_joint")
            q = {} if joint is None else {joint: angle}
            if joint is not None and not model["joints"][joint]["limits"][0] <= angle <= model["joints"][joint]["limits"][1]:
                raise ValueError(f"outside joint bounds: {joint}")
            world = {}
            for link in (lower, foot):
                vertices = meshes[link][0]
                pose = geometry.fk(model["joints"], link, q)
                world[link] = vertices @ pose[:3, :3].T + pose[:3, 3]
            result = body_precheck.pair_evaluate(lower, foot, world, meshes, 0., np, triangles)
            results.append({"joint": joint, "angle_rad": angle, **result})
    return {"urdf": str(path.resolve()), "sha256": sha256_file(path),
            "amplitude_rad": amplitude, "results": results,
            "scope": "isolated single-axis samples; no combined-axis or continuous-range claim"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urdf", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--amplitude", type=float, default=0.2)
    args = parser.parse_args()
    if args.out.exists() or not np.isfinite(args.amplitude) or args.amplitude <= 0:
        parser.error("output must be fresh and amplitude must be positive")
    data = run(args.urdf, args.amplitude)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
    failures = [r for r in data["results"] if r["state"] != "pass"]
    print("samples", len(data["results"]), "failures", len(failures), flush=True)
    raise SystemExit(1 if failures else 0)
