# -*- coding: utf-8 -*-
"""View the lizard standing on a recipe version's actual terrain (pre-training eyeball check).

GUI by default: zero actions, no randomization (PLAY wiring), so the
sole-vs-bump scale is directly readable. Ctrl+C to quit. With --steps N the
script auto-exits after N steps -- use --headless --steps for smoke checks.
To view a trained policy on a terrain, use the standard play script instead.

Also injects a robot-vs-terrain contact-point probe and reports the count
against the collision stack budget under test -- the v4 re-test of the stock
2**26 (v3.6.1 had raised it to 2**28, suspected of masking a terrain
contact-density root cause; contact points are the pressure proxy for the
narrowphase stack).

Usage:
  python view_terrain.py --viz kit                                   # flat (default)
  python view_terrain.py --viz kit --task Lizard-Rough-Play-v4       # v4 rubble
  python view_terrain.py --headless --task Lizard-Rough-Play-v4 --steps 10
"""
import argparse
import importlib

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--task", default="Lizard-Velocity-Flat-Play-v0",
                    help="Registered task id; PLAY variants have no randomization.")
parser.add_argument("--num-envs", type=int, default=4,
                    help="Number of envs (more envs = more sub-terrains visible).")
parser.add_argument("--steps", type=int, default=0,
                    help="Auto-exit after N steps (0 = run until Ctrl+C, GUI mode).")
parser.add_argument("--report-every", type=int, default=50,
                    help="Steps between contact-count reports.")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402
import warp as wp  # noqa: E402

import isaaclab_tasks  # noqa: F401,E402  -- registers the lizard task ids
from isaaclab_physx.sensors import ContactSensorCfg  # noqa: E402

CONTACT_PROBE = "terrain_contact_probe"

# resolve the task's env cfg class from the registry (no per-version map to drift)
spec = gym.spec(args_cli.task)
module_name, class_name = spec.kwargs["env_cfg_entry_point"].split(":")
cfg_cls = getattr(importlib.import_module(module_name), class_name)

cfg = cfg_cls()
cfg.scene.num_envs = args_cli.num_envs
# hold the default pose across resets (same trick view_lizard used on flat)
if hasattr(cfg.events, "reset_robot_joints"):
    cfg.events.reset_robot_joints = None

# collision stack under test (None = PhysX default 2**26). v3.6.1 calibration:
# at 4096 envs the stock stack overflowed and PhysX demanded 67,137,584 bytes
stack = getattr(cfg.sim.physics.default, "gpu_collision_stack_size", None) or 2**26
print(f"[contact check] gpu_collision_stack_size = {stack} bytes ({stack / 1048576:.0f} MiB)"
      f" -- v3.6.1 overflow at 4096 envs needed 67,137,584 bytes")

# robot-vs-terrain contact-point probe. The env's own contact_forces sensor is
# body-mode and cannot do this: track_contact_points requires
# filter_prim_paths_expr (contact_sensor.py:341). Filter paths follow the
# upstream test convention (test_contact_sensor.py:666-670)
_terrain = cfg.scene.terrain
_terrain_filter = (
    [_terrain.prim_path + "/terrain/GroundPlane/CollisionPlane"]
    if _terrain.terrain_type == "plane"
    else [_terrain.prim_path + "/terrain/mesh"]
)
cfg.scene.terrain_contact_probe = ContactSensorCfg(
    prim_path="{ENV_REGEX_NS}/Robot/.*",
    history_length=0,
    track_air_time=False,
    track_contact_points=True,
    filter_prim_paths_expr=_terrain_filter,
    max_contact_data_count_per_prim=64,  # per-env capacity 64 x num_bodies points
)

env = gym.make(args_cli.task, cfg=cfg)
env.reset()

num_envs = env.unwrapped.num_envs
action_dim = env.unwrapped.action_manager.total_action_dim
actions = torch.zeros(num_envs, action_dim)

probe = env.unwrapped.scene[CONTACT_PROBE]
sim_dt = env.unwrapped.sim.get_physics_dt()


def contact_points_total() -> int:
    """Robot-vs-terrain contact points in the last physics step (all envs)."""
    counts = probe.contact_view.get_contact_data(dt=sim_dt)[4]
    return int(wp.to_torch(counts).sum().item())


step = 0
reports = 0
points_sum = 0
points_max = 0
try:
    while simulation_app.is_running():
        with torch.inference_mode():
            env.step(actions)
        step += 1
        if step % args_cli.report_every == 0:
            pts = contact_points_total()
            reports += 1
            points_sum += pts
            points_max = max(points_max, pts)
            print(f"[contact check] step {step}: {pts} contact points "
                  f"({pts / num_envs:.1f}/env | max {points_max / num_envs:.1f}/env)")
        if args_cli.steps and step >= args_cli.steps:
            break
except KeyboardInterrupt:
    pass
if reports:
    print(f"[contact check] summary over {reports} reports: mean {points_sum / reports / num_envs:.1f}/env, "
          f"max {points_max / num_envs:.1f}/env contact points")
    print(f"[contact check] stack under test {stack} bytes; extrapolate points/env to the "
          f"training env count for the v4 stock-2**26 verdict (v3.6.1: 4096 envs overflowed 2**26)")
env.close()
