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
"""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import pathlib
import subprocess
import sys
import threading
import time

_REPO = pathlib.Path(__file__).resolve().parents[3]
_V = "rl_exp/tools/verify"  # relative on purpose: every check expects the repo root as cwd

# (label, argv after the interpreter). The order is the [i/N] numbering the version
# records and ACCEPTANCE.md cite, so entries are appended, never reshuffled.
CHECKS: list[tuple[str, list[str]]] = [
    ("framework pin check (IsaacLab internals + pinned SHA)", [f"{_V}/framework_pin_check.py"]),
    ("freeze contracts (DR/wiring + robot block parity, DR lists, PLAY coverage, asset contract + locks)",
     [f"{_V}/check_dr_parity.py", "--strict"]),
    ("recovery vectorization parity", [f"{_V}/test_recovery_parity.py"]),
    ("staged curriculum offline test", [f"{_V}/test_staged_curriculum.py"]),
    ("teacher split-encoder networks (forward/gradient/export/transfer)", [f"{_V}/test_teacher_networks.py"]),
    ("student belief networks (GRU/gate/decoder/load_from_teacher)", [f"{_V}/test_student_networks.py"]),
    ("v3 curriculum + ring pattern (c_k math, tilt predicate, geometry)", [f"{_V}/test_v3_curriculum.py"]),
    ("obs layout gate (group names, term order, c_k step consistency)", [f"{_V}/check_obs_layout.py"]),
    ("v5 anti-collapse rewards (linear tracking / slip / belly / c_k scaling)", [f"{_V}/test_v5_rewards.py"]),
    ("v5.3 SIR terrain curriculum (band / resample / walk clamp / replay / throttle)", [f"{_V}/test_v5_terrain_sir.py"]),
    ("v11 joint SIR terrain curriculum (param grid / Eq.2-3-7 / fallback / walk / command)",
     [f"{_V}/test_joint_sir.py"]),
    ("version-record completeness (four-piece set / FAMILY row / FILEMAP row)", [f"{_V}/check_version_docs.py"]),
    ("v12 height-ring noise model (conditions / scopes / outliers / c_k / mid redraw)", [f"{_V}/test_v12_noise.py"]),
    ("pre-kit pxr leak gate (P001/P003: env cfg import chain must stay pxr-clean)", [f"{_V}/check_pxr_leak.py"]),
    ("curriculum resume state (roundtrip / fingerprint / hard-abort / hook)", [f"{_V}/test_resume_state.py"]),
    ("tb_scalars record sampling (max_points / first+last / CLI resample)", [f"{_V}/test_dump_tb_sampling.py"]),
    ("v13 symmetric tracking kernel (miki wired / EP gone / v5+v10 frozen)", [f"{_V}/check_reward_v13.py"]),
    ("v14 front-plant/roll fall gate (predicate / dwell / wiring / v13 frozen)", [f"{_V}/check_terminations_v14.py"]),
    ("acceptance metrics (yaw frame / abs sideslip / per-frame MAE / kernel frame contract)",
     [f"{_V}/test_acceptance_metrics.py"]),
    ("eval frame contract v2 (terminal frame closes the fall window / v1 truncation)",
     [f"{_V}/test_eval_frame_v2.py"]),
    ("configclass field surface (params_version field vs to_dict vs own_fields)",
     [f"{_V}/check_configclass_fields.py"]),
    ("configclass field-surface gate falsifier (each drift must still fire)",
     [f"{_V}/test_configclass_fields_gate.py"]),
    ("config snapshot serializer (order / floats / identities / paths / digest)", [f"{_V}/test_cfg_snapshot.py"]),
    ("recipe golden lock (per-line entries vs versions/<line>/cfg_lock.json, shared baselines)",
     [f"{_V}/check_cfg_lock.py"]),
    ("recipe golden gate falsifier (each drift must still fire)", [f"{_V}/test_cfg_lock_gate.py"]),
    ("run manifest (T0/T1 record, checkpoint infos, external index, --verify)", [f"{_V}/test_run_manifest.py"]),
    ("isolation rebuild gate (material capture/refusal, sources, missing-file negative test)",
     [f"{_V}/test_rebuild_gate.py"]),
    ("recipe line discovery (yaml/lock convention, refusals must fire)", [f"{_V}/test_recipe_lines.py"]),
    ("recipe line lifecycle (identity / retirement evidence / announced notice period)",
     [f"{_V}/check_recipe_registry.py"]),
    ("recipe lifecycle gate falsifier (each refusal must still fire)", [f"{_V}/test_recipe_registry_gate.py"]),
    ("recipe identity map (task id to recipe, revision to entries, vs registration + built configs)",
     [f"{_V}/check_recipe_map.py", "--bind-config"]),
    ("recipe map gate falsifier (each refusal must still fire)", [f"{_V}/test_recipe_map_gate.py"]),
    ("suite banner hygiene (no bare redirects in echo lines; detector self-tested)",
     [f"{_V}/check_suite_banners.py"]),
    ("params loaders hand each caller its own document (cache must not alias cfgs)",
     [f"{_V}/test_params_isolation.py"]),
    ("stage B acceptance baseline is still the frozen one (golden locks pinned by digest)",
     [f"{_V}/check_golden_frozen.py"]),
]


def default_jobs() -> int:
    """Workers to use: half the cores, so the import bursts do not thrash each other."""
    return max(1, min(6, (os.cpu_count() or 2) // 2))


def _run_one(interpreter: str, argv: list[str], stop: threading.Event) -> tuple[int | None, str, float]:
    """Run one check; returns (exit code, output, seconds), or (None, ...) when skipped.

    ``PYTHONIOENCODING`` keeps a check's non-ASCII verdict readable when it is captured
    rather than written straight to the console. The failure flag is set *here* rather
    than by the caller: the queue has to stop the moment a check turns red, not when the
    main thread gets round to reading its result.
    """
    if stop.is_set():
        return None, "", 0.0
    started = time.time()
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        proc = subprocess.run(
            [interpreter, *argv],
            cwd=str(_REPO),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        code, output = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
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
    interpreter: str, jobs: int, checks: list[tuple[str, list[str]]], verbose: bool = False
) -> tuple[list[tuple[int, str, int, str]], float, int]:
    """Run every check, at most ``jobs`` at a time, stopping the queue on the first failure.

    Returns:
        ``(failures, seconds, skipped)`` with one ``(index, label, exit code, output)`` per
        failed check, in list order. Fail-fast is kept from the sequential suite: a check
        that turns red stops the queue, so only the checks already in flight finish -- none
        of them is ever silently dropped from the report.
    """
    stop = threading.Event()
    failures: list[tuple[int, str, int, str]] = []
    skipped = 0
    total = len(checks)
    started_at = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        pending = {
            pool.submit(_run_one, interpreter, argv, stop): (index, label)
            for index, (label, argv) in enumerate(checks, start=1)
        }
        for future in concurrent.futures.as_completed(pending):
            index, label = pending[future]
            code, output, seconds = future.result()
            if code is None:
                skipped += 1
                print(f"[{index}/{total}] {label} ... skipped (an earlier check failed)", flush=True)
                continue
            state = "ok" if code == 0 else f"FAIL rc={code}"
            print(f"[{index}/{total}] {label} ... {state} ({seconds:.1f}s) -> {_verdict(output)}", flush=True)
            if verbose and output:
                print(output.rstrip())
            if code != 0:
                failures.append((index, label, code, output))
                stop.set()
    return sorted(failures), time.time() - started_at, skipped


def self_test() -> int:
    """Prove the scheduler: exit codes are read, and a failure really does skip the queue."""
    problems: list[str] = []
    clean, _, _ = run_checks(
        sys.executable, 2, [("a", ["-c", "print('VERDICT_A')"]), ("b", ["-c", "print('VERDICT_B')"])]
    )
    if clean:
        problems.append(f"all-passing checks reported as failures: {clean}")
    bad, _, _ = run_checks(
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
    missing, _, _ = run_checks(str(_REPO / "no-such-python.exe"), 2, [("x", ["-c", "print(1)"])])
    if [index for index, *_ in missing] != [1] or missing[0][2] != 127:
        problems.append(f"a missing interpreter was not reported as a failed check: {missing}")
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
        for index, (label, argv_tail) in enumerate(CHECKS, start=1):
            print(f"[{index}/{len(CHECKS)}] {' '.join(argv_tail)}  -- {label}")
        return 0
    if args.self_test:
        return self_test()

    # The checks print Chinese verdicts; a console that cannot encode one must not turn a
    # passing suite into a traceback on the summary line.
    sys.stdout.reconfigure(errors="replace")

    failures, seconds, skipped = run_checks(args.python, args.jobs, CHECKS, args.verbose)
    total = len(CHECKS)
    if failures:
        for index, label, code, output in failures:
            print(f"\n[{index}/{total}] {label} FAILED (rc={code})")
            print(output.rstrip())
        print(f"OFFLINE_CHECK_FAILED ({total} check(s): {len(failures)} failed, {skipped} skipped, {seconds:.1f}s, jobs={args.jobs})")
        return 1
    print(f"ALL_OFFLINE_CHECKS_PASSED ({total}/{total} in {seconds:.1f}s, jobs={args.jobs})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
