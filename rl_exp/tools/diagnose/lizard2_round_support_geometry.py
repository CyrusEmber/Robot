# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Prepare two round-foot static geometry candidates; no simulation or lift.

SI units: metres, radians, kilograms. Identity root quaternion uses xyzw.
Clearance is provisional geometry input, not physical approval. No internal
self-collision, continuous path, contact force, stability or dynamics claim.
"""

import argparse
import copy
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial.transform import Rotation

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from rl_exp.tools.runrecord import binding  # noqa: E402

import pose_target_solver as solver  # noqa: E402

FEET = ("lf_wrist", "rf_wrist", "rl_ankle", "rr_ankle")
GROUPS = {"lf+rr": ("lf_wrist", "rr_ankle"), "rf+rl": ("rf_wrist", "rl_ankle")}
MARGIN = 0.02
POINT_TOL = 1e-5
NONFOOT_GAP = 0.002
DEFAULT_URDF = REPO / "rl_exp/out/lizard2_round_feet/export04/lizard2_round_feet.urdf"
DEFAULT_OUT = REPO / "rl_exp/out/lizard2_round_support/prepare03/geometry_current.json"


def vector(text, size=3):
    value = np.array([float(x) for x in text.split()])
    if value.shape != (size,) or not np.all(np.isfinite(value)):
        raise ValueError(f"invalid vector: {text}")
    return value


def origin(element):
    """Return item/inertial origin transform, including URDF fixed-axis RPY."""
    result = np.eye(4)
    node = element.find("origin")
    if node is not None:
        result[:3, 3] = vector(node.get("xyz", "0 0 0"))
        result[:3, :3] = Rotation.from_euler("xyz", vector(node.get("rpy", "0 0 0"))).as_matrix()
    return result


def prepare(urdf):
    """Read every visual/collision item; reject unsupported geometry explicitly."""
    urdf = Path(urdf).resolve()
    model = solver.load_model(urdf)
    root = ET.parse(urdf).getroot()
    movable = {n for n, j in model["joints"].items() if j["axis"] is not None}
    if len(movable) != 26 or sum(j.get("type") == "fixed" for j in root.findall("joint")) != 4:
        raise ValueError("expected 26 movable and 4 fixed joints")
    children = {j["child"] for j in model["joints"].values()}
    if set(model["links"]) - children != {"base_link"}:
        raise ValueError("expected one base_link-rooted tree")
    items, inertials, meshes = [], [], set()
    for link in root.findall("link"):
        name = link.get("name")
        inertial = link.find("inertial")
        if inertial is None or inertial.find("mass") is None:
            raise ValueError(f"missing inertial: {name}")
        mass = float(inertial.find("mass").get("value"))
        if not np.isfinite(mass) or mass <= 0:
            raise ValueError(f"invalid mass: {name}")
        inertials.append((name, mass, origin(inertial)[:3, 3]))
        for kind in ("visual", "collision"):
            for index, item in enumerate(link.findall(kind)):
                shapes = list(item.find("geometry")) if item.find("geometry") is not None else []
                if len(shapes) != 1 or shapes[0].tag not in ("mesh", "sphere"):
                    raise ValueError(f"unsupported geometry: {name}/{kind}/{index}")
                shape = shapes[0]
                row = {"link": name, "kind": kind, "index": index,
                       "shape": shape.tag, "origin": origin(item)}
                if shape.tag == "mesh":
                    path = (urdf.parent / shape.get("filename")).resolve()
                    if path.suffix.lower() != ".obj":
                        raise ValueError(f"unsupported mesh: {path}")
                    vertices = solver.geometry.read_obj(path)
                    if vertices.ndim != 2 or vertices.shape[1] != 3 or not len(vertices) or not np.all(np.isfinite(vertices)):
                        raise ValueError(f"invalid OBJ vertices: {path}")
                    scale = vector(shape.get("scale", "1 1 1"))
                    if np.any(scale <= 0):
                        raise ValueError(f"unsupported mesh scale: {path}")
                    row.update(vertices=vertices * scale, path=str(path))
                    meshes.add(path)
                else:
                    radius = float(shape.get("radius"))
                    if not np.isfinite(radius) or radius <= 0:
                        raise ValueError(f"invalid sphere: {name}")
                    row["radius_m"] = radius
                items.append(row)
    feet = {}
    for foot in FEET:
        rows = [i for i in items if i["link"] == foot]
        if len(rows) != 2 or {i["kind"] for i in rows} != {"visual", "collision"} or any(i["shape"] != "sphere" for i in rows):
            raise ValueError(f"expected visual/collision foot spheres: {foot}")
        if any(abs(i["radius_m"] - 0.08) > 1e-12 for i in rows) or not np.allclose(rows[0]["origin"][:3, 3], rows[1]["origin"][:3, 3], atol=1e-12, rtol=0):
            raise ValueError(f"inconsistent foot spheres: {foot}")
        feet[foot] = next(i for i in rows if i["kind"] == "collision")
    initial = {n: 0. for n in model["joints"] if n in movable}
    initial["tail1_pitch_joint"] = 0.3
    narrowed = copy.deepcopy(model)
    for name in movable:
        lo, hi = model["joints"][name]["limits"]
        if not lo + MARGIN <= initial[name] <= hi - MARGIN:
            raise ValueError(f"initial pose lacks margin: {name}")
        narrowed["joints"][name]["limits"] = (lo + MARGIN, hi - MARGIN)
    free = sorted({n for foot in FEET for n in solver.geometry.chain_up(model["joints"], foot)
                   if n in movable and n.startswith(foot[:2] + "_") and not n.endswith("_twist_joint")})
    if len(free) != 12 or any(sum(n.startswith(foot[:2] + "_") for n in free) != 3 for foot in FEET):
        raise ValueError("expected exactly three free leg joints per foot; twists held at zero")
    centers = {foot: (solver.geometry.fk(model["joints"], foot, initial) @ item["origin"])[:3, 3]
               for foot, item in feet.items()}
    height = -min(centers[f][2] - feet[f]["radius_m"] for f in FEET)
    return {"model": model, "narrowed": narrowed, "items": items, "inertials": inertials,
            "meshes": meshes, "initial": initial, "free": free, "feet": feet,
            "centers": centers, "root_height_m": float(height)}


def targets_for(context, support, clearance):
    return [{"link": foot, "point_local": context["feet"][foot]["origin"][:3, 3].tolist(),
             "point_target": [float(context["centers"][foot][0]), float(context["centers"][foot][1]),
                              context["feet"][foot]["radius_m"] - context["root_height_m"]
                              + (0. if foot in support else clearance)]} for foot in FEET]


def validate(context, q, support, clearance):
    """Recompute full FK geometry and limits, not cached solver measurements."""
    failures, margins, measured = [], {}, []
    model = context["model"]
    if set(q) != set(context["initial"]) or not all(np.isfinite(v) for v in q.values()):
        raise ValueError("q must contain all 26 finite joint angles")
    for name, angle in q.items():
        lo, hi = model["joints"][name]["limits"]
        lower, upper = float(angle - lo), float(hi - angle)
        margins[name] = {"lower_rad": lower, "upper_rad": upper, "min_rad": min(lower, upper)}
        if min(lower, upper) < MARGIN - 1e-10:
            failures.append(f"joint_margin:{name}")
        if name not in context["free"] and abs(angle - context["initial"][name]) > 1e-12:
            failures.append(f"held_joint:{name}")
    poses = {}
    for link in model["links"]:
        pose = solver.geometry.fk(model["joints"], link, q).copy()
        pose[2, 3] += context["root_height_m"]
        poses[link] = pose
    for item in context["items"]:
        transform = poses[item["link"]] @ item["origin"]
        row = {k: item[k] for k in ("link", "kind", "index", "shape")}
        if item["shape"] == "sphere":
            center = transform[:3, 3]
            gap = float(center[2] - item["radius_m"])
            row.update(center_world_m=center.tolist(), radius_m=item["radius_m"])
        else:
            vertices = item["vertices"] @ transform[:3, :3].T + transform[:3, 3]
            gap = float(vertices[:, 2].min())
            row["mesh"] = item["path"]
        row["ground_gap_m"] = gap
        measured.append(row)
        label = f'{item["link"]}/{item["kind"]}/{item["index"]}'
        if item["link"] in FEET:
            if item["shape"] != "sphere":
                failures.append(f"foot_shape:{label}")
                continue
            target = context["centers"][item["link"]][:2]
            if np.linalg.norm(center[:2] - target) > POINT_TOL:
                failures.append(f"foot_xy:{label}")
            if item["link"] in support:
                if abs(gap) > POINT_TOL:
                    failures.append(f"support_gap:{label}")
            elif abs(gap - clearance) > POINT_TOL:
                failures.append(f"swing_clearance:{label}")
        elif gap < NONFOOT_GAP:
            failures.append(f"nonfoot_ground:{label}")
    mass = sum(m for _, m, _ in context["inertials"])
    com = sum(m * (poses[n][:3, :3] @ p + poses[n][:3, 3]) for n, m, p in context["inertials"]) / mass
    return {"passed": not failures, "failures": failures, "joint_margins": margins,
            "min_joint_margin_rad": min(v["min_rad"] for v in margins.values()),
            "geometry": measured, "total_mass_kg": float(mass), "com_world_m": com.tolist(),
            "min_nonfoot_gap_m": min(r["ground_gap_m"] for r in measured if r["link"] not in FEET)}


def run(urdf, clearance=0.10):
    """Compute independent group candidates, preserving unsuccessful full states."""
    if not np.isfinite(clearance) or clearance < 0:
        raise ValueError("clearance must be finite and nonnegative")
    context = prepare(urdf)
    sources = [Path(__file__), Path(solver.__file__), Path(solver.geometry.__file__), Path(binding.__file__),
               REPO / "rl_exp/tools/verify/check_leg_reachability.py", REPO / "rl_exp/tasks/joint_names.py"]
    files = sorted(set([Path(urdf).resolve(), *context["meshes"], *sources]))
    hashes = {str(p.resolve()): binding.sha256_file(p) for p in files}
    if any(v is None for v in hashes.values()):
        raise ValueError("cannot bind all input/source files")
    data = {"urdf": str(Path(urdf).resolve()), "git_rev": binding.git_rev(REPO), "sha256": hashes,
            "scope": __doc__, "clearance_m": clearance, "joint_margin_required_rad": MARGIN,
            "nonfoot_gap_required_m": NONFOOT_GAP, "point_tolerance_m": POINT_TOL,
            "root_position_world_m": [0., 0., context["root_height_m"]],
            "root_quaternion_xyzw": [0., 0., 0., 1.], "root_rise_m": 0.,
            "root_height_rule": "negative minimum q0 sphere bottom; tail1_pitch explicitly 0.3 rad",
            "initial_q_rad": context["initial"], "initial_centers_root_m": {f: p.tolist() for f, p in context["centers"].items()},
            "free_joints": context["free"], "groups": {}}
    for name, support in GROUPS.items():
        targets = targets_for(context, support, clearance)
        try:
            result = solver.solve(context["narrowed"], dict(context["initial"]), context["free"], targets,
                                  position_tolerance=1e-7, normal_tolerance=1e-3, max_evaluations=300)
        except Exception as exc:
            result = {"passed": False, "q_rad": dict(context["initial"]), "error": f"{type(exc).__name__}: {exc}"}
        validation = validate(context, result["q_rad"], support, clearance)
        data["groups"][name] = {"support": list(support), "targets_root_m": targets,
                                "solver": result, "validation": validation,
                                "passed": bool(result["passed"] and validation["passed"])}
    data["passed"] = all(g["passed"] for g in data["groups"].values())
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urdf", type=Path, default=DEFAULT_URDF)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--clearance", type=float, default=0.10, help="Provisional swing sphere clearance [m]")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output exists; choose a fresh path")
    data = run(args.urdf, args.clearance)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
    print(json.dumps({"out": str(args.out), "passed": data["passed"],
                      "root_height_m": data["root_position_world_m"][2],
                      "groups": {n: {"passed": g["passed"], "failures": g["validation"]["failures"],
                                     "min_joint_margin_rad": g["validation"]["min_joint_margin_rad"],
                                     "min_nonfoot_gap_m": g["validation"]["min_nonfoot_gap_m"]}
                                 for n, g in data["groups"].items()}}))
    return 0 if data["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
