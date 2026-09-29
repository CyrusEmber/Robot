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
  ``joint_out_of_range_*``  on the frames where the target is outside the joint range and the joint is
                            NOT sitting at its stop: how much of the drive projecting the target back
                            onto the limit would remove before the effort limit, and how much SURVIVES
                            it -- the reading that decides "a different saturation" against "the same
                            saturation". Kp alone cannot make it: with an implicit drive the solver
                            clips the composite torque, and it never reaches the data API.
  ``joint_torque_*``/``joint_target_off_default_*``  the same reconstruction over the STEADY part of each
                            stance, for every joint a leg carries -- the blade (``*_foot_joint``)
                            included, against its OWN effort limit (70 N*m where the leg group's is
                            180): how hard the joint is driven, what share of its limit that is, how
                            often the drive reaches the limit, and how far the policy commands the
                            joint away from the zero pose. Beside the command sits what the joint
                            ACTUALLY stands at, the peak rate it moves at while loaded, and how often
                            its drive reverses sign per second: a softer gain is supposed to let the
                            pad settle under load, and "settles" versus "rattles" is the difference
                            between a low peak rate and a high flip rate. ``stance_count`` /
                            ``steady_stance_count`` say how many load cycles the medians rest on --
                            the number that decides whether a reading is a distribution or an anecdote.
                            "All four feet tip up" is an appearance: at Kp 200 / Kd 12 the cap is only
                            reached at 0.35 rad of error, so how much force a blade uses is a number,
                            not something a pose can show. A limit can only be cut for a reason if the
                            drive has been read against it first -- and if the drive never reaches it,
                            cutting it changes nothing and the trial that cut it answers nothing.
                            ``--feet-kp`` / ``--feet-kd`` / ``--feet-effort`` override that group's
                            drive before the env is built, which is how a candidate gain is read on an
                            EXISTING checkpoint without touching a frozen recipe; the override is
                            recorded in the report and the gains are read back out of the sim, so a
                            report cannot claim nominal gains it did not run.
  ``sole_contact_area_m2``  how much of the sole is within ``--sole_band_mm`` of the floor, and how
                            much is under it (``sole_through_area_m2``), from the collision mesh's
                            triangles rotated by the live pose -- the reading for "bearing weight on a
                            toe or an edge", which force alone cannot see. Read on the steady part of
                            each stance; the band is declared, never inferred, because a band with no
                            floor on its underside scores grinding as contact.
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
import json
import math
import os
import pathlib
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "rl_exp" / "tools" / "diagnose"))

import torch  # noqa: E402

import diag_metrics  # noqa: E402

from rl_exp.tools.runrecord import binding  # noqa: E402
from rl_exp.tasks import obs_protocol  # noqa: E402

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
parser.add_argument("--sole_band_mm", type=float, default=2.0,
                    help="sole within this height of the floor is called on the floor [mm]")
parser.add_argument("--sole_eps_mm", type=float, default=0.0,
                    help="sole below -this is called through the floor, not contact [mm]")
parser.add_argument("--feet-kp", type=float, default=None,
                    help="override the feet group's stiffness [N*m/rad] before the env is built: a "
                         "diagnostic of the DRIVE, not a recipe -- the probe owns its cfg, the "
                         "override lands in the report, and the per-joint gains are read back out of "
                         "the sim, so a report cannot claim nominal gains it did not run")
parser.add_argument("--feet-kd", type=float, default=None,
                    help="override the feet group's damping [N*m*s/rad]")
parser.add_argument("--feet-effort", type=float, default=None,
                    help="override the feet group's effort limit [N*m]")
