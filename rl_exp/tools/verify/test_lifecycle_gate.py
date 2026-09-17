# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""The startup lifecycle check's own cases (ARCH_PLAN 2.2, stage C1).

A gate cannot be shown by its happy path: one that only ever allows is indistinguishable from no
gate at all, and this one decides whether a *trainer process* starts. So every case below is a
rule of 2.2 with a directory behind it, and the properties a reader cannot see from the code get
their own cases:

* **a refusal is evidence, not silence** -- the trainer's T0 is on disk with the verdict before
  the refusal is raised, so a refused launch is distinguishable from one that never happened;
* **a refusal is a terminal state** -- the record of a refused launch is complete, and ``--verify``
  reads it as a refusal instead of as a run that died on the way to T1;
* **nothing is defaulted** -- an unreadable index, an unregistered task and a line with no
  lifecycle entry all refuse. "Not known" is never "active".

Most cases build a synthetic index (``root=`` is the entry that moves the read), because identity
and refusal paths must be exercisable without editing the real directory. The retired case needs
no synthetic tree at all: ``lizard/parkour`` is retired in the real index, and 2.1a forbids
retiring a line to make a test pass -- so that one is read from this checkout.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from rl_exp.tools.runrecord import lifecycle  # noqa: E402
from rl_exp.tools.runrecord import manifest as M  # noqa: E402

MAIN = "lizard/main"
SIDE = "lizard/parkour"
TASK = "Lizard-Rough-v14"
SIDE_TASK = "Lizard-Parkour-Climb-v1"
MAIN_RECIPE = "teacher-v14@1"
SIDE_RECIPE = "climb-v1@1"
_TASKS = {MAIN_RECIPE: TASK, SIDE_RECIPE: SIDE_TASK}


class _AgentCfg:
    """The agent-config fields the gate reads, without an rsl_rl config object."""

    def __init__(self, *, resume: bool = False, load_run: str | None = None, load_checkpoint: str | None = None):
        self.resume = resume
        self.load_run = load_run
        self.load_checkpoint = load_checkpoint


def _entry(**over) -> dict:
    entry = {"status": "active", "successor": None, "retired_at": None, "reason": None}
    entry.update(over)
    return entry


def _retired(successor: str | None = "lizard/baseline") -> dict:
    return _entry(status="retired", successor=successor, retired_at="2026-09-16", reason="superseded")


def _tree(tmp: pathlib.Path, *, lines: dict, recipes: dict) -> pathlib.Path:
    """A synthetic repo root whose ``rl_exp/versions`` holds both index halves."""
    root = tmp / "repo"
    versions = root / "rl_exp" / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    (versions / "lines.json").write_text(json.dumps({"format": 1, "lines": lines}), encoding="utf-8")
    (versions / "recipes.json").write_text(
        json.dumps(
            {
                "format": 1,
                "recipes": {
                    key: {
                        "line": line,
                        "env_cfg_entry": "pkg.mod:Cfg",
                        "agent_entry": "pkg.mod:Agent",
                        "legacy_task_version": None,
                    }
                    for key, line in recipes.items()
                },
                "tasks": {task: key for key, task in _TASKS.items() if key in recipes},
            }
        ),
        encoding="utf-8",
    )
    return root


def _active_tree(tmp: pathlib.Path) -> pathlib.Path:
    return _tree(tmp, lines={MAIN: _entry(), SIDE: _entry()}, recipes={MAIN_RECIPE: MAIN, SIDE_RECIPE: SIDE})


def _retired_tree(tmp: pathlib.Path, key: str) -> pathlib.Path:
    return _tree(tmp / key, lines={MAIN: _retired(), SIDE: _entry()}, recipes={MAIN_RECIPE: MAIN, SIDE_RECIPE: SIDE})


def _gate(tmp: pathlib.Path, **over):
    """Run the gate against a directory; ``root`` is how a case moves the read."""
    directory = over.pop("directory", None) or _active_tree(tmp)
    kwargs = {
        "task": TASK,
        "argv": ["train.py", "--task", TASK],
        "agent_cfg": _AgentCfg(),
        "root": directory,
    }
    declared_line = over.pop("declared_line", None)
    if declared_line is not None:
        kwargs["declared_line"] = declared_line
    kwargs.update(over)
    return lifecycle.startup_check(**kwargs)


