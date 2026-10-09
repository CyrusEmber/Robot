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
* **the knee's straight pose is not at zero**: ``hfe`` makes thigh and shank collinear at +-75.00 deg,
  while the asset's range is a symmetric +-1.2 rad (:data:`KNEE_FACTS`), so the range stops 6.245 deg
  SHORT of straight -- reverse bending is unreachable and the knee cannot fully straighten either.
  The sign of that margin is the requirement (the user's 2026-10-09 decision: the limit must not
  allow reverse bending); the first body carried +13.6 deg of it the other way, because ``hfe``'s
  axis changed from ``Z`` to ``-X`` in ``rl_exp/blender/generate_urdf.py`` while its +-1.2 limit was
  carried over.

A third reading is separated here because it is what "a level pad" is actually asked for:

* **flat is not the same as facing down**: the fold identity reads the pad normal's z-component and
  :func:`fold_tilt` returns the same 0 for a pad lying on its sole and one lying on its back. The
  direction is a separate read (:func:`faces_down` on ``facing_cos``), and the review's counterexample
  -- inside the limits -- is refused by it.

The pad's facing and the pad's height are read in the WORLD frame: ``base_link`` may carry roll and
pitch, so :func:`pad_state` takes the body's own attitude instead of assuming a level body (the body
frame's ``-z`` is the world's down only when it is level).

Which body a reading belongs to is not guessed either. The pad's collision mesh is resolved from the
URDF's own ``<leg>_foot`` link -- the convention ``check_joint_layout.py`` already uses -- so a
candidate URDF cannot be scored against the old body's mesh, and a URDF carried away from its meshes
fails instead of borrowing one. The chain itself is walked off the URDF's tree (:func:`load_chain`), so
a candidate that INSERTED a joint is read with that joint rather than as the old chain with it silently
missing; joints carry their own ``rpy``, so an inserted joint may sit on a rotated frame; and
``--compare`` reads two candidates at the same body pose, height and tolerance, reporting a joint only
one of them has on its own rather than folding it into the shared numbers.

The chain, per leg, is a 5-revolute serial chain off ``base_link``
(``*_hip`` -> ``*_haa`` -> ``*_hfe`` -> ``*_kfe`` -> ``*_foot``); the URDF gives each joint's origin,
axis and position limits, so nothing here is transcribed from the asset by hand.

``--self-check`` compares the composed transform against two independently derived poses: at the zero
pose the foot origin must equal the sum of the chain's origins (valid there because every leg origin
carries ``rpy="0 0 0"``), and with the hip turned a quarter turn the foot must be that same point
rotated about the hip's own axis. Both are hand arithmetic, not a re-run of the same matrix product.
``--break-test`` perturbs the readings those verdicts rest on and fails if the self-check stays green.

:func:`chain_frames` and :func:`pad_vertices` are the two things a display needs out of this module:
the frame each joint turns in (an axis drawn in ``base_link``) and the pad's own mesh.

