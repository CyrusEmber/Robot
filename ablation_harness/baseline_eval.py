# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Evaluate baseline's first episode on its own plane for exactly 20 s.

The protocol is an input, not a constant: ``--protocol`` names the frozen file this rollout is
collected and judged under, and the report records its digest. A protocol that declares a different
recipe version than the task resolves, or a command box the recipe does not sample, is refused --
the point of separating collection from judgement is that a verdict can always name the ruler.

Run with IsaacLab Python after Kit initialization by this entry point. A missing checkpoint selects
zero actions for evaluator smoke tests, never a trained-policy pass.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import pathlib
import re
import sys
import traceback

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))


def yaw_of(quat: torch.Tensor) -> torch.Tensor:
    """Yaw [rad] of a world-frame orientation in the library's (x, y, z, w) layout.

    One source of truth for the frame the evaluator reports in: ``yaw_quat`` + its yaw are
    what the reward kernel projects into (``rl_exp.tasks.baseline_mdp.track_lin_vel_xy_miki``),
    so the evaluator must not re-derive the angle by hand.
    """
    from isaaclab.utils.math import euler_xyz_from_quat

    return euler_xyz_from_quat(quat)[2]


def _gait_shape_joints(cfg, names: list[str]) -> list[str]:
    """The joints a gait-shape reading needs: the spine's own group, plus one token per leg.

    Named rather than "all of them": a column nobody reads is what this harness refuses elsewhere, and
    these are the joints a stride can come from (the sprawl axis, the thigh's own elevation, the
    fore-aft hinge, the shank, the blade) plus the trunk that a sprawled reptile undulates. A family
    without one of the tokens simply matches fewer joints; the joint order is the asset's own, so the
    axis labels cannot disagree with the values they label.
    """
    actuators = getattr(cfg.scene.robot, "actuators", None) or {}
    spinal = getattr(actuators.get("spine"), "joint_names_expr", ()) or ()
    tokens = ("_hip_joint", "_haa_joint", "_hfe_joint", "_kfe_joint", "_foot_joint")
    return [name for name in names
            if name.endswith(tokens) or any(re.fullmatch(pattern, name) for pattern in spinal)]


def judged_or_recoverable(artifact: dict, frames_path: pathlib.Path | str) -> dict:
    """Judge a record that is already on disk; a judge that raises names the file to retry from.

    The record is written before this runs on purpose. A judge that raises is a defect on the judging
    side, not a bad policy, and it must not take the completed window with it: the error carries the
    record's path and the offline command that re-judges it without the simulator.
    """
    from ablation_harness import baseline_metrics

    try:
        return baseline_metrics.judge(artifact)
    except Exception as err:
        raise RuntimeError(
            f"judging failed ({type(err).__name__}: {err}). The window is saved; re-judge it offline "
            f"with: python -m ablation_harness.baseline_metrics {frames_path} --protocol <protocol file>"
        ) from err


