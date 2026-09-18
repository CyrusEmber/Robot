# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Offline suite runner: the checks below, run in parallel.

Every check is its own interpreter, and two thirds of them import torch/isaaclab before
they prove anything (2.5 s of import before the first assertion). Run one after another,
the wall clock is the *sum* of that import; the checks share nothing -- separate
processes, separate temp dirs, read-only on the repo -- so it only has to be the slowest
wave.

The check list lives here and nowhere else. ``run_offline_checks.bat`` keeps the
host-python bootstrap and calls this, so adding a gate is one entry rather than an entry
plus a matching banner in a second file that can drift out of step with it.

What a check may touch is now a contract, not a habit: **read-only on the repo, or writing
only under its own temp dir**. Sequential execution used to hide a check that wrote a
shared path -- two files in one repo root, not an interleaving bug -- but in parallel that
becomes a race, so a new check that must write somewhere shared has to say so here rather
than assume the suite is serial.

The rules and the cost budgets are written down in ``OFFLINE_CHECKS.md`` (next to this
file): read it before adding a check. The shape gate ``check_suite_shape.py`` enforces the
static half of it, and the budgets below are enforced here because they need the timings.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import pathlib
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from typing import NamedTuple

_REPO = pathlib.Path(__file__).resolve().parents[3]
_V = "rl_exp/tools/verify"  # relative on purpose: every check expects the repo root as cwd


class Check(NamedTuple):
    """One scheduled process and the repository artifacts whose contracts it guards."""

    label: str
    argv: list[str]
    contract: tuple[str, ...]


