# -*- coding: utf-8 -*-
"""Does the stance survive its own default targets? Static load, then one small fore-aft step.

The v3 decision drops the ankle joints (`kfe`/`foot`) from the policy's action interface and leaves them
to PD at the version's default target. The question that decision creates is physical, not geometric: a
level sole in the default *pose* says nothing about the sole once an upstream joint moves, because the
pad still rides the chain. This probe reads that on the frozen asset, with no policy and no checkpoint:

  1. **settle** -- every joint at its default target. An all-zero action means exactly that, so this is
     already the v3 situation for `kfe`/`foot`: not commanded, only PD-held.
  2. **small fore-aft step** -- one joint's target ramped out and back at the physics step rate, so
     contact, slip and torque are read while the leg carries load.

Per sample it prints base height, each foot's contact force, the pad's tilt off level, the horizontal
speed of every *loaded* foot (the slip proxy), the swept joint's target/actual/torque, and the largest
contact force on a body that is not a foot.

What it cannot say: the torque is reconstructed from the joint's own Kp/Kd (there is no torque sensor on
this asset), and "collision" here means an unexpected contact *force*, not a mesh intersection -- the
full mesh-level collision check is a different piece of work. Read the numbers with those two limits.

Usage:
    python rl_exp/tools/diagnose/stance_step_probe.py --headless [--leg lf] [--joint hip]
        [--amplitude 0.15] [--steps 120] [--settle 400] [--report-every 20]
"""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from isaaclab.app import AppLauncher  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--task", default="Lizard2-Flat-Play-v2",
                    help="a PLAY task: no randomization, no policy. Defaults to v2, the version the "
                         "v3 ankle-channel decision builds on (v1 commands all 30 joints, so a v1 run "
                         "would not reproduce the interface under test)")
parser.add_argument("--leg", default="lf", choices=("lf", "rf", "rl", "rr"), help="leg whose joint is ramped")
parser.add_argument("--joint", default="hip", choices=("hip", "haa", "hfe", "kfe", "foot"),
                    help="joint token of that leg; hip is the fore-aft stride axis")
parser.add_argument("--amplitude", type=float, default=0.15, help="half-range of the ramp [rad]")
parser.add_argument("--steps", type=int, default=120, help="control steps per ramp direction")
parser.add_argument("--settle", type=int, default=400, help="control steps of default-target holding first")
parser.add_argument("--report-every", type=int, default=20, help="control steps between printed samples")
parser.add_argument("--contact-n", type=float, default=5.0, help="force [N] above which a foot is loaded")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
simulation_app = AppLauncher(args_cli).app

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402

import isaaclab_tasks  # noqa: F401,E402
from isaaclab.utils.string import string_to_callable  # noqa: E402

import diag_metrics  # noqa: E402  (same directory: the pose/sole readers gait_probe uses)

GRAVITY = 9.80665

cfg = string_to_callable(gym.spec(args_cli.task).kwargs["env_cfg_entry_point"])()
cfg.scene.num_envs = 1
env = gym.make(args_cli.task, cfg=cfg)
env.reset()
robot = env.unwrapped.scene["robot"]
sensor = env.unwrapped.scene["contact_forces"]
manager = env.unwrapped.action_manager
step_dt = env.unwrapped.step_dt

joint_names = list(robot.joint_names)
body_names = list(robot.data.body_names)
foot_names = [name for name in body_names if name.endswith("_foot")]
foot_ids = [body_names.index(name) for name in foot_names]
non_foot_ids = [i for i in range(len(body_names)) if body_names[i] not in foot_names]
target_joint = "%s_%s_joint" % (args_cli.leg, args_cli.joint)
if target_joint not in joint_names:
    raise SystemExit("task %s has no joint %s (joints: %s)" % (args_cli.task, target_joint, joint_names))
target_index = joint_names.index(target_joint)

print("TASK %s | step_dt=%.4f s | joints=%d | action_dim=%d" % (
    args_cli.task, step_dt, len(joint_names), manager.total_action_dim))
print("RAMP %s over %d steps per direction, amplitude %.3f rad (+/- %.1f deg)" % (
    target_joint, args_cli.steps, args_cli.amplitude, torch.rad2deg(torch.tensor(args_cli.amplitude))))

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


def sample():
    forces = sensor.data.net_forces_w.torch[0]
    quat = robot.data.body_quat_w.torch
    down_in_link = diag_metrics.body_down_in_link(quat, foot_ids)[0]
    tilt = torch.rad2deg(torch.acos((-down_in_link[:, 2]).clamp(-1.0, 1.0)))
    speed = robot.data.body_com_lin_vel_w.torch[0, foot_ids, :2].norm(dim=-1)
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
with torch.inference_mode():
    for _ in range(args_cli.settle):
        env.step(actions)
settled = sample()
line("settled", 0.0, settled)
print("  implied mass from the four feet = %.2f kg" % (sum(settled["foot_fz"]) / GRAVITY))
print("  feet order: %s" % foot_names)

print("=== RAMP %s ===" % target_joint)
ramp = []
with torch.inference_mode():
    for direction in (1.0, -1.0, 0.0):
        for step in range(args_cli.steps + 1):
            fraction = step / float(args_cli.steps)
            set_target(args_cli.amplitude * direction * fraction)
            env.step(actions)
            if step % args_cli.report_every == 0 or step == args_cli.steps:
                s = sample()
                ramp.append(s)
                line("ramp %+d" % int(direction), (len(ramp)) * args_cli.report_every * step_dt, s)

print("=== VERDICT ===")
loaded = [(s, i) for s in ramp for i in range(len(foot_ids)) if s["foot_fz"][i] > args_cli.contact_n]
print("  contact: the four feet carried %.1f..%.1f N (min per foot %s)"
      % (min(sum(s["foot_fz"]) for s in ramp), max(sum(s["foot_fz"]) for s in ramp),
         " ".join("%.1f" % min(s["foot_fz"][i] for s in ramp) for i in range(len(foot_ids)))))
print("  slip: max horizontal speed of a loaded foot = %.4f m/s (%d loaded samples, %.2f N threshold)"
      % (max((s["slip"][i] for s, i in loaded), default=0.0), len(loaded), args_cli.contact_n))
print("  base height: %.4f..%.4f m (drift %+.4f m)" % (min(s["base_z"] for s in ramp),
                                                      max(s["base_z"] for s in ramp),
                                                      ramp[-1]["base_z"] - settled["base_z"]))
print("  pad tilt off level: %s deg (was %s settled)"
      % (" ".join("%.2f..%.2f" % (min(s["tilt"][i] for s in ramp), max(s["tilt"][i] for s in ramp))
                  for i in range(len(foot_ids))), " ".join("%.2f" % v for v in settled["tilt"])))
print("  non-foot contact: max %.2f N on %s (settled: %.2f N)"
      % (max(s["body_force"] for s in ramp),
         max(ramp, key=lambda s: s["body_force"])["worst_body"], settled["body_force"]))
print("  swept joint: target %.3f..%.3f rad, tracking error max %.4f rad, torque %.2f..%.2f Nm"
      % (min(s["joint"][0] for s in ramp), max(s["joint"][0] for s in ramp),
         max(abs(s["joint"][0] - s["joint"][1]) for s in ramp),
         min(s["joint"][3] for s in ramp), max(s["joint"][3] for s in ramp)))
print("  (torque is Kp*(target-actual) - Kd*vel reconstructed from this asset's own gains, not measured)")

env.close()
simulation_app.close()
