# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""True-resume state for the lizard teacher curricula: every registered SIR term + the c_k clock.

Checkpoint resume restores only actor/critic/optimizer/iteration (rsl_rl
``OnPolicyRunner``), so a resumed run re-heats ``c_k`` from ``c0`` and cold-starts
the terrain curriculum -- the documented "resume = re-heat from scratch" incident
(``versions/lizard/v3/NOTES.md``). This module closes that gap for THREE lines:

* the joint SIR (v11/v12 line, :class:`JointSIRTerrainCurriculum`),
* the v5 spawn-weight SIR (v5-v10 and the v13/v14 line, which inherits from v10 --
  :class:`SpawnWeightSIRTerrainCurriculum`),
* the ``common_step_counter`` of any task that runs the c_k schedule, even when it
  wires no registered term at all (v3/v4 line: ``ck_value`` is a pure function of
  that counter, so the counter IS the c_k state).

The state is keyed by a static **fingerprint** of everything the term derives from
cfg/terrain, plus the c_k schedule parameters. A yaml edit that renumbers particles,
re-splits terrain columns, reorders two equal-proportion terrain types or retunes a
terrain parameter or the c_k schedule aborts the restore instead of silently
reinterpreting old indices/values (see :func:`static_state`).

* :func:`apply_resume_state` runs BEFORE the wrapper's first full reset (train.py,
  between ``gym.make`` and ``RslRlVecEnvWrapper``): the term's respawn at that reset
  consumes the restored particles, so terrain slots, ``desired_vel``, spawn origins
  and the c_k-scaled reset DR are consistent from episode 0.
* :func:`hook_runner_save` wraps ``OnPolicyRunner.save`` so the state rides the
  checkpoint's ``infos`` slot (single file, no sidecar to desynchronize).

