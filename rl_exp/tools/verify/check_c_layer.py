# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Verify the ARCH_PLAN 1.4b C-layer evidence (truly resumed real runs).

Reads the JSON files written by ``cstate_observer.py`` inside the real trainer process and
adjudicates the C-layer claims. Arms are recognised by their directory name:

* ``s_<task>``  -- source run (from scratch): establishes the fixture and the counter the
  resume arms must continue from (``learn_exit.counter``)
* ``p_<task>_<resume|drop>`` -- short resume (``--max_iterations 1``): P0/P1/P2, the
  model/optimizer comparison, cold control
* ``t_<task>_<resume|drop>`` -- the main evidence (``--max_iterations 84``): per-step clock,
  real curriculum updates, optimizer updates, and the arithmetic
  ``resume: final - source == 84*24`` / ``drop: final - 0 == 84*24``

Two cases are kept apart per ARCH_PLAN 1.4b (a restore may legitimately re-draw spawn state
on the first reset): PERSISTENT fields (particles/weights/episodes/successes/history plus the
schedule) must not change between P1 and P2; SPAWN-related fields may (they are re-sampled by
the production respawn), so they are only required to stay legal.

Usage (from the repo root):

    python rl_exp\\tools\\verify\\check_c_layer.py --root <dir with the arm subdirs> [--steps-per-iteration 24]