def main() -> int:
    """Run every case; each one asserts a rule that would otherwise rot unenforced."""
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = pathlib.Path(tmp_dir)
        failures.extend(_identity_cases(tmp))
        failures.extend(_retired_cases(tmp))
        failures.extend(_flag_cases(tmp))
        failures.extend(_trainer_cases(tmp))

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        print(f"lifecycle startup gate: {len(failures)} case(s) wrong")
        return 1
    print("  refusals fired, refusals left evidence, and a refused record verifies as one")
    print("LIFECYCLE_STARTUP_OK")
    return 0


def _identity_cases(tmp: pathlib.Path) -> list[str]:
    """Identity comes from the directory, and every missing piece refuses."""
    problems: list[str] = []
    verdict, evidence = _gate(tmp)
    if not (
        verdict.allowed
        and evidence["line"] == MAIN
        and evidence["recipe"] == MAIN_RECIPE
        and evidence["status"] == "active"
    ):
        problems.append(f"an active line must proceed with its identity recorded: {verdict!r} {evidence!r}")

    invented = _active_tree(tmp / "invented")
    verdict, _ = _gate(tmp, directory=invented, task="Lizard-Invented-v99")
    if verdict.allowed or "not in the recipe map" not in verdict.reason:
        problems.append(f"a task with no recipe must be refused, got {verdict!r}")

    dangling = _tree(tmp / "dangling", lines={MAIN: _entry()}, recipes={MAIN_RECIPE: "lizard/ghost"})
    verdict, _ = _gate(tmp, directory=dangling)
    if verdict.allowed or "no lifecycle entry" not in verdict.reason:
        problems.append(f"a line with no lifecycle entry must not read as active, got {verdict!r}")

    mangled = tmp / "mangled" / "repo"
    (mangled / "rl_exp" / "versions").mkdir(parents=True)
    (mangled / "rl_exp" / "versions" / "recipes.json").write_text("{}", encoding="utf-8")
    verdict, _ = _gate(tmp, directory=mangled)
    if verdict.allowed or "not usable" not in verdict.reason:
        problems.append(f"an unreadable index must refuse, got {verdict!r}")

    # two answers to "which line is this" cannot both be describing this launch
    verdict, _ = _gate(tmp, declared_line=SIDE)
    if verdict.allowed or "identity disagreement" not in verdict.reason:
        problems.append(f"a declared line that contradicts the map must be refused, got {verdict!r}")
    verdict, _ = _gate(tmp, declared_line=MAIN)
    if not verdict.allowed:
        problems.append(f"a declared line that agrees with the map must proceed, got {verdict!r}")

    # ``root`` is what moves the read, and the record says which directory answered
    fixture = _tree(tmp / "fixture", lines={MAIN: _entry()}, recipes={MAIN_RECIPE: MAIN})
    _, relocated = _gate(tmp, directory=fixture)
    if relocated["directory_sha256"] != lifecycle.read_index(fixture)["digests"]:
        problems.append("the directory named by root must be the one read, digests included")
    if relocated["directory_sha256"] == lifecycle.read_index(_REPO)["digests"]:
        problems.append("the relocated read must not silently read this checkout instead")
    return problems


def _retired_cases(tmp: pathlib.Path) -> list[str]:
    """The 2.2 table, on a synthetic retired line and on the real one."""
    problems: list[str] = []
    retired = _retired_tree(tmp, "retired")

    verdict, _ = _gate(tmp, directory=retired)
    if verdict.allowed or "refusing new_train" not in verdict.reason:
        problems.append(f"new work on a retired line must be refused, got {verdict!r}")

    verdict, _ = _gate(tmp, directory=retired, agent_cfg=_AgentCfg(resume=True))
    if verdict.allowed or "refusing resume" not in verdict.reason:
        problems.append(f"a resume on a retired line must be refused, got {verdict!r}")

    # the real line: no fixture stands in for it, and no successor is registered for it
    verdict, evidence = lifecycle.startup_check(
        task=SIDE_TASK,
        argv=["train.py", "--task", SIDE_TASK],
        agent_cfg=_AgentCfg(),
        root=_REPO,
    )
    if verdict.allowed or evidence["status"] != "retired" or evidence["line"] != SIDE:
        problems.append(f"the real retired line must refuse with its identity: {verdict!r} {evidence!r}")
    if "successor" in verdict.reason:
        problems.append(f"the refusal must not promise a successor the index does not register: {verdict!r}")
    return problems


