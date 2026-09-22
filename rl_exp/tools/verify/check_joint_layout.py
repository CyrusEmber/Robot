# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Joint function check on the lizard asset: layout + actuation.

No version in the name on purpose: layout is a property of the *asset*, not of a recipe
version (an old task id loads today's asset -- FAMILY.md's retirement note), so the gate
outlives any one recipe. The default task is a lizard PLAY variant; a newer family is checked
with `--task Lizard2-Flat-Play-v1`, and this script then reads the family, the URDF and the leg
joint list from that task's own spawn path -- nothing here is hard-coded to one asset's chain.

Part 1 prints every body's position in the BASE frame (yaw-randomized spawn
removed via quat_apply_inverse) -- expect thighs sprawling along +/-y, shanks
pointing down (-z), feet near ground, the SPHERE HEAD (neck_pitch link) at +x,
the ANTENNA TAIL (tail3_pitch link) at -x, front legs (lf/rf) ahead of the
root, rear legs (rl/rr) behind.

Part 2 injects +0.3 rad into one joint at a time (all others zero) via the
position-action channel, lets the PD settle, and prints the BASE-frame
displacement of the segment's endpoint. Reading key (head = +x, left = +y):
  hfe (axis Z)  -> endpoint moves in the x-y plane, z ~ 0
  kfe (axis X)  -> endpoint lifts: dz dominant
  haa (axis -X) -> endpoint lifts/spreads: dz or dy dominant
  foot (axis Y) -> dy dominant
  yaw joints (axis Z) -> head/tail endpoints move in the x-y plane

Part 1.5 (FK) injects the same +0.30 rad but reads with NO physics step (`sim.forward()`),
so PD, gravity and the ground cannot enter the number. It prints two columns per joint: the
child link's axis*angle in the base frame (`turn=`, which IS the joint's axis and sign -- the
answered question) and the endpoint delta (`d=`, how far the segment travels). The endpoint
column has a blind spot: a URDF child link's frame origin sits ON its joint's axis, so the
last joint of a chain moves it nowhere -- `*_foot_joint`, `neck_yaw`, `neck_pitch` and
`tail3_pitch` all read 0.000 there by construction, while `turn=` stays exact. `turn=` also
settles the head-side pitch chains, whose standing reading mixes sag and a ~90-step oscillation.
It works on a task whose action group excludes the joint (it writes joint states, not targets),
so the blade joints can be read on a version that dropped them. The probed leg joints are
derived from the asset's own joint list, so a family that INSERTED a joint (lizard2's hip) has
it measured here without touching this table.