# Positions are run-local: retirement may remove entries. Historical [i/N]
# references belong to the commit where they were recorded.
CHECKS: list[Check] = [
    Check("framework pin check (IsaacLab internals + pinned SHA)",
          [f"{_V}/framework_pin_check.py"], contract=("rl_exp/tasks/teacher_env_cfg.py",)),
    Check("freeze contracts (DR/wiring + robot block parity, DR lists, PLAY coverage, asset contract + locks)",
          [f"{_V}/check_dr_parity.py", "--strict"], contract=("rl_exp/tasks/teacher_env_cfg.py",)),
    Check("recovery vectorization parity",
          [f"{_V}/test_recovery_parity.py"], contract=("ablation_harness/components/recovery.py",)),
    Check("staged curriculum offline test",
          [f"{_V}/test_staged_curriculum.py"], contract=("rl_exp/tasks/staged_curriculum.py",)),
    Check("teacher split-encoder networks (forward/gradient/export/transfer)",
          [f"{_V}/test_teacher_networks.py"], contract=("rl_exp/tasks/teacher_networks.py",)),
    Check("student belief networks (GRU/gate/decoder/load_from_teacher)",
          [f"{_V}/test_student_networks.py"], contract=("rl_exp/tasks/student_networks.py",)),
    Check("v3 curriculum + ring pattern (c_k math, tilt predicate, geometry)",
          [f"{_V}/test_v3_curriculum.py"], contract=("rl_exp/versions/lizard/main/v3/main_params.yaml",)),
    Check("obs layout gate (group names, term order, c_k step consistency)",
          [f"{_V}/check_obs_layout.py"], contract=("rl_exp/tasks/obs_protocol.py",)),
    Check("v5 anti-collapse rewards (linear tracking / slip / belly / c_k scaling)",
          [f"{_V}/test_v5_rewards.py"], contract=("rl_exp/versions/lizard/main/v5/main_params.yaml",)),
    Check("v5.3 SIR terrain curriculum (band / resample / walk clamp / replay / throttle)",
          [f"{_V}/test_v5_terrain_sir.py"], contract=("rl_exp/versions/lizard/main/v5/main_params.yaml",)),
    Check("v11 joint SIR terrain curriculum (param grid / Eq.2-3-7 / fallback / walk / command)",
          [f"{_V}/test_joint_sir.py"], contract=("rl_exp/versions/lizard/main/v11/main_params.yaml",)),
    Check("version-record completeness (four-piece set / FAMILY row / FILEMAP row)",
          [f"{_V}/check_version_docs.py"], contract=("rl_exp/versions/lizard/FAMILY.md",)),
    Check("v12 height-ring noise model (conditions / scopes / outliers / c_k / mid redraw)",
          [f"{_V}/test_v12_noise.py"], contract=("rl_exp/versions/lizard/main/v12/main_params.yaml",)),
    Check("pre-kit pxr leak gate (P001/P003/P004: registry-resolved env cfg construction must stay pxr-clean)",
          [f"{_V}/check_pxr_leak.py", "--self-test"], contract=("rl_exp/tasks/recipe_tasks.py",)),
    Check("curriculum resume state (roundtrip / fingerprint / hard-abort / hook)",
          [f"{_V}/test_resume_state.py"], contract=("rl_exp/tasks/curriculum_state.py",)),
    Check("tb_scalars record sampling (max_points / first+last / CLI resample)",
          [f"{_V}/test_dump_tb_sampling.py"], contract=("rl_exp/tools/trainlog/dump_tb.py",)),
    Check("v13 symmetric tracking kernel (miki wired / EP gone / v5+v10 frozen)",
          [f"{_V}/check_reward_v13.py"], contract=("rl_exp/versions/lizard/main/v13/main_params.yaml",)),
    Check("v14 front-plant/roll fall gate (predicate / dwell / wiring / v13 frozen)",
          [f"{_V}/check_terminations_v14.py"], contract=("rl_exp/versions/lizard/main/v14/main_params.yaml",)),
    Check("acceptance metrics (yaw frame / abs sideslip / per-frame MAE / kernel frame contract)",
          [f"{_V}/test_acceptance_metrics.py"], contract=("ablation_harness/metrics.py",)),
    Check("eval frame contract v2 (terminal frame closes the fall window / v1 truncation)",
          [f"{_V}/test_eval_frame_v2.py"], contract=("ablation_harness/protocols/locomotion_eval_v2.yaml",)),
    Check("configclass field surface (params_version field vs to_dict vs own_fields)",
          [f"{_V}/check_configclass_fields.py", "--self-test"], contract=("rl_exp/tasks/recipe_tasks.py",)),
    Check("config snapshot serializer (order / floats / identities / paths / digest)",
          [f"{_V}/test_cfg_snapshot.py"], contract=("rl_exp/tools/verify/cfg_snapshot.py",)),
    Check("recipe golden lock (per-line entries vs versions/<line>/cfg_lock.json, shared baselines)",
          [f"{_V}/check_cfg_lock.py", "--self-test"], contract=("rl_exp/versions/cfg_baselines.json",)),
    Check("run manifest (T0/T1 record, checkpoint infos, external index, --verify)",
          [f"{_V}/test_run_manifest.py"], contract=("rl_exp/tools/runrecord/manifest.py",)),
    Check("isolation rebuild gate (material capture/refusal, sources, missing-file negative test)",
          [f"{_V}/test_rebuild_gate.py"], contract=("rl_exp/tools/runrecord/rebuild.py",)),
    Check("recipe line discovery (yaml/lock convention, refusals must fire)",
          [f"{_V}/test_recipe_lines.py"], contract=("rl_exp/tools/verify/recipe_lines.py",)),
    Check("recipe line lifecycle (identity / retirement evidence / binary status)",
          [f"{_V}/check_recipe_registry.py", "--self-test"], contract=("rl_exp/versions/lines.json",)),
    Check("recipe identity map (task id to recipe, revision to entries, vs registration + built configs)",
          [f"{_V}/check_recipe_map.py", "--self-test", "--bind-config"], contract=("rl_exp/versions/recipes.json",)),
    Check("suite banner hygiene (no bare redirects in echo lines; detector self-tested)",
          [f"{_V}/check_suite_banners.py"], contract=("rl_exp/tools/verify/run_offline_checks.bat",)),
    Check("params loaders hand each caller its own document (cache must not alias cfgs)",
          [f"{_V}/test_params_isolation.py"], contract=("rl_exp/tasks/recipe_params.py",)),
    Check("stage B acceptance baseline is still the frozen one (golden locks pinned by digest)",
          [f"{_V}/check_golden_frozen.py"], contract=("rl_exp/versions/cfg_baselines.json",)),
    Check("recipe lifecycle decision contract (verdicts / unknown status / refusal wording)",
          [f"{_V}/recipe_lifecycle.py"], contract=("rl_exp/versions/lines.json",)),
    Check("one writer per structural component (form per recipe version, no second writer)",
          [f"{_V}/test_component_ownership.py"], contract=("rl_exp/tasks/components.py",)),
    Check("suite shape (single list / entries exist / no undeclared interpreter children)",
          [f"{_V}/check_suite_shape.py"], contract=("rl_exp/tools/verify/offline_suite.py",)),
    Check("lifecycle startup gate (identity/status/curriculum flag; a refusal is a terminal record)",
          [f"{_V}/test_lifecycle_gate.py"], contract=("rl_exp/tools/runrecord/lifecycle.py",)),
    Check("launcher (directory-driven plan; its record must match the trainer's T0)",
          [f"{_V}/test_launcher.py"], contract=("rl_exp/tools/launch_recipe.py",)),
    Check("hard A: built recipes are field-for-field the frozen golden (declaration, no subclass)",
          [f"{_V}/check_recipe_build.py"], contract=("rl_exp/tasks/recipe.py",)),
    Check("obs protocol declaration (laid out as declared, self-consistent, digests approved)",
          [f"{_V}/check_obs_protocol.py", "--self-test"], contract=("rl_exp/versions/obs_protocols.json",)),
    Check("eval record format (three-state read / P04 substitutions / run-id reuse)",
          [f"{_V}/test_eval_record.py"], contract=("ablation_harness/record.py",)),
    Check("terrain split rule and record (hand-computed split / pairing identity / sanity refusals)",
          [f"{_V}/test_terrain_map.py"], contract=("rl_exp/tasks/terrain_map.py",)),
    Check("terrain split rule has one home (no reintroduced copy; detector self-tested)",
          [f"{_V}/check_terrain_split_source.py"], contract=("rl_exp/tasks/terrain_map.py",)),
    Check("split-probe wait (a foreign import must still land the patch; install() imports nothing)",
          [f"{_V}/check_split_probe_wait.py"], contract=("rl_exp/tools/verify/terrain_split_probe.py",)),
]


