# -*- coding: utf-8 -*-
"""Does the stance survive its own default targets? Static load, then one small fore-aft step.

The v3 decision drops the ankle joints (`kfe`/`foot`) from the policy's action interface and leaves them
to PD at the version's default target. The question that decision creates is physical, not geometric: a
level sole in the default *pose* says nothing about the sole once an upstream joint moves, because the
pad still rides the chain. This probe reads that, with no policy and no checkpoint, on whatever asset
`--usd` points at (by default the task's own frozen one -- pass the candidate's USD to measure the
candidate, because a run on the frozen asset says nothing about it):

  1. **settle** -- every joint at its default target. An all-zero action means exactly that, so this is
     already the v3 situation for `kfe`/`foot`: not commanded, only PD-held.
  2. **small fore-aft step** -- one joint's target interpolated continuously out and back at the physics
     step rate, so contact, slip and torque are read while the leg carries load. Every control step is
     sampled: a 20-step interval cannot see a brief liftoff.

Per sample it prints base height, each foot's contact force, the sole's tilt off level (from the
*calibrated* contact-band normal of that leg's pad mesh, not the foot link's own z axis), the horizontal
speed of the contact point itself (`v_com + w x r`, not the body's centre of mass, which moves even while
a pad rolls without slipping), the swept joint's target/actual/torque, and the largest contact force on a
body that is not a foot -- read with self collisions on, since the versioned config ships them off and a
zero force there would otherwise prove nothing.

What it still cannot say: the torque is reconstructed from the joint's own Kp/Kd (there is no torque
sensor on this asset), and "collision" means an unexpected contact *force*, not a mesh intersection.

Usage:
    python rl_exp/tools/diagnose/stance_step_probe.py --headless [--leg lf] [--joint hip]
        [--amplitude 0.15] [--steps 120] [--settle 400]
    python rl_exp/tools/diagnose/stance_step_probe.py --headless --usd rl_exp/assets/lizard2_candidate/
        lizard2_candidate.usda --urdf rl_exp/lizard2_candidate/lizard2_candidate.urdf
"""

import argparse
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parent))                 # diag_metrics
sys.path.insert(0, str(_HERE.parents[3]))             # rl_exp.tools.verify.check_leg_reachability

from isaaclab.app import AppLauncher  # noqa: E402

# Declared-body calibration, resolved before the parser so the default is a real path and its source is
# printable: the literal this replaced named the retired first body, which is P011's failure mode (the
# calibration source and the spawned USD drifting apart silently). Stdlib-only import, so it is safe
# ahead of the app launcher.
from rl_exp.tools.verify.check_leg_reachability import family_urdf as _family_urdf  # noqa: E402

_DEFAULT_URDF, _DEFAULT_URDF_SOURCE = _family_urdf(_HERE.parents[2], "lizard2")

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--task", default="Lizard2-Flat-Play-v2",
                    help="a PLAY task: no randomization, no policy. It supplies the cfg shape only -- "
                         "--usd replaces the asset it spawns, so a candidate asset can be measured "
                         "without touching a frozen one")
parser.add_argument("--usd", default=None,
                    help="USD to spawn instead of the task's own asset (e.g. an isolated candidate USD)")
parser.add_argument("--urdf", default=str(_DEFAULT_URDF),
                    help="URDF the sole calibration is read from (pad mesh + contact-band normal); defaults "
                         "to the body this family declares and the header prints which file was read. Pass "
                         "the candidate's URDF together with its --usd when they are not the same body")
parser.add_argument("--drop-joints", default="kfe,foot",
                    help="comma-separated joint suffixes taken OFF the action interface, so their drives "
                         "only hold the version's default target")
parser.add_argument("--self-collision", default="on", choices=("on", "off"),
                    help="the versioned config ships it off; a collision reading needs it on")
parser.add_argument("--leg", default="lf", choices=("lf", "rf", "rl", "rr"), help="leg whose joint is ramped")
parser.add_argument("--joint", default="hip", choices=("hip", "haa", "hfe", "kfe", "foot"),
                    help="joint token of that leg; hip is the fore-aft stride axis")
parser.add_argument("--amplitude", type=float, default=0.15, help="half-range of the ramp [rad]")
parser.add_argument("--steps", type=int, default=120, help="control steps per ramp direction")
parser.add_argument("--settle", type=int, default=400, help="control steps of default-target holding first")
parser.add_argument("--contact-n", type=float, default=5.0, help="force [N] above which a foot is loaded")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
simulation_app = AppLauncher(args_cli).app

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402

