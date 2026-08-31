# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Command timeline player: the protocol yaml is the single source of truth.

The same timeline drives (a) the per-step command injection into the env and
(b) the metric segment windows -- they can never drift apart.
"""

from __future__ import annotations

import torch


class CommandPlayer:
    """Plays a protocol command timeline into a velocity command term.

    Args:
        timeline: List of ``{t, vx, vy, wz}`` dicts (protocol yaml), sorted by t.
        num_envs: Number of environments.
        device: Torch device for the command tensor.
    """

    def __init__(self, timeline: list[dict], num_envs: int, device: str):
        self._starts = torch.tensor([seg["t"] for seg in timeline], device=device, dtype=torch.float)
        # (num_segments, 3) commands [vx, vy, wz] in the base frame
        self._cmds = torch.tensor(
            [[seg.get("vx", 0.0), seg.get("vy", 0.0), seg.get("wz", 0.0)] for seg in timeline],
            device=device,
            dtype=torch.float,
        )
        self._num_envs = num_envs
        self._device = device

    def command_at(self, t: float) -> torch.Tensor:
        """Command active at time ``t`` [s], broadcast to (num_envs, 3)."""
        # last segment whose start <= t (torch.searchsorted right side - 1)
        idx = int(torch.searchsorted(self._starts, torch.tensor(t, device=self._device), right=True)) - 1
        idx = max(idx, 0)
        return self._cmds[idx].unsqueeze(0).expand(self._num_envs, 3)

    def segments(self, episode_length_s: float, step_dt: float) -> list[dict]:
        """Metric windows derived from the same timeline.

        Returns a list of ``{name, start_s, end_s, cmd}`` dicts covering the
        episode (segments starting after the episode end are dropped).
        """
        out = []
        for i, seg in enumerate(self._starts.tolist()):
            start_s = seg
            end_s = self._starts[i + 1].item() if i + 1 < len(self._starts) else episode_length_s
            if start_s >= episode_length_s:
                break
            out.append(
                {
                    "name": "%g-%gs vx=%g wz=%g" % (start_s, end_s, self._cmds[i, 0].item(), self._cmds[i, 2].item()),
                    "start_s": start_s,
                    "end_s": min(end_s, episode_length_s),
                    "cmd": [float(v) for v in self._cmds[i].tolist()],
                }
            )
        return out
