# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Judge a baseline fixed window from its record -- gates, and whether it may be judged at all.

Three outcomes, and the difference is the point:

* ``invalid``: the record cannot support a verdict (the window never finished, a quantity the
  protocol gates on was never measured, a sample is not finite, a column does not line up with its
  axis labels). Every gate is left ``None``: unjudged, never failed by accident, never passed;
* ``fail`` / ``pass``: the data is trustworthy and the protocol's gates decided.

Nothing here touches the simulator. The input is the record
:mod:`ablation_harness.baseline_frames` wrote, so moving a threshold is
``python -m ablation_harness.baseline_metrics <record> --protocol <other protocol>`` instead of
another rollout -- and a changed verdict then has exactly one possible cause.

A gate exists only when the protocol declares it, and then the column it reads is required: a
protocol may not gate on a quantity the run never measured. That refusal is why the old single-file
window could report 0 deg of tilt for a run that never measured tilt.

**Where the criterion lives.** A criterion is a *named kind* plus that kind's closed parameter set
(:data:`CRITERION_KINDS`), never a free combination of an operator, a unit, an aggregation and a
threshold: a criterion assembled per protocol is a DSL, and what a reader needs a year later is a
short list of names they can look up. So the comparison, its strictness, its unit conversion and its
aggregation order are *inside* the kind -- ``non_foot_carrier_v1`` is "any body over the fraction,
held for the dwell", and no protocol can reorder it into "this body held" by accident.

