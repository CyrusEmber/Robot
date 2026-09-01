# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Offline unit test for the v3 curriculum/geometry pieces (no sim, plain torch).

Checks: the c_k schedule math (direction, warm-up length, no-params fallback),
the DR range anchoring, the tilt termination predicate, and the foot-ring
pattern geometry (52 points, per-ring counts and radii).
"""

import math
from types import SimpleNamespace

import torch

from rl_exp.tasks.teacher_env_cfg import RingPatternCfg, ring_pattern
from rl_exp.tasks.teacher_mdp import _ck_scale_range, ck_value, init_ck, tilt_terminate


class _MockEnv:
    def __init__(self, common_step_counter: int = 0):
        self.common_step_counter = common_step_counter


def test_ck_schedule_direction() -> None:
    env = _MockEnv()
    init_ck(env, None, c0=0.2, decay=0.98, steps_per_iteration=24)
    values = []
    for step in range(0, 24 * 200, 24):
        env.common_step_counter = step
        values.append(ck_value(env))
    assert abs(values[0] - 0.2) < 1e-9, f"c_0 should be 0.2, got {values[0]}"
    assert all(b > a for a, b in zip(values, values[1:])), "c_k must be monotone increasing"
    # half-life in log-distance is ~34 iters; ~140 iters to reach 0.9 (plan D3)
    assert values[140] > 0.9, f"c_k at iter 140 should exceed 0.9, got {values[140]}"
    assert values[-1] > 0.95, "c_k should keep converging toward 1.0"


def test_ck_no_params_fallback() -> None:
    assert ck_value(_MockEnv()) == 1.0


def test_ck_scale_range_anchors() -> None:
    # scale operation: pulled toward 1.0
    assert _ck_scale_range((0.9, 1.1), 0.0, 1.0) == (1.0, 1.0)
    lo, hi = _ck_scale_range((0.9, 1.1), 0.5, 1.0)
    assert math.isclose(lo, 0.95) and math.isclose(hi, 1.05)
    # additive operation: pulled toward 0.0
    assert _ck_scale_range((0.0, 0.01), 0.2, 0.0) == (0.0, 0.002)
    # full curriculum returns the original range
    assert _ck_scale_range((0.9, 1.1), 1.0, 1.0) == (0.9, 1.1)


def test_tilt_terminate_predicate() -> None:
    def env_with(gz: torch.Tensor):
        return SimpleNamespace(scene={"robot": SimpleNamespace(data=SimpleNamespace(projected_gravity_b=gz))})

    upright = torch.tensor([[-0.999, 0.0, -1.0]])
    fallen = torch.tensor([[0.0, 0.0, -0.2]])
    assert not tilt_terminate(env_with(upright), gravity_z_limit=-0.6).any()
    assert tilt_terminate(env_with(fallen), gravity_z_limit=-0.6).all()


def test_ring_pattern_geometry() -> None:
    cfg = RingPatternCfg()
    starts, dirs = ring_pattern(cfg, "cpu")
    counts, radii = cfg.ring_counts, cfg.ring_radii
    assert starts.shape == (52, 3), f"expected 52 rays, got {starts.shape}"
    assert dirs.shape == (52, 3)
    assert torch.allclose(dirs, torch.zeros_like(dirs) + torch.tensor([0.0, 0.0, -1.0]))
    cursor = 0
    for count, radius in zip(counts, radii):
        ring = starts[cursor : cursor + count]
        assert torch.allclose(ring[:, 2], torch.zeros(count)), "ring must be horizontal"
        radii_actual = torch.linalg.norm(ring[:, :2], dim=-1)
        assert torch.allclose(radii_actual, torch.full((count,), radius), atol=1e-6), (
            f"ring radius mismatch at r={radius}"
        )
        # even angular spacing
        angles = torch.atan2(ring[:, 1], ring[:, 0])
        angles = angles.sort().values
        gaps = torch.diff(angles)
        assert torch.allclose(gaps, gaps[0].expand_as(gaps), atol=1e-5), "uneven ring spacing"
        cursor += count
    assert cursor == 52


def main() -> int:
    tests = [
        test_ck_schedule_direction,
        test_ck_no_params_fallback,
        test_ck_scale_range_anchors,
        test_tilt_terminate_predicate,
        test_ring_pattern_geometry,
    ]
    for t in tests:
        t()
        print(f"  ok {t.__name__}")
    print("ALL_V3_CURRICULUM_TESTS_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
