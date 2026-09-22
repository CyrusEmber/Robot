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
    "no_mesh_through_floor",
)

#: The identity of the criteria reader. Declared rather than derived from a file hash: a comment is
#: not a semantic change, and a semantic change is exactly what this must make loud.
#: ``rl_exp/tools/verify/check_judge_semantics.py`` freezes ``id -> kinds -> cases -> expectations``
#: and refuses an in-place edit to a published id, so a changed criterion needs a new kind and a new
#: id instead of an edit here.
JUDGE_ID = "baseline-criteria-1"

#: The identity of the pre-criteria reader. Spelled by mechanism, not by version: ``v1``/``v2``/``v3``
#: are three declarations read by *one* implementation, and this names that implementation. Their
#: protocol identity travels next to it, so "which thresholds" and "which reader" stay separable.
LEGACY_JUDGE_ID = "legacy-baseline-threshold-keys-1"

#: Protocols allowed to arrive without a ``criteria`` block, by declared identity (not by filename).
LEGACY_PROTOCOLS = (("Baseline-Flat-v1", 1), ("Baseline-Flat-v2", 2), ("Baseline-Flat-v3", 3))

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
    return plan, reasons


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


def semantics_surface() -> dict:
    """What this judge's criteria can reach, for the frozen case table to pin by digest."""
    return CRITERION_KINDS


def judge_identity(protocol: dict) -> dict:
    """Which reader decided (or would decide) this protocol, and which protocol was read."""
    _, origin, _ = judge_plan(protocol)
    reader = {"declared": JUDGE_ID, "legacy": LEGACY_JUDGE_ID}.get(origin, "unresolved")
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
    plan, _, _ = judge_plan(protocol)
    reasons = []
    read = [column for kind, _ in plan.values() for column in CRITERION_KINDS[kind]["columns"]]
    needed = list(_BASE_COLUMNS) + [name for name in read if name not in _BASE_COLUMNS]
    for name in needed:
        bad = int((~torch.isfinite(frames[name])).sum())
        if bad:
            reasons.append(f"{name} has {bad} non-finite values: a verdict needs finite measurements")
    empty = int((alive.sum(dim=0) == 0).sum())
    if empty:
        reasons.append(f"{empty} env(s) never contributed a frame inside their first episode")
    tracking = plan.get("tracking")
    if tracking is not None and tracking[1]["normalized"]:
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
    passed: dict[str, bool] = {}

    def decide(gate: str) -> None:
        """The one place a verdict comes from: the gate's declared kind decides it."""
        kind, params = plan[gate]
        passed[gate] = CRITERIA[kind](frames, alive, dt, measured, artifact["meta"], params)

    # An absolute MAE asks "did it hold this number"; a normalized one asks "did it hold the band
    # it was given", which is the only question a 1-3 m/s task can answer. Frames after the end
    # score 1.0 -- standing still while commanded to move is the worst normalized error there is.
    tracking = plan.get("tracking")
    if tracking is not None and tracking[1]["normalized"]:
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
    if displacement_gate is not None and displacement_gate[1]["normalized"]:
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