**Two readers, declared apart.** :data:`JUDGE_ID` names the criteria reader;
:data:`LEGACY_JUDGE_ID` names the threshold-key reader that judged ``Baseline-Flat-v1``/``v2``/``v3``.
A protocol that declares no criteria is judged by the legacy reader only when its identity is one of
:data:`LEGACY_PROTOCOLS`; anything else is refused rather than guessed at, so a new protocol file
that loses a field fails instead of silently scoring under older semantics. Every verdict carries the
judge identity that produced it, which is what makes a re-judged record attributable.
"""

from __future__ import annotations

import argparse
import json
import pathlib

import torch

from ablation_harness import baseline_frames, record

_BASE_COLUMNS = ("pos", "yaw", "velocity_yaw", "command_world", "terminated", "timeout")

#: The gates a protocol may declare, in reporting order. A name outside this set is refused: an
#: unknown gate is a gate nobody reads.
GATE_ORDER = (
    "tracking",
    "displacement",
    "survival",
    "attitude",
    "no_non_foot_contact",
    "no_non_foot_carrier",
    "no_non_foot_load_sum",
    "gait",
    "foot_lift",
    "foot_slip",
    "no_mesh_through_floor",
)

#: The identity of the criteria reader. Declared rather than derived from a file hash: a comment is
#: not a semantic change, and a semantic change is exactly what this must make loud.
#: ``rl_exp/tools/verify/test_baseline_contract.py`` freezes ``id -> kinds -> cases -> expectations``
#: and refuses an in-place edit to a published id, so a changed criterion needs a new kind and a new
#: id instead of an edit here.
JUDGE_ID = "baseline-criteria-1"

#: The identity of the reader that can read the banded criteria (they were added for the lizard2
#: main line, whose command window is a 0-3 m/s range). A protocol names it in ``judge``; the reason
#: is that the record's verdict carries the reader, and a record judged by the banded criteria must
#: not be attributed to the reader that predates them.
BANDED_JUDGE_ID = "baseline-criteria-banded-1"

#: The reader for the banded criteria once a band's first frames are no longer evidence. The first
#: real verdict of the lizard2 line failed its zero-command band on the single frame the 10 s resample
#: dropped the command to 0 m/s (2.622 m/s there, decaying below 0.1 within 1.0 s, 0.004 m per frame
#: after 0.5 s): the band judges a step change the policy cannot have followed yet. The settled reader
#: declares how long a command must have been in force before a frame counts, and a different
#: allowance is a different reader -- hence a new id rather than a re-pinned parameter.
BANDED_SETTLED_JUDGE_ID = "baseline-criteria-banded-settled-1"

#: The identity of the pre-criteria reader. Spelled by mechanism, not by version: ``v1``/``v2``/``v3``
#: are three declarations read by *one* implementation, and this names that implementation. Their
#: protocol identity travels next to it, so "which thresholds" and "which reader" stay separable.
LEGACY_JUDGE_ID = "legacy-baseline-threshold-keys-1"

#: The reader that can read the foot criteria. A new id rather than two more kinds on an old one:
#: they read columns an earlier format does not carry, and a published id's case table is frozen.
FOOTED_JUDGE_ID = "baseline-criteria-footed-1"

#: Protocols allowed to arrive without a ``criteria`` block, by declared identity (not by filename).
LEGACY_PROTOCOLS = (("Baseline-Flat-v1", 1), ("Baseline-Flat-v2", 2), ("Baseline-Flat-v3", 3))

#: Every number this judge can report: name -> (group, unit, columns it reads, what it means).
#: The declaration is the point. A report item is what a protocol lists in ``report_only``, and a name
#: that nobody computes comes back as an absent number -- which reads like a quantity that happened to
#: be unremarkable, not like a gap. So the items are declared where they are produced, with the
#: columns they depend on and the group they answer for:
#:   * ``measurement`` -- was the window measured at all, and over how many samples;
#:   * ``task`` -- did the policy do what the command asked;
#:   * ``behaviour`` -- how did it do it (a policy can track the command by dragging its chin).
REPORT_ITEMS = {
    # -- task performance -------------------------------------------------------------------------
    "forward_mae_mps": ("task", "m/s", ("command_world", "velocity_yaw"), "mean forward speed error"),
    "forward_mae_norm": ("task", "1", ("command_world", "velocity_yaw"), "that error over the command"),
    "forward_displacement_m": ("task", "m", ("pos", "command_world"), "distance along the initial heading"),
    "displacement_frac": ("task", "1", ("pos", "command_world"), "that distance over the asked one"),
    "expected_displacement_m": ("task", "m", ("command_world",), "distance the commands asked for"),
    "first_episode_timeout_fraction": ("task", "1", ("timeout",), "envs that survived the window"),
    "tilt_max_deg": ("task", "deg", ("tilt_cos",), "worst posture of the episode"),
    "tracking_band_error": ("task", "m/s", ("command_world", "velocity_yaw"), "per-band speed error"),
    "displacement_band_ratio": ("task", "1", ("pos", "command_world"), "per-band distance ratio"),
    # -- measurement validity ---------------------------------------------------------------------
    "first_episode_frame_fraction": ("measurement", "1", ("timeout", "terminated"),
                                     "share of the window inside the first episode"),
    "command_mps_mean": ("measurement", "m/s", ("command_world",), "mean issued command"),
    "tracking_band_frames": ("measurement", "frames", ("command_world",), "frames per band"),
    "displacement_band_frames": ("measurement", "frames", ("command_world",), "frames per band"),
    "tracking_unclaimed_frames": ("measurement", "frames", ("command_world",), "frames outside every band"),
    "foot_ground_source": ("measurement", "text", ("ground_source",),
                           "how the ground the clearance is read against was obtained"),
    "foot_swing_frames": ("measurement", "frames", ("foot_contact",), "unloaded frames per foot"),
    "foot_loaded_frames": ("measurement", "frames", ("foot_fraction",), "loaded frames per foot"),
    # -- behaviour --------------------------------------------------------------------------------
    "lateral_speed_abs_mps": ("behaviour", "m/s", ("velocity_yaw",), "mean sideways speed"),
    "yaw_offset_abs_rad": ("behaviour", "rad", ("yaw",), "mean |yaw drift|"),
    "head_tail_contact_force_n": ("behaviour", "N", ("head_tail_force",), "mean force on head/neck/tail"),
    "non_foot_load_fraction": ("behaviour", "1", ("non_foot_fraction",), "peak non-foot load fraction"),
    "non_foot_contact_load_n": ("behaviour", "N", ("non_foot_fraction",), "the same, in newtons"),
    "non_foot_contact_frames": ("behaviour", "frames", ("non_foot_fraction",), "frames above the limit"),
    "non_foot_mesh_min_z_m": ("behaviour", "m", ("mesh_min_z",), "lowest non-foot mesh point"),
    "foot_duty": ("behaviour", "1", ("foot_contact",), "share of frames each foot carried load"),
    "foot_load_fraction": ("behaviour", "1", ("foot_fraction",), "mean load fraction per foot"),
    "feet_down_mean": ("behaviour", "1", ("foot_contact",), "feet carrying load per frame"),
    "gait_swing_feet_least": ("behaviour", "feet", ("foot_contact", "foot_fraction"), "worst env's swings"),
    "foot_clearance_swing_m": ("behaviour", "m", ("foot_lowest_point",),
                               "peak clearance per foot while unloaded"),
    "foot_slip_mps": ("behaviour", "m/s",
                      ("foot_lowest_point", "foot_com_pos", "foot_lin_vel", "foot_ang_vel"),
                      "mean tangential contact-point speed per foot while loaded"),
    "foot_lift_peak_m": ("behaviour", "m", ("foot_lowest_point",), "highest clearance any foot reached"),
    "foot_lift_feet_least": ("behaviour", "feet", ("foot_lowest_point",), "worst env's lifted feet"),
    "foot_slip_fraction_worst": ("behaviour", "1", ("foot_lin_vel",), "worst foot's sliding share"),
}

#: kind -> {"params": exactly these, "columns": the record columns it reads}.
#: The parameter set is closed in both directions: an extra key is refused (it would be a knob the
#: kind ignores, i.e. a declaration that lies) and a missing one is refused (it would be a default
#: nobody wrote down).
CRITERION_KINDS = {
    "tracking_v1": {"params": ("threshold", "normalized"), "columns": ()},
    "displacement_v1": {"params": ("threshold", "normalized"), "columns": ()},
    "survival_v1": {"params": ("threshold",), "columns": ()},
    "sustained_tilt_v1": {"params": ("threshold_cos", "sustain_s"), "columns": ("tilt_cos",)},
    "non_foot_contact_v1": {"params": ("limit_n", "eps"), "columns": ("non_foot_fraction",)},
    "non_foot_carrier_v1": {"params": ("fraction", "sustain_s"), "columns": ("non_foot_fraction",)},
    "mesh_clearance_v1": {"params": ("threshold_m",), "columns": ("mesh_min_z",)},
    # -- the banded criteria -------------------------------------------------------------------
    # A range command cannot be judged by one mean: the mean of a run that walks in the low band and
    # stalls in the top one looks the same as a run that is uniformly mediocre, and those are
    # different failures. The bands are part of the criterion, not a reporting detail.
    "tracking_banded_v1": {
        "params": ("threshold", "floor_mps", "zero_band_mps", "zero_abs_mps", "bands"),
        "columns": ("command_world", "velocity_yaw")},
    "displacement_banded_v1": {
        "params": ("threshold", "zero_band_mps", "zero_abs_m", "bands"),
        "columns": ("command_world", "pos")},
    # The same two criteria with a declared settling time. ``settle_s`` is how long a command must have
    # been in force before a frame is evidence; the band boundary is a step, and at the frame it lands
    # no causal policy is already at the new speed. New kind names on purpose: adding the parameter to
    # the kinds above would move a published reader's semantics instead of adding a reader.
    "tracking_banded_settled_v1": {
        "params": ("threshold", "floor_mps", "zero_band_mps", "zero_abs_mps", "settle_s", "bands"),
        "columns": ("command_world", "velocity_yaw")},
    "displacement_banded_settled_v1": {
        "params": ("threshold", "zero_band_mps", "zero_abs_m", "settle_s", "bands"),
        "columns": ("command_world", "pos")},
    # The single-body criterion reads each body against the fraction *before* the dwell, so bodies
    # taking turns under the fraction accumulate into one sustained reading there. Two bodies at 4%
    # under a 5% threshold are invisible to it while carrying 8% between them; here the load is
    # summed over the bodies first.
    "non_foot_load_sum_v1": {"params": ("fraction_sum", "sustain_s"), "columns": ("non_foot_fraction",)},
    # A gait is a sequence, not a level: the criterion is "enough feet completed a swing", judged on
    # the frames the command actually asked to move.
    "gait_swing_v1": {
        "params": ("min_swing_feet", "min_air_time_s", "min_landing_load", "band_mps"),
        "columns": ("command_world", "foot_contact", "foot_fraction")},
    # -- the foot criteria: what the gait kind cannot see -------------------------------------------
    # A completed swing says the foot left the ground and came back; it does not say the foot ever
    # lifted clear, and it says nothing about a loaded foot that is sliding. Both read the contact
    # candidate's own geometry and velocity rather than the body's: a foot that only rotates has a
    # zero body velocity and a moving contact point (``foot_point_velocity``, shared with the probe).
    # They exist as kinds now because format 2 measures the columns they gate -- a threshold over an
    # unmeasured quantity is what this module refuses everywhere.
    "foot_lift_v1": {"params": ("min_lift_m", "band_mps", "min_feet"),
                     "columns": ("foot_lowest_point", "foot_contact", "command_world")},
    "foot_slip_v1": {"params": ("max_slip_mps", "min_load", "max_slip_fraction"),
                     "columns": ("foot_lowest_point", "foot_com_pos", "foot_lin_vel", "foot_ang_vel",
                                 "foot_fraction")},
}

#: Which reader may read which kinds. The protocol's ``judge`` is a binding, not a label: a criterion
#: the named reader does not cover is refused, so a protocol cannot reach new semantics by naming an
#: old reader. (Adding a kind here does not move a published id's digest: the freeze pins the subset
#: of kinds each id *lists*, see ``test_baseline_contract.frozen_digests``.)
JUDGE_KINDS = {
    JUDGE_ID: ("tracking_v1", "displacement_v1", "survival_v1", "sustained_tilt_v1",
               "non_foot_contact_v1", "non_foot_carrier_v1", "mesh_clearance_v1"),
    BANDED_JUDGE_ID: ("tracking_v1", "displacement_v1", "survival_v1", "sustained_tilt_v1",
                      "non_foot_contact_v1", "non_foot_carrier_v1", "mesh_clearance_v1",
                      "tracking_banded_v1", "displacement_banded_v1", "non_foot_load_sum_v1",
                      "gait_swing_v1"),
    BANDED_SETTLED_JUDGE_ID: ("tracking_v1", "displacement_v1", "survival_v1", "sustained_tilt_v1",
                              "non_foot_contact_v1", "non_foot_carrier_v1", "mesh_clearance_v1",
                              "tracking_banded_settled_v1", "displacement_banded_settled_v1",
                              "non_foot_load_sum_v1", "gait_swing_v1"),
    FOOTED_JUDGE_ID: ("tracking_v1", "displacement_v1", "survival_v1", "sustained_tilt_v1",
                      "non_foot_contact_v1", "non_foot_carrier_v1", "mesh_clearance_v1",
                      "tracking_banded_settled_v1", "displacement_banded_settled_v1",
                      "non_foot_load_sum_v1", "gait_swing_v1", "foot_lift_v1", "foot_slip_v1"),
}

#: Which reader produces which report items. Only the newest reader declares its list: the older ones
#: were published without one, and tightening them now would invalidate verdicts already on record.
JUDGE_REPORTS = {
    FOOTED_JUDGE_ID: tuple(REPORT_ITEMS),
}


def _gate_tracking_v1(frames: dict, alive: torch.Tensor, dt: float, measured: dict, meta: dict,
                      params: dict) -> bool:
    """Absolute or band-relative forward speed error, strictly below the threshold."""
    key = "forward_mae_norm" if params["normalized"] else "forward_mae_mps"
    return measured[key] < params["threshold"]


def _gate_displacement_v1(frames: dict, alive: torch.Tensor, dt: float, measured: dict, meta: dict,
                          params: dict) -> bool:
    """Distance travelled, strictly above the threshold (absolute meters, or the commanded fraction)."""
    key = "displacement_frac" if params["normalized"] else "forward_displacement_m"
    return measured[key] > params["threshold"]


def _gate_survival_v1(frames: dict, alive: torch.Tensor, dt: float, measured: dict, meta: dict,
                      params: dict) -> bool:
    """Fraction of envs that reached the window's end without terminating, strictly above threshold."""
    return measured["first_episode_timeout_fraction"] > params["threshold"]


def _gate_sustained_tilt_v1(frames: dict, alive: torch.Tensor, dt: float, measured: dict, meta: dict,
                            params: dict) -> bool:
    """The worst posture of the episode, and only while it is sustained: ``cos(tilt) < threshold``."""
    breach = (frames["tilt_cos"] < params["threshold_cos"]) & alive
    return not bool(_sustained(breach, dt, params["sustain_s"]).any())


def _non_foot_contact_breach(frames: dict, alive: torch.Tensor, meta: dict, params: dict) -> torch.Tensor:
    """(T, N, B) bool: this body is above the load limit on this frame, inside the first episode.

    Shared by the criterion that decides on it and the diagnostic that reports it, so the number a
    reviewer reads and the number the verdict came from are one computation.
    """
    weight_n = float(meta["body_weight_n"])
    limit = params["limit_n"] / weight_n  # the recorded column is a fraction of body weight
    return (frames["non_foot_fraction"] > limit + params["eps"]) & alive.unsqueeze(-1)


