# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""One guided two-foot lift trial with per-substep ground and joint samples."""

import argparse
import json
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--usd", type=Path, required=True)
parser.add_argument("--ik", type=Path, required=True)
parser.add_argument("--precheck", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
parser.add_argument("--offset", type=Path, help="JSON {joint: rad} added to every PD target (preload diagnostic)")
parser.add_argument("--height_m", type=float, default=0.02, help="target body rise [m], multiple of 5 mm")
parser.add_argument("--steps", type=int, default=2600, help="physics substeps to run (full window is 2600)")
parser.add_argument("--video", type=Path, help="Record this physical run; requires cameras enabled")
parser.add_argument("--eye", type=float, nargs=3, default=(0., -5., 1.5), help="Video camera position [m]")
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
if args.out.exists() or (args.video and args.video.exists()):
    parser.error("output already exists")
app = AppLauncher(args).app
rows, metadata = [], {}
try:
    import numpy as np
    import torch
    import warp as wp
    import gymnasium as gym
    from pxr import Usd, UsdPhysics
    from isaaclab.utils.string import string_to_callable
    from isaaclab_tasks.utils.hydra import resolve_presets
    from isaaclab_physx.physics import PhysxManager
    import rl_exp.tasks  # noqa: F401
    from ablation_harness.components.dr_controller import apply_eval_mode
    from rl_exp.tools.runrecord.binding import sha256_file
    from rl_exp.tools.diagnose.palm_spatial_runtime import pair_binding

    settings = {"dt_s": 0.005, "settle_s": 5., "rise_s": 2., "hold_s": 2., "return_s": 2.,
                "recover_s": 2., "height_m": args.height_m, "wall_s": 900., "forbidden_contact_n": 5.,
                "guide_vertical_force_n": 5., "max_error_rad": 0.35, "max_drop_m": 0.15,
                "speed_fraction": 0.5, "minimum_foot_n": 5.}
    ik = json.loads(args.ik.read_text(encoding="utf-8"))
    precheck = json.loads(args.precheck.read_text(encoding="utf-8"))
    config = json.loads(args.precheck.with_name("config.json").read_text(encoding="utf-8"))
    if precheck["status"] != "pass" or precheck["lift_input"]["ik_sha256"] != sha256_file(args.ik):
        raise ValueError("precheck did not pass for this IK input")
    nodes = round(args.height_m / 0.005)
    if nodes < 1 or abs(nodes * 0.005 - args.height_m) > 1e-9 or len(ik["samples"]) < nodes + 1:
        raise ValueError("height must be a multiple of 5 mm covered by the IK samples")
    if any(not s["passed"] for s in ik["samples"][:nodes + 1]):
        raise ValueError("every trajectory node up to the target height must pass")
    if [round(s["root_rise_m"], 6) for s in ik["samples"][:nodes + 1]] != [round(.005 * i, 6) for i in range(nodes + 1)]:
        raise ValueError("unexpected height nodes")
    covered = {c["id"] for c in config["tasks"]["cases"]}
    if not {f"sample_{i}" for i in range(nodes + 1)} | {f"sample_{i}_mid" for i in range(nodes)} <= covered:
        raise ValueError("precheck does not cover every node and midpoint up to the target height")
    if not args.usd.resolve().is_relative_to((ROOT / "rl_exp/out").resolve()):
        raise ValueError("guided asset must be isolated")
    metadata = {"settings": settings, "ik": str(args.ik.resolve()), "ik_sha256": sha256_file(args.ik),
                "precheck_sha256": sha256_file(args.precheck), "usd_sha256": sha256_file(args.usd),
                "scope": "v6 guided diagnostic, not free walking or hardware validation"}
    spec = gym.spec("Lizard2-Flat-Play-v6")
    cfg = resolve_presets(string_to_callable(spec.kwargs["env_cfg_entry_point"])())
    cfg.scene.num_envs, cfg.seed = 1, 123
    apply_eval_mode(cfg, "nominal")
    cfg.scene.robot.spawn.usd_path = str(args.usd.resolve())
    cfg.scene.robot.init_state.pos = (0., 0., config["tasks"]["cases"][0]["root_transform"][2][3])
    cfg.scene.robot.init_state.joint_pos = dict(ik["samples"][0]["q_rad"], lift_vertical_joint=0.)
    if args.video:
        cfg.viewer.eye = tuple(args.eye)
        cfg.viewer.lookat = (-0.35, 0., 0.45)
    env = gym.make("Lizard2-Flat-Play-v6", cfg=cfg, render_mode="rgb_array" if args.video else None)
    live, robot = env.unwrapped, env.unwrapped.scene["robot"]
    env.reset()
    names, bodies = list(robot.joint_names), list(robot.body_names)
    controlled = list(ik["samples"][0]["q_rad"])
    if set(names) != set(controlled) | {"lift_vertical_joint"}:
        raise ValueError("runtime joints differ from bound input")
    ids = [names.index(n) for n in controlled]
    base_index = bodies.index("base_link")
    guide_index = names.index("lift_vertical_joint")
    initial = np.array([ik["samples"][0]["q_rad"][n] for n in controlled])
    offset_map = json.loads(args.offset.read_text(encoding="utf-8")) if args.offset else {}
    if set(offset_map) - set(controlled):
        raise ValueError("offset names a joint that is not controlled")
    offset = np.array([offset_map.get(n, 0.) for n in controlled])
    metadata.update(offset=offset_map, steps=args.steps)
    backend = lambda value: wp.to_torch(value)[0].cpu().numpy().copy()
    if np.max(np.abs(robot.data.joint_pos.torch[0, ids].cpu().numpy() - initial)) > 1e-5:
        raise ValueError("reset did not produce the intended initial posture")
    limits = backend(robot.root_view.get_dof_max_velocities())
    metadata.update(joints=names, bodies=bodies, support=ik["support"], velocity_limits=limits.tolist(),
                    stiffness=backend(robot.root_view.get_dof_stiffnesses()).tolist(),
                    damping=backend(robot.root_view.get_dof_dampings()).tolist(),
                    effort_limits=backend(robot.root_view.get_dof_max_forces()).tolist())
    ground = live.sim.stage.GetPrimAtPath(cfg.scene.terrain.prim_path)
    floors = [p for p in Usd.PrimRange(ground) if p.HasAPI(UsdPhysics.CollisionAPI)]
    if len(floors) != 1:
        raise ValueError("expected exactly one floor")
    views, pair_paths = {}, {}
    for prim in live.sim.stage.Traverse():
        if prim.HasAPI(UsdPhysics.RigidBodyAPI) and prim.GetName() in bodies and any(
                p.HasAPI(UsdPhysics.CollisionAPI) for p in Usd.PrimRange(prim)):
            view = PhysxManager.get_physics_sim_view().create_rigid_contact_view(
                str(prim.GetPath()), filter_patterns=[str(floors[0].GetPath())], max_contact_data_count=256)
            if view.sensor_count != 1 or view.filter_count != 1:
                raise ValueError("unexpected ground pair view")
            pair_binding(view.sensor_paths, view.filter_paths, str(prim.GetPath()),
                         [str(floors[0].GetPath())], (1, 1, 3))
            views[prim.GetName()] = view
            pair_paths[prim.GetName()] = {"sensors": view.sensor_paths, "filters": view.filter_paths}
    if not set(ik["support"]) <= set(views):
        raise ValueError("missing support contact views")
    metadata["ground_bodies"] = list(views)
    metadata["ground_pair_paths"] = pair_paths
    writer = None
    if args.video:
        import imageio.v2 as imageio
        from PIL import Image, ImageDraw
        preview = None
        for _ in range(40):
            live.sim.render()
            preview = env.render()
            if preview is not None and np.asarray(preview).mean() > 1.:
                break
        if preview is None or np.asarray(preview).mean() <= 1.:
            raise RuntimeError("camera failed warmup before physical sampling")
        args.video.parent.mkdir(parents=True, exist_ok=True)
        writer = imageio.get_writer(str(args.video), fps=20, codec="libx264", macro_block_size=16)
        metadata["video"] = {"path": str(args.video.resolve()), "fps": 20, "copies_per_substep": 8,
                             "scope": "camera frames captured during physical run; no interpolation"}
    start_z = float(robot.data.body_link_pose_w.torch[0, base_index, 2])
    started, reason, desired = time.monotonic(), None, initial.copy()
    for step in range(1, args.steps + 1):
        t = step * settings["dt_s"]
        if (step - 1) % 4 == 0:
            u = max(0., min(1., (t - settings["settle_s"]) / settings["rise_s"]))
            if t > 9.:
                u = 1. - max(0., min(1., (t - 9.) / settings["return_s"]))
            u = 10*u**3 - 15*u**4 + 6*u**5
            position = min(u * nodes, float(nodes))
            index = min(int(position), nodes - 1)
            fraction = position - index
            a, b = ik["samples"][index]["q_rad"], ik["samples"][index + 1]["q_rad"]
            desired = np.array([a[n] + fraction * (b[n] - a[n]) for n in controlled]) + offset
        robot.set_joint_position_target(torch.tensor(desired, device=live.device, dtype=torch.float32).unsqueeze(0), joint_ids=ids)
        live.scene.write_data_to_sim()
        actual_target = backend(robot.root_view.get_dof_position_targets())
        velocity_target = backend(robot.root_view.get_dof_velocity_targets())
        if np.max(np.abs(actual_target[ids] - desired)) > 1e-5 or np.max(np.abs(velocity_target[ids])) > 1e-5:
            raise ValueError("backend target mismatch")
        live.sim.step(render=False)
        live.scene.update(settings["dt_s"])
        q = robot.data.joint_pos.torch[0].cpu().numpy().copy()
        vel = robot.data.joint_vel.torch[0].cpu().numpy().copy()
        pos = robot.data.body_link_pose_w.torch[0, base_index].cpu().numpy().copy()
        ground_forces = {n: wp.to_torch(v.get_contact_force_matrix(dt=settings["dt_s"])).cpu().numpy().reshape(3).tolist() for n, v in views.items()}
        wrench = backend(robot.root_view.get_link_incoming_joint_force())
        effort = backend(robot.root_view.get_dof_projected_joint_forces())
        explicit = backend(robot.root_view.get_dof_actuation_forces())
        sample = {"t_s": t, "q": q.tolist(), "velocity": vel.tolist(), "target": desired.tolist(),
                  "base_pose": pos.tolist(), "ground_forces": ground_forces,
                  "backend_position_target": actual_target.tolist(), "backend_velocity_target": velocity_target.tolist(),
                  "incoming_wrench": wrench.tolist(), "joint_projected_effort": effort.tolist(),
                  "explicit_actuation": explicit.tolist()}
        rows.append(sample)
        if writer is not None:
            live.sim.render()
            frame = env.render()
            if frame is None or np.asarray(frame).mean() <= 1.:
                raise RuntimeError("camera returned an empty frame during physical sampling")
            image = Image.fromarray(np.asarray(frame, dtype=np.uint8))
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, image.width, 58), fill=(0, 0, 0))
            draw.text((10, 6), f"PHYSICAL RUN - t={t:.3f}s - 80x SLOW", fill=(255, 255, 255))
            draw.text((10, 30), "Ground normal force: " + "  ".join(
                f"{label} {ground_forces.get(name,[0,0,0])[2]:.0f}N" for name, label in
                (("lf_wrist", "LF"), ("rf_wrist", "RF"), ("rl_ankle", "LH"), ("rr_ankle", "RH"))), fill=(255, 255, 255))
            for _ in range(8):
                writer.append_data(np.asarray(image))
        forbidden = max((np.linalg.norm(f) for n, f in ground_forces.items() if n not in ik["support"]), default=0.)
        checks = {"nonfinite": not all(np.isfinite(x).all() for x in (q, vel, pos, wrench, effort, explicit)),
                  "wall_budget": time.monotonic() - started > settings["wall_s"],
                  "forbidden_contact": forbidden > settings["forbidden_contact_n"],
                  "joint_error": np.max(np.abs(q[ids] - desired)) > settings["max_error_rad"],
                  "joint_speed": bool(np.any(np.abs(vel[ids]) >= limits[ids] * settings["speed_fraction"])),
                  "base_drop": start_z - pos[2] > settings["max_drop_m"],
                  "guide_force": abs(wrench[base_index, 2]) > settings["guide_vertical_force_n"] or abs(explicit[guide_index]) > 1e-5}
        if step == 1000:
            checks["insufficient_initial_support"] = any(
                np.mean([r["ground_forces"][n][2] for r in rows[-200:]]) < settings["minimum_foot_n"] for n in ik["support"])
        triggered = [n for n, v in checks.items() if v]
        if triggered:
            reason = triggered
            break
    result = {"metadata": metadata, "controlled": controlled, "samples": rows, "stop_reason": reason,
              "completed_full_window": len(rows) == args.steps, "status": "observation_only_pending_audit"}
    if writer is not None:
        writer.close()
        writer = None
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print("GUIDED_TRIAL", json.dumps({"steps": len(rows), "stop": reason, "full": result["completed_full_window"]}), flush=True)
    env.close()
    app.close(exit_code=0 if reason is None else 1)
except BaseException:
    traceback.print_exc()
    if "writer" in locals() and writer is not None:
        writer.close()
    if rows and not args.out.exists():
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as stream:
            json.dump({"metadata": metadata, "samples": rows, "status": "exception", "traceback": traceback.format_exc()}, stream, allow_nan=False)
    sys.stdout.flush()
    sys.stderr.flush()
    app.close(exit_code=1)
    raise