Part 1.6 (load-bearing sweep) settles the robot (zero action) and then sweeps ONE leg joint at a time
over its URDF range from the SETTLED joint state, reporting the fore-aft (base +x) and vertical travel of
THAT leg's plate centre, plus the joint's LEVER ARM: the perpendicular distance from its axis line to that
plate centre, both read in the SAME pose (an axis measured in another pose is off by the body's tilt --
measured 2026-09-22: 8% on lizard's rr_hfe). The arm is the whole story (travel ~ arm x dtheta), the
printed `chord` is the upper bound `2 arm sin(dtheta/2)`, and the sweep ASSERTS `dx <= chord` -- the
machine version of pitfall P009, where reading the axis VALUE instead of the arm overstated a joint by
60x. It runs over every leg joint the ASSET has (`leg_probes`, derived from the joint list, so four legs
and any inserted joint) and names the leg's largest fore-aft joint.

Part 1.7 (composite grid) sweeps the pair given by --sweep-a/--sweep-b (joint TOKENS, prefixed with
--sweep-leg; defaults `lf`/`hfe`/`kfe`, which reproduces the 2026-09-21 lizard table) and WARNs when the
pair excludes the leg's largest fore-aft joint, so the grid cannot be mistaken for the stride evidence on
a family whose stride axis is elsewhere. The single-joint table is not a bound -- hfe sweeps the whole
distal assembly, so what kfe does to the shank changes hfe's radius. The plate CENTRE is a fixed material
point on purpose: the plate pitches, so "the lowest corner" changes identity between cells and a table of
those x values measures the plate's own 0.458 m extent instead of the leg's stroke. Base x is invariant
under a vertical shift, so each cell also reports the body height it would need to put the plate floor
back on the ground.

Action coverage is printed as the full index -> joint order; `--require-all-actions` turns "every joint
of the asset is carried by exactly one action term, and the vector is as wide as the mapping" into a
hard failure. Use it whenever the run is the evidence that a newly added joint is commandable.

CAVEAT (same as the v6-era reading, by design of the asset): the two
HEAD-SIDE pitch joints (chest_pitch, neck_pitch) carry the front legs + ball
head on a ~1 m lever propped by the planted legs -- underdamped (I ~ 30 kg m^2
vs damping 20), oscillation period ~ 90 steps > the 40-step settle window, so
their `achieved`/delta readings mix gravity sag + oscillation phase. Yaw
joints (no gravity torque) and the antenna tail (light) read clean.

v8 ground truth (rename_flip_v8.py): the old "neck1-3" chain was the tail,
the old "tail_yaw/tail_pitch" chain carried the head -- names now match
anatomy and the body was rotated net +90 deg (sphere head -y -> +x).

Any registered PLAY task can be checked (`--task`): layout and the action
split are the ASSET's contract, not a recipe's, so the entry point is
resolved from the registry rather than naming one line's cfg class.

Precondition: the reading assumes the robot stands under zero action. On a
task where zero action falls over, `p0` is a falling pose and every delta
mixes the fall with the injected joint -- check the stance first
(`baseline_probe.py` prints the zero-action height, load and tilt).
"""

import argparse
import pathlib
import xml.etree.ElementTree as ET

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Asset layout + actuation check (any task id).")
parser.add_argument(
    "--task",
    default="Lizard-Rough-Play-v8",
    help="registered PLAY task id; the layout and the action split are the ASSET's contract, not a "
    "recipe's, so the entry point is read from the registry and any line's PLAY task works",
)
parser.add_argument(
    "--settle",
    type=int,
    default=40,
    help="steps per phase. The head-side pitch joints oscillate with a ~90-step period (see the "
    "caveat in the docstring), so a window below that reads the oscillation phase, not the target",
)
parser.add_argument(
    "--sweep-leg",
    default="lf",
    help="leg whose plate the --sweep-a/--sweep-b grid reads (default lf). The per-leg table above "
    "covers all four legs; this only picks which leg the pair grid is computed for",
)
parser.add_argument(
    "--sweep-a",
    default="hfe",
    help="first joint TOKEN of the composite load-height sweep (hip/haa/hfe/kfe/foot, prefixed with "
    "--sweep-leg). The default reproduces the 2026-09-21 lizard table; on an asset whose stride "
    "axis is another joint this run prints a WARN and the pair must be named explicitly",
)
parser.add_argument(
    "--sweep-b",
    default="kfe",
    help="second joint TOKEN of the composite load-height sweep, prefixed with --sweep-leg",
)
parser.add_argument(
    "--require-all-actions",
    action="store_true",
    help="fail unless every joint of the asset is carried by exactly one action term, in a vector of "
    "the expected width. Required when this run is the evidence that a new joint is commandable",
)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
simulation_app = AppLauncher(args_cli).app

import gymnasium as gym
import torch

import isaaclab_tasks  # noqa: F401
from isaaclab.utils.math import quat_apply, quat_apply_inverse
from isaaclab.utils.string import string_to_callable

INJECT_RAD = 0.3
SETTLE_STEPS = args_cli.settle

cfg = string_to_callable(gym.spec(args_cli.task).kwargs["env_cfg_entry_point"])()
cfg.scene.num_envs = 1
env = gym.make(args_cli.task, cfg=cfg)
env.reset()
robot = env.unwrapped.scene["robot"]
joint_names = list(robot.joint_names)
body_names = list(robot.data.body_names)

# The script is task-parameterized, so its asset knowledge has to be too: the leg chain of a family
# that INSERTED a joint is a different chain, and a hand-written "hfe x kfe" sweep on it measures the
# wrong joints while looking exactly like a passing run (review 2026-09-22). Family and URDF are read
# off the task's own spawn path; every leg joint below is derived from the joint list.
_USD = pathlib.Path(str(cfg.scene.robot.spawn.usd_path))
_FAMILY = _USD.parent.name
_RL_EXP = pathlib.Path(__file__).resolve().parents[2]
_URDF = _RL_EXP / "versions" / _FAMILY / f"{_FAMILY}.urdf"
if not _URDF.exists():
    raise SystemExit(f"no urdf beside the task's asset: {_URDF} (task {args_cli.task}, usd {_USD})")
print("ASSET family=%s usd=%s urdf=%s" % (_FAMILY, _USD.name, _URDF.name))


def urdf_joints() -> dict:
    """URDF joints by SIM joint name (they match on this asset), with axis and limits."""
    out = {}
    for j in ET.parse(_URDF).getroot().findall("joint"):
        axis, limit = j.find("axis"), j.find("limit")
        out[j.get("name")] = {
            "axis": tuple(float(v) for v in axis.get("xyz").split()) if axis is not None else None,
            "lower": float(limit.get("lower")),
            "upper": float(limit.get("upper")),
        }
    return out


JOINTS = urdf_joints()

# leg tokens, proximal -> distal. `hip` is lizard2's addition (a vertical axis at the leg root); a
# family that inserts another joint adds a token here, which is the one line a new joint costs.
_LEG_TOKENS = ("hip", "haa", "hfe", "kfe", "foot")


def leg_probes() -> list[tuple[str, str, str]]:
    """``(sim joint, child link, chain endpoint)`` for every leg joint the ASSET has, all four legs."""
    out = []
    for name in joint_names:
        if not name.endswith("_joint"):
            continue
        link = name[: -len("_joint")]
        prefix, _, token = link.rpartition("_")
        if token not in _LEG_TOKENS or link not in body_names or f"{prefix}_foot" not in body_names:
            continue
        out.append((name, link, f"{prefix}_foot"))
    return out


def pos_b():
    """All body positions in the base frame, tensor (num_bodies, 3)."""
    root_q = robot.data.root_quat_w.torch
    rel = robot.data.body_pos_w.torch - robot.data.root_pos_w.torch
    return quat_apply_inverse(root_q, rel)


print("=== LAYOUT (base frame: sphere head=+x, antenna tail=-x, left=+y, up=+z) ===")
p = pos_b()[0]
base = p[body_names.index("base_link")]
# The leg bodies are the asset's own (a family that inserted `hip` prints one more row per leg).
_LEG_ORDER = ("hip", "haa", "hfe", "kfe", "foot")
for name in ("neck_pitch", "chest_pitch", "tail1_pitch", "tail3_pitch") + tuple(
        child for _, child, _ in sorted(leg_probes(),
                                        key=lambda probe: (probe[1][:2], _LEG_ORDER.index(probe[1].rpartition("_")[2])))):
    i = body_names.index(name)
    print("BODY %-11s rel=(%7.3f, %7.3f, %7.3f)" % (name, p[i, 0] - base[0], p[i, 1] - base[1], p[i, 2] - base[2]))

# hard gate: anatomy must match the names -- the v6 lesson (names trusted over
# geometry for two versions) dies here
assert p[body_names.index("neck_pitch"), 0] - base[0] > 1.0, "sphere head (neck_pitch) must sit at +x"
assert p[body_names.index("tail3_pitch"), 0] - base[0] < -1.0, "antenna tail (tail3_pitch) must sit at -x"
for n in ("lf_haa", "rf_haa"):
    assert p[body_names.index(n), 0] - base[0] > 0, f"front leg {n} must be ahead of the root"
for n in ("rl_haa", "rr_haa"):
    assert p[body_names.index(n), 0] - base[0] < 0, f"rear leg {n} must be behind the root"
for n in ("lf_haa", "rl_haa"):
    assert p[body_names.index(n), 1] - base[1] > 0, f"left leg {n} must be on +y"
for n in ("rf_haa", "rr_haa"):
    assert p[body_names.index(n), 1] - base[1] < 0, f"right leg {n} must be on -y"
print("LAYOUT_GATES PASSED (head +x / tail -x / legs anatomical)")

print("=== FK (joint +%.2f rad, kinematics only: no physics step, so PD/gravity/ground cannot enter) ==="
      % INJECT_RAD)
# The polarity authority. Same injection as Part 2, but the endpoint is read after `sim.forward()`
# instead of 40 physics steps, so the number is forward kinematics and nothing else. Sample: on the
# standing baseline stance lf_hfe really turns 0.269 rad and its foot reads 13 mm (load path); here
# the same joint reads the arc its axis prescribes.
SPINE_PROBES = [
    ("chest_pitch_joint", "chest_pitch", "neck_pitch"),
    ("neck_yaw_joint", "neck_yaw", "neck_pitch"),
    ("neck_pitch_joint", "neck_pitch", "neck_pitch"),
    ("tail1_yaw_joint", "tail1_yaw", "tail3_pitch"),
    ("tail3_pitch_joint", "tail3_pitch", "tail3_pitch"),
]
FK_PROBES = leg_probes() + SPINE_PROBES


def fk_pose(row):
    """Write one joint configuration and propagate kinematics only (no physics step)."""
    q = row.reshape(1, len(joint_names)).to(robot.device)
    robot.write_joint_state_to_sim(q, torch.zeros_like(q))
    env.unwrapped.sim.forward()
    env.unwrapped.scene.update(env.unwrapped.physics_dt)


def joint_turn(i, q0):
    """The injected joint's axis*angle in the base frame, from the child link's own axes.

    Deliberately avoids quaternion algebra: `quat_apply` is the library's own composition (the same
    call the head-arrow marker uses, and `.torch` quats are consistent with it), whereas hand-rolled
    delta quaternions depend on the (x,y,z,w)/(w,x,y,z) ordering of the buffer. The child frame axis
    that moves most is the probe -- a vector parallel to the joint's axis has no cross product.

    The norm of the result is the injected angle, so `|turn| != INJECT_RAD` means the reading is
    wrong rather than the asset.
    """
    eye = torch.eye(3, device=robot.device)
    v0 = torch.stack([quat_apply(q0, eye[k]) for k in range(3)])
    v1 = torch.stack([quat_apply(robot.data.body_quat_w.torch[0, i], eye[k]) for k in range(3)])
    cross = torch.linalg.cross(v0, v1)
    k = int(torch.argmax(torch.linalg.norm(cross, dim=-1)))
    angle = torch.atan2(torch.linalg.norm(cross[k]), torch.dot(v0[k], v1[k]))
    axis = cross[k] / torch.linalg.norm(cross[k])
    return quat_apply_inverse(robot.data.root_quat_w.torch[0], axis) * angle


stance = torch.zeros(len(joint_names), device=robot.device)
fk_pose(stance)
fk_p0, fk_q0 = pos_b()[0], robot.data.body_quat_w.torch[0].clone()
TURN = {}  # joint -> unit axis in the base frame (the load-height section below uses these)
for joint, child, endpoint in FK_PROBES:
    row = stance.clone()
    row[joint_names.index(joint)] = INJECT_RAD
    fk_pose(row)
    p = pos_b()[0]
    c_idx, e_idx = body_names.index(child), body_names.index(endpoint)
    dc, de = p[c_idx] - fk_p0[c_idx], p[e_idx] - fk_p0[e_idx]
    turn = joint_turn(c_idx, fk_q0[c_idx])
    TURN[joint] = turn / torch.linalg.norm(turn)
    print("FK %-17s +%.2f -> %-11s turn=(%+.3f, %+.3f, %+.3f) |%.3f| | d=(%7.3f, %7.3f, %7.3f) "
          "| %-11s d=(%7.3f, %7.3f, %7.3f)"
          % (joint, INJECT_RAD, child, turn[0], turn[1], turn[2], float(torch.linalg.norm(turn)),
             dc[0], dc[1], dc[2], endpoint, de[0], de[1], de[2]))

# --- composite scan at the load-bearing height --------------------------------------------------
# The single-joint table above is a diagnostic, NOT a bound on the leg: `hfe` swings the whole
# distal assembly, so whatever `kfe` does to the shank changes the radius `hfe` sweeps -- two
# joints compose, their product is not the sum of their single-joint travels. This section settles
# the robot first (the stroke that counts is the one available while the plate carries the body),
# then sweeps the pair and reports the fore-aft (base +x) excursion of the plate's centre.
# The base is not re-solved during the sweep (`sim.forward()` updates kinematics only), so the body
# stays at the settled height and only the leg moves.
_SWEEP_A, _SWEEP_B = args_cli.sweep_a, args_cli.sweep_b
_FOOT_LINK = f"{args_cli.sweep_leg}_foot"
for _token in (_SWEEP_A, _SWEEP_B):
    if f"{args_cli.sweep_leg}_{_token}_joint" not in JOINTS or _FOOT_LINK not in body_names:
        raise SystemExit(f"--sweep-leg {args_cli.sweep_leg} + --sweep-a/-b {_SWEEP_A}/{_SWEEP_B}: no such"
                         f" joint ({args_cli.sweep_leg}_{_token}_joint) or foot ({_FOOT_LINK}) on this asset."
                         f" Joints here: {sorted(JOINTS)}")


def plate_corners(foot_link: str):
    """Bbox corners of ONE foot's collision mesh in the foot frame, at the mesh floor.

    A proxy for the contact patch: that plate is a 26-vertex hull, so its bbox floor is what the
    ground can touch. Read from the URDF's own collision mesh rather than hard-coded. Per foot,
    because a sweep of the right-rear leg measured against the left-front plate reads 0.000 --
    the plate simply does not move (measured 2026-09-22, first version of the per-leg table).
    """
    root = ET.parse(_URDF).getroot()
    link = next(item for item in root.findall("link") if item.get("name") == foot_link)
    mesh = _URDF.parent / link.find("collision/geometry/mesh").get("filename")
    verts = [list(map(float, ln.split()[1:4])) for ln in mesh.read_text().splitlines() if ln.startswith("v ")]
    lo = [min(v[i] for v in verts) for i in range(3)]
    hi = [max(v[i] for v in verts) for i in range(3)]
    return torch.tensor([[x, y, lo[2]] for x in (lo[0], hi[0]) for y in (lo[1], hi[1])], device=robot.device)


_CORNERS = {}


def corners_of(foot_link: str):
    """``plate_corners(foot_link)``, read once per leg."""
    if foot_link not in _CORNERS:
        _CORNERS[foot_link] = plate_corners(foot_link)
    return _CORNERS[foot_link]


def contact_corner(foot_link: str = _FOOT_LINK):
    """World point of that plate's lowest corner at the current configuration."""
    i = body_names.index(foot_link)
    pts = robot.data.body_pos_w.torch[0, i] + quat_apply(robot.data.body_quat_w.torch[0, i], corners_of(foot_link))
    return pts[int(torch.argmin(pts[:, 2]))]


