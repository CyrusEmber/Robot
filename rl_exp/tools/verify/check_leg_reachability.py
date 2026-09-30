# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Offline forward kinematics of lizard2's leg chain, read from the URDF (no simulator, no torch).

Why this exists: the open question is whether the leg can pose a **level pad** inside its own joint
limits -- while standing at body height, and while sweeping through a stance of the required length.
That is a kinematics feasibility question, and it does not need a rollout. What it does need is an
FK whose numbers are the simulator's, which is what the caliber check below is for.

Two properties of this chain are asserted here rather than argued in prose, because both were read
wrong from the numbers alone, and both decide what "a level pad" can even mean:

* **the pad's tilt is its fold sum's**: the three hinges share one axis, so the tilt is a function of
  ``haa + hfe + kfe`` and the blade angle alone (:func:`fold_tilt`) -- the hip angle drops out, how the
  sum is split does not matter, and no blade stroke can cancel the part of the fold that lies along the
  hinge axis (measured: 1-3 deg of travel against a 30-50 deg fold);
* **the knee's straight pose is not at zero**: ``hfe`` makes thigh and shank collinear at +-55.15 deg,
  while the asset's range is a symmetric +-1.2 rad (:data:`KNEE_FACTS`), so every leg carries 13.6 deg
  of knee hyperextension -- the limit was carried over when ``hfe``'s axis changed from ``Z`` to ``-X``.

The chain, per leg, is a 5-revolute serial chain off ``base_link``
(``*_hip`` -> ``*_haa`` -> ``*_hfe`` -> ``*_kfe`` -> ``*_foot``); the URDF gives each joint's origin,
axis and position limits, so nothing here is transcribed from the asset by hand.

``--self-check`` compares the composed transform against two independently derived poses: at the zero
pose the foot origin must equal the sum of the chain's origins (valid there because every leg origin
carries ``rpy="0 0 0"``), and with the hip turned a quarter turn the foot must be that same point
rotated about the hip's own axis. Both are hand arithmetic, not a re-run of the same matrix product.

:func:`chain_frames` and :func:`pad_vertices` are the two things a display needs out of this module:
the frame each joint turns in (an axis drawn in ``base_link``) and the pad's own mesh.

