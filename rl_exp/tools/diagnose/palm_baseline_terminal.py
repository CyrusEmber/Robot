# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Exercise baseline's real pre-reset collector with a synthetic timeout [rad, s].

One fixed-base, gravity-disabled, zero-gain environment; three control steps.
Inject a bounded joint/command marker after physics at step two, then call the
original termination manager at its deadline. This tests collection, not dynamics.
The frozen protocol and production evaluator are not modified.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from rl_exp.tools.runrecord import binding  # noqa: E402

TASK = "Lizard2-Flat-Play-v3"
PROTOCOL = REPO / "ablation_harness/protocols/lizard2_flat_v5.json"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(report: dict, artifact: dict) -> dict:
    """Recompute marker/terminal/reset correspondence from saved raw data [rad]."""
    import torch
    from ablation_harness import baseline_metrics

    probe = report["terminal_probe"]
    frames, axes = artifact["frames"], artifact["axes"]["joint_pos"]
    require(report["terminal_frames_captured"] == 1 and len(probe["resets"]) == 1,
            "expected exactly one observed reset/captured terminal frame")
    require(artifact["meta"]["terminal_probe"]["scope"] == probe["scope"], "missing diagnostic frame metadata")
    require(artifact["meta"]["steps"] == 3 and report["smoke"]["collected_steps"] == 3,
            "collection must contain exactly three steps")
    require(frames["timeout"][:, 0].bool().tolist() == [False, True, False], "timeout is missing/misplaced")
    require(not frames["terminated"].bool().any(), "unexpected physical termination")
    require(set(axes) == set(probe["joint_names"]) and len(axes) == len(probe["joint_names"]),
            "joint axis differs from independently observed runtime")
    reset = probe["resets"][0]
    require(reset["env_ids"] == [0] and reset["control_step"] == 2, "unexpected reset identity/timing")
    positions = [probe["joint_names"].index(name) for name in axes]
    expected = torch.tensor(reset["pre_backend_q_rad"], dtype=torch.float32)[:, positions]
    post = torch.tensor(reset["post_backend_q_rad"], dtype=torch.float32)[:, positions]
    marker = torch.tensor(probe["marker_q_rad"], dtype=torch.float32)[:, positions]
    require(torch.equal(expected, marker), "backend did not contain the injected marker before reset")
    require(torch.equal(post, torch.zeros_like(post)), "reset did not restore the approved zero defaults")
    require(torch.equal(frames["joint_pos"][1], expected), "terminal joint frame came from reset/wrong columns")
    require(not torch.equal(frames["joint_pos"][1], post), "terminal joint frame cannot distinguish reset")
    command = torch.tensor(reset["pre_command"], dtype=torch.float32)
    require(torch.equal(command, torch.tensor([[.17, 0., 0.]], dtype=torch.float32)), "command marker missing")
    require(torch.equal(frames["command_world"][1], command), "terminal command frame came from reset")
    require(reset["post_command"] != reset["pre_command"], "command marker cannot distinguish reset")
    require(report["reader_validation"] == baseline_metrics.judge(artifact), "saved reader verdict differs")
    for name, values in frames.items():
        require(values.shape[:2] == (3, 1) and torch.isfinite(values).all(), "invalid saved column: " + name)
    return {"terminal_step": 2, "joint_columns": len(axes), "finite_columns": len(frames),
            "joint_marker_error_rad": float((frames["joint_pos"][1] - expected).abs().max()),
            "scope": "injected post-physics state/clock; not physical fall/timeout duration validation"}


def replay(path: Path, approved: str) -> dict:
    """Authenticate and re-read the actual collector output without starting Kit."""
    from ablation_harness import baseline_frames, record

    raw = path.read_bytes()
    require(binding.sha256_bytes(raw) == approved, "report approval mismatch")
    report = json.loads(raw)
    require(report["terminal_probe"]["completed"], "probe is incomplete")
    frames_path = Path(report["frames_path"])
    require(record.file_sha256(frames_path) == report["frames_sha256"], "frames digest mismatch")
    source = path.parent / "source.py"
    require(binding.sha256_file(source) == report["terminal_probe"]["code_sha256"], "probe source digest mismatch")
    require(binding.sha256_file(path.parent / "baseline_eval.py") == report["terminal_probe"]["collector_sha256"],
            "collector source digest mismatch")
    artifact = baseline_frames.load(frames_path)
    result = audit(report, artifact)
    rejected = []
    for defect in ("post_reset", "wrong_joint", "timeout", "command"):
        bad = copy.deepcopy(artifact)
        if defect == "post_reset":
            bad["frames"]["joint_pos"][1].zero_()
        elif defect == "wrong_joint":
            bad["frames"]["joint_pos"][1] = bad["frames"]["joint_pos"][1].flip([1])
        elif defect == "timeout":
            bad["frames"]["timeout"].zero_()
        else:
            bad["frames"]["command_world"][1].zero_()
        try:
            audit(report, bad)
        except ValueError:
            rejected.append(defect)
        else:
            raise ValueError("corrupted terminal artifact accepted: " + defect)
    return {**result, "rejected": rejected}


