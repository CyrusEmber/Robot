# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""The launcher's cases, and phase C's cross-check (ARCH_PLAN 2.4 C2/C3).

C3 asks the two entries to *each* bind what they read and then be compared, because an entry
that only inherits the other's answer has no evidence chain of its own. So the cases here are:
what the launcher refuses, what it records, and whether the record it produces for a task
matches, field for field, the lifecycle verdict the trainer's T0 carries for the same task --
which is what "the two entries cannot answer differently" has to mean in practice.

The comparison is only meaningful if both sides are produced for the same directory: the
launcher and trainer read an isolated active-line fixture through the same module;
both hash its actual files. The refusal case uses the retirement the directory really
carries (``lizard2/main``'s v1, retired 2026-10-08): a line or version is never retired to
make a test pass (2.1a), and the refusal must not promise a successor the index does not
register.
"""

from __future__ import annotations

import inspect
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from rl_exp.tools import launch_recipe  # noqa: E402
from rl_exp.tools.runrecord import lifecycle  # noqa: E402
from rl_exp.tools.runrecord import manifest as M  # noqa: E402
from test_lifecycle_gate import active_index  # noqa: E402

TASK = "Lizard2-Flat-v3"
#: The retirement the directory really carries, judged on the real index rather than a fixture: a
#: line is never retired to make a test pass (2.1a). lizard2/main's v1 exited maintenance on
#: 2026-10-08 and its recipe and classes are still registered, so the launch reaches the refusal.
RETIRED_TASK = "Lizard2-Flat-v1"
RETIRED_LINE = "lizard2/main"


def main() -> int:
    """Run every case; each one asserts something a reader cannot see from the happy path."""
    problems: list[str] = []
    problems.extend(_dependency_cases())
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = pathlib.Path(tmp_dir)
        problems.extend(_refusals())
        with active_index(tmp):
            problems.extend(_happy_path())
            problems.extend(_cross_check(tmp))
    if problems:
        for problem in problems:
            print(f"FAIL {problem}")
        print(f"launcher: {len(problems)} case(s) wrong")
        return 1
    print("  the launcher refuses what the directory refuses, and matches the trainer's T0")
    print("LAUNCHER_OK")
    return 0


def _happy_path() -> list[str]:
    """An active task: allowed, with the identity, the built entries and the golden recorded."""
    problems: list[str] = []
    record = launch_recipe.plan(TASK, argv=["launch_recipe.py", "--task", TASK], num_envs=64, seed=7)
    if not record["allowed"]:
        return [f"{TASK} must be launchable from an active line: {record['reason']}"]
    if record["recipe"] != "lizard2-flat-v3@1" or record["lifecycle"]["line"] != "lizard2/main":
        problems.append(f"the directory's own identity must be recorded: {record['identity']!r}")
    declared = lifecycle.read_index()["recipes"]["recipes"][record["recipe"]]["env_cfg_entry"]
    if record["recipe_entry"]["env_cfg_entry"] != declared:
        problems.append(f"the declared entry must be recorded verbatim: {record['recipe_entry']!r}")
    if not record["golden"].get("golden_digest"):
        problems.append(f"the golden comparison must be recorded, got {record['golden']!r}")
    if record["lifecycle"]["directory_sha256"] != lifecycle.read_index()["digests"]:
        problems.append("the record must name the directory it was read from, by digest")
    if record["lifecycle"]["operation"] != "new_train":
        problems.append(f"a launch without --resume is new work, got {record['lifecycle']['operation']!r}")
    resumed = launch_recipe.plan(TASK, argv=["launch_recipe.py", "--resume"], resume=True, load_run=".*")
    if resumed["lifecycle"]["operation"] != "resume":
        problems.append("--resume must read as a resume (the table treats the two differently)")
    return problems


def _refusals() -> list[str]:
    """What the launcher must not let through, on the retirement the directory really carries."""
    problems: list[str] = []
    invented = launch_recipe.plan("Lizard-Invented-v99", argv=["launch_recipe.py"])
    if invented["allowed"] or "not in the recipe map" not in invented["reason"]:
        problems.append(f"an unregistered task must be refused: {invented.get('reason')!r}")

    retired = launch_recipe.plan(RETIRED_TASK, argv=["launch_recipe.py", "--task", RETIRED_TASK])
    if retired["allowed"]:
        problems.append(f"{RETIRED_TASK} must be refused: the directory retired it")
    if retired["lifecycle"]["status"] != "retired" or retired["lifecycle"]["line"] != RETIRED_LINE:
        problems.append(f"the refusal must carry the identity it read: {retired.get('lifecycle')!r}")
    if "retired line" not in retired["reason"]:
        problems.append(f"the refusal must say the subject is retired: {retired.get('reason')!r}")
    if "successor" in retired["reason"]:
        problems.append(
            f"the index registers no successor for {RETIRED_LINE}, so the refusal must not promise one:"
            f" {retired['reason']!r}"
        )
    # this checkout's directory is what was judged: no fixture stands in for it
    if retired["lifecycle"]["directory_sha256"] != lifecycle.read_index(_REPO)["digests"]:
        problems.append("the checkout's own directory must be the one judged")
    return problems


FIELDS = ("operation", "task", "recipe", "line", "status", "directory_sha256")


def _compare(launcher: dict, trainer: dict) -> list[str]:
    """What the two entries disagree on: phase C's cross-check, kept callable so it can be falsified.

    Args:
        launcher: the ``lifecycle`` evidence :func:`rl_exp.tools.launch_recipe.plan` recorded.
        trainer: the ``declaration.lifecycle`` the trainer's T0 carries.

    Returns:
        One line per disagreement.
    """
    return [
        f"{field}: launcher {launcher.get(field)!r} != trainer {trainer.get(field)!r}"
        for field in ("declared_params_line", *FIELDS)
        if launcher.get(field) != trainer.get(field)
    ]


def _cross_check(tmp: pathlib.Path) -> list[str]:
    """C3: the launcher's record and the trainer's T0 verdict, for the same directory.

    The trainer's side is produced by the real call site (``manifest.begin``, which the fork
    patch calls before ``gym.make``), not by a copy of its logic.
    """
    problems: list[str] = []
    argv = ["train.py", "--task", TASK, "--num_envs", "64"]
    record = launch_recipe.plan(TASK, argv=argv, num_envs=64)
    if not record["allowed"]:
        return [f"the cross-check needs an allowed launch first: {record['reason']}"]

    os.environ["RL_ALLOW_DIRTY_TREE"] = "offline test: the cross-check needs a launch record"
    try:
        log_dir = tmp / "logs" / "cross_check"
        ctx = M.begin(log_dir=log_dir, task=TASK, argv=argv, env_cfg=_env_cfg(), agent_cfg=_agent_cfg())
        written = json.loads(ctx.manifest_path.read_text(encoding="utf-8"))["declaration"]["lifecycle"]
    finally:
        os.environ.pop("RL_ALLOW_DIRTY_TREE", None)

    problems.extend(f"the two entries disagree: {line}" for line in _compare(record["lifecycle"], written))

    # the comparison has to be able to fail: a single field moved on either side is a difference
    doctored = {**written, "line": "lizard/parkour"}
    if not _compare(record["lifecycle"], doctored):
        problems.append("a differing field slipped through the cross-check")
    return problems


def _env_cfg():
    """The env cfg the trainer's T0 reads: declared line and version, nothing else used here."""

    class _Cfg:
        params_version = "v3"
        params_line = "lizard2/main"
        seed = 42
        decimation = 4

        class sim:  # noqa: N801
            dt = 0.005

        class scene:  # noqa: N801
            num_envs = 64

    return _Cfg()


