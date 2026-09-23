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


# --- fixed scenes: one command per env, held for the whole window ---------------------------------
#
# A *scene* is a constant command a single env walks under, and a window is a set of them. This is
# not a timeline, so it does not go through ``CommandPlayer``: nothing here changes over time, and
# the two tools that do use the player (``eval.py``, ``video_matrix.py``) depend on its broadcast
# semantics. What the two share is the injection point, not the structure.

def scene_assignment(scenes: list[dict], num_envs: int, seed: int) -> torch.Tensor:
    """Which scene each env plays, as an index into ``scenes`` per env, shape ``(num_envs,)``.

    Round-robin decides the counts and a seeded shuffle decides *which* envs, for two different
    reasons: the counts are what makes every scene measurable at all (a band with no env is a
    question nobody asked), and the permutation is what stops a band from always sitting on the same
    env -- the spawn pose and the terrain differ per env, so a fixed pairing would confound the band
    with that env's start.
    """
    if not scenes:
        raise ValueError("no scenes: a fixed-scene window needs at least one")
    if num_envs < 1:
        raise ValueError(f"a fixed-scene window needs at least one env, got {num_envs}")
    rounds = torch.tensor([index % len(scenes) for index in range(num_envs)])
    generator = torch.Generator().manual_seed(int(seed))
    return rounds[torch.randperm(num_envs, generator=generator)]


def scene_commands(scenes: list[dict], assignment: torch.Tensor, num_envs: int,
                   device: str) -> torch.Tensor:
    """The constant ``(num_envs, 3)`` block ``[vx, vy, wz]`` each env is commanded under.

    Held for the whole window, which is the point: a fixed scene is what lets a band be judged on a
    frame count somebody planned, instead of on wherever the environment's own resampling landed.
    """
    if assignment.numel() != num_envs:
        raise ValueError(f"assignment has {assignment.numel()} entries for {num_envs} envs")
    block = torch.zeros(num_envs, 3, device=device)
    for scene_index, scene in enumerate(scenes):
        rows = assignment == scene_index
        for column, key in enumerate(("vx", "vy", "wz")):
            block[rows, column] = float(scene.get(key, 0.0))
    return block