Run it from the repo root -- the repo tree does not live inside the IsaacLab install. Standard library
only (``-m`` works from any cwd when the venv's ``rl_exp.pth`` points at the repo); ``--frames`` is the
one path that touches a record and therefore torch:

    cd /d <REPO>
    python rl_exp\\tools\\verify\\check_leg_reachability.py --self-check
    python rl_exp\\tools\\verify\\check_leg_reachability.py --frames <record>\\eval.frames.pt
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

#: The knee's own geometry, per leg: the ``hfe`` that makes thigh and shank collinear [deg, signed
#: about the joint's own axis], the hyperextension the +-1.2 rad limit leaves beyond it [deg], and the
#: thigh-shank angle at the FOLDED end of the range [deg]. Four entries rather than one because the
#: four chains are not exact mirrors of one another (the front pair mirrors to ~4 mdeg, and the rear
#: pair is not the right legs' mirror at all). ``hfe``'s axis moved from ``Z`` to ``-X`` in
#: ``rl_exp/blender/generate_urdf.py`` while its +-1.2 limit was carried over, so the number never had
#: a knee's geometry behind it: every leg's range contains 13.6 deg of knee hyperextension.
KNEE_FACTS = {
    "rr": (55.146871, 13.608064, 123.901807),
    "rf": (55.148202, 13.606733, 123.903137),
    "lf": (-55.146496, 13.608439, 123.901431),
    "rl": (-55.149688, 13.605247, 123.904623),
}


def _floats(text: str, count: int) -> list[float]:
    values = [float(token) for token in (text or "").split()]
    if len(values) != count:
        raise ValueError(f"expected {count} numbers, got {text!r}")
    return values


def _unit(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector]


def _cross(a: list[float], b: list[float]) -> list[float]:
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


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
    """The leg's five joints as ``(origin xyz, axis, limits)``, in chain order, read off the URDF.

    A joint origin carrying a non-zero ``rpy`` is refused rather than dropped: this FK composes
    rotations from the axes alone, so an asset that rotated a joint frame would be read silently
    wrong (every leg joint in the current asset has ``rpy="0 0 0"``, which the self-check leans on).
    """
    root = ET.parse(urdf).getroot()
    by_name = {joint.get("name"): joint for joint in root.iter("joint")}
    chain = []
    for token in CHAIN:
        name = f"{leg}_{token}_joint"
        joint = by_name.get(name)
        if joint is None:
            raise SystemExit(f"{urdf} has no joint {name}")
        origin_tag = joint.find("origin")
        origin = _floats(origin_tag.get("xyz"), 3) if origin_tag is not None else [0.0] * 3
        rpy = origin_tag.get("rpy") if origin_tag is not None else None
        if any(value != 0.0 for value in _floats(rpy or "0 0 0", 3)):
            raise SystemExit(f"{name} carries rpy={rpy!r}: this FK turns joints about their axes "
                             f"only, so a rotated joint origin would be read as the identity")
        axis = _floats(joint.find("axis").get("xyz"), 3)
        limit = joint.find("limit")
        bounds = (float(limit.get("lower")), float(limit.get("upper")))
        chain.append({"name": name, "origin": origin, "axis": axis, "limits": bounds})
    return chain


def chain_frames(chain: list[dict], angles: list[float]):
    """Every frame up the chain: ``[base_link, after joint 0, ..., after the last joint]``.

    Element ``k`` is the frame joint ``k`` turns in, so ``frames[k]`` is what an axis has to be
    composed with to be drawn in ``base_link`` -- the URDF states an axis in its own joint frame.
    """
    transform = [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]
    frames = [transform]
    for joint, angle in zip(chain, angles):
        transform = _multiply(transform, _matrix(joint["origin"], joint["axis"], angle))
        frames.append(transform)
    return frames


def foot_pose(chain: list[dict], angles: list[float]):
    """The pad link's pose in ``base_link``: ``(position, 3x3 rotation)`` for the given joint angles."""
    transform = chain_frames(chain, angles)[-1]
    position = [transform[i][3] for i in range(3)]
    rotation = [[transform[i][j] for j in range(3)] for i in range(3)]
    return position, rotation


def _pad_mesh(leg: str) -> pathlib.Path:
    """The pad's collision mesh, from the family's own mesh tree."""
    candidates = sorted((_REPO / "rl_exp" / "versions" / "lizard2" / "meshes" / "collision").glob(
        f"{leg}_foot_collision.obj"))
    if not candidates:
        raise SystemExit(f"no collision mesh for {leg}'s pad")
    return candidates[0]


def _obj_lines(leg: str) -> list[str]:
    return _pad_mesh(leg).read_text(encoding="utf-8", errors="replace").splitlines()


def pad_vertices(leg: str) -> list[list[float]]:
    """The pad's mesh vertices in the foot link's frame, read from the exported ``.obj``."""
    return [[float(token) for token in line.split()[1:4]] for line in _obj_lines(leg)
            if line.startswith("v ")]


def pad_faces(leg: str) -> list[list[int]]:
    """The pad mesh's triangles, as 0-based indices into :func:`pad_vertices`.

    The asset is triangulated: 26 vertices and 48 faces satisfy ``V - E + F = 2`` with ``3F = 2E``,
    so a face is always three indices and there is nothing to fan here.
    """
    faces = []
    for line in _obj_lines(leg):
        if line.startswith("f "):
            tokens = line.split()[1:]
            if len(tokens) != 3:
                raise SystemExit(f"{_pad_mesh(leg).name} has a {len(tokens)}-gon face: not triangulated")
            faces.append([int(token.split("/")[0]) - 1 for token in tokens])
    return faces


def pad_normal_in_link(urdf: pathlib.Path, leg: str) -> list[float]:
    """The pad's own normal in the foot link's frame, fitted to the collision mesh's lowest band.

    Read from the exported ``.obj`` rather than assumed: the sole is a curved cap, and how far its
    contact patch is from the link's ``-z`` is a property of the asset, not of this script.
    """
    vertices = pad_vertices(leg)
    lowest = min(vertex[2] for vertex in vertices)
    band = [vertex for vertex in vertices if vertex[2] <= lowest + 0.002]
    centroid = [sum(vertex[i] for vertex in band) / len(band) for i in range(3)]
    # The plane through the contact band: its normal is the direction the band spans least in.
    cov = [[sum((vertex[i] - centroid[i]) * (vertex[j] - centroid[j]) for vertex in band) / len(band)
            for j in range(3)] for i in range(3)]
    normal = _smallest_eigenvector(cov)
    return normal if normal[2] < 0 else [-value for value in normal]


def pad_state(chain: list[dict], angles: list[float], normal: list[float],
              vertices: list[list[float]], base_z: float) -> dict:
    """One leg's pad read out for a given pose: where it is, how tilted, and how far off the ground.

    A fixed, level body is assumed throughout: with no roll or pitch on ``base_link``, the body
    frame's ``-z`` *is* the world's down, so the tilt is ``angle(normal, -z)`` and the ground is the
    plane ``z = -base_z``. That is the one assumption this file cannot check.

    Args:
        chain: as :func:`load_chain` returns it.
        angles: five joint angles [rad].
        normal: unit pad normal in the foot link's frame -- :func:`pad_normal_in_link`.
        vertices: pad mesh vertices in the foot link's frame -- :func:`pad_vertices`.
        base_z: the body's height above the ground [m].

    Returns:
        ``frames`` (as :func:`chain_frames`), the pad origin and pad normal in ``base_link``,
        ``tilt_deg`` off the world down, and ``lowest_z`` -- the lowest pad vertex above the ground
        [m], negative when the pad is through it.
    """
    frames = chain_frames(chain, angles)
    rotation = [[frames[-1][i][j] for j in range(3)] for i in range(3)]
    position = [frames[-1][i][3] for i in range(3)]
    body_normal = [sum(rotation[i][k] * normal[k] for k in range(3)) for i in range(3)]
    tilt = math.degrees(math.acos(max(-1.0, min(1.0, -body_normal[2]))))
    lowest = min(base_z + position[2] + sum(rotation[2][k] * vertex[k] for k in range(3))
                 for vertex in vertices)
    return {"frames": frames, "position": position, "normal": body_normal,
            "tilt_deg": tilt, "lowest_z": lowest}


def joint_effect(chain: list[dict], angles: list[float], index: int, normal: list[float],
                 vertices: list[list[float]], eps: float = 1e-5):
    """How joint ``index`` moves the pad, per radian, at these angles.

    Returns ``(dp/dq, dn/dq, axis, d_tilt/dq)`` with ``axis`` in ``base_link`` and the tilt
    derivative in deg/rad. ``dn/dq`` is a rotation axis of length ``dtheta/dq``: its direction is the
    axis the pad turns about and its magnitude the angle per radian of joint travel. That separates
    "which way does this joint spin the pad" from "how far does the pad move" -- reading only the
    second is how a vertical-axis joint gets mistaken for one that could level a pad.

    ``base_z`` does not enter either derivative (a derivative of a translation cannot depend on it),
    so :func:`pad_state` is asked with ``0.0``.
    """
    plus, minus = list(angles), list(angles)
    plus[index] += eps
    minus[index] -= eps
    high = pad_state(chain, plus, normal, vertices, 0.0)
    low = pad_state(chain, minus, normal, vertices, 0.0)
    dp = [(high["position"][i] - low["position"][i]) / (2 * eps) for i in range(3)]
    dn = [(high["normal"][i] - low["normal"][i]) / (2 * eps) for i in range(3)]
    d_tilt = (high["tilt_deg"] - low["tilt_deg"]) / (2 * eps)
    rotation = high["frames"][index]
    axis = [sum(rotation[i][k] * _unit(chain[index]["axis"])[k] for k in range(3)) for i in range(3)]
    return dp, dn, axis, d_tilt


def fold_tilt_cos(normal: list[float], sigma: float, foot: float) -> float:
    """The pad normal's z-component in a level body frame, read so that 1 = flat:

        cos(tilt) = ny sin(sigma) + (nx sin(foot) - nz cos(foot)) cos(sigma)

    The well-conditioned form of :func:`fold_tilt`, and the one to check against a measured tilt: an
    angle near 0 has no resolution through ``acos`` (a float64 cosine at 1 - 1e-16 returns ~1e-8 rad),
    so comparing angles would measure the rounding instead of the identity. Valid for this asset's axis
    directions -- the three hinges along ``-x`` and the blade along ``+y`` -- which the self-check
    asserts, because a sign in either would silently flip a term here.
    """
    nx, ny, nz = _unit(normal)
    return (ny * math.sin(sigma)
            + (nx * math.sin(foot) - nz * math.cos(foot)) * math.cos(sigma))


def fold_tilt(normal: list[float], sigma: float, foot: float) -> float:
    """The pad's tilt [deg] off a level body's down, from the fold sum alone.

    ``haa``, ``hfe`` and ``kfe`` all turn about the same axis, so the pad link's attitude in
    ``base_link`` is ``Rz(hip) Rx(sigma) Ry(foot)`` with ``sigma`` their SUM: the hip drops out of the
    tilt (a z rotation leaves the normal's z alone) and how the sum is split does not matter. For a
    level body the tilt is therefore a function of ``(sigma, foot)`` and the pad's own normal
    (:func:`fold_tilt_cos`) -- exact, and it says nothing about a pad that has to be level to the WORLD
    while the body carries roll and pitch, which is what an eval frame cannot show.
    """
    return math.degrees(math.acos(max(-1.0, min(1.0, abs(fold_tilt_cos(normal, sigma, foot))))))


def straight_hfe(chain: list[dict]) -> float:
    """The ``hfe`` angle [rad] that makes thigh and shank collinear, signed about the joint's axis.

    The thigh and shank are the two segments the chain's third and fourth origins span, so this is
    where the knee IS straight. The asset states the knee's range as a symmetric +-1.2 rad around a
    neutral pose that is already bent by this much, which is why the limit has to be compared with
    this angle rather than with zero.
    """
    thigh, shank, axis = _unit(chain[2]["origin"]), _unit(chain[3]["origin"]), _unit(chain[2]["axis"])
    return math.atan2(sum(_cross(shank, thigh)[i] * axis[i] for i in range(3)),
                      sum(shank[i] * thigh[i] for i in range(3)))


def thigh_shank_angle(chain: list[dict], angles: list[float]) -> float:
    """Angle [deg] between the thigh and shank segments: 0 = collinear, 180 = folded onto the thigh."""
    frames = chain_frames(chain, angles)
    thigh = [sum(frames[2][i][j] * chain[2]["origin"][j] for j in range(3)) for i in range(3)]
    shank = [sum(frames[3][i][j] * chain[3]["origin"][j] for j in range(3)) for i in range(3)]
    norm = math.sqrt(sum(v * v for v in thigh)) * math.sqrt(sum(v * v for v in shank))
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(thigh[i] * shank[i] for i in range(3)) / norm))))


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
    """Poses whose answers are hand arithmetic, not a second pass of the same matrix product."""
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
        # The readouts, against hand facts too: a vertical hip axis cannot change how far the pad
        # normal leans off the world's down (a rotation about z leaves the normal's z alone), and
        # raising the body by h must raise every pad vertex by exactly h.
        normal = pad_normal_in_link(urdf, leg)
        vertices = pad_vertices(leg)
        zero_angles = [0.0] * len(CHAIN)
        zero = pad_state(chain, zero_angles, normal, vertices, 0.9)
        turned_tilt = pad_state(chain, [0.4, 0.0, 0.0, 0.0, 0.0], normal, vertices, 0.9)["tilt_deg"]
        assert abs(turned_tilt - zero["tilt_deg"]) < 1e-9, (leg, turned_tilt, zero["tilt_deg"])
        above = pad_state(chain, zero_angles, normal, vertices, 0.95)["lowest_z"]
        assert abs((above - zero["lowest_z"]) - 0.05) < 1e-12, (leg, above, zero["lowest_z"])
        # A joint's dp/dq is its axis crossed with the lever arm: |dp/dq| is the perpendicular
        # distance from that axis to the pad origin, which is hand arithmetic from the origin sum.
        hip_axis = _unit(chain[0]["axis"])
        offset = [zero["position"][i] - pivot[i] for i in range(3)]
        along = sum(offset[i] * hip_axis[i] for i in range(3))
        lever = math.sqrt(sum((offset[i] - along * hip_axis[i]) ** 2 for i in range(3)))
        dp, _, _, hip_tilt_rate = joint_effect(chain, zero_angles, 0, normal, vertices)
        assert abs(math.sqrt(sum(value * value for value in dp)) - lever) < 1e-5, (leg, dp, lever)
        assert abs(hip_tilt_rate) < 1e-9, (leg, hip_tilt_rate)
        # The pad joint spins the pad normal about its own axis: |dn/dq| = |axis x normal|.
        dp, dn, axis, _ = joint_effect(chain, zero_angles, len(CHAIN) - 1, normal, vertices)
        assert abs(math.sqrt(sum(value * value for value in dn))
                   - math.sqrt(sum(value * value for value in _cross(axis, normal)))) < 1e-6, (leg, dn, axis)
        # The pad's tilt is its FOLD SUM's, and the hip is not in it: the three hinges share one axis,
        # so redistributing the same sum must change the tilt by nothing, and so must the hip angle.
        assert chain[1]["axis"] == chain[2]["axis"] == chain[3]["axis"], (leg, "hinges not parallel")
        assert chain[1]["axis"] == [-1.0, 0.0, 0.0] and chain[4]["axis"] == [0.0, 1.0, 0.0], \
            (leg, "the closed form is written for the asset's own hinge and blade directions")
        # The motion plane can be yawed but never tilted: with the hip as the body's z, `haa`'s axis in
        # the body frame is the zero-pose hinge turned about that z, so its z component stays zero over
        # the whole hip range and the plane the three parallel hinges span always contains the body's z.
        # The premise is asserted above (a level-hip turn leaves the tilt alone) and to the left (the
        # hinges are parallel and `haa` is a literal -X); what this adds is the literal on the hip's own
        # axis plus the regression across the range, endpoints included because a limit is where a
        # rebuild would drift first. A break test (hip axis perturbed to `0 0.3 1`) fails, but at the
        # level-hip-tilt assertion rather than here -- this one is the backstop, not the first guard.
        assert chain[0]["axis"] == [0.0, 0.0, 1.0], (leg, chain[0]["axis"], "hip is not the body's z")
        hinge = _unit(chain[1]["axis"])
        low, high = chain[0]["limits"]
        for hip in (low, low / 2.0, 0.0, high / 2.0, high):
            axis_at = joint_effect(chain, [hip, 0.0, 0.0, 0.0, 0.0], 1, normal, vertices)[2]
            turned = _rotation_about([0.0, 0.0, 1.0], hip)
            expected = [sum(turned[i][k] * hinge[k] for k in range(3)) for i in range(3)]
            assert abs(axis_at[2]) < 1e-12, (leg, hip, axis_at, "the motion plane tilted")
            assert all(abs(axis_at[i] - expected[i]) < 1e-9 for i in range(3)), \
                (leg, hip, axis_at, expected)
        for sigma in (-0.9, -0.35, 0.0, 0.31, 0.62):
            for foot in (-0.5, -0.2, 0.0, 0.17, 0.5):
                spread = pad_state(chain, [0.11, sigma, 0.0, 0.0, foot], normal, vertices, 0.9)
                other = pad_state(chain, [0.11, sigma / 3.0, sigma / 3.0, sigma / 3.0, foot],
                                  normal, vertices, 0.9)
                turned = pad_state(chain, [-0.4, sigma, 0.0, 0.0, foot], normal, vertices, 0.9)
                assert abs(spread["tilt_deg"] - other["tilt_deg"]) < 1e-9, (leg, sigma, foot)
                assert abs(spread["tilt_deg"] - turned["tilt_deg"]) < 1e-9, (leg, sigma, foot)
                assert abs(fold_tilt_cos(normal, sigma, foot) - (-spread["normal"][2])) < 1e-12, \
                    (leg, sigma, foot)
        # The blade cannot buy the tilt back: with the legs folded by 0.62 rad its whole +-0.5 rad
        # stroke leaves >= 30 deg, which is the reading ("1-3 deg of travel against a 30-50 deg fold").
        stroke = min(pad_state(chain, [0.0, 0.62, 0.0, 0.0, -0.5 + i * 0.01], normal, vertices,
                               0.9)["tilt_deg"] for i in range(101))
        assert stroke > 30.0, (leg, stroke)
        # The knee's straight pose, against the pinned per-leg facts: the limit over-runs it, and the
        # other end of the range is a fold. A regeneration that moves an origin must trip these.
        straight = math.degrees(straight_hfe(chain))
        pinned, margin, folded = KNEE_FACTS[leg]
        assert abs(straight - pinned) < 1e-3, (leg, straight, pinned)
        low, high = chain[2]["limits"]
        fold_limit, over_limit = (low, high) if straight > 0 else (high, low)
        over_run = math.degrees(abs(over_limit)) - abs(straight)
        assert abs(over_run - margin) < 1e-3, (leg, over_run, margin)
        assert abs(thigh_shank_angle(chain, [0.0, 0.0, fold_limit, 0.0, 0.0]) - folded) < 1e-3, leg
        limits = " ".join("%s[%+.2f,%+.2f]" % (joint["name"].split("_")[-2], *joint["limits"])
                          for joint in chain)
        tilt = math.degrees(math.acos(-normal[2] / math.sqrt(sum(v * v for v in normal))))
        print("  %s zero-pose pad origin %s  quarter-turn %s  limits %s"
              % (leg, ["%+.6f" % v for v in zero_position], ["%+.6f" % v for v in turned_position], limits))
        print("      pad normal %s -> %.2f deg off the link's -z  tilt %.2f deg  lowest %+.4f m  "
              "hip lever %.4f m"
              % (["%+.4f" % v for v in normal], tilt, zero["tilt_deg"], zero["lowest_z"], lever))
        print("      knee: straight at %+.4f deg, the +-1.2 rad limit over-runs it by %.4f deg, "
              "folded end %.2f deg" % (straight, over_run, folded))
    print("[SELF-CHECK] zero pose equals the origin sum, a quarter hip turn rotates about the hip "
          "axis, the hip leaves the tilt alone, a body-height shift moves the pad with it, each "
          "joint's dp/dq equals its own lever arm, the tilt is the fold sum's alone (a blade stroke "
          "worth 1-3 deg against a 30-50 deg fold), the motion plane never tilts (haa's axis stays "
          "turned about the body's z over the hip's whole range), and the knee's straight pose is "
          "not at zero")


