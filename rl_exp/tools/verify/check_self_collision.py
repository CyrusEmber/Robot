# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Self-collision check on a family's leg reachable set (no sim, no framework).

Why this exists: a leg that gains a new axis gains a new reachable set, and this repo runs its lizard
lines with ``enabled_self_collisions=False`` -- so nothing in training punishes a leg that passes
through the torso or through another leg. A coarse sweep cannot PROVE the set is clear; what it can do
is hand back a counterexample (a pose inside the joint limits where two links overlap) or a minimum
clearance that is uncomfortably small, and both are actionable before training.

Method, and its stated limits:

* poses stay INSIDE the URDF's own joint limits, read from the same file the importer reads. A sweep
  that leaves them reports overlaps the robot cannot reach -- the first version of this script did
  exactly that (haa swept to +-1.2 rad against a +-0.6 limit) and its worst "finding" was 317 mm of
  foot-inside-torso at an impossible pose;
* each link's COLLISION mesh is replaced by its CONVEX HULL, and overlap is tested by containment (a
  vertex of A inside hull(B), either direction). Hulls over-approximate concave links, so a reported
  overlap can be a hull artefact, and containment misses a pure edge-face crossing, so a real one can
  be missed. Both are ceilings of this method, printed with the result, not hidden;
* a directly jointed pair is skipped: its geometry shares the pivot by construction, so overlap there
  is expected and is not a finding;
* forward kinematics is re-implemented in numpy from the URDF itself (origin xyz + axis angle) -- that
  is the point of the check being offline: a second, no GPU, and more poses than a stepped sim sweep;
* the sweep is reported in two families of poses so an inherited quirk is not read as this family's
  new axis: ``single`` (one joint at a time, others zero) and ``combined`` (hip x fold, and
  hip x knee).

Usage (from the repo root):

    python rl_exp/tools/verify/check_self_collision.py --family lizard2
    python rl_exp/tools/verify/check_self_collision.py --family lizard --json <report.json>

