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

A gate exists only when its threshold key is in the protocol, and then the column it reads is
required: a protocol may not gate on a quantity the run never measured. That refusal is why the
old single-file window could report 0 deg of tilt for a run that never measured tilt.
"""

from __future__ import annotations

import argparse
import json
import pathlib

import torch

from ablation_harness import baseline_frames

_BASE_COLUMNS = ("pos", "yaw", "velocity_yaw", "command_world", "terminated", "timeout")

# The three gates the protocol names thresholds for by itself.
_BASE_GATES = ("tracking", "displacement", "survival")

# gate -> (column, threshold key, sustain key or None, "min" or "max")
# ``min``: the metric must stay at or above the threshold, so a breach is being below it.
#
# Two head-chain axes are declared here because the protocol family has two generations: v1/v2 gate
# a *weight-bearing* reading (a fraction of body weight held for a dwell), v3 gates *contact* (above
# 1 N on any frame), which is the criterion v2's training termination uses. A protocol declaring one
# gets that gate; a protocol declaring both would get both, which is a deliberate possibility, not an
# accident. The mesh-clearance gate exists for the same reason: v2 declared it, v3 reports it only.
_GATED = {
    "attitude": ("tilt_cos", "tilt_cos_min", "tilt_sustain_s", "min"),
    "no_non_foot_carrier": ("non_foot_fraction", "non_foot_load_fraction_lt", "non_foot_load_sustain_s", "max"),
    "no_non_foot_contact": ("non_foot_fraction", "non_foot_contact_load_n_gt", None, "max"),
    "no_mesh_through_floor": ("mesh_min_z", "non_foot_mesh_min_z_gt", None, "min"),
}


def gate_names(protocol: dict) -> list[str]:
    """The gates this protocol decides: the base three plus every gated column it names."""
    return list(_BASE_GATES) + [
        name for name, (_, key, _, _) in _GATED.items() if key in protocol["gates"]
    ]


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
    protocol, frames = artifact["protocol"], artifact["frames"]
    axes, meta = artifact.get("axes", {}), artifact.get("meta", {})
    steps, num_envs = meta.get("steps"), meta.get("num_envs")
    if not steps or not num_envs:
        return [f"the record does not say how large the window was: steps={steps}, num_envs={num_envs}"]
    missing = [name for name in baseline_frames.REQUIRED_META if name not in meta]
    if missing:
        return [f"the record is missing {missing}: frame 0 is already one step in, so the episode's "
                "initial state cannot be recovered from it"]
    step_dt = meta.get("step_dt")
    reasons = []
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
    for gate, (column, key, _, _) in _GATED.items():
        if key in protocol["gates"] and column not in frames:
            reasons.append(f"the protocol gates {gate} on {column}, but the record never measured it: "
                           "unmeasured is unknown, and unknown is not a pass")
    if reasons:
        return reasons
    short = sorted(name for name in frames if len(frames[name]) != steps)
    if short:
        return [f"the window is incomplete: {len(frames[short[0]])} of {steps} frames were collected "
                f"({len(short)} of {len(frames)} columns are short)"]
    for name, tensor in frames.items():
        if name not in baseline_frames.COLUMNS:
            reasons.append(f"the record carries {name}, which the contract does not declare")
            continue
        kind, _, meaning = baseline_frames.COLUMNS[name]
        expected = {"env": (steps, num_envs), "vec3": (steps, num_envs, 3)}.get(kind)
        if expected is None:
            labels = axes.get(name, [])
            if not labels:
                reasons.append(f"{name} carries no axis labels: a per-body reading that cannot name its "
                               "bodies is not evidence")
                continue
            if len(labels) != tensor.shape[-1]:
                reasons.append(f"{name} has {tensor.shape[-1]} values per frame but {len(labels)} axis labels")
                continue
            expected = (steps, num_envs, len(labels))
        if tuple(tensor.shape) != expected:
            reasons.append(f"{name} has shape {tuple(tensor.shape)}, the contract says {expected} ({meaning})")
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
    reasons = []
    needed = list(_BASE_COLUMNS) + [col for col, key, _, _ in _GATED.values() if key in protocol["gates"]]
    for name in needed:
        bad = int((~torch.isfinite(frames[name])).sum())
        if bad:
            reasons.append(f"{name} has {bad} non-finite values: a verdict needs finite measurements")
    empty = int((alive.sum(dim=0) == 0).sum())
    if empty:
        reasons.append(f"{empty} env(s) never contributed a frame inside their first episode")
    if "forward_mae_norm_lt" in protocol["gates"]:
        low = command_box(protocol)[0][0]
        if abs(low) < 1e-6:
            reasons.append("the declared command box includes 0 m/s, where a normalized tracking "
                           "error is undefined")
    return reasons


def _score(artifact: dict, alive: torch.Tensor) -> dict:
    """The gates, the metrics behind them, and the per-env evidence."""
    protocol, frames, axes = artifact["protocol"], artifact["frames"], artifact.get("axes", {})
    steps, dt = artifact["meta"]["steps"], artifact["meta"]["step_dt"]
    thresholds = protocol["gates"]
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
    # An absolute MAE asks "did it hold this number"; a normalized one asks "did it hold the band
    # it was given", which is the only question a 1-3 m/s task can answer. Frames after the end
    # score 1.0 -- standing still while commanded to move is the worst normalized error there is.
    if "forward_mae_norm_lt" in thresholds:
        norm_error = torch.where(alive, (frames["velocity_yaw"][:, :, 0] - command).abs()
                                 / command.clamp_min(1e-6), 1.0)
        measured["forward_mae_norm"] = (norm_error.sum(dim=0) / steps).mean().item()
        passed = {"tracking": measured["forward_mae_norm"] < thresholds["forward_mae_norm_lt"]}
    else:
        passed = {"tracking": measured["forward_mae_mps"] < thresholds["forward_mae_mps_lt"]}
    # Same idea for distance: against what the issued commands asked for, over the whole declared
    # window -- a shorter denominator would forgive a policy that stopped after five seconds.
    expected_m = (command * dt).sum(dim=0)
    measured["expected_displacement_m"] = expected_m.mean().item()
    if "displacement_frac_gt" in thresholds:
        measured["displacement_frac"] = (displacement / expected_m.clamp_min(1e-6)).mean().item()
        passed["displacement"] = measured["displacement_frac"] > thresholds["displacement_frac_gt"]
    else:
        passed["displacement"] = measured["forward_displacement_m"] > thresholds["forward_displacement_m_gt"]
    passed["survival"] = (measured["first_episode_timeout_fraction"]
                          > thresholds["first_episode_timeout_fraction_gt"])
    yaw_drift = torch.atan2(torch.sin(frames["yaw"] - start_yaw), torch.cos(frames["yaw"] - start_yaw)).abs()
    diagnostics = {
        "lateral_speed_abs_mps": episode_mean(frames["velocity_yaw"][:, :, 1].abs()).mean().item(),
        "yaw_offset_abs_rad": episode_mean(yaw_drift).mean().item(),
        "head_tail_contact_force_n": episode_mean(frames["head_tail_force"]).mean().item(),
        "first_episode_frame_fraction": (valid / steps).to(torch.float32).mean().item(),
    }

    # -- attitude: the WORST posture of the episode, and only while it is sustained --
    if "tilt_cos_min" in thresholds:
        worst_cos = _keep(frames["tilt_cos"], alive, float("inf")).min(dim=0).values
        measured["tilt_max_deg"] = worst_cos.clamp(-1.0, 1.0).acos().max().rad2deg().item()
        diagnostics["tilt_max_deg"] = measured["tilt_max_deg"]
        breach = (frames["tilt_cos"] < thresholds["tilt_cos_min"]) & alive
        passed["attitude"] = not bool(_sustained(breach, dt, thresholds["tilt_sustain_s"]).any())

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
        if "non_foot_contact_load_n_gt" in thresholds:
            limit = thresholds["non_foot_contact_load_n_gt"] / weight_n  # the column is a fraction
            breach = (fractions > limit + 1e-9) & alive.unsqueeze(-1)
            passed["no_non_foot_contact"] = not bool(breach.any())
            # Per body, summed over envs and the window: "how much of this rollout was this body
            # using the ground for", which is the next thing a reviewer asks when the gate trips.
            diagnostics["non_foot_contact_frames"] = breach.sum(dim=(0, 1)).tolist()
        # v1/v2: the same reading, gated as weight-bearing sustained for a dwell.
        if "non_foot_load_fraction_lt" in thresholds:
            breach = (fractions >= thresholds["non_foot_load_fraction_lt"]).any(dim=-1) & alive
            passed["no_non_foot_carrier"] = not bool(
                _sustained(breach, dt, thresholds["non_foot_load_sustain_s"]).any())

    if "mesh_min_z" in frames:
        clearance = _keep(frames["mesh_min_z"], alive, float("inf")).amin(dim=0)  # (N, B)
        measured["non_foot_mesh_min_z_m"] = clearance.min().item()
        diagnostics["non_foot_mesh_min_z_m"] = clearance.amin(dim=0).tolist()
        if "non_foot_mesh_min_z_gt" in thresholds:
            passed["no_mesh_through_floor"] = bool((clearance > thresholds["non_foot_mesh_min_z_gt"]).all())

    # -- per-foot readings are diagnostics: a gait is described, not gated, here ----
    if "foot_contact" in frames:
        diagnostics["foot_duty"] = episode_mean(frames["foot_contact"]).mean(dim=0).tolist()
        # Feet down per frame, averaged over the episode. The old window divided the per-frame
        # count by the frame count again, reading 0.05 where the answer is 1.0.
        diagnostics["feet_down_mean"] = episode_mean(frames["foot_contact"].sum(dim=-1)).mean().item()
    if "foot_fraction" in frames:
        diagnostics["foot_load_fraction"] = episode_mean(frames["foot_fraction"]).mean(dim=0).tolist()

    return {
        "verdict": "pass" if all(passed.values()) else "fail",
        "invalid_reasons": [],
        "metrics": measured,
        "gates": passed,
        "diagnostics": diagnostics,
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
        where unjudged), ``metrics``, ``diagnostics`` and the per-env evidence.
    """
    names = gate_names(artifact["protocol"])
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
            "gates": {name: None for name in names},
            "metrics": {},
            "diagnostics": {},
            "per_env": {},
            "axes": artifact.get("axes", {}),
        }
    return _score(artifact, alive)


def main() -> None:
    """Re-judge a saved record without re-running physics."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=pathlib.Path, help="a baseline_frames record (.pt)")
    parser.add_argument("--protocol", type=pathlib.Path,
                        help="judge under this protocol instead of the one the run was collected with")
    args = parser.parse_args()
    artifact = baseline_frames.load(args.record)
    if args.protocol:
        artifact["protocol"] = json.loads(args.protocol.read_text(encoding="utf-8"))
    result = judge(artifact)
    print(json.dumps({key: value for key, value in result.items() if key != "axes"}, indent=2,
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
