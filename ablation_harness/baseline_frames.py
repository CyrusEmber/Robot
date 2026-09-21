# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""What one baseline fixed-window frame is: the data contract, declared once in one table.

Collection and judging are separate on purpose:

* this module is the simulator side. Every frame is checked against :data:`COLUMNS` and stored
  with the axis labels it was measured against (which body, which foot), so "the numbers line up
  with the right body" is a property of the record instead of a convention in a reader's head;
* :mod:`ablation_harness.baseline_metrics` is the judge: pure functions over one saved record, so
  a threshold can move without re-running physics.

A frame is post-physics and pre-reset. An env's terminal frame carries the state its episode ended
in, never the state after the respawn, and it carries the termination flags of that step so the
judge reconstructs each env's valid interval rather than inferring it from the numbers.
"""

from __future__ import annotations

import pathlib

import torch

ENV = "env"
VEC3 = "vec3"
BODIES = "bodies"
FEET = "feet"

# name -> (kind, unit, meaning). One declaration, read by both sides.
COLUMNS: dict[str, tuple[str, str, str]] = {
    "pos": (VEC3, "m", "base position, world frame"),
    "yaw": (ENV, "rad", "base yaw, in the reward kernel's yaw-aligned frame"),
    "velocity_yaw": (VEC3, "m/s", "base velocity in the yaw-aligned gravity frame"),
    "command_world": (VEC3, "m/s",
                      "command as issued this frame, world frame -- the x/y the reward kernel compares "
                      "against the yaw-frame velocity, so acceptance reads the trained quantity"),
    "head_tail_force": (ENV, "N", "sum of |net contact force| over the head/neck/tail bodies"),
    "tilt_cos": (ENV, "1", "cosine of the base tilt, 1.0 = upright"),
    "non_foot_fraction": (BODIES, "1", "per-body normal contact force / body weight"),
    "mesh_min_z": (BODIES, "m", "lowest world z of those bodies' collision meshes (ground z = 0)"),
    "foot_contact": (FEET, "1", "1.0 where that foot carries more than 1 N this frame"),
    "foot_fraction": (FEET, "1", "per-foot normal contact force / body weight"),
    "terminated": (ENV, "1", "nonzero-termination flag of this frame"),
    "timeout": (ENV, "1", "episode-length flag of this frame"),
}
AXIS_KINDS = (BODIES, FEET)
FORMAT = "baseline-frames-1"

# Meta the judge cannot reconstruct from the frames: the episode's initial state. Frame 0 is
# already one control step in, so every displacement and yaw drift is measured from here.
REQUIRED_META = ("start_pos", "start_yaw")


class FramesContractError(ValueError):
    """A frame does not match the contract the collector and the judge share."""


def _expected_shape(name: str, num_envs: int, axis_len: int) -> tuple[int, ...]:
    """Frame shape the contract prescribes for one column, trailing dims only."""
    kind = COLUMNS[name][0]
    if kind == ENV:
        return (num_envs,)
    if kind == VEC3:
        return (num_envs, 3)
    return (num_envs, axis_len)


class BaselineFrames:
    """Collect one fixed window, frame by frame, under the declared contract.

    ``add`` is all-or-nothing: a frame that is missing a column, carries an undeclared one, or
    whose shape does not line up with its axis labels is refused, because a report built from a
    mis-shaped sample reads like evidence while being none. Numeric problems are *not* refused
    here -- :func:`ablation_harness.baseline_metrics.judge` turns a non-finite sample into an
    ``invalid`` verdict with the column named, which is the legible outcome.
    """

    def __init__(self, *, num_envs: int, step_dt: float, axes: dict[str, list[str]]):
        if num_envs < 1:
            raise ValueError("a window needs at least one env")
        self.num_envs = num_envs
        self.step_dt = step_dt
        self.axes: dict[str, list[str]] = {}
        for name, labels in axes.items():
            if name not in COLUMNS or COLUMNS[name][0] not in AXIS_KINDS:
                raise FramesContractError(f"{name} is not a body- or foot-indexed column")
            if not labels or len(set(labels)) != len(labels):
                raise FramesContractError(f"{name}: axis labels must be non-empty and unique, got {labels}")
            self.axes[name] = list(labels)
        missing = [name for name, spec in COLUMNS.items() if spec[0] in AXIS_KINDS and name not in self.axes]
        if missing:
            raise FramesContractError(f"axis labels missing for {missing}: a per-body reading must name its bodies")
        self._series: dict[str, list[torch.Tensor]] = {name: [] for name in COLUMNS}
        self.count = 0

    def add(self, **frame: torch.Tensor) -> None:
        """Append one frame; every declared column must be present exactly once."""
        for name in COLUMNS:
            if name not in frame:
                raise FramesContractError(
                    f"frame {self.count} has no {name}: a frame is all of {sorted(COLUMNS)}, not a bag of "
                    "whatever happened to be measured")
        for name, value in frame.items():
            if name not in COLUMNS:
                raise FramesContractError(f"frame {self.count} carries {name}, which the contract does not declare")
            if not torch.is_tensor(value):
                raise FramesContractError(f"frame {self.count}: {name} is {type(value).__name__}, not a tensor")
            expected = _expected_shape(name, self.num_envs, len(self.axes.get(name, ())))
            if tuple(value.shape) != expected:
                raise FramesContractError(
                    f"frame {self.count}: {name} has shape {tuple(value.shape)}, the contract says {expected} "
                    f"({COLUMNS[name][2]})")
        for name, value in frame.items():
            self._series[name].append(value.detach().to(device="cpu", dtype=torch.float32).clone())
        self.count += 1

    def frames(self) -> dict[str, torch.Tensor]:
        """The window as ``(T, N, ...)`` float32 tensors, one per declared column."""
        if self.count == 0:
            raise FramesContractError("no frames collected")
        return {name: torch.stack(series) for name, series in self._series.items()}

    def artifact(self, *, protocol: dict, **meta) -> dict:
        """The judge's whole input: frames, their axis labels, the protocol, and the run's meta.

        Everything a verdict depends on travels in this one object, so ``judge`` cannot read a
        second source and a saved record can be re-judged later without the simulator.
        """
        missing = [name for name in REQUIRED_META if name not in meta]
        if missing:
            raise FramesContractError(f"artifact is missing {missing}: without the initial state no "
                                      "displacement or yaw drift can be measured")
        return {
            "format": FORMAT,
            "protocol": protocol,
            "frames": self.frames(),
            "axes": {name: list(labels) for name, labels in self.axes.items()},
            "meta": {"steps": self.count, "step_dt": self.step_dt, "num_envs": self.num_envs, **meta},
        }


def save(path: pathlib.Path | str, artifact: dict) -> None:
    """Write a record for the offline judge."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(artifact, path)


def load(path: pathlib.Path | str) -> dict:
    """Read a record back; refuse anything that is not one of ours."""
    artifact = torch.load(pathlib.Path(path), map_location="cpu", weights_only=False)
    if artifact.get("format") != FORMAT:
        raise FramesContractError(f"{path}: format is {artifact.get('format')!r}, not {FORMAT!r}")
    return artifact
