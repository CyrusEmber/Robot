# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Run the real gait CLI with tiny, distinguishable state/action injections [rad, rad/s].

Four control steps in one fixed-base, gravity-disabled, zero-gain environment.
This is a writer/reader wiring test, not a policy, tracking or gait evaluation.
The producer and frozen configuration remain unchanged on disk.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from rl_exp.tools.runrecord import binding  # noqa: E402

GAIT = REPO / "rl_exp/tools/diagnose/gait_probe.py"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(report: dict) -> dict:
    """Compare every saved column with the independently sampled backend [SI units]."""
    import numpy as np
    from rl_exp.tasks import joint_names
    from rl_exp.tools.diagnose.plot_joints import report_naming

    naming = report_naming(report)
    probe = report["wiring_probe"]
    require(report["policy_mode"] == "injected_wiring" and probe["completed"], "missing diagnostic identity")
    require(report["steps"] == 4 and len(report["envs"]) == 1, "unexpected collection size")
    samples, names, channels = probe["samples"], probe["joint_names"], probe["action_names"]
    require(len(samples) == 4 and len(names) == 30 and len(set(names)) == 30, "unexpected sample/joint set")
    require(len(channels) == 30 and set(channels) == set(names), "action coverage mismatch")
    require(names == report["target_binding"]["joint_names"], "runtime/binding order mismatch")
    entry = report["envs"][0]
    require(entry["done_series"] == [False, False, False, True], "unexpected termination")
    require(entry["valid_series"] == [True, True, True, False], "incorrect first-episode mask")
    require(entry["frames_alive"] == entry["frames_recorded"] == 3, "incorrect recorded scope")
    raw_fields = {"actual": "backend_q_rad", "target": "backend_target_rad", "vel": "backend_dq_rad_s"}
    max_error = 0.
    for step, sample in enumerate(samples):
        require(sample["step"] == step and sample["done"] == (step == 3), "sample timing mismatch")
        for backend, cached in (("backend_q_rad", "cache_q_rad"), ("backend_dq_rad_s", "cache_dq_rad_s"),
                                ("backend_target_rad", "cache_target_rad")):
            a, b = np.asarray(sample[backend]), np.asarray(sample[cached])
            require(a.shape == b.shape == (1, 30) and np.isfinite(a).all() and np.isfinite(b).all(),
                    "invalid raw sample: " + backend)
            require(np.max(abs(a-b)) <= 1.e-7, "backend/cache disagreement: " + backend)
        desired = np.zeros((1, 30))
        for column, name in enumerate(channels):
            desired[0, names.index(name)] = sample["raw_action"][0][column]
        require(np.max(abs(desired - sample["backend_target_rad"])) <= 1.e-7, "wrong action/target mapping")
        require(not np.asarray(sample["backend_velocity_target_rad_s"]).any(), "unexpected velocity target")
    legs = {joint_names.joint_name(leg, root): f"{joint_names.end_link(leg, naming)}_{root}"
            for leg in joint_names.LEGS for root in joint_names.roots_of(naming, leg)}
    for index, name in enumerate(names):
        series = entry["joint_series"] if name in legs else entry["spine_series"]
        stem = legs.get(name, name)
        for kind, field in raw_fields.items():
            actual = np.asarray(series[stem + "_" + kind])
            expected = np.asarray([row[field][0][index] for row in samples[:3]])
            require(actual.shape == (3,) and np.isfinite(actual).all(), "invalid report series: " + stem)
            error = float(np.max(abs(actual-expected)))
            # The existing writer rounds these series to five decimal places.
            require(error <= 5.1e-6, "wrong nonzero report values: " + stem + "_" + kind)
            require(np.min(abs(expected)) > 1.e-5, "nonzero mapping evidence is empty: " + stem)
            max_error = max(max_error, error)
    return {"verified_joint_columns": 30, "verified_series": 90, "recorded_frames": 3,
            "max_rounding_error": max_error, "scope": "injected state/action writer mapping only"}