def _agent_cfg():
    """An agent config with the fields the trainer's T0 and the gate read."""

    class _Agent:
        resume = False
        load_run = None
        load_checkpoint = None
        max_iterations = 3000
        experiment_name = "lizard2_v3"
        seed = 42
        device = "cuda:0"

        def to_dict(self):
            return {"experiment_name": self.experiment_name, "seed": self.seed}

    return _Agent()


# Installed by sitecustomize in both fresh interpreters, before either entry imports repository code.
_SITE = r'''
import ast, importlib.util, os, pathlib, sys

repo = pathlib.Path(os.environ["PROBE_REPO"])
source = repo / "rl_exp/tools/runrecord/provenance.py"
tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
declarations = [node.value for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "EVAL_EXCLUSIVE_PATHS"
                        for target in node.targets)]
if len(declarations) != 1:
    raise RuntimeError("expected one literal eval-exclusive declaration")
forbidden = {(repo / path).resolve() for path in ast.literal_eval(declarations[0])}
if not forbidden or (repo / "ablation_harness/record.py").resolve() not in forbidden:
    raise RuntimeError("record.py must be in the nonempty eval-exclusive declaration")

is_trainer = pathlib.Path(sys.argv[0]).name == "train.py"
role = "trainer" if is_trainer else "launcher"
filenames = {}

def guard(frame, event, arg):
    if event == "call":
        filename = frame.f_code.co_filename
        if filename not in filenames:
            filenames[filename] = not filename.startswith("<") and pathlib.Path(filename).resolve() in forbidden
        if filenames[filename]:
            print(f"DEPENDENCY_GUARD_HIT {role} {filename}", file=sys.stderr, flush=True)
            raise SystemExit(86)
    return None
# The guard needs call events only; avoid the trace hook's per-frame tracing overhead.
sys.setprofile(guard)
print(f"DEPENDENCY_GUARD_READY {role} {os.getpid()} {os.getppid()}", flush=True)

from rl_exp.tools.runrecord import lifecycle, provenance
read = lifecycle.read_index
lifecycle.read_index = lambda root=None: read(root or pathlib.Path(os.environ["PROBE_INDEX"]))
if os.environ.get("PROBE_INJECT") == role:
    if is_trainer:
        from rl_exp.tools.runrecord import manifest
        original = manifest.prov.code_sources
        def injected(*args, **kwargs):
            spec = importlib.util.spec_from_file_location("dependency_probe", repo / os.environ["PROBE_PATH"])
            spec.loader.exec_module(importlib.util.module_from_spec(spec))
            return original(*args, **kwargs)
        manifest.prov.code_sources = injected
    else:
        original = lifecycle.check_recipe_map.bind
        def injected(*args, **kwargs):
            spec = importlib.util.spec_from_file_location("dependency_probe", repo / os.environ["PROBE_PATH"])
            spec.loader.exec_module(importlib.util.module_from_spec(spec))
            return original(*args, **kwargs)
        lifecycle.check_recipe_map.bind = injected
'''


