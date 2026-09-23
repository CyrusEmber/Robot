# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Gait probe: the four readings the 2026-09-23 record says are still unmeasured.

The record (``acceptance/records/2026-09-23-lizard2-v1-gait-skate.md``) retracted two conclusions its
first version drew from a throwaway probe -- "the swing foot lifts only 2-8 cm" and "the loaded foot
slides at body speed" -- because that probe read the foot body ORIGIN's height above its own window
minimum, and the foot body's rigid-body velocity. Neither is the quantity the symptom needs. This
probe measures the four that are, in one rollout, so the three surviving explanations can be told
apart:

  ``sole_clearance_m``      lowest collision-mesh vertex of each foot, ground at z = 0. The recipe's
                            terrain is a plane, so this IS the foot-to-ground distance -- not a foot
                            origin offset (``diag_metrics.mesh_min_z`` / ``mesh_lowest_point``).
  ``contact_speed_horiz_mps``  ``v_com + omega x (p - p_com)`` at that vertex
                            (``diag_metrics.contact_point_velocity``). A foot rolling over its toe
                            moves its origin while the contact point stands still; a dragged foot
                            moves both. This is the reading that separates the two.
  ``foot_fore_aft_m``       foot origin relative to the root in the yaw frame
                            (``diag_metrics.yaw_frame_offset``), so ``[0]`` fore-aft and ``[2]`` up.
                            Per unloaded run its excursion is the step the foot actually took, per
                            loaded run its change is stance drag.
  ``joint_target_*``/``joint_err_*``  ``*_hip_joint`` (the stride axis) and ``*_hfe_joint`` (the knee):
                            does the policy COMMAND a swing at all (target peak-to-peak), and does the
                            actuator follow it (|target - pos|)?

What each reading separates (the record's question, nothing more):

  policy never commands a swing  -> target peak-to-peak tiny, tracking error tiny
  actuator cannot follow the swing -> target moves, tracking error large and phase-lagged
  toe roll / dragging            -> contact point horizontal speed ~0 (or negative) while the foot
                                    origin rises and the sole clearance stays ~0

Usage (repo root):
    "E:/IsaacLab/env_isaaclab/Scripts/python.exe" rl_exp\\tools\\diagnose\\gait_probe.py --self-check
    ... --checkpoint <isaaclab root>\\logs\\rsl_rl\\lizard2_v1\\<run dir>\\model_13999.pt
Output: rl_exp/tools/diagnose/out/gait_probe/gait_probe.json, plus the report on stdout.
Headless is the default; pass ``--viz none`` only if the cfg enables visualizers.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "rl_exp" / "tools" / "diagnose"))

import torch  # noqa: E402

import diag_metrics  # noqa: E402

from isaaclab.app import AppLauncher  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument("--task", default="Lizard2-Flat-Play-v1")
parser.add_argument("--checkpoint", default=None, help="required unless --self-check")
parser.add_argument("--speeds", default="0.5,1.5,2.8", help="one env per speed [m/s]")
parser.add_argument("--seconds", type=float, default=8.0)
parser.add_argument("--seed", type=int, default=123)
parser.add_argument("--contact_n", type=float, default=1.0,
                    help="per-foot vertical force above which the foot is called loaded [N]")
parser.add_argument("--out", type=pathlib.Path,
                    default=_REPO_ROOT / "rl_exp" / "tools" / "diagnose" / "out"
                    / "gait_probe" / "gait_probe.json")
parser.add_argument("--self-check", action="store_true",
                    help="assert the synthetic cases and exit without starting the sim")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()


