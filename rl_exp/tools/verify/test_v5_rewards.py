# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Offline unit test for the v5 anti-collapse reward terms (no sim, plain torch).

Checks the EP-style linear tracking kernel (standstill 0 / reversal negative /
tracking 1 / overspeed capped / min_speed clamp), the c_k-scaled foot-slide and
undesired-contact penalties, and the continuous belly-contact force penalty.
"""

import sys
from types import SimpleNamespace

import torch

from rl_exp.tasks.teacher_mdp import (
    belly_contact_force,
    feet_slide_ck,
    init_ck,
    track_lin_vel_xy_lin,
    undesired_contacts_ck,
)

_IDENTITY_QUAT = torch.tensor([[1.0, 0.0, 0.0, 0.0]])


def _env_with_lin(vel_w: torch.Tensor, cmd: torch.Tensor):
    """Env mock for track_lin_vel_xy_lin: identity orientation, world=body frame."""
    asset = SimpleNamespace(
        data=SimpleNamespace(
            root_quat_w=SimpleNamespace(torch=_IDENTITY_QUAT.expand(vel_w.shape[0], 4)),
            root_lin_vel_w=SimpleNamespace(torch=torch.nn.functional.pad(vel_w, (0, 1))),
        )
    )
    return SimpleNamespace(
        scene={"robot": asset},
        command_manager=SimpleNamespace(get_command=lambda name: cmd),
    )


def test_track_lin_vel_lin_kernel() -> None:
    # per-row: (cmd, vel, expected)
    cases = [
        ((1.0, 0.0), (0.0, 0.0), 0.0),      # standstill scores exactly 0
        ((1.0, 0.0), (1.0, 0.0), 1.0),      # perfect tracking
        ((1.0, 0.0), (-1.0, 0.0), -1.0),    # reversal is negative
        ((1.0, 0.0), (3.0, 0.0), 1.0),      # overspeed capped at 1
        ((1.0, 0.0), (0.0, 1.0), 0.0),      # sideways motion does not count
        ((0.0, 0.5), (0.0, 0.5), 1.0),      # lateral command tracks normally
        ((2.0, 0.0), (1.0, 0.0), 0.5),      # half the commanded speed
        ((0.05, 0.0), (0.05, 0.0), 0.25),   # below min_speed: needs v >= 0.1 for full
    ]
    cmd = torch.tensor([c[0] for c in cases])
    vel = torch.tensor([c[1] for c in cases])
    expected = torch.tensor([c[2] for c in cases])
    env = _env_with_lin(vel, torch.nn.functional.pad(cmd, (0, 1)))
    out = track_lin_vel_xy_lin(env, "base_velocity", SimpleNamespace(name="robot"), min_speed=0.1)
    assert out.shape == (len(cases),)
    assert torch.allclose(out, expected, atol=1e-6), f"{out.tolist()} != {expected.tolist()}"


class _Scene:
    """Minimal scene mock: dict-style access + sensors mapping."""

    def __init__(self, entries: dict):
        self.sensors = {k: v for k, v in entries.items() if k.startswith("contact")}
        self._entries = entries

    def __getitem__(self, key):
        return self._entries[key]


def _env_with_feet(forces_hist: torch.Tensor, body_vel: torch.Tensor):
    """Env mock for feet_slide_ck: forces (N,H,B,3), velocities (N,B,3)."""
    sensor = SimpleNamespace(
        data=SimpleNamespace(net_forces_w_history=SimpleNamespace(torch=forces_hist))
    )
    asset = SimpleNamespace(
        data=SimpleNamespace(body_lin_vel_w=SimpleNamespace(torch=body_vel)),
        body_ids=[0, 1],
    )
    env = SimpleNamespace(
        scene=_Scene({"contact_forces": sensor, "robot": asset}),
        common_step_counter=0,
    )
    init_ck(env, None, c0=0.5, decay=1.0, steps_per_iteration=24)  # frozen c_k = 0.5
    return env


def test_feet_slide_ck() -> None:
    # 1 env, 2 feet, 1 history step: foot 0 in contact (200 N) sliding at
    # 0.3 m/s, foot 1 airborne (0 N) flying at 1.0 m/s -> only foot 0 counts
    forces = torch.tensor([[[[0.0, 0.0, 200.0], [0.0, 0.0, 0.0]]]])
    vel = torch.tensor([[[0.3, 0.0, 0.0], [1.0, 0.0, 0.0]]])
    env = _env_with_feet(forces, vel)
    sensor_cfg = SimpleNamespace(name="contact_forces", body_ids=[0, 1])
    asset_cfg = SimpleNamespace(name="robot", body_ids=[0, 1])
    out = feet_slide_ck(env, sensor_cfg, asset_cfg)
    assert out.shape == (1,)
    # unscaled value 0.3; c_k = 0.5 -> 0.15
    assert torch.allclose(out, torch.tensor([0.15]), atol=1e-6), f"got {out}"
    # zero contact forces -> no penalty regardless of speed
    env_zero = _env_with_feet(torch.zeros_like(forces), vel)
    assert torch.allclose(feet_slide_ck(env_zero, sensor_cfg, asset_cfg), torch.zeros(1))


def _env_with_belly(forces: torch.Tensor, step: int = 0):
    sensor = SimpleNamespace(data=SimpleNamespace(net_forces_w=SimpleNamespace(torch=forces)))
    env = SimpleNamespace(
        scene=_Scene({"contact_forces": sensor}),
        common_step_counter=step,
    )
    init_ck(env, None, c0=0.2, decay=0.98, steps_per_iteration=24)
    return env


def test_belly_contact_force() -> None:
    sensor_cfg = SimpleNamespace(name="contact_forces", body_ids=[0])
    # normal stance: no base contact -> 0
    env = _env_with_belly(torch.tensor([[[0.0, 0.0, 0.0]]]))
    assert torch.allclose(belly_contact_force(env, sensor_cfg, 706.0), torch.zeros(1))
    # flat belly carries the full body weight -> ~1.0
    env = _env_with_belly(torch.tensor([[[0.0, 0.0, 706.0]]]))
    assert torch.allclose(belly_contact_force(env, sensor_cfg, 706.0), torch.ones(1), atol=1e-4)
    # NOT c_k-scaled: at iteration 0 (c_k = 0.2) the penalty is the same
    env2 = _env_with_belly(torch.tensor([[[0.0, 0.0, 706.0]]]), step=0)
    v_early = belly_contact_force(env2, sensor_cfg, 706.0)
    env3 = _env_with_belly(torch.tensor([[[0.0, 0.0, 706.0]]]), step=24 * 500)
    v_late = belly_contact_force(env3, sensor_cfg, 706.0)
    assert torch.allclose(v_early, v_late), "belly penalty must not anneal with c_k"


def _env_with_contacts(forces_hist: torch.Tensor, step: int = 0):
    sensor = SimpleNamespace(
        data=SimpleNamespace(net_forces_w_history=SimpleNamespace(torch=forces_hist))
    )
    env = SimpleNamespace(
        scene=_Scene({"contact_forces": sensor}),
        common_step_counter=step,
    )
    init_ck(env, None, c0=0.5, decay=1.0, steps_per_iteration=24)
    return env


def test_undesired_contacts_ck() -> None:
    sensor_cfg = SimpleNamespace(name="contact_forces", body_ids=[0])
    # 2 N on the body: above the 1 N threshold -> raw penalty 1, c_k = 0.5
    # forces shape (N, history, bodies, 3) -- the stock term reads the
    # history buffer and maxes over it
    env = _env_with_contacts(torch.tensor([[[[0.0, 0.0, 2.0]]]]))
    out = undesired_contacts_ck(env, 1.0, sensor_cfg)
    assert torch.allclose(out, torch.tensor([0.5]), atol=1e-6), f"got {out}"
    # sub-threshold force -> no penalty
    env_low = _env_with_contacts(torch.tensor([[[[0.0, 0.0, 0.5]]]]))
    assert torch.allclose(undesired_contacts_ck(env_low, 1.0, sensor_cfg), torch.zeros(1))


def main() -> int:
    tests = [
        test_track_lin_vel_lin_kernel,
        test_feet_slide_ck,
        test_belly_contact_force,
        test_undesired_contacts_ck,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {test.__name__}: {exc}")
    if failed:
        print(f"V5_REWARDS_TEST_FAILED ({failed})")
        return 1
    print("V5_REWARDS_TEST_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
