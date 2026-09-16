# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Observe-only probe for the ARCH_PLAN 1.4b C-layer run (true resume).

The C layer claims something no offline test can see: that the restore lands BEFORE the
wrapper's first full reset, that ``common_step_counter`` advances by exactly one per env
step, that the curricula update on their real schedule, and that a drop arm cold-starts
while still loading model/optimizer. Those observation points only exist inside the REAL
trainer process, so this module is injected there (``sitecustomize`` on ``PYTHONPATH``)
and wraps production callables. It never changes a parameter, a return value or the
number of random draws: every wrapper calls through and only reads.

Usage (cwd ``E:\\IsaacLab``, one JSON file per process under the target directory):

    set RL_CSTATE_OBSERVE=<dir>
    set PYTHONPATH=<dir holding the sitecustomize shim>;%PYTHONPATH%
    python scripts\\reinforcement_learning\\rsl_rl\\train.py --task <id> --headless ...

The shim is three lines and lives outside the repo (see ``docs`` in ACCEPTANCE 1.4b); the
logic that has to be reviewed lives here. Read the JSON with the companion verifier, or by
hand: ``load`` / ``p1`` / ``p2`` / ``steps`` / ``updates`` / ``curriculum_updates``.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import pathlib
import sys
import time

ENV_VAR = "RL_CSTATE_OBSERVE"

_REPO = pathlib.Path(__file__).resolve().parents[3]
_records: dict = {"pid": os.getpid(), "argv": sys.argv, "events": [], "installed": []}
_installed = False


def _log(event: str, **fields) -> None:
    _records["events"].append({"t": round(time.time(), 3), "event": event, **fields})
    _maybe_flush()


def _tensor_digest(t) -> str:
    import torch

    if not torch.is_tensor(t):
        return repr(t)
    arr = t.detach().to("cpu").contiguous()
    return f"{tuple(arr.shape)}:{arr.dtype}:{hashlib.sha256(arr.numpy().tobytes()).hexdigest()[:16]}"


