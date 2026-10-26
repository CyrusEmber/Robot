# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Additional lizard2 terms; published earlier terms keep their original semantics."""

import math

import torch
from isaaclab.managers import ManagerTermBase, TerminationTermCfg


class HeadGroundContactDwell(ManagerTermBase):
    """Terminate after uninterrupted head-to-floor normal force [N] for a duration [s].

    The head mesh's rigid owner is named ``neck_pitch`` in the adopted asset. A
    separate, single-body sensor filters only the floor collider; chest contact
    and self-contact never enter this term. Every physics sample in the control
    window is consumed oldest first, so even one detached substep clears dwell.
    """

    def __init__(self, cfg: TerminationTermCfg, env):
        super().__init__(cfg, env)
        self._sensor = env.scene[cfg.params["sensor_name"]]
        self._substeps = env.cfg.decimation
        self._dt = env.cfg.sim.dt
        if (env.cfg.scene.lazy_sensor_update
                or not math.isclose(self._sensor.cfg.update_period, self._dt)
                or self._sensor.cfg.history_length < self._substeps):
            raise ValueError("Head ground dwell requires every physics substep in sensor history")
        if self._sensor.body_names != [cfg.params["head_body_name"]]:
            raise ValueError("Head ground sensor must resolve exactly the head mesh owner")
        # Multi-environment PhysX views return one filter-path list per sensor.
        paths = list(self._sensor.contact_view.filter_paths)
        floor = cfg.params["floor_prim_path"]
        if (not paths or not all(row == floor or row == [floor] for row in paths)
                or self._sensor.contact_view.filter_count != 1):
            raise ValueError(f"Head ground sensor must resolve exactly the floor collider: {paths!r}")
        if cfg.params["dwell_s"] <= 0 or cfg.params["threshold"] <= 0:
            raise ValueError("Head ground threshold and dwell must be positive")
        self._steps = torch.zeros(env.num_envs, dtype=torch.long, device=env.device)

    def __call__(self, env, sensor_name: str, head_body_name: str, floor_prim_path: str,
                 threshold: float = 1.0, dwell_s: float = 0.5) -> torch.Tensor:
        """Consume the last control window; threshold [N], continuous dwell [s]."""
        history = self._sensor.data.force_matrix_w_history
        if history is None:
            raise RuntimeError("Head ground contact requires filtered force history")
        forces = history.torch
        if forces.shape != (env.num_envs, self._sensor.cfg.history_length, 1, 1, 3):
            raise RuntimeError("Unexpected head-to-floor contact history shape")
        touching = torch.linalg.vector_norm(forces[:, :self._substeps, 0, 0], dim=-1) > threshold
        required = max(1, math.ceil(dwell_s / self._dt - 1.e-9))
        terminated = torch.zeros(env.num_envs, dtype=torch.bool, device=env.device)
        # PhysX history index 0 is newest. A gap must reset before the next sample.
        for index in range(self._substeps - 1, -1, -1):
            # Keep the buffer allocated outside rollout inference_mode, so a
            # later explicit env.reset() can safely clear it outside that mode.
            self._steps.copy_(torch.where(touching[:, index], self._steps + 1, 0))
            terminated |= self._steps >= required
        return terminated

    def reset(self, env_ids=None) -> None:
        """Clear dwell for the reset environments only."""
        if env_ids is None:
            self._steps.zero_()
        else:
            self._steps[env_ids] = 0