def _gate_non_foot_contact_v1(frames: dict, alive: torch.Tensor, dt: float, measured: dict, meta: dict,
                              params: dict) -> bool:
    """Any frame with a non-foot body above the load limit: the training termination's criterion.

    ``eps`` is carried by the protocol rather than written here because the boundary case -- a body
    sitting exactly at the limit -- is a decision, and a decision belongs in the frozen declaration.
    """
    return not bool(_non_foot_contact_breach(frames, alive, meta, params).any())


def _gate_non_foot_carrier_v1(frames: dict, alive: torch.Tensor, dt: float, measured: dict, meta: dict,
                              params: dict) -> bool:
    """A *weight-bearing* contact held for a dwell, aggregated **across bodies before time**.

    The order is the criterion, not an implementation detail: ``any(dim=-1)`` collapses the bodies
    first, so bodies taking turns carrying the weight accumulate into one sustained reading. A
    reader who wants "one body held it alone" needs a different kind, because that is a different
    observation about the robot.
    """
    breach = (frames["non_foot_fraction"] >= params["fraction"]).any(dim=-1) & alive
    return not bool(_sustained(breach, dt, params["sustain_s"]).any())


def _gate_mesh_clearance_v1(frames: dict, alive: torch.Tensor, dt: float, measured: dict, meta: dict,
                            params: dict) -> bool:
    """Every body's lowest mesh vertex above the threshold on every frame: no dwell, no tolerance."""
    clearance = _keep(frames["mesh_min_z"], alive, float("inf")).amin(dim=0)  # (N, B)
    return bool((clearance > params["threshold_m"]).all())


def _band_masks(command: torch.Tensor, params: dict):
    """``[[(lo, hi), mask], ...]`` over the commanded speed, plus the frames no band claims.

    Bands are ``[lo, hi)`` and the highest is closed at its top, so a frame belongs to exactly one
    band AND the declared maximum lands inside the window -- an exact maximum would otherwise pass
    through every band and read as a hole in the declaration. A frame outside every band is such a
    hole: the callers fail on it, because dropping a frame is the silent pass this module keeps
    refusing.
    """
    bands = [(float(lo), float(hi)) for lo, hi in params["bands"]]
    masks, claimed = [], torch.zeros_like(command, dtype=torch.bool)
    for index, (lo, hi) in enumerate(bands):
        top = index == len(bands) - 1
        mask = (command >= lo) & (command <= hi if top else command < hi)
        masks.append(((lo, hi), mask))
        claimed |= mask
    return masks, ~claimed


def _band_label(band: tuple[float, float]) -> str:
    """The band as a report key, so a failure names the band a reader has to look at."""
    return f"{band[0]:g}-{band[1]:g}mps"


def _settled(command: torch.Tensor, dt: float, params: dict) -> torch.Tensor | None:
    """``(T, N)`` bool: the command has been in force for at least this kind's ``settle_s``.

    ``None`` when the kind declares no settling time, which is how the banded kinds read. The question
    the allowance answers is causal: a band boundary is a step, and on the frame it lands no policy has
    had time to be at the new speed. Measured on the lizard2 line's first verdict, the zero band's
    worst frame is the resample frame itself -- 2.622 m/s against a 0.15 limit, decaying below 0.1
    within 1.0 s and moving 0.004 m per frame after 0.5 s -- so the whole failure was the step, not
    the policy. The allowance is bounded and declared: a policy still at the old speed after
    ``settle_s`` is judged like any other frame, and the frames the episode's first command covers are
    as new as a change, so they are not evidence either.
    """
    settle_s = float(params.get("settle_s", 0.0))
    if settle_s <= 0.0:
        return None
    steps = max(1, int(round(settle_s / dt)))
    index = torch.arange(command.shape[0], device=command.device).reshape(-1, 1).expand_as(command)
    changed = torch.zeros_like(command, dtype=torch.bool)
    changed[0] = True  # the episode's first command is as new as a change
    changed[1:] = command[1:] != command[:-1]
    since = torch.cummax(torch.where(changed, index, torch.zeros_like(index)), dim=0).values
    return (index - since) >= steps


def _gate_tracking_banded_v1(frames: dict, alive: torch.Tensor, dt: float, measured: dict, meta: dict,
                             params: dict) -> bool:
    """Per-band forward-speed error, with the zero-command band judged on absolute speed.

    One mean cannot tell "walked in the low band, stalled in the top one" from "uniformly mediocre",
    so the bands are the criterion. Inside a relative band the reading is the mean of
    ``|v_fwd - v_cmd| / max(v_cmd, floor_mps)``; the ``floor_mps`` is what makes a frame commanded
    near zero divided by something real instead of by a 1e-6 epsilon. Frames outside the first
    episode are charged the full error (a policy that stopped early keeps scoring), while the zero
    band is read on ``alive`` frames only -- otherwise a fallen robot would collect "stood still"
    credit. A band with no frames inside the episode is not a pass: it is a run whose command
    schedule never covered the declared window. With a ``settle_s`` declared, only frames whose
    command has been in force that long are read at all -- see :func:`_settled` for why a band's first
    frames are not evidence about the policy.
    """
    command = frames["command_world"][:, :, 0]
    forward = frames["velocity_yaw"][:, :, 0]
    zero_band = float(params["zero_band_mps"])
    settled = _settled(command, dt, params)
    relative = torch.where(alive, (forward - command).abs() / command.clamp_min(params["floor_mps"]),
                           torch.ones_like(forward))
    masks, unclaimed = _band_masks(command, params)
    counts, readings, reasons = {}, {}, []
    for band, mask in masks:
        label = _band_label(band)
        inside = mask & alive if settled is None else mask & alive & settled
        counts[label] = int(inside.sum())
        if counts[label] == 0:
            reasons.append(f"{label} measured nothing")
            continue
        if band[0] < zero_band < band[1]:
            reasons.append(f"{label} straddles the zero-command boundary at {zero_band:g}")
            continue
        if band[1] <= zero_band:
            worst = float(_keep(forward.abs(), inside, 0.0).max())
            readings[label] = worst
            if settled is not None:
                # Reported beside the gated number: what the settle window removed. On the line's own
                # run the zero band read 2.622 m/s untrimmed and 0.213 m/s trimmed, so a reader who
                # wants the allowance moved has the margin in front of them.
                measured.setdefault("tracking_band_unsettled_max", {})[label] = \
                    float(_keep(forward.abs(), mask & alive, 0.0).max())
            if worst > params["zero_abs_mps"]:
                reasons.append(f"{label} moved at {worst:.3f} m/s with no command (limit "
                               f"{params['zero_abs_mps']})")
            continue
        mean_error = float(relative[mask if settled is None else mask & settled].mean())
        readings[label] = mean_error
        if not mean_error < params["threshold"]:
            reasons.append(f"{label} error {mean_error:.3f} is not below {params['threshold']}")
    measured["tracking_band_frames"] = counts
    measured["tracking_band_error"] = readings
    measured["tracking_unclaimed_frames"] = int(unclaimed.sum())
    if int(unclaimed.sum()):
        reasons.append(f"{int(unclaimed.sum())} frame(s) fall outside every declared band")
    measured["tracking_band_reasons"] = reasons
    return not reasons