parser.add_argument("--freeze-feet-action", action="store_true",
                    help="zero the blade joints' action columns, i.e. run the v2 configuration "
                         "(blade keeps its PD, its target stays at the default pose) on the policy it "
                         "was NOT trained with. This is the only way to read a candidate blade gain "
                         "without retraining: without it, overriding the gain leaves the policy free "
                         "to COMMAND the blade, and an unadapted policy drives that command far "
                         "outside anything it ever asked for")
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
        "joint_kp_sim_hip": 800.0, "joint_kp_sim_hfe": 800.0,
        "joint_kd_sim_hip": 40.0, "joint_kd_sim_hfe": 40.0,
        # Per joint, because the row key has to be: one shared key is overwritten once per joint in the
        # loop that fills it, so the blade's 70 would silently become the limit the hip is scored
        # against -- every torque share in the report would be wrong by a factor of 180/70.
        "joint_effort_limit_hip": 180.0, "joint_effort_limit_hfe": 180.0,
        "joint_effort_limit_foot": 70.0,
        "joint_vel_hip": torch.zeros(12), "joint_vel_hfe": torch.zeros(12),
        "joint_default_hip": 0.0, "joint_default_hfe": 0.0,
        # The blade, whose numbers this reading was added for: Kp 200, Kd 12, its own 70 N*m cap. Target
        # 0.3 against actual 0.1 is 40 N*m at rest, and the ONE steady frame carrying -3 rad/s drives it
        # to |40 + 36| = 76 -- past the cap, on 1 of the 4 steady frames. Median (40) and saturated share
        # (0.25) are therefore different readings of the same series, and a reader that had only one of
        # them could call this joint either barely loaded or saturated. The last steady frame carries
        # +4 rad/s instead, which drives the SAME joint to 40 - 48 = -8: one frame on the other side of
        # zero, so the sign-flip reading has something to count (two flips over four steady frames) and
        # the offset/velocity readings have a peak to report. A fixture where every steady frame pushes
        # the same way would pass a broken sign counter.
        "joint_target_foot": torch.full((12,), 0.3),
        "joint_actual_foot": torch.full((12,), 0.1),
        "joint_vel_foot": torch.tensor([0.0, 0.0, -3.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                                        0.0, 4.0, 0.0, 0.0]),
        "joint_default_foot": 0.0,
        "joint_limits_foot": (-0.6, 0.6),
        "joint_kp_sim_foot": 200.0, "joint_kd_sim_foot": 12.0,
        # Sole area 0.02 m^2 on the four TRANSITION frames and 0.004 on the steady ones, through-floor
        # 0.0005 everywhere: reading the loaded frames instead of the steady ones gives 0.02 and looks
        # like a flat foot, which is the mistake this pair of numbers is here to catch.
        "sole_area_m2": 0.16418,
        "sole_contact_area_m2": torch.tensor([0.02, 0.004, 0.004, 0.02, 0, 0, 0, 0,
                                              0.02, 0.004, 0.004, 0.02]),
        "sole_through_area_m2": torch.full((12,), 0.0005),
        # 45 deg on the transition frames and 10 on the steady ones, for the same reason as the area
        # above: a reading that skips the transition cut reports 45.
        "sole_cap_m2": 0.02,
        "sole_tilt_deg": torch.tensor([45.0, 10, 10, 45, 0, 0, 0, 0, 45, 10, 10, 45]),
        "sole_low_edge_xy": torch.tensor([[0.5, 0.0]] * 12),
    }
    summary = summarise(series, 0.5, transition_frames=1, step_dt=0.02)
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
        "hip_clip_removed_torque_after_limit_p50_nm": None,
        "hip_out_of_range_effort_saturated_frac": None,
        "hip_effort_limit_nm": 180.0,
        # 0.004 m^2 on the steady frames and 0.02 on the transition ones, so a reading that skips the
        # transition cut reports 0.02; 0.004 / 0.16418 = 0.024.
        "sole_area_m2": 0.16418, "sole_contact_area_p50_m2": 0.004,
        "sole_contact_ratio_p50": 0.024, "sole_through_area_p50_m2": 0.0005,
        "sole_cap_m2": 0.02, "sole_contact_of_cap_p50": 0.2,
        "sole_tilt_deg_p50": 10.0, "sole_low_edge_xy_p50": [0.5, 0.0],
        # The drive readings, on the hand case above: the blade is at 40 N*m on three of the four steady
        # frames and 76 on the one that reaches at 3 rad/s, so its p50 is 40 and its saturated share is
        # 1/4. 40/70 = 0.571. The hip's 800 * 0.1 = 80 N*m -- 0.444 of ITS 180 -- is asserted beside it
        # so the loop is shown to read every joint against its own limit and not one shared number, which
        # is the mistake a single ``joint_effort_limit`` in the row would have hidden.
        "hip_torque_steady_p50_nm": 80.0, "hip_torque_steady_max_nm": 80.0,
        "hip_torque_frac_of_limit_p50": 0.444, "hip_effort_saturated_frac_steady": 0.0,
        "hip_target_off_default_steady_p50_rad": 0.2,
        "hip_actual_off_default_steady_p50_rad": 0.1, "hip_vel_steady_max_abs": 0.0,
        "hip_torque_sign_flips_per_s": 0.0,
        "foot_torque_steady_p50_nm": 40.0, "foot_torque_steady_max_nm": 76.0,
        "foot_torque_loaded_p50_nm": 40.0, "foot_torque_frac_of_limit_p50": 0.571,
        "foot_effort_saturated_frac_steady": 0.25, "foot_target_off_default_steady_p50_rad": 0.3,
        # The blade stands 0.1 rad off its flat pose under this fixture's load while being COMMANDED to
        # 0.3: the two numbers are the two claims, and the fixture is built so they differ.
        "foot_actual_off_default_steady_p50_rad": 0.1, "foot_vel_steady_max_abs": 4.0,
        # 40 -> 76 -> -8 -> 40 over the four steady frames: two sign changes, 0.02 s each.
        "foot_torque_sign_flips_per_s": 25.0,
        # Two load cycles here, both long enough to keep a middle frame at transition_frames=1: the
        # sample count a comparison needs before its medians mean anything.
        "stance_count": 2, "steady_stance_count": 2,
    }
    for key, value in expected.items():
        assert summary[key] == value, (key, summary[key], value)
    print("[SELF-CHECK] geometry, contact-point velocity, yaw frame, target prediction and the "
          "swing/stance summary all agree with the hand cases; the blade reads its own 70 N*m limit "
          "(p50 40 N*m, 1 saturated frame of 4), its commanded and its ACTUAL offset, its peak rate "
          "and two drive sign flips over four steady frames, while the hip is scored against its own "
          "180 N*m")
    self_check_sole_area()
    self_check_clip_saturation()