corners_of(_FOOT_LINK)
fk_pose(stance)
settle_steps = max(SETTLE_STEPS, 100)  # ~2 s: the landing transient is ~0.3 s; the stance HEIGHT is what must settle
zero_actions = torch.zeros(env.unwrapped.num_envs, env.unwrapped.action_manager.total_action_dim)
for _ in range(settle_steps):
    env.step(zero_actions)
base_z = float(robot.data.root_pos_w.torch[0, 2])
ground_z = float(contact_corner()[2])
# The reference row is the SETTLED joint state, never zeros: under load the PD sags, so a sweep from
# zeros is "an unloaded leg at a loaded body height" -- neither pose, and the neutral cell of the
# first version of this scan was wrong for exactly that reason.
q_ref = robot.data.joint_pos.torch[0].clone()
print("=== COMPOSITE %s x %s from the load-bearing stance (base z = %.3f m after %d zero-action steps, "
      "plate floor z = %.3f m, sag |q_ref - 0| = %.4f rad) ==="
      % (_SWEEP_A, _SWEEP_B, base_z, settle_steps, ground_z, float(torch.linalg.norm(q_ref - stance))))
if base_z > 1.0:
    print("WARN base z is at spawn height: the settle did not land (reset or termination fired?) -- "
          "this sweep is then measured airborne")