def _gate_displacement_banded_v1(frames: dict, alive: torch.Tensor, dt: float, measured: dict,
                                 meta: dict, params: dict) -> bool:
    """Distance travelled per band, summed before dividing, with the zero band in absolute metres.

    The order is the criterion: the commanded distance keeps entering the denominator on frames after
    the episode ended (the command is still issued while the robot no longer moves), so a policy that
    stopped early is pulled down by its own denominator instead of having the rest of the window cut
    away. The numerator counts per-frame forward travel in the episode's initial-yaw frame -- an
    increment, not a position difference, so a respawn's jump cannot enter it. With a ``settle_s``
    declared, a band is read over the frames whose command has been in force that long: the numerator
    and the denominator drop the same frames, so the ratio stays a ratio and the braking distance a
    command step costs is charged to no band.
    """
    command = frames["command_world"][:, :, 0]
    zero_band = float(params["zero_band_mps"])
    # The collector hands meta through unchanged, so it may still be the live device tensor the episode
    # started from while the frames are already CPU copies. Bring it to the frames, the same way the
    # retired displacement kind does -- assuming a device is what broke this gate's first real run
    # ("Expected all tensors to be on the same device, but found at least two devices, cuda:0 and cpu").
    position = frames["pos"]
    device = position.device
    start = torch.as_tensor(meta["start_pos"]).to(device)
    yaw = torch.as_tensor(meta["start_yaw"]).to(device)
    heading = torch.stack([torch.cos(yaw), torch.sin(yaw), torch.zeros_like(yaw)], dim=-1)  # (N, 3)
    travel = torch.zeros_like(command)
    travel[0] = (position[0] - start).mul(heading).sum(dim=-1)
    travel[1:] = (position[1:] - position[:-1]).mul(heading).sum(dim=-1)
    masks, unclaimed = _band_masks(command, params)
    settled = _settled(command, dt, params)
    counts, readings, reasons = {}, {}, []
    for band, mask in masks:
        label = _band_label(band)
        inside = mask & alive if settled is None else mask & alive & settled
        counts[label] = int(inside.sum())
        if counts[label] == 0:
            reasons.append(f"{label} measured nothing")
            continue
        if band[0] < zero_band < band[1]:
            reasons.append(f"{label} straddles the zero-command boundary at {zero_band:g}")
            continue
        if band[1] <= zero_band:
            # Per env, then the worst env: the limit is metres, so the reading has to be metres. Summing
            # over every env as well multiplied the reading by however many envs the band covered, which
            # made the same policy read differently at 16 and 256 envs (the settled reader's first run
            # read +1.248 m = 0.083 m per env against a 0.3 m limit).
            per_env = travel.masked_fill(~inside, 0.0).sum(dim=0)
            net = float(per_env.sum()) if settled is None else float(per_env.abs().max())
            readings[label] = net
            if abs(net) > params["zero_abs_m"]:
                reasons.append(f"{label} drifted {net:+.3f} m with no command (limit "
                               f"{params['zero_abs_m']})")
            continue
        # Summed over the band's frames, then divided: the command of every frame in the band counts,
        # including the frames after the episode ended, which is what makes stopping early visible.
        samples = mask if settled is None else mask & settled
        commanded = float((command[samples] * dt).sum())
        actual = float(travel.masked_fill(~inside, 0.0).sum())
        ratio = actual / commanded if commanded > 0.0 else 0.0
        readings[label] = ratio
        if not ratio > params["threshold"]:
            reasons.append(f"{label} travelled {ratio:.3f} of the commanded distance, not above "
                           f"{params['threshold']}")
    measured["displacement_band_frames"] = counts
    measured["displacement_band_ratio"] = readings
    if int(unclaimed.sum()):
        reasons.append(f"{int(unclaimed.sum())} frame(s) fall outside every declared band")
    measured["displacement_band_reasons"] = reasons
    return not reasons


def _gate_non_foot_load_sum_v1(frames: dict, alive: torch.Tensor, dt: float, measured: dict,
                               meta: dict, params: dict) -> bool:
    """The SUM of every non-foot body's vertical load, aggregated before the dwell.

    ``non_foot_carrier_v1`` collapses the bodies with ``any`` before the dwell, so bodies taking
    turns under the fraction accumulate there; this one sums them first, which is what catches two
    bodies at 4% each carrying 8% of the weight between them. Both are pass conditions because they
    answer different questions, and neither is the other's approximation.
    """
    total = _keep(frames["non_foot_fraction"], alive, 0.0).sum(dim=-1)  # (T, N)
    breach = (total >= params["fraction_sum"]) & alive
    measured["non_foot_load_sum_max"] = float(total.max())
    return not bool(_sustained(breach, dt, params["sustain_s"]).any())


def _gate_gait_swing_v1(frames: dict, alive: torch.Tensor, dt: float, measured: dict, meta: dict,
                        params: dict) -> bool:
    """At least ``min_swing_feet`` feet complete a swing, on the frames the command asks to move.

    A swing is a run of frames in which that foot carries no load. It counts only if the run lasts
    ``min_air_time_s`` and the foot carries at least ``min_landing_load`` on the frame it comes back
    down on, so contact chatter cannot pass for a step -- ``feet_air_time`` alone is fooled by it.

    Judged per env, over the envs this window asked to move: four feet planted while standing is not
    a gait failure, so an env commanded below ``band_mps`` throughout is excluded (the zero-command
    bands of the tracking criteria are what judge it). A window that asked no env to move failed to
    measure a gait at all, which is not a pass.
    """
    command = frames["command_world"][:, :, 0]
    moving = (command >= params["band_mps"]) & alive  # (T, N)
    contact = frames["foot_contact"] > 0.0  # (T, N, F)
    swing = (~contact) & moving.unsqueeze(-1)
    runs = _run_lengths(swing.reshape(swing.shape[0], -1)).reshape(swing.shape) * dt
    landed = torch.zeros_like(swing)
    # the swing ended on a frame still asked to move (the foot-load half of the condition below)
    landed[1:] = swing[:-1] & moving[1:].unsqueeze(-1) & ~swing[1:]
    so_far = torch.zeros_like(runs)
    so_far[1:] = runs[:-1]  # the finished run's length, read on the landing frame
    completes = landed & (so_far >= params["min_air_time_s"]) & (frames["foot_fraction"] >= params["min_landing_load"])
    feet = completes.any(dim=0).sum(dim=-1)  # (N,) feet that completed a swing, per env
    requested = moving.any(dim=0)  # (N,) envs this window asked to move
    measured["gait_envs_request_swing_feet_mean"] = float(feet.to(torch.float32).mean())
    if not bool(requested.any()):
        return False
    measured["gait_swing_feet_least"] = int(feet[requested].min())
    return bool((feet[requested] >= params["min_swing_feet"]).all())


# --- the foot readings: one computation behind the report and the gates ---------------------------

def foot_clearance(frames: dict, meta: dict) -> tuple[torch.Tensor, str]:
    """``(T, N, F)`` each foot's lowest mesh point above the ground [m], and how the ground is known.

    Measured against the ground the record *names*, not against z=0 from memory: a plane is today's
    answer, and a record that says so is what lets a reader notice when it stops being true. A record
    carrying no ground source is read as z=0 and *says* it assumed so, instead of passing an
    assumption off as a measurement.
    """
    source = meta.get("ground_source")
    if isinstance(source, dict) and "z_m" in source:
        ground_z, how = float(source["z_m"]), f"declared ({source.get('kind', 'unknown')})"
    else:
        ground_z, how = 0.0, "assumed z=0: this record names no ground source"
    return frames["foot_lowest_point"][..., 2] - ground_z, how


def foot_point_velocity(frames: dict) -> torch.Tensor:
    """``(T, N, F, 3)`` velocity of each foot's contact candidate, world frame [m/s].

    At the lowest mesh point, not at the body: a loaded foot that is only rotating has a zero body
    velocity and a moving contact point, and reading the body's velocity would call that slip zero.
    The arithmetic is ``v_com + omega x (p - p_com)``, and it is the function the diagnoses already
    use (``diag_metrics.contact_point_velocity``) rather than a second copy of the cross product.
    """
    from rl_exp.tools.diagnose.diag_metrics import contact_point_velocity

    return contact_point_velocity(frames["foot_lin_vel"], frames["foot_ang_vel"],
                                  frames["foot_lowest_point"], frames["foot_com_pos"])


def foot_slip_speed(frames: dict, meta: dict) -> torch.Tensor:
    """``(T, N, F)`` tangential speed of that contact candidate relative to the ground [m/s].

    Tangential to the declared ground normal: a foot coming down towards the ground is not sliding
    along it, and a normal component in this reading would make every landing look like a slip.
    """
    velocity = foot_point_velocity(frames)
    source = meta.get("ground_source") or {}
    normal = torch.as_tensor(source.get("normal") or (0.0, 0.0, 1.0),
                             dtype=velocity.dtype, device=velocity.device)
    normal = normal / normal.norm().clamp_min(1e-9)
    along = (velocity * normal).sum(dim=-1, keepdim=True)
    return (velocity - along * normal).norm(dim=-1)


def _foot_readings(frames: dict, alive: torch.Tensor, meta: dict) -> dict:
    """The matrices both the report and the foot gates need, computed once.

    One computation, two consumers, so the number a reviewer reads is the number a verdict came from.
    A gate applies its own thresholds to these; the report reads them unthresholded.
    """
    clearance, ground_how = foot_clearance(frames, meta)
    return {
        "clearance_m": clearance,
        "slip_mps": foot_slip_speed(frames, meta),
        "ground_source": ground_how,
        "unloaded": (frames["foot_contact"] <= 0) & alive.unsqueeze(-1),
        "loaded": (frames["foot_contact"] > 0) & alive.unsqueeze(-1),
        "load_fraction": frames["foot_fraction"],
    }


def _gate_foot_lift_v1(frames: dict, alive: torch.Tensor, dt: float, measured: dict, meta: dict,
                       params: dict) -> bool:
    """Enough feet clear the ground by ``min_lift_m`` while unloaded, where the command asked to move.

    No swing-phase machine here on purpose: a frame counts when the foot is unloaded and a foot counts
    when its peak clearance over those frames reaches the threshold. "And it came back down" is
    ``gait_swing_v1``'s half of the pair rather than a second phase detector to keep in step with it.
    """
    clearance, ground_how = foot_clearance(frames, meta)
    unloaded = (frames["foot_contact"] <= 0) & alive.unsqueeze(-1)
    peak = torch.where(unloaded, clearance, torch.full_like(clearance, float("-inf"))).amax(dim=0)
    peak = torch.where(torch.isfinite(peak), peak, torch.zeros_like(peak))  # (N, F)
    moving = (frames["command_world"][:, :, 0].abs() >= params["band_mps"]) & alive
    requested = moving.any(dim=0)  # (N,) envs this window asked to move
    feet = (peak >= params["min_lift_m"]).sum(dim=-1)  # (N,) feet that lifted clear
    measured["foot_lift_ground_source"] = ground_how
    measured["foot_lift_peak_m"] = float(peak.amax())
    measured["foot_lift_envs_requested"] = int(requested.sum())
    if not bool(requested.any()):
        return False
    measured["foot_lift_feet_least"] = int(feet[requested].min())
    return bool((feet[requested] >= params["min_feet"]).all())