import isaaclab_tasks  # noqa: F401,E402
from isaaclab.utils.math import quat_apply  # noqa: E402
from isaaclab.utils.string import string_to_callable  # noqa: E402

import diag_metrics  # noqa: E402  (same directory: the sole/slip readers gait_probe uses)
from rl_exp.tools.verify import check_leg_reachability as reach  # noqa: E402  (calibrated sole normal)

GRAVITY = 9.80665

cfg = string_to_callable(gym.spec(args_cli.task).kwargs["env_cfg_entry_point"])()
cfg.scene.num_envs = 1
if args_cli.usd:
    cfg.scene.robot.spawn.usd_path = str(pathlib.Path(args_cli.usd).resolve())
cfg.scene.robot.spawn.articulation_props.enabled_self_collisions = args_cli.self_collision == "on"

# Taking a joint off the action interface leaves its drive holding the version's default target, which is
# what "the channel is gone" means physically. The term's scale may be one number for the whole group or
# one per joint, so it is filtered with the same mask.
DROP = tuple("_%s_joint" % token for token in args_cli.drop_joints.split(",") if token)
for _group in ("legs", "spine"):
    _term = getattr(cfg.actions, "joint_pos_%s" % _group)
    if isinstance(_term.joint_names, str):
        raise SystemExit("action term joint_pos_%s carries the regex %r, so --drop-joints cannot filter "
                         "it; this probe needs a version that declares its joint list" % (_group, _term.joint_names))
    _names = [name for name in _term.joint_names if not name.endswith(DROP)]
    if len(_names) == len(_term.joint_names):
        continue
    if hasattr(_term.scale, "__len__") and not isinstance(_term.scale, str):
        _term.scale = [_term.scale[i] for i, name in enumerate(_term.joint_names) if not name.endswith(DROP)]
    _term.joint_names = _names

URDF = pathlib.Path(args_cli.urdf).resolve()
URDF_SOURCE = _DEFAULT_URDF_SOURCE if URDF == _DEFAULT_URDF.resolve() else "--urdf override"
PAD_NORMAL = {leg: torch.tensor(reach.pad_normal_in_link(URDF, leg), dtype=torch.float32)
              for leg in ("lf", "rf", "rl", "rr")}
PAD_CLOUDS = diag_metrics.pad_point_clouds([diag_metrics.mesh_vertices(reach.pad_mesh(URDF, leg))
                                            for leg in ("lf", "rf", "rl", "rr")])
env = gym.make(args_cli.task, cfg=cfg)
env.reset()
robot = env.unwrapped.scene["robot"]
sensor = env.unwrapped.scene["contact_forces"]
manager = env.unwrapped.action_manager
step_dt = env.unwrapped.step_dt

joint_names = list(robot.joint_names)
body_names = list(robot.data.body_names)
_DEVICE = robot.data.body_pos_w.torch.device
PAD_CLOUDS = PAD_CLOUDS.to(_DEVICE)  # the clouds are read from files, so they start on the CPU
PAD_NORMAL = {leg: value.to(_DEVICE) for leg, value in PAD_NORMAL.items()}
foot_names = [name for name in body_names if name.endswith("_foot")]
foot_ids = [body_names.index(name) for name in foot_names]
non_foot_ids = [i for i in range(len(body_names)) if body_names[i] not in foot_names]
target_joint = "%s_%s_joint" % (args_cli.leg, args_cli.joint)
if target_joint not in joint_names:
    raise SystemExit("task %s has no joint %s (joints: %s)" % (args_cli.task, target_joint, joint_names))
target_index = joint_names.index(target_joint)

print("ASSET %s (task %s) | self_collision=%s | step_dt=%.4f s | joints=%d | action_dim=%d" % (
    cfg.scene.robot.spawn.usd_path, args_cli.task, args_cli.self_collision, step_dt, len(joint_names),
    manager.total_action_dim))
print("CALIBRATION %s [body from: %s] | pad contact-band normals loaded for %s"
      % (URDF, URDF_SOURCE, " ".join(sorted(PAD_NORMAL))))