def self_check_sole_area() -> None:
    """Controlled poses for the sole-on-floor reading: flat, toe, edge, airborne, through the floor.

    The reading is "projected area of the sole within a band of the floor", and every branch of the
    clip is exercised here on a pose whose answer is known by hand, because a plausible-looking wrong
    number is exactly what this metric must not produce: a band with no floor on its underside reads a
    foot pressed deeper as a foot lying flatter, and a whole-triangle test would quantise the answer to
    the mesh's 48 triangles.
    """
    # One flat 0.1 x 0.1 m plate lying on the floor, wound so its normal points down: the denominator
    # counts link-frame downward faces, which is what an outward-wound collision mesh's sole is.
    plate = torch.tensor([[[0.0, 0.0, 0.0], [0.1, 0.1, 0.0], [0.1, 0.0, 0.0]],
                          [[0.0, 0.0, 0.0], [0.0, 0.1, 0.0], [0.1, 0.1, 0.0]]])
    assert abs(diag_metrics.sole_area_m2(plate) - 0.01) < 1e-9, diag_metrics.sole_area_m2(plate)
    on_floor, through = diag_metrics.ground_contact_area_m2(plate, 0.002, 0.0)
    assert abs(float(on_floor.sum()) - 0.01) < 1e-6, on_floor
    assert float(through.sum()) == 0.0, through
    # Airborne 0.1 m up: the whole sole is outside the band, and neither reading may be positive.
    airborne, _ = diag_metrics.ground_contact_area_m2(plate + torch.tensor([0.0, 0.0, 0.1]), 0.002, 0.0)
    assert float(airborne.sum()) == 0.0, airborne
    # 10 mm through the floor with eps = 0: contact area 0 (nothing of it is within the band) and the
    # penetration carries the full 0.01 m^2. A reading that merges the two calls this a flat foot.
    pressed, below = diag_metrics.ground_contact_area_m2(plate - torch.tensor([0.0, 0.0, 0.01]), 0.002, 0.0)
    assert float(pressed.sum()) == 0.0, pressed
    assert abs(float(below.sum()) - 0.01) < 1e-6, below
    # Toe support: the same plate pitched 45 deg about y, resting on its low edge. Only the strip
    # within band_m of the floor can be in contact, and on a 45 deg slope that strip's projected
    # width equals the band: 0.1 m x 1 mm = 1e-4 m^2, against 7.07e-3 m^2 of projected plate.
    theta = math.pi / 4
    pitched = plate.clone()
    pitched[..., 0] = plate[..., 0] * math.cos(theta)
    pitched[..., 2] = -plate[..., 0] * math.sin(theta) + 0.1 * math.sin(theta)
    toe_only, toe_through = diag_metrics.ground_contact_area_m2(pitched, 0.001, 0.0)
    assert abs(float(toe_only.sum()) - 1e-4) < 1e-9, toe_only
    assert float(toe_through.sum()) < 1e-12, toe_through
    assert abs(diag_metrics.sole_area_m2(pitched) - 0.1 * 0.1 * math.cos(theta)) < 1e-9

    # Which part of the pad is lowest, in the pad's own frame. Identity (xyzw (0,0,0,1)) must leave
    # world-down where it was, and a 30 deg pitch about the link's x must move it to (0, -sin, -cos):
    # the two components are what says "toe" against "side edge", and acos of the third is the tilt.
    down = diag_metrics.body_down_in_link(torch.tensor([[[0.0, 0.0, 0.0, 1.0]]]), [0])
    assert torch.allclose(down, torch.tensor([[[0.0, 0.0, -1.0]]]), atol=1e-6), down
    theta = math.radians(30)
    pitched_quat = torch.tensor([[[math.sin(theta / 2), 0.0, 0.0, math.cos(theta / 2)]]])
    tilted = diag_metrics.body_down_in_link(pitched_quat, [0])
    assert torch.allclose(tilted, torch.tensor([[[0.0, -math.sin(theta), -math.cos(theta)]]]),
                          atol=1e-6), tilted

    # The asset's own four feet, identity orientation, floor at each mesh's lowest vertex: what a flat
    # floor can give this shape at all. Measured 2026-09-28 -- 1 mm band 0.003422 m^2, 2 mm 0.013352,
    # 5 mm 0.051689, 10 mm 0.116479 of a 0.164180 m^2 denominator. The pad is curved and its faces are
    # ~2 cm across, so the reading steps rather than slides: its lowest vertices sit at 0, 1.668,
    # 5.302 and 9.845 mm, and each ring a band crosses adds a whole triangle's area (~0.01 m^2), which
    # is also why no pose can approach a ratio of 1 and why the threshold needs the same measurement
    # behind it. 2 mm and 5 mm are asserted away from those rings so a hair of float noise cannot move
    # them across a step.
    areas, flat = {}, {}
    for name in ("lf", "rf", "rl", "rr"):
        mesh = diag_metrics.mesh_triangles(diag_metrics.collision_mesh_dir(
            obs_protocol.family_of("Lizard2-Flat-v1")) / f"{name}_foot_collision.obj")
        assert mesh.shape == (48, 3, 3), mesh.shape
        areas[name] = diag_metrics.sole_area_m2(mesh)
        grounded = mesh - torch.tensor([0.0, 0.0, float(mesh[..., 2].min())])
        flat[name] = {band: float(diag_metrics.ground_contact_area_m2(grounded, band, 0.0)[0].sum())
                      for band in (0.001, 0.005)}
    assert all(abs(area - 0.16418) < 2e-4 for area in areas.values()), areas
    assert abs(flat["lf"][0.001] - 0.003422) < 1e-6, flat["lf"]
    assert abs(flat["lf"][0.005] - 0.051689) < 1e-6, flat["lf"]
    print("[SELF-CHECK] sole-on-floor area: flat plate full, airborne and through-floor zero contact, "
          f"45 deg toe support 1e-4 m^2, and the four feet read {flat['lf'][0.001]:.6f} m^2 at a 1 mm "
          f"band against a {areas['lf']:.6f} m^2 denominator")

    # Two families, two trees, on purpose (2026-09-28): the retired lizard family's rl hull is the
    # flat one its own physics still carries, and lizard2's is the repaired dome. This asserts the
    # isolation itself -- resolution per family plus the difference it exists to preserve -- so a
    # later change that points both at one tree fails here rather than in a report nobody re-reads.
    for family, expected_cap in (("lizard", 0.119282), ("lizard2", 0.013352)):
        tree = diag_metrics.collision_mesh_dir(family)
        assert tree.is_dir(), tree
        hull = diag_metrics.mesh_triangles(tree / "rl_foot_collision.obj")
        grounded = hull - torch.tensor([0.0, 0.0, float(hull[..., 2].min())])
        cap = float(diag_metrics.ground_contact_area_m2(grounded, 0.002, 0.0)[0].sum())
        assert abs(cap - expected_cap) < 1e-6, (family, tree, cap, expected_cap)
    print("[SELF-CHECK] family isolation: lizard still reads its flat rl hull (0.119282 m^2 cap), "
          "lizard2 the repaired one (0.013352) -- one declaration per family, two trees")