def run(args) -> dict:
    """Run the registered task and return the fixed-window report."""
    import gymnasium as gym
    import torch
    import rl_exp.tasks  # noqa: F401
    from isaaclab.utils.math import quat_apply_inverse, yaw_quat
    from isaaclab.utils.string import string_to_callable
    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper, handle_deprecated_rsl_rl_cfg
    from rsl_rl.runners import OnPolicyRunner

    from ablation_harness import baseline_frames, baseline_metrics, record
    from rl_exp.tools.diagnose.diag_metrics import (
        MESH_CHECK_BODIES, collision_mesh_dir, foot_ids, mesh_lowest_point, mesh_min_z, mesh_vertices,
        pad_point_clouds, tilt_cos,
    )
    from rl_exp.tools.runrecord import provenance
    from rl_exp.tools.verify import cfg_snapshot
    from rl_exp.tools.verify.baseline_runtime import joint_reset_errors, resolve_task_cfg
    from rl_exp.tasks import obs_protocol

    # The tree this task's family declares (2026-09-28): two families can carry different geometry,
    # and the foot reading plus its `foot_geometry` meta have to come off the mesh the run loaded.
    mesh_dir = collision_mesh_dir(obs_protocol.family_of(args.task))

    protocol_path = pathlib.Path(args.protocol)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    cfg = resolve_task_cfg(args.task)
    judged = protocol.get("recipe_version", "v1")
    if cfg.params_version != judged:
        raise ValueError(f"this protocol judges baseline/{judged}, but the task resolves "
                         f"params_version={cfg.params_version}")
    if cfg.scene.terrain.terrain_type != "plane" or cfg.scene.terrain.terrain_generator is not None:
        raise ValueError("baseline evaluation requires the recipe's plane, without a suite swap")
    if cfg.episode_length_s != protocol["episode_length_s"]:
        raise ValueError("recipe episode length differs from the frozen baseline protocol")
    cfg.scene.num_envs = args.num_envs
    cfg.seed = args.seed
    # A protocol may declare fixed scenes: one constant command per env, held for the whole window.
    # Then the environment's own resampling has to go, or it overwrites the injected command on its
    # own schedule and the frames belong to a command nobody planned. The neutralization is the one
    # the locomotion harness applies for the same reason (``components/dr_controller.apply_eval_mode``)
    # and it is recorded in the frame meta, because it is a collection condition like any other.
    scenes = protocol.get("scenes")
    if scenes is not None:
        if not isinstance(scenes, list) or not scenes or not all(isinstance(scene, dict) for scene in scenes):
            raise ValueError("the protocol's scenes must be a non-empty list of objects with vx/vy/wz")
        missing = [scene for scene in scenes if "name" not in scene]
        if missing:
            raise ValueError(f"every scene needs a name to be reported by: {missing}")
        cmd_cfg = cfg.commands.base_velocity
        cmd_cfg.heading_command = False
        cmd_cfg.rel_standing_envs = 0.0
        cmd_cfg.rel_heading_envs = 0.0
        cmd_cfg.resampling_time_range = (1.0e9, 1.0e9)
        cmd_cfg.debug_vis = False
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
        mesh_corners = pad_point_clouds([mesh_vertices(mesh_dir / f"{name}_collision.obj")
                                        for name in mesh_present]).to(live.device)
        # The foot reading is taken off the asset's own collision meshes too: the geometry travels
        # with the record (below), so a later reader cannot substitute another family's foot.
        foot_names = [names[i] for i in feet]
        foot_meshes = [f"{name}_collision.obj" for name in foot_names]
        missing_meshes = [name for name in foot_meshes if not (mesh_dir / name).is_file()]
        if missing_meshes:
            raise RuntimeError(f"no collision mesh for {missing_meshes}: the foot clearance and the "
                               "contact candidate are read off those files, not off the body origin")
        foot_corners = pad_point_clouds([mesh_vertices(mesh_dir / name)
                                        for name in foot_meshes]).to(live.device)
        weight_n = float(robot.data.body_mass.torch[0].sum().item() * 9.81)
        # The joint reading: which joints, and in the asset's own order, so the axis labels and the
        # values they label cannot drift apart. Empty is refused here rather than stored as a column
        # with no axes -- a reading nobody can name is not evidence.
        gait_joints = _gait_shape_joints(cfg, list(robot.joint_names))
        if not gait_joints:
            raise RuntimeError("no leg-token or spine joint resolved: the gait-shape reading would "
                               "carry an empty axis")
        gait_joint_ids = [robot.joint_names.index(name) for name in gait_joints]
        recorder = baseline_frames.BaselineFrames(
            num_envs=live.num_envs, step_dt=live.step_dt,
            axes={"non_foot_fraction": [names[i] for i in non_foot], "mesh_min_z": mesh_present,
                  "foot_contact": foot_names, "foot_fraction": foot_names,
                  "foot_lowest_point": foot_names, "foot_com_pos": foot_names,
                  "foot_lin_vel": foot_names, "foot_ang_vel": foot_names,
                  "joint_pos": gait_joints})

        def snapshot():
            q = yaw_quat(robot.data.root_quat_w.torch)
            forces = sensor.data.net_forces_w.torch
            load = forces[:, :, 2] / weight_n  # (N, num_bodies): per env, per body
            return {
                "pos": robot.data.root_pos_w.torch.clone(),
                "yaw": yaw_of(robot.data.root_quat_w.torch),
                "velocity_yaw": quat_apply_inverse(q, robot.data.root_lin_vel_w.torch).clone(),
                "command_world": live.command_manager.get_command("base_velocity").clone(),
                "head_tail_force": forces[:, load_ids].norm(dim=-1).sum(dim=-1).clone(),
                "tilt_cos": tilt_cos(robot.data.projected_gravity_b.torch).clone(),
                "non_foot_fraction": load[:, non_foot].clone(),
                # clone(): mesh_min_z indexes and expands; the live warp-backed view does not
                # survive that on this backend (the diagnose tool only ever feeds it plain tensors).
                "mesh_min_z": mesh_min_z(robot.data.body_pos_w.torch.clone(),
                                         robot.data.body_quat_w.torch.clone(),
                                         mesh_ids, mesh_corners).clone(),
                # float, not bool: a duty cycle is a count of contact frames, and bool + bool is
                # still bool -- the accumulator would saturate at one frame per env.
                "foot_contact": (forces[:, feet, 2] > 1.0).to(torch.float32).clone(),
                "foot_fraction": load[:, feet].clone(),
                # The contact candidate per foot and the substrate of a velocity *at* it: the body's
                # COM (which is what `body_lin_vel_w` is the velocity of -- it is the COM alias, not
                # the link-origin one), that velocity, and the angular velocity. So the offline reader
                # can take `v + omega x (p - p_com)` itself instead of trusting a frozen projection.
                # `mesh_lowest_point` indexes and expands, so it needs plain tensors.
                "foot_lowest_point": mesh_lowest_point(robot.data.body_pos_w.torch.clone(),
                                                       robot.data.body_quat_w.torch.clone(),
                                                       feet, foot_corners).clone(),
                "foot_com_pos": robot.data.body_com_pos_w.torch[:, feet],
                "foot_lin_vel": robot.data.body_lin_vel_w.torch[:, feet],
                "foot_ang_vel": robot.data.body_ang_vel_w.torch[:, feet],
                # The joint reading. `joint_pos` is the live deployed quantity (implicit PD drives
                # against it), so a gait-shape reading taken from here is the same window the verdict
                # is taken from, not a second rollout that happened to look similar.
                "joint_pos": robot.data.joint_pos.torch[:, gait_joint_ids].clone(),
            }

        # The episode's initial state: frame 0 is already one control step in, so displacement and
        # yaw drift are measured from here, and the record carries it (per env: the spawn poses
        # differ, so one env's origin cannot speak for the others).
        first = snapshot()
        start = {"start_pos": first["pos"].clone(), "start_yaw": first["yaw"].clone()}
        original_reset = live._reset_idx
        terminal = {}
        pending = None
        captured = 0
        contract_error = None

        def capture_reset(env_ids):
            nonlocal pending, captured
            terminal.update(snapshot())
            pending = env_ids.clone()
            captured += int(env_ids.numel())
            original_reset(env_ids)

        live._reset_idx = capture_reset
        # The protocol declares a box, not necessarily a point: v1/v2 held the command constant,
        # v2's recipe samples 1-3 m/s on the framework's own window. Both read through the same
        # accessor, and every frame's issued command is checked against it and recorded.
        box = baseline_metrics.command_box(protocol)
        low = torch.tensor([low for low, _ in box], device=live.device)
        high = torch.tensor([high for _, high in box], device=live.device)
        # The declared scenes as one constant command per env. The box check below is read back from
        # the environment rather than from this variable, so an injection that did not land (or
        # landed on the wrong envs) shows up here instead of being assumed away.
        scene_block = scene_term = None
        assignment = None
        if scenes is not None:
            from ablation_harness.components.command_player import scene_assignment, scene_commands

            assignment = scene_assignment(scenes, live.num_envs, args.seed)
            scene_block = scene_commands(scenes, assignment, live.num_envs, live.device)
            scene_term = live.command_manager.get_term("base_velocity")
        torch.manual_seed(args.seed)
        try:
            for _ in range(steps):
                if scene_term is not None:
                    scene_term.vel_command_b[:] = scene_block
                command = live.command_manager.get_command("base_velocity")
                if bool((command < low - 1e-6).any() or (command > high + 1e-6).any()):
                    raise RuntimeError(f"issued command leaves the protocol's box {box}: "
                                       f"{command[0].tolist()}")
                with torch.no_grad():
                    obs, _, _, _ = wrapper.step(policy(obs))
                frame = snapshot()
                if pending is not None:
                    for key in frame:
                        frame[key][pending] = terminal[key][pending]
                    pending = None
                try:
                    recorder.add(**frame, terminated=live.termination_manager.terminated.clone(),
                                 timeout=live.termination_manager.time_outs.clone())
                except baseline_frames.FramesContractError as err:
                    # A mis-shaped sample is a bug on this side, but "no report at all" hides it:
                    # the run still lands a report, and that report says its verdict is invalid.
                    contract_error = err
                    break
        finally:
            live._reset_idx = original_reset
        frames_path = args.output.with_name(args.output.stem + ".frames.pt")
        artifact = None
        if contract_error is not None:
            result = {
                "verdict": "invalid", "invalid_reasons": [f"collection contract: {contract_error}"],
                "judge": baseline_metrics.judge_identity(protocol),
                "gates": {name: None for name in baseline_metrics.gate_names(protocol)},
                "metrics": {}, "diagnostics": {}, "per_env": {}, "axes": recorder.axes,
            }
        else:
            # The collection conditions a scene window carries: which scenes were declared, which env
            # walked which one, and that the environment's own resampling was frozen to make that hold.
            # The frame record is not a run record, so its meta is the only home these have.
            scene_conditions = {} if scenes is None else {
                "scenes": {"declared": [dict(scene) for scene in scenes],
                           "assignment": assignment.tolist(),
                           "resampling_frozen": True,
                           "seed": args.seed}}
            artifact = recorder.artifact(
                protocol=protocol, **start, task=args.task, seed=args.seed, num_envs=live.num_envs,
                checkpoint=checkpoint, policy_mode=args.policy_mode if checkpoint else "zero_action",
                body_weight_n=weight_n, **scene_conditions,
                # Provenance of the two geometries the foot reading depends on: the ground the
                # clearance is measured against, and the asset the sole geometry was taken off. Both
                # travel in the record, so a later reader cannot fill either in from memory.
                ground_source={"kind": cfg.scene.terrain.terrain_type, "z_m": 0.0,
                               "normal": [0.0, 0.0, 1.0]},
                # The tree is per-family now, so the file NAME no longer identifies the geometry --
                # the digest does, and it is taken from the tree this family declares. No new key
                # here: the frame format's meta shape is fixed for the life of the format.
                foot_geometry={name: {"obj": mesh,
                                      "sha256": record.file_sha256(mesh_dir / mesh),
                                      "vertices": int(mesh_vertices(mesh_dir / mesh).shape[0])}
                               for name, mesh in zip(foot_names, foot_meshes)})
            # Saved first, judged second: the window is the evidence, and the verdict is derivable
            # from it again offline -- so a judge defect cannot cost a completed collection.
            baseline_frames.save(frames_path, artifact)
            result = judged_or_recoverable(artifact, frames_path)
        if checkpoint is None and result["verdict"] in ("pass", "fail"):
            result["verdict"] = "smoke_only"
        return {
            "report_format": "baseline-eval-2", "protocol": protocol,
            "protocol_path": str(protocol_path),
            "protocol_digest": record.file_sha256(protocol_path),
            "task": args.task, "seed": args.seed, "num_envs": live.num_envs,
            "timestamp": provenance.now(), "code": sources,
            "policy_mode": args.policy_mode if checkpoint else "zero_action", "checkpoint": checkpoint,
            "terminal_frames_captured": captured, "head_tail_sensor_bodies": [names[i] for i in load_ids],
            "foot_bodies": [names[i] for i in feet],
            "non_foot_bodies": [names[i] for i in non_foot],
            "mesh_check_bodies": mesh_present, "body_weight_n": weight_n,
            "frames_path": str(frames_path) if artifact is not None else None,
            "frames_sha256": record.file_sha256(frames_path) if artifact is not None else None,
            "env_cfg": cfg_snapshot.snapshot(cfg), "agent_cfg": cfg_snapshot.snapshot(agent_cfg),
            **result,
        }
    finally:
        (wrapper if wrapper is not None else env).close()


def main() -> None:
    from isaaclab.app import AppLauncher

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default="Lizard-Baseline-Flat-Play-v1")
    parser.add_argument("--protocol", type=pathlib.Path, required=True,
                        help="frozen protocol under protocols/; the report records its digest")
    parser.add_argument("--checkpoint")
    parser.add_argument("--policy_mode", choices=("deterministic", "sampled"), default="deterministic")
    parser.add_argument("--num_envs", type=int, default=16)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()
    if args.num_envs < 1:
        parser.error("--num_envs must be positive")
    if not args.protocol.is_file():
        parser.error(f"--protocol {args.protocol} does not exist")
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
    except BaseException:
        # Two things `app.close()` would otherwise take with it, both measured on a real run:
        # raised past it, the traceback never reaches the terminal; and close() ends the process with
        # status 0, so a script reading the status would call a failed run a success. Report, flush,
        # then leave with a non-zero status *before* close can run -- so a failed run skips Kit's
        # shutdown, which is a price only a run that already failed pays.
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
    finally:
        app.close()


if __name__ == "__main__":
    main()