_spawn_z = float(cfg.scene.robot.init_state.pos[2])
if base_z < 0.7 * _spawn_z:
    print("WARN base z %.3f m is far below the spawn height %.3f m: the settle ended with the robot low or"
          " down (rough terrain? a termination?), so every number below is measured in THAT pose -- rerun on"
          " a flat PLAY task of the same family for the load-bearing stance" % (base_z, _spawn_z))
_bx = quat_apply(robot.data.root_quat_w.torch[0], torch.tensor([1.0, 0.0, 0.0], device=robot.device))
print("base yaw check: body +x in world = (%+.2f, %+.2f, %+.2f); the table below is BASE-frame, so a "
      "randomized spawn yaw cannot mix fore-aft into lateral" % (_bx[0], _bx[1], _bx[2]))
# A fixed material point, not "the lowest corner": the plate pitches with kfe, so the lowest corner
# changes identity between cells and a table of those x values measures the plate's own 0.458 m
# extent rather than the leg's stroke (measured 2026-09-21: 143-644 mm, i.e. the plate's size).
# The base x is invariant under a vertical shift, so the fore-aft numbers hold at ANY body height;
# what the height decides is whether the cell is reachable at the settled height, reported as the
# base z that cell would need to put the plate floor back on the ground.
_STANCE_TOL = 0.05  # m: body height a cell may require and still count as "reachable at the stance"


