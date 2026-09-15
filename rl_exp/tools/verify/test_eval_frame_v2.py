# -*- coding: utf-8 -*-
"""Regression gate for the Locomotion-Eval-v2 frame contract (no sim).

v1 sampled the pre-step state, so an episode whose bad attitude run ended on the
frame it terminated on only ever showed ``sustain_steps - 1`` bad frames -- the
auto-reset inside ``step()`` had already overwritten the last one -- and read as
no-fall. v2 samples the post-physics pre-reset state with the terminal frame
captured, so the same episode's window closes.

This gate encodes both readings on the pure metric layer (``metrics.fall_flags``
+ the valid mask), which is where the frame contract lands. The capture itself
(hooking the env reset) is runtime-only and is reported by the
``terminal frames captured=`` line every eval run prints: it must equal the
number of early-ended episodes, else the private hook went stale.

Usage: python rl_exp\\tools\\verify\\test_eval_frame_v2.py
"""
import pathlib
import sys

import torch

_REPO = pathlib.Path(__file__).absolute().parents[3]
sys.path.insert(0, str(_REPO / "ablation_harness"))
from metrics import fall_flags  # noqa: E402

STEPS, SUSTAIN = 120, 25
TILT_COS_MIN = 0.766044443118978  # cos(40 deg) = the protocol's tilt threshold


def _case(bad_start: int, bad_len: int, first_done: int):
    """(tilt_cos, valid) for one env: bad run of ``bad_len`` frames from ``bad_start``.

    ``tilt_cos = -projected_gravity_b.z``: upright = +1, a 60 deg tilt = cos(60) = 0.5.
    """
    tilt = torch.full((STEPS, 1), 1.0)  # upright
    tilt[bad_start:bad_start + bad_len] = 0.5  # 60 deg, past the 40 deg threshold
    valid = torch.arange(STEPS).unsqueeze(1) <= first_done
    return tilt, valid


def _fall(tilt: torch.Tensor, valid: torch.Tensor) -> bool:
    return bool(fall_flags(tilt, None, TILT_COS_MIN, None, SUSTAIN, valid)[0])


def main():
    # 1) bad run 36..60, episode ends on 60: 25 bad frames, terminal one included
    tilt, valid = _case(36, SUSTAIN, first_done=60)
    assert _fall(tilt, valid), "v2 (terminal frame present): 25-frame window must register"
    # the v1 reading of the same episode: the terminal frame was lost, so the
    # mask stops one row earlier and only 24 bad frames remain
    v1_valid = valid & (torch.arange(STEPS).unsqueeze(1) <= 59)
    assert not _fall(tilt, v1_valid), "v1 truncation (24 frames) must read as no-fall"
    print("  ok terminal frame closes the window (its v1 truncation does not)")

    # 2) one frame short stays short: the fix must not turn any near-miss into a fall
    tilt, valid = _case(36, SUSTAIN - 1, first_done=60)
    assert not _fall(tilt, valid), "24 bad frames must not register as fall"
    print("  ok one frame short is still no fall")

    # 3) same window at the very tail of the series (no termination involved)
    tilt, valid = _case(STEPS - SUSTAIN, SUSTAIN, first_done=STEPS - 1)
    assert _fall(tilt, valid), "window ending on the final row must register"
    print("  ok window ending on the final row")

    # 4) an upright episode still reads clean (mask not inverted by any of the above)
    tilt, valid = _case(0, 0, first_done=STEPS - 1)
    assert not _fall(tilt, valid), "upright episode must not register as fall"
    print("  ok upright episode stays clean")

    print("ALL_EVAL_FRAME_V2_TESTS_PASSED")


if __name__ == "__main__":
    main()
