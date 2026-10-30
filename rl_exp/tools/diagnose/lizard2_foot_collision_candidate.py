# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Build an isolated foot collision candidate by clipping convex hulls below their pivots.

This alters collision geometry, not visual meshes, joint frames or masses. The
result is an exploratory candidate: static samples cannot establish full-range
clearance, contact equivalence, or hardware geometry.
"""

import argparse
import json
from pathlib import Path
import shutil
import sys

import numpy as np
from scipy.spatial import ConvexHull

from pose_target_solver import geometry, load_model

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from rl_exp.tools.runrecord.binding import sha256_file as digest  # noqa: E402

FEET = ("lf_wrist", "rf_wrist", "rl_ankle", "rr_ankle")


def clipped_hull(vertices, ceiling):
    """Clip the input convex hull to local z <= ceiling [m]."""
    vertices = np.unique(vertices, axis=0)
    if not np.isfinite(ceiling) or not vertices[:, 2].min() < ceiling < vertices[:, 2].max():
        raise ValueError("ceiling must cut the original hull")
    hull = ConvexHull(vertices)
    edges = {tuple(sorted((int(face[i]), int(face[(i + 1) % 3]))))
             for face in hull.simplices for i in range(3)}
    points = list(vertices[vertices[:, 2] <= ceiling])
    for i, j in edges:
        a, b = vertices[i], vertices[j]
        if (a[2] < ceiling < b[2]) or (b[2] < ceiling < a[2]):
            points.append(a + (b - a) * ((ceiling - a[2]) / (b[2] - a[2])))
    points = np.unique(np.round(np.asarray(points), 12), axis=0)
    output_hull = ConvexHull(points)
    faces = []
    for face, equation in zip(output_hull.simplices, output_hull.equations):
        a, b, c = points[face]
        if np.dot(np.cross(b - a, c - a), equation[:3]) < 0:
            face = face[[0, 2, 1]]
        faces.append(face)
    used = sorted({int(i) for f in faces for i in f})
    mapping = {old: new + 1 for new, old in enumerate(used)}
    return points[used], [[mapping[int(i)] for i in face] for face in faces]


def create(source, out, ceiling):
    source, out = source.resolve(), out.resolve()
    if not out.is_relative_to((ROOT / "rl_exp/out").resolve()) or out.exists():
        raise ValueError("output must be a fresh directory under rl_exp/out")
    model = load_model(source)
    inputs = {foot: model["links"][foot]["collision"] for foot in FEET}
    for path in inputs.values():
        if not path.is_relative_to(source.parent.resolve()):
            raise ValueError("collision mesh must be under source asset directory")
    source_hashes = {foot: digest(path) for foot, path in inputs.items()}
    source_urdf_hash = digest(source)
    out.mkdir(parents=True)
    shutil.copytree(source.parent / "meshes", out / "meshes")
    shutil.copy2(source, out / source.name)
    rows = {}
    for foot, path in inputs.items():
        original = geometry.read_obj(path)
        verts, faces = clipped_hull(original, ceiling)
        target = out / path.relative_to(source.parent)
        with target.open("w", encoding="utf-8", newline="\n") as stream:
            for v in verts:
                stream.write("v %.12g %.12g %.12g\n" % tuple(v))
            for face in faces:
                stream.write("f %d %d %d\n" % tuple(face))
        rows[foot] = {"original_sha256": source_hashes[foot], "candidate_sha256": digest(target),
                      "original_min_z_m": float(original[:, 2].min()),
                      "candidate_min_z_m": float(verts[:, 2].min()), "candidate_max_z_m": float(verts[:, 2].max()),
                      "vertices": len(verts), "faces": len(faces)}
    if digest(source) != source_urdf_hash or any(digest(path) != source_hashes[foot] for foot, path in inputs.items()):
        raise ValueError("source changed during generation")
    result = {"source_urdf": str(source), "source_sha256": source_urdf_hash,
              "candidate_urdf": str(out / source.name), "ceiling_local_z_m": ceiling,
              "method": "convex hull clipped below foot local joint pivot", "feet": rows,
              "scope": "isolated collision-shape candidate; no full-range or runtime verification"}
    (out / "collision_candidate.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urdf", type=Path, required=True)
    parser.add_argument("--out_dir", type=Path, required=True)
    parser.add_argument("--ceiling", type=float, required=True)
    args = parser.parse_args()
    result = create(args.urdf, args.out_dir, args.ceiling)
    print(json.dumps({"candidate": result["candidate_urdf"], "feet": result["feet"]}, indent=2))
