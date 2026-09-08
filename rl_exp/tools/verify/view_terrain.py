# -*- coding: utf-8 -*-
"""View the lizard standing on a recipe version's actual terrain (pre-training eyeball check).

GUI by default: zero actions, no randomization (PLAY wiring), so the
sole-vs-bump scale is directly readable. Ctrl+C to quit. With --steps N the
script auto-exits after N steps -- use --headless --steps for smoke checks.
To view a trained policy on a terrain, use the standard play script instead.

Also draws one red head-arrow per env (absorbed from view_head_arrow): a
cuboid shaft + two angled chevron arms floating 1.9 m above the root,
pointing along base +X -- which since v8 is the anatomical head (the sphere).
The arrow re-tracks the robot every step, so it stays correct across resets
(random spawn yaw). No cone, so no USD axis ambiguity: every piece is long-X
and rotated about Z in the body frame. Quaternion convention: IsaacLab math
is (w,x,y,z); the marker backend wants (x,y,z,w) -- converted once at the
boundary.

Also injects a robot-vs-terrain contact-point probe and reports the count
against the collision stack budget under test -- the v4 re-test of the stock
2**26 (v3.6.1 had raised it to 2**28, suspected of masking a terrain
contact-density root cause; contact points are the pressure proxy for the
narrowphase stack).

Usage:
  python view_terrain.py --viz kit                                   # flat (default)
  python view_terrain.py --viz kit --task Lizard-Rough-Play-v4       # v4 rubble
  python view_terrain.py --viz kit --task Lizard-Rough-Play-v8 --num-envs 4  # arrow vs ball/antenna
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
from isaaclab.markers import VisualizationMarkers  # noqa: E402
from isaaclab.markers.visualization_markers_cfg import VisualizationMarkersCfg  # noqa: E402
from isaaclab.sim.spawners.materials.visual_materials_cfg import PreviewSurfaceCfg  # noqa: E402
from isaaclab.sim.spawners.shapes.shapes_cfg import CuboidCfg  # noqa: E402
from isaaclab.utils.math import quat_apply, quat_from_euler_xyz, quat_mul  # noqa: E402

CONTACT_PROBE = "terrain_contact_probe"

# arrow geometry, body frame (x=head, y=left, z=up), all lengths in m
SHAFT_LEN = 2.4
ARM_LEN = 0.45
THICK = 0.07
HOVER_Z = 1.9  # arrow base height above the root
_ARM_C = ARM_LEN * 0.5 * 0.70710678  # arm center offset along the chevron direction

RED = PreviewSurfaceCfg(diffuse_color=(1.0, 0.1, 0.05))

marker_cfg = VisualizationMarkersCfg(
    prim_path="/Visuals/HeadArrow",
    markers={
        "shaft": CuboidCfg(size=(SHAFT_LEN, THICK, THICK), visual_material=RED),
        "arm": CuboidCfg(size=(ARM_LEN, THICK, THICK), visual_material=RED),
    },
)

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

robot = env.unwrapped.scene["robot"]
markers = VisualizationMarkers(marker_cfg)

num_envs = env.unwrapped.num_envs
action_dim = env.unwrapped.action_manager.total_action_dim
actions = torch.zeros(num_envs, action_dim)

probe = env.unwrapped.scene[CONTACT_PROBE]
sim_dt = env.unwrapped.sim.get_physics_dt()

# per-env arrow piece offsets/quats in the body frame
_shaft_off = torch.tensor([[SHAFT_LEN * 0.5, 0.0, 0.0]], device=robot.device).repeat(num_envs, 1)
_arm_off_l = torch.tensor([[SHAFT_LEN - _ARM_C, _ARM_C, 0.0]], device=robot.device).repeat(num_envs, 1)
_arm_off_r = torch.tensor([[SHAFT_LEN - _ARM_C, -_ARM_C, 0.0]], device=robot.device).repeat(num_envs, 1)
_hover = torch.tensor([0.0, 0.0, HOVER_Z], device=robot.device)
_dev = robot.device
_arm_l_quat = quat_from_euler_xyz(torch.tensor(0.0, device=_dev), torch.tensor(0.0, device=_dev),
                                  torch.tensor(torch.pi * 0.75, device=_dev))  # 135 deg
_arm_r_quat = quat_from_euler_xyz(torch.tensor(0.0, device=_dev), torch.tensor(0.0, device=_dev),
                                  torch.tensor(-torch.pi * 0.75, device=_dev))
_idx = torch.tensor([0, 1, 1] * num_envs, dtype=torch.int32, device=robot.device)


def wxyz_to_xyzw(q):
    return torch.cat([q[:, 1:4], q[:, :1]], dim=-1)


def update_arrow():
    root_pos = robot.data.root_pos_w.torch[:, :3]
    root_quat = robot.data.root_quat_w.torch
    base = root_pos + _hover
    translations = torch.stack([
        base + quat_apply(root_quat, _shaft_off),
        base + quat_apply(root_quat, _arm_off_l),
        base + quat_apply(root_quat, _arm_off_r),
    ], dim=1).reshape(3 * num_envs, 3)
    shaft_q = root_quat
    arm_l_q = quat_mul(root_quat, _arm_l_quat.expand(num_envs, 4))
    arm_r_q = quat_mul(root_quat, _arm_r_quat.expand(num_envs, 4))
    orientations = wxyz_to_xyzw(torch.stack([shaft_q, arm_l_q, arm_r_q], dim=1).reshape(3 * num_envs, 4))
    markers.visualize(translations=translations, orientations=orientations, marker_indices=_idx)


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
        update_arrow()
        step += 1
        if step % args_cli.report_every == 0:
            pts = contact_points_total()
            reports += 1
            points_sum += pts
            points_max = max(points_max, pts)
            print(f"[contact check] step {step}: {pts} contact points "
                  f"({pts / num_envs:.1f}/env | max {points_max / num_envs:.1f}/env)")
        if step % 100 == 0:
            head_w = quat_apply(robot.data.root_quat_w.torch,
                                torch.tensor([1.0, 0.0, 0.0], device=robot.device).expand(num_envs, 3))
            print("[head] step %d | env0 head dir (world) = (%+.2f, %+.2f, %+.2f)"
                  % (step, head_w[0, 0], head_w[0, 1], head_w[0, 2]))
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