def _summary(obj):
    """Small JSON value for a tensor / list of tensors / nested dict (hashes, not copies)."""
    import torch

    if torch.is_tensor(obj):
        return {
            "digest": _tensor_digest(obj),
            "shape": list(obj.shape),
            "sum": round(float(obj.float().sum()), 6),
            "finite": bool(torch.isfinite(obj.float()).all()),
        }
    if isinstance(obj, (list, tuple)):
        return [_summary(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _summary(v) for k, v in obj.items()}
    if isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    return repr(obj)


def _slot_summary(state: dict | None) -> dict | None:
    if state is None:
        return None
    return {
        key: _summary(value)
        for key, value in state.items()
        if key in ("clock", "terms", "task", "num_envs", "written_at_iter", "payload_version")
    }


def _counter(env) -> int | None:
    env = _unwrap(env)
    return int(getattr(env, "common_step_counter", -1))


def _unwrap(env):
    from rl_exp.tasks.curriculum_state import _unwrap as unwrap

    return unwrap(env)


def _registered_terms(env) -> list[str]:
    """The env's registered stateful curriculum terms (positive signal for c_k-only lines)."""
    try:
        from rl_exp.tasks.curriculum_state import covered_terms

        return sorted(covered_terms(_unwrap(env)))
    except Exception:  # noqa: BLE001
        return []


def _c_k(env) -> float | None:
    try:
        from rl_exp.tasks.teacher_mdp import ck_value

        return round(float(ck_value(_unwrap(env))), 12)
    except Exception:  # noqa: BLE001
        return None


def _term_instances(env) -> list:
    """The registered stateful curriculum terms of this env (production registry)."""
    try:
        from rl_exp.tasks.curriculum_state import covered_terms

        return [term for _adapter, term in covered_terms(_unwrap(env)).values()]
    except Exception:  # noqa: BLE001
        return []


def _install_step_hook(runner) -> None:
    """Per-env-step counter check + P2 (the state right after the wrapper's first reset)."""
    from rl_exp.tasks.curriculum_state import collect

    raw = _unwrap(runner.env)
    steps = _records.setdefault("steps", {"deltas": {}, "bad": [], "nonfinite": 0, "n": 0})
    real_step = raw.step

    def step_wrapped(actions, *args, **kwargs):
        if "p2" not in _records:
            # the wrapper ran the first full reset in its constructor: this is the first
            # moment after that reset and before any policy step
            _records["p2"] = {"counter": _counter(raw), "collect": _slot_summary(collect(raw))}
            _log("P2", counter=_counter(raw), note="after the first full reset, before any step")
        before = raw.common_step_counter
        out = real_step(actions, *args, **kwargs)
        after = raw.common_step_counter
        delta = after - before
        steps["deltas"][str(delta)] = steps["deltas"].get(str(delta), 0) + 1
        steps["n"] += 1
        if delta != 1:
            steps["bad"].append({"before": before, "after": after})
        pending = _records.pop("pending_next_eval", None)
        if pending is not None:
            # the term call ran inside this step; the production __call__ has re-armed the
            # schedule by now, so this is the real post-update next_eval_step
            name, event = pending
            for instance in _term_instances(raw):
                if type(instance).__name__ == name:
                    event["next_eval_after"] = int(getattr(instance, "_next_eval_step", -1))
                    break
        import torch

        obs, rew = out[0], out[1]
        if not (torch.isfinite(_flatten_torch(obs)).all() and torch.isfinite(_flatten_torch(rew)).all()):
            steps["nonfinite"] += 1
        return out

    raw.step = step_wrapped
    _records["installed"].append("env.step")


def _flatten_torch(obj):
    import torch

    if torch.is_tensor(obj):
        return obj.float()
    if isinstance(obj, dict):
        return torch.cat([_flatten_torch(v).reshape(-1) for v in obj.values()]) if obj else torch.zeros(0)
    if isinstance(obj, (list, tuple)):
        return torch.cat([_flatten_torch(v).reshape(-1) for v in obj]) if obj else torch.zeros(0)
    return torch.zeros(0)


def _install_update_hook(runner) -> None:
    """Optimizer updates: count, loss finiteness, parameter movement, Adam step counter."""
    alg = runner.alg
    upd = _records.setdefault("updates", {"count": 0, "opt_steps": [], "losses": [], "param_moved": []})
    real_update = alg.update

    def update_wrapped(*args, **kwargs):
        before = _params_digest(alg)
        out = real_update(*args, **kwargs)
        upd["count"] += 1
        upd["opt_steps"].append(_optimizer_steps(alg))
        upd["param_moved"].append(_params_digest(alg) != before)
        upd["losses"].append({k: round(float(v), 6) for k, v in dict(out).items()})
        _maybe_flush(force=True)
        return out

    alg.update = update_wrapped
    _records["installed"].append("alg.update")


def _params_digest(alg) -> str:
    parts = []
    for name in ("_raw_actor", "_raw_critic", "actor", "critic"):
        module = getattr(alg, name, None)
        if module is not None and hasattr(module, "state_dict"):
            for key, value in module.state_dict().items():
                parts.append(f"{name}.{key}:{_tensor_digest(value)}")
            break
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def _optimizer_steps(alg) -> int:
    import torch

    optimizer = getattr(alg, "optimizer", None)
    if optimizer is None:
        return -1
    total = 0
    for value in optimizer.state.values():
        step = value.get("step")
        if torch.is_tensor(step):
            total += int(step.float().sum())
        elif isinstance(step, (int, float)):
            total += int(step)
    return total


def _install_curriculum_hooks() -> None:
    """Count the REAL curriculum updates and re-check their legality right after they run."""
    from rl_exp.tasks import teacher_mdp

    events: list = _records.setdefault("curriculum_updates", [])

    def wrap(cls, method_name: str) -> None:
        real = getattr(cls, method_name)

        def wrapped(self, *args, **kwargs):
            env = self._env
            before_next = int(getattr(self, "_next_eval_step", -1))
            out = real(self, *args, **kwargs)
            events.append(
                {
                    "term": method_name,
                    "class": type(self).__name__,
                    "clock": getattr(env, "common_step_counter", None),
                    "next_eval_before": before_next,
                    # the production __call__ re-arms next_eval_step AFTER this method
                    # returns, so it is read back on the enclosing env.step (see below)
                    "next_eval_after": None,
                    "legal": _legality(self, env),
                }
            )
            _records["pending_next_eval"] = [type(self).__name__, events[-1]]
            _records["p3"] = {"counter": getattr(env, "common_step_counter", None), "collect": _slot_summary(_collect(env))}
            _maybe_flush(force=True)
            return out

        setattr(cls, method_name, wrapped)

    wrap(teacher_mdp.SpawnWeightSIRTerrainCurriculum, "_resample")
    wrap(teacher_mdp.JointSIRTerrainCurriculum, "_resample_all")
    _records["installed"].append("curriculum update")


def _collect(env):
    from rl_exp.tasks.curriculum_state import collect

    return collect(_unwrap(env))


def _legality(term, env) -> dict:
    """Post-update legality in the production terms' own terms (indices, weights, labels)."""
    import torch

    out: dict = {"ok": True, "problems": []}
    joint = hasattr(term, "_n_pairs") and hasattr(term, "_env_pair")
    counts = term._n_pairs if joint else [term._num_rows] * term._num_types
    for ti, count in enumerate(counts):
        weight = term._estimate[ti] if joint else term._weights[ti]
        if joint:
            # the joint term keeps a raw band-probability estimate, not a sampling
            # distribution (review 2026-09-16 #4), so the legality check is a range
            if float(weight.min()) < -1e-6 or float(weight.max()) > 1.0 + 1e-6:
                out["problems"].append(
                    f"estimate[{ti}] range [{float(weight.min()):.4f}, {float(weight.max()):.4f}] outside [0, 1]"
                )
        elif abs(float(weight.sum()) - 1.0) > 1e-6:
            out["problems"].append(f"weights[{ti}] sums to {float(weight.sum()):.6f}")
        part = term._particles[ti]
        if int(part.min()) < 0 or int(part.max()) >= count:
            out["problems"].append(f"particles[{ti}] range [{int(part.min())},{int(part.max())}] outside [0,{count})")
        if joint:
            hist = term._history[ti]
            if int(hist.min()) < 0 or int(hist.max()) >= count:
                out["problems"].append(f"history[{ti}] outside [0,{count})")
    if joint:
        env_pair = term._env_pair
        total_pairs = int(sum(term._n_pairs))
        if int(env_pair.min()) < 0 or int(env_pair.max()) >= total_pairs:
            out["problems"].append(f"env_pair range [{int(env_pair.min())},{int(env_pair.max())}] / {total_pairs}")
        if not torch.isfinite(term.desired_vel).all():
            out["problems"].append("desired_vel not finite")
    else:
        env_type = term._env_type
        if int(env_type.min()) < 0 or int(env_type.max()) >= term._num_types:
            out["problems"].append(f"env_type range [{int(env_type.min())},{int(env_type.max())}]")
    out["ok"] = not out["problems"]
    return out


def _install_load_hook() -> None:
    """Model/optimizer restore evidence: compare the live module against the file itself."""
    import torch
    from rsl_rl.runners.on_policy_runner import OnPolicyRunner

    real_load = OnPolicyRunner.load

    def load_wrapped(self, path, *args, **kwargs):
        saved = torch.load(path, map_location="cpu", weights_only=False)
        out = real_load(self, path, *args, **kwargs)
        alg = self.alg
        report: dict = {"path": os.path.abspath(path), "checkpoint_iter": saved.get("iter")}
        report["current_learning_iteration"] = int(getattr(self, "current_learning_iteration", -1))
        for attr, key in (("_raw_actor", "actor_state_dict"), ("_raw_critic", "critic_state_dict")):
            module = getattr(alg, attr, None)
            if module is None or key not in saved:
                report[key] = "unavailable"
                continue
            live = module.state_dict()
            mismatched = [k for k, v in saved[key].items() if k not in live or not torch.equal(live[k].cpu(), v.cpu())]
            missing = [k for k in live if k not in saved[key]]
            report[key] = {"keys": len(live), "mismatched": mismatched[:8], "n_mismatched": len(mismatched),
                           "n_extra_live": len(missing), "equal": not mismatched and not missing}
        live_opt = alg.optimizer.state_dict() if getattr(alg, "optimizer", None) is not None else None
        saved_opt = saved.get("optimizer_state_dict")
        if live_opt is None or saved_opt is None:
            report["optimizer_state_dict"] = "unavailable"
        else:
            groups = [
                {k: (list(v) if k == "params" else v) for k, v in g.items() if k != "params"}
                | {"n_params": len(g.get("params", []))}
                for g in live_opt["param_groups"]
            ]
            saved_groups = [
                {k: (list(v) if k == "params" else v) for k, v in g.items() if k != "params"}
                | {"n_params": len(g.get("params", []))}
                for g in saved_opt["param_groups"]
            ]
            state_keys = set(map(str, saved_opt["state"]))
            live_keys = set(map(str, live_opt["state"]))
            state_equal = True
            for key in sorted(state_keys & live_keys):
                for field, value in saved_opt["state"][int(key)].items():
                    other = live_opt["state"][int(key)].get(field)
                    if not (torch.is_tensor(value) and torch.is_tensor(other) and torch.equal(value.cpu(), other.cpu())):
                        if value != other:
                            state_equal = False
            report["optimizer_state_dict"] = {
                "param_groups_equal": groups == saved_groups,
                "state_entries": {"saved": len(state_keys), "live": len(live_keys), "tensors_equal": state_equal},
            }
        _records["load"] = report
        _log("load", **{k: v for k, v in report.items() if k in ("checkpoint_iter", "current_learning_iteration")})
        return out

    OnPolicyRunner.load = load_wrapped
    _records["installed"].append("runner.load")


def _install_apply_hook() -> None:
    from rl_exp.tasks import curriculum_state as cstate

    real_apply = cstate.apply_resume_state

    def apply_wrapped(env, resume_path, *args, **kwargs):
        _records["p0"] = {"counter": _counter(env), "collect": _slot_summary(_collect(env))}
        _log("P0", counter=_counter(env), note="before the restore (fresh env, no full reset yet)")
        outcome = real_apply(env, resume_path, *args, **kwargs)
        _records["payload"] = {
            "path": os.path.abspath(resume_path),
            "mtime": round(os.path.getmtime(resume_path), 3),
            "outcome": outcome,
        }
        _records["p1"] = {"counter": _counter(env), "collect": _slot_summary(_collect(env))}
        _log("P1", counter=_counter(env), outcome_status=outcome.get("status"))
        return outcome

    cstate.apply_resume_state = apply_wrapped
    _records["installed"].append("apply_resume_state")


def _install_learn_hook() -> None:
    from rsl_rl.runners.on_policy_runner import OnPolicyRunner

    real_learn = OnPolicyRunner.learn

    def learn_wrapped(self, num_learning_iterations, *args, **kwargs):
        _records["terms"] = sorted(_registered_terms(self.env))
        _records["learn_enter"] = {
            "requested": int(num_learning_iterations),
            "current_learning_iteration": int(getattr(self, "current_learning_iteration", -1)),
            "num_envs": int(getattr(self.env, "num_envs", -1)),
            "counter": _counter(self.env),
            "c_k": _c_k(self.env),
            "kwargs": {k: v for k, v in kwargs.items() if isinstance(v, (int, float, bool, str))},
        }
        _records["run_dir"] = str(getattr(getattr(self, "logger", None), "log_dir", "") or "")
        _install_step_hook(self)
        _install_update_hook(self)
        out = real_learn(self, num_learning_iterations, *args, **kwargs)
        _records["learn_exit"] = {
            "current_learning_iteration": int(getattr(self, "current_learning_iteration", -1)),
            "counter": _counter(self.env),
            "c_k": _c_k(self.env),
        }
        _maybe_flush(force=True)
        return out

    OnPolicyRunner.learn = learn_wrapped
    _records["installed"].append("runner.learn")


def _target() -> str | None:
    """The dump directory; cmd's ``set VAR=value &&`` leaves a trailing space, so strip it."""
    value = os.environ.get(ENV_VAR)
    return value.strip() if value else None


def _maybe_flush(force: bool = False) -> None:
    """Write the record out as we go.

    ``atexit`` is NOT enough: the Omniverse launcher teardown exits the process in a way
    that skips it (observed on the first smoke run -- install printed, no file appeared),
    so every event and a throttled step counter rewrites the JSON instead.
    """
    if force:
        _write()
        return
    steps = _records.get("steps", {}).get("n")
    if steps is not None and steps % 64 == 0:
        _write()


def _write() -> None:
    target = _target()
    if not target:
        return
    try:
        path = pathlib.Path(target)
        path.mkdir(parents=True, exist_ok=True)
        out = path / f"observe_{os.getpid()}.json"
        out.write_text(json.dumps(_records, indent=1, sort_keys=True), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"[cstate-observer] flush failed for {target!r}: {exc!r}")


def _flush() -> None:
    _write()
    print(f"[cstate-observer] wrote observe_{os.getpid()}.json under {_target()!r}")


def install() -> None:
    """Idempotent; no-op unless RL_CSTATE_OBSERVE is set (the trainer exports it)."""
    global _installed
    if _installed or not os.environ.get(ENV_VAR):
        return
    if "train.py" not in " ".join(sys.argv):
        return  # a child process of the launcher: not the trainer we are observing
    _installed = True
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    atexit.register(_flush)
    try:
        _install_apply_hook()
        _install_load_hook()
        _install_learn_hook()
        _install_curriculum_hooks()
    except Exception as exc:  # noqa: BLE001 -- never break the run we are observing
        _log("install_failed", error=repr(exc))
    _log("installed", versions={"torch": _torch_version()}, cwd=os.getcwd())
    print(f"[cstate-observer] installed: {_records['installed']} (json -> {ENV_VAR})")


def _torch_version() -> str:
    try:
        import torch

        return torch.__version__
    except Exception:  # noqa: BLE001
        return "unavailable"