def _gate_foot_slip_v1(frames: dict, alive: torch.Tensor, dt: float, measured: dict, meta: dict,
                       params: dict) -> bool:
    """A loaded foot may slide tangentially for at most ``max_slip_fraction`` of its loaded frames.

    A share rather than a peak: the reading is "is this foot being dragged", and one frame at the
    moment of a stumble is not the same claim as a foot that slides the whole stance. The threshold
    this is compared against is a speed, the share is what tolerates the single frame.
    """
    slip = foot_slip_speed(frames, meta)
    loaded = (frames["foot_contact"] > 0) & alive.unsqueeze(-1) \
        & (frames["foot_fraction"] >= params["min_load"])
    breach = (slip > params["max_slip_mps"]) & loaded
    share = breach.sum(dim=0) / loaded.sum(dim=0).clamp_min(1)  # (N, F)
    carried = loaded.any(dim=0)  # (N, F) feet that took any load at all
    measured["foot_slip_fraction_worst"] = float(share[carried].max()) if bool(carried.any()) else 0.0
    measured["foot_slip_frames_loaded"] = int(loaded.sum())
    if not bool(carried.any()):
        return False
    return bool((share[carried] <= params["max_slip_fraction"]).all())


#: kind -> the function that decides it. One dispatch table, so a protocol names a criterion and the
#: judge has exactly one place to look it up.
CRITERIA = {
    "tracking_v1": _gate_tracking_v1,
    "displacement_v1": _gate_displacement_v1,
    "survival_v1": _gate_survival_v1,
    "sustained_tilt_v1": _gate_sustained_tilt_v1,
    "non_foot_contact_v1": _gate_non_foot_contact_v1,
    "non_foot_carrier_v1": _gate_non_foot_carrier_v1,
    "mesh_clearance_v1": _gate_mesh_clearance_v1,
    "tracking_banded_v1": _gate_tracking_banded_v1,
    "displacement_banded_v1": _gate_displacement_banded_v1,
    # One function each, two kinds: ``settle_s`` is what the kind may declare, and a kind that does not
    # declare it reaches the same code with no settling time, so the published banded reader keeps
    # reading exactly what it read before.
    "tracking_banded_settled_v1": _gate_tracking_banded_v1,
    "displacement_banded_settled_v1": _gate_displacement_banded_v1,
    "non_foot_load_sum_v1": _gate_non_foot_load_sum_v1,
    "gait_swing_v1": _gate_gait_swing_v1,
    "foot_lift_v1": _gate_foot_lift_v1,
    "foot_slip_v1": _gate_foot_slip_v1,
}


def _validate_params(gate: str, kind: str, params) -> tuple[dict, list[str]]:
    """The kind's parameters, or why they are not a criterion this judge can read."""
    if not isinstance(params, dict):
        return {}, [f"{gate} ({kind}): params must be an object, got {type(params).__name__}"]
    reasons = []
    unknown = sorted(set(params) - set(CRITERION_KINDS[kind]["params"]))
    if unknown:
        reasons.append(f"{gate} ({kind}) carries {unknown}, which the kind does not accept")
    missing = sorted(set(CRITERION_KINDS[kind]["params"]) - set(params))
    if missing:
        reasons.append(f"{gate} ({kind}) is missing {missing}")
    if reasons:
        return {}, reasons
    blanks = sorted(name for name, value in params.items() if value is None)
    if blanks:
        return {}, [f"{gate} ({kind}) leaves {blanks} unset: a criterion with a missing number is "
                    "not a weaker criterion, it is an unreadable one"]
    return dict(params), []


def _criteria_plan(protocol: dict) -> tuple[dict, list[str]]:
    """The declared ``criteria`` block as ``gate -> (kind, params)``, or why it cannot be read."""
    declared = protocol["criteria"]
    if not isinstance(declared, dict) or not declared:
        return {}, ["the criteria block is empty: a protocol that declares no gate decides nothing"]
    plan, reasons = {}, []
    for gate, spec in declared.items():
        if gate not in GATE_ORDER:
            reasons.append(f"the criteria block declares {gate}, which is not a known gate")
            continue
        if not isinstance(spec, dict) or set(spec) != {"kind", "params"}:
            spelled = sorted(spec) if isinstance(spec, dict) else type(spec).__name__
            reasons.append(f"{gate}: a criterion is {{kind, params}}, got {spelled}")
            continue
        kind = spec["kind"]
        if kind not in CRITERION_KINDS:
            reasons.append(f"{gate} declares kind {kind!r}, which this judge does not implement")
            continue
        params, param_reasons = _validate_params(gate, kind, spec["params"])
        reasons.extend(param_reasons)
        if not param_reasons:
            plan[gate] = (kind, params)
    reasons.extend(_judge_reasons(protocol, plan))
    return plan, reasons


def reader_id(protocol: dict) -> str:
    """Which reader a declared protocol names, or the first one by default.

    ``judge`` is a binding, not a label: a protocol that declares criteria no reader implements, or
    names a reader that does not cover the kinds it used, is refused rather than judged by whichever
    reader happens to be reached first. Naming no reader means the reader that read every protocol
    before the banded kinds existed -- v4 declares no ``judge`` and keeps its identity that way.
    """
    return str(protocol.get("judge") or JUDGE_ID)


def _judge_reasons(protocol: dict, plan: dict) -> list[str]:
    """Why the named reader cannot read this plan, or nothing."""
    reader = reader_id(protocol)
    if reader not in JUDGE_KINDS:
        return [f"the protocol names judge {reader!r}, which this module does not implement "
                f"({sorted(JUDGE_KINDS)})"]
    covered = set(JUDGE_KINDS[reader])
    uncovered = sorted({kind for kind, _ in plan.values()} - covered)
    if uncovered:
        return [f"judge {reader!r} does not cover {uncovered}: a kind is reachable only through a "
                "reader that lists it, so a new criterion needs a new id and not just a new name"]
    # A reader may declare which report items it produces (only the newest one does). Then a protocol
    # that asks to be *reported* on something nobody computes is refused here, instead of coming back
    # with a silently missing number -- which reads like a quantity that happened to be unremarkable.
    # Readers that declare nothing keep the behaviour they were published with: no retroactive
    # tightening, because a verdict already published must stay reproducible.
    produced = JUDGE_REPORTS.get(reader)
    if produced is not None:
        unknown = sorted(set(protocol.get("report_only", ())) - set(produced))
        if unknown:
            return [f"judge {reader!r} does not produce {unknown}: a declared report item has to be "
                    f"computed by somebody, or be removed from the list ({len(produced)} are produced)"]
    return []


#: Legacy threshold key -> the criterion it stands for, and the keys it consumes. Spelled out rather
#: than inferred from the key's name: a key this table does not know is refused, so a protocol that
#: quietly gains a gate keeps failing loudly instead of having the gate ignored.
_LEGACY_KEYS = {
    "forward_mae_norm_lt": "tracking",
    "forward_mae_mps_lt": "tracking",
    "displacement_frac_gt": "displacement",
    "forward_displacement_m_gt": "displacement",
    "first_episode_timeout_fraction_gt": "survival",
    "tilt_cos_min": "attitude",
    "tilt_sustain_s": "attitude",
    "non_foot_contact_load_n_gt": "no_non_foot_contact",
    "non_foot_load_fraction_lt": "no_non_foot_carrier",
    "non_foot_load_sustain_s": "no_non_foot_carrier",
    "non_foot_mesh_min_z_gt": "no_mesh_through_floor",
}


