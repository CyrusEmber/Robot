# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""What one baseline fixed-window frame is: the data contract, declared once in one table.

Collection and judging are separate on purpose:

* this module is the simulator side. Every frame is checked against the columns its record's format
  declares and stored with the axis labels it was measured against (which body, which foot), so "the
  numbers line up with the right body" is a property of the record instead of a convention in a
  reader's head;
* :mod:`ablation_harness.baseline_metrics` is the judge: pure functions over one saved record, so
  a threshold can move without re-running physics.

A frame is post-physics and pre-reset. An env's terminal frame carries the state its episode ended
in, never the state after the respawn, and it carries the termination flags of that step so the
judge reconstructs each env's valid interval rather than inferring it from the numbers.

The contract is looked up by the format a record names (:func:`format_spec`), never read off this
module's newest table: a column added to the newest format was never declared by the older ones, and
reading them under it would turn every earlier record unreadable. The current format's own table is
frozen by digest in ``ablation_harness/frame_semantics.json``, checked by
``rl_exp/tools/verify/test_baseline_contract.py``.
"""

from __future__ import annotations

import os
import pathlib
import tempfile

import torch

ENV = "env"
VEC3 = "vec3"
BODIES = "bodies"
FEET = "feet"
#: A vec3 per axis label -- one point per foot, not one vector for the whole robot.
VEC3_FEET = "vec3_feet"

# name -> (kind, unit, meaning). One declaration, read by both sides. These twelve are the first
# format's table; ``COLUMNS`` below is the newest one, which shares them by value.
COLUMNS_V1: dict[str, tuple[str, str, str]] = {
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
FORMAT_V1 = "baseline-frames-1"

# Meta the judge cannot reconstruct from the frames: the episode's initial state, and the body
# weight a per-body contact fraction has to be converted with when a protocol gates in newtons.
# Frame 0 is already one control step in, so every displacement and yaw drift is measured from here.
REQUIRED_META = ("start_pos", "start_yaw", "body_weight_n")

#: The foot reading: where that foot's own collision mesh reaches lowest under the live pose (its z
#: is the clearance, and the point is the geometric candidate for the contact), plus the substrate of
#: a contact-point velocity -- the body's COM, its velocity, and its angular velocity, all in world.
#: All three are raw: `v_com + omega x (p_lowest - p_com)` is reconstructible from them, and that is
#: the one reading a velocity at a *point* of a rotating body cannot be taken without. Attitude is
#: deliberately not a column: the pose already enters through the lowest point, and a column nothing
#: reads is what this harness refuses elsewhere.
FOOT_COLUMNS: dict[str, tuple[str, str, str]] = {
    "foot_lowest_point": (VEC3_FEET, "m", "world position of that foot's lowest collision-mesh vertex"),
    "foot_com_pos": (VEC3_FEET, "m", "that foot body's center of mass, world frame -- the point "
                                     "foot_lin_vel is the velocity of"),
    "foot_lin_vel": (VEC3_FEET, "m/s", "that foot body's COM linear velocity, world frame"),
    "foot_ang_vel": (VEC3_FEET, "rad/s", "that foot body's angular velocity, world frame"),
}

#: The newest format: the twelve columns above plus the foot reading.
COLUMNS: dict[str, tuple[str, str, str]] = {**COLUMNS_V1, **FOOT_COLUMNS}
#: What the newest format must carry on top of the first one's meta: where its ground came from, and
#: which asset's geometry the foot reading was taken off -- so no later reader fills that gap with
#: another family's mesh, which is how a historical record would silently change meaning.
REQUIRED_META_V2 = ("ground_source", "foot_geometry")

#: The format a collector writes unless it pins an older one.
FORMAT = "baseline-frames-2"

#: Every format this reader knows, by the name a record carries. A declaration is fixed for the life
#: of its format: changing a column's meaning, unit or shape publishes a new name, so records written
#: under the old one keep being read as what they were. The newest shares the first one's twelve
#: entries by value, so editing a shared column moves *both* digests in ``frame_semantics.json``:
#: it cannot pass as an edit of one of them.
_FORMATS: dict[str, dict] = {
    FORMAT_V1: {"columns": COLUMNS_V1, "axis_kinds": AXIS_KINDS, "required_meta": REQUIRED_META},
    FORMAT: {"columns": COLUMNS, "axis_kinds": (*AXIS_KINDS, VEC3_FEET),
             "required_meta": (*REQUIRED_META, *REQUIRED_META_V2)},
}


class FramesContractError(ValueError):
    """A frame does not match the contract the collector and the judge share."""


def format_names() -> list[str]:
    """The formats this reader declares, sorted."""
    return sorted(_FORMATS)


def format_spec(name: object) -> dict:
    """The declaration a record's format names, or a refusal listing the ones this reader knows."""
    spec = _FORMATS.get(name)  # type: ignore[arg-type]
    if spec is None:
        raise FramesContractError(
            f"{name!r} is not a frame format this reader knows ({format_names()}): a record whose "
            "format is unknown cannot be read as if it were one of them")
    return spec