def self_check() -> None:
    """The synthetic cases, asserted before any simulation is started.

    Three of them are the record's own counterexamples: the toe-roll pose (origin moves, contact
    point does not), the pure-translation pose (both move together), and a foot mesh whose lowest
    point is not below its origin.
    """
    cloud = torch.tensor([[-0.05, -0.05, 0.0], [0.05, 0.05, 0.0],
                          [-0.05, 0.05, 0.04], [0.05, -0.05, 0.04]])
    corners = diag_metrics.pad_point_clouds([cloud, cloud])
    pos = torch.tensor([[[0.0, 0.0, 0.05], [1.0, 0.0, 0.20]]])
    identity = torch.tensor([[0.0, 0.0, 0.0, 1.0]])  # xyzw, the framework's layout
    quat = identity.expand(1, 2, 4).clone()
    # Upside down about y: the lowest vertex is the highest one, so the reading must follow the pose.
    quat[:, 1] = torch.tensor([0.0, 1.0, 0.0, 0.0])
    z = diag_metrics.mesh_min_z(pos, quat, [0, 1], corners)
    assert torch.allclose(z, torch.tensor([[0.05, 0.16]]), atol=1e-6), z
    lowest = diag_metrics.mesh_lowest_point(pos, quat, [0, 1], corners)
    assert torch.allclose(lowest[0, 0], torch.tensor([-0.05, -0.05, 0.05]), atol=1e-6), lowest
    assert torch.allclose(lowest[0, 1], torch.tensor([1.05, 0.05, 0.16]), atol=1e-6), lowest

    zero_v = torch.zeros(1, 1, 3)
    com = torch.tensor([[[0.0, 0.0, 0.0]]])
    omega = torch.tensor([[[0.0, 0.0, 1.0]]])
    toe_roll = diag_metrics.contact_point_velocity(zero_v, omega, com,
                                                   torch.tensor([[[0.1, 0.0, -0.05]]]))
    assert torch.allclose(toe_roll, torch.tensor([[[0.0, 0.1, 0.0]]]), atol=1e-6), toe_roll
    slip = diag_metrics.contact_point_velocity(torch.tensor([[[1.0, 0.0, 0.0]]]), zero_v, com,
                                               torch.tensor([[[0.05, 0.0, 0.0]]]))
    assert torch.allclose(slip, torch.tensor([[[1.0, 0.0, 0.0]]]), atol=1e-6), slip
    # The same world point with the COM moved under it is a point at rest: v + w x r is only about
    # the reference point, and reading it against the LINK origin is the trap the record retracted.
    at_com = diag_metrics.contact_point_velocity(zero_v, omega, torch.tensor([[[0.1, 0.0, 0.0]]]),
                                                 torch.tensor([[[0.1, 0.0, -0.05]]]))
    assert torch.allclose(at_com, torch.zeros(1, 1, 3), atol=1e-6), at_com

    yaw90 = torch.tensor([[0.0, 0.0, 0.7071068, 0.7071068]])  # xyzw: 90 deg about z
    delta = diag_metrics.yaw_frame_offset(torch.tensor([[1.0, 2.0, 0.5]]), yaw90,
                                          torch.tensor([[[1.0, 3.0, 1.1]]]))
    assert torch.allclose(delta, torch.tensor([[[1.0, 0.0, 0.6]]]), atol=1e-6), delta
    print("[SELF-CHECK] geometry, contact-point velocity and yaw frame agree with the hand cases")


def _runs(mask: torch.Tensor) -> list[tuple[int, int]]:
    """Half-open index ranges of consecutive ``True`` in a 1-D bool tensor."""
    spans, start = [], None
    for i, flag in enumerate(mask.tolist()):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            spans.append((start, i))
            start = None
    if start is not None:
        spans.append((start, len(mask)))
    return spans


