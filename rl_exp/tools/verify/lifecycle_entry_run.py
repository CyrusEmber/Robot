# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""The entry-side run (ARCH_PLAN 2.3 C4 / L02, L03): a real process, not a mock.

The offline suite proves the decision table and the wiring; it cannot prove that a *trainer
process* consults them before it builds anything. So this tool drives the real entries against
the real retired line -- ``lizard/parkour`` (``Lizard-Parkour-Climb-v1``), retired because its
env cannot be constructed -- and judges what came out:

``launcher``   the launcher refuses in-process, without starting the trainer at all: exit 2,
               the identity it judged recorded, and no run directory
``trainer``    the old trainer refuses *and leaves its T0 refusal* on disk, which ``--verify``
               then reads as a refusal and not as a run that died on the way to T1

Only ``launcher`` can run without the sim app; ``trainer`` starts it and belongs in the run
window. A retired line is never *produced* for a test (2.1a): both tracks use the line the
directory already retired.

    python rl_exp\\tools\\verify\\lifecycle_entry_run.py --track launcher
    python rl_exp\\tools\\verify\\lifecycle_entry_run.py --track trainer --task Lizard-Parkour-Climb-v1
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
from rl_exp.tools.runrecord import manifest as M  # noqa: E402

TRAINER = "scripts/reinforcement_learning/rsl_rl/train.py"
REFUSAL = "refused to start"
RETIRED_TASK = "Lizard-Parkour-Climb-v1"
RETIRED_LINE = "lizard/parkour"


def _run(command: list[str], *, cwd: pathlib.Path, environment: dict) -> subprocess.CompletedProcess:
    """One real process, output captured (the judgement reads it, so it has to be here).

    The decode is pinned rather than left to the host locale: the trainer's log is not ASCII, and
    when the locale cannot decode it the reader thread dies, ``stdout`` arrives as ``None`` and the
    run still reports success -- evidence silently missing instead of a loud failure. UTF-8 with
    replacement is how the other tool-output readers in this tree decode.
    """
    print(f"[entry-run] {' '.join(command[:3])} ... (cwd {cwd})", flush=True)
    return subprocess.run(command, cwd=str(cwd), env=environment, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=1800)


def _environment() -> dict:
    """The child's environment.

    ``RL_ALLOW_DIRTY_TREE`` is set because these tracks run while the repository is being
    changed: the lifecycle answer is what they are about, and a dirty tree would otherwise be a
    second refusal standing in front of the one under test.
    """
    return {
        **os.environ,
        "RL_ALLOW_DIRTY_TREE": "lifecycle entry run: the tree is dirty by definition here",
        "PYTHONUNBUFFERED": "1",
    }


def _newest_run_dir(experiment_name: str, root: pathlib.Path) -> pathlib.Path | None:
    """The run directory a launch just created, if any (it exists as soon as T0 is written).

    Resolved under the *IsaacLab* tree: the trainer is launched with that as its cwd, so that is
    where ``logs/`` lands -- asking from this repo's cwd would silently look in the wrong tree.
    """
    directory = pathlib.Path(os.path.abspath(os.path.join(root, "logs", "rsl_rl", experiment_name)))
    runs = sorted((path for path in directory.iterdir() if path.is_dir()), key=lambda path: path.name) if directory.is_dir() else []
    return runs[-1] if runs else None


def _refusal_problems(label: str, record: dict) -> list[str]:
    """What the refusal itself must say, whichever entry produced it.

    The reason has to name the retired line, and it must not promise a successor: the index
    registers none for ``lizard/parkour``, and a message that points at a line which does not
    exist is worse than no message.
    """
    problems: list[str] = []
    if record.get("allowed") is not False:
        problems.append(f"{label}: the launch must be refused, got allowed={record.get('allowed')!r}")
    # the identity lives where the entry that produced it put it: the launcher nests it under
    # ``identity`` (and repeats the decision under ``lifecycle``), the trainer's record is the
    # T0 declaration. Reading only one shape would judge the record's layout, not its content.
    identity = record.get("identity") or record.get("lifecycle") or record
    if identity.get("line") != RETIRED_LINE or identity.get("status") != "retired":
        problems.append(f"{label}: the refusal must carry the identity it read, got {identity!r}")
    reason = record.get("reason") or ""
    if "retired line" not in reason:
        problems.append(f"{label}: the refusal must say the line is retired, got {reason!r}")
    if "successor" in reason:
        problems.append(f"{label}: the refusal promises a successor the index does not register: {reason!r}")
    return problems