def self_check_clip_saturation() -> None:
    """The "same saturation into the same saturation" case, on numbers known by hand.

    Limits +-0.6 rad, Kp 800, Kd 40, effort limit 180 N*m, and no in-range frame in the chosen set, so
    every number below is decided by the three frames that count: the illustrative one from the record
    (``acceptance/records/2026-09-23-lizard2-v1-gait-skate.md`` ⑦ 7, a joint at 0.4 asked for 0.7 at
    2 rad/s) plus a high-speed and a mirrored one. Frame 0 asks 160 N*m against 80 after projecting:
    both UNDER the effort limit, so nothing but the projection separates them and clipping really does
    take 80. Frames 1 and 4 ask 480 against 400 and -360 against -280: each pair clips to the same
    +-180, so what clipping takes there is ZERO -- the case the pre-limit number cannot see, and the
    reason the p50 after the limit (0.0) is smaller than the one before it (80.0). Frame 2 (joint at
    its stop) and frame 3 (target in range) must contribute nothing at all.
    """
    kp, kd, effort, low, high = 800.0, 40.0, 180.0, -0.6, 0.6
    target = torch.tensor([0.7, 0.7, 0.7, 0.5, -0.7])
    actual = torch.tensor([0.4, 0.1, 0.595, 0.1, -0.1])
    vel = torch.tensor([2.0, 0.0, 0.0, 0.0, -3.0])
    foot = {
        "body": "test_foot",
        # Only the joint readings are under test here; the gait inputs stay quiet so a mistake in the
        # torque arithmetic cannot hide behind an unrelated one.
        "force": torch.zeros(5), "sole_clearance_m": torch.zeros(5),
        "sole_clearance_target_m": torch.zeros(5), "pred_linear_m": torch.zeros(5),
        "pred_rotation_m": torch.zeros(5), "contact_speed_horiz_mps": torch.zeros(5),
        "foot_fore_aft_m": torch.zeros(5),
        "joint_target_hip": target, "joint_actual_hip": actual, "joint_vel_hip": vel,
        "joint_target_hfe": target, "joint_actual_hfe": actual, "joint_vel_hfe": vel,
        "joint_limits_hip": (low, high), "joint_limits_hfe": (low, high),
        "joint_kp_sim_hip": kp, "joint_kp_sim_hfe": kp,
        "joint_kd_sim_hip": kd, "joint_kd_sim_hfe": kd,
        "joint_effort_limit_hip": effort, "joint_effort_limit_hfe": effort,
        "joint_effort_limit_foot": effort,
        # The blade rides the same loop, and here it must produce the same silence as the sole readings:
        # no frame carries load, so there is no window to take a drive reading over.
        "joint_target_foot": target, "joint_actual_foot": actual, "joint_vel_foot": vel,
        "joint_limits_foot": (low, high), "joint_default_foot": 0.0,
        "joint_kp_sim_foot": kp, "joint_kd_sim_foot": kd,
        # No frame carries load here, so the sole readings have no window to be taken over: None, not
        # zero, because a foot that was never loaded was never measured.
        "sole_area_m2": 0.16418, "sole_contact_area_m2": torch.zeros(5),
        "sole_through_area_m2": torch.zeros(5), "sole_cap_m2": 0.02,
        "sole_tilt_deg": torch.zeros(5), "sole_low_edge_xy": torch.zeros(5, 2),
    }
    summary = summarise(foot, 0.5, step_dt=0.02)
    # 4 of 5 targets are outside; only frame 2 has the joint within 5 mrad of its stop, and it is the
    # one outside frame that sits there, so the two fractions disagree on purpose. |target - actual|
    # over the outside frames is [0.3, 0.6, 0.105, 0.6] -> the lower middle is 0.3.
    expected = {
        "hip_target_outside_range_frac": 0.8, "hip_actual_at_stop_frac": 0.2,
        "hip_actual_at_stop_dwell_max_frames": 1, "hip_out_of_range_actual_at_stop_frac": 0.25,
        "hip_err_p50_out_of_range_rad": 0.3,
        "hip_clip_removed_torque_p50_nm": 80.0,
        "hip_clip_removed_torque_after_limit_p50_nm": 0.0,
        "hip_out_of_range_effort_saturated_frac": 0.667,
        "hip_effort_limit_nm": 180.0, "hip_kp_sim": 800.0, "hip_kd_sim": 40.0,
        # Every drive reading is None here for the same reason the sole readings below are: no frame
        # carries load, so a joint that never bore weight was never measured. Zero would be a reading,
        # and "the blade used no force" is a conclusion this fixture contains nothing to support.
        "hip_torque_steady_p50_nm": None, "hip_torque_steady_max_nm": None,
        "foot_torque_steady_p50_nm": None, "foot_torque_loaded_p50_nm": None,
        "foot_torque_frac_of_limit_p50": None, "foot_effort_saturated_frac_steady": None,
        "foot_target_off_default_steady_p50_rad": None,
        "foot_actual_off_default_steady_p50_rad": None, "foot_vel_steady_max_abs": None,
        "foot_torque_sign_flips_per_s": None, "steady_stance_count": 0,
        "sole_area_m2": 0.16418, "sole_contact_area_p50_m2": None,
        "sole_contact_ratio_p50": None, "sole_through_area_p50_m2": None,
        "sole_cap_m2": 0.02, "sole_contact_of_cap_p50": None,
        "sole_tilt_deg_p50": None, "sole_low_edge_xy_p50": None,
    }
    for key, value in expected.items():
        assert summary[key] == value, (key, summary[key], value)
    print("[SELF-CHECK] the torque clipping removes survives the effort limit on one of the three "
          "counted frames, and the pre-limit p50 (80.0) is not the post-limit p50 (0.0)")


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


