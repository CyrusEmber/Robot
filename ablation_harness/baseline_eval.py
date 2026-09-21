# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Evaluate baseline's first episode on its own plane for exactly 20 s.

Run with IsaacLab Python after Kit initialization by this entry point. A missing
checkpoint selects zero actions for evaluator smoke tests, never a trained-policy pass.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))
PROTOCOL_PATH = pathlib.Path(__file__).resolve().parent / "protocols" / "baseline_flat_v2.json"


def yaw_of(quat: torch.Tensor) -> torch.Tensor:
    """Yaw [rad] of a world-frame orientation in the library's (x, y, z, w) layout.

    One source of truth for the frame the evaluator reports in: ``yaw_quat`` + its yaw are
    what the reward kernel projects into (``rl_exp.tasks.baseline_mdp.track_lin_vel_xy_miki``),
    so the evaluator must not re-derive the angle by hand.
    """
    from isaaclab.utils.math import euler_xyz_from_quat

    return euler_xyz_from_quat(quat)[2]


def run(args) -> dict:
    """Run the registered task and return the fixed-window report."""
    import gymnasium as gym
    import torch
    import rl_exp.tasks  # noqa: F401
    from isaaclab.utils.math import quat_apply_inverse, yaw_quat
    from isaaclab.utils.string import string_to_callable
    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper, handle_deprecated_rsl_rl_cfg
    from rsl_rl.runners import OnPolicyRunner

    from ablation_harness import record
    from ablation_harness.baseline_metrics import BaselineWindow
    from rl_exp.tools.diagnose.diag_metrics import (
        MESH_CHECK_BODIES, body_load_n, collision_mesh_dir, foot_ids, mesh_min_z, mesh_vertices,
        pad_point_clouds, tilt_cos,
    )
    from rl_exp.tools.runrecord import provenance
    from rl_exp.tools.verify import cfg_snapshot
    from rl_exp.tools.verify.baseline_runtime import joint_reset_errors, resolve_task_cfg

    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    cfg = resolve_task_cfg(args.task)
    if cfg.params_version != "v1":
        raise ValueError("Baseline-Flat-v1 protocol only accepts baseline/v1")
    if cfg.scene.terrain.terrain_type != "plane" or cfg.scene.terrain.terrain_generator is not None:
        raise ValueError("baseline evaluation requires the recipe's plane, without a suite swap")
    if cfg.episode_length_s != protocol["episode_length_s"]:
        raise ValueError("recipe episode length differs from the frozen baseline protocol")
    cfg.scene.num_envs = args.num_envs
    cfg.seed = args.seed
    if args.device:
        cfg.sim.device = args.device
    agent_cfg = string_to_callable(gym.spec(args.task).kwargs["rsl_rl_cfg_entry_point"])()
    agent_cfg = handle_deprecated_rsl_rl_cfg(agent_cfg, importlib.metadata.version("rsl-rl-lib"))
    sources = provenance.code_sources()
    env = gym.make(args.task, cfg=cfg)
    wrapper = None
    try:
        wrapper = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
        live = env.unwrapped
        robot = live.scene["robot"]
        errors = joint_reset_errors(robot)
        if errors:
            raise RuntimeError("; ".join(errors))
        steps = round(protocol["episode_length_s"] / live.step_dt)
        if abs(steps * live.step_dt - protocol["episode_length_s"]) > 1e-8:
            raise ValueError("protocol duration is not an integer number of control steps")
        obs = wrapper.get_observations()
        checkpoint = None
        if args.checkpoint:
            checkpoint = record.checkpoint_digest(args.checkpoint)
            if checkpoint["sha256"] is None:
                raise ValueError("checkpoint is unreadable")
            runner = OnPolicyRunner(wrapper, agent_cfg.to_dict(), log_dir=None, device=live.device)
            runner.load(args.checkpoint)
            if record.file_sha256(checkpoint["resolved"]) != checkpoint["sha256"]:
                raise RuntimeError("checkpoint changed during load")
            actor = runner.get_inference_policy(device=live.device)

            def policy(observations):
                return actor(observations, stochastic_output=args.policy_mode == "sampled")
        else:
            def policy(observations):
                return torch.zeros(live.num_envs, live.action_manager.total_action_dim, device=live.device)

        sensor = live.scene.sensors["contact_forces"]
        names = sensor.body_names
        load_ids = [i for i, name in enumerate(names) if any(word in name.lower() for word in ("head", "neck", "tail"))]
        if not load_ids:
            raise RuntimeError("no head/neck/tail sensor bodies resolved: cannot report auxiliary support")
        feet = foot_ids(names)
        if not feet:
            raise RuntimeError("no foot bodies resolved: cannot attribute standing to the legs")
        non_foot = [i for i in range(len(names)) if i not in feet]
        mesh_present = [name for name in MESH_CHECK_BODIES if name in names]
        mesh_ids = [names.index(name) for name in mesh_present]
        if not mesh_present:
            raise RuntimeError(f"none of {MESH_CHECK_BODIES} is a body of this asset: cannot check the floor")
        mesh_corners = pad_point_clouds([mesh_vertices(collision_mesh_dir() / f"{name}_collision.obj")
                                        for name in mesh_present]).to(live.device)
        weight_n = float(robot.data.body_mass.torch[0].sum().item() * 9.81)

        def snapshot():
            q = yaw_quat(robot.data.root_quat_w.torch)
            forces = sensor.data.net_forces_w.torch
            load = body_load_n(forces) / weight_n
            return {
                "pos": robot.data.root_pos_w.torch.clone(),
                "yaw": yaw_of(robot.data.root_quat_w.torch),
                "velocity_yaw": quat_apply_inverse(q, robot.data.root_lin_vel_w.torch).clone(),
                "head_tail_force": forces[:, load_ids].norm(dim=-1).sum(dim=-1).clone(),
                "tilt_cos": tilt_cos(robot.data.projected_gravity_b.torch).clone(),
                "non_foot_fraction": load[non_foot].clone(),
                # clone(): mesh_min_z indexes and expands; the live warp-backed view does not
                # survive that on this backend (the diagnose tool only ever feeds it plain tensors).
                "mesh_min_z": mesh_min_z(robot.data.body_pos_w.torch.clone(),
                                         robot.data.body_quat_w.torch.clone(),
                                         mesh_ids, mesh_corners).clone(),
                "foot_contact": (forces[:, feet, 2] > 1.0).clone(),
                "foot_fraction": load[feet].clone(),
            }

        first = snapshot()
        window = BaselineWindow(first["pos"], first["yaw"], steps=steps, protocol=protocol)
        original_reset = live._reset_idx
        terminal = {}
        pending = None
        captured = 0

        def capture_reset(env_ids):
            nonlocal pending, captured
            terminal.update(snapshot())
            pending = env_ids.clone()
            captured += int(env_ids.numel())
            original_reset(env_ids)

        live._reset_idx = capture_reset
        expected = torch.tensor(protocol["command_mps_radps"], device=live.device).expand(live.num_envs, -1)
        torch.manual_seed(args.seed)
        try:
            for _ in range(steps):
                command = live.command_manager.get_command("base_velocity")
                if not torch.allclose(command, expected, atol=1e-6, rtol=0):
                    raise RuntimeError("issued command differs from the fixed baseline protocol")
                with torch.no_grad():
                    obs, _, _, _ = wrapper.step(policy(obs))
                frame = snapshot()
                if pending is not None:
                    for key in frame:
                        frame[key][pending] = terminal[key][pending]
                    pending = None
                window.add(**frame, terminated=live.termination_manager.terminated.clone(),
                           timeout=live.termination_manager.time_outs.clone())
        finally:
            live._reset_idx = original_reset
        result = window.result()
        if checkpoint is None:
            result["verdict"] = "smoke_only"
        return {
            "report_format": "baseline-eval-1", "protocol": protocol,
            "protocol_digest": record.file_sha256(PROTOCOL_PATH),
            "task": args.task, "seed": args.seed, "num_envs": live.num_envs,
            "timestamp": provenance.now(), "code": sources,
            "policy_mode": args.policy_mode if checkpoint else "zero_action", "checkpoint": checkpoint,
            "terminal_frames_captured": captured, "head_tail_sensor_bodies": [names[i] for i in load_ids],
            "foot_bodies": [names[i] for i in feet],
            "non_foot_bodies": [names[i] for i in non_foot],
            "mesh_check_bodies": mesh_present, "body_weight_n": weight_n,
            "env_cfg": cfg_snapshot.snapshot(cfg), "agent_cfg": cfg_snapshot.snapshot(agent_cfg),
            **result,
        }
    finally:
        (wrapper if wrapper is not None else env).close()


def main() -> None:
    from isaaclab.app import AppLauncher

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default="Lizard-Baseline-Flat-Play-v1")
    parser.add_argument("--checkpoint")
    parser.add_argument("--policy_mode", choices=("deterministic", "sampled"), default="deterministic")
    parser.add_argument("--num_envs", type=int, default=16)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()
    if args.num_envs < 1:
        parser.error("--num_envs must be positive")
    if args.output.exists():
        parser.error("output already exists; choose a new report path")
    app = AppLauncher(args).app
    try:
        result = run(args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation also refuses a concurrent writer to the same report name.
        payload = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(payload)
        print(json.dumps({"verdict": result["verdict"], **result["metrics"]}, indent=2))
    finally:
        app.close()


if __name__ == "__main__":
    main()