def track_launcher(args, python: str, out: pathlib.Path) -> list[str]:
    """The new entry refuses before starting anything -- provable without the sim app."""
    before = _newest_run_dir(args.experiment, _isaac_root())
    record_path = out / "launcher_record.json"
    result = _run(
        [
            python,
            "rl_exp/tools/launch_recipe.py",
            "--task",
            args.task,
            "--launch",
            "--num_envs",
            "64",
            "--record",
            str(record_path),
        ],
        cwd=_REPO,
        environment=_environment(),
    )
    problems: list[str] = []
    if result.returncode != 2:
        problems.append(f"launcher: exit {result.returncode}, expected 2 (refusal)")
    if "refused:" not in result.stderr:
        problems.append(f"launcher: no refusal line in stderr: {result.stderr.strip()[:200]!r}")
    if not record_path.is_file():
        problems.append("launcher: no launch record was written, so the verdict cannot be read")
        return problems
    problems.extend(_refusal_problems("launcher", json.loads(record_path.read_text(encoding="utf-8"))))
    if _newest_run_dir(args.experiment, _isaac_root()) != before:
        problems.append("launcher: a refusal must not start the trainer (a run directory appeared)")
    print(f"[entry-run] launcher: exit {result.returncode}, {result.stderr.strip().splitlines()[:1]}")
    return problems


def track_trainer(args, python: str, out: pathlib.Path) -> list[str]:
    """The trainer refuses, the refusal is on disk, and ``--verify`` reads it as a refusal."""
    before = _newest_run_dir(args.experiment, _isaac_root())
    result = _run(_trainer_command(python, args, iterations=1), cwd=_isaac_root(), environment=_environment())
    problems: list[str] = []
    if result.returncode != 2:
        problems.append(
            f"trainer: exit {result.returncode}, expected 2 -- a refusal must be observable to a"
            " CI job or a sweep scheduler (a raise alone exits 0 here: the sim app teardown)"
        )
    if REFUSAL not in (result.stdout + result.stderr):
        problems.append(f"trainer: no refusal in the output: {(result.stdout + result.stderr)[-300:]!r}")
    run_dir = _newest_run_dir(args.experiment, _isaac_root())
    if run_dir is None or run_dir == before:
        problems.append("trainer: the refusal must leave its T0 on disk (a refused launch is evidence)")
        return problems
    written = json.loads((run_dir / M.MANIFEST_NAME).read_text(encoding="utf-8"))
    problems.extend(_refusal_problems("trainer", (written.get("declaration") or {}).get("lifecycle") or {}))
    if not written.get("failures"):
        problems.append("trainer: the refusal is not in the record's failures")
    rows, blocking = M.verify(run_dir)
    if blocking:
        problems.append(f"trainer: --verify must not report a refused launch as broken: {blocking}")
    if not any("refused at T0" in row.get("detail", "") for row in rows):
        problems.append(f"trainer: --verify must say the launch was refused: {[row['detail'] for row in rows]}")
    print(f"[entry-run] trainer: exit {result.returncode}, refusal recorded at {run_dir.name}")
    return problems


def _newest_checkpoint(run_dir: pathlib.Path) -> pathlib.Path | None:
    """The run's newest *real* checkpoint (never one of this tool's stripped copies).

    A stripped copy is newer than the checkpoint it came from, so picking by time alone would
    hand the next arm its own fixture -- and stripping a stripped file would look like a clean
    control while proving nothing. The self-check in the track catches that, this is the fix.
    """
    files = sorted(
        (path for path in run_dir.glob("model_*.pt") if not path.name.startswith("model_stripped")),
        key=lambda path: path.stat().st_mtime,
    )
    return files[-1] if files else None


def _strip_curriculum_state(source: pathlib.Path, destination: pathlib.Path) -> tuple[bool, bool]:
    """Copy a checkpoint with its curriculum payload removed, and report what that did.

    Returns:
        ``(carried_state_before, carries_state_after)``. The first is the check that makes this
        control honest: a source checkpoint that never had the state would let the arm below pass
        while proving nothing -- the same vacuum the moved-directory control had.
    """
    import torch

    from rl_exp.tasks.curriculum_state import STATE_KEY

    checkpoint = torch.load(source, weights_only=False, map_location="cpu")
    infos = checkpoint.get("infos") or {}
    carried = STATE_KEY in infos
    infos.pop(STATE_KEY, None)
    checkpoint["infos"] = infos
    torch.save(checkpoint, destination)
    written = torch.load(destination, weights_only=False, map_location="cpu")
    return carried, STATE_KEY in (written.get("infos") or {})


