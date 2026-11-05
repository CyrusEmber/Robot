# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Probe the real launcher/fork handoff without creating an environment or learning.

Run with the IsaacLab interpreter. Outputs are exclusively diagnostic, not training runs.
The temporary sitecustomize installs the dependency guard and two pre-environment stops;
it redirects only manifest.begin's log_dir and stops immediately after the real call.
"""

from __future__ import annotations

import ast
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from rl_exp.tools.runrecord import binding, provenance  # noqa: E402

FORK = provenance.isaac_root()
TRAIN = FORK / "scripts/reinforcement_learning/rsl_rl/train.py" if FORK else None
LAUNCHER = REPO / "rl_exp/tools/launch_recipe.py"
OUT = REPO / "rl_exp/tools/diagnose/out/launcher_source_probe"
TASK = "Lizard2-Flat-v7"

# Executed in both independent interpreters. A startup failure must be fatal: Python normally
# prints sitecustomize errors and continues, which would be unsafe for this particular probe.
SITE = r'''import os, sys
try:
    import ast, importlib.util, json, pathlib
    from rl_exp.tools.runrecord import binding
    repo = pathlib.Path(os.environ["PROBE_REPO"]).resolve()
    train = pathlib.Path(os.environ["PROBE_TRAIN"]).resolve()
    out = pathlib.Path(os.environ["PROBE_OUT"]).resolve()
    trainer = pathlib.Path(sys.argv[0]).name == "train.py"
    role = "trainer" if trainer else "launcher"
    source = repo / "rl_exp/tools/runrecord/provenance.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    values = [n.value for n in tree.body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == "EVAL_EXCLUSIVE_PATHS" for t in n.targets)]
    if len(values) != 1:
        raise RuntimeError("expected one literal EVAL_EXCLUSIVE_PATHS")
    paths = ast.literal_eval(values[0])
    forbidden = {(repo / p).resolve() for p in paths}
    if not forbidden:
        raise RuntimeError("empty dependency declaration")
    entered = False
    filename_cache = {}
    def stop(code, marker, detail):
        print(marker + " " + json.dumps(detail, ensure_ascii=False, default=str), flush=True)
        os._exit(code)
    def profile(frame, event, arg):
        global entered
        if event != "call":
            return
        filename = frame.f_code.co_filename
        if filename not in filename_cache:
            filename_cache[filename] = pathlib.Path(filename).resolve() if not filename.startswith("<") else None
        path = filename_cache[filename]
        if path in forbidden:
            stop(86, "DEPENDENCY_GUARD_HIT", {"role": role, "path": str(path), "pid": os.getpid()})
        if trainer and path == train and frame.f_code.co_name == "<module>":
            entered = True
            train_sha256 = binding.sha256_file(train)
            if train_sha256 is None:
                raise OSError(f"cannot hash {train}")
            stop_data = {"pid": os.getpid(), "ppid": os.getppid(), "cwd": os.getcwd(),
                         "executable": sys.executable, "argv": sys.argv,
                         "train_file": str(path), "train_sha256": train_sha256}
            print("REAL_TRAIN_ENTER " + json.dumps(stop_data, ensure_ascii=False), flush=True)
        if trainer and frame.f_code.co_name == "learn":
            stop(88, "SAFETY_LEARN_BLOCKED", {"path": filename})
    def inject():
        target = repo / os.environ["PROBE_INJECT_PATH"]
        print("INJECTION_ENTER " + json.dumps({"role": role, "path": str(target)}), flush=True)
        spec = importlib.util.spec_from_file_location("source_audit_injection", target)
        spec.loader.exec_module(importlib.util.module_from_spec(spec))
        stop(89, "INJECTION_NOT_BLOCKED", {"path": str(target)})
    if role == "launcher" and os.environ.get("PROBE_INJECT_ROLE") == role:
        from rl_exp.tools.verify import check_recipe_map
        original_bind = check_recipe_map.bind
        def bind_probe(*args, **kwargs):
            inject()
            return original_bind(*args, **kwargs)
        check_recipe_map.bind = bind_probe
    # A separate line-level stop prevents gym.make even if the begin wrapper returns.
    # Refuse if the expected fork's source structure has changed.
    train_tree = ast.parse(train.read_text(encoding="utf-8"), filename=str(train))
    main_nodes = [n for n in train_tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"]
    gym_calls = [n for n in ast.walk(main_nodes[0]) if isinstance(n, ast.Attribute)
                 and isinstance(n.value, ast.Name) and n.value.id == "gym" and n.attr == "make"]
    if len(main_nodes) != 1 or len(gym_calls) != 1:
        raise RuntimeError("cannot identify unique fork main/gym.make stop")
    stop_line = gym_calls[0].lineno - 1  # outer _or_die call starts on preceding line
    def trace(frame, event, arg):
        if event == "call":
            filename = frame.f_code.co_filename
            if filename not in filename_cache:
                filename_cache[filename] = pathlib.Path(filename).resolve() if not filename.startswith("<") else None
            if filename_cache[filename] in forbidden:
                stop(86, "DEPENDENCY_GUARD_HIT", {"role": role, "path": str(filename_cache[filename]),
                     "pid": os.getpid(), "via": "trace"})
        if frame.f_code.co_name == "main" and pathlib.Path(frame.f_code.co_filename).resolve() == train:
            if event == "line" and frame.f_lineno >= stop_line:
                stop(87, "SAFETY_PRE_GYM_STOP", {"line": frame.f_lineno, "pid": os.getpid()})
            return trace
        return None
    sys.setprofile(profile)
    sys.settrace(trace)
    print("DEPENDENCY_GUARD_READY " + json.dumps({"role": role, "pid": os.getpid(),
          "ppid": os.getppid(), "executable": sys.executable, "cwd": os.getcwd(),
          "argv": sys.argv, "declaration": paths, "stop_line": stop_line}), flush=True)
    if trainer:
        if pathlib.Path(sys.argv[0]).resolve() != train or pathlib.Path.cwd().resolve() != train.parents[3]:
            raise RuntimeError("unexpected trainer path or cwd")
        sys.argv.append("--headless")
        from rl_exp.tools.runrecord import manifest
        original = manifest.begin
        if os.environ.get("PROBE_INJECT_ROLE") == role:
            original_sources = manifest.prov.code_sources
            def sources_probe(*args, **kwargs):
                print("INJECTION_BEGIN_PATH " + json.dumps({"caller": sys._getframe(1).f_code.co_filename,
                      "line": sys._getframe(1).f_lineno}), flush=True)
                inject()
                return original_sources(*args, **kwargs)
            manifest.prov.code_sources = sources_probe
        def begin_probe(*args, **kwargs):
            print("PROFILE_AT_BEGIN " + json.dumps({"preserved": sys.getprofile() is profile,
                  "trace_preserved": sys.gettrace() is trace}), flush=True)
            sys.setprofile(profile)
            sys.settrace(trace)
            caller = sys._getframe(1)
            if pathlib.Path(caller.f_code.co_filename).resolve() != train or not entered:
                stop(90, "SAFETY_WRONG_BEGIN_CALLER", {"caller": caller.f_code.co_filename})
            print("REAL_BEGIN_CALL " + json.dumps({"caller": caller.f_code.co_filename,
                  "line": caller.f_lineno, "original": original.__code__.co_filename,
                  "original_line": original.__code__.co_firstlineno,
                  "original_log_dir": str(kwargs.get("log_dir")),
                  "isolated_log_dir": str(out / "manifest")}), flush=True)
            kwargs["log_dir"] = out / "manifest"
            ctx = original(*args, **kwargs)
            stop(73, "REAL_BEGIN_RETURN_STOP", {"manifest": str(ctx.manifest_path),
                 "exists": ctx.manifest_path.is_file(), "pid": os.getpid(), "learner_called": False})
        manifest.begin = begin_probe
except BaseException as exc:
    print("PROBE_STARTUP_FATAL " + repr(exc), file=sys.stderr, flush=True)
    os._exit(91)
'''


def main() -> int:
    if TRAIN is None or not TRAIN.is_file():
        raise RuntimeError("IsaacLab trainer unavailable; check paths.yaml or RL_ISAAC_ROOT")
    declaration_tree = ast.parse((REPO / "rl_exp/tools/runrecord/provenance.py").read_text(encoding="utf-8"))
    declaration = [node.value for node in declaration_tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "EVAL_EXCLUSIVE_PATHS" for t in node.targets)]
    if len(declaration) != 1:
        raise RuntimeError("expected a unique EVAL_EXCLUSIVE_PATHS")
    paths = ast.literal_eval(declaration[0])
    run = OUT / (datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    run.mkdir(parents=True, exist_ok=False)
    cases = [("control", "", "")]
    cases += [(f"{role}-{i}", role, path) for role in ("launcher", "trainer") for i, path in enumerate(paths)]
    train_sha256 = binding.sha256_file(TRAIN)
    if train_sha256 is None:
        raise OSError(f"cannot hash {TRAIN}")
    summary = {"diagnostic_only": True, "task": TASK, "fork_train": str(TRAIN),
               "fork_train_sha256": train_sha256, "cases": []}
    print(f"PROBE_OUTPUT {run}", flush=True)
    with tempfile.TemporaryDirectory(prefix="launcher-source-probe-") as temp:
        site = pathlib.Path(temp) / "sitecustomize.py"
        site.write_text(SITE, encoding="utf-8")
        summary["site_sha256"] = binding.sha256_file(site)
        if summary["site_sha256"] is None:
            raise OSError(f"cannot hash {site}")
        for label, role, path in cases:
            case = run / label
            case.mkdir()
            env = {**os.environ, "PROBE_REPO": str(REPO), "PROBE_TRAIN": str(TRAIN), "PROBE_OUT": str(case),
                   "PROBE_INJECT_ROLE": role, "PROBE_INJECT_PATH": path, "RL_ISAAC_ROOT": str(FORK),
                   "RL_ALLOW_DIRTY_TREE": "isolated source-audit diagnostic; stops before gym.make; no training",
                   "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1",
                   "PYTHONPATH": os.pathsep.join((temp, str(REPO), os.environ.get("PYTHONPATH", "")))}
            command = [sys.executable, str(LAUNCHER), "--task", TASK, "--num_envs", "1", "--seed", "7",
                       "--max_iterations", "0", "--record", str(case / "launcher.json"),
                       "--launch", "--python", sys.executable]
            (case / "command.json").write_text(json.dumps({"command": command, "cwd": str(REPO),
                "inject_role": role, "inject_path": path, "temporary_site_sha256": summary["site_sha256"],
                "diagnostic_override": env["RL_ALLOW_DIRTY_TREE"]}, indent=2), encoding="utf-8")
            with (case / "stdout.txt").open("wb") as stdout, (case / "stderr.txt").open("wb") as stderr:
                proc = subprocess.Popen(command, cwd=REPO, env=env, stdout=stdout, stderr=stderr)
                try:
                    code = proc.wait(timeout=240)
                except subprocess.TimeoutExpired:
                    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, check=False)
                    code = proc.wait()
                    code = f"timeout (launcher exit {code})"
            text = (case / "stdout.txt").read_text(encoding="utf-8", errors="replace")
            markers = [line for line in text.splitlines() if line.startswith(("DEPENDENCY_GUARD_READY ",
                       "REAL_TRAIN_ENTER ", "REAL_BEGIN_CALL ", "REAL_BEGIN_RETURN_STOP ",
                       "INJECTION_ENTER ", "DEPENDENCY_GUARD_HIT ", "SAFETY_"))]
            expected = 73 if not role else 86
            hit = [line for line in markers if line.startswith("DEPENDENCY_GUARD_HIT ")]
            trainer_entered = any(line.startswith("REAL_TRAIN_ENTER ") for line in markers)
            begin_entered = any(line.startswith("REAL_BEGIN_CALL ") for line in markers)
            ended = any(line.startswith("REAL_BEGIN_RETURN_STOP ") for line in markers)
            hit_path = json.loads(hit[-1].split(" ", 1)[1])["path"] if hit else None
            valid = code == expected and (ended if not role else hit_path is not None
                    and pathlib.Path(hit_path).resolve() == (REPO / path).resolve()
                    and (begin_entered and trainer_entered if role == "trainer" else not trainer_entered))
            result = {"label": label, "injection": path or None, "exit": code, "expected": expected,
                      "passed": bool(valid), "trainer_entered": trainer_entered, "begin_entered": begin_entered,
                      "manifest_files": [str(p.relative_to(case)) for p in case.rglob("*manifest*.json")],
                      "markers": markers}
            summary["cases"].append(result)
            (case / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            (run / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{label}: exit={code}, expected={expected}, {'PASS' if valid else 'FAIL'}", flush=True)
    return 0 if all(case["passed"] for case in summary["cases"]) else 1


if __name__ == "__main__":
    sys.exit(main())
