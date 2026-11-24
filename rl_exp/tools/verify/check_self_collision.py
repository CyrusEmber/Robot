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
    python rl_exp/tools/verify/check_self_collision.py --family lizard2 --urdf <renamed>.urdf --naming split

``--naming`` declares which words the swept body carries (``shared`` = every leg one root set, ``split``
= the front/rear rename); the roles (root axis, the three hinges, the knee) are swept by POSITION off it,
so the same body renamed sweeps the same poses and the two reports differ only in vocabulary. A body
carrying no root axis (the old one) simply has none of those poses -- that is the body, not the naming.

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
sys.path.insert(0, str(pathlib.Path(__file__).parent))
# ``rl_exp`` is not an installed package, so the repo root joins sys.path beside the table it holds --
# the same insert ``check_dr_parity`` does for the same reason.
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
from rl_exp.tasks import joint_names  # noqa: E402 - the leg-chain vocabulary the sweep is bound to
_LEGS = ("lf", "rf", "rl", "rr")


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


def read_obj_faces(path: pathlib.Path) -> tuple[np.ndarray, np.ndarray]:
    """Vertices and (0-based) triangles of an OBJ, for the mesh-level confirmation step."""
    vertices, faces = [], []
    for line in path.read_text().splitlines():
        if line.startswith("v "):
            vertices.append(list(map(float, line.split()[1:4])))
        elif line.startswith("f "):
            faces.append([int(tok.split("/")[0]) - 1 for tok in line.split()[1:4]])
    return np.array(vertices), np.array(faces, dtype=int)


def mesh_gap(points_a: np.ndarray, verts_b: np.ndarray, faces_b: np.ndarray) -> float:
    """Signed mesh-level gap: negative when a point of A is inside B's surface.

    Point-to-triangle distance, sign by the nearest triangle's own normal (the winding of these
    generated meshes is outward). It is the quantity the hull margin only approximates: the hulls
    over-approximate a concave link, so a positive hull margin can still be a real clearance and a
    negative one can be a hull artefact -- which is exactly why the flagged poses are re-checked here
    (review 2026-09-22).

    Both arguments must be in the SAME frame, and that sign is only containment evidence while the gap
    is small: at tens of millimetres a point can sit behind the nearest triangle's plane while being
    outside the mesh, so a large negative number is not a penetration (2026-09-29).
    """
    tri = verts_b[faces_b]
    best = float("inf")
    for point in points_a:
        edge1, edge2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
        rel = point - tri[:, 0]
        d00 = np.einsum("ij,ij->i", edge1, edge1)
        d01 = np.einsum("ij,ij->i", edge1, edge2)
        d11 = np.einsum("ij,ij->i", edge2, edge2)
        d20 = np.einsum("ij,ij->i", rel, edge1)
        d21 = np.einsum("ij,ij->i", rel, edge2)
        denom = d00 * d11 - d01 * d01
        denom[denom == 0] = 1e-12
        v = (d11 * d20 - d01 * d21) / denom
        w = (d00 * d21 - d01 * d20) / denom
        u = 1.0 - v - w
        # closest point on each triangle: inside the face, or on the nearest edge (barycentric clamp)
        clamp_v = np.clip(v, 0.0, 1.0)
        clamp_w = np.clip(w, 0.0, 1.0)
        clamp_u = np.clip(u, 0.0, 1.0)
        total = clamp_u + clamp_v + clamp_w
        clamp_u, clamp_v, clamp_w = clamp_u / total, clamp_v / total, clamp_w / total
        closest = (clamp_u[:, None] * tri[:, 0] + clamp_v[:, None] * tri[:, 1]
                   + clamp_w[:, None] * tri[:, 2])
        distance = np.linalg.norm(point - closest, axis=1)
        index = int(np.argmin(distance))
        normal = np.cross(edge1[index], edge2[index])
        norm = np.linalg.norm(normal)
        sign = -1.0 if norm > 0 and np.dot(point - tri[index, 0], normal / norm) < 0 else 1.0
        best = min(best, sign * float(distance[index]))
    return best