Run it from the repo root -- the repo tree does not live inside the IsaacLab install. Standard library
only (``-m`` works from any cwd when the venv's ``rl_exp.pth`` points at the repo); ``--frames`` is the
one path that touches a record and therefore torch:

    cd /d <REPO>
    python rl_exp\\tools\\verify\\check_leg_reachability.py --self-check
    python rl_exp\\tools\\verify\\check_leg_reachability.py --break-test
    python rl_exp\\tools\\verify\\check_leg_reachability.py --frames <record>\\eval.frames.pt
    python rl_exp\\tools\\verify\\check_leg_reachability.py --compare <candidate>.urdf --leg rl

``--urdf`` reads ANY body's geometry (``--pose`` / ``--compare`` / ``--frames``), but the pinned knee
facts are the ADOPTED body's, so ``--self-check`` is a reading of that body: pointing it at another
URDF is expected to trip the knee assertions rather than to pass on borrowed numbers.
"""

import argparse
import contextlib
import io
import itertools
import json
import math
import pathlib
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
# ONE answer to "which actuator group owns this joint" (the parity gate's), shared rather than
# re-implemented: the gain table below reads the same yaml block that gate asserts coverage over.
from check_dr_parity import _actuator_groups, _joint_owners  # noqa: E402

_REPO = pathlib.Path(__file__).resolve().parents[3]


def family_urdf(rl_exp: pathlib.Path, family: str) -> tuple[pathlib.Path, str]:
    """The URDF of the body ``family`` consumes, and where that choice came from (callers print it).

    Two layouts are live, so the rule tries the family's own asset declaration first and falls back to
    the pre-adoption one: a family that adopted a body inside its declared mesh tree (``lizard2`` ->
    ``lizard2_candidate/``) is read there, while a family whose tree is shared at the repo level
    (``lizard`` -> ``rl_exp/meshes``, its URDF beside the version directory) is read from
    ``versions/<family>/<family>.urdf``. The source string comes back rather than being logged here so
    that a reading of an old body can never be silent about which file it answered for (P011: a tool
    reported on the current body while reading the retired one, twice in one day).
    """
    declared = rl_exp / "versions" / family / "assets.json"
    meshes = rl_exp / json.loads(declared.read_text(encoding="utf-8"))["meshes_dir"]
    body = meshes.parent
    candidate = body / f"{body.name}.urdf"
    if candidate.exists():
        return candidate, f"declared asset tree ({declared.name}: {meshes.name})"
    return rl_exp / "versions" / family / f"{family}.urdf", "legacy layout versions/<family>/<family>.urdf"


#: The body the family consumes today, resolved from its own declaration (``versions/lizard2/assets.json``
#: names the candidate's mesh tree, and ``main_params.yaml`` spawns its USD): the default reading has to
#: be the adopted body, otherwise the pinned knee facts below would describe a body nothing runs. The
#: first body stays reachable through ``--urdf``.
DEFAULT_URDF = family_urdf(_REPO / "rl_exp", "lizard2")[0]
#: The five joints of a leg, root to pad. The blade is the last one: the pad is rigid to it.
CHAIN = ("hip", "haa", "hfe", "kfe", "foot")
#: The three hinges that share one axis. Their plane is what ``hip`` can yaw and nothing can tilt,
#: which is the structural claim :func:`hinge_vs_body_z` turns into a number.
HINGES = CHAIN[1:4]
LEGS = ("lf", "rf", "rl", "rr")

#: The knee's own geometry, per leg: the ``hfe`` that makes thigh and shank collinear [deg, signed
#: about the joint's own axis], the margin the +-1.2 rad limit leaves against that pose [deg, signed:
#: POSITIVE = the limit runs past straight, i.e. the knee can hyperextend; NEGATIVE = the range stops
#: short of straight], and the thigh-shank angle at the FOLDED end of the range [deg]. Four entries
#: rather than one because the four chains are not exact mirrors of one another.
#:
#: These are the ADOPTED body's numbers (``rl_exp/lizard2_candidate/lizard2_candidate.urdf``), where
#: the range stops 6.245 deg short of straight, so reverse bending is not reachable and the knee
#: cannot fully straighten either. The first body was the other way round -- collinear at +-55.1465
#: deg inside a +-1.2 rad range, i.e. 13.608 deg of hyperextension it inherited when ``hfe``'s axis
#: moved from ``Z`` to ``-X`` -- and the user's requirement (2026-10-09: the limit must not allow
#: reverse bending) is what makes this sign count. A regeneration that flips it back fails the
#: self-check below, which is the only guard this requirement has.
KNEE_FACTS = {
    "rr": (74.999968, -6.245033, 143.754903),
    "rf": (74.999965, -6.245030, 143.754901),
    "lf": (-74.999965, -6.245030, 143.754901),
    "rl": (-74.999968, -6.245033, 143.754903),
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


def _rpy_matrix(rpy) -> list[list[float]]:
    """The URDF's ``rpy`` as a rotation matrix: ``Rz(yaw) Ry(pitch) Rx(roll)``."""
    roll, pitch, yaw = rpy
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return [
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ]


def _matrix(origin, axis, angle: float, rpy=None) -> list[list[float]]:
    """One joint's transform: ``T(origin) . R(rpy) . R(axis, angle)``, the URDF's own order.

    The axis is stated in the joint's OWN frame, i.e. after ``rpy`` -- composing the axis before it is
    how an inserted joint on a rotated frame comes out silently wrong. Every joint that carries
    ``rpy="0 0 0"`` (the current asset's, all of them) takes the identical path it always did.
    """
    x, y, z = origin
    ax, ay, az = axis
    norm = math.sqrt(ax * ax + ay * ay + az * az)
    ax, ay, az = ax / norm, ay / norm, az / norm
    c, s = math.cos(angle), math.sin(angle)
    k = 1.0 - c
    rotation = [
        [ax * ax * k + c, ax * ay * k - az * s, ax * az * k + ay * s],
        [ay * ax * k + az * s, ay * ay * k + c, ay * az * k - ax * s],
        [az * ax * k - ay * s, az * ay * k + ax * s, az * az * k + c],
    ]
    if rpy is not None and any(value != 0.0 for value in rpy):
        turn = _rpy_matrix(rpy)
        rotation = [[sum(turn[i][k] * rotation[k][j] for k in range(3)) for j in range(3)]
                    for i in range(3)]
    return [
        [rotation[0][0], rotation[0][1], rotation[0][2], x],
        [rotation[1][0], rotation[1][1], rotation[1][2], y],
        [rotation[2][0], rotation[2][1], rotation[2][2], z],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _multiply(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def chain_joint_names(urdf: pathlib.Path, leg: str) -> tuple[str, ...]:
    """The leg's joints, root to pad, walked UP the URDF's own tree from ``<leg>_foot``.

    The tree is the authority on which joints a candidate has, so nobody has to hand it the list: a
    candidate that inserted a femoral rotation gets it read without this file naming it. The walk stops
    at the first parent link that does not carry the leg's own prefix (``lf_``), which is the family's
    naming convention and the only thing assumed here; a link with no parent joint or with two is
    refused rather than guessed at.
    """
    root = ET.parse(urdf).getroot()
    parent_of = {}
    for joint in root.iter("joint"):
        child = joint.find("child").get("link")
        if child in parent_of:
            raise SystemExit(f"{urdf}: link {child} has two parent joints")
        parent_of[child] = joint
    names, link = [], f"{leg}_foot"
    while link.startswith(f"{leg}_"):
        joint = parent_of.get(link)
        if joint is None:
            raise SystemExit(f"{urdf}: no joint leads into link {link}")
        names.append(joint.get("name"))
        link = joint.find("parent").get("link")
    if not names:
        raise SystemExit(f"{urdf}: {leg}_foot has no joint of its own")
    return tuple(reversed(names))


def load_chain(urdf: pathlib.Path, leg: str) -> list[dict]:
    """The leg's joints as ``(origin, rpy, axis, limits)``, root to pad, read off the URDF.

    Which joints those are comes off the tree (:func:`chain_joint_names`), so a candidate that INSERTED
    a joint is read with it instead of being read as the old chain with the extra joint silently
    missing. Each entry keeps its own ``rpy``, so an inserted joint may sit on a rotated frame -- the
    composition is the URDF's own (see :func:`_matrix`) -- and the URDF states an axis in its own joint
    frame, which is why the axis has to be read together with that frame's ``rpy``.
    """
    root = ET.parse(urdf).getroot()
    by_name = {joint.get("name"): joint for joint in root.iter("joint")}
    chain = []
    for name in chain_joint_names(urdf, leg):
        joint = by_name[name]
        origin_tag = joint.find("origin")
        origin = _floats(origin_tag.get("xyz"), 3) if origin_tag is not None else [0.0] * 3
        rpy = _floats(origin_tag.get("rpy") or "0 0 0", 3) if origin_tag is not None else [0.0] * 3
        axis = _floats(joint.find("axis").get("xyz"), 3)
        limit = joint.find("limit")
        bounds = (float(limit.get("lower")), float(limit.get("upper")))
        chain.append({"name": name, "token": name[len(leg) + 1: -len("_joint")], "origin": origin,
                      "rpy": rpy, "axis": axis, "limits": bounds})
    return chain


def chain_frames(chain: list[dict], angles: list[float]):
    """Every frame up the chain: ``[base_link, after joint 0, ..., after the last joint]``.

    Element ``k`` is the frame joint ``k`` turns in, so ``frames[k]`` is what an axis has to be
    composed with to be drawn in ``base_link`` -- the URDF states an axis in its own joint frame.
    """
    transform = [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]
    frames = [transform]
    for joint, angle in zip(chain, angles):
        transform = _multiply(transform, _matrix(joint["origin"], joint["axis"], angle,
                                                 joint.get("rpy")))
        frames.append(transform)
    return frames


def link_inertials(urdf: pathlib.Path) -> dict[str, dict]:
    """Each link's own mass properties, in the LINK's own frame: ``{link: {"mass", "com", "tensor"}}``.

    Read straight off ``<inertial>`` (``origin``/``mass``/``ixx``..``iyz``). A link with no ``<inertial>``
    gets zero mass -- the massless link, not a substituted one.
    """
    out = {}
    for link in ET.parse(urdf).getroot().iter("link"):
        inertial = link.find("inertial")
        if inertial is None:
            out[link.get("name")] = {"mass": 0.0, "com": [0.0, 0.0, 0.0],
                                     "tensor": [[0.0] * 3 for _ in range(3)]}
            continue
        origin = inertial.find("origin")
        com = _floats(origin.get("xyz"), 3) if origin is not None else [0.0] * 3
        block = inertial.find("inertia")
        ixx, iyy, izz, ixy, ixz, iyz = (float(block.get(key)) for key in
                                        ("ixx", "iyy", "izz", "ixy", "ixz", "iyz"))
        # The URDF states the inertia MATRIX, so these go in as written: ixy is the (0,1) entry, not a
        # product of inertia to be negated. Some CAD exporters write the products into these fields
        # instead -- a known divergence, and one this file cannot settle from the asset, because this
        # asset states ZERO off-diagonals on every link (its own generator, blender/generate_urdf.py:301,
        # writes 0). An asset with non-zero ones would have to be read against the engine's URDF
        # importer before this projection can be trusted for it.
        out[link.get("name")] = {
            "mass": float(inertial.find("mass").get("value")), "com": com,
            "tensor": [[ixx, ixy, ixz], [ixy, iyy, iyz], [ixz, iyz, izz]],
        }
    return out


def downstream_links(urdf: pathlib.Path, leg: str) -> dict[str, list[str]]:
    """Per leg joint, the links at or below its child link: ``{joint: [child, ...subtree]}`` root-first.

    Walked off the URDF's own tree. On this family the subtree is exactly the rest of the chain, and
    :func:`reflected_inertia` refuses anything else rather than inventing a frame for a link no chain
    transform covers.
    """
    root = ET.parse(urdf).getroot()
    children: dict[str, list] = {}
    for joint in root.iter("joint"):
        children.setdefault(joint.find("parent").get("link"), []).append(joint)
    by_name = {joint.get("name"): joint for joint in root.iter("joint")}

    def subtree(link: str) -> list[str]:
        out = [link]
        for joint in children.get(link, []):
            out += subtree(joint.find("child").get("link"))
        return out

    return {name: subtree(by_name[name].find("child").get("link"))
            for name in chain_joint_names(urdf, leg)}


def gain_table(rl_exp: pathlib.Path, family: str, joint_names: tuple[str, ...]) -> dict[str, dict]:
    """``{joint: {"group", "kp", "kd"}}`` from the recipe that CONSUMES this body, not from the body.

    The gains are not in the URDF, so they have to come from their one home: the line's ``actuators:``
    block, matched to joints by its own ``joint_patterns``. The group->joint mapping is imported from the
    parity gate instead of being re-implemented (one answer to "which group owns this joint"), and a
    joint no group claims -- or two claiming it -- is refused: a gain table invented here would be a
    second home for a number the recipe owns.
    """
    yaml_path = rl_exp / "versions" / family / "main" / "main_params.yaml"
    groups = _actuator_groups(yaml_path.read_text(encoding="utf-8"))
    if not groups:
        raise SystemExit(f"{yaml_path}: declares no actuators block, so there are no gains to read")
    owners = _joint_owners(groups, {name: {} for name in joint_names})
    table = {}
    for name, claims in owners.items():
        if len(claims) != 1:
            raise SystemExit(f"{yaml_path}: {name} is claimed by {claims or 'no group'} -- "
                             "expected exactly one actuator group")
        spec = groups[claims[0]]
        table[name] = {"group": claims[0], "kp": float(spec["stiffness"]), "kd": float(spec["damping"])}
    return table


def reflected_inertia(chain: list[dict], angles: list[float], inertials: dict[str, dict],
                      downstream: dict[str, list[str]], table: dict[str, dict]) -> list[dict]:
    """Per chain joint, the inertia its own axis sees at this pose, and what the gains make of it.

    The caliber, stated because an inertia number without one is not a reading:

    * the value is the DIAGONAL of the joint-space inertia at this configuration -- every link below the
      joint summed as ``m*|r_perp|^2 + u' I_L u``, i.e. composite-rigid-body with the downstream joints
      held at these same angles. Exact for the diagonal, and NOT the off-diagonal coupling;
    * the base is treated as FIXED. With a floating base the strict quantity is the base-eliminated
      ``M_ii``; the body is far heavier than one leg, but how far this approximation lands was **not**
      quantified here -- it is a named gap, not a correction;
    * no contact, no ground, no other leg, no spine: it is this chain alone, at ONE pose, and it moves
      with the pose;
    * ``w_n = sqrt(Kp/I)`` [rad/s] and ``zeta = Kd/(2*sqrt(Kp*I))`` are the LOCAL single-DOF pair. zeta is
      not a statement about the robot's stability: coupled joints, contacts and the spine live outside it;
    * the frequency columns are ratios only -- against the physics step (200 Hz) and the control period
      (50 Hz). The actuator's own bandwidth is not known here (no datasheet), so it gets no number.

    Returns ``[{joint, group, kp, kd, inertia, wn_rad_s, wn_hz, zeta, over_physics_rate,
    over_control_rate}]``; a joint whose downstream links are all massless refuses rather than dividing
    by zero.
    """
    frames = chain_frames(chain, angles)
    names = [joint["name"] for joint in chain]
    for index, joint in enumerate(chain):
        expected = [downstream[name][0] for name in names[index:]]
        if downstream[joint["name"]] != expected:
            raise SystemExit(f"{joint['name']}: its subtree is {downstream[joint['name']]} but the chain "
                             f"below it is {expected} -- this caliber only covers a leg that is one chain")
    frame_of = {downstream[name][0]: frames[index + 1][:] for index, name in enumerate(names)}
    rows = []
    for index, joint in enumerate(chain):
        # The joint's own frame is the CHILD link's frame (URDF states the axis in it), i.e. the frame
        # after this joint's origin/rpy -- frames[index], which is the parent frame the axis is stated
        # relative to, would put the axis one joint's origin away and still look plausible. The hand
        # case below is what caught exactly that.
        own = frames[index + 1]
        origin = [own[i][3] for i in range(3)]
        rotation = [[own[i][j] for j in range(3)] for i in range(3)]
        raw = [sum(rotation[i][k] * joint["axis"][k] for k in range(3)) for i in range(3)]
        axis = _unit(raw)
        inertia = 0.0
        for link in downstream[joint["name"]]:
            props = inertials.get(link)
            if props is None:
                raise SystemExit(f"{joint['name']}: link {link} is not in the URDF's link list")
            frame = frame_of.get(link)
            if frame is None:
                raise SystemExit(f"{joint['name']}: link {link} has no chain frame")
            point = [frame[i][3] + sum(frame[i][j] * props["com"][j] for j in range(3))
                     for i in range(3)]
            offset = [point[i] - origin[i] for i in range(3)]
            along = sum(offset[i] * axis[i] for i in range(3))
            perpendicular = math.sqrt(sum((offset[i] - along * axis[i]) ** 2 for i in range(3)))
            # u' (R I R') u, taken in the LINK's own frame: the axis expressed there is R' u, and the
            # tensor is stated there. Composing only R on the left (`u' R I u`) is not the same rotation
            # and can come out NEGATIVE on a light link -- which is how this was caught, and the case
            # below keeps it caught.
            local_axis = [sum(frame[k][i] * axis[k] for k in range(3)) for i in range(3)]
            along_tensor = sum(local_axis[i] * props["tensor"][i][j] * local_axis[j]
                               for i in range(3) for j in range(3))
            inertia += props["mass"] * perpendicular ** 2 + along_tensor
        gains = table[joint["name"]]
        if inertia <= 0.0:
            raise SystemExit(f"{joint['name']}: reflected inertia {inertia} -- the gains cannot be "
                             "scaled against a massless chain")
        wn = math.sqrt(gains["kp"] / inertia)
        rows.append({"joint": joint["name"], "group": gains["group"], "kp": gains["kp"], "kd": gains["kd"],
                     "inertia": inertia, "wn_rad_s": wn, "wn_hz": wn / (2 * math.pi),
                     "zeta": gains["kd"] / (2 * math.sqrt(gains["kp"] * inertia)),
                     "over_physics_rate": (wn / (2 * math.pi)) / 200.0,
                     "over_control_rate": (wn / (2 * math.pi)) / 50.0})
    return rows


def load_case_angles(chain: list[dict]) -> dict[str, list[float]]:
    """The poses the inertia is read at: each joint driven to its OWN declared limits, one at a time.

    Nothing here is invented -- every angle below is a limit the URDF states, with the other joints left
    at zero. The caveat a single-pose reading carries ("it moves with the pose") is only a number once
    the poses are named, and these are the ones the mechanism itself declares. The knee's straight pose
    is deliberately NOT a case: it sits outside this range (that is what keeps reverse bending
    unreachable), so posing there would be a configuration the leg cannot be in.
    """
    cases = {"zero": [0.0] * len(chain)}
    for index, joint in enumerate(chain):
        low, high = joint["limits"]
        for label, angle in (("lo", low), ("hi", high)):
            angles = [0.0] * len(chain)
            angles[index] = angle
            cases[f"{joint['token']}-{label}"] = angles
    return cases


def inertia_range(chain: list[dict], cases: dict[str, list[float]], inertials: dict[str, dict],
                  downstream: dict[str, list[str]], table: dict[str, dict]) -> list[dict]:
    """Per joint, the reflected inertia's spread over the load cases, and which case gives each end.

    Reports ``{joint, group, i_min, i_min_case, i_max, i_max_case, wn_min_hz, wn_max_hz, i_ratio}``.
    The gain's frequency pairs follow from the inertia because ``w_n = sqrt(Kp/I)`` is monotone in it:
    the smallest inertia is the HIGHEST ``w_n``, so the ends swap between the two columns.
    """
    per_case = {name: reflected_inertia(chain, angles, inertials, downstream, table)
                for name, angles in cases.items()}
    rows = []
    for index, joint in enumerate(chain):
        readings = [(name, moments[index]["inertia"]) for name, moments in per_case.items()]
        low_case, low = min(readings, key=lambda pair: pair[1])
        high_case, high = max(readings, key=lambda pair: pair[1])
        gains = table[joint["name"]]
        rows.append({"joint": joint["name"], "group": gains["group"], "i_min": low, "i_min_case": low_case,
                     "i_max": high, "i_max_case": high_case,
                     "wn_min_hz": math.sqrt(gains["kp"] / high) / (2 * math.pi),
                     "wn_max_hz": math.sqrt(gains["kp"] / low) / (2 * math.pi),
                     "i_ratio": high / low if low else float("inf")})
    return rows


def foot_pose(chain: list[dict], angles: list[float]):
    """The pad link's pose in ``base_link``: ``(position, 3x3 rotation)`` for the given joint angles."""
    transform = chain_frames(chain, angles)[-1]
    position = [transform[i][3] for i in range(3)]
    rotation = [[transform[i][j] for j in range(3)] for i in range(3)]
    return position, rotation


def pad_mesh(urdf: pathlib.Path, leg: str) -> pathlib.Path:
    """The pad's collision mesh, from the URDF's OWN ``<leg>_foot`` link.

    Resolved off the URDF rather than a fixed directory (``check_joint_layout.py`` reads the same
    node), because the mesh and the chain have to belong to the SAME body: scored against the old
    body's mesh, a candidate URDF reads a pad it does not have.
    """
    root = ET.parse(urdf).getroot()
    link_name = f"{leg}_foot"
    link = next((item for item in root.findall("link") if item.get("name") == link_name), None)
    if link is None:
        raise SystemExit(f"{urdf} has no link {link_name}")
    mesh = link.find("collision/geometry/mesh")
    if mesh is None:
        raise SystemExit(f"{urdf}: {link_name} declares no collision mesh")
    path = (urdf.parent / mesh.get("filename")).resolve()
    if not path.is_file():
        raise SystemExit(f"{urdf}: {link_name}'s collision mesh {path} is missing")
    return path


def _obj_lines(urdf: pathlib.Path, leg: str) -> list[str]:
    return pad_mesh(urdf, leg).read_text(encoding="utf-8", errors="replace").splitlines()


def pad_vertices(urdf: pathlib.Path, leg: str) -> list[list[float]]:
    """The pad's mesh vertices in the foot link's frame, read from the exported ``.obj``."""
    return [[float(token) for token in line.split()[1:4]] for line in _obj_lines(urdf, leg)
            if line.startswith("v ")]


def pad_faces(urdf: pathlib.Path, leg: str) -> list[list[int]]:
    """The pad mesh's triangles, as 0-based indices into :func:`pad_vertices`.

    The asset is triangulated: 26 vertices and 48 faces satisfy ``V - E + F = 2`` with ``3F = 2E``,
    so a face is always three indices and there is nothing to fan here.
    """
    faces = []
    for line in _obj_lines(urdf, leg):
        if line.startswith("f "):
            tokens = line.split()[1:]
            if len(tokens) != 3:
                raise SystemExit(f"{pad_mesh(urdf, leg).name} has a {len(tokens)}-gon face: "
                                 f"not triangulated")
            faces.append([int(token.split("/")[0]) - 1 for token in tokens])
    return faces


def pad_normal_in_link(urdf: pathlib.Path, leg: str) -> list[float]:
    """The pad's own normal in the foot link's frame, fitted to the collision mesh's lowest band.

    Read from the exported ``.obj`` rather than assumed: the sole is a curved cap, and how far its
    contact patch is from the link's ``-z`` is a property of the asset, not of this script.
    """
    vertices = pad_vertices(urdf, leg)
    lowest = min(vertex[2] for vertex in vertices)
    band = [vertex for vertex in vertices if vertex[2] <= lowest + 0.002]
    centroid = [sum(vertex[i] for vertex in band) / len(band) for i in range(3)]
    # The plane through the contact band: its normal is the direction the band spans least in.
    cov = [[sum((vertex[i] - centroid[i]) * (vertex[j] - centroid[j]) for vertex in band) / len(band)
            for j in range(3)] for i in range(3)]
    normal = _smallest_eigenvector(cov)
    return normal if normal[2] < 0 else [-value for value in normal]


def pad_state(chain: list[dict], angles: list[float], normal: list[float],
              vertices: list[list[float]], base_z: float,
              base_rpy: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> dict:
    """One leg's pad read out for a pose: where it is, which way it FACES, and how far off the ground.

    Read in the WORLD frame: the pad's facing and its height are taken through the body's own attitude
    ``base_rpy``, because ``base_link``'s ``-z`` is the world's down only while the body is level, and
    a pad that has to meet the ground while the body rolls is not answered by a body-frame lean.

    Args:
        chain: as :func:`load_chain` returns it.
        angles: one angle per joint [rad].
        normal: unit pad normal in the foot link's frame -- :func:`pad_normal_in_link`.
        vertices: pad mesh vertices in the foot link's frame -- :func:`pad_vertices`.
        base_z: the body's height above the ground [m]; the ground is the plane ``z = 0``.
        base_rpy: the body's own roll, pitch, yaw [rad] -- the attitude the world is read through.

    Returns:
        ``frames`` (as :func:`chain_frames`); ``position`` and ``normal``, the pad origin and pad
        normal in ``base_link`` (what a display draws); ``world_normal``, that normal in the world
        frame; ``facing_cos``, its cosine with the world's down, SIGNED -- ``+1`` flat on the sole,
        ``-1`` flat on its back; ``tilt_deg``, the same read as an angle off the world's down
        (0 = facing down, 180 = facing straight up); and ``lowest_z``, the lowest pad vertex above the
        ground [m], negative when the pad is through it.
    """
    frames = chain_frames(chain, angles)
    rotation = [[frames[-1][i][j] for j in range(3)] for i in range(3)]
    position = [frames[-1][i][3] for i in range(3)]
    body_normal = [sum(rotation[i][k] * normal[k] for k in range(3)) for i in range(3)]
    body_rotation = _rpy_matrix(base_rpy)
    world_normal = [sum(body_rotation[i][k] * body_normal[k] for k in range(3)) for i in range(3)]
    facing = max(-1.0, min(1.0, -world_normal[2]))
    tilt = math.degrees(math.acos(facing))
    lowest = min(base_z + sum(body_rotation[2][k] * (position[k] + sum(rotation[k][j] * vertex[j]
                                                                         for j in range(3)))
                               for k in range(3)) for vertex in vertices)
    return {"frames": frames, "position": position, "normal": body_normal,
            "world_normal": world_normal, "facing_cos": facing, "tilt_deg": tilt, "lowest_z": lowest}


def faces_down(facing_cos: float, tol_deg: float) -> bool:
    """Whether a pad closing the world's down at ``facing_cos`` faces it within ``tol_deg``.

    The DIRECTED verdict, and the only one that separates a pad resting on its sole from one resting
    on its back: ``fold_tilt`` returns 0 for both, and ``tilt_deg`` -- which reads the same cosine as
    an angle -- is 180 for the second. Feed it ``pad_state(...)["facing_cos"]`` or the closed form's
    :func:`fold_tilt_cos`; both are the same quantity.
    """
    return facing_cos >= math.cos(math.radians(tol_deg))


def hinge_vs_body_z(chain: list[dict], angles: list[float], index: int) -> float:
    """The angle [deg] between joint ``index``'s axis and the body's z, both in ``base_link``.

    90 means the joint's motion plane can never be tilted out of a plane that contains the body's z --
    the invariant the current asset's three hinges hold exactly, over the hip's whole range. A joint
    inserted along the femur drives its downstream hinges off 90, which is the structural difference
    an added femoral rotation buys; measured here rather than argued from an axis name.
    """
    frames = chain_frames(chain, angles)
    axis = _unit(chain[index]["axis"])
    turned = [sum(frames[index][i][k] * axis[k] for k in range(3)) for i in range(3)]
    return math.degrees(math.acos(max(-1.0, min(1.0, abs(turned[2])))))


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


def leg_plane_yaw(chain: list[dict]) -> float:
    """The leg plane's yaw [rad] about the body's z, read off the hinge axis itself.

    The three hinges turn about one axis, and on this family's assets that axis is the body's ``-x``
    turned by the leg's own yaw: ``R_z(psi) @ (-1, 0, 0)``. It is 0 on the first body and +-20 deg on
    the adopted candidate, so the closed form below reads it here instead of assuming ``-x``.
    """
    hinge = _unit(chain[1]["axis"])
    return math.atan2(-hinge[1], -hinge[0])


def yawed_normal(normal: list[float], yaw: float) -> list[float]:
    """``normal`` taken into the un-yawed leg frame -- the frame the closed form is written in.

    The plane's yaw is a rotation about the body's z, which leaves the normal's z-component alone, so
    this one substitution carries a yawed leg through the closed form unchanged.
    """
    cos_yaw, sin_yaw = math.cos(yaw), math.sin(yaw)
    unit = _unit(normal)
    return [unit[0] * cos_yaw + unit[1] * sin_yaw,
            -unit[0] * sin_yaw + unit[1] * cos_yaw,
            unit[2]]


def fold_tilt_cos(normal: list[float], sigma: float, foot: float, yaw: float = 0.0) -> float:
    """The pad normal's z-component in a level body frame, read so that 1 = flat:

        cos(tilt) = ny sin(sigma) + (nx sin(foot) - nz cos(foot)) cos(sigma)

    The well-conditioned form of :func:`fold_tilt`, and the one to check against a measured tilt: an
    angle near 0 has no resolution through ``acos`` (a float64 cosine at 1 - 1e-16 returns ~1e-8 rad),
    so comparing angles would measure the rounding instead of the identity. ``yaw`` is the leg
    plane's own yaw (:func:`leg_plane_yaw`): the hinge and the blade are the body's ``-x`` and ``+y``
    turned by it, and a rotation about the body's z leaves the normal's z-component alone, so the
    plane factors out as ``R_z(-yaw)`` applied to the normal. The premise is asserted by the
    self-check and this form is compared against the FK, because a sign in either would silently flip
    a term here.
    """
    nx, ny, nz = yawed_normal(normal, yaw)
    return (ny * math.sin(sigma)
            + (nx * math.sin(foot) - nz * math.cos(foot)) * math.cos(sigma))

def fold_tilt(normal: list[float], sigma: float, foot: float, yaw: float = 0.0) -> float:
    """The pad's tilt [deg] off a level body's down, from the fold sum alone.

    ``haa``, ``hfe`` and ``kfe`` all turn about the same axis, so the pad link's attitude in
    ``base_link`` is ``Rz(hip + yaw) Rx(sigma) Ry(foot) Rz(-yaw)`` with ``sigma`` their SUM: the hip drops out of the
    tilt (a z rotation leaves the normal's z alone) and how the sum is split does not matter. For a
    level body the tilt is therefore a function of ``(sigma, foot)`` and the pad's own normal
    (:func:`fold_tilt_cos`) -- exact, and it says nothing about a pad that has to be level to the WORLD
    while the body carries roll and pitch, which is what an eval frame cannot show.

    UNDIRECTED: this is the fold's magnitude, and it reads 0 for a pad on its sole and on its back
    alike (the ``abs`` is where the sign dies). It cannot accept a pose -- that takes the DIRECTED read,
    :func:`fold_tilt_cos`'s sign through :func:`faces_down`.
    """
    return math.degrees(math.acos(max(-1.0, min(1.0, abs(fold_tilt_cos(normal, sigma, foot, yaw))))))


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


def _inserted_joint_urdf(urdf: pathlib.Path, leg: str, token: str, folder: pathlib.Path) -> pathlib.Path:
    """The asset's own URDF plus ONE revolute inserted along the femur, for the self-check.

    A fixture, not a design asset: the inserted joint takes ``hfe``'s own origin while ``hfe``'s origin
    becomes zero, so the zero pose is the asset's exactly and the only difference is the extra rotation.
    Its axis is the femur direction (``haa``'s frame to ``hfe``'s origin, stated in the frame it sits
    in), i.e. the shape a femoral long-axis rotation would have -- which is what the FK has to be able
    to carry. Mesh paths are made absolute so the fixture runs out of a temp directory.
    """
    tree = ET.parse(urdf)
    root = tree.getroot()
    hfe = next(joint for joint in root.iter("joint") if joint.get("name") == f"{leg}_hfe_joint")
    femur = _floats(hfe.find("origin").get("xyz"), 3)
    for mesh in root.iter("mesh"):
        mesh.set("filename", str((urdf.parent / mesh.get("filename")).resolve()))
    ET.SubElement(root, "link").set("name", f"{leg}_{token}")
    insertion = ET.Element("joint", {"name": f"{leg}_{token}_joint", "type": "revolute"})
    ET.SubElement(insertion, "parent", {"link": f"{leg}_haa"})
    ET.SubElement(insertion, "child", {"link": f"{leg}_{token}"})
    ET.SubElement(insertion, "origin", {"xyz": " ".join("%.6f" % value for value in femur),
                                        "rpy": "0 0 0"})
    ET.SubElement(insertion, "axis", {"xyz": " ".join("%.6f" % value for value in _unit(femur))})
    ET.SubElement(insertion, "limit", {"lower": "-0.60", "upper": "0.60", "effort": "120",
                                       "velocity": "8"})
    root.insert(0, insertion)
    hfe.find("parent").set("link", f"{leg}_{token}")
    hfe.find("origin").set("xyz", "0.000000 0.000000 0.000000")
    path = folder / f"{urdf.stem}_{token}.urdf"
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path


def _candidate_chain_check(urdf: pathlib.Path) -> None:
    """A candidate chain loads, moves, and tilts the plane the asset's hinges cannot tilt.

    The asset holds one invariant that a femoral rotation breaks: its three hinge axes stay exactly 90
    deg to the body's z over the whole range, so the plane they span always contains that z
    (:func:`hinge_vs_body_z`). This reads both sides of that -- the asset at exactly 90, the fixture
    off it by the inserted joint's angle -- so the read can be shown to tell the two chains apart.
    """
    leg, token = "lf", "fem"
    with tempfile.TemporaryDirectory() as folder:
        candidate = _inserted_joint_urdf(urdf, leg, token, pathlib.Path(folder))
        chain, base = load_chain(candidate, leg), load_chain(urdf, leg)
    tokens = tuple(joint["token"] for joint in chain)
    # The walk finds the asset's own chain, and it finds the inserted joint in its place rather than
    # reading the candidate as the old chain -- both are the point of walking the tree at all.
    assert tuple(joint["token"] for joint in base) == CHAIN, tuple(joint["token"] for joint in base)
    assert tokens == CHAIN[:2] + (token,) + CHAIN[2:], tokens
    zero_candidate = foot_pose(chain, [0.0] * len(tokens))[0]
    zero_base = foot_pose(base, [0.0] * len(CHAIN))[0]
    assert all(abs(zero_candidate[i] - zero_base[i]) < 1e-9 for i in range(3)), (zero_candidate, zero_base)
    moved = foot_pose(chain, [0.0, 0.0, 0.5, 0.0, 0.0, 0.0])[0]
    travel = math.sqrt(sum((moved[i] - zero_candidate[i]) ** 2 for i in range(3)))
    assert travel > 1e-3, (travel, "the inserted joint does not move the pad")
    for angles in ([0.0] * 5, [0.4, 0.2, 0.6, -0.3, 0.1], [-0.6, -0.6, -1.2, -1.0, 0.5]):
        for index in range(1, len(HINGES) + 1):
            assert abs(hinge_vs_body_z(base, angles, index) - 90.0) < 1e-9, (angles, index)
    driven = hinge_vs_body_z(chain, [0.0, 0.0, 0.5, 0.0, 0.0, 0.0], tokens.index("hfe"))
    assert 90.0 - driven > 20.0, (driven, "an inserted femoral rotation left the hinge plane alone")
    print("[CANDIDATE-CHAIN] one revolute inserted along the femur loads as a %d-joint chain: zero pose "
          "unchanged, pad travels %.4f m at 0.5 rad, and the downstream hinge leaves 90 deg by %.1f deg"
          " (the asset's three stay at 90.0000 over their whole range)"
          % (len(tokens), travel, 90.0 - driven))


#: The recipe the gains are read from. The gains are not a property of the body, so this is the family
#: whose line consumes it -- the same family the default body is resolved for.
_GAIN_FAMILY = "lizard2"


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
        vertices = pad_vertices(urdf, leg)
        # The mesh and the chain have to come off the SAME body: a path resolved from anywhere else is
        # how a candidate URDF gets scored against the old body's pad. This literal is a BACKSTOP --
        # on this asset the old hard-coded tree and the URDF's own tree coincide, so a reintroduced
        # hard-coded path would not trip it. What does trip loudly is `pad_mesh` on a URDF carried away
        # from its meshes (SystemExit), which is the misuse this binding exists to stop.
        assert urdf.parent in pad_mesh(urdf, leg).parents, \
            (leg, pad_mesh(urdf, leg), "the pad mesh is not read off this URDF's own tree")
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
        # The closed form's premise, read off the axes instead of asserted as the first body's
        # literals: both axes horizontal (a rotation about the body's z cannot tilt them), the blade
        # the hinge turned a quarter turn about the z, and -- the non-tautological half -- the yaw the
        # hinge states equal to the yaw the blade states.
        hinge, blade = _unit(chain[1]["axis"]), _unit(chain[4]["axis"])
        assert abs(hinge[2]) < 1e-12 and abs(blade[2]) < 1e-12, (leg, hinge, blade, "a tilted plane")
        assert all(abs(blade[i] + _cross([0.0, 0.0, 1.0], hinge)[i]) < 1e-9 for i in range(3)), \
            (leg, hinge, blade, "the blade is not the hinge turned a quarter turn about the z")
        assert abs(leg_plane_yaw(chain) - math.atan2(-blade[0], blade[1])) < 1e-9, \
            (leg, leg_plane_yaw(chain), blade, "the hinge and the blade disagree on the plane's yaw")
        # The motion plane can be yawed but never tilted: with the hip as the body's z, `haa`'s axis in
        # the body frame is the zero-pose hinge turned about that z, so its z component stays zero over
        # the whole hip range and the plane the three parallel hinges span always contains the body's z.
        # The premise is asserted above (a level-hip turn leaves the tilt alone) and to the left (the
        # hinges are parallel and horizontal); what this adds is the literal on the hip's own
        # axis plus the regression across the range, endpoints included because a limit is where a
        # rebuild would drift first. A break test (hip axis perturbed to `0 0.3 1`) fails, but at the
        # level-hip-tilt assertion rather than here -- this one is the backstop, not the first guard.
        assert chain[0]["axis"] == [0.0, 0.0, 1.0], (leg, chain[0]["axis"], "hip is not the body's z")
        yaw = leg_plane_yaw(chain)
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
                assert abs(fold_tilt_cos(normal, sigma, foot, yaw) - (-spread["normal"][2])) < 1e-12, \
                    (leg, sigma, foot)
        # The blade cannot buy the tilt back: with the legs folded by 0.62 rad its whole +-0.5 rad
        # stroke leaves >= 30 deg, which is the reading ("1-3 deg of travel against a 30-50 deg fold").
        stroke = min(pad_state(chain, [0.0, 0.62, 0.0, 0.0, -0.5 + i * 0.01], normal, vertices,
                               0.9)["tilt_deg"] for i in range(101))
        assert stroke > 30.0, (leg, stroke)
        # A pad on its BACK must not pass for a pad on its sole. The review's counterexample sits
        # inside the limits and the fold identity reads it as flat, so only the DIRECTED facing
        # separates the two -- and the verdict is checked on both reads that carry it (the FK state and
        # the closed form), because they are the same quantity and were allowed to drift apart.
        flip_normal = yawed_normal(normal, yaw)
        sigma_flip = math.pi + math.atan2(flip_normal[1], -flip_normal[2])
        flip = [0.0, 0.6, 1.2, sigma_flip - 1.8, 0.0]
        assert all(joint["limits"][0] <= angle <= joint["limits"][1] for joint, angle in zip(chain, flip)), \
            (leg, flip, "the flipped counterexample is no longer inside the limits")
        flipped = pad_state(chain, flip, normal, vertices, 0.9)
        assert abs(fold_tilt(normal, sigma_flip, 0.0, yaw)) < 0.5, (leg, "the counterexample is not flat")
        assert flipped["facing_cos"] < -0.9, (leg, flipped["facing_cos"], "the flip is not facing up")
        assert not faces_down(flipped["facing_cos"], 10.0), (leg, "a pad on its back was accepted")
        assert not faces_down(fold_tilt_cos(normal, sigma_flip, 0.0, yaw), 10.0), \
            (leg, "the closed form accepted the flipped pad")
        assert zero["facing_cos"] - flipped["facing_cos"] > 1.8, \
            (leg, zero["facing_cos"], flipped["facing_cos"])
        assert faces_down(1.0, 10.0) and not faces_down(0.9, 10.0) and faces_down(0.9, 30.0), leg
        # The body's attitude is part of the read, not an assumption this file gets to make: rolled by
        # phi about x, the pad's facing takes the hand-written Rx row, and so does the world height of
        # every pad vertex. Both are asserted at a NON-zero pose (at the zero pose the link rotation is
        # the identity and the second assertion would not exercise a rotation at all).
        roll = 0.3
        posed = pad_state(chain, [0.2, 0.3, 0.4, -0.2, 0.1], normal, vertices, 0.9)
        rolled = pad_state(chain, [0.2, 0.3, 0.4, -0.2, 0.1], normal, vertices, 0.9, base_rpy=(roll, 0.0, 0.0))
        expected_facing = posed["facing_cos"] * math.cos(roll) - posed["normal"][1] * math.sin(roll)
        assert abs(rolled["facing_cos"] - expected_facing) < 1e-12, (leg, rolled["facing_cos"], expected_facing)
        link_rotation = [[posed["frames"][-1][i][j] for j in range(3)] for i in range(3)]
        position = posed["position"]
        hand_low = min(0.9 + (position[1] + sum(link_rotation[1][k] * vertex[k] for k in range(3)))
                       * math.sin(roll)
                       + (position[2] + sum(link_rotation[2][k] * vertex[k] for k in range(3)))
                       * math.cos(roll) for vertex in vertices)
        assert abs(rolled["lowest_z"] - hand_low) < 1e-12, (leg, rolled["lowest_z"], hand_low)
        # The knee's straight pose, against the pinned per-leg facts: how far the range gets against it,
        # and the other end of the range being a fold. A regeneration that moves an origin must trip
        # these. The SIGN of the margin is the user's requirement (2026-10-09): positive means the limit
        # runs past straight, i.e. reverse bending is reachable.
        straight = math.degrees(straight_hfe(chain))
        pinned, margin, folded = KNEE_FACTS[leg]
        assert abs(straight - pinned) < 1e-3, (leg, straight, pinned)
        low, high = chain[2]["limits"]
        fold_limit, over_limit = (low, high) if straight > 0 else (high, low)
        over_run = math.degrees(abs(over_limit)) - abs(straight)
        assert abs(over_run - margin) < 1e-3, (leg, over_run, margin)
        assert over_run <= 0.0, (leg, over_run, "the knee's range reaches straight: reverse bending")
        assert abs(thigh_shank_angle(chain, [0.0, 0.0, fold_limit, 0.0, 0.0]) - folded) < 1e-3, leg
        limits = " ".join("%s[%+.2f,%+.2f]" % (joint["name"].split("_")[-2], *joint["limits"])
                          for joint in chain)
        tilt = math.degrees(math.acos(-normal[2] / math.sqrt(sum(v * v for v in normal))))
        print("  %s zero-pose pad origin %s  quarter-turn %s  limits %s"
              % (leg, ["%+.6f" % v for v in zero_position], ["%+.6f" % v for v in turned_position], limits))
        print("      pad normal %s -> %.2f deg off the link's -z  tilt %.2f deg to the world's down "
              "(facing %+.3f)  lowest %+.4f m  hip lever %.4f m"
              % (["%+.4f" % v for v in normal], tilt, zero["tilt_deg"], zero["facing_cos"],
                 zero["lowest_z"], lever))
        print("      flipped counterexample in the box: fold_tilt %.2f deg (undirected), facing %+.3f "
              "-> %s" % (fold_tilt(normal, sigma_flip, 0.0, yaw), flipped["facing_cos"],
                         "rejected" if not faces_down(flipped["facing_cos"], 10.0) else "ACCEPTED"))
        print("      hinges vs the body's z: haa/hfe/kfe %.4f/%.4f/%.4f deg (90 = the plane the three "
              "of them span contains the body's z)"
              % tuple(hinge_vs_body_z(chain, zero_angles, i) for i in (1, 2, 3)))
        print("      knee: straight at %+.4f deg, the +-1.2 rad range's margin against it %+.4f deg "
              "(>0 = reverse bending reachable), folded end %.2f deg" % (straight, over_run, folded))
        # Reflected inertia about each of this leg's own axes, and what the DECLARED gains make of it.
        # Nested subtrees do NOT make it monotone -- the mass term carries each joint's OWN lever arm, so
        # at the zero pose the yaw hip sees almost nothing of a leg that hangs along its axis while the
        # abduction axis swings the whole leg. The reading is per joint, not a nesting of the one above.
        gains = gain_table(_REPO / "rl_exp", _GAIN_FAMILY, tuple(joint["name"] for joint in chain))
        moments = reflected_inertia(chain, zero_angles, link_inertials(urdf), downstream_links(urdf, leg),
                                   gains)
        assert all(moment["inertia"] > 0.0 for moment in moments), (leg, moments)
        assert [m["group"] for m in moments] == ["legs"] * 4 + ["feet"], (leg, moments[0]["group"])
        # Dropping a link's own tensor is a change the nesting cannot see and the magnitude checks
        # cannot see either, so it gets its own statement on the REAL asset: every link's tensor term is
        # `u' I u >= 0`, hence the point-mass reading is strictly below the full one at every joint. The
        # synthetic hand case below covers the same mistake on arithmetic; this covers the asset.
        stub = [[0.0] * 3 for _ in range(3)]
        light = reflected_inertia(chain, zero_angles,
                                  {name: {**props, "tensor": stub}
                                   for name, props in link_inertials(urdf).items()},
                                  downstream_links(urdf, leg), gains)
        assert all(smaller["inertia"] < bigger["inertia"] for smaller, bigger in zip(light, moments)), leg
        # The spread over the poses the mechanism itself declares -- and the two facts that keep it from
        # being decoration. (a) Every joint's reading is INVARIANT under the hip angle: the hip's rotation
        # turns the whole downstream leg about the hip's own axis, so both the axis and the geometry it
        # measures turn together and every distance/tensor product in the sum is unchanged. A reading that
        # moved here would mean the sweep posed the wrong frame. (b) A case that changes no joint's reading
        # is a case that was never applied, which is the way this kind of sweep goes silently empty.
        cases = load_case_angles(chain)
        inertials = link_inertials(urdf)
        spread = inertia_range(chain, cases, inertials, downstream_links(urdf, leg), gains)
        per_case = {name: reflected_inertia(chain, angles, inertials, downstream_links(urdf, leg), gains)
                    for name, angles in cases.items()}
        for name, case_moments in per_case.items():
            if name not in ("zero", "hip-lo", "hip-hi"):  # zero IS the reading; the hip cases are invariant
                moved = max(abs(case_moments[i]["inertia"] - moments[i]["inertia"]) / moments[i]["inertia"]
                            for i in range(len(moments)))
                assert moved > 1e-6, (leg, name, "the case left every reading where it was")
        for name in ("hip-lo", "hip-hi"):
            for index, case_moment in enumerate(per_case[name]):
                assert abs(case_moment["inertia"] - moments[index]["inertia"]) \
                    < 1e-9 * moments[index]["inertia"], (leg, name, index)
        # And the last joint's reading is invariant under EVERY case, by construction rather than by
        # luck: its subtree is the pad alone, and the axis it measures about sits in the pad's own link
        # frame -- so every joint upstream (and the pad's own angle, which turns about that very axis)
        # carries the pad and the axis together. A sweep that posed the wrong joint index would move it.
        tip = len(moments) - 1
        tips = [per_case[name][tip]["inertia"] for name in per_case]
        assert max(tips) - min(tips) < 1e-12, (leg, tips)
        print("      inertia over the %d declared load cases (%s): %s"
              % (len(cases), " ".join(sorted(cases)), "  ".join(
                  "%s %.4f-%.4f [%s]" % (row["joint"].split("_")[-2], row["i_min"], row["i_max"],
                                         row["i_max_case"]) for row in spread)))
        print("      reflected inertia (base fixed, zero pose): %s"
              % "  ".join("%s I=%.4f w_n=%.1f Hz zeta=%.3f" % (m["joint"].split("_")[-2], m["inertia"],
                                                              m["wn_hz"], m["zeta"]) for m in moments))
    # A joint's own frame may be rotated, and then the axis is stated in it: composed, not ignored.
    yawed = [{"name": "t", "token": "t", "origin": [0.0, 0.0, 0.0], "rpy": [0.0, 0.0, math.pi / 2],
              "axis": [1.0, 0.0, 0.0], "limits": (-1.0, 1.0)}]
    rotation = foot_pose(yawed, [0.0])[1]
    assert abs(rotation[0][1] + 1.0) < 1e-12 and abs(rotation[1][0] - 1.0) < 1e-12, rotation
    # The reflected inertia, against hand arithmetic on a two-joint chain: joint b sits 1 m along x from
    # joint a, both turn about z, and the only massive link (c, below b) has mass 2 kg, its COM at
    # +0.5 m x in its own frame and 0.3 kg m^2 about z. So a sees |1.5| m and b sees |0.5| m of lever:
    # 2*1.5^2 + 0.3 = 4.8 and 2*0.5^2 + 0.3 = 0.8. Dropping the tensor (a point mass) would give 4.5
    # and 0.5, which is the mistake the break test puts back.
    zero_tensor = [[0.0] * 3 for _ in range(3)]
    synthetic = [{"name": "j_a", "token": "a", "origin": [0.0, 0.0, 0.0], "rpy": [0.0, 0.0, 0.0],
                  "axis": [0.0, 0.0, 1.0], "limits": (-1.0, 1.0)},
                 {"name": "j_b", "token": "b", "origin": [1.0, 0.0, 0.0], "rpy": [0.0, 0.0, 0.0],
                  "axis": [0.0, 0.0, 1.0], "limits": (-1.0, 1.0)}]
    synthetic_masses = {"l_b": {"mass": 0.0, "com": [0.0, 0.0, 0.0], "tensor": zero_tensor},
                        "l_c": {"mass": 2.0, "com": [0.5, 0.0, 0.0], "tensor": [[0.0, 0.0, 0.0],
                                                                                  [0.0, 0.0, 0.0],
                                                                                  [0.0, 0.0, 0.3]]}}
    synthetic_downstream = {"j_a": ["l_b", "l_c"], "j_b": ["l_c"]}
    synthetic_gains = {"j_a": {"group": "g", "kp": 100.0, "kd": 10.0},
                       "j_b": {"group": "g", "kp": 100.0, "kd": 10.0}}
    moments = reflected_inertia(synthetic, [0.0, 0.0], synthetic_masses, synthetic_downstream,
                                synthetic_gains)
    assert abs(moments[0]["inertia"] - 4.8) < 1e-12, moments
    assert abs(moments[1]["inertia"] - 0.8) < 1e-12, moments
    assert abs(moments[1]["wn_rad_s"] - math.sqrt(100.0 / 0.8)) < 1e-12, moments
    assert abs(moments[1]["zeta"] - 10.0 / (2 * math.sqrt(100.0 * 0.8))) < 1e-12, moments
    # The mass term scales with mass and the tensor does not: with the tensor gone, doubling the mass
    # doubles the reading exactly -- which is the pair of facts a point-mass model would get wrong.
    point_mass = {**synthetic_masses, "l_c": {**synthetic_masses["l_c"], "tensor": zero_tensor}}
    light = reflected_inertia(synthetic, [0.0, 0.0], point_mass, synthetic_downstream, synthetic_gains)
    heavy = reflected_inertia(synthetic, [0.0, 0.0], {**point_mass, "l_c": {**point_mass["l_c"],
                                                                            "mass": 4.0}},
                              synthetic_downstream, synthetic_gains)
    assert abs(light[0]["inertia"] - 4.5) < 1e-12 and abs(light[1]["inertia"] - 0.5) < 1e-12, light
    assert abs(heavy[0]["inertia"] - 2 * light[0]["inertia"]) < 1e-12, (light, heavy)
    assert abs(heavy[1]["inertia"] - 2 * light[1]["inertia"]) < 1e-12, (light, heavy)
    # And the tensor's rotation, on a link frame that is actually turned: the joint carries rpy 90 deg
    # about x, so the joint's axis (its own z, which IS the link's z) still reads izz -- but the axis in
    # base_link is -y now, and the transform that takes it there is where the term comes from. Dropping
    # the R' on the right (the bug this was written for) reads 0 here instead of 3, and it is invisible
    # whenever every link frame happens to be identity -- which is what the cases above are.
    turned_chain = [{"name": "j_r", "token": "r", "origin": [0.0, 0.0, 0.0],
                     "rpy": [math.pi / 2, 0.0, 0.0], "axis": [0.0, 0.0, 1.0], "limits": (-1.0, 1.0)}]
    turned_masses = {"l_r": {"mass": 0.0, "com": [0.0, 0.0, 0.0], "tensor": [[1.0, 0.0, 0.0],
                                                                              [0.0, 2.0, 0.0],
                                                                              [0.0, 0.0, 3.0]]}}
    turned_gains = {"j_r": {"group": "g", "kp": 100.0, "kd": 10.0}}
    assert abs(reflected_inertia(turned_chain, [0.0], turned_masses, {"j_r": ["l_r"]},
                                 turned_gains)[0]["inertia"] - 3.0) < 1e-12
    # The tensor's off-diagonals, against the URDF's own statement of them: the file states the inertia
    # MATRIX, so ixy goes in as the (0,1) entry. An earlier version of this fixture asserted the negated
    # matrix (reading ixy as a product of inertia) and so agreed with the same mistake in the reader --
    # which is why a fixture agreeing with the code proves nothing on its own.
    with tempfile.TemporaryDirectory() as folder:
        fixture = pathlib.Path(folder) / "tensor.urdf"
        fixture.write_text(
            '<robot name="t"><link name="x"><inertial><mass value="1"/><inertia ixx="1" iyy="2" izz="3" '
            'ixy="0.5" ixz="0.25" iyz="0.125"/></inertial></link></robot>\n', encoding="utf-8")
        tensor = link_inertials(fixture)["x"]["tensor"]
    assert tensor == [[1.0, 0.5, 0.25], [0.5, 2.0, 0.125], [0.25, 0.125, 3.0]], tensor
    _candidate_chain_check(urdf)
    print("[SELF-CHECK] zero pose equals the origin sum, a quarter hip turn rotates about the hip "
          "axis, the hip leaves the tilt alone, a body-height shift moves the pad with it, each "
          "joint's dp/dq equals its own lever arm, the tilt is the fold sum's alone (a blade stroke "
          "worth 1-3 deg against a 30-50 deg fold), the motion plane never tilts (haa's axis stays "
          "turned about the body's z over the hip's whole range), the knee's straight pose is not at "
          "zero, a pad flat on its BACK is rejected while the same pad on its sole is accepted, the "
          "body's roll enters the facing and the pad height by the hand-written Rx row, a joint's rpy "
          "is composed before its axis, a candidate chain with an inserted femoral rotation loads "
          "and leaves the hinge plane's 90 deg, and the reflected inertia about each axis matches the "
          "hand-computed 4.8/0.8 on a two-link chain -- where the axis read one frame out would give "
          "the same number for both joints -- and halves exactly once the tensor is dropped, while the "
          "tensor's off-diagonals go in as the URDF's own matrix entries (no extra sign) and the tensor "
          "turns with the link frame (a 90 deg rpy picks izz), every declared load case moves at least "
          "one reading, and the last joint's reading is invariant under all of them")


def _grid_poses(chain: list[dict], grid_tokens: tuple[str, ...], samples: int):
    """Every pose of the grid: ``samples`` values per gridded joint, endpoints included, the rest 0.

    Joints outside the grid are held at zero, and that is what makes two candidates comparable: the
    shared joints carry the same values in both, while each candidate's own extra joint is read on its
    own afterwards instead of being folded into the shared numbers.
    """
    per_joint = []
    for joint in chain:
        low, high = joint["limits"]
        if joint["token"] in grid_tokens and samples > 1:
            per_joint.append([low + (high - low) * step / (samples - 1) for step in range(samples)])
        else:
            per_joint.append([0.0])
    return list(itertools.product(*per_joint))


def _candidate_read(path: pathlib.Path, chain: list[dict], tokens: tuple[str, ...], leg: str,
                    grid_tokens: tuple[str, ...], samples: int, base_z: float) -> dict:
    """One chain over the grid: where its pad reaches, which way it faces, and its hinge-vs-body-z."""
    normal, vertices = pad_normal_in_link(path, leg), pad_vertices(path, leg)
    spans = [[], [], []]
    facings, hinges = [], []
    for angles in _grid_poses(chain, grid_tokens, samples):
        state = pad_state(chain, list(angles), normal, vertices, base_z)
        for i in range(3):
            spans[i].append(state["position"][i])
        facings.append(state["facing_cos"])
        for token in HINGES:
            if token in grid_tokens:
                hinges.append((hinge_vs_body_z(chain, list(angles), tokens.index(token)), token))
    return {"poses": len(facings), "spans": [(min(values), max(values)) for values in spans],
            "facings": facings, "hinge_worst": min(hinges) if hinges else None}


def _extra_read(chain: list[dict], tokens: tuple[str, ...], extra: list[str], samples: int) -> None:
    """The joints only this chain has, each swept ALONE: its own effect, not a pose the other can take."""
    for token in extra:
        low, high = next(joint for joint in chain if joint["token"] == token)["limits"]
        values = [low + (high - low) * step / (samples - 1) for step in range(samples)] \
            if samples > 1 else [0.0]
        worst = (90.0, "-", 0.0)
        for value in values:
            angles = [0.0] * len(tokens)
            angles[tokens.index(token)] = value
            for hinge in HINGES:
                if hinge in tokens:
                    worst = min(worst, (hinge_vs_body_z(chain, angles, tokens.index(hinge)), hinge, value))
        own = hinge_vs_body_z(chain, [0.0] * len(tokens), tokens.index(token))
        print("  extra %-19s its own axis sits %.1f deg off the body's z at rest; swept alone over "
              "%.2f..%.2f it drives the worst hinge (%s) to %.4f deg at %s=%+.2f"
              % (token, own, low, high, worst[1], worst[0], token, worst[2]))


def compare(urdf: pathlib.Path, candidate: pathlib.Path, leg: str, tol_deg: float, base_z: float,
            samples: int = 3) -> None:
    """Two chains read at the same body pose, height and tolerance: the reference against a candidate.

    Only the joints BOTH chains have are gridded, so the shared part of every pose is identical and the
    reads can be subtracted; a joint only one of them carries is reported on its own, never folded into
    the shared numbers -- that is how an inserted axis collects credit it has not earned.

    It reads STRUCTURE, not the target action, so a wider reachable set is not a verdict: nothing here
    says a pose is one the animal makes, and a bone length, body height or collision shape that differs
    between the two candidates is a second change this cannot separate out. Whether the hinge plane's
    departure from the body's z is worth an axis is decided by fitting a target sequence, not here.
    """
    reference, other = load_chain(urdf, leg), load_chain(candidate, leg)
    tokens_a = tuple(joint["token"] for joint in reference)
    tokens_b = tuple(joint["token"] for joint in other)
    shared = tuple(token for token in tokens_a if token in tokens_b)
    print("=== COMPARE leg %s | body z %.3f m | tolerance %.0f deg | %d values per joint ==="
          % (leg, base_z, tol_deg, samples))
    print("  shared joints (gridded): %s" % " ".join(shared))
    for name, path, chain, tokens in ((urdf.name + " (reference)", urdf, reference, tokens_a),
                                      (candidate.name + " (candidate)", candidate, other, tokens_b)):
        read = _candidate_read(path, chain, tokens, leg, shared, samples, base_z)
        flipped = sum(1 for facing in read["facings"] if facing < 0)
        accepted = sum(1 for facing in read["facings"] if faces_down(facing, tol_deg))
        print("  %-26s %4d poses | pad span (base_link) %s m | facing %+.3f..%+.3f (%d flipped, "
              "%d/%d accepted) | hinge vs body z min %.4f deg"
              % (name, read["poses"],
                 " ".join("%s %.3f" % (axis, high - low)
                          for axis, (low, high) in zip("xyz", read["spans"])),
                 min(read["facings"]), max(read["facings"]), flipped, accepted, read["poses"],
                 read["hinge_worst"][0] if read["hinge_worst"] else float("nan")))
        extra = [token for token in tokens if token not in shared]
        if extra:
            _extra_read(chain, tokens, extra, samples)
        else:
            print("  %-26s extra joints: none" % "")
    print("  not a verdict: reachability and the hinge plane only -- no target action, no bone length "
          "comparison, no collision and no dynamics")


def break_test(urdf: pathlib.Path) -> int:
    """Perturb what this file's verdicts rest on; every one must make :func:`self_check` fail.

    A check nobody has seen fail is not evidence of anything, and the work item this tool serves asks
    that counterexamples be able to fail the acceptance. Each case below is one reading put back the
    way it was wrong before (or wrong in the way it is easy to be wrong again); a case that leaves
    ``self_check`` green is a hole in the caliber pass, printed and returned as a failure.
    """
    identity = [[1.0 if i == j else 0.0 for j in range(3)] for i in range(3)]
    real = {name: globals()[name]
            for name in ("faces_down", "_rpy_matrix", "pad_state", "chain_joint_names", "load_chain",
                         "link_inertials", "downstream_links", "load_case_angles")}

    def point_masses(urdf: pathlib.Path) -> dict:
        """Every link's inertia tensor dropped: the chain read as a set of point masses.

        The mistake is easy to make (mass and COM are the obvious fields) and it changes the reading in
        a way no nesting assertion sees -- a truncated tensor still nests, it just understates. The hand
        case on the two-link chain is what refuses it: 4.5 against 4.8.
        """
        zero = [[0.0] * 3 for _ in range(3)]
        return {link: {**props, "tensor": zero} for link, props in real["link_inertials"](urdf).items()}

    def no_attitude(*args, **kwargs):
        """``pad_state`` with the body's attitude dropped: the level-body assumption, put back."""
        kwargs = {name: value for name, value in kwargs.items() if name != "base_rpy"}
        return real["pad_state"](*args[:5], **kwargs)

    def widened_knee(urdf: pathlib.Path, leg: str) -> list[dict]:
        """The knee's range widened past straight: the reverse bending the requirement forbids.

        This is the perturbation the 2026-10-09 decision buys: a limit that reaches straight (or runs
        past it, which is what the first body's +-1.2 rad did) must not pass the self-check.
        """
        chain = real["load_chain"](urdf, leg)
        straight = abs(straight_hfe(chain))
        for joint in chain:
            if joint["token"] == "hfe":
                joint["limits"] = (-straight - 0.05, straight + 0.05)
        return chain

    cases = [
        ("a sign-blind facing verdict",
         {"faces_down": lambda cos_value, tol: abs(cos_value) >= math.cos(math.radians(tol))}),
        ("a joint's rpy read as zero",
         {"_rpy_matrix": lambda rpy: identity}),
        ("the body's attitude dropped",
         {"pad_state": no_attitude}),
        ("the chain taken from the asset's token list, not the tree",
         {"chain_joint_names": lambda _urdf, leg: tuple(f"{leg}_{token}_joint" for token in CHAIN)}),
        ("the knee's range widened past straight (reverse bending)",
         {"load_chain": widened_knee}),
        ("the links' own inertia tensors dropped (point masses)",
         {"link_inertials": point_masses}),
        ("the subtree truncated to the joint's own child link",
         {"downstream_links": lambda urdf, leg: {name: links[:1]
                                                 for name, links in real["downstream_links"](urdf, leg).items()}}),
        ("the load cases posed at zero (a sweep that never moved the leg)",
         {"load_case_angles": lambda chain: {name: [0.0] * len(chain)
                                             for name in real["load_case_angles"](chain)}}),
    ]
    holes = []
    for label, patches in cases:
        globals().update(patches)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                self_check(urdf)
        except (AssertionError, SystemExit):
            print("  %-56s caught" % label)
        else:
            holes.append(label)
            print("  %-56s NOT CAUGHT" % label)
        finally:
            globals().update(real)
    # Not a patch: a URDF carried away from its meshes must FAIL rather than borrow another body's.
    with tempfile.TemporaryDirectory() as folder:
        moved = pathlib.Path(folder) / urdf.name
        moved.write_text(urdf.read_text(encoding="utf-8"), encoding="utf-8")
        try:
            pad_mesh(moved, LEGS[0])
        except SystemExit:
            print("  %-56s caught" % "a URDF carried away from its meshes")
        else:
            holes.append("a URDF carried away from its meshes")
            print("  %-56s NOT CAUGHT" % "a URDF carried away from its meshes")
    if holes:
        print("BREAK_TEST_FAILED: %d perturbation(s) left the self-check green" % len(holes))
        return 1
    print("BREAK_TEST_OK (%d perturbation(s), every one caught)" % (len(cases) + 1))
    return 0


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
            predicted = fold_tilt(pad_normal_in_link(urdf, leg), float(sigma.median()), 0.0,
                                  leg_plane_yaw(load_chain(urdf, leg)))
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
    parser.add_argument("--break-test", action="store_true",
                        help="perturb the readings --self-check's verdicts rest on: each one must "
                             "make it fail, or this reports the hole and exits non-zero")
    parser.add_argument("--pose", nargs=5, type=float, metavar=("HIP", "HAA", "HFE", "KFE", "FOOT"),
                        help="print one leg's pad pose at these joint angles [rad]")
    parser.add_argument("--leg", default="lf", choices=LEGS)
    parser.add_argument("--compare", type=pathlib.Path, default=None,
                        help="a candidate URDF, read against --urdf at the same body pose, height and "
                             "tolerance. Joints only one of them has are reported separately")
    parser.add_argument("--tol", type=float, default=10.0,
                        help="how far off the world's down a pad may face and still be accepted [deg]")
    parser.add_argument("--base_z", type=float, default=0.9,
                        help="the body's height above the ground for the pad reads [m]")
    parser.add_argument("--samples", type=int, default=3,
                        help="values per joint in --compare's grid, endpoints included")
    parser.add_argument("--frames", type=pathlib.Path, default=None,
                        help="a baseline-frames-3 record: print the fold sum on its loaded frames")
    parser.add_argument("--contact_n", type=float, default=1.0,
                        help="per-foot normal force above which the pad is called loaded [N]")
    args = parser.parse_args()
    # Resolved once, here: the mesh check below compares the URDF's own tree with the path a mesh was
    # read from, and a relative URDF would compare a relative parent against an absolute child.
    args.urdf = args.urdf.resolve()
    if args.self_check:
        self_check(args.urdf)
        return
    if args.break_test:
        raise SystemExit(break_test(args.urdf))
    if args.compare is not None:
        compare(args.urdf, args.compare, args.leg, args.tol, args.base_z, args.samples)
        return
    if args.frames is not None:
        fold_reading(args.frames, args.urdf, args.contact_n)
        return
    if args.pose is None:
        parser.error("nothing to do: pass --self-check, --compare, --frames or --pose")
    chain = load_chain(args.urdf, args.leg)
    position, rotation = foot_pose(chain, args.pose)
    for i, row in enumerate(rotation):
        print("  row %d %s" % (i, ["%+.5f" % v for v in row]))
    print("  pad origin in base_link %s" % ["%+.6f" % v for v in position])
    state = pad_state(chain, list(args.pose), pad_normal_in_link(args.urdf, args.leg),
                      pad_vertices(args.urdf, args.leg), args.base_z)
    print("  pad faces %+.4f of the world's down (%.2f deg off it: 0 faces down, 180 faces up)"
          % (state["facing_cos"], state["tilt_deg"]))


if __name__ == "__main__":
    main()
