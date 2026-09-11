# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""True-resume state for the lizard teacher curriculum: joint SIR + the c_k clock.

Checkpoint resume today restores only actor/critic/optimizer/iteration (rsl_rl
``OnPolicyRunner``), so a resumed run re-heats ``c_k`` from ``c0`` and
cold-starts the joint SIR particle filter -- the documented "resume = re-heat
from scratch" incident (``versions/lizard/v3/NOTES.md``), which makes a resumed
reward curve a new run rather than a continuation. This module closes that gap:

* :func:`collect` snapshots ``common_step_counter`` (the c_k clock AND the SIR
  eval throttle's reference) plus the whole :class:`JointSIRTerrainCurriculum`
  runtime state, keyed by a static fingerprint of everything the term derives
  from cfg/terrain. A yaml edit that renumbers particles or re-splits terrain
  columns aborts the restore instead of silently reinterpreting pair indices.
* :func:`apply_resume_state` runs BEFORE the wrapper's first full reset
  (train.py, between ``gym.make`` and ``RslRlVecEnvWrapper``): the term's
  respawn at that reset consumes the restored particles, so terrain slots,
  ``desired_vel``, spawn origins and the c_k-scaled reset DR are consistent
  from episode 0.
* :func:`hook_runner_save` wraps ``OnPolicyRunner.save`` so the state rides the
  checkpoint's ``infos`` slot (single file, no sidecar to desynchronize).

Not saved (per-episode transients, re-rolled at the next reset): the command
term's ``_nu_sum``/``_step_count``, the ring-noise state, foot-friction dips,
``episode_length_buf``. Not saved (the term's own respawn rewrites them):
``terrain_levels``/``terrain_types``/``env_origins``. No RNG states: resume is
statistically continuous, deliberately NOT bit-identical (user decision
2026-09-11) -- particle draws after the restore differ while the distributions,
counters and the c_k clock carry over.

ponytail: hardcoded to the one stateful curriculum term of the v11/v12 line
(``JOINT_SIR_TERM``). A second stateful term would need its own collect/apply;
``_other_stateful_terms`` is the tripwire that says so out loud instead of
silently cold-starting it.
"""

from __future__ import annotations

import functools
import os

import torch
from isaaclab.managers import ManagerTermBase

from rl_exp.tasks.teacher_mdp import JOINT_SIR_TERM, JointSIRTerrainCurriculum, ck_value

STATE_KEY = "lizard_curriculum_state"
"""Key under ``checkpoint["infos"]`` carrying the curriculum state."""

STATE_VERSION = 1
"""Payload schema version; bump when the field set changes shape."""

_CFG_KEYS = (
    "command_name",
    "band",
    "velocity_buckets",
    "particles_per_type",
    "eval_every",
    "n_traj_min",
    "p_transition",
    "p_replay",
    "maintain_mass",
    "steps_per_iteration",
)

_SIZE_WARN_BYTES = 64 * 2**20
"""Checkpoint state size beyond which the unbounded history pool gets called out."""


def _unwrap(env):
    """Accept the raw env or any gym/rsl_rl wrapper around it."""
    return getattr(env, "unwrapped", env)


def _active_term(env):
    """The live :class:`JointSIRTerrainCurriculum` instance, or None.

    ``ManagerBase`` replaces a class term's ``cfg.func`` with the instance at
    build time, which is the same handle :class:`ParticleVelocityCommand` reads
    (``sir_cfg.func.desired_vel``). ``cfg.<term> is None`` means the term is not
    wired (PLAY variants, other tasks).
    """
    manager = getattr(env, "curriculum_manager", None)
    if manager is None:
        return None
    cfg = getattr(manager.cfg, JOINT_SIR_TERM, None)
    if cfg is None:
        return None
    term = getattr(cfg, "func", None)
    if isinstance(term, JointSIRTerrainCurriculum):
        return term
    raise RuntimeError(
        f"curriculum term {JOINT_SIR_TERM!r} is wired but cfg.func is {type(term).__name__}, not an"
        " instantiated JointSIRTerrainCurriculum -- collect/restore would silently no-op"
    )


def _other_stateful_terms(env) -> list[str]:
    """Wired curriculum terms with runtime state that this module does not cover."""
    manager = getattr(env, "curriculum_manager", None)
    if manager is None:
        return []
    out = []
    for name in vars(manager.cfg):
        func = getattr(getattr(manager.cfg, name), "func", None)
        if isinstance(func, ManagerTermBase) and not isinstance(func, JointSIRTerrainCurriculum):
            out.append(name)
    return sorted(out)


def _tensor_eq(a, b) -> bool:
    """Deep equality over the nested list/dict/tensor shapes of the payload."""
    if isinstance(b, torch.Tensor):
        return isinstance(a, torch.Tensor) and torch.equal(a.detach().cpu(), b.detach().cpu())
    if isinstance(b, (list, tuple)):
        return isinstance(a, (list, tuple)) and len(a) == len(b) and all(_tensor_eq(x, y) for x, y in zip(a, b))
    if isinstance(b, dict):
        return isinstance(a, dict) and a.keys() == b.keys() and all(_tensor_eq(a[k], b[k]) for k in b)
    return a == b


def _tensor_bytes(obj) -> int:
    """Tensor payload size [bytes] (scalars and strings excluded)."""
    if isinstance(obj, torch.Tensor):
        return obj.numel() * obj.element_size()
    if isinstance(obj, dict):
        return sum(_tensor_bytes(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return sum(_tensor_bytes(v) for v in obj)
    return 0


def _static_state(term: JointSIRTerrainCurriculum) -> dict:
    """Everything the term derives from cfg/terrain (the restore's guard).

    A ``rl_exp/*.yaml`` edit that changes the terrain grid re-splits columns and
    renumbers pairs while leaving counts like ``n_pairs`` possibly intact; pair
    indices from the old checkpoint would then name different sub-terrains and
    every downstream number would look plausible. Comparing this snapshot
    key-by-key turns that into a startup error.
    """
    return {
        "types": list(term._types),
        "num_rows": int(term._num_rows),
        "n_levels": [list(v) for v in term._n_levels],
        "n_pairs": list(term._n_pairs),
        "n_v": int(term._n_v),
        "velocity": term._velocity.detach().cpu().clone(),
        "combo_cols": [[c.detach().cpu().clone() for c in cols] for cols in term._combo_cols],
        "cfg": {k: getattr(term.cfg, k) for k in _CFG_KEYS},
    }


def collect(env, it: int | None = None) -> dict | None:
    """Snapshot the curriculum state, or None when the task wires no joint SIR.

    Args:
        env: The environment (raw or wrapped).
        it: The runner's current learning iteration, for diagnostics only.

    Returns:
        The payload to store under ``infos[STATE_KEY]``, or None for tasks
        without the joint SIR term (other robots, PLAY variants).
    """
    env = _unwrap(env)
    term = _active_term(env)
    if term is None:
        return None
    return {
        "version": STATE_VERSION,
        "written_at_iter": None if it is None else int(it),
        "task": type(getattr(env, "cfg", None)).__name__,
        "num_envs": int(env.num_envs),
        "common_step_counter": int(env.common_step_counter),
        "static": _static_state(term),
        "runtime": {
            "particles": [t.detach().cpu().clone() for t in term._particles],
            "weights": [t.detach().cpu().clone() for t in term._weights],
            "episodes": [t.detach().cpu().clone() for t in term._episodes],
            "in_band": [t.detach().cpu().clone() for t in term._in_band],
            "tr_sum": [t.detach().cpu().clone() for t in term._tr_sum],
            "history": [t.detach().cpu().clone() for t in term._history],
            "env_pair": term._env_pair.detach().cpu().clone(),
            "desired_vel": term.desired_vel.detach().cpu().clone(),
            "env_type": term._env_type.detach().cpu().clone(),
            "next_eval_step": int(term._next_eval_step),
            "tr_block_sum": float(term._tr_block_sum),
            "tr_block_count": int(term._tr_block_count),
            "last_tr_mean": float(term._last_tr_mean),
        },
    }


def _validate(state: dict, env, term: JointSIRTerrainCurriculum) -> None:
    """Raise ValueError when the payload cannot be interpreted by the live term."""
    problems: list[str] = []
    if state.get("version") != STATE_VERSION:
        problems.append(f"schema version {state.get('version')!r} != {STATE_VERSION}")
    if state.get("num_envs") != int(getattr(env, "num_envs", -1)):
        problems.append(f"num_envs {state.get('num_envs')} -> {getattr(env, 'num_envs', None)}")
    task_now = type(getattr(env, "cfg", None)).__name__
    if state.get("task") != task_now:
        problems.append(f"task {state.get('task')} -> {task_now}")

    saved = state.get("static", {})
    now = _static_state(term)
    for key, current in now.items():
        if not _tensor_eq(saved.get(key), current):
            problems.append(f"static.{key}")

    rt = state.get("runtime", {})
    n_part = int(term.cfg.particles_per_type)
    for ti, n_pairs in enumerate(term._n_pairs):
        for key in ("particles", "weights", "episodes", "in_band", "tr_sum", "history"):
            got = rt.get(key, [])
            numel = got[ti].numel() if ti < len(got) and isinstance(got[ti], torch.Tensor) else -1
            want = n_part if key in ("particles", "history") else n_pairs
            if key == "history":
                if numel < n_part:
                    problems.append(f"runtime.{key}[{ti}] has {numel} < {n_part} entries")
            elif numel != want:
                problems.append(f"runtime.{key}[{ti}] has {numel} != {want}")
        weights = rt.get("weights", [])
        if ti < len(weights) and isinstance(weights[ti], torch.Tensor) and abs(float(weights[ti].sum()) - 1.0) > 1e-3:
            problems.append(f"runtime.weights[{ti}] sums to {float(weights[ti].sum()):.4f} != 1")
        particles = rt.get("particles", [])
        if ti < len(particles) and isinstance(particles[ti], torch.Tensor) and particles[ti].numel():
            lo, hi = int(particles[ti].min()), int(particles[ti].max())
            if lo < 0 or hi >= n_pairs:
                problems.append(f"runtime.particles[{ti}] range [{lo}, {hi}] outside [0, {n_pairs})")
    for key in ("env_pair", "desired_vel", "env_type"):
        got = rt.get(key)
        want = int(getattr(env, "num_envs", -1))
        if not isinstance(got, torch.Tensor) or got.numel() != want:
            problems.append(f"runtime.{key} is not a [{want}] tensor")

    counter = int(state.get("common_step_counter", -1))
    block = int(term.cfg.eval_every) * int(term.cfg.steps_per_iteration)
    next_eval = int(rt.get("next_eval_step", -1))
    if block > 0 and (next_eval % block != 0 or next_eval <= counter):
        problems.append(f"runtime.next_eval_step {next_eval} is not the first block edge above counter {counter}")

    if problems:
        raise ValueError(
            "curriculum state in the checkpoint does not fit this task (yaml/task/env-count change?): "
            + "; ".join(problems)
        )


def apply_state(env, state: dict, *, report=print) -> None:
    """Validate and restore a payload into the live term (no file IO).

    Args:
        env: The environment (raw or wrapped) whose term should receive the state.
        state: A payload from :func:`collect`.
        report: Sink for the restore report (default :func:`print`).

    Raises:
        ValueError: When the payload does not fit the live task/term.
        RuntimeError: When the task wires no joint SIR term at all.
    """
    env = _unwrap(env)
    term = _active_term(env)
    if term is None:
        raise RuntimeError(f"apply_state called on a task without a live {JOINT_SIR_TERM!r} term")
    _validate(state, env, term)

    rt = state["runtime"]
    device = term._particles[0].device
    for key in ("particles", "weights", "episodes", "in_band", "tr_sum", "history"):
        setattr(term, "_" + key, [t.to(device) for t in rt[key]])
    term._env_pair = rt["env_pair"].to(device)
    term.desired_vel = rt["desired_vel"].to(device)
    fresh_type = term._env_type
    term._env_type = rt["env_type"].to(device)
    if not torch.equal(fresh_type, term._env_type):
        report(
            "[curriculum-state] WARN: the fresh per-env terrain-type draw differs from the checkpoint"
            " (different seed or env count?) -- restored the saved assignment, so the per-type traffic"
            " share continues as it was"
        )
    term._next_eval_step = int(rt["next_eval_step"])
    term._tr_block_sum = float(rt["tr_block_sum"])
    term._tr_block_count = int(rt["tr_block_count"])
    term._last_tr_mean = float(rt["last_tr_mean"])
    env.common_step_counter = int(state["common_step_counter"])


def _peek_lr(ckpt: dict) -> float | None:
    """Learning rate recorded in the checkpoint's optimizer state (diagnostic)."""
    try:
        return float(ckpt["optimizer_state_dict"]["param_groups"][0]["lr"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def apply_resume_state(env, resume_path: str, *, weights_only: bool = False, report=print) -> bool:
    """Restore the curriculum state carried by ``resume_path`` before the first reset.

    Args:
        env: The environment straight out of ``gym.make`` (managers built, no
            full reset yet -- the wrapper has not been constructed).
        resume_path: The checkpoint the runner is about to load.
        weights_only: Explicitly drop the curriculum state (weights/optimizer
            only; c_k re-heats and the SIR cold-starts, the pre-2026-09 behavior).
        report: Sink for the resume report (default :func:`print`).

    Returns:
        True when curriculum state was restored.

    Raises:
        RuntimeError: When the task wires the joint SIR term but the checkpoint
            carries no curriculum state and ``weights_only`` was not given --
            silently resuming as a fresh curriculum is the failure this module
            exists to prevent.
    """
    env = _unwrap(env)
    ckpt = torch.load(resume_path, weights_only=False, map_location="cpu")
    infos = ckpt.get("infos") or {}
    state = infos.get(STATE_KEY) if isinstance(infos, dict) else None
    have_term = _active_term(env) is not None

    if weights_only:
        report(
            "[curriculum-state] --weights_only: "
            + ("dropped the checkpoint's curriculum state (c_k re-heats, SIR cold-starts)"
               if state is not None
               else "checkpoint carries no curriculum state")
        )
        return False
    if not have_term:
        if state is not None:
            report(
                f"[curriculum-state] WARN: checkpoint carries curriculum state but task"
                f" {type(getattr(env, 'cfg', None)).__name__} wires no {JOINT_SIR_TERM!r} term -- ignored"
            )
        return False
    if state is None:
        raise RuntimeError(
            f"--resume: {resume_path} carries no curriculum state, but this task wires {JOINT_SIR_TERM!r}."
            " Resuming as-is would re-heat c_k from c0 and cold-start the joint SIR particle filter"
            " (the v3/NOTES incident). Refusing by design -- pass --weights_only to accept that explicitly."
        )

    apply_state(env, state, report=report)

    term = _active_term(env)
    metrics = term._metrics()
    block = int(term.cfg.eval_every) * int(term.cfg.steps_per_iteration)
    report(
        f"[curriculum-state] restored checkpoint iter={ckpt.get('iter')} task={state['task']}"
        f" counter={env.common_step_counter} c_k={ck_value(env):.4f}"
        f" lr={_peek_lr(ckpt)} state~{_tensor_bytes(state) / 2**20:.1f} MB touched={state.get('written_at_iter')}"
    )
    report(
        f"[curriculum-state] joint_sir next_eval_step={term._next_eval_step} (counter={env.common_step_counter},"
        f" block={block}, partial block n={term._tr_block_count}) frontier_max_v={metrics['frontier_max_v']:.3f}"
        f" particle_entropy={metrics['particle_entropy']:.4f} tr_mean={metrics['tr_mean']:.3f}"
    )
    others = _other_stateful_terms(env)
    if others:
        report(
            f"[curriculum-state] WARN: stateful curriculum term(s) {others} are NOT covered by this module"
            " and cold-start on resume -- extend collect/apply_state before trusting their curves"
        )
    return True


def hook_runner_save(runner, env, *, report=print) -> None:
    """Make every checkpoint carry the curriculum state (``infos`` slot).

    ``OnPolicyRunner.save`` writes ``{"...", "iter", "infos"}``; putting the
    state in ``infos`` keeps model and curriculum state in the SAME file, so a
    resume cannot pair an iteration-X policy with an iteration-Y curriculum.

    Args:
        runner: The rsl_rl runner (its ``save`` is replaced by a wrapper).
        env: The wrapped vec env handed to the runner.
        report: Sink for the per-save line (default :func:`print`).
    """
    if getattr(runner, "is_distributed", False):
        if getattr(runner, "gpu_global_rank", 0) != 0:
            return
        report("[curriculum-state] WARN: multi-GPU resume is unverified; curriculum state written from rank 0 only")

    original = runner.save

    @functools.wraps(original)
    def save_with_state(path, infos=None, *args, **kwargs):
        state = collect(env, it=getattr(runner, "current_learning_iteration", None))
        if state is not None:
            infos = {**(infos or {}), STATE_KEY: state}
            size = _tensor_bytes(state)
            report(
                f"[curriculum-state] {os.path.basename(str(path))}: counter={state['common_step_counter']}"
                f" tensors~{size / 2**20:.1f} MB"
            )
            if size > _SIZE_WARN_BYTES:
                report(
                    "WARN: curriculum state exceeds 64 MB -- _history grows every SIR block (unbounded"
                    " concat, teacher_mdp._resample_all). Trim/compact the replay pool if checkpoints drag."
                )
        return original(path, infos, *args, **kwargs)

    runner.save = save_with_state