def _flag_cases(tmp: pathlib.Path) -> list[str]:
    """The curriculum flag is refused where it cannot mean anything, both spellings alike."""
    problems: list[str] = []
    for spelling in ("--drop_curriculum_state", "--weights_only"):
        verdict, evidence = _gate(tmp, argv=["train.py", spelling])
        if verdict.allowed or "cold start" not in verdict.reason:
            problems.append(f"{spelling} without a resume must be refused, got {verdict!r}")
        if not evidence["drop_curriculum_state"]:
            problems.append(f"{spelling} must be recorded as the curriculum drop it is: {evidence!r}")

        verdict, evidence = _gate(tmp, agent_cfg=_AgentCfg(resume=True), argv=["train.py", "--resume", spelling])
        if not verdict.allowed:
            problems.append(f"{spelling} with a resume must proceed, got {verdict!r}")
        if not evidence["drop_curriculum_state"]:
            problems.append(f"{spelling} with a resume must be recorded: {evidence!r}")

    if not lifecycle.flag_in(["train.py", "--drop_curriculum_state=true"], "--drop_curriculum_state"):
        problems.append("an =true spelling of a flag must count as the flag")
    if lifecycle.flag_in(["train.py", "--drop_curriculum_state_typo"], "--drop_curriculum_state"):
        problems.append("a flag whose name only starts the same must not count")
    return problems


def _trainer_cases(tmp: pathlib.Path) -> list[str]:
    """The trainer-side half: ``begin`` records the verdict, and a refusal is raised *and* recorded.

    ``begin`` is the trainer's own call site (the fork patch calls it before ``gym.make``), so
    these cases run it for real, with a synthetic directory patched in -- the real retired line
    cannot be launched here (that is a real process, ``lifecycle_entry_run.py --track trainer``).
    The dirty-tree override is set because this checkout is dirty while the change is being
    written; it is the documented way to say so and it has its own tests.
    """
    problems: list[str] = []
    os.environ["RL_ALLOW_DIRTY_TREE"] = "offline test: the gate's own cases"
    try:
        log_dir = tmp / "logs" / "active_run"
        ctx = M.begin(
            log_dir=log_dir,
            task=TASK,
            argv=["train.py", "--task", TASK],
            env_cfg=_env_cfg(),
            agent_cfg=_AgentCfg(),
        )
        manifest = json.loads(ctx.manifest_path.read_text(encoding="utf-8"))
        recorded = manifest["declaration"].get("lifecycle")
        if not recorded or recorded.get("allowed") is not True or recorded.get("line") != MAIN:
            problems.append(f"T0 must carry the lifecycle verdict verbatim, got {recorded!r}")
        if recorded and recorded.get("directory_sha256") != lifecycle.read_index()["digests"]:
            problems.append("T0 must bind the directory by content digest, not by a counter someone maintains")

        # the verdict sits inside the T1 payload: editing it afterwards is detectable
        before = M.t1_digest(manifest)
        manifest["declaration"]["lifecycle"]["line"] = SIDE
        if M.t1_digest(manifest) == before:
            problems.append("editing the recorded lifecycle must change the T1 digest")

        # a refused launch: the verdict reaches T0, then the launch stops
        refused = _retired_tree(tmp, "refused")
        live_read_index = lifecycle.read_index
        lifecycle.read_index = lambda *a, **k: live_read_index(refused)
        refused_log = tmp / "logs" / "refused_run"
        try:
            try:
                M.begin(
                    log_dir=refused_log,
                    task=TASK,
                    argv=["train.py", "--task", TASK],
                    env_cfg=_env_cfg(),
                    agent_cfg=_AgentCfg(),
                )
            except RuntimeError as err:
                if "refused to start" not in str(err):
                    problems.append(f"a refusal must say it refused, got {err}")
            else:
                problems.append("a retired line must refuse the launch before anything is built")
            written = json.loads((refused_log / M.MANIFEST_NAME).read_text(encoding="utf-8"))
            verdict = written["declaration"].get("lifecycle") or {}
            if verdict.get("allowed") is not False or "retired line" not in (verdict.get("reason") or ""):
                problems.append(f"a refused launch must leave its verdict in T0, got {verdict!r}")
            if not written.get("failures"):
                problems.append("a refused launch must record the refusal, not only raise it")
        finally:
            lifecycle.read_index = live_read_index

        problems.extend(_verify_cases(refused_log))
    finally:
        os.environ.pop("RL_ALLOW_DIRTY_TREE", None)
    return problems


