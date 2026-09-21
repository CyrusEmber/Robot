# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Baseline's own reward contracts; no dependency on the teacher implementation."""

import math
import pathlib
import sys
from types import SimpleNamespace as NS

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
import torch
from rl_exp.tasks import baseline_mdp as mdp


def test_tracking_kernel():
    cmd = torch.tensor([[0.5, 0.0]])
    assert mdp.miki_tracking_kernel(cmd, cmd).item() == 1
    stopped = mdp.miki_tracking_kernel(cmd, torch.zeros_like(cmd)).item()
    assert abs(stopped - math.exp(-1)) < 1e-6
    for velocity in ([0.75, 0], [0.25, 0], [0.5, 0.25]):
        assert abs(mdp.miki_tracking_kernel(cmd, torch.tensor([velocity])).item() - math.exp(-0.25)) < 1e-6


def test_tracking_wrapper_yaw_and_pitch():
    # Pitch must not turn horizontal travel into an apparent forward speed error.
    from isaaclab.utils.math import quat_from_euler_xyz
    yaw = torch.tensor([0.0, math.pi / 2, math.pi])
    q = quat_from_euler_xyz(torch.zeros(3), torch.full((3,), 0.6), yaw)
    velocity = torch.stack((0.5 * yaw.cos(), 0.5 * yaw.sin(), torch.zeros(3)), dim=-1)
    data = NS(root_quat_w=NS(torch=q), root_lin_vel_w=NS(torch=velocity))
    env = NS(scene={"robot": NS(data=data)},
             command_manager=NS(get_command=lambda name: torch.tensor([[0.5, 0, 0.0]]).expand(3, -1)))
    assert torch.allclose(mdp.track_lin_vel_xy_miki(env, "base_velocity"), torch.ones(3))


def test_belly_uses_sensor_ids_and_force_scale():
    forces = torch.tensor([[[999.0, 0, 0], [3.0, 4, 0], [0.0, 0, 7]]])
    env = NS(scene=NS(sensors={"contact": NS(data=NS(net_forces_w=NS(torch=forces)))}))
    cfg = NS(name="contact", body_ids=[1, 2])
    assert mdp.belly_contact_force(env, cfg, 6.0).item() == 2.0


def test_contact_load_dwell_term():
    """Touching the ground is the end of the episode, and only the guarded bodies count."""
    forces = torch.zeros(1, 3, 3)
    stub = NS(
        step_dt=0.02, num_envs=1, device=torch.device("cpu"),
        scene={"contact_forces": NS(data=NS(net_forces_w=NS(torch=forces)))},
    )
    cfg = NS(params={"sensor_cfg": NS(name="contact_forces", body_ids=[1])})
    term = mdp.ContactLoadDwellTerm(cfg, stub)
    load = dict(sensor_cfg=cfg.params["sensor_cfg"], load_n=1.0, dwell_s=0.0)

    def force(newtons: float) -> None:
        forces.zero_()
        forces[:, 1, 2] = newtons

    force(0.5)
    assert not term(env=stub, **load).item(), "below the contact threshold is not a press"
    force(87.2)  # the load v1's neck actually carried
    assert term(env=stub, **load).item(), "one frame of pressing ends the episode"
    term.reset(torch.tensor([0]))
    force(87.2)
    assert term(env=stub, **load).item(), "reset must clear the counter, not the criterion"

    forces.zero_()
    forces[:, 0, 2] = 500.0  # a body the guard does not name
    assert not any(term(env=stub, **load).item() for _ in range(5))
    forces[:, 1, 0] = 500.0  # a lateral self-contact on a guarded body is not a floor press
    assert not term(env=stub, **load).item()

    held = dict(load, dwell_s=0.5)
    forces.zero_()
    force(87.2)
    fired = [term(env=stub, **held).item() for _ in range(int(round(0.5 / 0.02)))]
    assert not any(fired[:-1]), "a dwell window must not fire before it elapses"
    assert fired[-1], "a dwell window must fire once it elapses"


def main():
    for name, test in sorted(globals().copy().items()):
        if name.startswith("test_"):
            test()
    print("BASELINE_MDP_OK")


if __name__ == "__main__":
    main()