def summarise(foot: dict, contact_n: float) -> dict:
    """Per-foot summary from the raw series of one env, plus the two joint readings for that leg."""
    force, clearance = foot["force"], foot["sole_clearance_m"]
    fore_aft, contact = foot["foot_fore_aft_m"], foot["contact_speed_horiz_mps"]
    loaded = force > contact_n
    unloaded = ~loaded
    swings = [(i, j) for i, j in _runs(unloaded) if j - i > 1]
    stances = [(i, j) for i, j in _runs(loaded) if j - i > 1]
    clearance_unloaded = clearance[unloaded] if bool(unloaded.any()) else torch.zeros(1)
    out = {
        "body": foot["body"],
        "duty": round(float(loaded.float().mean()), 3),
        "sole_clearance_min_m": round(float(clearance.min()), 4),
        "sole_clearance_unloaded_p50_m": round(float(clearance_unloaded.median()), 4),
        "sole_clearance_unloaded_max_m": round(float(clearance_unloaded.max()), 4),
        "contact_speed_horiz_loaded_p50_mps": (round(float(contact[loaded].median()), 4)
                                               if bool(loaded.any()) else None),
        "contact_speed_horiz_loaded_p95_mps": (round(float(contact[loaded].quantile(0.95)), 4)
                                               if bool(loaded.any()) else None),
        "contact_speed_horiz_unloaded_p50_mps": (round(float(contact[unloaded].median()), 4)
                                                 if bool(unloaded.any()) else None),
        "swing_count": len(swings),
        "swing_fore_aft_excursion_p50_m": (round(float(torch.tensor(
            [float(fore_aft[i:j].max() - fore_aft[i:j].min()) for i, j in swings]).median()), 4)
            if swings else None),
        "swing_forward_p50_m": (round(float(torch.tensor(
            [float(fore_aft[j - 1] - fore_aft[i]) for i, j in swings]).median()), 4)
            if swings else None),
        "stance_fore_aft_drift_p50_m": (round(float(torch.tensor(
            [float(fore_aft[j - 1] - fore_aft[i]) for i, j in stances]).median()), 4)
            if stances else None),
    }
    for joint in ("hip", "hfe"):
        target, actual = foot[f"joint_target_{joint}"], foot[f"joint_actual_{joint}"]
        out[f"{joint}_target_p2p_rad"] = round(float(target.max() - target.min()), 4)
        out[f"{joint}_err_p50_rad"] = round(float((target - actual).abs().median()), 4)
        out[f"{joint}_err_p95_rad"] = round(float((target - actual).abs().quantile(0.95)), 4)
        out[f"{joint}_target_p2p_unloaded_rad"] = (round(float(
            target[unloaded].max() - target[unloaded].min()), 4) if bool(unloaded.any()) else None)
    return out