def plate_centre(foot_link: str = _FOOT_LINK):
    """That plate's bbox centre in the BASE frame (spawn yaw stripped, as `pos_b` does) and its floor z."""
    i = body_names.index(foot_link)
    pts = robot.data.body_pos_w.torch[0, i] + quat_apply(robot.data.body_quat_w.torch[0, i], corners_of(foot_link))
    centre_w = pts.mean(dim=0)
    centre_b = quat_apply_inverse(robot.data.root_quat_w.torch[0], centre_w - robot.data.root_pos_w.torch[0])
    return centre_b, float(pts[:, 2].min())


# Self-check: the sweep's neutral cell (hfe = 0, kfe = 0) must land within a few mm of the plate centre
# measured right here, on the settled robot. It is the one cell whose answer is already known, and the
# first two versions of this section both failed it (unloaded reference row, and corner identity churn).
print("self-check: settled plate centre x = %.0f mm -- the %s=0,%s=0 cell below must match it"
      % (1000 * float(plate_centre()[0][0]), _SWEEP_A, _SWEEP_B))

# --- every leg joint, swept at the load-bearing height -------------------------------------------
# A joint that exists but is never swept is a joint nobody checked. This table is derived from the
# asset's own joint list (`leg_probes`), so a family that inserted a joint grows through it instead of
# slipping past it, and it covers all four legs rather than the one the grid below uses.
# Per joint, the number that decides everything is the LEVER ARM `r`: the perpendicular distance from
# that joint's axis line to the plate centre. Rotation by dtheta moves the point by ~r*dtheta, so r is
# the whole story -- lizard's hfe turned out to sit at the femur's distal end (r = 49 mm, i.e. 15 mm of
# foot travel per 0.3 rad) while its haa has r = 0.27 m at the same injection. Reading the axis VALUE
# instead of the arm is pitfall P009; `chord` here is the free upper bound `2 r sin(dtheta/2)`, and the
# assertion below is the machine version of that lesson.
fk_pose(q_ref)
settled = pos_b()[0]
settled_quat = robot.data.body_quat_w.torch[0].clone()


