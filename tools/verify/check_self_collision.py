# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause


"""URDF readers and forward kinematics shared by the offline geometry tools (no sim).

Only the pure helpers live here: the leg-sweep CLI it used to carry retired with the old
recipe line, and its callers (pose_target_solver, lizard2_round_support_geometry) need
nothing beyond these four functions.
"""

from __future__ import annotations

import pathlib
import xml.etree.ElementTree as ET

import numpy as np


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