def main() -> None:
    import importlib.metadata

    import gymnasium as gym  # noqa: E402
    from isaaclab.utils.string import string_to_callable  # noqa: E402
    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper, handle_deprecated_rsl_rl_cfg  # noqa: E402
    from rsl_rl.runners import OnPolicyRunner  # noqa: E402

    import rl_exp.tasks  # noqa: F401,E402

    speeds = [float(token) for token in args_cli.speeds.split(",")]
    spec = gym.spec(args_cli.task)
    cfg = string_to_callable(spec.kwargs["env_cfg_entry_point"])()
    agent_cfg = string_to_callable(spec.kwargs["rsl_rl_cfg_entry_point"])()
    agent_cfg = handle_deprecated_rsl_rl_cfg(agent_cfg, importlib.metadata.version("rsl-rl-lib"))
    cfg.scene.num_envs = len(speeds)
    cfg.seed = args_cli.seed
    cfg.episode_length_s = args_cli.seconds
    env = gym.make(args_cli.task, cfg=cfg)
    wrapper = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
    live = env.unwrapped
    robot = live.scene["robot"]
    sensor = live.scene.sensors["contact_forces"]

    foot_columns = [i for i, name in enumerate(sensor.body_names) if name.endswith("_foot")]
    foot_bodies = [sensor.body_names[i] for i in foot_columns]
    robot_foot_ids = [robot.body_names.index(name) for name in foot_bodies]
    clouds = diag_metrics.pad_point_clouds(
        [diag_metrics.mesh_vertices(diag_metrics.collision_mesh_dir() / f"{name}_collision.obj")
         for name in foot_bodies]).to(live.device)
    joint_names = list(robot.joint_names)
    leg_joint_ids = {}
    for joint in ("hip", "hfe"):
        leg_joint_ids[joint] = {name.split("_")[0]: joint_names.index(f"{name.split('_')[0]}_{joint}_joint")
                                for name in foot_bodies}

    command = torch.tensor([[speed, 0.0, 0.0] for speed in speeds], device=live.device)
    command_term = live.command_manager.get_term("base_velocity")

    runner = OnPolicyRunner(wrapper, agent_cfg.to_dict(), log_dir=None, device=live.device)
    runner.load(args_cli.checkpoint)
    policy = runner.get_inference_policy(device=live.device)

    steps = round(args_cli.seconds / live.step_dt)
    obs = wrapper.get_observations()
    trace: dict[str, list[torch.Tensor]] = {key: [] for key in
                                            ("force", "clearance", "contact", "fore_aft", "done")}
    joint_trace: dict[str, list[torch.Tensor]] = {key: [] for key in ("target", "actual")}
    for step in range(steps):
        command_term.vel_command_b[:] = command
        with torch.no_grad():
            obs, _, _, _ = wrapper.step(policy(obs))
        data = robot.data
        pose, quat = data.body_pos_w.torch, data.body_quat_w.torch
        lowest = diag_metrics.mesh_lowest_point(pose, quat, robot_foot_ids, clouds)
        contact_vel = diag_metrics.contact_point_velocity(
            data.body_com_lin_vel_w.torch[:, robot_foot_ids],
            data.body_ang_vel_w.torch[:, robot_foot_ids],
            data.body_com_pos_w.torch[:, robot_foot_ids], lowest)
        trace["force"].append(sensor.data.net_forces_w.torch[:, foot_columns, 2].clone())
        trace["clearance"].append(lowest[..., 2].clone())
        trace["contact"].append(contact_vel[..., :2].norm(dim=-1).clone())
        trace["fore_aft"].append(diag_metrics.yaw_frame_offset(
            data.root_pos_w.torch, data.root_quat_w.torch, pose)[:, robot_foot_ids, 0].clone())
        trace["done"].append(live.termination_manager.dones.clone())
        joint_trace["target"].append(data.joint_pos_target.torch.clone())
        joint_trace["actual"].append(data.joint_pos.torch.clone())
        if step % 50 == 0:
            print(f"  step {step}/{steps}", flush=True)

    force = torch.stack(trace["force"])
    clearance = torch.stack(trace["clearance"])
    contact = torch.stack(trace["contact"])
    fore_aft = torch.stack(trace["fore_aft"])
    done = torch.stack(trace["done"])
    target = torch.stack(joint_trace["target"])
    actual = torch.stack(joint_trace["actual"])

    report = {"speeds": speeds, "step_dt": live.step_dt, "steps": steps,
              "contact_n": args_cli.contact_n, "foot_bodies": foot_bodies, "envs": []}
    for env_index, speed in enumerate(speeds):
        alive = ~done[:, env_index].cumsum(dim=0).bool()  # up to the first termination
        if not bool(alive.any()):
            alive = torch.ones_like(done[:, env_index])
        entry = {"speed": speed, "frames_alive": int(alive.sum()),
                 "done_frames": int(done[:, env_index].sum()), "feet": []}
        for foot, name in enumerate(foot_bodies):
            leg = name.split("_")[0]
            row = {"body": name, "force": force[alive, env_index, foot],
                   "sole_clearance_m": clearance[alive, env_index, foot],
                   "contact_speed_horiz_mps": contact[alive, env_index, foot],
                   "foot_fore_aft_m": fore_aft[alive, env_index, foot]}
            for joint in ("hip", "hfe"):
                column = leg_joint_ids[joint][leg]
                row[f"joint_target_{joint}"] = target[alive, env_index, column]
                row[f"joint_actual_{joint}"] = actual[alive, env_index, column]
            entry["feet"].append(summarise(row, args_cli.contact_n))
        entry["series"] = {key: [[round(float(x), 5) for x in values[alive, env_index, foot].tolist()]
                                 for foot in range(len(foot_bodies))]
                           for key, values in (("force", force), ("clearance", clearance),
                                               ("contact", contact), ("fore_aft", fore_aft))}
        report["envs"].append(entry)

    args_cli.out.parent.mkdir(parents=True, exist_ok=True)
    args_cli.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))
    (wrapper if wrapper is not None else env).close()


if __name__ == "__main__":
    if args_cli.self_check:
        self_check()
    else:
        if not args_cli.checkpoint:
            parser.error("--checkpoint is required (or pass --self-check)")
        simulation_app = AppLauncher(args_cli).app
        try:
            main()
        except BaseException:
            # app.close() ends the process, so a traceback raised past it never reaches the terminal.
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
            raise
        finally:
            simulation_app.close()