def axis_at(joint: str, child: str, base_q) -> torch.Tensor:
    """The joint's unit axis in the BASE frame AT ``base_q``.

    The FK section measures axes at the zero stance; under load the base body has tilted, so reusing
    those directions here mixes two frames and the lever arm comes out wrong -- measured 2026-09-22:
    lizard's rr_hfe read an arm 8% short, which the chord assertion below caught.
    """
    row = base_q.clone()
    row[joint_names.index(joint)] += INJECT_RAD
    fk_pose(row)
    turn = joint_turn(body_names.index(child), settled_quat[body_names.index(child)])
    fk_pose(base_q)
    return turn / torch.linalg.norm(turn)


print("=== LOAD-BEARING SWEEP: every leg joint over its URDF range (body held at %.3f m) ===" % base_z)
stride_rows = []
for joint, child, foot in leg_probes():
    spec = JOINTS[joint]
    fk_pose(q_ref)
    centre_here = plate_centre(foot)[0]
    arm_vec = centre_here - settled[body_names.index(child)]
    axis = axis_at(joint, child, q_ref)
    arm = float(torch.linalg.norm(arm_vec - torch.dot(arm_vec, axis) * axis))
    dtheta = spec["upper"] - spec["lower"]
    chord = 2.0 * arm * float(torch.sin(torch.tensor(dtheta / 2.0)))
    xs, zs = [], []
    for v in torch.linspace(spec["lower"], spec["upper"], 5).tolist():
        row = q_ref.clone()
        row[joint_names.index(joint)] = v
        fk_pose(row)
        centre, floor_z = plate_centre(foot)
        xs.append(float(centre[0]))
        zs.append(float(floor_z))
    dx, dz = max(xs) - min(xs), max(zs) - min(zs)
    stride_rows.append((joint, dx, dz, arm))
    print("  SWEEP %-17s axis=(%s) range=(%+.2f,%+.2f) arm=%5.3f m chord=%5.3f m | "
          "dx=%6.3f m dz=%6.3f m  (dx/chord=%.2f)"
          % (joint, "".join("%+.2f" % v for v in spec["axis"]), spec["lower"], spec["upper"],
             arm, chord, dx, dz, dx / chord if chord > 1e-9 else 0.0))
    assert dx <= chord + 1e-3, (
        "SWEEP %s: fore-aft travel %.3f m exceeds the %.3f m chord its %.3f m lever arm allows -- "
        "the reading or the arm is wrong, not the asset" % (joint, dx, chord, arm))
_fore = max(stride_rows, key=lambda r: r[1])
_fore_token = _fore[0][len(args_cli.sweep_leg) + 1: -len("_joint")]
print("LARGEST FORE-AFT AT LOAD: %s dx=%.3f m (arm %.3f m, urdf axis %s)"
      % (_fore[0], _fore[1], _fore[3], "".join("%+.2f" % v for v in JOINTS[_fore[0]]["axis"])))
