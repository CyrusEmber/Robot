# -*- coding: utf-8 -*-
"""Offline gate for the acceptance-side velocity metrics (no sim).

Covers the two frame/cancellation bugs fixed on 2026-09-14:

1. **Frame mismatch** -- the reward kernel ``teacher_mdp.miki_tracking_kernel``
   scores the error in the yaw-aligned gravity frame
   (``quat_apply_inverse(yaw_quat(q), v_w)``), but the P2 acceptance gates read
   ``root_lin_vel_b`` (body frame), where pitch/roll fold gravity into the
   forward axis and a correctly moving pitched base reads as underspeed. The
   gate below asserts the yaw-frame contract and shows the body-frame reading
   would fail the 0.15 gate on a perfect run (regression evidence).
2. **Sign cancellation** -- the P2 sideslip gate was ``mean(vel_yaw_y)``, which
   cancels a left/right alternating sideslip to ~0. The gate below shows the
   old rule passing that series while the corrected ``mean|vel_yaw_y|`` fails.

Regression discipline: the two ``_legacy_*`` helpers reproduce the old
implementations so the tests fail against them by construction.
"""

import math
import pathlib
import sys

import torch

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "rl_exp" / "tools" / "diagnose"))

import diag_metrics  # noqa: E402
from isaaclab.utils.math import quat_apply_inverse, quat_from_euler_xyz  # noqa: E402
from rl_exp.tasks.teacher_mdp import miki_tracking_kernel  # noqa: E402

SIGMA_SQ = 0.25
ATOL = 1e-5


def _yaw_frame(q_wxyz: torch.Tensor, v_w: torch.Tensor) -> torch.Tensor:
    """diag_metrics.yaw_frame_lin_vel with the torch (w, x, y, z) quat convention."""
    return diag_metrics.yaw_frame_lin_vel(q_wxyz, v_w)


def _legacy_body_frame(q_wxyz: torch.Tensor, v_w: torch.Tensor) -> torch.Tensor:
    """The pre-fix acceptance reading: root_lin_vel_b, pitch/roll included."""
    return quat_apply_inverse(q_wxyz, v_w)[:, :2]


def _legacy_signed_sideslip(vel_yaw_y: torch.Tensor) -> float:
    """The pre-fix sideslip gate: signed mean (cancels left/right alternation)."""
    return round(vel_yaw_y.mean().item(), 3)


def test_kernel_rewards_tracking_and_penalizes_all_errors() -> None:
    """Perfect tracking scores the ceiling; overspeed, underspeed and sideslip all lose credit."""
    cmd = torch.tensor([[0.5, 0.0]])
    assert miki_tracking_kernel(cmd, cmd, SIGMA_SQ).item() == 1.0, "perfect tracking must score 1.0"

    overspeed = miki_tracking_kernel(cmd, torch.tensor([[0.75, 0.0]]), SIGMA_SQ).item()
    underspeed = miki_tracking_kernel(cmd, torch.tensor([[0.25, 0.0]]), SIGMA_SQ).item()
    sideslip = miki_tracking_kernel(cmd, torch.tensor([[0.5, 0.2]]), SIGMA_SQ).item()
    for name, value in (("overspeed", overspeed), ("underspeed", underspeed), ("sideslip", sideslip)):
        assert value < 1.0, f"{name} must lose credit vs perfect tracking"
    assert abs(overspeed - underspeed) < ATOL, "the kernel is symmetric (no overspeed bias)"

    # stop objective: a stationary base at a zero command keeps the ceiling
    stop_cmd = torch.tensor([[0.0, 0.0]])
    assert miki_tracking_kernel(stop_cmd, stop_cmd, SIGMA_SQ).item() == 1.0

    # the v10 EP kernel left exactly the overspeed hole: credit saturates, growth is free
    legacy_overspeed = min(0.75 / 0.5, 1.0)
    assert legacy_overspeed == 1.0 > overspeed, "regression: the EP clamp scored overspeed full credit"


def test_same_relative_motion_scores_the_same_after_yaw_changes() -> None:
    """Reward depends on the relative motion only: rotate both command and velocity with yaw."""
    body_speed = 0.5
    for yaw_deg in (0.0, 45.0, 90.0, 180.0, 270.0, -135.0):
        yaw = math.radians(yaw_deg)
        q = quat_from_euler_xyz(torch.zeros(1), torch.zeros(1), torch.tensor([yaw]))
        # the base travels along its own heading at 0.5 m/s -> yaw frame (0.5, 0)
        v_w = torch.tensor([[body_speed * math.cos(yaw), body_speed * math.sin(yaw), 0.0]])
        vel_yaw = _yaw_frame(q, v_w)
        assert torch.allclose(vel_yaw, torch.tensor([[body_speed, 0.0]]), atol=ATOL), \
            f"yaw {yaw_deg} deg: yaw-frame velocity must be heading-invariant"
        cmd = torch.tensor([[body_speed, 0.0]])
        assert miki_tracking_kernel(cmd, vel_yaw, SIGMA_SQ).item() == 1.0, \
            f"yaw {yaw_deg} deg: same relative motion must score the same reward"