def summarise(foot: dict, contact_n: float, transition_frames: int = 2,
              step_dt: float | None = None) -> dict:
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
        # How many load cycles this foot actually produced here, and how many of them kept a middle
        # frame to be read on. A per-foot, per-tier sample count is the one number a comparison across
        # runs needs before its medians mean anything: a stance count in the single digits is a
        # different claim from the same reading over hundreds of cycles, and the difference is
        # invisible in the medians themselves.
        "stance_count": len(stances),
        "steady_stance_count": sum(1 for i, j in stances if j - i - 2 * transition_frames >= 1),
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
    for joint in ("hip", "hfe", "foot"):
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
        # the drive is the same either way). Kp alone makes that an UPPER BOUND: it carries no damping
        # term and no effort limit, so it reads what the COMMAND differs by, not what the joint feels.
        # The solver clips the composite torque, and for an implicit drive ``applied_torque`` is all
        # zero, so reconstructing it is the only reading available -- the same
        # ``tau = K (q* - q) - D q_dot`` the paper's torque terms use (``parkour_mdp._pd_torque``).
        # Gains come from the sim rather than the cfg: gain randomization writes into the sim.
        kp, kd = foot[f"joint_kp_sim_{joint}"], foot[f"joint_kd_sim_{joint}"]
        effort = foot[f"joint_effort_limit_{joint}"]
        chosen = outside & ~at_stop
        removed = (kp * (target - target.clamp(low, high)).abs())[chosen]
        out[f"{joint}_clip_removed_torque_p50_nm"] = (round(float(removed.median()), 2)
                                                     if bool(removed.numel()) else None)
        # The composite the solver actually clips: ``Kp (q* - q) - Kd q_dot``, reconstructed rather than
        # read, because an implicit drive leaves ``applied_torque`` all zero. One expression serves both
        # readings below -- the clipping difference and the torque the joint is being driven with -- so
        # the two cannot disagree about what "the drive" is.
        cmd = kp * (target - actual) - kd * foot[f"joint_vel_{joint}"]
        # The same difference read the way the solver sees it: two commands, each clipped at the effort
        # limit, then subtracted. On a frame that is already saturated the clips agree and the
        # difference is zero -- "one saturation into the same saturation" -- which the pre-limit number
        # above cannot show, because that number is largest in exactly those frames. An effort limit of
        # zero (or none recorded) is a missing reading, not a saturated one, so it reports None instead
        # of a false zero, and the damping term belongs here because the limit bounds the sum.
        if effort > 0.0 and bool(chosen.any()):
            proj = kp * (target.clamp(low, high) - actual) - kd * foot[f"joint_vel_{joint}"]
            after = (cmd.clamp(-effort, effort) - proj.clamp(-effort, effort)).abs()[chosen]
            out[f"{joint}_clip_removed_torque_after_limit_p50_nm"] = round(float(after.median()), 2)
            out[f"{joint}_out_of_range_effort_saturated_frac"] = round(
                float((cmd.abs() >= effort)[chosen].float().mean()), 3)
        else:
            out[f"{joint}_clip_removed_torque_after_limit_p50_nm"] = None
            out[f"{joint}_out_of_range_effort_saturated_frac"] = None
        out[f"{joint}_effort_limit_nm"] = round(float(effort), 1)
        # The gains the two torque numbers above were made from, for the same reason the effort limit
        # sits next to them: a torque reading whose stiffness is not in the report cannot be re-read.
        out[f"{joint}_kp_sim"] = round(float(kp), 1)
        out[f"{joint}_kd_sim"] = round(float(kd), 1)
        # How hard this joint is driven while it bears weight, against its OWN limit: a share of "the leg
        # limit" would be the wrong denominator for the one joint this reading was added for (blade 70
        # N*m, leg 180). Read on the steady part of each stance for the reason the contact speed is --
        # a p95 or a max over every loaded frame is mostly liftoff and touchdown, where the joint is
        # changing phase for a real reason. A cap only binds if the drive reaches it; a drive that never
        # touches it is exactly the case where cutting it cannot have caused whatever the trial then
        # measures, which is why this number comes before any such trial rather than after it.
        torque_window = steady if bool(steady.any()) else loaded
        if bool(torque_window.any()):
            drive = cmd[torque_window].abs()
            out[f"{joint}_torque_steady_p50_nm"] = round(float(drive.median()), 2)
            out[f"{joint}_torque_steady_max_nm"] = round(float(drive.max()), 2)
            out[f"{joint}_torque_loaded_p50_nm"] = (round(float(cmd[loaded].abs().median()), 2)
                                                    if bool(loaded.any()) else None)
            out[f"{joint}_torque_frac_of_limit_p50"] = (round(float(drive.median()) / effort, 3)
                                                        if effort > 0.0 else None)
            out[f"{joint}_effort_saturated_frac_steady"] = (round(float(
                (drive >= effort).float().mean()), 3) if effort > 0.0 else None)
            # How far the policy commands this joint away from the zero pose while the foot bears
            # weight: the reading that answers "is the pose the policy's own command" without changing
            # anything about the run, the same distinction the sole-clearance target made for the knee.
            out[f"{joint}_target_off_default_steady_p50_rad"] = round(float(
                (target - foot[f"joint_default_{joint}"])[torque_window].abs().median()), 4)
            # ... and what the joint ACTUALLY sits at while the foot bears weight. Target and actual
            # are two different claims about the pose: a blade that is commanded to the flat pose and
            # still stands at 0.3 rad is a blade the drive cannot hold back, which is the question a
            # softer gain is supposed to answer -- and the one the load under it is really applying.
            out[f"{joint}_actual_off_default_steady_p50_rad"] = round(float(
                (actual - foot[f"joint_default_{joint}"])[torque_window].abs().median()), 4)
            # Peak rate while loaded: a pad that rattles against the floor shows up here before it
            # shows up in a median, and a pad that is compliant under load moves slowly. Max is used
            # rather than a quantile because it is a hand-checkable number in the synthetic case, and
            # this reading's job is to catch "does it chatter at all", not to describe a tail.
            out[f"{joint}_vel_steady_max_abs"] = round(float(
                foot[f"joint_vel_{joint}"][torque_window].abs().max()), 3)
            # Chatter as a rate and not a vibe: how often the drive REVERSES SIGN while the foot is on
            # the floor. A spring holding a one-sided load keeps its sign; a blade oscillating against
            # the floor flips it every cycle. This is the reading that distinguishes "softer gain lets
            # the pad settle" from "softer gain lets the pad rattle", which is the failure mode a
            # weaker gain is meant to avoid. None without a step time: a per-second rate whose
            # denominator is unknown is not a rate.
            ordered = cmd[torque_window]
            flips = int((ordered[1:] * ordered[:-1] < 0).sum()) if ordered.numel() > 1 else 0
            out[f"{joint}_torque_sign_flips_per_s"] = (round(flips / (step_dt * ordered.numel()), 2)
                                                      if step_dt else None)
        else:
            # A joint that never bore weight was never measured: None, not zero, for the same reason the
            # sole-area readings report None on a foot that was never loaded.
            for key in ("torque_steady_p50_nm", "torque_steady_max_nm", "torque_loaded_p50_nm",
                        "torque_frac_of_limit_p50", "effort_saturated_frac_steady",
                        "target_off_default_steady_p50_rad", "actual_off_default_steady_p50_rad",
                        "vel_steady_max_abs", "torque_sign_flips_per_s"):
                out[f"{joint}_{key}"] = None
    # How much of the sole is on the floor, which is the reading for "bearing weight on a toe or an
    # edge": area, not force, so it says WHERE the foot is loaded and not only that it is. Read on the
    # steady part of each stance -- a foot is legitimately on its edge for a frame at liftoff and
    # touchdown, and including those frames is what would make the reading untargetable. The
    # penetration area is reported beside it, never inside it: a sole pressed through the floor has
    # less in the band, so folding the two together would score grinding as contact.
    window = steady if bool(steady.any()) else loaded
    contact_area = foot["sole_contact_area_m2"]
    through_area = foot["sole_through_area_m2"]
    sole_area = foot["sole_area_m2"]
    cap = foot["sole_cap_m2"]
    tilt = foot["sole_tilt_deg"]
    edge = foot["sole_low_edge_xy"]
    out["sole_area_m2"] = round(float(sole_area), 6)
    # The reference that makes the area readable: how much of THIS pad can lie within the declared band
    # when its own lowest point is on a flat floor. A constant of the mesh, so the measured area over
    # it is "how close to resting flat", and the curvature of the pad stops being mistaken for a pose.
    out["sole_cap_m2"] = round(float(cap), 6)
    out["sole_contact_area_p50_m2"] = (round(float(contact_area[window].median()), 5)
                                      if bool(window.any()) else None)
    out["sole_contact_of_cap_p50"] = (round(float(contact_area[window].median()) / cap, 3)
                                      if bool(window.any()) and cap > 0.0 else None)
    out["sole_contact_ratio_p50"] = (round(float(contact_area[window].median()) / sole_area, 3)
                                     if bool(window.any()) and sole_area > 0.0 else None)
    out["sole_through_area_p50_m2"] = (round(float(through_area[window].median()), 5)
                                      if bool(window.any()) else None)
    # Which part of the pad is lowest, and by how much the sole is off level: area alone cannot tell a
    # foot resting on its toe from a foot whose curved pad just touches, because the second one also
    # reads a small patch. The direction is reported as its two components rather than an angle, which
    # would have to be averaged around a circle.
    out["sole_tilt_deg_p50"] = round(float(tilt[window].median()), 2) if bool(window.any()) else None
    out["sole_low_edge_xy_p50"] = ([round(float(edge[window, 0].median()), 3),
                                    round(float(edge[window, 1].median()), 3)]
                                   if bool(window.any()) else None)
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
    # The feet group's drive, overridden BEFORE the env exists: the one way to ask "how does this
    # blade behave at these gains" without touching a frozen recipe. Both the deprecated and the sim
    # field are written, so the value cannot be silently dropped by whichever one this fork reads.
    # The reading stays honest because the gains and the limit are read back OUT of the sim per joint
    # and printed in the report: an override that did not take shows up as the old number.
    feet_overrides = {"stiffness": args_cli.feet_kp, "damping": args_cli.feet_kd,
                      "effort_limit": args_cli.feet_effort}
    for field, value in feet_overrides.items():
        if value is not None:
            setattr(cfg.scene.robot.actuators["feet"], field, value)
            if field == "effort_limit":
                cfg.scene.robot.actuators["feet"].effort_limit_sim = value
    env = gym.make(args_cli.task, cfg=cfg)
    wrapper = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
    live = env.unwrapped
    robot = live.scene["robot"]
    sensor = live.scene.sensors["contact_forces"]

    # Which columns of the concatenated action belong to the blade joints, read from the action
    # manager rather than assumed: both the term order and each term's joint order are the framework's,
    # and a hardcoded offset would zero the wrong four numbers while looking like it worked. Zeroing
    # the raw action IS "target = the default pose" because the term is built with use_default_offset
    # (target = default + scale * action), which makes the mask self-verifying: the blade's commanded
    # offset in the report reads ~0 exactly when the mask took.
    frozen_foot_columns: list[int] = []
    action_offset = 0
    for term_name in live.action_manager.active_terms:
        action_term = live.action_manager.get_term(term_name)
        for position, joint_name in enumerate(action_term._joint_names):
            if joint_name.endswith("_foot_joint"):
                frozen_foot_columns.append(action_offset + position)
        action_offset += len(action_term._joint_names)
    if action_offset != live.action_manager.total_action_dim:
        parser.error(f"action interface read as {action_offset} columns, manager says "
                     f"{live.action_manager.total_action_dim}: refusing to mask against a guess")
    if args_cli.freeze_feet_action and not frozen_foot_columns:
        parser.error("--freeze-feet-action found no *_foot_joint in the action interface")

    foot_columns = [i for i, name in enumerate(sensor.body_names) if name.endswith("_foot")]
    foot_bodies = [sensor.body_names[i] for i in foot_columns]
    robot_foot_ids = [robot.body_names.index(name) for name in foot_bodies]
    # The shank each pad hangs off. A pad's orientation is the leg chain's, composed with the blade's
    # own angle, so a tilted sole cannot be attributed to either one without the shank's orientation.
    robot_shank_ids = [robot.body_names.index(name.split("_")[0] + "_kfe") for name in foot_bodies]
    # The tree this family declares, not a global one: a reading off another family's mesh is how a
    # report silently stops describing the run it was taken from.
    family = obs_protocol.family_of(args_cli.task)
    family_mesh_dir = diag_metrics.collision_mesh_dir(family)
    clouds = diag_metrics.pad_point_clouds(
        [diag_metrics.mesh_vertices(family_mesh_dir / f"{name}_collision.obj")
         for name in foot_bodies]).to(live.device)
    foot_meshes = torch.stack([diag_metrics.mesh_triangles(
        family_mesh_dir / f"{name}_collision.obj") for name in foot_bodies]).to(live.device)
    sole_areas = [diag_metrics.sole_area_m2(mesh) for mesh in foot_meshes]
    sole_band, sole_eps = args_cli.sole_band_mm / 1000.0, args_cli.sole_eps_mm / 1000.0
    # What each pad can put within the declared band when it rests flat, i.e. its own lowest point on
    # the floor: a constant of the mesh, and the only reference that makes the measured area mean "how
    # close to flat" instead of "how curved is this pad".
    sole_caps = [float(diag_metrics.ground_contact_area_m2(
        mesh - torch.tensor([0.0, 0.0, float(mesh[..., 2].min())], device=mesh.device),
        sole_band, 0.0)[0].sum()) for mesh in foot_meshes]
    joint_names = list(robot.joint_names)
    leg_joint_ids = {}
    for joint in ("hip", "hfe", "foot"):
        leg_joint_ids[joint] = {name.split("_")[0]: joint_names.index(f"{name.split('_')[0]}_{joint}_joint")
                                for name in foot_bodies}
    # Position limits, because "the target asks for the sole below the floor" has two very different
    # readings: a pose the policy chose, or a target pressed against a stop it cannot pass.
    pos_limits = robot.data.joint_pos_limits.torch[0]  # (J, 2); the same for every env
    # The zero pose the action offset is taken from (``use_default_offset``): the reference that turns
    # "how far the policy commands this joint from its resting angle" into a number instead of a pose.
    default_pos = robot.data.default_joint_pos.torch[0]  # (J,); the same for every env
    # The effort limit each group's drive is clipped at. With position PD a target error is a torque, so
    # this is the number every torque reading has to be compared against -- and it is per group, because
    # the blade's cap (70 N*m) is not the leg's (180). Read from the instantiated actuator
    # (``effort_limit_sim``, which the implicit cfg mirrors ``effort_limit`` into) rather than copied
    # from the yaml. Gains are NOT read here: they come from the sim data below, because that is where
    # gain randomization lands (``parkour_mdp._pd_torque`` does the same).
    def group_effort(group: str) -> float:
        """The effort limit the solver was given for one actuator group [N*m]."""
        actuators = cfg.scene.robot.actuators if hasattr(cfg.scene.robot, "actuators") else {}
        actuator = actuators.get(group)
        return float(getattr(actuator, "effort_limit_sim", None)
                     or getattr(actuator, "effort_limit", 0.0) or 0.0)

    joint_effort = {"hip": group_effort("legs"), "hfe": group_effort("legs"),
                    "foot": group_effort("feet")}

    command = torch.tensor([[speed, 0.0, 0.0] for speed in speeds], device=live.device)
    command_term = live.command_manager.get_term("base_velocity")

    runner = OnPolicyRunner(wrapper, agent_cfg.to_dict(), log_dir=None, device=live.device)
    runner.load(args_cli.checkpoint)
    policy = runner.get_inference_policy(device=live.device)

    steps = round(args_cli.seconds / live.step_dt)
    obs = wrapper.get_observations()
    trace: dict[str, list[torch.Tensor]] = {key: [] for key in
                                            ("force", "clearance", "clearance_target", "contact",
                                             "fore_aft", "pred_linear", "pred_rotation", "done",
                                             "sole_contact", "sole_through", "sole_tilt", "sole_edge",
                                             "shank_up")}
    joint_trace: dict[str, list[torch.Tensor]] = {key: [] for key in ("target", "actual", "vel")}
    # One read of the sim-side gains, which are static per joint. They are the ones the torque
    # reconstruction needs (see the clipping reading in ``summarise``).
    gains: dict[str, torch.Tensor] = {}
    for step in range(steps):
        command_term.vel_command_b[:] = command
        with torch.no_grad():
            action = policy(obs)
            if args_cli.freeze_feet_action:
                action = action.clone()
                action[:, frozen_foot_columns] = 0.0
            obs, _, _, _ = wrapper.step(action)
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
        # Where the sole is relative to the floor plane, per foot: how much of it lies within
        # ``sole_band`` of the ground, and how much is under the ground. Computed from the mesh
        # triangles rotated by the live pose, so it needs no contact point and no new sensor. The
        # triangles of every (env, foot) are flattened into the one axis the clipping reader takes;
        # they are independent of each other, so this is only a loop over 48 shapes instead of 576.
        world_meshes = diag_metrics.mesh_triangles_w(pose, quat, robot_foot_ids, foot_meshes)
        shape = world_meshes.shape[:3]  # (envs, feet, triangles)
        on_floor, beneath = diag_metrics.ground_contact_area_m2(world_meshes.reshape(-1, 3, 3),
                                                               sole_band, sole_eps)
        trace["sole_contact"].append(on_floor.reshape(shape).sum(-1).clone())
        trace["sole_through"].append(beneath.reshape(shape).sum(-1).clone())
        # Which part of the pad is lowest, in the pad's own frame, and how far the sole is off level.
        # Without this pair the area reading cannot tell a foot rolled onto its edge from a foot whose
        # curved pad happens to touch with a small patch -- the two read the same area.
        down_in_link = diag_metrics.body_down_in_link(quat, robot_foot_ids)
        trace["sole_tilt"].append(torch.rad2deg(
            torch.acos((-down_in_link[..., 2]).clamp(-1.0, 1.0))).clone())
        trace["sole_edge"].append(down_in_link[..., :2].clone())
        # The world up vector in the SHANK's frame. Together with the pad's own normal (a constant in
        # the foot frame, measured at ~1.45 deg off -z) and the blade's angle, this is everything the
        # reading "is a level pad reachable at all" needs: the pad's tilt for any blade angle is the
        # angle between that angle's rotation of the pad normal and this vector. Stored per frame
        # because it is a pose, not a statistic -- its median describes no frame that occurred.
        trace["shank_up"].append(diag_metrics.body_down_in_link(quat, robot_shank_ids).neg().clone())
        joint_trace["target"].append(data.joint_pos_target.torch.clone())
        joint_trace["actual"].append(data.joint_pos.torch.clone())
        joint_trace["vel"].append(data.joint_vel.torch.clone())
        if step == 0:
            gains["kp"] = data.joint_stiffness.torch.clone()
            gains["kd"] = data.joint_damping.torch.clone()
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
    sole_contact = torch.stack(trace["sole_contact"])
    sole_through = torch.stack(trace["sole_through"])
    sole_tilt = torch.stack(trace["sole_tilt"])
    sole_edge = torch.stack(trace["sole_edge"])
    shank_up = torch.stack(trace["shank_up"])
    target = torch.stack(joint_trace["target"])
    actual = torch.stack(joint_trace["actual"])
    vel = torch.stack(joint_trace["vel"])

    # Identity, so a report cannot outlive the run that made it unnoticed: the checkpoint it was
    # taken from, by digest, and the command line it was taken with. A crashed run leaves no report
    # (the failure branch exits non-zero before writing), and this makes the surviving one traceable.
    report = {"task": args_cli.task, "speeds": speeds, "step_dt": live.step_dt, "steps": steps,
              "family": family,
              "mesh_dir": str(family_mesh_dir.relative_to(_REPO_ROOT)).replace("\\", "/"),
              "mesh_digests": {name: binding.sha256_file(family_mesh_dir / f"{name}_collision.obj")
                               for name in foot_bodies},
              "contact_n": args_cli.contact_n, "transition_frames": args_cli.transition_frames,
              "sole_band_m": sole_band, "sole_eps_m": sole_eps, "sole_area_m2": sole_areas,
              "sole_cap_m2": sole_caps,
              "checkpoint": str(args_cli.checkpoint),
              "checkpoint_sha256": binding.sha256_file(pathlib.Path(args_cli.checkpoint)),
              "feet_overrides": {name: value for name, value in feet_overrides.items()
                                 if value is not None},
              "frozen_foot_columns": (frozen_foot_columns if args_cli.freeze_feet_action else []),
              "argv": sys.argv, "foot_bodies": foot_bodies, "envs": []}
    for env_index, speed in enumerate(speeds):
        # "up to the first termination", written as a cummax: this is not the terrain split rule and
        # must not read like one -- `check_terrain_split_source` keys on the epsilon-plus-cumulative
        # shape as its renamed-copy fallback, and this mask tripped it (2026-09-23).
        alive = ~done[:, env_index].long().cummax(dim=0).values.bool()  # up to the first termination
        if not bool(alive.any()):
            alive = torch.ones_like(done[:, env_index])
        entry = {"speed": speed, "frames_alive": int(alive.sum()),
                 "done_frames": int(done[:, env_index].sum()), "feet": []}
        for foot, name in enumerate(foot_bodies):
            leg = name.split("_")[0]
            row = {"body": name, "force": force[alive, env_index, foot],
                   "sole_clearance_m": clearance[alive, env_index, foot],
                   "sole_clearance_target_m": clearance_target[alive, env_index, foot],
                   "sole_contact_area_m2": sole_contact[alive, env_index, foot],
                   "sole_through_area_m2": sole_through[alive, env_index, foot],
                   "sole_area_m2": sole_areas[foot], "sole_cap_m2": sole_caps[foot],
                   "sole_tilt_deg": sole_tilt[alive, env_index, foot],
                   "sole_low_edge_xy": sole_edge[alive, env_index, foot],
                   "pred_linear_m": pred_linear[alive, env_index, foot],
                   "pred_rotation_m": pred_rotation[alive, env_index, foot],
                   "contact_speed_horiz_mps": contact[alive, env_index, foot],
                   "foot_fore_aft_m": fore_aft[alive, env_index, foot]}
            for joint in ("hip", "hfe", "foot"):
                column = leg_joint_ids[joint][leg]
                row[f"joint_target_{joint}"] = target[alive, env_index, column]
                row[f"joint_actual_{joint}"] = actual[alive, env_index, column]
                row[f"joint_vel_{joint}"] = vel[alive, env_index, column]
                row[f"joint_limits_{joint}"] = tuple(pos_limits[column].tolist())
                row[f"joint_default_{joint}"] = float(default_pos[column])
                row[f"joint_kp_sim_{joint}"] = float(gains["kp"][env_index, column])
                row[f"joint_kd_sim_{joint}"] = float(gains["kd"][env_index, column])
                row[f"joint_effort_limit_{joint}"] = joint_effort[joint]
            entry["feet"].append(summarise(row, args_cli.contact_n, args_cli.transition_frames,
                                           live.step_dt))
        entry["series"] = {key: [[round(float(x), 5) for x in values[alive, env_index, foot].tolist()]
                                 for foot in range(len(foot_bodies))]
                           for key, values in (("force", force), ("clearance", clearance),
                                               ("contact", contact), ("fore_aft", fore_aft),
                                               ("clearance_target", clearance_target),
                                               ("sole_contact", sole_contact),
                                               ("sole_through", sole_through),
                                               ("sole_tilt", sole_tilt),
                                               ("shank_up_x", shank_up[..., 0]),
                                               ("shank_up_y", shank_up[..., 1]),
                                               ("shank_up_z", shank_up[..., 2]))}
        # Per-frame joint targets, actual positions and velocities, per leg. A summary can say one leg
        # behaves differently; only the series says whether it is the same phase done differently or a
        # different phase altogether, which is the comparison the left front leg still needs. The
        # velocities are here so the torque and effort-limit readings in the summary can be recomputed
        # from the report without another rollout.
        entry["joint_series"] = {
            f"{name}_{joint}_{kind}": [round(float(x), 5) for x in values[
                alive, env_index, leg_joint_ids[joint][name.split("_")[0]]].tolist()]
            for name in foot_bodies for joint in ("hip", "hfe", "foot")
            for kind, values in (("target", target), ("actual", actual), ("vel", vel))}
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