for leg in ("lf", "rf", "rl", "rr"):
    mine = [(j, dx) for j, dx, _, _ in stride_rows if j.startswith(leg + "_")]
    if mine:
        print("  LEG %s: " % leg + "  ".join("%s=%.3f" % (j[len(leg) + 1:-6], dx) for j, dx in mine))


if _SWEEP_A != _fore_token and _SWEEP_B != _fore_token:
    print("WARN the %s x %s grid below does NOT include %s, %s's largest fore-aft joint "
          "(%.3f m). Name the pair with --sweep-a/--sweep-b if this grid is meant to be the evidence."
          % (_SWEEP_A, _SWEEP_B, _fore[0], args_cli.sweep_leg, _fore[1]))
_leg = args_cli.sweep_leg
_joint_a = f"{_leg}_{_SWEEP_A}_joint"
_joint_b = f"{_leg}_{_SWEEP_B}_joint"
_a_grid = torch.linspace(JOINTS[_joint_a]["lower"], JOINTS[_joint_a]["upper"], 5).tolist()
_b_grid = torch.linspace(JOINTS[_joint_b]["lower"], JOINTS[_joint_b]["upper"], 5).tolist()
print("plate CENTRE x [mm]; '*' marks cells needing a body height more than %.0f mm off the settled one"
      % (1000 * _STANCE_TOL))
print("            %s=" % _SWEEP_B + "".join("%9.1f" % k for k in _b_grid))
cells = []
for h in _a_grid:
    line = []
    for k in _b_grid:
        row = q_ref.clone()
        row[joint_names.index(_joint_a)] = h
        row[joint_names.index(_joint_b)] = k
        fk_pose(row)
        centre, floor_z = plate_centre()
        need_z = base_z - (floor_z - ground_z)
        line.append((float(centre[0]), need_z))
        cells.append((float(centre[0]), need_z))
    print("  %s=%+5.2f " % (_SWEEP_A, h)
          + "".join("%8.0f%s" % (1000 * c[0], "" if abs(c[1] - base_z) <= _STANCE_TOL else "*")
                    for c in line))
usable = [c[0] for c in cells if abs(c[1] - base_z) <= _STANCE_TOL]
all_x = [c[0] for c in cells]
print("COMPOSITE stroke: plate centre x-range = %.3f m over %d of %d cells reachable at the settled "
      "height; %.3f m over all cells (which would need a body height of %.3f-%.3f m instead of %.3f)"
      % ((max(usable) - min(usable)) if usable else 0.0, len(usable), len(cells),
         max(all_x) - min(all_x), min(c[1] for c in cells), max(c[1] for c in cells), base_z))
fk_pose(q_ref)  # leave the settled stance: the ACTUATION section below assumes a standing robot

print("=== ACTUATION (+%.2f rad single joint, endpoint delta in base frame) ===" % INJECT_RAD)
# Both deltas are printed, and on a STANDING robot neither of them answers "which way does this
# joint go": the endpoint sits under the load path (the foot is planted, the head chain is propped
# by the legs), so a joint that really moved 0.27 rad can read as millimetres of endpoint motion --
# measured 2026-09-18 on the baseline stance: lf_hfe achieved 0.269 rad, lf_foot moved 13 mm.
# The sign of that millimetre motion is not the joint's direction -- read the FK section above for
# polarity, and read this one for whether the channel is alive.
# Read `achieved/commanded` for those chains (it says whether the channel is alive and how much of
# the target the PD wins against the load); the deltas stay meaningful for the free chains (tail).
# Every leg joint of THIS asset (so an inserted joint is probed without a table edit) plus the spine
# chains, whose endpoints and names are the same on every family.
PROBES = [(joint, endpoint) for joint, _child, endpoint in leg_probes()] + [
    ("chest_pitch_joint", "neck_pitch"),  # chest pitch: ball head nods (dz)
    ("neck_yaw_joint", "neck_pitch"),     # neck yaw: ball head sweeps in xy
    ("neck_pitch_joint", "neck_pitch"),   # neck pitch: ball head nods (dz)
    ("tail1_yaw_joint", "tail3_pitch"),   # tail yaw: antenna sweeps in xy
    ("tail3_pitch_joint", "tail3_pitch"), # tail tip pitch
]

