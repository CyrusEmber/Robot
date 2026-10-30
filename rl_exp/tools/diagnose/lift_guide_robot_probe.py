# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Probe passive guide integration on a robot falling above the floor.

No foot support or lift command is tested. Free-fall COM acceleration is an
indirect guide-force diagnostic; constraint wrench is not directly measured.
"""

import argparse
import json
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--usd", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
if args.out.exists() or not args.usd.resolve().is_relative_to((ROOT / "rl_exp/out").resolve()):
    parser.error("fresh output and an isolated asset under rl_exp/out are required")
app = AppLauncher(args).app
try:
    import gymnasium as gym
    import torch
    import warp as wp
    from isaaclab.utils.string import string_to_callable
    from isaaclab_tasks.utils.hydra import resolve_presets
    import rl_exp.tasks  # noqa: F401
    from ablation_harness.components.dr_controller import apply_eval_mode
    from rl_exp.tools.runrecord.binding import sha256_file

    spec = gym.spec("Lizard2-Flat-Play-v6")
    cfg = resolve_presets(string_to_callable(spec.kwargs["env_cfg_entry_point"])())
    cfg.scene.num_envs, cfg.seed = 1, 123
    apply_eval_mode(cfg, "nominal")
    cfg.scene.robot.spawn.usd_path = str(args.usd.resolve())
    cfg.scene.robot.init_state.pos = (0., 0., 2.)
    env = gym.make("Lizard2-Flat-Play-v6", cfg=cfg)
    live, robot = env.unwrapped, env.unwrapped.scene["robot"]
    env.reset()
    action = torch.zeros((1, live.action_manager.total_action_dim), device=live.device)
    masses = robot.data.body_mass.torch[0].clone()
    body_names = list(robot.body_names)
    if "lift_guide_carrier" in body_names:
        masses[body_names.index("lift_guide_carrier")] = 0.
    base_index = body_names.index("base_link")
    base_joint_index = list(robot.joint_names).index("lift_vertical_joint") if "lift_vertical_joint" in robot.joint_names else None
    samples = []
    done_found = False
    for step in range(11):
        if step:
            live.command_manager.get_term("base_velocity").vel_command_b[:] = 0.
            _, _, terminated, truncated, _ = env.step(action)
            done_found = bool(terminated[0] or truncated[0])
        body_pos = robot.data.body_com_pos_w.torch[0]
        body_vel = robot.data.body_com_vel_w.torch[0, :, :3]
        com = (body_pos * masses[:, None]).sum(0) / masses.sum()
        velocity = (body_vel * masses[:, None]).sum(0) / masses.sum()
        incoming = wp.to_torch(robot.root_view.get_link_incoming_joint_force())[0].cpu()
        applied = wp.to_torch(robot.root_view.get_dof_actuation_forces())[0].cpu()
        samples.append({"step": step, "com_m": com.cpu().tolist(), "com_velocity_m_s": velocity.cpu().tolist(),
                        "root_pose": robot.data.root_link_pose_w.torch[0].cpu().tolist(),
                        "base_pose": robot.data.body_link_pose_w.torch[0, base_index].cpu().tolist(),
                        "guide_base_incoming_wrench": incoming[base_index].tolist(),
                        "guide_explicit_force": None if base_joint_index is None else float(applied[base_joint_index]),
                        "done": done_found})
        if done_found:
            break
    duration = (len(samples) - 1) * live.step_dt
    a = [(samples[-1]["com_velocity_m_s"][i] - samples[0]["com_velocity_m_s"][i]) / duration for i in range(3)]
    m = float(masses.sum())
    inferred_fz = m * (a[2] - cfg.sim.gravity[2])
    report = {"asset": str(args.usd.resolve()), "asset_sha256": sha256_file(args.usd),
              "duration_s": duration, "mass_kg": m, "gravity": cfg.sim.gravity, "joint_names": list(robot.joint_names),
              "body_names": body_names, "fixed_base": bool(robot.is_fixed_base), "com_acceleration_m_s2": a,
              "inferred_fz_n": inferred_fz, "terminated": done_found, "samples": samples,
              "scope": "airborne COM-based inference; no contact, commanded lift or direct fixture-wrench validation"}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    print("GUIDED_ROBOT_PROBE", json.dumps({k: report[k] for k in ("fixed_base", "duration_s", "inferred_fz_n", "terminated")}), flush=True)
    env.close()
    app.close(exit_code=0)
except BaseException:
    traceback.print_exc()
    sys.stdout.flush()
    sys.stderr.flush()
    app.close(exit_code=1)
    raise
