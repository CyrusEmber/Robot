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
  ``sole_clearance_target_m``  where the deepest vertex would sit if the joints reached their targets
                            in this step, to first order (``body_link_jacobian_w`` times the joint
                            target error). This is the reading that separates the last two
                            explanations: same low clearance as the actual one means the TARGET holds
                            the foot down, a higher one means the actuator does.

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
import hashlib
import json
import os
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
parser.add_argument("--transition_frames", type=int, default=2,
                    help="frames dropped at each end of a stance for the steady contact-speed reading")
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

    # Target prediction: a joint whose world Jacobian lifts the sole by 1 m/rad, error 0.1 rad, and a
    # point 0.05 m below the link origin turned by an angular row of 1 rad/rad. Both terms must count:
    # the second one is what a toe roll does, and dropping it is the mistake being screened for.
    jac = torch.zeros(1, 1, 6, 2)
    jac[0, 0, 2, 0] = 1.0  # linear z from joint 0
    jac[0, 0, 4, 1] = 1.0  # angular y from joint 1
    error = torch.tensor([[[0.1, 0.1]]])  # (N, 1, J)
    offset = torch.tensor([[[0.0, 0.0, -0.05]]])
    moved = diag_metrics.target_vertex_delta(jac, error, offset)
    assert torch.allclose(moved, torch.tensor([[[-0.005, 0.0, 0.1]]]), atol=1e-6), moved
    # The split, on the same case: the z lift is entirely the linear term and the sideways push is
    # entirely the rotation term. A reader that mixes them cannot tell a motion from an estimator
    # artefact, which is the distinction the left front leg needed.
    linear, rotation = diag_metrics.target_vertex_delta_parts(jac, error, offset)
    assert torch.allclose(linear, torch.tensor([[[0.0, 0.0, 0.1]]]), atol=1e-6), linear
    assert torch.allclose(rotation, torch.tensor([[[-0.005, 0.0, 0.0]]]), atol=1e-6), rotation

    # The summary itself, on a series whose answers are known by hand. One swing (frames 4-7) between
    # two stances, and a contact speed that is 9 at each stance's two END frames and 1 in between, so
    # a missing transition cut shows up as a median of 5.0 where the answer is 1.0 -- an exclusion
    # nobody would notice in a real run, where both numbers look plausible.
    series = {
        "body": "test_foot",
        "force": torch.tensor([1.0, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1]),
        "sole_clearance_m": torch.tensor([0.001, 0.001, 0.001, 0.001,
                                          0.005, 0.02, 0.03, 0.01,
                                          0.001, 0.001, 0.001, 0.001]),
        "sole_clearance_target_m": torch.tensor([0.001, 0.001, 0.001, 0.001,
                                                 0.004, 0.015, 0.05, 0.008,
                                                 0.001, 0.001, 0.001, 0.001]),
        "pred_linear_m": torch.full((12,), 0.001),
        "pred_rotation_m": torch.tensor([0.0005] * 4 + [0.002] * 4 + [0.0005] * 4),
        "contact_speed_horiz_mps": torch.tensor([9.0, 1, 1, 9, 0, 0, 0, 0, 9, 1, 1, 9]),
        "foot_fore_aft_m": torch.tensor([0.0, 0.1, 0.2, 0.3, 0.30, 0.25, 0.20, 0.15,
                                         0.4, 0.5, 0.6, 0.7]),
        "joint_target_hip": torch.tensor([0.2, 0.2, 0.2, 0.2, 0.5, 0.5, 0.5, 0.5,
                                          0.2, 0.2, 0.2, 0.2]),
        "joint_actual_hip": torch.full((12,), 0.1),
        "joint_target_hfe": torch.tensor([0.2, 0.2, 0.2, 0.2, 0.5, 0.5, 0.5, 0.5,
                                          0.2, 0.2, 0.2, 0.2]),
        "joint_actual_hfe": torch.full((12,), 0.1),
        "joint_limits_hip": (-1.0, 1.0),
        "joint_limits_hfe": (-1.0, 1.0),
        "joint_kp": 800.0,
        "joint_effort_limit": 180.0,
    }
    summary = summarise(series, 0.5, transition_frames=1)
    # Every ``p50`` here is ``torch.median``, i.e. the LOWER middle value on an even count, not the
    # midpoint of the two -- worth knowing before reading any median in this probe's report. And the
    # transition cut shows up in the p95, not the p50: with the edges the minority, a median votes
    # for the middle frames either way, which is exactly why the p95 was the reading that needed it.
    expected = {
        "duty": 0.667, "swing_count": 1, "steady_frames": 4,
        "sole_clearance_unloaded_p50_m": 0.01, "sole_clearance_unloaded_max_m": 0.03,
        "swing_peak_clearance_p50_m": 0.03, "swing_peak_clearance_target_p50_m": 0.05,
        "swing_peak_target_minus_actual_p50_m": 0.02,
        "contact_speed_horiz_loaded_p50_mps": 1.0, "contact_speed_horiz_loaded_p95_mps": 9.0,
        "contact_speed_horiz_steady_p50_mps": 1.0, "contact_speed_horiz_steady_p95_mps": 1.0,
        "stance_fore_aft_drift_p50_m": 0.3,
        "swing_fore_aft_excursion_p50_m": 0.15, "swing_forward_p50_m": -0.15,
        "hip_target_p2p_rad": 0.3, "hip_err_p50_rad": 0.1, "hip_target_p2p_unloaded_rad": 0.0,
        "hip_target_outside_range_frac": 0.0, "hip_target_margin_min_rad": 0.5,
        "hip_err_p50_in_range_rad": 0.1, "hip_err_p50_out_of_range_rad": None,
        "swing_mid_clearance_p50_m": 0.02, "swing_mid_clearance_target_p50_m": 0.015,
        "unloaded_pred_linear_p50_m": 0.001, "unloaded_pred_rotation_p50_m": 0.002,
        "hip_actual_at_stop_frac": 0.0, "hip_actual_at_stop_dwell_max_frames": 0,
        "hip_out_of_range_actual_at_stop_frac": None, "hip_clip_removed_torque_p50_nm": None,
        "hip_effort_limit_nm": 180.0,
    }
    for key, value in expected.items():
        assert summary[key] == value, (key, summary[key], value)
    print("[SELF-CHECK] geometry, contact-point velocity, yaw frame, target prediction and the "
          "swing/stance summary all agree with the hand cases")


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