# action layout = concat of manager terms; map joint -> (action idx, scale)
am = env.unwrapped.action_manager
joint_to_action = {}
action_order = []
twice = []
offset = 0
for term_name in am.active_terms:
    term = am.get_term(term_name)
    t_scale = term._scale
    t_scale = float(t_scale) if not hasattr(t_scale, "reshape") else float(t_scale.reshape(-1)[0])
    print("ACTION_TERM %s %s scale=%s joints=%s" %
          (term_name, type(term).__name__, t_scale, term._joint_names))
    for i, jn in enumerate(term._joint_names):
        if jn in joint_to_action:
            twice.append(jn)
        joint_to_action[jn] = (offset + i, t_scale)
        action_order.append(jn)
    offset += len(term._joint_names)
print("TOTAL_ACTION_DIM %d" % am.total_action_dim)
# The mapping check: a joint the action vector does not carry is a joint the policy can never move --
# on a family that ADDED a joint that is the whole point of the family, and before this line the run
# printed it as a SKIP line among ten others (review 2026-09-22).
_unchannelled = [j for j in joint_names if j not in joint_to_action]
print("ACTION COVERAGE %d of %d joints channelled (dim %d); index -> joint order:"
      % (len(joint_to_action), len(joint_names), am.total_action_dim))
for i, jn in enumerate(action_order):
    print("  ACTION_IDX %3d %s" % (i, jn))
if _unchannelled:
    print("  NOT COMMANDABLE: " + ", ".join(_unchannelled))
if twice:
    print("  IN MORE THAN ONE GROUP: " + ", ".join(sorted(set(twice))))
if args_cli.require_all_actions:
    _bad = []
    if _unchannelled:
        _bad.append("no action term carries %s" % ", ".join(_unchannelled))
    if twice:
        _bad.append("more than one term carries %s" % ", ".join(sorted(set(twice))))
    if am.total_action_dim != len(action_order):
        _bad.append("action dim %d != %d channelled joints" % (am.total_action_dim, len(action_order)))
    if _bad:
        raise SystemExit("--require-all-actions FAILED: " + "; ".join(_bad))
    print("ACTION_COVERAGE_GATE PASSED (every joint channelled exactly once)")

act_dim = am.total_action_dim
for joint, endpoint in PROBES:
    zero = torch.zeros(1, act_dim)
    idx = joint_names.index(joint)
    e_idx = body_names.index(endpoint)
    # settle back to stance
    for _ in range(SETTLE_STEPS):
        env.step(zero)
    p0 = pos_b()[0, e_idx]
    p0_w = robot.data.body_pos_w.torch[0, e_idx].clone()
    cmd = zero.clone()
    if joint not in joint_to_action:
        print("JOINT %-17s SKIP -- no action group carries it on this task, so the policy cannot command "
              "it (its axis is in the FK section above)" % joint)
        continue
    a_idx, a_scale = joint_to_action[joint]
    # use_default_offset=True everywhere in this family, so the joint target the action asks for is
    # default + scale * action -- which is INJECT_RAD by construction. The action VALUE is what
    # differs between groups, and printing that as "commanded" would read as a 4x PD shortfall
    target = INJECT_RAD
    cmd[0, a_idx] = target / a_scale if a_scale > 0 else 1.0  # scale 0 = dead channel, poke anyway
    for _ in range(SETTLE_STEPS):
        env.step(cmd)
    p1 = pos_b()[0, e_idx]
    p1_w = robot.data.body_pos_w.torch[0, e_idx]
    d = p1 - p0
    d_w = p1_w - p0_w
    achieved = float(robot.data.joint_pos[0][idx])
    # a target the limits clamp would still read as "the joint answered" -- report the soft limits
    # and flag a reading sitting on one of them, or a small delta has two very different causes
    limits = robot.data.soft_joint_pos_limits.torch[0, idx]
    lo, hi = float(limits[0]), float(limits[1])
    clamped = min(abs(achieved - lo), abs(achieved - hi)) < 1e-3
    print("JOINT %-17s scale=%.2f -> %-11s achieved=%+.3f of target %+.3f (%.0f%%) limits=(%+.2f,%+.2f)%s "
          "d_base=(%7.3f, %7.3f, %7.3f) d_world=(%7.3f, %7.3f, %7.3f)"
          % (joint, a_scale, endpoint, achieved, target, 100.0 * abs(achieved) / target,
             lo, hi, " CLAMPED" if clamped else "", d[0], d[1], d[2], d_w[0], d_w[1], d_w[2]))

env.close()
print("=== DONE ===")