def _dependency_cases() -> list[str]:
    """Run the real launcher CLI and its child stub, not a simulation or the fork trainer."""
    problems = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = pathlib.Path(tmp_dir)
        with active_index(tmp):
            pass  # materialize the same active fixture independently read in both processes
        (tmp / "sitecustomize.py").write_text(_SITE, encoding="utf-8")
        trainer = tmp / "scripts/reinforcement_learning/rsl_rl/train.py"
        trainer.parent.mkdir(parents=True)
        trainer.write_text(
            "import json, os, pathlib, sys\n"
            "from rl_exp.tools.runrecord import manifest as M\n"
            + inspect.getsource(_env_cfg) + "\n" + inspect.getsource(_agent_cfg) + "\n"
            "task = sys.argv[sys.argv.index('--task') + 1]\n"
            "print('TRAINER_STUB_ENTER ' + json.dumps({'pid': os.getpid(), 'ppid': os.getppid(), "
            "'argv': sys.argv, 'cwd': os.getcwd(), 'executable': sys.executable}), flush=True)\n"
            "ctx = M.begin(log_dir=pathlib.Path(os.environ['PROBE_LOG']), task=task, "
            "argv=sys.argv, env_cfg=_env_cfg(), agent_cfg=_agent_cfg())\n"
            "record = json.loads(ctx.manifest_path.read_text(encoding='utf-8'))\n"
            "assert record['declaration']['lifecycle']['allowed']\n"
            "print('TRAINER_MANIFEST_OK', flush=True)\n",
            encoding="utf-8",
        )
        launcher = _REPO / "rl_exp/tools/launch_recipe.py"

        def run(case):
            label, launch, injection, path = case
            env = {**os.environ, "PROBE_REPO": str(_REPO), "PROBE_INDEX": str(tmp / "active_index"),
                   "PROBE_INJECT": injection, "PROBE_PATH": path, "PROBE_LOG": str(tmp / label), "RL_ISAAC_ROOT": str(tmp),
                   "RL_ALLOW_DIRTY_TREE": "offline dependency check, not training",
                   "PYTHONPATH": os.pathsep.join((str(tmp), str(_REPO), os.environ.get("PYTHONPATH", "")))}
            return subprocess.run(
                [sys.executable, str(launcher), "--task", TASK, "--num_envs", "64", "--seed", "7",
                 *(["--launch", "--python", sys.executable] if launch else [])],
                cwd=_REPO, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
            )

        paths = ("ablation_harness/eval.py", "ablation_harness/record.py", "ablation_harness/run_ablation.py")
        cases = [("default", False, "trainer", paths[0]), ("handoff", True, "", paths[0])]
        cases.extend((f"{role}-injected-{i}", True, role, path)
                     for role in ("launcher", "trainer") for i, path in enumerate(paths))
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(run, cases))
        for (label, _, _, path), result in zip(cases, results):
            out, err = result.stdout, result.stderr
            ready = [line.split() for line in out.splitlines() if line.startswith("DEPENDENCY_GUARD_READY ")]
            launcher_pids = [int(line[2]) for line in ready if line[1] == "launcher"]
            trainer_pids = [int(line[2]) for line in ready if line[1] == "trainer"]
            stub_lines = [line.removeprefix("TRAINER_STUB_ENTER ") for line in out.splitlines()
                          if line.startswith("TRAINER_STUB_ENTER ")]
            stub = json.loads(stub_lines[0]) if len(stub_lines) == 1 else None
            launcher_ready = len(launcher_pids) == 1
            trainer_ready = len(trainer_pids) == 1
            entered = stub is not None
            handoff = (launcher_ready and trainer_ready and entered
                       and stub["pid"] == trainer_pids[0] != launcher_pids[0]
                       and stub["ppid"] == int(next(line[3] for line in ready if line[1] == "trainer"))
                       # Windows venv launchers can insert a native process between interpreters.
                       and pathlib.Path(stub["cwd"]).resolve() == tmp.resolve()
                       and pathlib.Path(stub["executable"]).resolve() == pathlib.Path(sys.executable).resolve()
                       and (tmp / stub["argv"][0]).resolve() == trainer.resolve()
                       and stub["argv"][1:] == ["--task", TASK, "--num_envs", "64", "--seed", "7"])
            manifest_ok = "TRAINER_MANIFEST_OK" in out
            if label == "default":
                ok = result.returncode == 0 and launcher_ready and not trainer_ready and not entered
            elif label == "handoff":
                ok = result.returncode == 0 and handoff and manifest_ok
            elif label.startswith("launcher-injected"):
                ok = (result.returncode == 86 and launcher_ready and not trainer_ready and not entered
                      and "DEPENDENCY_GUARD_HIT launcher " in err and pathlib.Path(path).name in err)
            else:
                ok = (result.returncode == 86 and handoff and not manifest_ok
                      and "DEPENDENCY_GUARD_HIT trainer " in err and pathlib.Path(path).name in err)
            if not ok:
                problems.append(f"dependency {label}: exit={result.returncode}\nstdout={out}\nstderr={err}")
            else:
                print(f"  dependency {label}: {'guard hit' if 'injected' in label else 'completed'}")
    return problems


if __name__ == "__main__":
    sys.exit(main())