print("RAMP %s continuously 0 -> +A -> 0 -> -A -> 0 (%d steps per leg of the triangle), A=%.3f rad = %.1f deg"
      % (target_joint, args_cli.steps, args_cli.amplitude, torch.rad2deg(torch.tensor(args_cli.amplitude))))

actions = torch.zeros(1, manager.total_action_dim)
offset = 0
carried = {}
for term_name in manager.active_terms:
    term = manager.get_term(term_name)
    scale = float(torch.as_tensor(term._scale).reshape(-1)[0])
    uses_default = bool(getattr(term, "use_default_offset", False))
    for position, name in enumerate(term._joint_names):
        carried[name] = (term_name, offset + position, scale, uses_default)
    offset += len(term._joint_names)

if target_joint not in carried:
    raise SystemExit(
        "%s is not on the action interface of this task, so its target cannot be ramped through it. "
        "Commanded joints: %s" % (target_joint, sorted(carried)))
_term, _column, _scale, _uses_default = carried[target_joint]
default = robot.data.default_joint_pos.torch
print("ACTION %s -> term=%s column=%d scale=%.4f use_default_offset=%s" % (
    target_joint, _term, _column, _scale, _uses_default))
print("CARRIED leg joints: %s" % " ".join(sorted(n for n in carried if "_hip_joint" in n or "_haa_joint" in n
                                                 or "_hfe_joint" in n or "_kfe_joint" in n or "_foot_joint" in n)))
print("UNCOMMANDED leg joints (PD holds their default target): %s" % " ".join(
    sorted(n for n in joint_names if any(n.endswith("_%s_joint" % t) for t in ("hip", "haa", "hfe", "kfe", "foot"))
           and n not in carried)))


def set_target(angle):
    """Write one joint's absolute target through the action interface (group scale + default offset)."""
    base = float(default[0, target_index]) if _uses_default else 0.0
    actions[0, _column] = (angle - base) / _scale


def sole_tilt_deg():
    """Each pad's calibrated contact-band normal, tilted off the world's down [deg].

    Not the foot link's own z axis: the asset's sole is a curved cap whose normal sits ~1.45 deg off
    that axis, so a link reading cannot be called "level" without this calibration.
    """
    quat = robot.data.body_quat_w.torch[0]
    normals = torch.stack([PAD_NORMAL[name[:2]] for name in foot_names])
    world = quat_apply(quat[foot_ids], normals)
    return torch.rad2deg(torch.acos((-world[:, 2]).clamp(-1.0, 1.0)))


def contact_speed():
    """Horizontal speed of the contact point itself [m/s]: the pad's lowest vertex, not its centre.

    ``v = v_com + w x r`` -- a pad rolling without slipping slides zero at the contact while its centre
    moves, so a centre-of-mass speed is not a slip reading.
    """
    data = robot.data
    lowest = diag_metrics.mesh_lowest_point(data.body_pos_w.torch, data.body_quat_w.torch,
                                            foot_ids, PAD_CLOUDS)[0]
    velocity = diag_metrics.contact_point_velocity(
        data.body_com_lin_vel_w.torch[:, foot_ids], data.body_ang_vel_w.torch[:, foot_ids],
        data.body_com_pos_w.torch[:, foot_ids], lowest)[0]
    return velocity[:, :2].norm(dim=-1)


def sample():
    forces = sensor.data.net_forces_w.torch[0]
    tilt = sole_tilt_deg()
    speed = contact_speed()
    torque = (robot.data.joint_stiffness.torch[0] * (robot.data.joint_pos_target.torch[0]
              - robot.data.joint_pos.torch[0]) - robot.data.joint_damping.torch[0] * robot.data.joint_vel.torch[0])
    return {
        "base_z": float(robot.data.root_pos_w.torch[0, 2]),
        "foot_fz": [float(forces[i][2]) for i in foot_ids],
        "tilt": [float(tilt[i]) for i in range(len(foot_ids))],
        "slip": [float(speed[i]) for i in range(len(foot_ids))],
        "body_force": float(forces[non_foot_ids, :].norm(dim=-1).max()),
        "worst_body": body_names[non_foot_ids[int(forces[non_foot_ids, :].norm(dim=-1).argmax())]],
        "joint": (float(robot.data.joint_pos_target.torch[0, target_index]),
                  float(robot.data.joint_pos.torch[0, target_index]),
                  float(robot.data.joint_vel.torch[0, target_index]),
                  float(torque[target_index])),
    }


