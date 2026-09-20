# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Fixed-window baseline scoring; terminal frames count, respawned episodes never do."""

import torch


class BaselineWindow:
    """Accumulate one first episode per env over a fixed window, using SI units.

    v1 read forward speed and survival only, and a policy that dragged its head along the
    floor passed all three gates. The protocol therefore also names the quantities that
    separate "walking" from "getting there somehow" -- tilt, non-foot carriers, collision
    meshes through the floor -- measured with the same functions the pre-train probe uses
    (``rl_exp.tools.diagnose.diag_metrics``), so a standard set before training is
    re-measured at acceptance rather than replaced by a weaker one.

    A gate whose quantity was never supplied is refused, not passed: unmeasured is unknown,
    and unknown is not a pass.
    """

    def __init__(self, start_pos: torch.Tensor, start_yaw: torch.Tensor, *, steps: int, protocol: dict):
        if steps < 1:
            raise ValueError("window needs at least one step")
        self.steps = steps
        self.protocol = protocol
        self.dt = float(protocol["episode_length_s"]) / steps
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
        self.tilt_max = torch.zeros_like(start_yaw)
        self.tilt_violation = torch.zeros_like(self.alive)
        self.non_foot_max = None
        self.non_foot_violation = torch.zeros_like(self.alive)
        self.mesh_min_z = None
        self.foot_contact = None
        self.foot_load = None
        self.feet_down = []
        self._tilt_run = None
        self._carrier_run = None
        self.count = 0

    def add(self, *, pos: torch.Tensor, yaw: torch.Tensor, velocity_yaw: torch.Tensor,
            terminated: torch.Tensor, timeout: torch.Tensor, head_tail_force: torch.Tensor,
            tilt_cos: torch.Tensor | None = None, non_foot_fraction: torch.Tensor | None = None,
            mesh_min_z: torch.Tensor | None = None, foot_contact: torch.Tensor | None = None,
            foot_fraction: torch.Tensor | None = None) -> None:
        """Consume a post-physics, pre-reset frame [m, rad, m/s, N, 1].

        After the first end, forward velocity is imputed as zero for the remaining window.
        Diagnostics cover only the first episode and report their coverage. A simultaneous
        failure and timeout is a failure, including on the final step.

        Args:
            pos: base position [m], (N, 3).
            yaw: base yaw [rad], (N,).
            velocity_yaw: base velocity in the yaw-aligned gravity frame [m/s], (N, 3).
            terminated: nonzero-termination flag, (N,).
            timeout: episode-timeout flag, (N,).
            head_tail_force: head/neck/tail contact force sum [N], (N,).
            tilt_cos: cosine of the base tilt (1.0 = upright), (N,).
            non_foot_fraction: non-foot body load as a fraction of body weight, (N, B).
            mesh_min_z: lowest world z of the non-foot collision meshes [m], (N, B).
            foot_contact: per-foot contact flag (> 1 N), (N, num_feet).
            foot_fraction: per-foot load as a fraction of body weight, (N, num_feet).
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
        if tilt_cos is not None and "tilt_cos_min" in self.protocol["gates"]:
            self.tilt_max = torch.where(self.alive, torch.maximum(self.tilt_max, tilt_cos), self.tilt_max)
            self.tilt_violation |= self._sustained(
                "_tilt_run", tilt_cos < self.protocol["gates"]["tilt_cos_min"], "tilt_sustain_s")
        if non_foot_fraction is not None and "non_foot_load_fraction_lt" in self.protocol["gates"]:
            peak = non_foot_fraction.max(dim=1).values
            self.non_foot_max = peak if self.non_foot_max is None else torch.maximum(self.non_foot_max, peak)
            over = (non_foot_fraction >= self.protocol["gates"]["non_foot_load_fraction_lt"]).any(dim=1)
            self.non_foot_violation |= self._sustained(
                "_carrier_run", over, "non_foot_load_sustain_s")
        if mesh_min_z is not None:
            self.mesh_min_z = mesh_min_z if self.mesh_min_z is None else torch.minimum(self.mesh_min_z, mesh_min_z)
        if foot_contact is not None:
            contact = foot_contact & self.alive[:, None]
            self.foot_contact = contact if self.foot_contact is None else self.foot_contact + contact
            self.feet_down.append(contact.sum(dim=1))
        if foot_fraction is not None:
            self.foot_load = foot_fraction if self.foot_load is None else self.foot_load + foot_fraction
        self.survived |= self.alive & timeout & ~terminated & (self.count == self.steps - 1)
        self.alive &= ~(terminated | timeout)
        self.count += 1

    def _sustained(self, field: str, condition: torch.Tensor, key: str) -> torch.Tensor:
        """True where ``condition`` has held for at least ``protocol[key]`` seconds."""
        condition = condition & self.alive
        previous = getattr(self, field)
        run = condition.to(torch.int64) if previous is None else torch.where(
            condition, previous + 1, torch.zeros_like(previous))
        setattr(self, field, run)
        return run * self.dt >= float(self.protocol["gates"][key])

    def _require(self, measured, key: str, quantity: str) -> None:
        """Refuse a protocol that gates on a quantity this run never measured."""
        if key in self.protocol["gates"] and measured is None:
            raise ValueError(f"protocol gates on {quantity}, but the run never measured it")

    def result(self) -> dict:
        """Return aggregate gates plus per-env evidence; refuse a partial window."""
        if self.count != self.steps:
            raise ValueError(f"incomplete window: {self.count}/{self.steps}")
        delta = self.end_pos - self.start_pos
        distance = delta[:, 0] * self.start_yaw.cos() + delta[:, 1] * self.start_yaw.sin()
        mae = self.error / self.steps
        coverage = self.valid_steps.clamp_min(1)
        gates = self.protocol["gates"]
        measured = {
            "forward_mae_mps": mae.mean().item(),
            "forward_displacement_m": distance.mean().item(),
            "first_episode_timeout_fraction": self.survived.float().mean().item(),
        }
        passed = {
            "tracking": measured["forward_mae_mps"] < gates["forward_mae_mps_lt"],
            "displacement": measured["forward_displacement_m"] > gates["forward_displacement_m_gt"],
            "survival": measured["first_episode_timeout_fraction"] > gates["first_episode_timeout_fraction_gt"],
        }
        diagnostics = {
            "lateral_speed_abs_mps": (self.lateral / coverage).mean().item(),
            "yaw_offset_abs_rad": (self.yaw / coverage).mean().item(),
            "head_tail_contact_force_n": (self.load / coverage).mean().item(),
            "first_episode_frame_fraction": (self.valid_steps / self.steps).mean().item(),
        }
        self._require(self.tilt_violation if self.tilt_max.numel() else None,
                      "tilt_cos_min", "the base tilt")
        if "tilt_cos_min" in gates:
            measured["tilt_max_deg"] = self.tilt_max.clamp(-1.0, 1.0).acos().max().rad2deg().item()
            diagnostics["tilt_max_deg"] = measured["tilt_max_deg"]
            passed["attitude"] = not bool(self.tilt_violation.any())
        self._require(self.non_foot_max, "non_foot_load_fraction_lt", "the per-body contact loads")
        if "non_foot_load_fraction_lt" in gates:
            measured["non_foot_load_fraction_max"] = self.non_foot_max.max().item()
            diagnostics["non_foot_load_fraction"] = measured["non_foot_load_fraction_max"]
            passed["no_non_foot_carrier"] = not bool(self.non_foot_violation.any())
        self._require(self.mesh_min_z, "non_foot_mesh_min_z_gt", "the collision-mesh ground clearance")
        if "non_foot_mesh_min_z_gt" in gates:
            measured["non_foot_mesh_min_z_m"] = self.mesh_min_z.min().item()
            diagnostics["non_foot_mesh_min_z_m"] = self.mesh_min_z.min(dim=0).values.tolist()
            passed["no_mesh_through_floor"] = bool(
                (self.mesh_min_z > gates["non_foot_mesh_min_z_gt"]).all())
        if self.foot_contact is not None:
            diagnostics["foot_duty"] = (self.foot_contact / coverage[:, None]).mean(dim=0).tolist()
            diagnostics["feet_down_mean"] = (torch.stack(self.feet_down, dim=1) / coverage[:, None]).mean().item()
        if self.foot_load is not None:
            diagnostics["foot_load_fraction"] = (self.foot_load / coverage[:, None]).mean(dim=0).tolist()
        return {
            "verdict": "pass" if all(passed.values()) else "fail",
            "metrics": measured, "gates": passed,
            "diagnostics": diagnostics,
            "per_env": {"forward_mae_mps": mae.tolist(), "forward_displacement_m": distance.tolist(),
                        "survived": self.survived.tolist(), "valid_steps": self.valid_steps.tolist()},
        }