def default_jobs() -> int:
    """Workers to use: half the cores, so the import bursts do not thrash each other."""
    return max(1, min(6, (os.cpu_count() or 2) // 2))


# What stops the suite growing back into minutes (OFFLINE_CHECKS.md). A check is a process
# that pays an interpreter + torch import before its first assertion, so the cost of the
# suite is (how many checks) x (that import) + what a check does inside.
#
# Two different questions, two different mechanisms -- they are not substitutes:
#
# * ``PER_CHECK_BUDGET_S`` / ``SERIAL_BUDGET_S`` are **cost** control. Cost is measured
#   under load (a wave of six import bursts), so a breach is only ever a *suspect*: it is
#   re-measured with the machine quiet before anything is blamed, first per check (alone)
#   and then, if the total is the problem, the whole list at ``--jobs 1``. Raising a budget
#   is never the response to a load false alarm -- it is allowed only once the quiet number
#   is over budget too *and* the coverage that caused it is worth its price, in the same
#   commit as that check.
# * ``PER_CHECK_TIMEOUT_S`` is not cost control, it is "the suite has to end": budgets are
#   evaluated after the fact, so they cannot save you from a check that never returns.
#   Deliberately far above the cost budget, so that a slow check is reported as cost, not
#   killed as a hang.
PER_CHECK_BUDGET_S = 25.0
SERIAL_BUDGET_S = 205.0  # initial ratchet: reported 178 s wave + 15% headroom
SOLO_RECHECKS = 3  # breaching checks re-run alone, worst first, before they are suspect
PER_CHECK_TIMEOUT_S = 180.0
_DRAIN_TIMEOUT_S = 30.0  # bounded read after a kill, so a survivor cannot block the report
TIMEOUT_EXIT = 124  # GNU timeout's code: a killed check is never mistaken for a pass


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill a check *and everything it started*.

    Killing only the direct child is not enough: a grandchild that outlives its parent
    keeps the pipe open, so the ``communicate()`` that follows would block forever -- the
    suite would hang exactly where it is supposed to give up. On Windows that means
    taskkill on the whole tree.
    """
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except OSError:  # already gone, or not a process-group leader
        proc.kill()


def _run_one(interpreter: str, argv: list[str], stop: threading.Event) -> tuple[int | None, str, float]:
    """Run one check; returns (exit code, output, seconds), or (None, ...) when skipped.

    ``PYTHONIOENCODING`` keeps a check's non-ASCII verdict readable when it is captured
    rather than written straight to the console. The failure flag is set *here* rather
    than by the caller: the queue has to stop the moment a check turns red, not when the
    main thread gets round to reading its result. The timeout is the suite's promise to
    terminate, not a cost gate -- see the constants above.
    """
    if stop.is_set():
        return None, "", 0.0
    started = time.time()
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        proc = subprocess.Popen(
            [interpreter, *argv],
            cwd=str(_REPO),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # one pipe: a surviving writer cannot hold the other open
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        try:
            output, _ = proc.communicate(timeout=PER_CHECK_TIMEOUT_S)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            try:
                output, _ = proc.communicate(timeout=_DRAIN_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                output = ""
            code = TIMEOUT_EXIT
            output = (output or "") + (
                f"\n[timeout] killed the process tree after {PER_CHECK_TIMEOUT_S:g}s: a budget is "
                f"evaluated after a check returns, so a check that never returns has to be ended here\n"
            )
    except OSError as err:
        # A missing interpreter (typo in --python, no venv, no PATH python) has to come back
        # as a failed check: a crashed runner would abandon the checks already in flight.
        code, output = 127, f"could not start the check: {type(err).__name__}: {err}"
    if code != 0:
        stop.set()
    return code, output, time.time() - started


def _verdict(output: str) -> str:
    """The check's own last word (``CFG_LOCK_OK (34 tasks)``), for the one-line summary."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else "(no output)"


def run_checks(
    interpreter: str, jobs: int, checks: Sequence[Check | tuple[str, list[str]]], verbose: bool = False
) -> tuple[list[tuple[int, str, int, str]], float, int, list[tuple[int, str, float]]]:
    """Run every check, at most ``jobs`` at a time, stopping the queue on the first failure.

    Returns:
        ``(failures, seconds, skipped, timings)`` with one ``(index, label, exit code, output)``
        per failed check, in list order, and one ``(index, label, seconds)`` per check that ran.
        Fail-fast is kept from the sequential suite: a check that turns red stops the queue, so
        only the checks already in flight finish -- none of them is ever silently dropped from
        the report.
    """
    stop = threading.Event()
    failures: list[tuple[int, str, int, str]] = []
    timings: list[tuple[int, str, float]] = []
    skipped = 0
    total = len(checks)
    started_at = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        pending = {
            pool.submit(_run_one, interpreter, argv, stop): (index, label)
            for index, (label, argv, *_) in enumerate(checks, start=1)
        }
        for future in concurrent.futures.as_completed(pending):
            index, label = pending[future]
            code, output, seconds = future.result()
            if code is None:
                skipped += 1
                print(f"[{index}/{total}] {label} ... skipped (an earlier check failed)", flush=True)
                continue
            timings.append((index, label, seconds))
            state = "ok" if code == 0 else f"FAIL rc={code}"
            print(f"[{index}/{total}] {label} ... {state} ({seconds:.1f}s) -> {_verdict(output)}", flush=True)
            if verbose and output:
                print(output.rstrip())
            if code != 0:
                failures.append((index, label, code, output))
                stop.set()
    return sorted(failures), time.time() - started_at, skipped, timings


def _per_check_cost(
    timings: list[tuple[int, str, float]],
    interpreter: str,
    checks: Sequence[Check | tuple[str, list[str]]] | None = None,
) -> tuple[list[tuple[int, str, float]], float]:
    """Which checks cost too much, and the wave's total.

    A wave number mixes one check's cost with five other import bursts, so it is a *suspect*
    (性能待确认), never a verdict: the verdict is that same check run with the machine quiet.
    Blaming the wave would make this a load-sensitive gate, and a gate that cries wolf on a
    busy machine is a gate that gets raised until it means nothing.
    """
    checks = CHECKS if checks is None else checks
    serial = sum(seconds for _, _, seconds in timings)
    breaches: list[tuple[int, str, float]] = []
    worst = sorted((t for t in timings if t[2] > PER_CHECK_BUDGET_S), key=lambda t: -t[2])[:SOLO_RECHECKS]
    for index, label, seconds in worst:
        _, _, alone = _run_one(interpreter, checks[index - 1][1], threading.Event())
        if alone > PER_CHECK_BUDGET_S:
            print(
                f"  [{index}/{len(checks)}] {label}: 性能待确认 {seconds:.1f}s in the wave -> "
                f"{alone:.1f}s alone, still over the {PER_CHECK_BUDGET_S:g}s cost budget",
                flush=True,
            )
            breaches.append((index, label, alone))
        else:
            print(
                f"  [{index}/{len(checks)}] {label}: {seconds:.1f}s in the wave was load -- "
                f"{alone:.1f}s alone, under the {PER_CHECK_BUDGET_S:g}s budget",
                flush=True,
            )
    return breaches, serial


def _total_verdict(wave_serial: float, quiet_serial: float) -> str:
    """``regression`` only if the quiet number is over budget too -- the sole admissible basis.

    The wave sum adds every check's cost to six-way resource contention, so it is not a stable
    cost metric: it can cross the line on a machine that is merely busy, and raising the budget
    to silence that both hides the real signal and teaches the next person to raise it again.
    """
    return "regression" if quiet_serial > SERIAL_BUDGET_S else "load"


def _budget_has_slack(measured: float) -> bool:
    """Warn only when measured seconds are more than 20% below the budget."""
    return measured < SERIAL_BUDGET_S * 0.8


def _quiet_serial(interpreter: str) -> tuple[float, list[str]]:
    """Re-measure the whole list one check at a time, the way a cost number has to be taken."""
    print(
        f"  the wave total is over budget -- re-measuring all {len(CHECKS)} checks at --jobs 1 "
        f"before blaming any of them (a wave number is a suspect, not a cost)",
        flush=True,
    )
    failures, _, _, quiet = run_checks(interpreter, 1, CHECKS)
    if failures:
        return 0.0, [f"[{index}/{len(CHECKS)}] {label} FAILED in the quiet re-measurement (rc={code})" for index, label, code, _ in failures]
    return sum(seconds for _, _, seconds in quiet), []


def self_test() -> int:
    """Prove the scheduler: exit codes are read, a failure skips the queue, budgets blame a check."""
    problems: list[str] = []
    quick = [("quick", ["-c", "print('q')"])]
    clean, _, _, _ = run_checks(sys.executable, 2, [("a", ["-c", "print('VERDICT_A')"]), ("b", ["-c", "print('VERDICT_B')"])])
    if clean:
        problems.append(f"all-passing checks reported as failures: {clean}")
    bad, _, _, _ = run_checks(
        sys.executable,
        1,
        [("fails", ["-c", "print('VERDICT_NG'); raise SystemExit(3)"]), ("must not run", ["-c", "raise SystemExit(9)"])],
    )
    if [index for index, *_ in bad] != [1]:
        problems.append(f"fail-fast did not stop the queue at the first failure: {[i for i, *_ in bad]}")
    elif bad[0][2] != 3 or "VERDICT_NG" not in bad[0][3]:
        problems.append(f"failure did not carry its exit code and output: {bad[0][2]}")
    # A bad interpreter must read as a failed check (the whole suite red), never as a crash
    # that drops the checks already in flight.
    missing, _, _, _ = run_checks(str(_REPO / "no-such-python.exe"), 2, [("x", ["-c", "print(1)"])])
    if [index for index, *_ in missing] != [1] or missing[0][2] != 127:
        problems.append(f"a missing interpreter was not reported as a failed check: {missing}")
    # Cost: a wave number is a suspect. Only a check that is slow *alone* is blamed, and the
    # total is a regression only when the quiet number is over budget too.
    global PER_CHECK_BUDGET_S
    saved, PER_CHECK_BUDGET_S = PER_CHECK_BUDGET_S, 0.0
    try:
        blamed, serial = _per_check_cost([(1, "quick", 0.1)], sys.executable, quick)
    finally:
        PER_CHECK_BUDGET_S = saved
    if [index for index, *_ in blamed] != [1] or serial != 0.1:
        problems.append(f"a check over budget alone was not blamed (or the wave sum is wrong): {blamed} {serial}")
    suspect, _ = _per_check_cost([(1, "quick", 999.0)], sys.executable, quick)
    if suspect:
        problems.append(f"a slow wave was blamed on the check instead of on the load: {suspect}")
    if _total_verdict(500.0, SERIAL_BUDGET_S * 0.9) != "load" or _total_verdict(500.0, SERIAL_BUDGET_S * 1.1) != "regression":
        problems.append("the total verdict does not separate a busy machine from a real regression")
    if not _budget_has_slack(SERIAL_BUDGET_S * 0.79) or _budget_has_slack(SERIAL_BUDGET_S * 0.8):
        problems.append("the budget ratchet does not warn at the >20% slack boundary")

    # Timeout: the suite has to end even when a check never returns -- including the case that
    # hangs a naive pipe read, a child that outlives the check that started it.
    global PER_CHECK_TIMEOUT_S
    saved_timeout, PER_CHECK_TIMEOUT_S = PER_CHECK_TIMEOUT_S, 1.0
    try:
        hung, hung_seconds, _, _ = run_checks(sys.executable, 1, [("hangs", ["-c", "import time; time.sleep(30)"])])
        orphaned, orphan_seconds, _, _ = run_checks(
            sys.executable,
            1,
            [
                (
                    "hangs, leaves a child behind",
                    [
                        "-c",
                        "import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', "
                        "'import time; time.sleep(30)']); time.sleep(30)",
                    ],
                )
            ],
        )
    finally:
        PER_CHECK_TIMEOUT_S = saved_timeout
    for label, killed, seconds in (("a check that never returns", hung, hung_seconds), ("a check whose child outlives it", orphaned, orphan_seconds)):
        if [index for index, *_ in killed] != [1] or killed[0][2] != TIMEOUT_EXIT:
            problems.append(f"{label} was not ended: {killed}")
        elif "[timeout]" not in killed[0][3]:
            problems.append(f"{label} was killed without saying why")
        elif seconds > 15:
            problems.append(f"{label} was not cut short ({seconds:.1f}s for a 30s sleep)")

    for problem in problems:
        print(f"  FAIL {problem}")
    if problems:
        print("offline suite: the scheduler itself is broken, a green run would mean nothing")
        return 1
    print("OFFLINE_SUITE_SELFTEST_OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--python", default=sys.executable, help="interpreter every check runs under")
    parser.add_argument("--jobs", type=int, default=default_jobs(), help="checks in flight at once")
    parser.add_argument("--verbose", action="store_true", help="print each check's full output, not its verdict")
    parser.add_argument("--list", action="store_true", help="print the check list and exit")
    parser.add_argument("--self-test", action="store_true", help="test this runner instead of the repo")
    args = parser.parse_args(argv)

    if args.list:
        for index, (label, argv_tail, _) in enumerate(CHECKS, start=1):
            print(f"[{index}/{len(CHECKS)}] {' '.join(argv_tail)}  -- {label}")
        return 0
    if args.self_test:
        return self_test()

    # The checks print Chinese verdicts; a console that cannot encode one must not turn a
    # passing suite into a traceback on the summary line.
    sys.stdout.reconfigure(errors="replace")

    failures, seconds, skipped, timings = run_checks(args.python, args.jobs, CHECKS, args.verbose)
    total = len(CHECKS)
    if failures:
        for index, label, code, output in failures:
            print(f"\n[{index}/{total}] {label} FAILED (rc={code})")
            print(output.rstrip())
        print(f"OFFLINE_CHECK_FAILED ({total} check(s): {len(failures)} failed, {skipped} skipped, {seconds:.1f}s, jobs={args.jobs})")
        return 1
    breaches, wave_serial = _per_check_cost(timings, args.python)
    quiet_serial = None
    quiet_problems: list[str] = []
    if wave_serial > SERIAL_BUDGET_S:
        quiet_serial, quiet_problems = _quiet_serial(args.python)
    if quiet_problems or breaches or (quiet_serial is not None and _total_verdict(wave_serial, quiet_serial) == "regression"):
        for problem in quiet_problems:
            print(f"  {problem}")
        for index, label, alone in breaches:
            print(f"  [{index}/{total}] {label}: {alone:.1f}s alone > {PER_CHECK_BUDGET_S:g}s per check")
        if quiet_serial is not None and _total_verdict(wave_serial, quiet_serial) == "regression":
            print(f"  serial {quiet_serial:.0f}s quiet > {SERIAL_BUDGET_S:g}s budget (wave {wave_serial:.0f}s)")
        print(
            "OFFLINE_SUITE_COST_REGRESSION (confirmed with the machine quiet). Make the check "
            "cheaper -- one process per check, no re-reading frozen data per cfg, no interpreter "
            "children -- or, if the coverage that caused it is worth the price, raise the budget "
            "in the same commit as that check; see rl_exp/tools/verify/OFFLINE_CHECKS.md"
        )
        return 1
    if quiet_serial is not None:
        print(
            f"  wave total {wave_serial:.0f}s was over budget under load; {quiet_serial:.0f}s quiet is "
            f"within {SERIAL_BUDGET_S:g}s -- no change, and no reason to touch the budget"
        )
    measured = wave_serial if quiet_serial is None else quiet_serial
    if _budget_has_slack(measured):
        print(
            f"  BUDGET_RATCHET_WARNING: measured {measured:.1f}s is >20% below "
            f"{SERIAL_BUDGET_S:g}s budget; confirm on a quiet host and tighten the budget"
        )
    print(
        f"ALL_OFFLINE_CHECKS_PASSED ({total}/{total} in {seconds:.1f}s, "
        f"wave {wave_serial:.0f}s{'' if quiet_serial is None else f', quiet {quiet_serial:.0f}s'}, jobs={args.jobs})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
