# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Run unchanged historical support scripts in paired native-replication trials.

Sources come from Git bytes and execute as temporary siblings of the live script,
preserving its repository discovery and import paths. No native callbacks are
instrumented. Phase 0 reaches environment creation, policy loading and sampling.
The experiment can complete with failed trials; report.json owns their outcomes.
Historical child records retain actual commands and archived source locations.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "ablation_harness"))
from host_paths import isaac_root, venv_python
from rl_exp.tools.runrecord.binding import git_run, sha256_bytes, sha256_file
from artifact_paths import ArtifactPaths, _relative, _unlinked
from artifact_run import ArtifactRun, _check_bindings, _write, inspect_run

SUPPORT = "rl_exp/tools/diagnose/diagnose_support.py"
REFERENCE = "rl_exp/tools/diagnose/out/runs/support/lifecycle-v3-nineenv-summary-20261022"
CONTROLLED_ENV = {"PYTHONIOENCODING": "utf-8", "OMNI_CRASHREPORTER_ENABLED": "0",
                  "OMNI_CRASHREPORTER_SKIPOLDDUMPUPLOAD": "1"}
KIT_ARGS = ("--/crashreporter/enabled=false --/crashreporter/skipOldDumpUpload=true "
            "--/app/uploadDumpsOnStartup=false")


def _environment_setup(source: bytes) -> str:
    """Compare the entire configuration block before either script creates the environment."""
    tree = ast.parse(source.decode("utf-8"))
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    nodes = []
    collecting = False
    for node in main.body:
        names = {n.id for n in ast.walk(node.targets[0]) if isinstance(n, ast.Name)} if isinstance(node, ast.Assign) else set()
        if "terrain_cfg" in names:
            collecting = True
        if collecting and names & {"gym_env", "agent_cfg"}:
            break
        if collecting:
            nodes.append(node)
    if not nodes:
        raise ValueError("historical environment configuration block not found")
    return ast.dump(ast.Module(body=nodes, type_ignores=[]), include_attributes=False)