def replay(path: Path, approved: str) -> dict:
    """Authenticate saved evidence, then reject numerical and binding corruptions."""
    raw = path.read_bytes()
    require(binding.sha256_bytes(raw) == approved, "report approval mismatch")
    report = json.loads(raw)
    for name, digest in report["wiring_probe"]["snapshots"].items():
        require(binding.sha256_file(path.parent / name) == digest, "snapshot digest mismatch: " + name)
    result, rejected = audit(report), []
    keys = list(report["envs"][0]["joint_series"])
    twist = next(key for key in keys if "twist_actual" in key)
    other = next(key for key in keys if "elbow_actual" in key)
    for defect in ("swap_twist", "zero_velocity", "wrong_target", "missing_twist", "source"):
        bad = copy.deepcopy(report)
        series = bad["envs"][0]["joint_series"]
        if defect == "swap_twist":
            series[twist], series[other] = series[other], series[twist]
        elif defect == "zero_velocity":
            series[twist.replace("actual", "vel")] = [0.] * 3
        elif defect == "wrong_target":
            series[twist.replace("actual", "target")][0] += .001
        elif defect == "missing_twist":
            del series[twist]
        else:
            bad["target_binding"]["source"] = ""
        try:
            audit(bad)
        except ValueError:
            rejected.append(defect)
        else:
            raise ValueError("corrupted gait report accepted: " + defect)
    return {**result, "rejected": rejected}