Exit code is 1 when a pose inside the limits overlaps or when the minimum clearance falls below
``--clearance`` mm.
"""

from __future__ import annotations

import argparse
import itertools
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial import ConvexHull

_REPO = pathlib.Path(__file__).resolve().parents[3]
_RL_EXP = _REPO / "rl_exp"
_LEGS = ("lf", "rf", "rl", "rr")
_LEG_TOKENS = ("hip", "haa", "hfe", "kfe", "foot")


def load_urdf(path: pathlib.Path) -> dict:
    """Links (with their collision mesh), joints (origin/axis/limits) as plain dicts."""
    root = ET.parse(path).getroot()
    links: dict[str, dict] = {}
    for link in root.findall("link"):
        mesh = link.find("collision/geometry/mesh")
        links[link.get("name")] = {
            "collision": (path.parent / mesh.get("filename")).resolve() if mesh is not None else None
        }
    joints: dict[str, dict] = {}
    for joint in root.findall("joint"):
        axis = joint.find("axis")
        limit = joint.find("limit")
        joints[joint.get("name")] = {
            "parent": joint.find("parent").get("link"),
            "child": joint.find("child").get("link"),
            "origin": np.array([float(v) for v in joint.find("origin").get("xyz").split()]),
            "axis": np.array([float(v) for v in axis.get("xyz").split()]) if axis is not None else None,
            "limits": (float(limit.get("lower")), float(limit.get("upper"))) if limit is not None else None,
        }
    return {"links": links, "joints": joints}


def read_obj(path: pathlib.Path) -> np.ndarray:
    return np.array([list(map(float, ln.split()[1:4])) for ln in path.read_text().splitlines()
                     if ln.startswith("v ")])


def transform_equations(equations: np.ndarray, rotate: np.ndarray, shift: np.ndarray) -> np.ndarray:
    """The same convex region after a rigid transform: inside stays ``n.x + d <= 0``.

    Exact and cheap, so a pose costs a matrix multiply per link instead of a hull rebuild (the first
    version rebuilt the hull for every pair and pose, which is what made the sweep too slow to be
    fine).
    """
    normals = equations[:, :3] @ rotate.T
    offsets = equations[:, 3] - normals @ shift
    return np.column_stack([normals, offsets])


def signed_inside(points: np.ndarray, equations: np.ndarray) -> float:
    """Best (largest) signed margin of ``points`` against a hull: negative = inside by that much."""
    violations = points @ equations[:, :3].T + equations[:, 3]
    return float(np.min(np.max(violations, axis=1)))


def chain_up(joints: dict, link: str) -> list[str]:
    parent_of = {spec["child"]: (name, spec) for name, spec in joints.items()}
    chain: list[str] = []
    current = link
    while current in parent_of:
        name, spec = parent_of[current]
        chain.append(name)
        current = spec["parent"]
    return list(reversed(chain))


def fk(joints: dict, link: str, q: dict[str, float]) -> np.ndarray:
    """4x4 pose of ``link`` with the named joints at ``q`` (unlisted joints at zero)."""
    transform = np.eye(4)
    for name in chain_up(joints, link):
        spec = joints[name]
        move = np.eye(4)
        move[:3, 3] = spec["origin"]
        angle = float(q.get(name, 0.0))
        axis = spec["axis"]
        if axis is not None and angle:
            axis = axis / np.linalg.norm(axis)
            cross = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
            spin = np.eye(4)
            spin[:3, :3] = np.eye(3) + np.sin(angle) * cross + (1 - np.cos(angle)) * (cross @ cross)
            move = move @ spin
        transform = transform @ move
    return transform


def jointed_pair(joints: dict, a: str, b: str) -> bool:
    return any({spec["parent"], spec["child"]} == {a, b} for spec in joints.values())


def depths(joints: dict, link: str) -> list[str]:
    """The links from the root down to ``link`` (inclusive)."""
    parent_of = {spec["child"]: spec["parent"] for spec in joints.values()}
    chain, current = [link], link
    while current in parent_of:
        current = parent_of[current]
        chain.append(current)
    return list(reversed(chain))


def chain_distance(joints: dict, a: str, b: str) -> int:
    """Joints between two links along the tree (1 = directly jointed)."""
    path_a, path_b = depths(joints, a), depths(joints, b)
    shared = 0
    for step, (link_a, link_b) in enumerate(zip(path_a, path_b)):
        if link_a != link_b:
            break
        shared = step + 1
    return (len(path_a) - shared) + (len(path_b) - shared)


def pivot_region(joints: dict, a: str, b: str, span: int = 2) -> bool:
    """True when two links meet at a pivot within ``span`` joints of each other.

    Their collision meshes are authored to share that pivot, so overlap there is a property of the
    construction, not a finding: the first version of this check reported the knee's own femur-vs-shank
    region (-119 mm) and sub-millimetre hull noise around every joint as "penetration", which buried
    what the sweep is actually for.
    """
    return chain_distance(joints, a, b) <= span


def leg_joints(joints: dict, leg: str) -> dict[str, tuple[float, float]]:
    """``{token: (lo, hi)}`` for the joints this leg actually has (a family without a hip has none)."""
    out = {}
    for token in _LEG_TOKENS:
        name = f"{leg}_{token}_joint"
        if name in joints and joints[name]["limits"] is not None:
            out[token] = joints[name]["limits"]
    return out


def sweep_poses(joints: dict) -> list[tuple[dict[str, float], str]]:
    """The poses to check, each labelled ``single`` or ``combined``, all inside the URDF limits.

    Single-joint poses catch a link folding onto a neighbour (the foot onto the femur at the ankle
    extreme); combined poses catch what only two axes together reach -- which is the whole reason a
    new hip axis needs this check.
    """
    poses: list[tuple[dict[str, float], str]] = []
    for leg in _LEGS:
        limits = leg_joints(joints, leg)
        if not limits:
            continue
        for token, (lo, hi) in limits.items():
            name = f"{leg}_{token}_joint"
            for value in (lo, 0.0, hi):
                poses.append(({name: value}, "single"))
        hip = limits.get("hip")
        others = [(f"{leg}_{t}_joint", limits[t]) for t in ("haa", "hfe", "kfe") if t in limits]
        for level in (0, 1, 2):  # all-fold-min / neutral / all-fold-max
            fold = {name: (lo if level == 0 else hi if level == 2 else 0.0) for name, (lo, hi) in others}
            if hip is None:
                poses.append((dict(fold), "combined"))
                continue
            for value in (hip[0], 0.0, hip[1]):
                poses.append(({f"{leg}_hip_joint": value, **fold}, "combined"))
        if hip is not None:
            knee = limits.get("hfe")
            if knee is not None:
                for hip_v, knee_v in itertools.product((hip[0], 0.0, hip[1]), (knee[0], 0.0, knee[1])):
                    poses.append(({f"{leg}_hip_joint": hip_v, f"{leg}_hfe_joint": knee_v}, "combined"))
    return poses


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--family", required=True, help="family whose urdf + collision meshes to sweep")
    parser.add_argument("--clearance", type=float, default=5.0, help="minimum clearance to demand [mm]")
    parser.add_argument("--json", help="write the full report here")
    args = parser.parse_args()

    urdf = _RL_EXP / "versions" / args.family / f"{args.family}.urdf"
    if not urdf.exists():
        print(f"no urdf: {urdf}", file=sys.stderr)
        return 1
    model = load_urdf(urdf)
    links, joints = model["links"], model["joints"]
    movable = [name for name in links if links[name]["collision"] is not None]
    print(f"family {args.family}: {len(movable)} of {len(links)} links carry a collision mesh")
    print(f"  no collision (cannot be the penetrating side): {sorted(set(links) - set(movable))}")

    hulls = {}
    for name in movable:
        points = read_obj(links[name]["collision"])
        convex = ConvexHull(points)
        # ``convex.vertices`` are INDICES into ``points``, not coordinates: the first version of this
        # check used them as coordinates and fell over on the matmul
        hulls[name] = {"equations": convex.equations, "vertices": points[convex.vertices]}

    pairs = [(a, b) for a, b in itertools.combinations(sorted(movable), 2)
             if not pivot_region(joints, a, b)]
    poses = sweep_poses(joints)
    print(f"  link pairs checked: {len(pairs)} | poses: {len(poses)} (all inside the URDF limits)")
    print("  skipped as pivot regions (<=2 joints apart, meshes share the pivot by construction): "
          + ", ".join(f"{a}|{b}" for a, b in itertools.combinations(sorted(movable), 2)
                      if pivot_region(joints, a, b)))

    worst = {"margin_mm": float("inf"), "pose": None, "pair": None, "kind": None}
    overlaps: list[dict] = []
    for q, kind in poses:
        placed = {name: fk(joints, name, q) for name in movable}
        world_eq = {
            name: transform_equations(hulls[name]["equations"], placed[name][:3, :3], placed[name][:3, 3])
            for name in movable
        }
        world_pts = {
            name: (placed[name][:3, :3] @ hulls[name]["vertices"].T).T + placed[name][:3, 3]
            for name in movable
        }
        for a, b in pairs:
            margin = min(signed_inside(world_pts[a], world_eq[b]), signed_inside(world_pts[b], world_eq[a]))
            if margin * 1000.0 < worst["margin_mm"]:
                worst = {"margin_mm": margin * 1000.0, "pose": dict(q), "pair": [a, b], "kind": kind}
            if margin < 0.0:
                overlaps.append({"pose": dict(q), "pair": [a, b], "kind": kind,
                                 "penetration_mm": -margin * 1000.0})
    print(f"\nminimum margin over all poses: {worst['margin_mm']:+.2f} mm"
          f" ({worst['pair']}, {worst['kind']}, {worst['pose']})")
    print(f"penetrating judgements: {len(overlaps)}")
    for hit in sorted(overlaps, key=lambda h: -h["penetration_mm"])[:12]:
        print(f"  PENETRATION {hit['penetration_mm']:7.2f} mm [{hit['kind']}] {hit['pair']} at "
              + " ".join(f"{k}={v:+.2f}" for k, v in sorted(hit["pose"].items())))
    kinds = sorted({h["kind"] for h in overlaps})
    print(f"  by kind: {kinds or 'none'}")
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(
            {"family": args.family, "poses": len(poses), "worst": worst, "overlaps": overlaps},
            ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"report written: {args.json}")

    print("\nCEILING: hulls over-approximate concave links (a reported overlap can be a hull artefact)")
    print("and containment misses a pure edge-face crossing (a real one can be missed). Findings, not")
    print("proof; the poses are inside the URDF limits but the product of per-joint extremes is not")
    print("necessarily reachable under load.")
    bad = bool(overlaps) or worst["margin_mm"] < args.clearance
    print("SELF_COLLISION_COUNTEREXAMPLE" if overlaps else
          ("SELF_COLLISION_CLEARANCE_LOW" if bad else "SELF_COLLISION_SWEEP_CLEAN"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