def _stop_owned(process):
    """Stop only the process tree launched by this trial, including the uv trampoline."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
    else:
        process.kill()
    process.wait(timeout=15)


def _classify(returncode, text, measurement, stopped):
    logged_native = "Windows fatal exception:" in text
    if returncode & 0xFFFFFFFF == 0xC0000005:
        return "native_access_violation"
    if stopped:
        return "native_exception_timeout" if logged_native else "timeout"
    if returncode != 0 and logged_native:
        return "native_failure"
    if "Traceback (most recent call last):" in text:
        return "python_failure"
    if returncode != 0 or not measurement.is_file():
        return "incomplete"
    report = json.loads(measurement.read_text(encoding="utf-8"))
    if "zero_action" not in report or "target_binding" not in report:
        return "incomplete"
    return "completed_with_native_exception_log" if logged_native else "completed"


def _archive_binding(rows, executable, snapshot):
    matches = [row for row in rows if Path(row["identity"]) == executable]
    if len(matches) != 1:
        raise ValueError("executed source has no unique binding")
    if matches[0]["sha256"] != sha256_file(snapshot) or matches[0]["sha256"] != sha256_file(executable):
        raise ValueError("executed source binding differs from archived source")
    matches[0]["location"] = snapshot.relative_to(REPO).as_posix()


def inspect_results(root: Path) -> dict:
    """Read verified original evidence through the current classifier without rewriting it."""
    inspect_run(root, ArtifactPaths(storage_root=REPO))
    report = json.loads((root / "report.json").read_text(encoding="utf-8"))
    results = []
    for original in report["results"]:
        name = f'pair{original["pair"]}-{original["variant"]}'
        log = root / original["log"]
        measurement = root / "cases" / name / "p0_measure_check.json"
        if sha256_file(log) != original["log_sha256"] or sha256_file(measurement) != original["measurement_sha256"]:
            raise ValueError(f"trial bindings changed: {name}")
        text = log.read_text(encoding="utf-8", errors="replace")
        results.append({"trial": name, "variant": original["variant"],
                        "reported_outcome": original["outcome"],
                        "reviewed_outcome": _classify(original["returncode"], text, measurement, original["forced_stop"]),
                        "returncode": original["returncode"], "exit_hex": f'0x{original["returncode"] & 0xFFFFFFFF:08x}',
                        "native_replication_frame": "physx_replicate.py" in text and "attach_end_fn" in text,
                        "native_frames": [line.strip() for line in text.splitlines()
                                          if "physx_replicate.py" in line and "attach_end_fn" in line]})
    return {"classifier_sha256": sha256_file(Path(__file__)), "original_report_sha256": sha256_file(root / "report.json"),
            "results": results,
            "counts": {variant: dict(Counter(row["reviewed_outcome"] for row in results if row["variant"] == variant))
                       for variant in report["versions"]}}


def _reporter_check(root, controls, kit_args):
    """Check effective local-only settings in Kit before starting any physics trial."""
    probe = root / "reporter_check.py"
    output = root / "reporter_check.json"
    probe.write_text('''import json, pathlib, sys
kit_args, output_name = sys.argv[1:3]
sys.argv = sys.argv[:1]
from isaaclab.app import AppLauncher
app = AppLauncher(headless=True, kit_args=kit_args).app
import carb.settings
settings = carb.settings.get_settings()
values = {name: settings.get(name) for name in (
    "/crashreporter/enabled", "/crashreporter/url", "/crashreporter/skipOldDumpUpload", "/app/uploadDumpsOnStartup")}
pathlib.Path(output_name).write_text(json.dumps(values, indent=2), encoding="utf-8")
ok = values["/crashreporter/enabled"] is True and values["/crashreporter/url"] == ""
ok = ok and values["/crashreporter/skipOldDumpUpload"] is True
ok = ok and values["/app/uploadDumpsOnStartup"] is False
app.close(exit_code=0 if ok else 1)
''', encoding="utf-8")
    with (root / "reporter_check.log").open("wb") as log:
        process = subprocess.Popen([venv_python(), "-B", str(probe), kit_args, str(output)], cwd=REPO,
                                   env=dict(os.environ, **controls), stdout=log, stderr=subprocess.STDOUT)
        try:
            process.wait(timeout=60)
        finally:
            _stop_owned(process)
    values = json.loads(output.read_text(encoding="utf-8"))
    if (process.returncode != 0 or values["/crashreporter/enabled"] is not True
            or values["/crashreporter/url"] != "" or values["/crashreporter/skipOldDumpUpload"] is not True
            or values["/app/uploadDumpsOnStartup"] is not False):
        raise ValueError("local crash reporter restrictions did not take effect; no physics trials started")
    return values


def _trial(root, variant, number, seed, snapshot, executable, bindings, timeout):
    name = f"pair{number}-{variant}"
    case = root / "cases" / name
    label = case.relative_to(REPO / "rl_exp/tools/diagnose/out").as_posix()
    command = [venv_python(), "-B", str(executable), "--headless", "--task", "Lizard2-Flat-v3",
               "--checkpoint", bindings["checkpoint"], "--phases", "0", "--reps", "1", "--base_seed", "1000",
               "--heights", "0.05,0.10,0.15,0.20", "--label", label,
               "--kit_args", bindings.get("kit_args", KIT_ARGS)]
    # Carbonite's documented environment overrides apply before plugin startup,
    # including old-dump upload. CLI settings repeat the restriction in both arms.
    environment = dict(os.environ, **bindings.get("environment", CONTROLLED_ENV), PYTHONHASHSEED=str(seed))
    log = root / f"{name}.log"
    _check_bindings(bindings["rows"], REPO)
    print(f"START {name} hash_seed={seed}", flush=True)
    started = time.monotonic()
    stopped = None
    with log.open("wb") as stream:
        process = subprocess.Popen(command, cwd=REPO, env=environment, stdout=stream, stderr=subprocess.STDOUT)
        try:
            while process.poll() is None:
                if time.monotonic() - started > timeout:
                    stopped = "deadline"
                    _stop_owned(process)
                time.sleep(0.25)
        finally:
            _stop_owned(process)
    text = log.read_text(encoding="utf-8", errors="replace")
    if "Uploading minidump:" in text:
        raise ValueError("crash reporter attempted an upload; no further trials allowed")
    status = _classify(process.returncode, text, case / "p0_measure_check.json", stopped)
    _check_bindings(bindings["rows"], REPO)
    # Preserve the actual historical source rather than falsely binding the live script.
    child_record = case / "run.json"
    if child_record.is_file():
        doc = json.loads(child_record.read_text(encoding="utf-8"))
        if doc["config"]["env"]["scene"]["replicate_physics"] is not True:
            raise ValueError("historical trial did not enable native replication")
        _archive_binding(doc["code"], executable, snapshot)
        doc["command"] = command
        doc["comparison"] = {"variant": variant, "snapshot": snapshot.relative_to(REPO).as_posix(),
                             "restore_script_to": str(executable), "outcome": status,
                             "note": "Restore exact archived source at command[2], use a fresh label to replay."}
        _write(child_record, doc, root)
    result = {"variant": variant, "pair": number, "hash_seed": seed, "outcome": status,
              "elapsed_s": round(time.monotonic() - started, 3), "returncode": process.returncode,
              "forced_stop": stopped, "command": command, "source_sha256": sha256_file(snapshot),
              "native_replication_frame": "physx_replicate.py" in text and "attach_end_fn" in text,
              "measurement_sha256": sha256_file(case / "p0_measure_check.json"),
              "log": log.relative_to(root).as_posix(), "log_sha256": sha256_file(log)}
    _write(root / f"{name}.json", result, root)
    print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--inspect_results", type=Path, help="read-only review of a completed matrix with current classifier")
    parser.add_argument("--before", default="6d89441")
    parser.add_argument("--after", default="8d94688")
    parser.add_argument("--pairs", type=int, default=4)
    parser.add_argument("--timeout_s", type=float, default=150)
    parser.add_argument("--crash_reporter", choices=("off", "local"), default="off",
                        help="local retains crash handling with empty upload URL and startup upload disabled")
    parser.add_argument("--reference_run", type=Path, default=REPO / REFERENCE)
    args = parser.parse_args()
    if args.inspect_results:
        print(json.dumps(inspect_results(args.inspect_results.resolve()), indent=2))
        return
    if args.output_dir is None:
        parser.error("--output_dir is required for new trials")
    if not 1 <= args.pairs <= 12 or args.timeout_s < 30:
        raise ValueError("pairs must be 1..12 and timeout_s at least 30")
    root = _unlinked(REPO, _relative(args.output_dir.resolve().relative_to(REPO).as_posix()))
    controls = dict(CONTROLLED_ENV)
    kit_args = KIT_ARGS
    if args.crash_reporter == "local":
        controls.update(OMNI_CRASHREPORTER_ENABLED="1", OMNI_CRASHREPORTER_URL="")
        kit_args = KIT_ARGS.replace("enabled=false", "enabled=true")
        kit_args += f' --/crashreporter/url="" --/crashreporter/dumpDir={root.as_posix()}/dumps'
    paths = ArtifactPaths(storage_root=REPO)
    reference = json.loads((args.reference_run / "run.json").read_text(encoding="utf-8"))
    checkpoint = next(row["location"] for row in reference["inputs"] if row["location"].endswith(".pt"))
    code = [row for row in reference["code"] if row["logical_path"] != SUPPORT]
    code.append(paths.describe(Path(__file__)))
    inputs = list(reference["inputs"])
    framework = isaac_root()
    for relative in ("source/isaaclab_physx/isaaclab_physx/cloner/physx_replicate.py",
                     "source/isaaclab_physx/isaaclab_physx/physics/physx_manager.py",
                     "source/isaaclab/isaaclab/scene/interactive_scene.py",
                     "source/isaaclab/isaaclab/sim/simulation_context.py"):
        inputs.append(paths.describe(framework / relative))
    versions, sources = {}, {}
    for name, revision in (("before", args.before), ("after", args.after)):
        commit = git_run(REPO, "log", "-1", "--format=%H", revision)
        if not commit:
            raise ValueError(f"unknown revision: {revision}")
        sources[name] = subprocess.run(["git", "show", f"{commit}:{SUPPORT}"], cwd=REPO,
                                       capture_output=True, check=True).stdout
        versions[name] = {"commit": commit, "sha256": sha256_bytes(sources[name])}
    if _environment_setup(sources["before"]) != _environment_setup(sources["after"]):
        raise ValueError("historical environment setup differs; isolate those differences before comparison")
    metadata = {"topic": "support-native-ab", "work_id": "diagnostic-artifact-lifecycle", "owner": "codex",
                "retention_reason": "Paired historical native replication failures and controls; not a physics acceptance.",
                "command": [sys.executable, str(Path(__file__)), *sys.argv[1:]], "inputs": inputs, "code": code,
                "config": {"sources": versions, "pairs": args.pairs, "phase": "0", "num_envs": 9,
                           "native_replication": True, "environment_setup_ast_equal": True,
                           "timeout_s": args.timeout_s, "hash_seeds": list(range(args.pairs)),
                           "crash_reporter": args.crash_reporter,
                           "controlled_environment": controls, "kit_args": kit_args}}
    bindings = {"rows": inputs + code, "checkpoint": checkpoint, "environment": controls, "kit_args": kit_args}
    token = uuid.uuid4().hex[:12]
    executables = {}
    results = []
    with ArtifactRun(root, paths, metadata, ["report.json", "sources/before.py", "sources/after.py", "driver.py"]):
        try:
            (root / "driver.py").write_bytes(Path(__file__).read_bytes())
            _archive_binding(code, Path(__file__), root / "driver.py")
            if args.crash_reporter == "local":
                (root / "dumps").mkdir()
                _reporter_check(root, controls, kit_args)
            (root / "sources").mkdir()
            for variant, content in sources.items():
                snapshot = root / "sources" / f"{variant}.py"
                snapshot.write_bytes(content)
                executable = REPO / f"rl_exp/tools/diagnose/_tmp_support_native_{token}_{variant}.py"
                with executable.open("xb") as stream:
                    stream.write(content)
                executables[variant] = executable
            for number in range(args.pairs):
                order = ("before", "after") if number % 2 == 0 else ("after", "before")
                for variant in order:
                    results.append(_trial(root, variant, number, number, root / "sources" / f"{variant}.py",
                                          executables[variant], bindings, args.timeout_s))
            report = {"versions": versions, "results": results,
                      "counts": {variant: dict(Counter(r["outcome"] for r in results if r["variant"] == variant))
                                 for variant in sources},
                      "scope": "Same current dependencies; native full scripts through Phase 0; small paired sample."}
            _write(root / "report.json", report, root)
            print(json.dumps(report["counts"]), flush=True)
        finally:
            for variant, executable in executables.items():
                if sha256_file(executable) != versions[variant]["sha256"]:
                    raise ValueError(f"temporary source changed; preserved for inspection: {executable}")
                executable.unlink()


if __name__ == "__main__":
    main()