def expected_shape(kind: str, num_envs: int, axis_len: int) -> tuple[int, ...]:
    """The trailing shape a column of this kind must have, given its axis labels.

    One home for "what shape is kind X": the collector checks a frame against it before storing, and
    the judge checks the stored column against it before measuring, so the two cannot drift apart.
    """
    if kind == ENV:
        return (num_envs,)
    if kind == VEC3:
        return (num_envs, 3)
    if kind == VEC3_FEET:
        return (num_envs, axis_len, 3)
    return (num_envs, axis_len)


class BaselineFrames:
    """Collect one fixed window, frame by frame, under the declared contract.

    ``add`` is all-or-nothing: a frame that is missing a column, carries an undeclared one, or
    whose shape does not line up with its axis labels is refused, because a report built from a
    mis-shaped sample reads like evidence while being none. Numeric problems are *not* refused
    here -- :func:`ablation_harness.baseline_metrics.judge` turns a non-finite sample into an
    ``invalid`` verdict with the column named, which is the legible outcome.

    ``fmt`` is the format this collector writes; it defaults to the newest one, and a caller that
    pins an older format is what keeps an older record reproducible.
    """

    def __init__(self, *, num_envs: int, step_dt: float, axes: dict[str, list[str]],
                 fmt: str = FORMAT):
        if num_envs < 1:
            raise ValueError("a window needs at least one env")
        self.fmt = fmt
        self.spec = format_spec(fmt)
        self.columns: dict[str, tuple[str, str, str]] = self.spec["columns"]
        self.axis_kinds: tuple[str, ...] = tuple(self.spec["axis_kinds"])
        self.num_envs = num_envs
        self.step_dt = step_dt
        self.axes: dict[str, list[str]] = {}
        for name, labels in axes.items():
            if name not in self.columns or self.columns[name][0] not in self.axis_kinds:
                raise FramesContractError(f"{name} is not a body- or foot-indexed column")
            if not labels or len(set(labels)) != len(labels):
                raise FramesContractError(f"{name}: axis labels must be non-empty and unique, got {labels}")
            self.axes[name] = list(labels)
        missing = [name for name, spec in self.columns.items()
                   if spec[0] in self.axis_kinds and name not in self.axes]
        if missing:
            raise FramesContractError(f"axis labels missing for {missing}: a per-body reading must name its bodies")
        self._series: dict[str, list[torch.Tensor]] = {name: [] for name in self.columns}
        self.count = 0

    def add(self, **frame: torch.Tensor) -> None:
        """Append one frame; every declared column must be present exactly once."""
        for name in self.columns:
            if name not in frame:
                raise FramesContractError(
                    f"frame {self.count} has no {name}: a frame is all of {sorted(self.columns)}, not a bag of "
                    "whatever happened to be measured")
        for name, value in frame.items():
            if name not in self.columns:
                raise FramesContractError(f"frame {self.count} carries {name}, which the contract does not declare")
            if not torch.is_tensor(value):
                raise FramesContractError(f"frame {self.count}: {name} is {type(value).__name__}, not a tensor")
            expected = expected_shape(self.columns[name][0], self.num_envs, len(self.axes.get(name, ())))
            if tuple(value.shape) != expected:
                raise FramesContractError(
                    f"frame {self.count}: {name} has shape {tuple(value.shape)}, the contract says {expected} "
                    f"({self.columns[name][2]})")
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
        missing = [name for name in self.spec["required_meta"] if name not in meta]
        if missing:
            raise FramesContractError(f"artifact is missing {missing}: without the initial state no "
                                      "displacement or yaw drift can be measured")
        return {
            "format": self.fmt,
            "protocol": protocol,
            "frames": self.frames(),
            "axes": {name: list(labels) for name, labels in self.axes.items()},
            "meta": {"steps": self.count, "step_dt": self.step_dt, "num_envs": self.num_envs, **meta},
        }


def save(path: pathlib.Path | str, artifact: dict) -> None:
    """Write a record for the offline judge: whole or not at all, never over one that exists.

    The record is what a verdict is re-derived from, so a second collection does not silently
    replace the first one's evidence, and a half-written file cannot pass for a complete window.
    """
    path = pathlib.Path(path)
    format_spec(artifact.get("format"))
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    os.close(handle)
    try:
        torch.save(artifact, tmp)
        try:
            # ponytail: link-then-unlink is create-if-absent, so two collectors racing for one path
            # cannot overwrite each other. Ceiling: no fsync, so a machine losing power mid-write can
            # still lose the record -- upgrade by fsyncing the temp file before this link.
            os.link(tmp, path)
        except OSError as err:
            if not path.exists():
                raise
            raise FileExistsError(f"{path} already exists: a collection is evidence, and a second "
                                  "one gets its own path") from err
    finally:
        pathlib.Path(tmp).unlink(missing_ok=True)


def load(path: pathlib.Path | str) -> dict:
    """Read a record back; refuse anything that is not one of ours."""
    artifact = torch.load(pathlib.Path(path), map_location="cpu", weights_only=False)
    format_spec(artifact.get("format"))
    return artifact