def summarise(foot: dict, contact_n: float, transition_frames: int = 2) -> dict:
    """Per-foot summary from the raw series of one env, plus the two joint readings for that leg."""
    force, clearance = foot["force"], foot["sole_clearance_m"]
    fore_aft, contact = foot["foot_fore_aft_m"], foot["contact_speed_horiz_mps"]
    loaded = force > contact_n
    unloaded = ~loaded
    swings = [(i, j) for i, j in _runs(unloaded) if j - i > 1]
    stances = [(i, j) for i, j in _runs(loaded) if j - i > 1]
    # A p95 over every loaded frame mixes the touchdown and liftoff frames, where the foot is changing
    # phase and its contact point moves fast for a real reason. Reading the same quantity with the
    # ends of each stance dropped is what turns "the p95 contains transitions" into a number instead
    # of an excuse; a stance too short to keep a middle frame contributes nothing here.
    steady = torch.zeros_like(loaded)
    for i, j in stances:
        if j - i - 2 * transition_frames >= 1:
            steady[i + transition_frames:j - transition_frames] = True
    # The cleanest comparison of target against actual: at the frame each swing lifts highest, does
    # the target agree it should be that high? The median over ALL unloaded frames cannot answer it,
    # because liftoff and touchdown are frames where the target legitimately asks for the floor.
    peaks, peaks_target = [], []
    for i, j in swings:
        peak = int(clearance[i:j].argmax())
        peaks.append(float(clearance[i:j][peak]))
        peaks_target.append(float(foot["sole_clearance_target_m"][i:j][peak]))
    clearance_unloaded = clearance[unloaded] if bool(unloaded.any()) else torch.zeros(1)
    clearance_target_unloaded = (foot["sole_clearance_target_m"][unloaded] if bool(unloaded.any())
                                 else torch.zeros(1))
    out = {
        "body": foot["body"],
        "duty": round(float(loaded.float().mean()), 3),
        "sole_clearance_min_m": round(float(clearance.min()), 4),
        "sole_clearance_unloaded_p50_m": round(float(clearance_unloaded.median()), 4),
        "sole_clearance_unloaded_max_m": round(float(clearance_unloaded.max()), 4),
        "sole_clearance_target_unloaded_p50_m": round(float(clearance_target_unloaded.median()), 4),
        "sole_clearance_target_minus_actual_p50_m": round(float(
            (clearance_target_unloaded - clearance_unloaded).median()), 4),
        "swing_peak_clearance_p50_m": round(float(torch.tensor(peaks).median()), 4) if peaks else None,
        "swing_peak_clearance_target_p50_m": (round(float(torch.tensor(peaks_target).median()), 4)
                                              if peaks_target else None),
        "swing_peak_target_minus_actual_p50_m": (round(float(torch.tensor(
            [p - a for p, a in zip(peaks_target, peaks)]).median()), 4) if peaks else None),
        "contact_speed_horiz_loaded_p50_mps": (round(float(contact[loaded].median()), 4)
                                               if bool(loaded.any()) else None),
        "contact_speed_horiz_loaded_p95_mps": (round(float(contact[loaded].quantile(0.95)), 4)
                                               if bool(loaded.any()) else None),
        "contact_speed_horiz_steady_p50_mps": (round(float(contact[steady].median()), 4)
                                               if bool(steady.any()) else None),
        "contact_speed_horiz_steady_p95_mps": (round(float(contact[steady].quantile(0.95)), 4)
                                               if bool(steady.any()) else None),
        "steady_frames": int(steady.sum()),
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
        # Mid-swing only, and the prediction split into its two terms. The unloaded-frame median
        # covers liftoff and touchdown as well, and for two legs that swing in alternation it is not
        # even the same phase on both -- which is how a mirrored pair of legs can read as opposites.
        "swing_mid_clearance_p50_m": (round(float(torch.tensor(
            [float(clearance[i + (j - i) // 3:j - (j - i) // 3].median()) for i, j in swings
             if j - i >= 3]).median()), 4) if any(j - i >= 3 for i, j in swings) else None),
        "swing_mid_clearance_target_p50_m": (round(float(torch.tensor(
            [float(foot["sole_clearance_target_m"][i + (j - i) // 3:j - (j - i) // 3].median())
             for i, j in swings if j - i >= 3]).median()), 4)
            if any(j - i >= 3 for i, j in swings) else None),
        "unloaded_pred_linear_p50_m": (round(float(foot["pred_linear_m"][unloaded].median()), 4)
                                       if bool(unloaded.any()) else None),
        "unloaded_pred_rotation_p50_m": (round(float(foot["pred_rotation_m"][unloaded].median()), 4)
                                         if bool(unloaded.any()) else None),
    }
    for joint in ("hip", "hfe"):
        target, actual = foot[f"joint_target_{joint}"], foot[f"joint_actual_{joint}"]
        out[f"{joint}_target_p2p_rad"] = round(float(target.max() - target.min()), 4)
        out[f"{joint}_err_p50_rad"] = round(float((target - actual).abs().median()), 4)
        out[f"{joint}_err_p95_rad"] = round(float((target - actual).abs().quantile(0.95)), 4)
        out[f"{joint}_target_p2p_unloaded_rad"] = (round(float(
            target[unloaded].max() - target[unloaded].min()), 4) if bool(unloaded.any()) else None)
        # Distance to the nearest stop, and how often the target is outside the range outright: a
        # target beyond a limit is the policy asking for a pose this joint cannot reach.
        low, high = foot[f"joint_limits_{joint}"]
        outside = (target < low) | (target > high)
        error = (target - actual).abs()
        out[f"{joint}_target_outside_range_frac"] = round(float(outside.float().mean()), 3)
        out[f"{joint}_target_margin_min_rad"] = round(
            float(torch.minimum(target - low, high - target).min()), 4)
        # The error split by whether the target was reachable at all: "the actuator lags" and "the
        # command was impossible" are different findings, and the sum of the two hides which one a
        # growing error is made of.
        out[f"{joint}_err_p50_in_range_rad"] = (round(float(error[~outside].median()), 4)
                                                if bool((~outside).any()) else None)
        out[f"{joint}_err_p50_out_of_range_rad"] = (round(float(error[outside].median()), 4)
                                                    if bool(outside.any()) else None)
        # The two facts that decide whether clipping an out-of-range reference is right, told apart:
        # a joint SITTING at its stop while the reference keeps pushing is a different situation from
        # a joint still moving normally with a distant reference -- which is how a position PD is
        # asked for torque in the first place. The out-of-range fraction alone cannot tell them apart.
        at_stop = torch.minimum(actual - low, high - actual).abs() < 0.01
        dwell = max((j - i for i, j in _runs(at_stop)), default=0)
        out[f"{joint}_actual_at_stop_frac"] = round(float(at_stop.float().mean()), 3)
        out[f"{joint}_actual_at_stop_dwell_max_frames"] = int(dwell)
        out[f"{joint}_out_of_range_actual_at_stop_frac"] = (
            round(float(at_stop[outside].float().mean()), 3) if bool(outside.any()) else None)
        # What clipping would remove, in torque: stiffness times the part of the reference that lies
        # beyond the stop (only while the joint is still inside it -- once the joint sits at the stop
        # the drive is the same either way, which is the "one saturation into the same saturation"
        # case). Effort limit is reported next to it so the size is readable.
        kp, effort = foot[f"joint_kp"], foot[f"joint_effort_limit"]
        removed = (kp * (target - target.clamp(low, high)).abs())[outside & ~at_stop]
        out[f"{joint}_clip_removed_torque_p50_nm"] = (round(float(removed.median()), 2)
                                                     if bool(removed.numel()) else None)
        out[f"{joint}_effort_limit_nm"] = round(float(effort), 1)
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
    # Position limits, because "the target asks for the sole below the floor" has two very different
    # readings: a pose the policy chose, or a target pressed against a stop it cannot pass.
    pos_limits = robot.data.joint_pos_limits.torch[0]  # (J, 2); the same for every env
    # Stiffness and effort limit from the INSTANTIATED cfg, not copied from the yaml: with position
    # PD a target error is a torque (stiffness times the error), so these two numbers decide what
    # clipping an out-of-range target would actually remove.
    legs = cfg.scene.robot.actuators.get("legs") if hasattr(cfg.scene.robot, "actuators") else None
    legs_kp = float(getattr(legs, "stiffness", 0.0) or 0.0)
    legs_effort = float(getattr(legs, "effort_limit", 0.0) or 0.0)

    command = torch.tensor([[speed, 0.0, 0.0] for speed in speeds], device=live.device)
    command_term = live.command_manager.get_term("base_velocity")

    runner = OnPolicyRunner(wrapper, agent_cfg.to_dict(), log_dir=None, device=live.device)
    runner.load(args_cli.checkpoint)
    policy = runner.get_inference_policy(device=live.device)

    steps = round(args_cli.seconds / live.step_dt)
    obs = wrapper.get_observations()
    trace: dict[str, list[torch.Tensor]] = {key: [] for key in
                                            ("force", "clearance", "clearance_target", "contact",
                                             "fore_aft", "pred_linear", "pred_rotation", "done")}
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
        # Where the sole would be if this step's joint targets were met, about the deepest vertex.
        # The Jacobian's DoF axis leads with the six base columns; nothing commands the base, so they
        # stay zero and the reading is "the joints met their targets, the base did not move".
        joint_error = torch.cat(
            [torch.zeros(pose.shape[0], 1, 6, device=pose.device),
             (data.joint_pos_target.torch - data.joint_pos.torch).unsqueeze(1)], dim=-1)
        linear, rotation = diag_metrics.target_vertex_delta_parts(
            data.body_link_jacobian_w.torch[:, robot_foot_ids], joint_error,
            lowest - pose[:, robot_foot_ids])
        trace["pred_linear"].append(linear[..., 2].clone())
        trace["pred_rotation"].append(rotation[..., 2].clone())
        trace["clearance_target"].append((lowest[..., 2] + linear[..., 2] + rotation[..., 2]).clone())
        trace["done"].append(live.termination_manager.dones.clone())
        joint_trace["target"].append(data.joint_pos_target.torch.clone())
        joint_trace["actual"].append(data.joint_pos.torch.clone())
        if step % 50 == 0:
            print(f"  step {step}/{steps}", flush=True)

    force = torch.stack(trace["force"])
    clearance = torch.stack(trace["clearance"])
    clearance_target = torch.stack(trace["clearance_target"])
    pred_linear = torch.stack(trace["pred_linear"])
    pred_rotation = torch.stack(trace["pred_rotation"])
    contact = torch.stack(trace["contact"])
    fore_aft = torch.stack(trace["fore_aft"])
    done = torch.stack(trace["done"])
    target = torch.stack(joint_trace["target"])
    actual = torch.stack(joint_trace["actual"])

    # Identity, so a report cannot outlive the run that made it unnoticed: the checkpoint it was
    # taken from, by digest, and the command line it was taken with. A crashed run leaves no report
    # (the failure branch exits non-zero before writing), and this makes the surviving one traceable.
    report = {"task": args_cli.task, "speeds": speeds, "step_dt": live.step_dt, "steps": steps,
              "contact_n": args_cli.contact_n, "transition_frames": args_cli.transition_frames,
              "checkpoint": str(args_cli.checkpoint),
              "checkpoint_sha256": hashlib.sha256(
                  pathlib.Path(args_cli.checkpoint).read_bytes()).hexdigest(),
              "argv": sys.argv, "foot_bodies": foot_bodies, "envs": []}
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
                   "sole_clearance_target_m": clearance_target[alive, env_index, foot],
                   "pred_linear_m": pred_linear[alive, env_index, foot],
                   "pred_rotation_m": pred_rotation[alive, env_index, foot],
                   "contact_speed_horiz_mps": contact[alive, env_index, foot],
                   "foot_fore_aft_m": fore_aft[alive, env_index, foot]}
            for joint in ("hip", "hfe"):
                column = leg_joint_ids[joint][leg]
                row[f"joint_target_{joint}"] = target[alive, env_index, column]
                row[f"joint_actual_{joint}"] = actual[alive, env_index, column]
                row[f"joint_limits_{joint}"] = tuple(pos_limits[column].tolist())
                row[f"joint_kp"] = legs_kp
                row[f"joint_effort_limit"] = legs_effort
            entry["feet"].append(summarise(row, args_cli.contact_n, args_cli.transition_frames))
        entry["series"] = {key: [[round(float(x), 5) for x in values[alive, env_index, foot].tolist()]
                                 for foot in range(len(foot_bodies))]
                           for key, values in (("force", force), ("clearance", clearance),
                                               ("contact", contact), ("fore_aft", fore_aft),
                                               ("clearance_target", clearance_target))}
        # Per-frame joint targets and actual positions, per leg. A summary can say one leg behaves
        # differently; only the series says whether it is the same phase done differently or a
        # different phase altogether, which is the comparison the left front leg still needs.
        entry["joint_series"] = {
            f"{name}_{joint}_{kind}": [round(float(x), 5) for x in values[
                alive, env_index, leg_joint_ids[joint][name.split("_")[0]]].tolist()]
            for name in foot_bodies for joint in ("hip", "hfe")
            for kind, values in (("target", target), ("actual", actual))}
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
            # The two losses `app.close()` otherwise takes with it, both measured on a real run (see
            # ablation_harness/baseline_eval.py's failure branch): a traceback raised past close()
            # never reaches the terminal, and close() ends the process with status 0, so a caller
            # reading the status calls a failed run a success -- and then reads the previous
            # report, which is exactly how a crashed probe would look like a fresh reading.
            # Report, flush, then leave with a non-zero status before close can run.
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(1)
        finally:
            simulation_app.close()