def _verify_cases(refused_dir: pathlib.Path) -> list[str]:
    """What ``verify`` must say about a refusal, and what must stay a failure.

    The refused directory is a *real* record produced by ``begin`` above, not a hand-written
    manifest: the claim is that the recorder's own output verifies, and a fixture would prove a
    different claim.
    """
    problems: list[str] = []
    rows, blocking = M.verify(refused_dir)
    if blocking:
        problems.append(f"a refused launch must not verify as broken: {blocking}")
    if not any("refused at T0" in row.get("detail", "") for row in rows):
        problems.append(f"verify must report the refusal: {[row['detail'] for row in rows]}")
    if not any(row.get("result") == "通过" for row in rows):
        problems.append(f"the refusal row must be a pass, not a gap: {rows}")

    cases = [
        # a refusal is a pass; a refusal next to training stages is not a refusal at all
        ("refusal", {"stages": {"pre_make": {}}, "failures": ["refused to start: retired line"]},
         "通过", False),
        ("refusal with training stages",
         {"stages": {"pre_make": {}, "ready_to_learn": {}}, "failures": ["refused to start: retired line"]},
         "失败", True),
        ("mid-run failure", {"stages": {"pre_make": {}}, "failures": ["T1 never froze"]}, "失败", True),
    ]
    for label, tail, expected, blocking_expected in cases:
        manifest = {"declaration": {"lifecycle": {"allowed": False, "reason": "retired line"}}, **tail}
        raised: list[str] = []
        rows = M._verify_lifecycle(manifest, raised)
        if rows[0]["result"] != expected:
            problems.append(f"verify row ({label}): expected {expected}, got {rows[0]!r}")
        if bool(raised) != blocking_expected:
            problems.append(f"verify row ({label}): blocking={bool(raised)}, expected {blocking_expected}")

    plain = [
        ("no verdict recorded", None, "未知", False),
        ("invented status", {"allowed": True, "status": "deprecated"}, "失败", True),
    ]
    for label, evidence, expected, blocking_expected in plain:
        manifest = {"declaration": {"lifecycle": evidence}} if evidence is not None else {"declaration": {}}
        raised = []
        rows = M._verify_lifecycle(manifest, raised)
        if rows[0]["result"] != expected:
            problems.append(f"verify row ({label}): expected {expected}, got {rows[0]!r}")
        if bool(raised) != blocking_expected:
            problems.append(f"verify row ({label}): blocking={bool(raised)}, expected {blocking_expected}")

    live = lifecycle.read_index()
    recorded = {
        "allowed": True,
        "status": "active",
        "line": MAIN,
        "directory_sha256": {"lines": "moved-on", "recipes": "moved-on"},
    }
    raised = []
    rows = M._verify_lifecycle({"declaration": {"lifecycle": recorded}}, raised)
    if rows[0]["result"] != "未知" or raised or rows[0]["required"]:
        problems.append(f"a moved directory is a note, not a block and not a pass: {rows[0]!r}")

    recorded["directory_sha256"] = live["digests"]
    raised = []
    rows = M._verify_lifecycle({"declaration": {"lifecycle": recorded}}, raised)
    if rows[0]["result"] != "通过" or raised:
        problems.append(f"an unchanged directory must confirm the recorded verdict: {rows[0]!r}")
    return problems


def _env_cfg():
    """A minimal env cfg: the fields the T0 declaration reads, and a declared recipe line."""

    class _Cfg:
        params_version = "v14"
        params_line = MAIN
        seed = 42
        decimation = 4

        class sim:  # noqa: N801 - the shape the record reads
            dt = 0.005

        class scene:  # noqa: N801
            num_envs = 64

    return _Cfg()


if __name__ == "__main__":
    sys.exit(main())
