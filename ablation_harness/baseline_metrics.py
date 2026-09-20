# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Fixed-window baseline scoring; terminal frames count, respawned episodes never do."""

import torch


class BaselineWindow:
    """Accumulate one first episode per env over a fixed window, using SI units."""

    def __init__(self, start_pos: torch.Tensor, start_yaw: torch.Tensor, *, steps: int, protocol: dict):
        if steps < 1:
            raise ValueError("window needs at least one step")
        self.steps = steps
        self.protocol = protocol
        self.start_pos = start_pos.clone()
        self.start_yaw = start_yaw.clone()
        self.end_pos = start_pos.clone()
        self.alive = torch.ones_like(start_yaw, dtype=torch.bool)
        self.survived = torch.zeros_like(self.alive)
        self.error = torch.zeros_like(start_yaw)
        self.lateral = torch.zeros_like(start_yaw)
        self.yaw = torch.zeros_like(start_yaw)
        self.load = torch.zeros_like(start_yaw)
        self.valid_steps = torch.zeros_like(start_yaw)
        self.count = 0

    def add(self, *, pos: torch.Tensor, yaw: torch.Tensor, velocity_yaw: torch.Tensor,
            terminated: torch.Tensor, timeout: torch.Tensor, head_tail_force: torch.Tensor) -> None:
        """Consume a post-physics, pre-reset frame [m, rad, m/s, N].

        After the first end, forward velocity is imputed as zero for the remaining
        window. Diagnostics cover only the first episode and report their coverage.
        A simultaneous failure and timeout is a failure, including on the final step.
        """
        if self.count >= self.steps:
            raise ValueError("window already complete")
        speed = float(self.protocol["command_mps_radps"][0])
        self.error += torch.where(self.alive, (velocity_yaw[:, 0] - speed).abs(), abs(speed))
        self.end_pos[self.alive] = pos[self.alive]
        delta_yaw = torch.atan2(torch.sin(yaw - self.start_yaw), torch.cos(yaw - self.start_yaw)).abs()
        self.lateral += torch.where(self.alive, velocity_yaw[:, 1].abs(), 0.0)
        self.yaw += torch.where(self.alive, delta_yaw, 0.0)
        self.load += torch.where(self.alive, head_tail_force, 0.0)
        self.valid_steps += self.alive
        self.survived |= self.alive & timeout & ~terminated & (self.count == self.steps - 1)
        self.alive &= ~(terminated | timeout)
        self.count += 1

    def result(self) -> dict:
        """Return aggregate gates plus per-env evidence; refuse a partial window."""
        if self.count != self.steps:
            raise ValueError(f"incomplete window: {self.count}/{self.steps}")
        delta = self.end_pos - self.start_pos
        distance = delta[:, 0] * self.start_yaw.cos() + delta[:, 1] * self.start_yaw.sin()
        mae = self.error / self.steps
        coverage = self.valid_steps.clamp_min(1)
        measured = {
            "forward_mae_mps": mae.mean().item(),
            "forward_displacement_m": distance.mean().item(),
            "first_episode_timeout_fraction": self.survived.float().mean().item(),
        }
        gates = self.protocol["gates"]
        passed = {
            "tracking": measured["forward_mae_mps"] < gates["forward_mae_mps_lt"],
            "displacement": measured["forward_displacement_m"] > gates["forward_displacement_m_gt"],
            "survival": measured["first_episode_timeout_fraction"] > gates["first_episode_timeout_fraction_gt"],
        }
        return {
            "verdict": "pass" if all(passed.values()) else "fail",
            "metrics": measured, "gates": passed,
            "diagnostics": {
                "lateral_speed_abs_mps": (self.lateral / coverage).mean().item(),
                "yaw_offset_abs_rad": (self.yaw / coverage).mean().item(),
                "head_tail_contact_force_n": (self.load / coverage).mean().item(),
                "first_episode_frame_fraction": (self.valid_steps / self.steps).mean().item(),
            },
            "per_env": {"forward_mae_mps": mae.tolist(), "forward_displacement_m": distance.tolist(),
                        "survived": self.survived.tolist(), "valid_steps": self.valid_steps.tolist()},
        }