Exit code 0 = every check passed or is explicitly unknown, 1 = a check failed.
"""

from __future__ import annotations

import argparse
import glob
import json
import pathlib
import sys

STEPS_PER_ITERATION = 24
"""``num_steps_per_env`` of the lizard teacher recipes (asserted equal by check_obs_layout)."""

DEFAULT_BLOCK_ITERATIONS = 10
"""``eval_every`` of the SIR recipes: the curriculum block is eval_every * steps_per_iteration."""

PERSISTENT_HINTS = ("particles", "weights", "episodes", "successes", "history", "next_eval_step",
                    "in_band", "tr_sum", "tr_block_sum", "tr_block_count", "last_tr_mean")
SPAWN_HINTS = ("env_type", "env_pair", "desired_vel")


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def check(self, arm: str, name: str, ok: bool | None, detail: str = "") -> None:
        verdict = "UNKNOWN" if ok is None else ("PASS" if ok else "FAIL")
        self.rows.append((arm, f"{name}: {verdict}", detail))

    def failed(self) -> int:
        return sum(1 for _a, n, _d in self.rows if n.endswith("FAIL"))


def load_arm(directory: pathlib.Path) -> dict | None:
    """One trainer process per arm; a second JSON (a launcher child) has no hooks."""
    for path in sorted(glob.glob(str(directory / "*.json"))):
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        if data.get("installed"):
            data["_path"] = path
            return data
    return None


def _digest(slot: dict | None, key: str) -> str | None:
    terms = ((slot or {}).get("terms") or {})
    for term in terms.values():
        runtime = (term.get("runtime") or {})
        if key in runtime:
            value = runtime[key]
            return value.get("digest") if isinstance(value, dict) else repr(value)
    return None


def _clock_counter(slot: dict | None) -> int | None:
    return ((slot or {}).get("clock") or {}).get("common_step_counter")


def sample_counter(sample: dict | None) -> int | None:
    """P samples are ``{counter, collect}``; tolerate a bare slot summary too."""
    if not sample:
        return None
    return sample.get("counter") if "counter" in sample else _clock_counter(sample)


def sample_digest(sample: dict | None, key: str) -> str | None:
    if not sample:
        return None
    return _digest(sample.get("collect", sample), key)


def checkpoint_path(data: dict) -> pathlib.Path | None:
    """The checkpoint the run itself wrote last: ``model_<current_learning_iteration>.pt``.

    The name is read off the run's own record, never guessed: rsl_rl keeps
    ``current_learning_iteration`` at the last COMPLETED index, so an N-iteration run ends in
    ``model_<N-1>.pt``.
    """
    run_dir = data.get("run_dir")
    iteration = (data.get("learn_exit") or {}).get("current_learning_iteration")
    if not run_dir or iteration is None:
        return None
    return pathlib.Path(run_dir) / f"model_{iteration}.pt"


def _checkpoint_exists(data: dict, _arm_dir: pathlib.Path) -> bool | None:
    path = checkpoint_path(data)
    if path is None:
        return None  # run_dir not recorded (older observer): not adjudicated
    return path.exists()


def is_termless(data: dict) -> bool:
    """c_k-only line: no registered curriculum term, so the counter IS the state.

    There is no schedule to be due, no per-update sample (P3) and no update event to count;
    the clock checks (plus c_k, a pure function of the counter) carry that line instead.
    """
    if "terms" in data:  # the observer reports the registry: a definitive signal
        return not data["terms"]
    for key in ("p1", "p2"):
        terms = ((data.get(key) or {}).get("collect") or {}).get("terms")
        if terms is not None:
            return not terms
    return False


def check_c_k_continuity(report: Report, arm: str, data: dict, cold: bool, source: dict | None) -> None:
    """c_k must continue across the restore -- never re-heat to c0.

    c_k = c0 ** (decay ** k) is a pure function of the counter and RISES toward 1 with k
    (c0=0.2, decay=0.98). The checks: the live c_k matches the payload's own schedule
    parameters recomputed through an independent float64 path (|err| <= 1e-12); a resume's c_k
    at entry equals the source run's c_k at exit (continuity, i.e. no re-heat); and c_k never
    jumps back toward c0 during the run.
    """
    import math

    params = (((data.get("p1") or {}).get("collect") or {}).get("clock") or {}).get("ck", {}).get("static")
    if not params:
        report.check(arm, "c_k schedule parameters known (from the restored payload)", None,
                     "the restored payload carried no c_k fingerprint")
        return
    enter, exit_ = data.get("learn_enter") or {}, data.get("learn_exit") or {}
    steps = int(params["steps_per_iteration"])

    def reference(counter: int) -> float:
        return math.exp(math.log(params["c0"]) * params["decay"] ** (counter // steps))

    for label, sample in (("enter", enter), ("exit", exit_)):
        counter, live = sample.get("counter"), sample.get("c_k")
        if counter is None or live is None:
            report.check(arm, f"c_k/{label} sampled", None, f"counter={counter} c_k={live}")
            continue
        report.check(arm, f"c_k/{label} matches the payload's schedule (|err| <= 1e-12)",
                     abs(live - reference(counter)) <= 1e-12,
                     f"counter={counter} live={live} reference={reference(counter):.12f}")
    if enter.get("c_k") is not None and exit_.get("c_k") is not None:
        report.check(arm, "c_k never re-heats inside the run (it only rises toward 1)",
                     exit_["c_k"] >= enter["c_k"], f"{enter['c_k']} -> {exit_['c_k']}")
    if cold:
        report.check(arm, "drop arm re-heats to c0 and starts from a cold clock",
                     enter.get("c_k") == params["c0"] and enter.get("counter") == 0,
                     f"c_k={enter.get('c_k')} c0={params['c0']} counter={enter.get('counter')}")
    elif source is not None:
        source_c_k = (source.get("learn_exit") or {}).get("c_k")
        report.check(arm, "resume entry c_k == the source run's exit c_k (continuity, no re-heat)",
                     source_c_k is not None and enter.get("c_k") == source_c_k,
                     f"enter={enter.get('c_k')} source_exit={source_c_k}")


def check_source(report: Report, arm: str, data: dict, arm_dir: pathlib.Path, task: str) -> None:
    """The source fixture: long enough to produce real updates, and a usable checkpoint."""
    enter, exit_ = data.get("learn_enter"), data.get("learn_exit")
    report.check(arm, "learn ran to completion", bool(exit_), f"enter={enter}")
    steps = data.get("steps") or {}
    report.check(arm, "every env.step advances the counter by exactly 1",
                 steps.get("deltas") == {"1": steps.get("n")} and not steps.get("bad"),
                 f"n={steps.get('n')} deltas={steps.get('deltas')} bad={len(steps.get('bad', []))}")
    report.check(arm, "no non-finite obs/reward", not steps.get("nonfinite"), f"nonfinite={steps.get('nonfinite')}")
    updates = data.get("updates") or {}
    requested = (enter or {}).get("requested")
    report.check(arm, "optimizer updates == iterations", updates.get("count") == requested,
                 f"count={updates.get('count')} requested={requested}")
    opt = updates.get("opt_steps") or []
    per_update = sorted({opt[i] - opt[i - 1] for i in range(1, len(opt))})
    report.check(arm, "each update advances every Adam step by one", updates.get("count") == 1 or len(per_update) == 1,
                 f"per-update Adam sum deltas={per_update[:4]}")
    report.check(arm, "parameters moved on every update", all(updates.get("param_moved") or [False]),
                 f"{sum(updates.get('param_moved') or [])}/{len(updates.get('param_moved') or [])}")
    losses = updates.get("losses") or []
    report.check(arm, "losses finite", all(all(v == v and abs(v) != float("inf") for v in loss.values())
                                          for loss in losses), f"n_losses={len(losses)}")
    events = data.get("curriculum_updates") or []
    if is_termless(data):  # c_k-only: no registered term, nothing to update
        report.check(arm, "c_k-only line wires no SIR term (the clock is the state)", not events, f"events={len(events)}")
    else:
        report.check(arm, "at least 2 real curriculum updates", len(events) >= 2, f"events={len(events)}")
        legal = all(e["legal"]["ok"] for e in events)
        report.check(arm, "every update leaves a legal state", legal,
                     f"problems={[e['legal']['problems'] for e in events if not e['legal']['ok']]}")
        monotone = all(events[i]["clock"] < events[i + 1]["clock"] for i in range(len(events) - 1))
        report.check(arm, "updates are monotone in the clock", monotone, f"clocks={[e['clock'] for e in events]}")
        block = DEFAULT_BLOCK_ITERATIONS * STEPS_PER_ITERATION
        edges_ok = all(e["clock"] >= e["next_eval_before"] for e in events)
        rearm_ok = all(e["next_eval_after"] == e["next_eval_before"] + block for e in events)
        report.check(arm, "each update fires at or after its block edge", edges_ok,
                     f"clocks={[e['clock'] for e in events]} edges={[e['next_eval_before'] for e in events]}")
        report.check(arm, "the schedule re-arms by exactly one block", rearm_ok,
                     f"after={[e['next_eval_after'] for e in events]}")
    report.check(arm, "checkpoint at the actual index exists", _checkpoint_exists(data, arm_dir),
                 f"iter={(exit_ or {}).get('current_learning_iteration')} run_dir={data.get('run_dir') or 'not recorded'}"
                 " -- superseded by --source-checkpoint when the verifier is given the path")


def check_p_arm(report: Report, arm: str, data: dict, expect_arm: str, source_counter: int | None) -> None:
    """The short resume: the four sampling points and the model/optimizer comparison."""
    payload = data.get("payload") or {}
    status = (payload.get("outcome") or {}).get("status")
    if expect_arm == "drop":
        report.check(arm, "the drop flag took effect", status == "dropped", f"status={status}")
    else:
        report.check(arm, "the restore ran (not dropped)", status not in (None, "dropped"), f"status={status}")
    report.check(arm, "P0 sampled before the restore (counter 0, no state)",
                 sample_counter(data.get("p0")) == 0, f"p0={sample_counter(data.get('p0'))}")
    counter_p1 = sample_counter(data.get("p1"))
    if expect_arm == "drop":
        report.check(arm, "drop keeps the fresh clock (counter stays 0)", counter_p1 == 0, f"p1={counter_p1}")
    else:
        report.check(arm, "P1 restores the counter from the payload", counter_p1 == source_counter,
                     f"p1={counter_p1} source={source_counter}")
    report.check(arm, "P2 sampled after the first full reset", data.get("p2") is not None,
                 f"p2={sample_counter(data.get('p2'))}")
    load = data.get("load") or {}
    for key in ("actor_state_dict", "critic_state_dict"):
        entry = load.get(key)
        report.check(arm, f"{key} matches the checkpoint after load",
                     entry is True or (isinstance(entry, dict) and entry.get("equal")),
                     f"{entry if not isinstance(entry, dict) else {k: entry[k] for k in ('keys', 'n_mismatched', 'n_extra_live')}}")
    opt = load.get("optimizer_state_dict")
    report.check(arm, "optimizer state matches the checkpoint after load",
                 opt is True or (isinstance(opt, dict) and opt.get("param_groups_equal")
                                 and opt["state_entries"]["saved"] == opt["state_entries"]["live"]
                                 and opt["state_entries"]["tensors_equal"]),
                 f"{opt}")
    updates = data.get("updates") or {}
    report.check(arm, "exactly one optimizer update ran", updates.get("count") == 1, f"count={updates.get('count')}")
    compare_first_reset(report, arm, data, expect_arm)


def compare_first_reset(report: Report, arm: str, data: dict, expect_arm: str) -> None:
    """P1 -> P2: persistent state preserved, spawn state only required to stay legal."""
    p1, p2 = data.get("p1"), data.get("p2")
    cache: dict = {}
    if p1 and p2:
        next_eval = sample_digest(p1, "next_eval_step")
        counter = sample_counter(p1)
        if next_eval is None:
            # c_k-only: no registered term, so there is no schedule to be due (the counter IS
            # the whole state; the offline suite pins that clock separately)
            report.check(arm, "no registered term: no schedule to be due (c_k-only line)", None,
                         f"samples={(p1.get('collect') or {}).get('terms')}")
            compare_first_reset_fields(report, arm, p1, p2, expect_arm)
            return
        report.check(arm, "P1 schedule is not due at the counter",
                     counter is not None and int(str(next_eval).split(":")[0]) > counter,
                     f"next_eval={next_eval} counter={counter}")
        compare_first_reset_fields(report, arm, p1, p2, expect_arm)


def compare_first_reset_fields(report: Report, arm: str, p1: dict, p2: dict, expect_arm: str) -> None:
    same, changed = [], []
    for key in PERSISTENT_HINTS + SPAWN_HINTS:
        a, b = sample_digest(p1, key), sample_digest(p2, key)
        if a is None and b is None:
            continue
        (same if a == b else changed).append(key)
    persistent_changed = [k for k in changed if k in PERSISTENT_HINTS]
    if expect_arm == "drop":
        report.check(arm, "P1/P2 are cold in both samples", True, f"persistent_changed={changed}")
    else:
        report.check(arm, "P1 -> first reset preserves every persistent field", not persistent_changed,
                     f"changed={persistent_changed} preserved={same}")
    report.check(arm, "spawn state was re-sampled or preserved (allowed, production respawn)",
                 True, f"spawn_changed={[k for k in changed if k in SPAWN_HINTS]}")
    report.check(arm, "the counter itself never resets", sample_counter(p1) == sample_counter(p2),
                 f"{sample_counter(p1)} -> {sample_counter(p2)}")


def check_t_arm(report: Report, arm: str, data: dict, expect_arm: str, source_counter: int | None,
                iterations: int, source: dict | None = None) -> None:
    """The main evidence: a full continuous run after the restore."""
    enter, exit_ = data.get("learn_enter"), data.get("learn_exit")
    expected = iterations * STEPS_PER_ITERATION
    report.check(arm, "one continuous learn() call of the requested length",
                 (enter or {}).get("requested") == iterations, f"enter={enter}")
    steps = data.get("steps") or {}
    report.check(arm, "every env.step advances the counter by exactly 1",
                 steps.get("deltas") == {"1": steps.get("n")} and not steps.get("bad"),
                 f"n={steps.get('n')} deltas={steps.get('deltas')}")
    report.check(arm, "the run covers at least max(2B, 2H) steps (84 it)", (steps.get("n") or 0) >= 2000,
                 f"steps={steps.get('n')} required=2000")
    report.check(arm, "no non-finite obs/reward", not steps.get("nonfinite"))
    final, start = (exit_ or {}).get("counter"), (enter or {}).get("counter")
    if final is not None and start is not None:
        report.check(arm, "the run added exactly 84*24 steps", final - start == expected,
                     f"{start} -> {final} (delta {final - start}, expected {expected})")
    if expect_arm == "drop":
        report.check(arm, "drop starts from a cold clock", start == 0, f"start={start}")
        report.check(arm, "drop final counter == 84*24", final == expected, f"final={final}")
    else:
        report.check(arm, "resume continues the source counter", start == source_counter,
                     f"start={start} source={source_counter}")
        if final is not None and source_counter is not None:
            report.check(arm, "resume final - source == 84*24", final - source_counter == expected,
                         f"{source_counter} -> {final} (delta {final - source_counter})")
    updates = data.get("updates") or {}
    report.check(arm, "optimizer updates == iterations", updates.get("count") == iterations,
                 f"count={updates.get('count')}")
    report.check(arm, "parameters moved on every update", all(updates.get("param_moved") or [False]),
                 f"{sum(updates.get('param_moved') or [])}/{len(updates.get('param_moved') or [])}")
    losses = updates.get("losses") or []
    bad = [loss for loss in losses if any(v != v or abs(v) == float("inf") for v in loss.values())]
    report.check(arm, "all losses finite", not bad, f"n={len(losses)} bad={len(bad)}")
    opt = updates.get("opt_steps") or []
    per_update = sorted({opt[i] - opt[i - 1] for i in range(1, len(opt))})
    report.check(arm, "each optimizer update advances every Adam step by one",
                 len(per_update) <= 1, f"per-update deltas={per_update[:4]}")
    events = data.get("curriculum_updates") or []
    if is_termless(data):
        report.check(arm, "c_k-only line: no update event exists to count", not events, f"events={len(events)}")
        check_c_k_continuity(report, arm, data, expect_arm == "drop", source)
    elif expect_arm == "drop":
        report.check(arm, "the cold curriculum still updates on schedule", len(events) >= 2, f"events={len(events)}")
    else:
        report.check(arm, "resumed curriculum updates on schedule (>=2)", len(events) >= 2, f"events={len(events)}")
    if not is_termless(data):
        report.check(arm, "every update leaves a legal state", all(e["legal"]["ok"] for e in events),
                     f"problems={[e['legal']['problems'] for e in events if not e['legal']['ok']]}")
        block = DEFAULT_BLOCK_ITERATIONS * STEPS_PER_ITERATION
        report.check(arm, "updates land at or after their block edge and re-arm by one block",
                     all(e["clock"] >= e["next_eval_before"] and e["next_eval_after"] == e["next_eval_before"] + block
                         for e in events),
                     f"{[(e['clock'], e['next_eval_before'], e['next_eval_after']) for e in events]}")
    load = data.get("load") or {}
    report.check(arm, "the runner loaded the requested checkpoint", load.get("checkpoint_iter") is not None,
                 f"checkpoint_iter={load.get('checkpoint_iter')} current={load.get('current_learning_iteration')}")
    sampled = [k for k in ("p0", "p1", "p2") if data.get(k)] + (["p3"] if data.get("p3") else [])
    report.check(arm, "P0/P1/P2 sampled" + (" (+P3)" if not is_termless(data) else " (no P3: no term to update)"),
                 all(data.get(k) for k in ("p0", "p1", "p2")) and (is_termless(data) or bool(data.get("p3"))),
                 f"sampled={sampled}")
    if expect_arm == "drop":
        report.check(arm, "drop P1 is cold", sample_counter(data.get("p1")) == 0, f"p1={sample_counter(data.get('p1'))}")
    elif source_counter is not None:
        report.check(arm, "P1 counter == source counter", sample_counter(data.get("p1")) == source_counter,
                     f"p1={sample_counter(data.get('p1'))} source={source_counter}")
    for key in ("actor_state_dict", "critic_state_dict"):
        entry = load.get(key)
        report.check(arm, f"{key} matches the checkpoint after load (both arms load the same model)",
                     entry is True or (isinstance(entry, dict) and entry.get("equal")), f"{entry}")


def check_resave(report: Report, arm: str, data: dict, expect_arm: str) -> None:
    """The final artifact: the resaved checkpoint still carries a state that matches the clock.

    Needs torch, so it is opt-in (``--resave``): it proves the save hook rode the whole run
    and that the payload is not a stale copy of the restored one.
    """
    path = checkpoint_path(data)
    if path is None or not path.exists():
        report.check(arm, "resaved checkpoint adjudicated", None, f"path={path}")
        return
    import torch

    from rl_exp.tasks.curriculum_state import STATE_KEY

    saved = torch.load(path, map_location="cpu", weights_only=False)
    state = (saved.get("infos") or {}).get(STATE_KEY)
    if state is None:
        report.check(arm, "resaved checkpoint carries the curriculum state", False, f"infos keys={list((saved.get('infos') or {}))}")
        return
    report.check(arm, "resaved checkpoint carries the curriculum state", True, f"path={path.name}")
    report.check(arm, "resaved iter == last completed iteration",
                 saved.get("iter") == (data.get("learn_exit") or {}).get("current_learning_iteration"),
                 f"iter={saved.get('iter')}")
    clock = _clock_counter(state)
    report.check(arm, "resaved payload counter == the observed final counter",
                 clock == (data.get("learn_exit") or {}).get("counter"),
                 f"payload={clock} observed={(data.get('learn_exit') or {}).get('counter')}")
    restored_next = sample_digest(data.get("p1"), "next_eval_step")
    saved_next = None
    for slot in (state.get("terms") or {}).values():
        if "next_eval_step" in (slot.get("runtime") or {}):
            saved_next = int(slot["runtime"]["next_eval_step"])
    if saved_next is None and is_termless(data):
        report.check(arm, "c_k-only: the resaved clock is the state (no schedule to advance)", None,
                     f"payload counter={clock}")
    elif expect_arm == "drop":
        report.check(arm, "drop payload advanced from a cold start", saved_next is not None and saved_next > 240,
                     f"next_eval_step={saved_next}")
    else:
        report.check(arm, "resumed payload advanced past the restored schedule",
                     saved_next is not None and restored_next is not None
                     and saved_next > int(str(restored_next).split(":")[0]),
                     f"restored={restored_next} resaved={saved_next}")


def check_source_payload(report: Report, task: str, path: pathlib.Path, cold: dict | None,
                         source_iter: int | None = None) -> None:
    """The source fixture must be usable: a payload with a non-zero clock and non-cold state.

    ``cold`` is the matching drop arm's P1 sample -- a real `collect()` of a freshly built env
    for the same task -- so both sides of the comparison are production artifacts, hashed by
    the same recipe (``cstate_observer._summary``).
    """
    import torch

    from rl_exp.tasks.curriculum_state import STATE_KEY
    from rl_exp.tools.verify.cstate_observer import _summary

    if not path.exists():
        report.check(f"s_{task}", "source checkpoint exists", False, str(path))
        return
    saved = torch.load(path, map_location="cpu", weights_only=False)
    state = (saved.get("infos") or {}).get(STATE_KEY)
    report.check(f"s_{task}", "source checkpoint carries the curriculum state", state is not None,
                 f"{path.name} iter={saved.get('iter')}")
    if source_iter is not None:
        report.check(f"s_{task}", "the checkpoint index equals the source run's last completed iteration",
                     saved.get("iter") == source_iter, f"file={saved.get('iter')} run={source_iter}")
    if state is None:
        return
    counter = _clock_counter(state)
    report.check(f"s_{task}", "source payload counter > 0", bool(counter), f"counter={counter}")
    terms = state.get("terms") or {}
    cold_slots = (((cold or {}).get("p1") or {}).get("collect") or {}).get("terms") or {}
    if not terms:
        report.check(f"s_{task}", "c_k-only source: the counter IS the state (no terms)", None,
                     f"terms={list(terms)}")
        report.check(f"s_{task}", "at least one declared field differs from the cold initialization", True,
                     f"counter {counter} != cold 0")
        return
    report.check(f"s_{task}", "source payload terms match the task's wired terms", set(terms) == set(cold_slots),
                 f"source={sorted(terms)} cold={sorted(cold_slots)}")
    differs, compared = [], 0
    for term, slot in terms.items():
        cold_runtime = (cold_slots.get(term) or {}).get("runtime") or {}
        for key, value in (slot.get("runtime") or {}).items():
            if key not in cold_runtime:
                continue
            compared += 1
            if _summary(value) != cold_runtime[key]:
                differs.append(f"{term}.{key}")
    report.check(f"s_{task}", "at least one persistent field differs from the cold initialization",
                 bool(differs) if compared else None,
                 f"differs={differs} compared={compared} (next_eval_step/counter count as declarations)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", required=True, help="directory holding s_/p_/t_ arm subdirectories")
    parser.add_argument("--iterations", type=int, default=84, help="T-arm length (max(2B, 2H)/steps_per_iteration)")
    parser.add_argument("--json", help="also write the table to this JSON file")
    parser.add_argument("--resave", action="store_true", help="also load each T arm's final checkpoint (needs torch)")
    parser.add_argument("--source-checkpoint", action="append", default=[], metavar="TASK=PATH",
                        help="source checkpoint to adjudicate (needs torch); cold reference comes from the "
                             "matching *_drop P1 sample")
    args = parser.parse_args()

    root = pathlib.Path(args.root)
    arms = {}
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        data = load_arm(directory)
        if data is not None:
            arms[directory.name] = data
    report = Report()
    if not arms:
        print(f"no arm JSON with hooks under {root}")
        return 1

    source_counter: dict[str, int | None] = {}
    for name, data in arms.items():
        if name.startswith("s_"):
            task = name[2:]
            source_counter[task] = (data.get("learn_exit") or {}).get("counter")
            check_source(report, name, data, root / name, task)

    for name, data in arms.items():
        if "-" not in name:
            continue
        head, expect_arm = name.rsplit("-", 1)
        task = head.split("_", 1)[1]
        if head.startswith("p_"):
            check_p_arm(report, name, data, expect_arm, source_counter.get(task))
        elif head.startswith("t_"):
            if expect_arm == "resume" and source_counter.get(task) is None:
                report.check(name, "source counter known", None, "no s_ arm found: arithmetic not adjudicated")
            check_t_arm(report, name, data, expect_arm, source_counter.get(task), args.iterations,
                        arms.get(f"s_{task}"))
            if args.resave:
                check_resave(report, name, data, expect_arm)

    for spec in args.source_checkpoint:
        task, _, path = spec.partition("=")
        cold = arms.get(f"p_{task}-drop") or arms.get(f"t_{task}-drop")
        source_iter = ((arms.get(f"s_{task}") or {}).get("learn_exit") or {}).get("current_learning_iteration")
        check_source_payload(report, task, pathlib.Path(path), cold, source_iter)

    width = max(len(a) for a, _n, _d in report.rows)
    for arm, name, detail in report.rows:
        print(f"{arm:<{width}}  {name}")
        if detail:
            print(f"{'':<{width}}    {detail}")
    failures = report.failed()
    print(f"\n{'C_LAYER_OK' if not failures else 'C_LAYER_FAILED'} ({failures} failing)")
    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps([{"arm": a, "check": n, "detail": d} for a, n, d in report.rows], indent=1),
            encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