def _legacy_plan(protocol: dict) -> tuple[dict, list[str]]:
    """The threshold-key readings of ``v1``/``v2``/``v3`` as the criteria they always meant."""
    t = protocol["gates"]
    plan, reasons = {}, []

    def pick(gate: str, kind: str, alternatives: dict, companions: dict):
        spelled = {key: alternatives[key] for key in alternatives if key in t}
        if len(spelled) > 1:
            reasons.append(f"the thresholds name both {' and '.join(sorted(spelled))} for {gate}: "
                           "only one of them is the criterion")
            return
        if not spelled:
            return
        params = dict(next(iter(spelled.values())))
        for key, param in companions.items():
            if key not in t:
                reasons.append(f"{gate} names no {key}: the reading it gates cannot be measured "
                               "without it, and a missing threshold is not a weaker criterion")
                return
            params[param] = t[key]
        params, param_reasons = _validate_params(gate, kind, params)
        reasons.extend(param_reasons)
        if not param_reasons:
            plan[gate] = (kind, params)

    pick("tracking", "tracking_v1",
         {"forward_mae_norm_lt": {"threshold": t.get("forward_mae_norm_lt"), "normalized": True},
          "forward_mae_mps_lt": {"threshold": t.get("forward_mae_mps_lt"), "normalized": False}}, {})
    pick("displacement", "displacement_v1",
         {"displacement_frac_gt": {"threshold": t.get("displacement_frac_gt"), "normalized": True},
          "forward_displacement_m_gt": {"threshold": t.get("forward_displacement_m_gt"), "normalized": False}}, {})
    pick("survival", "survival_v1",
         {"first_episode_timeout_fraction_gt": {"threshold": t.get("first_episode_timeout_fraction_gt")}}, {})
    pick("attitude", "sustained_tilt_v1", {"tilt_cos_min": {"threshold_cos": t.get("tilt_cos_min")}},
         {"tilt_sustain_s": "sustain_s"})
    pick("no_non_foot_contact", "non_foot_contact_v1",
         {"non_foot_contact_load_n_gt": {"limit_n": t.get("non_foot_contact_load_n_gt"), "eps": 1e-9}}, {})
    pick("no_non_foot_carrier", "non_foot_carrier_v1",
         {"non_foot_load_fraction_lt": {"fraction": t.get("non_foot_load_fraction_lt")}},
         {"non_foot_load_sustain_s": "sustain_s"})
    pick("no_mesh_through_floor", "mesh_clearance_v1",
         {"non_foot_mesh_min_z_gt": {"threshold_m": t.get("non_foot_mesh_min_z_gt")}}, {})

    leftover = sorted(set(t) - set(_LEGACY_KEYS))
    if leftover:
        reasons.append(f"the protocol gates on {leftover}, which this reader has no criterion for")
    return plan, reasons


def judge_plan(protocol: dict) -> tuple[dict, str, list[str]]:
    """``(gate -> (kind, params), origin, reasons)`` -- how this protocol must be judged.

    ``origin`` is ``declared`` (the protocol names its criteria), ``legacy`` (it is one of the
    protocols allowed to arrive without them) or ``unresolved`` (neither -- refused, because judging
    it would mean guessing which criterion was meant).
    """
    if "criteria" in protocol:
        plan, reasons = _criteria_plan(protocol)
        return plan, "declared", reasons
    identity = (protocol.get("name"), protocol.get("version"))
    if identity not in LEGACY_PROTOCOLS:
        return {}, "unresolved", [
            f"{identity[0]!r} v{identity[1]} declares no criteria and is not one of the protocols "
            f"allowed to omit them ({[f'{n} v{v}' for n, v in LEGACY_PROTOCOLS]}): judging it would "
            "guess at the criterion"
        ]
    plan, reasons = _legacy_plan(protocol)
    return plan, "legacy", reasons


def _report_groups(*produced: dict) -> dict:
    """The produced numbers under the group their declaration names: measurement, task, behaviour.

    Derived from the declaration rather than hand-listed here, so a number cannot end up in a group
    nobody declared it for. A number with no declaration is simply not grouped -- it is still
    reported, and the completeness check is what refuses an undeclared one a protocol asks for.
    """
    groups: dict[str, list[str]] = {}
    for block in produced:
        for name in block:
            item = REPORT_ITEMS.get(name)
            if item is not None:
                groups.setdefault(item[0], []).append(name)
    return {group: sorted(names) for group, names in groups.items()}


def semantics_surface() -> dict:
    """What this judge's criteria can reach, for the frozen case table to pin by digest."""
    return CRITERION_KINDS


def judge_identity(protocol: dict) -> dict:
    """Which reader decided (or would decide) this protocol, and which protocol was read."""
    _, origin, _ = judge_plan(protocol)
    reader = {"declared": reader_id(protocol), "legacy": LEGACY_JUDGE_ID}.get(origin, "unresolved")
    return {
        "id": reader,
        "origin": origin,
        "protocol_name": protocol.get("name"),
        "protocol_version": protocol.get("version"),
    }


def gate_names(protocol: dict) -> list[str]:
    """The gates this protocol decides, in :data:`GATE_ORDER`; empty when it cannot be read."""
    plan, _, _ = judge_plan(protocol)
    return [gate for gate in GATE_ORDER if gate in plan]


def command_box(protocol: dict) -> list[tuple[float, float]]:
    """The command bounds the protocol declares, ``[(lo, hi)]`` for x, y and yaw rate.

    Two spellings, one reader. v1/v2 wrote a single fixed vector (``command_mps_radps``) because
    their recipes held the command constant; v3 writes a box (``command``) because v2's recipe
    samples 1-3 m/s on the framework's own resampling window. A record whose issued command leaves
    the declared box belongs to a different protocol and is refused instead of scored.
    """
    if "command" in protocol:
        spec = protocol["command"]
        keys = ("lin_vel_x", "lin_vel_y", "ang_vel_z")
        return [(float(spec[key][0]), float(spec[key][1])) for key in keys]
    fixed = [float(value) for value in protocol["command_mps_radps"]]
    return [(value, value) for value in fixed]


def _alive(terminated: torch.Tensor, timeout: torch.Tensor) -> torch.Tensor:
    """(T, N) bool: this frame is inside the env's FIRST episode.

    Frames after a respawn are not that env's episode: they belong to a new rollout whose initial
    state was not the one under test. The old window kept them in its per-body readings, which put
    respawned postures inside the mesh-through-floor gate.
    """
    ended = (terminated + timeout) > 0
    return (ended.cumsum(dim=0) - ended.to(torch.float32)) <= 0


def _keep(values: torch.Tensor, alive: torch.Tensor, fill: float) -> torch.Tensor:
    """``values`` (T, N, ...) with the frames outside the first episode replaced by ``fill``."""
    return values.masked_fill(~alive.reshape(alive.shape + (1,) * (values.dim() - 2)), fill)


def _run_lengths(condition: torch.Tensor) -> torch.Tensor:
    """Consecutive-true run length ending at each frame, same shape as ``condition`` (T, N)."""
    index = torch.arange(condition.shape[0]).reshape(-1, 1).expand_as(condition).to(torch.int64)
    last_false = torch.where(~condition, index, torch.full_like(index, -1)).cummax(dim=0).values
    return index - last_false


def _sustained(breach: torch.Tensor, dt: float, seconds: float) -> torch.Tensor:
    """Per env (N,): the breach held for at least ``seconds``."""
    return (_run_lengths(breach) * dt >= seconds).any(dim=0)


