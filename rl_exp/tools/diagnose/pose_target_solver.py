# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Bounded point/normal IK for declared URDF links, independent of simulation.

Uses the repository FK reader, which supports revolute/fixed trees with zero joint
origin rotations. Results are sampled geometric candidates, not collision,
contact, dynamics or hardware capability evidence. The caller owns frame and
target definitions, limits, initial state, tolerances, and subsequent prechecks.
"""

from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np
from scipy.optimize import least_squares

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "verify"))
import check_self_collision as geometry  # noqa: E402


def load_model(path):
    """Load a URDF after validating the subset supported by the shared FK reader."""
    path = Path(path)
    root = ET.parse(path).getroot()
    for joint in root.findall("joint"):
        origin = joint.find("origin")
        kind = joint.get("type")
        if kind not in ("fixed", "revolute") or origin is None:
            raise ValueError(f"unsupported joint: {joint.get('name')}")
        rpy = [float(x) for x in origin.get("rpy", "0 0 0").split()]
        if len(rpy) != 3 or not np.allclose(rpy, 0, atol=1e-12, rtol=0):
            raise ValueError(f"unsupported joint origin rotation: {joint.get('name')}")
        if kind == "revolute":
            axis, limit = joint.find("axis"), joint.find("limit")
            if axis is None or limit is None:
                raise ValueError(f"missing axis or limits: {joint.get('name')}")
            a = np.array([float(x) for x in axis.get("xyz").split()])
            bounds = np.array([float(limit.get("lower")), float(limit.get("upper"))])
            if a.shape != (3,) or not np.all(np.isfinite(a)) or np.linalg.norm(a) == 0 or not np.all(np.isfinite(bounds)) or bounds[0] >= bounds[1]:
                raise ValueError(f"invalid axis or limits: {joint.get('name')}")
    model = geometry.load_urdf(path)
    children = [j["child"] for j in model["joints"].values()]
    if len(children) != len(set(children)):
        raise ValueError("URDF is not a tree: repeated child")
    for link in model["links"]:
        seen, cur = set(), link
        parents = {j["child"]: j["parent"] for j in model["joints"].values()}
        while cur in parents:
            if cur in seen:
                raise ValueError("URDF contains a cycle")
            seen.add(cur)
            cur = parents[cur]
    return model


def solve(model, initial, free_joints, targets, position_tolerance, normal_tolerance, max_evaluations=300):
    """Fit link-local points and normals to root-frame targets within URDF bounds.

    ``initial`` includes every movable joint, including held joints; ``targets``
    contains mappings with link, point_local, point_target and optionally both
    normal_local and normal_target. Position tolerances are metres and normal
    tolerance is Euclidean unit-vector distance. Failure returns residuals and
    a candidate with ``passed=False``; it does not establish unreachable geometry.
    """
    joints = model["joints"]
    movable = {name for name, spec in joints.items() if spec["axis"] is not None}
    if set(initial) != movable or not free_joints or len(set(free_joints)) != len(free_joints) or not set(free_joints) <= movable or not targets:
        raise ValueError("declare all initial joints, unique free joints, and targets")
    if not np.isfinite(position_tolerance) or position_tolerance <= 0 or not np.isfinite(normal_tolerance) or normal_tolerance <= 0 or max_evaluations < 1:
        raise ValueError("invalid tolerance or budget")
    for name in movable:
        lo, hi = joints[name]["limits"]
        if not np.isfinite(initial[name]) or not lo <= initial[name] <= hi:
            raise ValueError(f"initial joint out of bounds: {name}")
    parsed = []
    for target in targets:
        link = target["link"]
        if link not in model["links"]:
            raise ValueError(f"unknown link: {link}")
        point, goal = (np.asarray(target[k], dtype=float) for k in ("point_local", "point_target"))
        if point.shape != (3,) or goal.shape != (3,) or not np.all(np.isfinite(point)) or not np.all(np.isfinite(goal)):
            raise ValueError("invalid point")
        has_normal = "normal_local" in target or "normal_target" in target
        normal, desired = None, None
        if has_normal:
            if "normal_local" not in target or "normal_target" not in target:
                raise ValueError("both normal vectors are required")
            normal, desired = (np.asarray(target[k], dtype=float) for k in ("normal_local", "normal_target"))
            for value in (normal, desired):
                if value.shape != (3,) or not np.all(np.isfinite(value)) or not np.isclose(np.linalg.norm(value), 1., atol=1e-6, rtol=0):
                    raise ValueError("normal vectors must be finite and unit length")
        parsed.append((link, point, goal, normal, desired))
    lo = np.array([joints[n]["limits"][0] for n in free_joints])
    hi = np.array([joints[n]["limits"][1] for n in free_joints])

    def errors(values):
        q = dict(initial, **dict(zip(free_joints, values)))
        rows = []
        for link, point, goal, normal, desired in parsed:
            pose = geometry.fk(joints, link, q)
            pos_error = pose[:3, :3] @ point + pose[:3, 3] - goal
            normal_error = None if normal is None else pose[:3, :3] @ normal - desired
            rows.append((pos_error, normal_error))
        return q, rows

    def residual(values):
        _, rows = errors(values)
        return np.concatenate([part for p, n in rows for part in ([p / position_tolerance] if n is None else [p / position_tolerance, n / normal_tolerance])])

    result = least_squares(residual, np.array([initial[n] for n in free_joints]), bounds=(lo, hi), max_nfev=max_evaluations)
    q, rows = errors(result.x)
    measurements = [{"link": target[0], "position_error_m": float(np.linalg.norm(p)),
                     "normal_error": None if n is None else float(np.linalg.norm(n))}
                    for target, (p, n) in zip(parsed, rows)]
    passed = bool(result.success and all(row["position_error_m"] <= position_tolerance and
                   (row["normal_error"] is None or row["normal_error"] <= normal_tolerance) for row in measurements))
    return {"passed": passed, "q_rad": {k: float(v) for k, v in q.items()},
            "targets": measurements, "evaluations": int(result.nfev), "solver_status": int(result.status)}