def collect(args, probe: dict):
    import gymnasium as gym

    original_make, original_write = gym.make, Path.write_text
    report_path = args.out.resolve() / "report.json"

    def make(task, **kwargs):
        import torch
        import warp as wp
        from pxr import UsdPhysics

        cfg = kwargs["cfg"]
        require(task == "Lizard2-Flat-Play-v3" and cfg.scene.num_envs == 1, "unexpected target")
        require(cfg.scene.robot.spawn.rigid_props.disable_gravity, "probe requires disabled gravity")
        require(all(a.stiffness == 0. and a.damping == 0. for a in cfg.scene.robot.actuators.values()),
                "probe requires zero configured gains")
        env = original_make(task, **kwargs)
        live, robot = env.unwrapped, env.unwrapped.scene["robot"]
        try:
            require(robot.is_fixed_base and live.max_episode_length == 4, "unexpected base/window")
            gravity = [p.GetAttribute("physxRigidBody:disableGravity").Get()
                       for p in live.sim.stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)]
            timing = live.sim.stage.GetPrimAtPath(cfg.sim.physics_prim_path).GetAttribute(
                "physxScene:enableExternalForcesEveryIteration").Get()
            require(len(gravity) == 31 and all(v is True for v in gravity) and timing is False,
                    "live gravity/force timing mismatch")
            require(not robot.data.joint_stiffness.torch.any() and not robot.data.joint_damping.torch.any(),
                    "live cached gains are nonzero")
            names = list(robot.joint_names)
            channels = [n for term in live.action_manager.active_terms
                        for n in live.action_manager.get_term(term)._joint_names]
            require(len(names) == len(channels) == 30 and set(channels) == set(names), "unexpected channels")
            probe.update(joint_names=names, action_names=channels,
                         readbacks={"fixed_base": True, "body_disable_gravity": gravity, "force_timing": timing})
            original_process = live.action_manager.process_action
            original_compute = live.termination_manager.compute

            def process(action):
                require(not action.any() and len(probe["samples"]) < 4, "unexpected producer action/call count")
                step = len(probe["samples"])
                sign = -1. if step % 2 else 1.
                index = torch.arange(1, 31, device=live.device).unsqueeze(0)
                q, dq = sign * index * .0001, sign * index * .0002
                injected = sign * index.flip([1]) * .00015
                limits = robot.data.joint_pos_limits.torch
                require(((q >= limits[..., 0]) & (q <= limits[..., 1])).all(), "state marker outside limits")
                desired = torch.zeros_like(q)
                for column, name in enumerate(channels):
                    desired[0, names.index(name)] = injected[0, column]
                require(((desired >= limits[..., 0]) & (desired <= limits[..., 1])).all(), "target outside limits")
                robot.write_joint_state_to_sim(q, dq)
                probe["samples"].append({"step": step, "input_q_rad": q.cpu().tolist(),
                    "input_dq_rad_s": dq.cpu().tolist(), "raw_action": injected.cpu().tolist()})
                return original_process(injected)

            def compute():
                result = original_compute()
                row = probe["samples"][-1]
                for name, getter in (("backend_q_rad", "get_dof_positions"),
                                     ("backend_dq_rad_s", "get_dof_velocities"),
                                     ("backend_target_rad", "get_dof_position_targets"),
                                     ("backend_velocity_target_rad_s", "get_dof_velocity_targets")):
                    row[name] = wp.to_torch(getattr(robot.root_view, getter)()).cpu().tolist()
                row.update(cache_q_rad=robot.data.joint_pos.torch.cpu().tolist(),
                           cache_dq_rad_s=robot.data.joint_vel.torch.cpu().tolist(),
                           cache_target_rad=robot.data.joint_pos_target.torch.cpu().tolist(), done=bool(result[0]))
                return result

            live.action_manager.process_action, live.termination_manager.compute = process, compute
            return env
        except BaseException:
            env.close()
            raise

    def write(path, text, *positional, **kwargs):
        if path.resolve() != report_path:
            return original_write(path, text, *positional, **kwargs)
        require(not path.exists(), "refusing to overwrite an existing report")
        report = json.loads(text)
        report["producer_policy_mode"], report["policy_mode"] = report["policy_mode"], "injected_wiring"
        probe["completed"] = True
        report["wiring_probe"] = probe
        probe["audit"] = audit(report)
        result = original_write(path, json.dumps(report, indent=2, allow_nan=False), *positional, **kwargs)
        original_write(args.out / "status.json", json.dumps({"completed": True, "scope": probe["scope"]}))
        print("GAIT_WIRING_COLLECTOR_OK", flush=True)
        return result

    argv = [str(GAIT), "--task", "Lizard2-Flat-Play-v3", "--target_config", str(args.manifest),
            "--policy_mode", "zero", "--speeds", "0", "--seconds", ".08", "--viz", "none",
            "--device", "cuda:0", "--out", str(report_path)]
    with patch.object(gym, "make", make), patch.object(Path, "write_text", write), patch.object(sys, "argv", argv):
        runpy.run_path(str(GAIT), run_name="__main__")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--approved_manifest_sha256")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--approved_report_sha256")
    args = parser.parse_args()
    if args.replay:
        require(args.approved_report_sha256, "replay requires independent report approval")
        print(json.dumps(replay(args.replay, args.approved_report_sha256), indent=2))
        print("GAIT_WIRING_REPLAY_OK")
        return
    require(args.manifest and args.out and args.approved_manifest_sha256, "manifest approval/output required")
    raw = args.manifest.read_bytes()
    require(binding.sha256_bytes(raw) == args.approved_manifest_sha256, "manifest approval mismatch")
    manifest = json.loads(raw)
    for field in ("target", "urdf"):
        require(binding.sha256_file(Path(manifest["target_binding"][field])) == manifest["sha256"][field],
                "asset digest mismatch: " + field)
    args.out = args.out.resolve()
    require(args.out.is_relative_to(REPO / "rl_exp/out"), "output must be under rl_exp/out")
    args.out.mkdir(parents=True, exist_ok=False)
    snapshots = {"source.py": Path(__file__).read_bytes(), "gait_probe.py": GAIT.read_bytes(), "manifest.json": raw}
    for name, payload in snapshots.items():
        (args.out / name).write_bytes(payload)
    probe = {"completed": False, "scope": "small injected state/action; no tracking or gait performance verdict",
             "samples": [], "snapshots": {name: binding.sha256_bytes(data) for name, data in snapshots.items()}}
    (args.out / "status.json").write_text(json.dumps({"completed": False, "scope": probe["scope"]}))
    collect(args, probe)


if __name__ == "__main__":
    main()
