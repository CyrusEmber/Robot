# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Render a recorded guided-trial prefix as slow collision-hull projections.

This is a kinematic reconstruction from saved base pose and joint samples, not
an original simulator recording. Each saved sample is held without interpolation;
the coloured force labels are recorded filtered ground-force samples. The view
projects convex silhouettes and does not validate runtime body poses, contact
points, occlusion, dynamics or precise collision geometry.
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from rl_exp.tools.runrecord.binding import sha256_file as digest  # noqa: E402

import imageio.v2 as imageio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Polygon  # noqa: E402
import numpy as np  # noqa: E402
from scipy.spatial import ConvexHull  # noqa: E402
from scipy.spatial.transform import Rotation  # noqa: E402

from pose_target_solver import geometry, load_model  # noqa: E402

FEET = {"lf_wrist": "LF", "rf_wrist": "RF", "rl_ankle": "LH", "rr_ankle": "RH"}


def render(report_path, ik_path, urdf_path, out):
    report = json.loads(report_path.read_text(encoding="utf-8"))
    ik = json.loads(ik_path.read_text(encoding="utf-8"))
    if digest(ik_path) != report["metadata"]["ik_sha256"] or digest(urdf_path) != ik["urdf_sha256"]:
        raise ValueError("asset or IK identity mismatch")
    model = load_model(urdf_path)
    meshes = {n: geometry.read_obj(spec["collision"]) for n, spec in model["links"].items() if spec["collision"]}
    if out.exists():
        raise ValueError("output already exists")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.6), dpi=100)
    fig.patch.set_facecolor("#f4f6f8")
    writer = imageio.get_writer(str(out), fps=20, codec="libx264", macro_block_size=16)
    try:
        for index, sample in enumerate(report["samples"]):
            q = dict(zip(report["metadata"]["joints"], sample["q"]))
            base = np.asarray(sample["base_pose"], dtype=float)
            if not np.isfinite(base).all() or abs(np.linalg.norm(base[3:]) - 1.) > 1e-4:
                raise ValueError("invalid recorded base pose")
            root_rotation = Rotation.from_quat(base[3:]).as_matrix()
            positions = {}
            for name, vertices in meshes.items():
                pose = geometry.fk(model["joints"], name, q)
                positions[name] = (vertices @ pose[:3, :3].T + pose[:3, 3]) @ root_rotation.T + base[:3]
            for ax, axis, title in zip(axes, (0, 1), ("SIDE VIEW (front → right)", "FRONT VIEW")):
                ax.clear()
                ax.set_facecolor("white")
                ax.axhline(0., color="#333", linewidth=1.8)
                for name, world in positions.items():
                    projected = world[:, [axis, 2]]
                    outline = projected[ConvexHull(projected).vertices]
                    force = float(np.linalg.norm(sample["ground_forces"].get(name, [0., 0., 0.])))
                    color = "#e85e47" if name in FEET and force > 5. else "#5993b7" if name in FEET else "#89959e"
                    ax.add_patch(Polygon(outline, closed=True, facecolor=color, edgecolor="#425563", linewidth=.4, alpha=.83))
                ax.set_xlim((-2.5, 1.8) if axis == 0 else (-1.35, 1.35))
                ax.set_ylim(-.08, 1.25)
                ax.set_aspect("equal", adjustable="box")
                ax.set_xlabel("x (m)" if axis == 0 else "y (m)")
                ax.set_ylabel("height (m)")
                ax.set_title(title, fontsize=11, weight="bold")
                ax.grid(alpha=.15)
            foot_text = "    ".join(f"{short}: {sample['ground_forces'].get(name, [0, 0, 0])[2]:.0f} N"
                                    for name, short in FEET.items())
            fig.suptitle(f"RECORDED STATE REPLAY  |  simulation t = {sample['t_s']:.3f} s  |  sample {index + 1}/{len(report['samples'])}\n"
                         f"{foot_text}    Red: ground force > 5 N", fontsize=11, weight="bold", y=.98)
            fig.text(.5, .02, "Collision-hull projection · 80× slow · state replay, not original camera footage",
                     ha="center", fontsize=9, color="#4c5660")
            fig.tight_layout(rect=(0, .05, 1, .88))
            fig.canvas.draw()
            frame = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
            for _ in range(8 + (20 if index == 0 or index == len(report["samples"]) - 1 else 0)):
                writer.append_data(frame)
    finally:
        writer.close()
        plt.close(fig)
    return {"report_sha256": digest(report_path), "ik_sha256": digest(ik_path), "urdf_sha256": digest(urdf_path),
            "samples": len(report["samples"]), "fps": 20, "frames_per_sample": 8,
            "slowdown": 80, "output": str(out.resolve()), "scope": "recorded state reconstruction; not live video"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--ik", type=Path, required=True)
    parser.add_argument("--urdf", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = render(args.report, args.ik, args.urdf, args.out)
    manifest = args.out.with_suffix(".json")
    with manifest.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print("LIFT_STATE_REPLAY", json.dumps(result))