def line(tag, when, s):
    print("%-8s t=%+6.2fs base_z=%.4f | fz=[%s] | tilt=[%s] deg | slip=[%s] m/s | swept q=%.3f/%.3f tau=%+.2f Nm"
          " | nonfoot max=%.2f N (%s)"
          % (tag, when, s["base_z"], " ".join("%6.1f" % v for v in s["foot_fz"]),
             " ".join("%5.2f" % v for v in s["tilt"]), " ".join("%5.3f" % v for v in s["slip"]),
             s["joint"][0], s["joint"][1], s["joint"][3], s["body_force"], s["worst_body"]), flush=True)

print("=== SETTLE (default targets held) ===")
clock = 0
with torch.inference_mode():
    for _ in range(args_cli.settle):
        env.step(actions)
        clock += 1
settled = sample()
line("settled", clock * step_dt, settled)
print("  implied mass from the four feet = %.2f kg" % (sum(settled["foot_fz"]) / GRAVITY))
print("  feet order: %s | sole normals calibrated from %s" % (foot_names, URDF))

print("=== RAMP %s (continuous triangle, every control step sampled) ===" % target_joint)
ramp = []
every = max(1, args_cli.steps // 6)
with torch.inference_mode():
    for phase in range(4):
        for step in range(args_cli.steps + 1):
            fraction = step / float(args_cli.steps)
            shape = (fraction, 1.0 - fraction, -fraction, fraction - 1.0)[phase]
            set_target(args_cli.amplitude * shape)
            env.step(actions)
            clock += 1
            state = sample()
            state["phase"] = phase
            state["fraction"] = fraction
            ramp.append(state)
            if step % every == 0 or step == args_cli.steps:
                line("ramp %d.%d" % (phase, int(round(fraction * 9))), clock * step_dt, state)

print("=== VERDICT ===")
steady = [s for s in ramp if 0.1 <= s["fraction"] <= 0.9]  # turnarounds are transient, not lag evidence
liftoff = sum(1 for s in ramp for i in range(len(foot_ids)) if s["foot_fz"][i] <= args_cli.contact_n)
print("  contact: four-foot sum %.1f..%.1f N | min per foot %s | %d of %d foot-samples at or below %.1f N"
      % (min(sum(s["foot_fz"]) for s in ramp), max(sum(s["foot_fz"]) for s in ramp),
         " ".join("%.1f" % min(s["foot_fz"][i] for s in ramp) for i in range(len(foot_ids))),
         liftoff, len(ramp) * len(foot_ids), args_cli.contact_n))
print("  base height: %.4f..%.4f m (drift %+.4f m)" % (min(s["base_z"] for s in ramp),
                                                      max(s["base_z"] for s in ramp),
                                                      ramp[-1]["base_z"] - settled["base_z"]))
print("  sole tilt off level [deg] per foot (%s): %s (settled %s)"
      % (" ".join(foot_names), " ".join("%.2f..%.2f" % (min(s["tilt"][i] for s in ramp),
                                                         max(s["tilt"][i] for s in ramp))
                                        for i in range(len(foot_ids))),
         " ".join("%.2f" % v for v in settled["tilt"])))
loaded = [(s, i) for s in ramp for i in range(len(foot_ids)) if s["foot_fz"][i] > args_cli.contact_n]
print("  contact-point horizontal speed of a loaded foot: max %.4f m/s over %d loaded samples"
      % (max((s["slip"][i] for s, i in loaded), default=0.0), len(loaded)))
print("  non-foot contact force: max %.2f N on %s (self collisions %s; a zero here proves nothing if off)"
      % (max(s["body_force"] for s in ramp), max(ramp, key=lambda s: s["body_force"])["worst_body"],
         args_cli.self_collision))
print("  swept joint, steady window only (%d samples): target %.3f..%.3f rad, tracking error max %.4f rad, "
      "torque %.2f..%.2f Nm" % (len(steady), min(s["joint"][0] for s in steady),
                                max(s["joint"][0] for s in steady),
                                max(abs(s["joint"][0] - s["joint"][1]) for s in steady),
                                min(s["joint"][3] for s in steady), max(s["joint"][3] for s in steady)))
print("  (torque is Kp*(target-actual) - Kd*vel reconstructed from this asset's own gains, not measured)")

env.close()
simulation_app.close()