def test_pitch_does_not_read_as_underspeed() -> None:
    """A pitched base moving correctly keeps full credit in the yaw frame (body frame does not)."""
    cmd_speed = 0.5
    yaw = math.radians(17.0)  # non-zero heading: the velocity must follow it, not world +x
    v_w = torch.tensor([[cmd_speed * math.cos(yaw), cmd_speed * math.sin(yaw), 0.0]])
    cmd = torch.tensor([[cmd_speed, 0.0]])
    legacy_fracs: list[float] = []
    for pitch_deg in (0.0, 20.0, 30.0, 45.0):
        pitch = math.radians(pitch_deg)
        q = quat_from_euler_xyz(torch.tensor([0.0]), torch.tensor([pitch]), torch.tensor([yaw]))
        vel_yaw = _yaw_frame(q, v_w)
        assert torch.allclose(vel_yaw, cmd, atol=ATOL), \
            f"pitch {pitch_deg} deg must not change the yaw-frame forward speed"
        assert miki_tracking_kernel(cmd, vel_yaw, SIGMA_SQ).item() == 1.0, \
            f"pitch {pitch_deg} deg: the reward must stay at the ceiling"
        # regression evidence: the body-frame acceptance reading drifts with pitch
        legacy_fracs.append(
            diag_metrics.forward_error(cmd_speed, _legacy_body_frame(q, v_w)[:, 0])["mean_abs_frac"]
        )
    # a systematic underspeed bias that grows with pitch (0 / 0.06 / 0.134 / 0.293 at
    # 0 / 20 / 30 / 45 deg) -- at 45 deg the body frame would fail the 0.15 acceptance gate
    assert legacy_fracs == sorted(legacy_fracs), f"body-frame bias must grow with pitch: {legacy_fracs}"
    assert legacy_fracs[-1] > 0.15, \
        f"body frame would falsely fail the 0.15 gate at 45 deg: {legacy_fracs}"


def test_alternating_sideslip_cannot_pass_acceptance() -> None:
    """Left/right alternating sideslip: the signed gate passes it, the abs gate must not."""
    vel_yaw_y = torch.tensor([0.1, -0.1] * 50, dtype=torch.float32)
    limit = 0.05
    assert abs(_legacy_signed_sideslip(vel_yaw_y)) < limit, \
        "regression: the signed mean hides a +/-0.1 m/s sideslip alternation"
    assert diag_metrics.sideslip_abs_mean(vel_yaw_y) > limit, \
        "the abs gate must reject an alternating sideslip"
    # a genuine one-sided sideslip is caught by both -- the fix only adds coverage
    one_sided = torch.full((100,), 0.1)
    assert diag_metrics.sideslip_abs_mean(one_sided) > limit, "one-sided sideslip > limit (abs gate)"
    assert abs(_legacy_signed_sideslip(one_sided)) > limit, "one-sided sideslip > limit (signed gate)"


def test_alternating_forward_speed_is_exposed_by_mae() -> None:
    """Fast/slow alternation keeps the mean but shows up in the per-frame MAE."""
    cmd_speed = 0.5
    fwd = torch.tensor([0.35, 0.65] * 50, dtype=torch.float32)
    err = diag_metrics.forward_error(cmd_speed, fwd)
    assert abs(err["mean_abs_frac"]) < 0.15, "the mean hides the alternation (0.5 == 0.5)"
    assert err["mae_mps"] > 0.1, "the per-frame MAE must expose it"
    # a never-moving robot fails the corrected abs gate even though it also scores -1 signed
    stalled = diag_metrics.forward_error(cmd_speed, torch.zeros(100))
    assert stalled["mean_signed_frac"] == -1.0 and stalled["mean_abs_frac"] == 1.0
    assert abs(stalled["mean_signed_frac"]) >= 0.15, "sanity: |0 - 1| = 1 fails the gate too"


def _main() -> None:
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for fn in tests:
        fn()
        print(f"[OK] {fn.__name__}")
    print(f"test_acceptance_metrics: {len(tests)} passed")


if __name__ == "__main__":
    _main()