def _contract_reasons(artifact: dict) -> list[str]:
    """Why this record cannot be read at all (empty when it can)."""
    # The declaration comes from the format the record names. Reading it off the newest table in
    # ``baseline_frames`` instead would judge every older record by columns it never had.
    try:
        spec = baseline_frames.format_spec(artifact.get("format"))
    except baseline_frames.FramesContractError as err:
        return [str(err)]
    protocol, frames = artifact["protocol"], artifact["frames"]
    axes, meta = artifact.get("axes", {}), artifact.get("meta", {})
    steps, num_envs = meta.get("steps"), meta.get("num_envs")
    if not steps or not num_envs:
        return [f"the record does not say how large the window was: steps={steps}, num_envs={num_envs}"]
    missing = [name for name in spec["required_meta"] if name not in meta]
    if missing:
        return [f"the record is missing {missing}: frame 0 is already one step in, so the episode's "
                "initial state cannot be recovered from it"]
    step_dt = meta.get("step_dt")
    # The protocol is read before the record is measured: a criterion this judge cannot resolve
    # makes every number below unreadable, whatever shape they are in.
    plan, _, plan_reasons = judge_plan(protocol)
    reasons = list(plan_reasons)
    # The window's length is a property of the record AND of the protocol, and the verdict is only
    # meaningful where the two agree: 1000 frames of a 20 s protocol is a 20 s window, 1000 frames
    # of a 40 s protocol is half of one.
    if not step_dt:
        reasons.append(f"the record does not say what its control step was: step_dt={step_dt}")
    else:
        declared_s = float(protocol["episode_length_s"])
        if abs(steps * step_dt - declared_s) > 1e-6:
            reasons.append(f"the window is {steps} steps x {step_dt:g} s = {steps * step_dt:g} s, but the "
                           f"protocol declares {declared_s:g} s")
    for name in ("start_pos", "start_yaw"):
        value = torch.as_tensor(meta[name], dtype=torch.float32)
        want = (num_envs, 3) if name == "start_pos" else (num_envs,)
        if tuple(value.shape) != want:
            reasons.append(f"{name} has shape {tuple(value.shape)}, the contract says {want} "
                           "(one initial state per env)")
        elif not bool(torch.isfinite(value).all()):
            reasons.append(f"{name} is not finite")
    weight = meta.get("body_weight_n")
    if weight is None or not (float(weight) > 0.0):
        reasons.append(f"body_weight_n is {weight}: a per-body contact reading cannot be expressed in "
                       "newtons without it")
    for name in _BASE_COLUMNS:
        if name not in frames:
            reasons.append(f"the record has no {name}: it is not a baseline fixed-window record")
    for gate, (kind, _) in plan.items():
        for column in CRITERION_KINDS[kind]["columns"]:
            if column not in frames:
                reasons.append(f"the protocol gates {gate} through {kind}, which reads {column}, but the "
                               "record never measured it: unmeasured is unknown, and unknown is not a pass")
    if reasons:
        return reasons
    short = sorted(name for name in frames if len(frames[name]) != steps)
    if short:
        return [f"the window is incomplete: {len(frames[short[0]])} of {steps} frames were collected "
                f"({len(short)} of {len(frames)} columns are short)"]
    for name, tensor in frames.items():
        if name not in spec["columns"]:
            reasons.append(f"the record carries {name}, which the contract does not declare")
            continue
        kind, _, meaning = spec["columns"][name]
        labels = axes.get(name, [])
        if kind in spec["axis_kinds"] and not labels:
            reasons.append(f"{name} carries no axis labels: a per-body reading that cannot name its "
                           "bodies is not evidence")
            continue
        # The shape rule lives with the declaration, not here: the collector stores a frame against it
        # and this reads the stored column against it, so a kind added to one side is known to both.
        expected = (steps, *baseline_frames.expected_shape(kind, num_envs, len(labels)))
        if tuple(tensor.shape) != expected:
            reasons.append(f"{name} has shape {tuple(tensor.shape)}, the contract says {expected} "
                           f"({meaning}) with {len(labels)} axis labels")
    if reasons:
        return reasons
    return _command_reasons(protocol, frames)


def _command_reasons(protocol: dict, frames: dict) -> list[str]:
    """Refuse a record whose issued command is not inside the protocol's declared box.

    This is the guard against judging a rollout under the wrong protocol: the v1 drag record was
    collected with a constant 0.5 m/s command, and scoring it under a 1-3 m/s protocol would answer
    a question nobody asked.
    """
    box = command_box(protocol)
    command = frames["command_world"]
    labels = ("x", "y", "yaw rate")
    outside = []
    for index, (low, high) in enumerate(box):
        component = command[:, :, index]
        bad = (component < low - 1e-6) | (component > high + 1e-6)
        if bool(bad.any()):
            where = int(bad.nonzero()[0][0])
            outside.append(f"{labels[index]}: {component.reshape(-1).min().item():g}.."
                           f"{component.reshape(-1).max().item():g} outside [{low:g}, {high:g}] "
                           f"(first at frame {where})")
    if not outside:
        return []
    return [f"the issued command leaves the declared box ({'; '.join(outside)}): this record was "
            "collected under a different command protocol"]


def _data_reasons(artifact: dict, alive: torch.Tensor) -> list[str]:
    """Why these numbers cannot support a verdict (empty when they can)."""
    protocol, frames = artifact["protocol"], artifact["frames"]
    plan, _, _ = judge_plan(protocol)
    reasons = []
    read = [column for kind, _ in plan.values() for column in CRITERION_KINDS[kind]["columns"]]
    needed = list(_BASE_COLUMNS) + [name for name in read if name not in _BASE_COLUMNS]
    for name in needed:
        if name not in frames:
            reasons.append(f"the record does not carry {name}, which a declared criterion reads: a "
                           "quantity the run never measured cannot be judged, only reported")
            continue
        bad = int((~torch.isfinite(frames[name])).sum())
        if bad:
            reasons.append(f"{name} has {bad} non-finite values: a verdict needs finite measurements")
    empty = int((alive.sum(dim=0) == 0).sum())
    if empty:
        reasons.append(f"{empty} env(s) never contributed a frame inside their first episode")
    tracking = plan.get("tracking")
    # Only the absolute/fraction-of-command kind normalizes: the banded kind carries a floor_mps and a
    # zero-command band precisely so that a box including 0 m/s stays readable.
    if tracking is not None and tracking[0] == "tracking_v1" and tracking[1]["normalized"]:
        low = command_box(protocol)[0][0]
        if abs(low) < 1e-6:
            reasons.append("the declared command box includes 0 m/s, where a normalized tracking "
                           "error is undefined")
    return reasons