def fold_reading(path: pathlib.Path, urdf: pathlib.Path, contact_n: float = 1.0) -> None:
    """Per leg and command band: the fold sum while the pad carries load, beside the blade's own angle.

    The quantity the pad question needs is ``|SIGMA|`` on the loaded frames -- the part of the tilt no
    blade stroke can cancel (:func:`fold_tilt`) -- read against the blade's own travel. ``tilt@fold`` is
    the identity's prediction at the band's median fold sum with the blade at zero, i.e. at the blade's
    own optimum here (these legs' mesh normals are offset in y, so the blade's angle can only make the
    tilt worse). It is read with each leg's own fitted normal, and it assumes a LEVEL body -- the one
    boundary this reading cannot close: format 3 deliberately carries no attitude column
    (``ablation_harness/baseline_frames.py``), so a pad that is level to the WORLD while the body
    carries roll and pitch sits flatter in a record than the prediction says.

    Run it on a ``baseline-frames-3`` record (``.../eval.frames.pt``). Older formats have no joint
    column and are refused rather than read as if the joints were missing.
    """
    import torch  # the one torch-touching path in this file: reading a record is not geometry

    artifact = torch.load(path, map_location="cpu", weights_only=False)
    if artifact.get("format") != "baseline-frames-3":
        raise SystemExit(f"{path}: format {artifact.get('format')!r} carries no joint column")
    index = {name: i for i, name in enumerate(artifact["axes"]["joint_pos"])}
    joints = artifact["frames"]["joint_pos"]
    load = artifact["frames"]["foot_fraction"] * float(artifact["meta"]["body_weight_n"])
    speed = artifact["frames"]["command_world"][..., 0].abs()
    legs = [name[: -len("_foot")] for name in artifact["axes"]["foot_contact"]]
    print("%s: %d steps x %d envs, loaded = >%s N"
          % (path.name, joints.shape[0], joints.shape[1], contact_n))
    print("%-5s %-3s %8s %16s %14s %10s"
          % ("band", "leg", "frames", "|SIGMA| p50/p95", "blade p50/p95", "tilt@fold"))
    for band, low, high in (("slow", 0.1, 1.0), ("mid", 1.0, 2.0), ("fast", 2.0, 3.0)):
        mask = (speed > low) & (speed <= high)
        for k, leg in enumerate(legs):
            loaded = (load[..., k] > contact_n) & mask
            sigma = (joints[..., index[f"{leg}_haa_joint"]] + joints[..., index[f"{leg}_hfe_joint"]]
                     + joints[..., index[f"{leg}_kfe_joint"]])[loaded]
            blade = joints[..., index[f"{leg}_foot_joint"]][loaded]
            if sigma.numel() == 0:
                print("%-5s %-3s %8d" % (band, leg, 0))
                continue
            predicted = fold_tilt(pad_normal_in_link(urdf, leg), float(sigma.median()), 0.0)
            print("%-5s %-3s %8d %7.1f/%6.1f %7.1f/%6.1f %10.1f"
                  % (band, leg, int(sigma.numel()),
                     math.degrees(float(sigma.abs().median())),
                     math.degrees(float(sigma.abs().quantile(0.95))),
                     math.degrees(float(blade.median())),
                     math.degrees(float(blade.quantile(0.95))), predicted))


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
    parser.add_argument("--frames", type=pathlib.Path, default=None,
                        help="a baseline-frames-3 record: print the fold sum on its loaded frames")
    parser.add_argument("--contact_n", type=float, default=1.0,
                        help="per-foot normal force above which the pad is called loaded [N]")
    args = parser.parse_args()
    if args.self_check:
        self_check(args.urdf)
        return
    if args.frames is not None:
        fold_reading(args.frames, args.urdf, args.contact_n)
        return
    if args.pose is None:
        parser.error("nothing to do: pass --self-check, --frames or --pose")
    chain = load_chain(args.urdf, args.leg)
    position, rotation = foot_pose(chain, args.pose)
    for i, row in enumerate(rotation):
        print("  row %d %s" % (i, ["%+.5f" % v for v in row]))
    print("  pad origin in base_link %s" % ["%+.6f" % v for v in position])


if __name__ == "__main__":
    main()