def confirm(joints: dict, links: dict, q: dict, pairs: list[tuple[str, str]], tops: int = 6) -> list[dict]:
    """Re-check the worst pairs of one pose against the real meshes, not their hulls."""
    placed = {name: fk(joints, name, q) for name in links}
    out = []
    for a, b in pairs:
        va, fa = read_obj_faces(links[a]["collision"])
        vb, fb = read_obj_faces(links[b]["collision"])
        pa = (placed[a][:3, :3] @ va.T).T + placed[a][:3, 3]
        pb = (placed[b][:3, :3] @ vb.T).T + placed[b][:3, 3]
        # Both sides placed: passing A's world points against B's LOCAL vertices (what this did until
        # 2026-09-29) measures A against B-as-if-at-the-origin, which is not a distance between the
        # links at all -- the lizard2 knee pair read +393 mm that way against a true -33 mm.
        gap = max(mesh_gap(pa, pb, fb), mesh_gap(pb, pa, fa))
        out.append({"pair": [a, b], "mesh_gap_mm": gap * 1000.0, "pose": dict(q)})
    return sorted(out, key=lambda row: row["mesh_gap_mm"])[:tops]


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


def leg_joints(joints: dict, leg: str,
               naming: dict[str, tuple[str, ...]] = joint_names.LEGACY_NAMING) -> dict[str, tuple[float, float]]:
    """``{token: (lo, hi)}`` for the joints this leg actually has (a body without a root axis has none).

    The tokens come from the naming the caller bound, not from a list this file carries: the roles are the
    naming's positions, and a body that does not carry one (the old body has no root axis) simply has no
    entry -- which is what keeps this the same sweep on both namings.
    """
    out = {}
    for token in joint_names.roots_of(naming, leg):
        name = joint_names.joint_name(leg, token)
        if name in joints and joints[name]["limits"] is not None:
            out[token] = joints[name]["limits"]
    return out


def sweep_poses(joints: dict,
                naming: dict[str, tuple[str, ...]] = joint_names.LEGACY_NAMING) -> list[tuple[dict[str, float], str]]:
    """The poses to check, each labelled ``single`` or ``combined``, all inside the URDF limits.

    Single-joint poses catch a link folding onto a neighbour (the foot onto the femur at the ankle
    extreme); combined poses catch what only two axes together reach -- which is the whole reason a
    new hip axis needs this check.

    Legacy namings retain their original root/hinge positions. Spatial palm inserts a twist
    before the elbow/knee: pair the root with that actual distal hinge and include all four
    non-root axes (including wrist/ankle) in combined corners. These finite corners do not
    establish collision freedom throughout the reachable set.
    """
    poses: list[tuple[dict[str, float], str]] = []
    for leg in _LEGS:
        roots = joint_names.roots_of(naming, leg)
        spatial = naming == joint_names.PALM_SPATIAL_NAMING
        root_token, knee_token = roots[0], roots[-2] if spatial else roots[2]
        limits = leg_joints(joints, leg, naming)
        if not limits:
            continue
        for token, (lo, hi) in limits.items():
            name = joint_names.joint_name(leg, token)
            for value in (lo, 0.0, hi):
                poses.append(({name: value}, "single"))
        hip = limits.get(root_token)
        other_tokens = roots[1:] if spatial else roots[1:4]
        others = [(joint_names.joint_name(leg, t), limits[t]) for t in other_tokens if t in limits]
        for level in (0, 1, 2):  # all-fold-min / neutral / all-fold-max
            fold = {name: (lo if level == 0 else hi if level == 2 else 0.0) for name, (lo, hi) in others}
            if hip is None:
                poses.append((dict(fold), "combined"))
                continue
            for value in (hip[0], 0.0, hip[1]):
                poses.append(({joint_names.joint_name(leg, root_token): value, **fold}, "combined"))
        if hip is not None:
            knee = limits.get(knee_token)
            if knee is not None:
                for hip_v, knee_v in itertools.product((hip[0], 0.0, hip[1]), (knee[0], 0.0, knee[1])):
                    poses.append(({joint_names.joint_name(leg, root_token): hip_v,
                                   joint_names.joint_name(leg, knee_token): knee_v}, "combined"))
    return poses