def _score(artifact: dict, alive: torch.Tensor) -> dict:
    """The gates, the metrics behind them, and the per-env evidence."""
    protocol, frames, axes = artifact["protocol"], artifact["frames"], artifact.get("axes", {})
    steps, dt = artifact["meta"]["steps"], artifact["meta"]["step_dt"]
    plan, _, _ = judge_plan(protocol)
    reporting = set(protocol.get("report_only", ()))
    valid = alive.sum(dim=0)
    coverage = valid.clamp_min(1)

    def episode_mean(values: torch.Tensor) -> torch.Tensor:
        """Per-env mean over the episode of a ``(T, N, ...)`` quantity -> ``(N, ...)``.

        Frames outside the first episode contribute nothing and are not counted either, so a
        quantity only ever averages the rollout under test.
        """
        width = (1,) * (values.dim() - 2)
        return _keep(values, alive, 0.0).sum(dim=0) / coverage.reshape((-1,) + width)

    # -- tracking, displacement and survival over the first episode ----------------
    # Exactly the reward kernel's comparison: world-frame commanded x against the yaw-frame forward
    # velocity (rl_exp.tasks.baseline_mdp.track_lin_vel_xy_miki), so the two are one quantity.
    command = frames["command_world"][:, :, 0]
    # Frames after the end are not tracking anything: they are charged the full command error, so
    # the window keeps scoring a policy that stopped early instead of losing those frames.
    error = torch.where(alive, (frames["velocity_yaw"][:, :, 0] - command).abs(), command.abs())
    forward_mae = error.sum(dim=0) / steps
    last = alive.to(torch.int64).cumsum(dim=0).argmax(dim=0)  # last frame inside the first episode
    env_ids = torch.arange(alive.shape[1])
    # Measured from the episode's initial state, which is why it travels in the record's meta. The
    # frames are CPU copies (the collector decides that); the meta may still be a live device
    # tensor, so it is moved to wherever the frames are instead of assuming either.
    device = frames["pos"].device
    delta = frames["pos"][last, env_ids] - torch.as_tensor(artifact["meta"]["start_pos"]).to(device)
    start_yaw = torch.as_tensor(artifact["meta"]["start_yaw"]).to(device)
    displacement = delta[:, 0] * start_yaw.cos() + delta[:, 1] * start_yaw.sin()
    survived = alive[-1] & (frames["timeout"][-1] > 0) & (frames["terminated"][-1] <= 0)

    measured = {
        "forward_mae_mps": forward_mae.mean().item(),
        "forward_displacement_m": displacement.mean().item(),
        "first_episode_timeout_fraction": survived.to(torch.float32).mean().item(),
        "command_mps_mean": episode_mean(command).mean().item(),
    }
    # Every gate the protocol declares, undecided until its ``decide`` call runs below. It starts
    # from the PLAN rather than empty because the verdict is ``all(passed.values())``: a declared gate
    # that no ``decide`` call reaches would otherwise be invisible to the verdict, which is the one
    # way a criterion can be written down and then not judged at all.
    passed: dict[str, bool | None] = {gate: None for gate in plan}

    def decide(gate: str) -> None:
        """The one place a verdict comes from: the gate's declared kind decides it."""
        kind, params = plan[gate]
        passed[gate] = CRITERIA[kind](frames, alive, dt, measured, artifact["meta"], params)

    # An absolute MAE asks "did it hold this number"; a normalized one asks "did it hold the band
    # it was given", which is the only question a 1-3 m/s task can answer. Frames after the end
    # score 1.0 -- standing still while commanded to move is the worst normalized error there is.
    tracking = plan.get("tracking")
    if tracking is not None and tracking[0] == "tracking_v1" and tracking[1]["normalized"]:
        norm_error = torch.where(alive, (frames["velocity_yaw"][:, :, 0] - command).abs()
                                 / command.clamp_min(1e-6), 1.0)
        measured["forward_mae_norm"] = (norm_error.sum(dim=0) / steps).mean().item()
    if "tracking" in plan:
        decide("tracking")
    # Same idea for distance: against what the issued commands asked for, over the whole declared
    # window -- a shorter denominator would forgive a policy that stopped after five seconds.
    expected_m = (command * dt).sum(dim=0)
    measured["expected_displacement_m"] = expected_m.mean().item()
    displacement_gate = plan.get("displacement")
    if displacement_gate is not None and displacement_gate[0] == "displacement_v1" \
            and displacement_gate[1]["normalized"]:
        measured["displacement_frac"] = (displacement / expected_m.clamp_min(1e-6)).mean().item()
    if "displacement" in plan:
        decide("displacement")
    if "survival" in plan:
        decide("survival")
    yaw_drift = torch.atan2(torch.sin(frames["yaw"] - start_yaw), torch.cos(frames["yaw"] - start_yaw)).abs()
    diagnostics = {
        "lateral_speed_abs_mps": episode_mean(frames["velocity_yaw"][:, :, 1].abs()).mean().item(),
        "yaw_offset_abs_rad": episode_mean(yaw_drift).mean().item(),
        "head_tail_contact_force_n": episode_mean(frames["head_tail_force"]).mean().item(),
        "first_episode_frame_fraction": (valid / steps).to(torch.float32).mean().item(),
    }

    # -- attitude: the WORST posture of the episode, and only while it is sustained --
    if "attitude" in plan or "tilt_max_deg" in reporting:
        worst_cos = _keep(frames["tilt_cos"], alive, float("inf")).min(dim=0).values
        measured["tilt_max_deg"] = worst_cos.clamp(-1.0, 1.0).acos().max().rad2deg().item()
        diagnostics["tilt_max_deg"] = measured["tilt_max_deg"]
    if "attitude" in plan:
        decide("attitude")

    # -- the foot readings: what the gait kind cannot see, reported whenever the format carries them --
    if "foot_lowest_point" in frames and "foot_com_pos" in frames:
        readings = _foot_readings(frames, alive, artifact["meta"])
        clearance, slip = readings["clearance_m"], readings["slip_mps"]
        unloaded, loaded = readings["unloaded"], readings["loaded"]
        peak = torch.where(unloaded, clearance, torch.full_like(clearance, float("-inf"))).amax(dim=0)
        peak = torch.where(torch.isfinite(peak), peak, torch.zeros_like(peak))
        diagnostics["foot_clearance_swing_m"] = peak.mean(dim=0).tolist()
        diagnostics["foot_slip_mps"] = (
            slip.masked_fill(~loaded, 0.0).sum(dim=0) / loaded.sum(dim=0).clamp_min(1)
        ).mean(dim=0).tolist()
        # Each reading next to its own sample count: a mean over three frames and a mean over three
        # thousand are not the same evidence, and a bare number cannot say which one it is.
        diagnostics["foot_swing_frames"] = unloaded.sum(dim=(0, 1)).tolist()
        diagnostics["foot_loaded_frames"] = loaded.sum(dim=(0, 1)).tolist()
        diagnostics["foot_ground_source"] = readings["ground_source"]
    if "foot_lift" in plan:
        decide("foot_lift")
    if "foot_slip" in plan:
        decide("foot_slip")

    # -- per-body readings: always reported, gated only where the protocol says so ---
    # The record carries these whatever the protocol does with them, so a protocol that only
    # reports them (v3 does that for the mesh) still produces the reading rather than a blank.
    if "non_foot_fraction" in frames:
        fractions = frames["non_foot_fraction"]
        weight_n = float(artifact["meta"]["body_weight_n"])
        load_n = _keep(fractions, alive, 0.0) * weight_n
        peak_fraction = _keep(fractions, alive, 0.0).amax(dim=(0, 1))
        measured["non_foot_load_fraction_max"] = peak_fraction.max().item()
        measured["non_foot_contact_load_n_max"] = load_n.amax().item()
        diagnostics["non_foot_load_fraction"] = peak_fraction.tolist()
        diagnostics["non_foot_contact_load_n"] = load_n.amax(dim=(0, 1)).tolist()

        # v3: contact is the criterion, because it is the training termination's criterion -- one
        # frame above the limit is already a body using the ground as support.
        if "no_non_foot_contact" in plan:
            decide("no_non_foot_contact")
            # Per body, summed over envs and the window: "how much of this rollout was this body
            # using the ground for", which is the next thing a reviewer asks when the gate trips.
            breach = _non_foot_contact_breach(frames, alive, artifact["meta"], plan["no_non_foot_contact"][1])
            diagnostics["non_foot_contact_frames"] = breach.sum(dim=(0, 1)).tolist()
        # v1/v2: the same reading, gated as weight-bearing sustained for a dwell.
        if "no_non_foot_carrier" in plan:
            decide("no_non_foot_carrier")
        # Summed over the non-foot bodies before the dwell: the same recording, the other question.
        if "no_non_foot_load_sum" in plan:
            decide("no_non_foot_load_sum")
        # A gait, on the frames the command asked to move.
        if "gait" in plan:
            decide("gait")

    if "mesh_min_z" in frames:
        clearance = _keep(frames["mesh_min_z"], alive, float("inf")).amin(dim=0)  # (N, B)
        measured["non_foot_mesh_min_z_m"] = clearance.min().item()
        diagnostics["non_foot_mesh_min_z_m"] = clearance.amin(dim=0).tolist()
        if "no_mesh_through_floor" in plan:
            decide("no_mesh_through_floor")

    # -- per-foot readings are diagnostics: a gait is described, not gated, here ----
    if "foot_contact" in frames:
        diagnostics["foot_duty"] = episode_mean(frames["foot_contact"]).mean(dim=0).tolist()
        # Feet down per frame, averaged over the episode. The old window divided the per-frame
        # count by the frame count again, reading 0.05 where the answer is 1.0.
        diagnostics["feet_down_mean"] = episode_mean(frames["foot_contact"].sum(dim=-1)).mean().item()
    if "foot_fraction" in frames:
        diagnostics["foot_load_fraction"] = episode_mean(frames["foot_fraction"]).mean(dim=0).tolist()

    # A declared criterion that no ``decide`` call reached is not a pass and not a policy failure: the
    # declaration and the reader disagree, so the record cannot be judged at all.
    undecided = sorted(gate for gate, value in passed.items() if value is None)
    return {
        "verdict": "invalid" if undecided else ("pass" if all(passed.values()) else "fail"),
        "invalid_reasons": [] if not undecided else [
            f"the protocol declares {undecided}, which this reader never decides: a criterion that is "
            "written down but not judged would read as a pass"],
        "metrics": measured,
        "gates": passed,
        "diagnostics": diagnostics,
        "report_groups": _report_groups(measured, diagnostics),
        "per_env": {
            "forward_mae_mps": forward_mae.tolist(),
            "forward_displacement_m": displacement.tolist(),
            "survived": survived.tolist(),
            "valid_steps": valid.tolist(),
        },
        "axes": axes,
    }


def judge(artifact: dict) -> dict:
    """Score one baseline record; a record that cannot carry a verdict comes back ``invalid``.

    Args:
        artifact: what :meth:`ablation_harness.baseline_frames.BaselineFrames.artifact` returns --
            frames, their axis labels, the protocol, and the run's meta.
    Returns:
        ``verdict`` (``invalid`` / ``fail`` / ``pass``), ``invalid_reasons``, ``gates`` (``None``
        where unjudged), ``metrics``, ``diagnostics``, the per-env evidence and ``judge`` -- the
        identity of the reader that decided, so a re-judged record says *who* re-judged it.
    """
    protocol = artifact["protocol"]
    names = gate_names(protocol)
    identity = judge_identity(protocol)
    reasons = _contract_reasons(artifact)
    alive = None
    if not reasons:
        frames = artifact["frames"]
        alive = _alive(frames["terminated"], frames["timeout"])
        reasons = _data_reasons(artifact, alive)
    if reasons:
        return {
            "verdict": "invalid",
            "invalid_reasons": reasons,
            "judge": identity,
            "gates": {name: None for name in names},
            "metrics": {},
            "diagnostics": {},
            "per_env": {},
            "axes": artifact.get("axes", {}),
        }
    return {**_score(artifact, alive), "judge": identity}


def main() -> None:
    """Re-judge a saved record without re-running physics.

    The output names the judge and the protocol file it read. Re-judging is the one operation whose
    whole point is that the criterion may differ from the run's own, so a verdict that did not say
    which criterion produced it would be a number nobody could attribute.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=pathlib.Path, help="a baseline_frames record (.pt)")
    parser.add_argument("--protocol", type=pathlib.Path,
                        help="judge under this protocol instead of the one the run was collected with")
    args = parser.parse_args()
    artifact = baseline_frames.load(args.record)
    if args.protocol:
        artifact["protocol"] = json.loads(args.protocol.read_text(encoding="utf-8"))
    result = judge(artifact)
    payload = {key: value for key, value in result.items() if key != "axes"}
    payload["protocol_file"] = str(args.protocol) if args.protocol else "embedded in the record"
    payload["protocol_digest"] = record.file_sha256(args.protocol) if args.protocol else None
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
