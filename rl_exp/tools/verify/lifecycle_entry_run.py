# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""The entry-side run (ARCH_PLAN 2.3 C4 / L02, L03, L05): a real process, not a mock.

The offline suite proves the decision table and the wiring; it cannot prove that a *trainer
process* consults them before it builds anything, and 2.2's whole point is that the answer must
not depend on which entry was used. So this tool drives the real entries against a fixture
directory (2.1a forbids retiring a real line to get one) and judges what came out:

``launcher``   the new launcher refuses in-process, without starting the trainer at all
``trainer``    the old trainer refuses *and leaves its T0 refusal* on disk -- the refusal is evidence
``tuning``     the tuning entry (``run_ablation``), which shells out to that trainer, is killed by it
``announce``   a due retirement announcement warns and proceeds, and the warning reaches the record
``moved``      a launch judged against one directory keeps that verdict when the directory moves on

Only ``launcher`` can run without the sim app; the others start it and belong in the run window.

    python rl_exp\\tools\\verify\\lifecycle_entry_run.py --track launcher
    python rl_exp\\tools\\verify\\lifecycle_entry_run.py --track all --task Lizard-Rough-v14
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _path in (str(_REPO), str(_REPO / "rl_exp" / "tools" / "verify"), str(_REPO / "ablation_harness")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import host_paths  # noqa: E402
from rl_exp.tools.runrecord import lifecycle  # noqa: E402
from rl_exp.tools.runrecord import manifest as M  #: E402
from rl_exp.tools.verify import lifecycle_entry_fixture as fixture_entry  # noqa: E402

TRAINER = "scripts/reinforcement_learning/rsl_rl/train.py"
REFUSAL = "refused to start"


def _run(command: list[str], *, cwd: pathlib.Path, environment: dict) -> subprocess.CompletedProcess:
    """One real process, output captured (the judgement reads it, so it has to be here)."""
    print(f"[entry-run] {' '.join(command[:3])} ... (cwd {cwd})", flush=True)
    return subprocess.run(command, cwd=str(cwd), env=environment, capture_output=True, text=True, timeout=1800)


def _environment(python: str, index_root: pathlib.Path) -> dict:
    """The child's environment: the fixture directory is the whole point of the run."""
    return {**os.environ, lifecycle.INDEX_DIR_ENV: str(index_root), "PYTHONUNBUFFERED": "1"}


def _newest_run_dir(experiment_name: str, root: pathlib.Path) -> pathlib.Path | None:
    """The run directory a launch just created, if any (it exists as soon as T0 is written).

    Resolved under the *IsaacLab* tree: the trainer is launched with that as its cwd, so that is
    where ``logs/`` lands -- asking from this repo's cwd would silently look in the wrong tree.
    """
    directory = pathlib.Path(os.path.abspath(os.path.join(root, "logs", "rsl_rl", experiment_name)))
    runs = sorted((path for path in directory.iterdir() if path.is_dir()), key=lambda path: path.name) if directory.is_dir() else []
    return runs[-1] if runs else None


def track_launcher(args, python: str, out: pathlib.Path) -> list[str]:
    """The new entry refuses before starting anything -- provable without the sim app."""
    fixture = out / "fixture_launcher"
    fixture_entry.build(fixture, retire=args.line, announce=None, notice_until=None, today=None, successor=None)
    environment = _environment(python, fixture)
    before = _newest_run_dir(args.experiment, _isaac_root())
    result = _run(
        [python, "rl_exp/tools/launch_recipe.py", "--task", args.task, "--launch", "--num_envs", "64"],
        cwd=_REPO,
        environment=environment,
    )
    problems: list[str] = []
    if result.returncode != 2:
        problems.append(f"launcher: exit {result.returncode}, expected 2 (refusal)")
    if "refused:" not in result.stderr:
        problems.append(f"launcher: no refusal line in stderr: {result.stderr.strip()[:200]!r}")
    if "successor" not in result.stderr:
        problems.append("launcher: the refusal must say where new work belongs")
    if _newest_run_dir(args.experiment, _isaac_root()) != before:
        problems.append("launcher: a refusal must not start the trainer (a run directory appeared)")
    print(f"[entry-run] launcher: {result.stderr.strip().splitlines()[:1]}")
    return problems


def track_trainer(args, python: str, out: pathlib.Path) -> list[str]:
    """The old trainer refuses, and the refusal is on disk: a refused launch is not nothing."""
    fixture = out / "fixture_trainer"
    fixture_entry.build(fixture, retire=args.line, announce=None, notice_until=None, today=None, successor=None)
    environment = _environment(python, fixture)
    result = _run(_trainer_command(python, args, iterations=1), cwd=_isaac_root(), environment=environment)
    problems: list[str] = []
    if result.returncode == 0:
        problems.append("trainer: a retired line must not launch")
    if REFUSAL not in result.stdout and REFUSAL not in result.stderr:
        problems.append(f"trainer: no refusal in the output: {(result.stdout + result.stderr)[-300:]!r}")
    run_dir = _newest_run_dir(args.experiment, _isaac_root())
    if run_dir is None:
        problems.append("trainer: the refusal must leave its T0 on disk")
    else:
        written = json.loads((run_dir / M.MANIFEST_NAME).read_text(encoding="utf-8"))
        verdict = (written.get("declaration") or {}).get("lifecycle") or {}
        if verdict.get("allowed") is not False:
            problems.append(f"trainer: T0 does not record the refusal: {verdict!r}")
        if not written.get("failures"):
            problems.append("trainer: the refusal is not in the record's failures")
        print(f"[entry-run] trainer: refused, T0 at {run_dir.name} (allowed={verdict.get('allowed')})")
    return problems


def track_tuning(args, python: str, out: pathlib.Path) -> list[str]:
    """The tuning entry trains through that same trainer, so it must die the same way."""
    fixture = out / "fixture_tuning"
    fixture_entry.build(fixture, retire=args.line, announce=None, notice_until=None, today=None, successor=None)
    spec = out / "spec.yaml"
    spec.write_text(
        "runs:\n"
        f"  - tag: refuse\n    task: {args.task}\n    seed: 42\n    max_iterations: 1\n"
        "    eval_checkpoints: []\n    eval_modes: []\n    overrides: []\n",
        encoding="utf-8",
    )
    result = _run(
        [python, "ablation_harness/run_ablation.py", "--spec", str(spec), "--python", python],
        cwd=_REPO,
        environment=_environment(python, fixture),
    )
    problems: list[str] = []
    if result.returncode == 0:
        problems.append("tuning: the sweep must fail when its run refuses to start")
    if REFUSAL not in result.stdout and REFUSAL not in result.stderr:
        problems.append("tuning: the child's refusal must surface (no refusal found in the sweep output)")
    print(f"[entry-run] tuning: exit {result.returncode}")
    return problems


def track_announce(args, python: str, out: pathlib.Path) -> list[str]:
    """A due announcement is a warning, not a wall: it proceeds and it is recorded."""
    fixture = out / "fixture_announce"
    fixture_entry.build(
        fixture,
        retire=None,
        announce=args.line,
        notice_until=(args.today or "2026-01-01"),
        today=_day(args.today or "2026-01-01"),
        successor=None,
    )
    result = _run(
        _trainer_command(python, args, iterations=2), cwd=_isaac_root(), environment=_environment(python, fixture)
    )
    problems: list[str] = []
    if result.returncode != 0:
        problems.append(f"announce: a due announcement must not block the launch (exit {result.returncode})")
    run_dir = _newest_run_dir(args.experiment, _isaac_root())
    if run_dir is None:
        problems.append("announce: no run directory to read the record from")
        return problems
    written = json.loads((run_dir / M.MANIFEST_NAME).read_text(encoding="utf-8"))
    verdict = (written.get("declaration") or {}).get("lifecycle") or {}
    if verdict.get("retirement_due") is not True or not verdict.get("warn"):
        problems.append(f"announce: the overdue announcement must be recorded as a warning: {verdict!r}")
    print(f"[entry-run] announce: exit 0, warn={verdict.get('warn')!r}")
    return problems


def track_moved(args, python: str, out: pathlib.Path) -> list[str]:
    """L05: the directory moving on does not rewrite what the run was started under."""
    first, second = out / "fixture_moved_a", out / "fixture_moved_b"
    fixture_entry.build(first, retire=None, announce=None, notice_until=None, today=None, successor=None)
    result = _run(
        _trainer_command(python, args, iterations=1), cwd=_isaac_root(), environment=_environment(python, first)
    )
    problems: list[str] = []
    if result.returncode != 0:
        problems.append(f"moved: the first launch must succeed (exit {result.returncode})")
        return problems
    run_dir = _newest_run_dir(args.experiment, _isaac_root())
    if run_dir is None:
        problems.append("moved: no run directory")
        return problems
    recorded = json.loads((run_dir / M.MANIFEST_NAME).read_text(encoding="utf-8"))
    digest = ((recorded.get("declaration") or {}).get("lifecycle") or {}).get("directory_sha256")

    # the directory is revised *after* the launch: the recorded verdict stands, and today's
    # directory is not re-applied to it (hard constraint 6)
    fixture_entry.build(second, retire=None, announce=None, notice_until=None, today=None, successor=None)
    os.environ[lifecycle.INDEX_DIR_ENV] = str(second)
    try:
        rows, blocking = M.verify(run_dir)
    finally:
        os.environ.pop(lifecycle.INDEX_DIR_ENV, None)
    lifecycle_rows = [row for row in rows if "line" in row.get("detail", "")]
    if blocking:
        problems.append(f"moved: a moved directory must not block the record: {blocking}")
    if not any("changed since this launch" in row.get("detail", "") for row in rows):
        problems.append(f"moved: the moved directory must be reported: {[row['detail'] for row in lifecycle_rows]}")
    still = json.loads((run_dir / M.MANIFEST_NAME).read_text(encoding="utf-8"))
    if ((still.get("declaration") or {}).get("lifecycle") or {}).get("directory_sha256") != digest:
        problems.append("moved: the record was rewritten when the directory moved")
    print(f"[entry-run] moved: record kept its directory digest, verify reported the move")
    return problems


def _day(text: str):
    import datetime as _dt

    return _dt.date.fromisoformat(text)


def _isaac_root() -> pathlib.Path:
    root = host_paths.isaac_root()
    if root is None:
        raise SystemExit("[entry-run] no IsaacLab tree configured (paths.yaml / RL_ISAAC_ROOT)")
    return root


def _trainer_command(python: str, args, *, iterations: int) -> list[str]:
    return [
        python,
        TRAINER,
        "--task",
        args.task,
        "--headless",
        "--num_envs",
        str(args.num_envs),
        "--seed",
        "42",
        "--max_iterations",
        str(iterations),
    ]


TRACKS = {
    "launcher": track_launcher,
    "trainer": track_trainer,
    "tuning": track_tuning,
    "announce": track_announce,
    "moved": track_moved,
}
NO_SIM = ("launcher",)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--track", default="launcher", choices=[*TRACKS, "all"])
    parser.add_argument("--task", default="Lizard-Rough-v14", help="task id the launch uses")
    parser.add_argument("--line", default="lizard/main", help="line the fixture retires/announces")
    parser.add_argument("--num_envs", type=int, default=64)
    parser.add_argument("--today", default=None, help="date for a due announcement (ISO)")
    parser.add_argument("--experiment", default=None, help="log directory name (default: read off the task)")
    parser.add_argument("--report", type=pathlib.Path, default=None, help="write the report here")
    parser.add_argument("--python", default=None, help="interpreter (default: paths.yaml's)")
    parser.add_argument("--dry-run", action="store_true", default=False, help="list the tracks and stop")
    args = parser.parse_args(argv)

    python = args.python or host_paths.venv_python(host_paths.isaac_root())
    if python is None:
        raise SystemExit("[entry-run] no interpreter configured (paths.yaml's python:, or --python)")
    args.experiment = args.experiment or _experiment_name(args.task)
    tracks = list(TRACKS) if args.track == "all" else [args.track]
    if args.dry_run:
        for name in tracks:
            print(f"[entry-run] {name}: {'no sim app needed' if name in NO_SIM else 'starts the sim app'}")
        return 0

    report: dict = {"task": args.task, "line": args.line, "python": python, "tracks": {}}
    problems: list[str] = []
    with tempfile.TemporaryDirectory(prefix="entry_run_") as tmp:
        out = pathlib.Path(tmp)
        for name in tracks:
            found = TRACKS[name](args, python, out)
            report["tracks"][name] = {"problems": found}
            problems.extend(f"{name}: {problem}" for problem in found)
    report["problems"] = problems
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for problem in problems:
        print(f"  FAIL {problem}")
    if problems:
        print("LIFECYCLE_ENTRY_RUN_FAILED")
        return 1
    print("LIFECYCLE_ENTRY_RUN_OK")
    return 0


def _experiment_name(task: str) -> str:
    """The log directory name for a task id, read off the agent cfg the task declares.

    The run directory is where the refusal's T0 lands, so the reader has to find the same one the
    trainer will; the registry is the single place that says which agent config a task uses.
    """
    import gymnasium as gym

    import rl_exp.tasks  # noqa: F401 - registers the tasks
    from isaaclab.utils.string import string_to_callable

    entry = gym.spec(task).kwargs["rsl_rl_cfg_entry_point"]
    return string_to_callable(entry)().experiment_name


if __name__ == "__main__":
    sys.exit(main())