def collect(args, probe: dict) -> dict:
    import gymnasium as gym
    import torch
    import warp as wp
    from pxr import UsdPhysics
    from ablation_harness import baseline_eval, baseline_frames

    original_make, original_save = gym.make, baseline_frames.save

    def make(task, **kwargs):
        cfg = kwargs["cfg"]
        require(task == TASK and cfg.scene.num_envs == 1, "unexpected task/environment count")
        require(cfg.scene.robot.spawn.rigid_props.disable_gravity, "probe requires disabled gravity")
        for actuator in cfg.scene.robot.actuators.values():
            require(actuator.stiffness == 0. and actuator.damping == 0., "probe requires zero gains")
        env = original_make(task, **kwargs)
        live, robot = env.unwrapped, env.unwrapped.scene["robot"]
        try:
            require(robot.is_fixed_base, "probe requires fixed base")
            stage = live.sim.stage
            gravity = [p.GetAttribute("physxRigidBody:disableGravity").Get()
                       for p in stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)]
            timing = stage.GetPrimAtPath(cfg.sim.physics_prim_path).GetAttribute(
                "physxScene:enableExternalForcesEveryIteration").Get()
            require(gravity and all(value is True for value in gravity), "live body gravity differs")
            require(timing is False, "probe must retain training's false force timing")
            probe.update(joint_names=list(robot.joint_names), readbacks={"fixed_base": True,
                         "body_disable_gravity": gravity, "force_timing": timing})
            original_compute, original_reset = live.termination_manager.compute, live._reset_idx
            marker = torch.arange(1, len(robot.joint_names) + 1, device=live.device).unsqueeze(0) * .001
            limits = robot.data.joint_pos_limits.torch
            require(((marker >= limits[..., 0]) & (marker <= limits[..., 1])).all(), "marker outside limits")
            probe["marker_q_rad"] = marker.cpu().tolist()

            def compute():
                if live.common_step_counter == 2:
                    require(not probe.get("injected"), "marker injection repeated")
                    robot.write_joint_state_to_sim(marker, torch.zeros_like(marker))
                    live.command_manager.get_command("base_velocity").copy_(
                        torch.tensor([[.17, 0., 0.]], device=live.device))
                    live.episode_length_buf[0] = live.max_episode_length
                    probe["injected"] = True
                return original_compute()

            def reset(env_ids):
                if not probe.get("injected"):
                    return original_reset(env_ids)
                row = {"control_step": live.common_step_counter, "env_ids": env_ids.cpu().tolist(),
                       "pre_backend_q_rad": wp.to_torch(robot.root_view.get_dof_positions()).cpu().tolist(),
                       "pre_command": live.command_manager.get_command("base_velocity").cpu().tolist()}
                original_reset(env_ids)
                row.update(post_backend_q_rad=wp.to_torch(robot.root_view.get_dof_positions()).cpu().tolist(),
                           post_command=live.command_manager.get_command("base_velocity").cpu().tolist())
                probe["resets"].append(row)

            live.termination_manager.compute, live._reset_idx = compute, reset
            return env
        except BaseException:
            env.close()
            raise

    def save(path, artifact):
        artifact["meta"]["terminal_probe"] = {"scope": probe["scope"], "injected_control_step": 2,
                                               "collector_sha256": probe["collector_sha256"]}
        original_save(path, artifact)

    collector_bytes = Path(baseline_eval.__file__).read_bytes()
    (args.out / "baseline_eval.py").write_bytes(collector_bytes)
    probe["collector_sha256"] = binding.sha256_bytes(collector_bytes)
    options = argparse.Namespace(task=TASK, protocol=PROTOCOL, target_config=args.manifest,
        naming="palm_spatial", num_envs=1, seed=0, device=args.device, checkpoint=None,
        smoke_steps=3, policy_mode="deterministic", output=args.out / "report.json")
    with patch.object(gym, "make", make), patch.object(baseline_frames, "save", save):
        result = baseline_eval.run(options)
    result["terminal_probe"] = probe
    result["terminal_probe"]["audit"] = audit(result, baseline_frames.load(result["frames_path"]))
    probe["completed"] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--approved_manifest_sha256")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--approved_report_sha256")
    preliminary, _ = parser.parse_known_args()
    if preliminary.replay:
        args = parser.parse_args()
        require(args.approved_report_sha256, "replay requires independent report approval")
        print(json.dumps(replay(args.replay, args.approved_report_sha256), indent=2))
        print("BASELINE_TERMINAL_REPLAY_OK")
        return
    require(preliminary.manifest and preliminary.out and preliminary.approved_manifest_sha256,
            "collection requires --manifest/--approved_manifest_sha256/--out")
    raw = preliminary.manifest.read_bytes()
    require(binding.sha256_bytes(raw) == preliminary.approved_manifest_sha256, "manifest approval mismatch")
    manifest = json.loads(raw)
    for field in ("target", "urdf"):
        require(binding.sha256_file(Path(manifest["target_binding"][field])) == manifest["sha256"][field],
                "manifest artifact digest mismatch: " + field)
    require(preliminary.out.resolve().is_relative_to(REPO / "rl_exp/out"), "output must be under rl_exp/out")
    preliminary.out.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).read_bytes()
    (preliminary.out / "source.py").write_bytes(source)
    probe = {"completed": False, "scope": "synthetic post-physics marker and timeout; no performance verdict",
             "code_sha256": binding.sha256_bytes(source), "manifest_sha256": binding.sha256_bytes(raw),
             "manifest": str(preliminary.manifest.resolve()), "resets": []}
    from isaaclab.app import AppLauncher
    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()
    app = AppLauncher(args).app
    try:
        report = collect(args, probe)
        with (args.out / "report.json").open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, allow_nan=False)
        print("BASELINE_TERMINAL_PROBE_OK")
    except BaseException as error:
        import os
        import traceback
        probe["error"] = repr(error)
        (args.out / "failure.json").write_text(json.dumps(probe, indent=2), encoding="utf-8")
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
    app.close()


if __name__ == "__main__":
    main()