def track_resume(args, python: str, out: pathlib.Path) -> list[str]:
    """L03: a checkpoint without the state its task promises must be refused, not cold-started.

    Three arms, and the middle one is why this cannot be done offline: the declaration, the save
    guard and the resume refusal all have to hold in a real process, against a real checkpoint
    whose payload was removed. The third arm is the control -- the same file with the explicit
    opt-out -- so a red in the second arm is about the missing state and not about the command.
    """
    task = args.resume_task
    experiments = _experiment_name(task)
    root = _isaac_root()
    logs = pathlib.Path(os.path.abspath(os.path.join(root, "logs", "rsl_rl", experiments)))
    problems: list[str] = []

    run_dir = None
    for candidate in sorted((p for p in logs.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True) if logs.is_dir() else []:
        if _newest_checkpoint(candidate) is not None:
            run_dir = candidate
            break
    if run_dir is None:
        # no checkpoint anywhere: make one (two iterations is enough -- the save hook writes the
        # state at the end of training, and a run that never reaches the end writes nothing)
        result = _run(
            _trainer_command(python, args, iterations=args.resume_train_iters, task=task),
            cwd=root,
            environment=_environment(),
        )
        if result.returncode != 0:
            return [f"resume: the source run failed (exit {result.returncode}): {result.stdout[-300:]!r}"]
        run_dir = _newest_run_dir(experiments, root)
    if run_dir is None:
        return ["resume: no run directory to take a source checkpoint from"]
    source = _newest_checkpoint(run_dir)
    if source is None:
        return [f"resume: {run_dir.name} has no checkpoint (a run shorter than the save interval writes none)"]

    stripped = run_dir / "model_stripped_nostate.pt"
    carried, carries = _strip_curriculum_state(source, stripped)
    if not carried:
        return [f"resume: {source.name} carries no curriculum state, so this arm would prove nothing"]
    if carries:
        return [f"resume: stripping did not remove the state from {stripped.name}"]

    # arm 2: the stripped checkpoint, resumed as the task promises to be resumed
    command = _trainer_command(python, args, iterations=1, task=task) + [
        "--resume",
        "--load_run",
        run_dir.name,
        "--checkpoint",
        stripped.name,
    ]
    result = _run(command, cwd=root, environment=_environment())
    output = result.stdout + result.stderr
    if result.returncode == 0:
        problems.append("resume: a checkpoint without the declared curriculum state must not resume")
    if "no curriculum state" not in output and "cold-start" not in output:
        problems.append(f"resume: the refusal must name the missing state, got {output[-300:]!r}")
    if "WARN" in output and "cold" in output and "refus" not in output.lower():
        problems.append("resume: the missing state was warned about instead of refused")
    print(f"[entry-run] resume: stripped source refused (exit {result.returncode})")

    # arm 3: the control -- the same file, with the explicit opt-out
    control = _run(command + ["--drop_curriculum_state"], cwd=root, environment=_environment())
    if control.returncode != 0:
        problems.append(
            f"resume: --drop_curriculum_state must let the same checkpoint through (exit {control.returncode})"
        )
    if "curriculum state" not in (control.stdout + control.stderr):
        problems.append("resume: the opt-out arm must report what it dropped")
    print(f"[entry-run] resume: opt-out arm exit {control.returncode}")
    return problems


def _isaac_root() -> pathlib.Path:
    root = host_paths.isaac_root()
    if root is None:
        raise SystemExit("[entry-run] no IsaacLab tree configured (paths.yaml / RL_ISAAC_ROOT)")
    return root


def _trainer_command(python: str, args, *, iterations: int, task: str | None = None) -> list[str]:
    return [
        python,
        TRAINER,
        "--task",
        task or args.task,
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
    "resume": track_resume,
}
NO_SIM = ("launcher",)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--track", default="launcher", choices=[*TRACKS, "all"])
    parser.add_argument("--task", default=RETIRED_TASK, help="the retired line's task id")
    parser.add_argument("--resume-task", default="Lizard-Rough-v14", help="the declared task the resume arm uses")
    parser.add_argument("--resume-train-iters", type=int, default=2, help="iterations for a missing source run")
    parser.add_argument("--num_envs", type=int, default=64)
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

    # Each track runs a different subject (the lifeline tracks the retired fixture, `resume` the
    # declared task), so the report names them per track instead of printing one of the two as if
    # it were the run's task.
    report: dict = {
        "tracks_run": tracks,
        "lifeline": {"task": args.task, "line": RETIRED_LINE},
        "resume": {"task": args.resume_task},
        "python": python,
        "tracks": {},
    }
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
