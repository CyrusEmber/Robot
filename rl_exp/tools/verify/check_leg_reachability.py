# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Offline forward kinematics of lizard2's leg chain, read from the URDF (no simulator, no torch).

Why this exists: the open question is whether the leg can pose a **level pad** inside its own joint
limits -- while standing at body height, and while sweeping through a stance of the required length.
That is a kinematics feasibility question, and it does not need a rollout. What it does need is an
FK whose numbers are the simulator's, which is what the caliber check below is for.

The chain, per leg, is a 5-revolute serial chain off ``base_link``
(``*_hip`` -> ``*_haa`` -> ``*_hfe`` -> ``*_kfe`` -> ``*_foot``); the URDF gives each joint's origin,
axis and position limits, so nothing here is transcribed from the asset by hand.

``--self-check`` compares the composed transform against two independently derived poses: at the zero
pose the foot origin must equal the sum of the chain's origins (valid there because every leg origin
carries ``rpy="0 0 0"``), and with the hip turned a quarter turn the foot must be that same point
rotated about the hip's own axis. Both are hand arithmetic, not a re-run of the same matrix product.
"""

import argparse
import math
import pathlib
import xml.etree.ElementTree as ET

_REPO = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_URDF = _REPO / "rl_exp" / "versions" / "lizard2" / "lizard2.urdf"
#: The five joints of a leg, root to pad. The blade is the last one: the pad is rigid to it.
CHAIN = ("hip", "haa", "hfe", "kfe", "foot")
LEGS = ("lf", "rf", "rl", "rr")


def _floats(text: str, count: int) -> list[float]:
    values = [float(token) for token in (text or "").split()]
    if len(values) != count:
        raise ValueError(f"expected {count} numbers, got {text!r}")
    return values


def _matrix(origin, axis, angle: float) -> list[list[float]]:
    """One joint's transform: the origin, then a rotation of ``angle`` about ``axis``."""
    x, y, z = origin
    ax, ay, az = axis
    norm = math.sqrt(ax * ax + ay * ay + az * az)
    ax, ay, az = ax / norm, ay / norm, az / norm
    c, s = math.cos(angle), math.sin(angle)
    k = 1.0 - c
    return [
        [ax * ax * k + c, ax * ay * k - az * s, ax * az * k + ay * s, x],
        [ay * ax * k + az * s, ay * ay * k + c, ay * az * k - ax * s, y],
        [az * ax * k - ay * s, az * ay * k + ax * s, az * az * k + c, z],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _multiply(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def load_chain(urdf: pathlib.Path, leg: str) -> dict:
    """The leg's five joints as ``(origin xyz, axis, limits)``, in chain order, read off the URDF."""
    root = ET.parse(urdf).getroot()
    by_name = {joint.get("name"): joint for joint in root.iter("joint")}
    chain = []
    for token in CHAIN:
        name = f"{leg}_{token}_joint"
        joint = by_name.get(name)
        if joint is None:
            raise SystemExit(f"{urdf} has no joint {name}")
        origin = _floats(joint.find("origin").get("xyz"), 3) if joint.find("origin") is not None else [0.0] * 3
        axis = _floats(joint.find("axis").get("xyz"), 3)
        limit = joint.find("limit")
        bounds = (float(limit.get("lower")), float(limit.get("upper")))
        chain.append({"name": name, "origin": origin, "axis": axis, "limits": bounds})
    return chain


def foot_pose(chain: list[dict], angles: list[float]):
    """The pad link's pose in ``base_link``: ``(position, 3x3 rotation)`` for the given joint angles."""
    transform = [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]
    for joint, angle in zip(chain, angles):
        transform = _multiply(transform, _matrix(joint["origin"], joint["axis"], angle))
    position = [transform[i][3] for i in range(3)]
    rotation = [[transform[i][j] for j in range(3)] for i in range(3)]
    return position, rotation


def pad_normal_in_link(urdf: pathlib.Path, leg: str) -> list[float]:
    """The pad's own normal in the foot link's frame, fitted to the collision mesh's lowest band.

    Read from the exported ``.obj`` rather than assumed: the sole is a curved cap, and how far its
    contact patch is from the link's ``-z`` is a property of the asset, not of this script.
    """
    candidates = sorted((_REPO / "rl_exp" / "versions" / "lizard2" / "meshes" / "collision").glob(
        f"{leg}_foot_collision.obj"))
    if not candidates:
        raise SystemExit("no collision mesh to take the pad normal from")
    vertices = []
    for line in candidates[0].read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("v "):
            vertices.append([float(token) for token in line.split()[1:4]])
    lowest = min(vertex[2] for vertex in vertices)
    band = [vertex for vertex in vertices if vertex[2] <= lowest + 0.002]
    centroid = [sum(vertex[i] for vertex in band) / len(band) for i in range(3)]
    # The plane through the contact band: its normal is the direction the band spans least in.
    cov = [[sum((vertex[i] - centroid[i]) * (vertex[j] - centroid[j]) for vertex in band) / len(band)
            for j in range(3)] for i in range(3)]
    normal = _smallest_eigenvector(cov)
    return normal if normal[2] < 0 else [-value for value in normal]


def _smallest_eigenvector(cov) -> list[float]:
    """The least-variance direction of a 3x3 covariance: power iteration on ``scale*I - cov``.

    Iterating on ``cov`` itself finds the *largest* variance -- which for a flat contact band is the
    direction the band spans, i.e. the plane, not its normal. That mistake reads as a pad standing at
    90 degrees, which is exactly what this returns if the sign of the shift is wrong.
    """
    scale = max(abs(cov[i][i]) for i in range(3)) or 1.0
    matrix = [[(scale if i == j else 0.0) - cov[i][j] for j in range(3)] for i in range(3)]
    vector = [0.3, 0.4, 0.5]
    for _ in range(200):
        vector = [sum(matrix[i][j] * vector[j] for j in range(3)) for i in range(3)]
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        vector = [value / norm for value in vector]
    return vector


def self_check(urdf: pathlib.Path) -> None:
    """Two poses whose answers are hand arithmetic, not a second pass of the same matrix product."""
    for leg in LEGS:
        chain = load_chain(urdf, leg)
        # Zero pose: every leg joint origin carries rpy="0 0 0", so the pad origin is their sum.
        hand = [sum(joint["origin"][i] for joint in chain) for i in range(3)]
        zero_position, rotation = foot_pose(chain, [0.0] * len(CHAIN))
        assert all(abs(zero_position[i] - hand[i]) < 1e-9 for i in range(3)), (leg, zero_position, hand)
        assert all(abs(rotation[i][j] - (1.0 if i == j else 0.0)) < 1e-12
                   for i in range(3) for j in range(3)), (leg, rotation)
        # Quarter turn on the hip: the pad rotates about the hip's own origin, and about its axis.
        pivot = chain[0]["origin"]
        turned = [pivot[i] + sum(_rotation_about(chain[0]["axis"], math.pi / 2)[i][j]
                                 * (hand[j] - pivot[j]) for j in range(3)) for i in range(3)]
        turned_position, _ = foot_pose(chain, [math.pi / 2, 0.0, 0.0, 0.0, 0.0])
        assert all(abs(turned_position[i] - turned[i]) < 1e-9 for i in range(3)), (leg, turned_position, turned)
        limits = " ".join("%s[%+.2f,%+.2f]" % (joint["name"].split("_")[-2], *joint["limits"])
                          for joint in chain)
        normal = pad_normal_in_link(urdf, leg)
        tilt = math.degrees(math.acos(-normal[2] / math.sqrt(sum(v * v for v in normal))))
        print("  %s zero-pose pad origin %s  quarter-turn %s  limits %s"
              % (leg, ["%+.6f" % v for v in zero_position], ["%+.6f" % v for v in turned_position], limits))
        print("      pad normal %s -> %.2f deg off the link's -z" % (["%+.4f" % v for v in normal], tilt))
    print("[SELF-CHECK] zero pose equals the origin sum, and a quarter hip turn rotates about the hip axis")


def _rotation_about(axis, angle: float):
    matrix = _matrix([0.0, 0.0, 0.0], axis, angle)
    return [[matrix[i][j] for j in range(3)] for i in range(3)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urdf", type=pathlib.Path, default=DEFAULT_URDF)
    parser.add_argument("--self-check", action="store_true",
                        help="hand-computed poses; no simulator, no sweep")
    parser.add_argument("--pose", nargs=5, type=float, metavar=("HIP", "HAA", "HFE", "KFE", "FOOT"),
                        help="print one leg's pad pose at these joint angles [rad]")
    parser.add_argument("--leg", default="lf", choices=LEGS)
    args = parser.parse_args()
    if args.self_check:
        self_check(args.urdf)
        return
    if args.pose is None:
        parser.error("nothing to do: pass --self-check or --pose")
    chain = load_chain(args.urdf, args.leg)
    position, rotation = foot_pose(chain, args.pose)
    for i, row in enumerate(rotation):
        print("  row %d %s" % (i, ["%+.5f" % v for v in row]))
    print("  pad origin in base_link %s" % ["%+.6f" % v for v in position])


if __name__ == "__main__":
    main()