Not saved (per-episode transients, re-rolled at the next reset): the command term's
``_nu_sum``/``_step_count``, the ring-noise state, foot-friction dips,
``episode_length_buf``. Not saved (the term's own respawn rewrites them):
``terrain_levels``/``terrain_types``/``env_origins``. No RNG states: resume is
statistically continuous, deliberately NOT bit-identical (user decision
2026-09-11) -- particle draws after the restore differ while the distributions,
counters and the c_k clock carry over.

Payload layout (``STATE_VERSION`` 2): common header + an independent clock + one
slot per term instance.

* header -- ``version`` (the container), ``task`` and ``num_envs`` (the v1 identity
  fields, kept), ``written_at_iter``.
* ``clock`` -- ``common_step_counter`` plus ``ck``: the c_k schedule fingerprint
  (``{"version": 1, "static": {c0, decay, steps_per_iteration}}``) or an explicit
  ``None`` for a task that runs no schedule. The same counter under other schedule
  parameters is a different c_k, so the counter alone is not evidence.
* ``terms`` -- one slot per **live curriculum term name**, interpreted by the
  ``adapter``/``adapter_version`` recorded inside the slot. A slot also carries
  ``term_type`` (the class it was written from) and its own ``static``/``runtime``.

Three rules that layout encodes:

1. **Index by instance name, interpret by adapter.** Two terms of the same class get
   two slots instead of overwriting each other, and a restore matches names exactly
   (plus type and adapter version): a renamed term is a mismatch that needs an
   explicit migration, never a guessed correspondence.
2. **Missing / empty / unknown stay distinct.** ``terms == {}`` means "no covered
   term" (a legal c_k-only task); ``clock.ck is None`` means "no c_k schedule"; a
   required field that is absent makes the payload incomplete and is a failure; and
   a v1 payload -- which has no c_k fingerprint at all -- records that absence as
   *unknown evidence*, never as "no c_k".
3. **The terrain digest proves configuration identity, not equal geometry.** It
   binds the ordered sub-terrain names, proportions and parameters so a reordered or
   retuned terrain cannot silently reinterpret old indices; it does not claim the
   meshes are identical.

Two-dimensional honesty (ARCH_PLAN hard constraint 1): a v1 payload is *loadable*
-- it is migrated to the v2 layout -- but its missing witnesses (the c_k
fingerprint, the terrain digest, the per-slot adapter version) are recorded as
``source_version: 1`` + ``missing_evidence`` and the resume is reported as
``evidence: partial``, never as a full pass. The live c_k parameters are NOT
written back into the migrated payload (that would manufacture evidence the old
checkpoint never had); a caller who prefers a clean cold start instead passes
``--drop_curriculum_state``, which skips the whole payload.

ponytail: one adapter instance per term class. Two terms of the same class would
need a per-term dispatch contract nobody has asked for yet, so
:func:`_check_unique_adapters` fails loudly instead of guessing which one a slot
belongs to.
"""

from __future__ import annotations

import functools
import os

import torch
from isaaclab.managers import ManagerTermBase

from rl_exp.tasks.teacher_mdp import (
    JointSIRTerrainCurriculum,
    SpawnWeightSIRTerrainCurriculum,
    ck_value,
)
from rl_exp.tools.verify import cfg_snapshot as cs

STATE_KEY = "lizard_curriculum_state"
"""Key under ``checkpoint["infos"]`` carrying the curriculum state."""

STATE_VERSION = 2
"""Payload *container* schema version; bump when the header/clock/terms layout changes.

1 = the joint SIR alone (``static``/``runtime`` at the top level, no clock, no c_k
    fingerprint, no terrain digest); migrated on read, marked ``source_version: 1``
    with the missing witnesses listed.
2 = header + ``clock`` + ``terms`` keyed by term instance name, each slot carrying
    ``adapter``/``adapter_version``/``term_type``.
"""

CLOCK_VERSION = 1
"""Version of the ``clock`` block (its fields and their interpretation)."""

CK_VERSION = 1
"""Version of the ``clock.ck`` schedule fingerprint (``c0``/``decay``/``steps_per_iteration``)."""

V1_JOINT_SIR_TERM = "joint_sir"
"""Term name the v1 schema implied: its payload carried no name, only one joint SIR state."""

REQUIRES_CURRICULUM_STATE = "REQUIRES_CURRICULUM_STATE"
"""Name of the task-side declaration (a ``ClassVar`` on the env cfg class).

Read at the train.py call site through ``type(env_cfg)`` -- NOT through this module
-- so a task that declares it still aborts on import failure instead of silently
cold-starting. Set on the SIR-carrying teacher recipes (V5..V14 inherit it; every
``*_PLAY`` variant overrides it to False).
"""

_SIZE_WARN_BYTES = 64 * 2**20
"""Checkpoint state size beyond which the unbounded history pool gets called out."""


def _unwrap(env):
    """Accept the raw env or any gym/rsl_rl wrapper around it."""
    return getattr(env, "unwrapped", env)


def _type_id(obj) -> str:
    """Stable identity of a term instance's class (module + qualname)."""
    cls = type(obj)
    return f"{cls.__module__}.{cls.__qualname__}"


def _ck_params(env) -> dict | None:
    """The c_k schedule stashed by the ``init_ck`` startup event, or None.

    ``manager_based_rl_env.load_managers`` applies startup events inside the env
    constructor (``manager_based_rl_env.py:142``), so this is readable before the
    wrapper's first reset -- which is exactly when the restore happens.
    """
    params = getattr(_unwrap(env), "_lizard_ck_params", None)
    if not params:
        return None
    return {
        "c0": float(params["c0"]),
        "decay": float(params["decay"]),
        "steps_per_iteration": int(params["steps_per_iteration"]),
    }


def _terrain_gen_cfg(env):
    """The terrain generator cfg the SIR terms parse their grid from."""
    terrain = getattr(getattr(_unwrap(env), "scene", None), "terrain", None)
    return getattr(getattr(terrain, "cfg", None), "terrain_generator", None)


def _terrain_config_sha256(gen_cfg) -> str | None:
    """Digest of the ordered sub-terrain set: names, proportions and parameters.

    Column indices alone identify nothing: two equal-proportion terrain types can
    swap places, or a difficulty parameter can move, while the column -> type split
    stays byte-identical. Binding the generator's sub-terrain mapping (order is
    semantic, and the serializer keeps it) makes those edits abort the restore.
    This proves the *configuration identity* of the terrain, not that the generated
    geometry is bit-identical.
    """
    sub_terrains = getattr(gen_cfg, "sub_terrains", None)
    if not sub_terrains:
        return None
    return cs.digest(cs.snapshot(sub_terrains))


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


# ---------------------------------------------------------------------------------
# Term adapters: what "this term's state" means, per registered term class.
# ---------------------------------------------------------------------------------


class _Adapter:
    """Snapshot/validate/restore contract for one stateful curriculum term class."""

    key: str = ""
    """Payload slot tag; must stay stable (it is written into checkpoints)."""
    adapter_version: int = 1
    """Version of this term's ``static``/``runtime`` fields and their meaning."""
    term_class: type
    """The ``ManagerTermBase`` subclass this adapter registers."""
    cfg_keys: tuple[str, ...] = ()
    """Cfg fields whose values the term's state cannot be reinterpreted across."""

    def static(self, term, gen_cfg) -> dict:
        """Everything the term derives from cfg/terrain (the restore's guard)."""
        raise NotImplementedError

    def runtime(self, term, env) -> dict:
        """The mutable curriculum state this adapter round-trips."""
        raise NotImplementedError

    def check(self, term, env, name: str, slot: dict, problems: list[str], missing: list[str]) -> None:
        """Append payload-vs-live mismatches (never mutate the term).

        A fingerprint present in the payload but absent live is a *problem*; one the
        payload never carried (a v1 slot has no ``terrain_config_sha256``) is
        *missing evidence*: not a mismatch, but nothing that can pass as verified.
        """
        raise NotImplementedError

    def apply(self, term, env, slot: dict, report) -> None:
        """Write a validated slot into the live term."""
        raise NotImplementedError

    def _cfg_values(self, term) -> dict:
        return {key: getattr(term.cfg, key) for key in self.cfg_keys}

    def _check_static(
        self, term, gen_cfg, name: str, slot: dict, problems: list[str], missing: list[str]
    ) -> None:
        saved, now = slot.get("static", {}), self.static(term, gen_cfg)
        for key, current in now.items():
            if key not in saved:
                missing.append(f"terms.{name}.static.{key}")
            elif not _tensor_eq(saved.get(key), current):
                problems.append(f"static.{key} (terms.{name})")

    def _check_common_cfg(self, term, name: str, slot: dict, problems: list[str], missing: list[str]) -> None:
        saved = slot.get("static", {}).get("cfg")
        now = self._cfg_values(term)
        if not isinstance(saved, dict):
            missing.append(f"terms.{name}.static.cfg")
            return
        for key, current in now.items():
            if key not in saved:
                missing.append(f"terms.{name}.static.cfg.{key}")
            elif saved.get(key) != current:
                problems.append(f"static.cfg.{key} (terms.{name}: {saved.get(key)!r} -> {current!r})")


class _JointSIRAdapter(_Adapter):
    """v11/v12 joint particle SIR over (param combo, velocity bucket) pairs."""

    key = "joint_sir"
    adapter_version = 1
    term_class = JointSIRTerrainCurriculum
    cfg_keys = (
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

    def static(self, term, gen_cfg) -> dict:
        """Grid split, velocity buckets, runtime-relevant cfg and the terrain digest."""
        return {
            "types": list(term._types),
            "num_rows": int(term._num_rows),
            "n_levels": [list(v) for v in term._n_levels],
            "n_pairs": list(term._n_pairs),
            "n_v": int(term._n_v),
            "velocity": term._velocity.detach().cpu().clone(),
            "combo_cols": [[c.detach().cpu().clone() for c in cols] for cols in term._combo_cols],
            "terrain_config_sha256": _terrain_config_sha256(gen_cfg),
            "cfg": self._cfg_values(term),
        }

    def runtime(self, term, env) -> dict:
        return {
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
        }

    def check(self, term, env, name, slot, problems, missing, counter) -> None:
        self._check_static(term, _terrain_gen_cfg(env), name, slot, problems, missing)
        self._check_common_cfg(term, name, slot, problems, missing)
        rt = slot.get("runtime", {})
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
            if ti < len(weights) and isinstance(weights[ti], torch.Tensor):
                if abs(float(weights[ti].sum()) - 1.0) > 1e-3:
                    problems.append(f"runtime.weights[{ti}] sums to {float(weights[ti].sum()):.4f} != 1")
            particles = rt.get("particles", [])
            if ti < len(particles) and isinstance(particles[ti], torch.Tensor) and particles[ti].numel():
                lo, hi = int(particles[ti].min()), int(particles[ti].max())
                if lo < 0 or hi >= n_pairs:
                    problems.append(f"runtime.particles[{ti}] range [{lo}, {hi}] outside [0, {n_pairs})")
        _check_env_vectors(rt, env, ("env_pair", "desired_vel", "env_type"), problems)
        _check_eval_clock(term.cfg, rt, counter, problems, name)

    def apply(self, term, env, slot, report) -> None:
        rt = slot["runtime"]
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


class _SpawnWeightSIRAdapter(_Adapter):
    """v5-v10 (+ the v13/v14 line) spawn-weight SIR over difficulty rows."""

    key = "row_sir"
    adapter_version = 1
    term_class = SpawnWeightSIRTerrainCurriculum
    cfg_keys = (
        "command_name",
        "band",
        "eval_every",
        "n_traj_min",
        "p_transition",
        "p_replay",
        "success_ratio",
        "soft_edge",
        "steps_per_iteration",
    )

    def static(self, term, gen_cfg) -> dict:
        """Column split, ordered type names, runtime-relevant cfg, terrain digest.

        ``type_cols`` is the same quantity the term computes at construction; the
        ordered ``types`` list plus ``terrain_config_sha256`` are what make a reorder of two
        equal-proportion types (or a retuned difficulty parameter) visible even when
        the column split does not move.
        """
        sub_terrains = getattr(gen_cfg, "sub_terrains", None) or {}
        return {
            "types": list(sub_terrains.keys()),
            "num_types": int(term._num_types),
            "num_rows": int(term._num_rows),
            "type_cols": [c.detach().cpu().clone() for c in term._type_cols],
            "terrain_config_sha256": _terrain_config_sha256(gen_cfg),
            "cfg": self._cfg_values(term),
        }

    def runtime(self, term, env) -> dict:
        return {
            "particles": [t.detach().cpu().clone() for t in term._particles],
            "weights": [t.detach().cpu().clone() for t in term._weights],
            "episodes": [t.detach().cpu().clone() for t in term._episodes],
            "successes": [t.detach().cpu().clone() for t in term._successes],
            "history": [t.detach().cpu().clone() for t in term._history],
            "env_type": term._env_type.detach().cpu().clone(),
            "next_eval_step": int(term._next_eval_step),
        }

    def check(self, term, env, name, slot, problems, missing, counter) -> None:
        self._check_static(term, _terrain_gen_cfg(env), name, slot, problems, missing)
        self._check_common_cfg(term, name, slot, problems, missing)
        rt = slot.get("runtime", {})
        rows = int(term._num_rows)
        for key in ("particles", "weights", "episodes", "successes", "history"):
            got = rt.get(key, [])
            if len(got) != len(term._type_cols):
                problems.append(f"runtime.{key} has {len(got)} types != {len(term._type_cols)}")
                continue
            for ti, tensor in enumerate(got):
                if not isinstance(tensor, torch.Tensor):
                    problems.append(f"runtime.{key}[{ti}] is not a tensor")
                    continue
                if key == "history":
                    if tensor.numel() < rows:
                        problems.append(f"runtime.{key}[{ti}] has {tensor.numel()} < {rows} entries")
                elif tensor.numel() != rows:
                    problems.append(f"runtime.{key}[{ti}] has {tensor.numel()} != {rows}")
        for key in ("particles", "weights", "episodes", "successes"):
            for ti, tensor in enumerate(rt.get(key, [])):
                if not isinstance(tensor, torch.Tensor) or not tensor.numel():
                    continue
                if key == "particles":
                    lo, hi = int(tensor.min()), int(tensor.max())
                    if lo < 0 or hi >= rows:
                        problems.append(f"runtime.particles[{ti}] range [{lo}, {hi}] outside [0, {rows})")
                elif key == "weights" and abs(float(tensor.sum()) - 1.0) > 1e-3:
                    problems.append(f"runtime.weights[{ti}] sums to {float(tensor.sum()):.4f} != 1")
        episodes = rt.get("episodes", [])
        successes = rt.get("successes", [])
        for ti, (a, b) in enumerate(zip(episodes, successes)):
            if isinstance(a, torch.Tensor) and isinstance(b, torch.Tensor) and float((b - a).max()) > 1e-6:
                problems.append(f"runtime.successes[{ti}] exceeds episodes[{ti}]")
        _check_env_vectors(rt, env, ("env_type",), problems)
        env_type = rt.get("env_type")
        if isinstance(env_type, torch.Tensor) and env_type.numel():
            lo, hi = int(env_type.min()), int(env_type.max())
            if lo < 0 or hi >= int(term._num_types):
                problems.append(f"runtime.env_type range [{lo}, {hi}] outside [0, {term._num_types})")
        _check_eval_clock(term.cfg, rt, counter, problems, name)

    def apply(self, term, env, slot, report) -> None:
        rt = slot["runtime"]
        device = term._particles[0].device
        for key in ("particles", "weights", "episodes", "successes", "history"):
            setattr(term, "_" + key, [t.to(device) for t in rt[key]])
        fresh_type = term._env_type
        term._env_type = rt["env_type"].to(device)
        if not torch.equal(fresh_type, term._env_type):
            report(
                "[curriculum-state] WARN: the fresh per-env terrain-type draw differs from the checkpoint"
                " (different seed or env count?) -- restored the saved assignment, so the per-type traffic"
                " share continues as it was"
            )
        term._next_eval_step = int(rt["next_eval_step"])


_ADAPTERS: tuple[_Adapter, ...] = (_JointSIRAdapter(), _SpawnWeightSIRAdapter())


def _check_env_vectors(rt: dict, env, keys: tuple[str, ...], problems: list[str]) -> None:
    """Per-env vectors must be [num_envs] tensors of the live env."""
    want = int(getattr(_unwrap(env), "num_envs", -1))
    for key in keys:
        got = rt.get(key)
        if not isinstance(got, torch.Tensor) or got.numel() != want:
            problems.append(f"runtime.{key} is not a [{want}] tensor")


def _check_eval_clock(cfg, rt: dict, counter: int, problems: list[str], tag: str) -> None:
    """``next_eval_step`` must stay the first block edge above the restored counter."""
    block = int(cfg.eval_every) * int(cfg.steps_per_iteration)
    next_eval = int(rt.get("next_eval_step", -1))
    if block > 0 and (next_eval % block != 0 or next_eval <= counter):
        problems.append(f"runtime.next_eval_step[{tag}] {next_eval} is not the first block edge above {counter}")


def adapter_for(cls) -> _Adapter | None:
    """The adapter registered for a curriculum term class, or None."""
    if not isinstance(cls, type):
        cls = type(cls)
    return next((a for a in _ADAPTERS if issubclass(cls, a.term_class)), None)


def _wired_terms(env) -> dict[str, object]:
    """Every wired curriculum term's callable, by term name (None terms skipped)."""
    manager = getattr(_unwrap(env), "curriculum_manager", None)
    if manager is None:
        return {}
    out: dict[str, object] = {}
    for name, term_cfg in vars(manager.cfg).items():
        if name.startswith("_"):
            continue
        func = getattr(term_cfg, "func", None)
        if func is not None:
            out[name] = func
    return out


def covered_terms(env) -> dict[str, tuple[_Adapter, object]]:
    """Wired curriculum terms an adapter can snapshot: name -> (adapter, instance)."""
    out: dict[str, tuple[_Adapter, object]] = {}
    for name, func in _wired_terms(env).items():
        if isinstance(func, type):
            # wired as a class: the manager has not built the instance yet, so there is
            # nothing to snapshot -- treating it as "no term" would silently drop state
            if adapter_for(func) is not None:
                raise RuntimeError(
                    f"curriculum term {name!r} is wired with the class {func.__name__}, not an instance;"
                    " curriculum state cannot be snapshotted (was the manager built?)"
                )
            continue
        if isinstance(func, ManagerTermBase):
            adapter = adapter_for(type(func))
            if adapter is not None:
                out[name] = (adapter, func)
    return out


def uncovered_terms(env) -> list[str]:
    """Wired stateful curriculum terms no adapter covers (they cold-start on resume)."""
    out = []
    for name, func in _wired_terms(env).items():
        if isinstance(func, ManagerTermBase) and adapter_for(type(func)) is None:
            out.append(name)
    return sorted(out)


def requires_resume_state(env) -> bool:
    """Does this task promise that a resume continues its curriculum?

    The task declares it (``REQUIRES_CURRICULUM_STATE`` on the env cfg class, read
    through the class so a config value's absence cannot hide it) and wires at least
    one curriculum term. A resume of such a task must not cold-start.
    """
    cfg_cls = type(getattr(_unwrap(env), "cfg", None))
    if not getattr(cfg_cls, REQUIRES_CURRICULUM_STATE, False):
        return False
    return bool(_wired_terms(env))


def static_state(term, env) -> dict:
    """The registered fingerprint of ``term`` (see the module docstring)."""
    adapter = adapter_for(type(term))
    if adapter is None:
        raise RuntimeError(f"no curriculum-state adapter is registered for {_type_id(term)}")
    return adapter.static(term, _terrain_gen_cfg(env))


def _check_unique_adapters(covered: dict[str, tuple[_Adapter, object]]) -> None:
    """One adapter instance per term class (see the module docstring's ponytail note)."""
    seen: dict[str, str] = {}
    for name, (adapter, _term) in covered.items():
        if adapter.key in seen:
            raise RuntimeError(
                f"curriculum terms {seen[adapter.key]!r} and {name!r} both map to the {adapter.key!r} adapter;"
                " this module registers one instance per term class -- extend the adapter contract first"
            )
        seen[adapter.key] = name


def collect(env, it: int | None = None) -> dict | None:
    """Snapshot the registered curriculum state, or None when there is none.

    Args:
        env: The environment (raw or wrapped).
        it: The runner's current learning iteration, for diagnostics only.

    Returns:
        The payload to store under ``infos[STATE_KEY]``, or None for tasks that wire
        no registered term and run no c_k schedule (PLAY variants of the retired
        v1/v2 recipes, non-lizard tasks).
    """
    env = _unwrap(env)
    covered = covered_terms(env)
    _check_unique_adapters(covered)
    ck = _ck_params(env)
    if not covered and ck is None:
        return None
    terms = {
        name: {
            "adapter": adapter.key,
            "adapter_version": int(adapter.adapter_version),
            "term_type": _type_id(term),
            "static": adapter.static(term, _terrain_gen_cfg(env)),
            "runtime": adapter.runtime(term, env),
        }
        for name, (adapter, term) in covered.items()
    }
    return {
        "version": STATE_VERSION,
        "written_at_iter": None if it is None else int(it),
        "task": type(getattr(env, "cfg", None)).__name__,
        "num_envs": int(env.num_envs),
        "clock": {
            "version": CLOCK_VERSION,
            "common_step_counter": int(env.common_step_counter),
            # None = this task runs no c_k schedule (explicit, not "unknown")
            "ck": None if ck is None else {"version": CK_VERSION, "static": ck},
        },
        "terms": terms,
    }


def _normalize(state: dict) -> dict:
    """Upgrade a v1 payload to the v2 layout WITHOUT inventing missing evidence.

    v1 stored the joint SIR state flat under its historical term name (it carried no
    term name at all) and had neither a c_k fingerprint nor a terrain digest. The
    migration maps it to that single joint SIR slot and keeps the original counter,
    but records the absent witnesses instead of filling them in from the live
    config: a v1 payload is *readable*, and that is deliberately not the same as
    "verified" -- the live c_k parameters say nothing about the parameters the
    checkpoint was built with. ``clock.ck`` is therefore left ``None`` *with*
    ``ck_evidence: absent_in_source``, so it can never be read as "no c_k schedule".

    The migrated slot keeps the historical name: a term renamed since v1 does not
    match by accident, it reports a missing slot (explicit migration is the
    caller's decision, never this module's guess).
    """
    if state.get("version") != 1:
        return state
    return {
        "version": STATE_VERSION,
        "source_version": 1,
        "written_at_iter": state.get("written_at_iter"),
        "task": state.get("task"),
        "num_envs": state.get("num_envs"),
        "clock": {
            "version": CLOCK_VERSION,
            "common_step_counter": state.get("common_step_counter"),
            "ck": None,
            "ck_evidence": "absent_in_source",
        },
        "terms": {
            V1_JOINT_SIR_TERM: {
                "adapter": _JointSIRAdapter.key,
                "adapter_version": int(_JointSIRAdapter.adapter_version),
                "term_type": f"{JointSIRTerrainCurriculum.__module__}.{JointSIRTerrainCurriculum.__qualname__}",
                "static": dict(state.get("static") or {}),
                "runtime": dict(state.get("runtime") or {}),
            }
        },
    }


def _check_payload_shape(state: dict, problems: list[str]) -> None:
    """Required header/clock/terms fields must be present: a partial payload is a failure.

    ``terms == {}`` (no covered term) and ``clock.ck is None`` (no schedule) are legal
    and explicit; a *missing* field is neither -- it says nothing.
    """
    for key in ("version", "task", "num_envs", "written_at_iter", "clock", "terms"):
        if key not in state:
            problems.append(f"payload field {key!r} is missing (incomplete state)")
    clock = state.get("clock")
    if not isinstance(clock, dict):
        problems.append(f"clock is {type(clock).__name__}, not a mapping")
        return
    for key in ("version", "common_step_counter", "ck"):
        if key not in clock:
            problems.append(f"clock field {key!r} is missing (incomplete state)")


def _clock_counter(clock: dict, problems: list[str]) -> int:
    """``clock.common_step_counter`` as int, or -1 with a problem when unusable."""
    try:
        return int(clock.get("common_step_counter"))
    except (TypeError, ValueError):
        problems.append(f"clock.common_step_counter is {clock.get('common_step_counter')!r}, not an int")
        return -1


def _check_c_k(clock: dict, live: dict | None, problems: list[str], missing: list[str]) -> None:
    """The c_k schedule is part of the state: the same counter under other parameters
    is a different c_k, so a mismatch cannot pass -- and an *absence of evidence*
    (a v1 payload) is recorded as unknown rather than as "no c_k"."""
    if clock.get("ck_evidence") == "absent_in_source":
        missing.append("clock.ck")
        return
    ck = clock.get("ck")
    if ck is None and live is None:
        return  # explicitly no schedule on both sides
    if ck is None:
        problems.append(
            "this task runs the c_k schedule but the checkpoint records none (clock.ck is None):"
            " the counter alone does not pin c_k"
        )
        return
    if not isinstance(ck, dict):
        problems.append(f"clock.ck is {type(ck).__name__}, not a mapping")
        return
    if ck.get("version") != CK_VERSION:
        problems.append(f"unknown clock.ck version {ck.get('version')!r}")
    saved = ck.get("static")
    if not isinstance(saved, dict):
        problems.append(f"clock.ck.static is {type(saved).__name__}, not a mapping")
        return
    if live is None:
        problems.append(
            f"c_k schedule {saved} in the checkpoint but this task wires no init_ck event"
            " (c_k cannot be continued)"
        )
        return
    for key in ("c0", "decay", "steps_per_iteration"):
        if key not in saved:
            missing.append(f"clock.ck.static.{key}")
        elif saved.get(key) != live.get(key):
            problems.append(f"clock.ck.static.{key} {saved.get(key)!r} -> {live.get(key)!r}")



def apply_state(env, state: dict, *, report=print) -> dict:
    """Validate and restore a payload into the live terms (no file IO).

    Every slot and fingerprint is checked BEFORE anything is written, so a payload
    that fails halfway leaves the live terms untouched instead of half-restored.

    Args:
        env: The environment (raw or wrapped) whose terms should receive the state.
        state: A payload from :func:`collect` (v1 payloads are upgraded and flagged).
        report: Sink for the restore report (default :func:`print`).

    Returns:
        The restore outcome (what was actually restored, what was skipped, and what
        could not be fully verified) -- the same dict the manifest records as-is.

    Raises:
        ValueError: When the payload does not fit the live task/terms.
    """
    env = _unwrap(env)
    state = _normalize(state)
    covered = covered_terms(env)
    _check_unique_adapters(covered)
    problems: list[str] = []
    missing: list[str] = []
    _check_payload_shape(state, problems)
    clock = state.get("clock") if isinstance(state.get("clock"), dict) else {}
    counter = _clock_counter(clock, problems)
    if state.get("version") != STATE_VERSION:
        problems.append(f"unknown/unsupported container version {state.get('version')!r}")
    if clock.get("version") != CLOCK_VERSION:
        problems.append(f"unknown clock version {clock.get('version')!r}")
    if state.get("num_envs") != int(getattr(env, "num_envs", -1)):
        problems.append(f"num_envs {state.get('num_envs')} -> {getattr(env, 'num_envs', None)}")
    task_now = type(getattr(env, "cfg", None)).__name__
    if state.get("task") != task_now:
        problems.append(f"task {state.get('task')} -> {task_now}")

    ck_live = _ck_params(env)
    _check_c_k(clock, ck_live, problems, missing)

    slots = state.get("terms") if isinstance(state.get("terms"), dict) else {}
    missing_slots = sorted(name for name in covered if name not in slots)
    extra_slots = sorted(name for name in slots if name not in covered)
    need_state = requires_resume_state(env) or bool(covered)
    if missing_slots:
        # a renamed term is a mismatch, not a correspondence to guess
        problems.append(
            f"checkpoint has no slot for live term(s) {missing_slots}: a renamed term needs an explicit"
            " migration (re-save with the current code, or --drop_curriculum_state)"
        )
    if extra_slots and need_state:
        problems.append(f"checkpoint slot(s) {extra_slots} have no live term; the curriculum changed under it")

    to_apply = []
    for name, (adapter, term) in sorted(covered.items()):
        slot = slots.get(name)
        if slot is None:
            continue
        if slot.get("adapter") != adapter.key:
            problems.append(f"terms.{name}.adapter {slot.get('adapter')!r} -> {adapter.key!r}")
            continue
        if slot.get("adapter_version") != int(adapter.adapter_version):
            problems.append(
                f"terms.{name}.adapter_version {slot.get('adapter_version')!r} -> {adapter.adapter_version}"
            )
            continue
        if slot.get("term_type") != _type_id(term):
            problems.append(f"terms.{name}.term_type {slot.get('term_type')!r} -> {_type_id(term)!r}")
            continue
        if not isinstance(slot.get("static"), dict) or not isinstance(slot.get("runtime"), dict):
            problems.append(f"terms.{name} lacks a static/runtime mapping (incomplete state)")
            continue
        adapter.check(term, env, name, slot, problems, missing, counter)
        to_apply.append((name, adapter, term, slot))

    if problems:
        raise ValueError(
            "curriculum state in the checkpoint does not fit this task (yaml/task/env-count change?): "
            + "; ".join(problems)
        )

    # nothing is written until every slot has passed, so a payload that fails anywhere
    # cannot leave a half-restored term behind
    for name, adapter, term, slot in to_apply:
        adapter.apply(term, env, slot, report)

    restored_terms = [
        {
            "name": name,
            "adapter": adapter.key,
            "adapter_version": int(adapter.adapter_version),
            "type": slot.get("term_type"),
        }
        for name, adapter, _t, slot in to_apply
    ]
    restore_counter = bool(to_apply) or ck_live is not None
    if restore_counter:
        env.common_step_counter = counter

    schedule = _schedule_verdict(clock, ck_live, missing)
    source_version = int(state.get("source_version") or state.get("version") or 0)
    notes: list[str] = []
    if source_version == 1:
        notes.append(
            "v1 payload: no c_k fingerprint, no terrain digest and no per-slot adapter version existed in"
            " that schema; the migrated state is readable, and the absent witnesses are reported below"
        )
    for item in missing:
        notes.append(f"missing evidence: {item} (not verifiable from this payload)")
    for name in missing_slots:
        notes.append(f"live term {name!r} is absent from the checkpoint")
    for name in extra_slots:
        notes.append(f"checkpoint slot {name!r} has no live term (not applied)")
    for name in uncovered_terms(env):
        notes.append(f"stateful term {name!r} is not covered by any registered adapter (cold-starts)")

    outcome = {
        "status": "restored",
        "source_version": source_version,
        "payload_version": int(state["version"]),
        "evidence": "complete" if not missing else "partial",
        "missing_evidence": missing,
        "terms": restored_terms,
        "skipped_terms": missing_slots,
        "extra_slots": extra_slots,
        "uncovered_terms": uncovered_terms(env),
        "c_k": {"restored": bool(restore_counter and ck_live is not None), "schedule": schedule},
        "common_step_counter": int(env.common_step_counter),
        "notes": notes,
    }
    if not to_apply:
        report(
            "[curriculum-state] WARN: no registered term state was restored"
            f" (c_k {'restored' if restore_counter else 'absent'})"
        )
    for note in notes:
        report(f"[curriculum-state] NOTE: {note}")
    return outcome


def _schedule_verdict(clock: dict, live: dict | None, missing: list[str]) -> str:
    """``none`` (no schedule either side) / ``matched`` / ``unverified`` (absent evidence)."""
    if any(item.startswith("clock.") for item in missing):
        return "unverified"
    ck = clock.get("ck")
    if ck is None and live is None:
        return "none"
    saved = ck.get("static") if isinstance(ck, dict) else None
    return "matched" if saved == live else "unverified"


def _peek_lr(ckpt: dict) -> float | None:
    """Learning rate recorded in the checkpoint's optimizer state (diagnostic)."""
    try:
        return float(ckpt["optimizer_state_dict"]["param_groups"][0]["lr"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _rank() -> int:
    """This process's distributed rank (rsl_rl/IsaacLab convention)."""
    try:
        return int(os.getenv("RANK", "0"))
    except ValueError:
        return 0


def apply_resume_state(
    env,
    resume_path: str,
    *,
    drop_curriculum_state: bool = False,
    weights_only: bool | None = None,
    report=print,
) -> dict:
    """Restore the curriculum state carried by ``resume_path`` before the first reset.

    Args:
        env: The environment straight out of ``gym.make`` (managers built, no full
            reset yet -- the wrapper has not been constructed).
        resume_path: The checkpoint the runner is about to load.
        drop_curriculum_state: Explicitly drop the curriculum state (weights/optimizer
            only; c_k re-heats and the SIR cold-starts, the pre-2026-09 behavior).
        weights_only: Deprecated alias of ``drop_curriculum_state``.
        report: Sink for the resume report (default :func:`print`).

    Returns:
        The resume outcome (see :func:`apply_state`), plus ``status`` values
        ``dropped`` / ``no_state`` / ``rank_skipped`` and, for a dropped or skipped
        resume, ``evidence: none``. This dict is what the manifest records -- the
        actual result, not something re-derived from the env.

    Raises:
        RuntimeError: When this task requires curriculum continuity (it declares
            ``REQUIRES_CURRICULUM_STATE`` or wires a registered term) but the
            checkpoint cannot provide it and no explicit drop was requested --
            silently resuming as a fresh curriculum is the failure this module
            exists to prevent.
    """
    env = _unwrap(env)
    if weights_only is not None:
        report(
            "[curriculum-state] DEPRECATED: weights_only= is now drop_curriculum_state="
            " (same behavior: drop the curriculum state, keep weights/optimizer)"
        )
        drop_curriculum_state = drop_curriculum_state or bool(weights_only)

    rank = _rank()
    if rank != 0:
        # the state in a checkpoint is rank 0's environment state; restoring it into
        # another rank's envs would be wrong, and multi-GPU is out of scope
        report(
            f"[curriculum-state] WARN: rank {rank} != 0 -- multi-GPU resume is not covered;"
            " this rank keeps a cold curriculum (state is written from rank 0 only)"
        )
        return _outcome("rank_skipped", rank=rank, report=report)

    ckpt = torch.load(resume_path, weights_only=False, map_location="cpu")
    infos = ckpt.get("infos") or {}
    state = infos.get(STATE_KEY) if isinstance(infos, dict) else None
    covered = covered_terms(env)
    need = requires_resume_state(env) or bool(covered)

    if drop_curriculum_state:
        report(
            "[curriculum-state] --drop_curriculum_state: "
            + ("dropped the checkpoint's curriculum state (c_k re-heats, SIR cold-starts)"
               if state is not None
               else "checkpoint carries no curriculum state")
        )
        return _outcome("dropped", rank=rank, report=report, checkpoint_iter=ckpt.get("iter"))

    if state is None:
        if need:
            raise RuntimeError(
                f"--resume: {resume_path} carries no curriculum state, but {type(getattr(env, 'cfg', None)).__name__}"
                f" requires curriculum continuity ({'declares ' + REQUIRES_CURRICULUM_STATE if requires_resume_state(env) else 'wires ' + ', '.join(sorted(covered))})."
                " Resuming as-is would re-heat c_k and cold-start the terrain curriculum (the v3/NOTES"
                " incident). Refusing by design -- pass --drop_curriculum_state to accept that explicitly."
            )
        report(
            f"[curriculum-state] WARN: {resume_path} carries no curriculum state and this task wires none"
            f" ({type(getattr(env, 'cfg', None)).__name__}) -- nothing to restore"
        )
        return _outcome("no_state", rank=rank, report=report, checkpoint_iter=ckpt.get("iter"))

    if not covered and not need and _ck_params(env) is None:
        # The checkpoint holds state (it came from a training run) but nothing HERE can
        # carry it: a PLAY variant, or a task whose stateful term was removed. That is a
        # fact about the checkpoint, not a mismatch, so it passes through with a warning
        # instead of refusing -- the hard refusal is reserved for tasks that ask for
        # continuity (declare REQUIRES_CURRICULUM_STATE or wire a registered term), which
        # is exactly the boundary ARCH_PLAN 1.3 draws (其它任务透传). Refusing here would
        # also break the ordinary "resume a trained checkpoint into a PLAY task" flow.
        report(
            f"[curriculum-state] WARN: {resume_path} carries curriculum state but this task wires no"
            f" stateful term and runs no c_k schedule ({type(getattr(env, 'cfg', None)).__name__})"
            " -- nothing to restore"
        )
        return _outcome("no_state", rank=rank, report=report, checkpoint_iter=ckpt.get("iter"))

    try:
        outcome = apply_state(env, state, report=report)
    except ValueError as err:
        raise ValueError(f"{err} [checkpoint {resume_path}]") from err
    outcome["checkpoint_iter"] = ckpt.get("iter")
    outcome["rank"] = rank

    metrics_note = _metrics_note(env, covered)
    report(
        f"[curriculum-state] restored checkpoint iter={ckpt.get('iter')}"
        f" task={state.get('task')} counter={env.common_step_counter} c_k={ck_value(env):.4f}"
        f" lr={_peek_lr(ckpt)} state~{_tensor_bytes(state) / 2**20:.1f} MB touched={state.get('written_at_iter')}"
    )
    if metrics_note:
        report(metrics_note)
    return outcome


def _metrics_note(env, covered: dict) -> str:
    """One diagnostic line per restored joint SIR (its metrics drive the curriculum)."""
    parts = []
    for name, (adapter, term) in covered.items():
        if adapter.key != _JointSIRAdapter.key:
            continue
        metrics = term._metrics()
        block = int(term.cfg.eval_every) * int(term.cfg.steps_per_iteration)
        parts.append(
            f"{name} next_eval_step={term._next_eval_step} (counter={env.common_step_counter}, block={block},"
            f" partial block n={term._tr_block_count}) frontier_max_v={metrics['frontier_max_v']:.3f}"
            f" particle_entropy={metrics['particle_entropy']:.4f} tr_mean={metrics['tr_mean']:.3f}"
        )
    return "[curriculum-state] " + "; ".join(parts) if parts else ""


def _outcome(status: str, *, rank: int, report, checkpoint_iter=None, note: str | None = None) -> dict:
    """A non-restore outcome (dropped / no_state / rank_skipped), same shape as a restore."""
    return {
        "status": status,
        "source_version": None,
        "payload_version": None,
        "evidence": "none",
        "missing_evidence": [],
        "terms": [],
        "skipped_terms": [],
        "extra_slots": [],
        "uncovered_terms": [],
        "c_k": {"restored": False, "schedule": "unverified"},
        "common_step_counter": None,
        "notes": [note] if note else [],
        "checkpoint_iter": checkpoint_iter,
        "rank": rank,
    }


def hook_runner_save(runner, env, *, report=print) -> bool:
    """Make every checkpoint carry the curriculum state (``infos`` slot).

    ``OnPolicyRunner.save`` writes ``{"...", "iter", "infos"}``; putting the state in
    ``infos`` keeps model and curriculum state in the SAME file, so a resume cannot
    pair an iteration-X policy with an iteration-Y curriculum.

    A task that requires curriculum continuity must never write a checkpoint without
    it, so this raises rather than silently writing one when ``collect`` comes back
    empty for such a task.

    Args:
        runner: The rsl_rl runner (its ``save`` is replaced by a wrapper).
        env: The wrapped vec env handed to the runner.
        report: Sink for the per-save line (default :func:`print`).

    Returns:
        True when the wrapper was installed; False when this rank does not save
        (multi-GPU: only rank 0 writes the state it verified).
    """
    if getattr(runner, "is_distributed", False):
        if getattr(runner, "gpu_global_rank", 0) != 0:
            report(
                "[curriculum-state] WARN: multi-GPU resume is unverified; curriculum state written"
                " from rank 0 only -- this rank saves no curriculum state"
            )
            return False
        report("[curriculum-state] WARN: multi-GPU resume is unverified; curriculum state written from rank 0 only")

    original = runner.save

    @functools.wraps(original)
    def save_with_state(path, infos=None, *args, **kwargs):
        state = collect(env, it=getattr(runner, "current_learning_iteration", None))
        if state is None:
            if requires_resume_state(env):
                raise RuntimeError(
                    f"{type(getattr(_unwrap(env), 'cfg', None)).__name__} declares {REQUIRES_CURRICULUM_STATE}"
                    f" but no curriculum state was collected for {path}: the checkpoint would be"
                    " un-resumable. Check the curriculum wiring (a term nulled by a recipe/PLAY variant?)."
                )
        else:
            infos = {**(infos or {}), STATE_KEY: state}
            size = _tensor_bytes(state)
            report(
                f"[curriculum-state] {os.path.basename(str(path))}: counter={state['clock']['common_step_counter']}"
                f" tensors~{size / 2**20:.1f} MB"
            )
            if size > _SIZE_WARN_BYTES:
                report(
                    "WARN: curriculum state exceeds 64 MB -- _history grows every SIR block (unbounded"
                    " concat, teacher_mdp._resample_all). Trim/compact the replay pool if checkpoints drag."
                )
        return original(path, infos, *args, **kwargs)

    runner.save = save_with_state
    return True
